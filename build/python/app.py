import os
import requests
import hmac
import hashlib

from flask import Flask, request, jsonify

#
# Optional Redis Setup
#
try:
    import redis
except ImportError:
    redis = None

REDIS_URL = os.environ.get("REDIS_URL")  # e.g. "redis://some-redis-host:6379/0"
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")  # your secret auth key
REDIS_ENABLED = False
redis_client = None

if REDIS_URL and redis is not None:
    try:
        # If a password is supplied, pass it to the Redis client
        if REDIS_PASSWORD:
            redis_client = redis.Redis.from_url(REDIS_URL, password=REDIS_PASSWORD)
        else:
            redis_client = redis.Redis.from_url(REDIS_URL)

        # Test connection
        redis_client.ping()
        REDIS_ENABLED = True
        print(f"Using Redis for token storage: {REDIS_URL}")
    except Exception as e:
        print(f"Failed to connect to Redis ({REDIS_URL}): {e}")
        print("Falling back to in-memory storage.")
else:
    print("Redis not configured or redis library not available. Using in-memory storage.")

#
# In-Memory Fallback Store
#
pending_callbacks_memory = {}

#
# Helper functions to store/retrieve/remove ephemeral data
#
def store_token(run_id, data, ttl_seconds=600):
    """
    Stores data (dict) for the given run_id (including access_token, callback_url).
    If Redis is enabled, store with a TTL. Otherwise, store in local dictionary.
    """
    if REDIS_ENABLED and redis_client:
        import json
        redis_client.setex(run_id, ttl_seconds, json.dumps(data))
    else:
        pending_callbacks_memory[run_id] = data

def get_token(run_id):
    """
    Retrieves data for a given run_id from Redis or memory.
    Returns a dict or None if not found.
    """
    if REDIS_ENABLED and redis_client:
        import json
        raw = redis_client.get(run_id)
        if raw is None:
            return None
        return json.loads(raw)
    else:
        return pending_callbacks_memory.get(run_id)

def remove_token(run_id):
    """
    Removes data for a given run_id from Redis or memory.
    """
    if REDIS_ENABLED and redis_client:
        redis_client.delete(run_id)
    else:
        if run_id in pending_callbacks_memory:
            del pending_callbacks_memory[run_id]

#
# Flask App
#
app = Flask(__name__)

# 1) Teams Incoming Webhook (replace with your actual URL or set as environment variable)
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")

# 2) Your public base URL (where Teams can link to /approve or /reject)
BASE_PUBLIC_URL = os.environ.get("BASE_PUBLIC_URL", "")

# 3) HMAC key for request verification
HMAC_KEY = os.environ.get("HMAC_KEY", "")

# If no HMAC key, log a warning at startup (but do NOT enforce)
if not HMAC_KEY:
    print("WARNING: No HMAC_KEY configured. HMAC signature verification is DISABLED.")

@app.before_request
def verify_hmac():
    """
    Enforce these rules on POST /run-task-check:
      - If BOTH sides have HMAC, we validate.
      - If NEITHER side has HMAC, skip validation (allow).
      - If incoming signature but no local key => reject (403).
      - If local key but no incoming signature => reject (403).
    """
    if request.path == "/run-task-check" and request.method == "POST":
        local_key_configured = bool(HMAC_KEY)
        inbound_signature = request.headers.get("X-Tfc-Task-Signature")
        inbound_has_hmac = bool(inbound_signature)

        # CASE 1: both sides have HMAC
        if inbound_has_hmac and local_key_configured:
            provided_signature = inbound_signature.strip()
            raw_body = request.get_data()
            computed_signature = hmac.new(
                key=HMAC_KEY.encode("utf-8"),
                msg=raw_body,
                digestmod=hashlib.sha512
            ).hexdigest()

            if not hmac.compare_digest(computed_signature, provided_signature):
                print("Invalid HMAC signature")
                return "Invalid HMAC signature", 403

            print("Valid HMAC signature")
            return  # Valid HMAC, so continue

        # CASE 2: neither side has HMAC
        elif not inbound_has_hmac and not local_key_configured:
            return  # No HMAC on either side, so skip validation

        # CASE 3: inbound has HMAC, local doesn’t
        elif inbound_has_hmac and not local_key_configured:
            return ("An HMAC signature was provided, but no local key is configured. "
                    "Request is rejected."), 403

        # CASE 4: local has HMAC, inbound doesn’t
        else:  # not inbound_has_hmac and local_key_configured
            return ("No HMAC signature was provided, but a local key is configured. "
                    "Request is rejected."), 403

@app.route("/run-task-check", methods=["POST"])
def run_task_check():
    """
    Terraform/HCP calls this endpoint with a JSON payload like:
      {
        "access_token": "<ephemeral_token>",
        "task_result_callback_url": "<callback URL>",
        "run_id": "run-ABC123",
        "run_created_by": "jdoe",
        "is_speculative": false,
        "run_message": "Triggered via UI",
        "vcs_pull_request_url": "...",
        "vcs_commit_url": "...",
        "workspace_app_url": "...",
        ...
      }

    Steps:
      1) Parse payload & store ephemeral data in Redis/memory.
      2) Construct a message for Teams with relevant links & info.
      3) POST that message to the Teams Incoming Webhook.
      4) Return 200 so Terraform/HCP doesn't retry.
    """
    try:
        payload = request.get_json() or {}

        # Required ephemeral token data
        access_token = payload.get("access_token")
        callback_url = payload.get("task_result_callback_url")
        run_id = payload.get("run_id", "unknown-run-id")

        if not access_token or not callback_url:
            return "Missing 'access_token' or 'task_result_callback_url'", 400

        # Additional metadata
        run_created_by = payload.get("run_created_by", "")
        is_speculative = payload.get("is_speculative")  # bool
        run_message = payload.get("run_message", "")

        # Links
        vcs_pull_request_url = payload.get("vcs_pull_request_url")
        vcs_commit_url = payload.get("vcs_commit_url")
        workspace_app_url = payload.get("workspace_app_url")

        # Store ephemeral data
        store_token(run_id, {
            "access_token": access_token,
            "callback_url": callback_url
        })

        # Build Approve/Reject links
        approve_link = f"{BASE_PUBLIC_URL}/approve?run_id={run_id}"
        reject_link = f"{BASE_PUBLIC_URL}/reject?run_id={run_id}"

        # Build the message body (Markdown)
        message_lines = []
        message_lines.append(f"Terraform/HCP Run ID: **{run_id}** needs approval.")

        if run_created_by:
            message_lines.append(f"Triggered by: **{run_created_by}**")

        if is_speculative is not None:
            spec_label = "Yes" if is_speculative else "No"
            message_lines.append(f"Speculative?: **{spec_label}**")

        if run_message:
            message_lines.append(f"Run Message: {run_message}")

        if workspace_app_url:
            message_lines.append(f"[Open Workspace]({workspace_app_url})")

        # If there's a PR URL, prioritize that, else commit URL
        if vcs_pull_request_url:
            message_lines.append(f"[View Pull Request]({vcs_pull_request_url})")
        elif vcs_commit_url:
            message_lines.append(f"[View Commit]({vcs_commit_url})")

        # Finally, add Approve/Reject
        message_lines.append(f"[Approve]({approve_link}) | [Reject]({reject_link})")

        teams_message = {
            "text": "\n\n".join(message_lines)
        }

        # POST to Teams
        resp = requests.post(TEAMS_WEBHOOK_URL, json=teams_message)
        resp.raise_for_status()
        print(f"Posted message to Teams for Run ID: {run_id}")
        return "Run task received. Posted message to Teams.", 200

    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route("/approve", methods=["GET"])
def approve():
    """
    When user clicks "Approve" in Teams, their browser goes to:
      GET /approve?run_id=<RUN_ID>
    Steps:
      1) Lookup ephemeral token & callback URL in Redis/memory.
      2) PATCH Terraform/HCP with status='passed'.
      3) Return a message to the user.
    """
    run_id = request.args.get("run_id")
    if not run_id:
        return "Missing 'run_id' parameter", 400

    data = get_token(run_id)
    if not data:
        return ("No pending run task for this run_id. Possibly "
                "already finalized or expired."), 404

    access_token = data["access_token"]
    callback_url = data["callback_url"]

    patch_body = {
        "data": {
            "type": "task-results",
            "attributes": {
                "status": "passed",
                "message": f"Run {run_id} approved via Teams link."
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/vnd.api+json"
    }

    try:
        resp = requests.patch(callback_url, json=patch_body, headers=headers)
        resp.raise_for_status()

        # Clean up
        remove_token(run_id)
        print(patch_body["data"]["attributes"]["message"])
        return f"Run {run_id} APPROVED. You can close this page."
    except Exception as e:
        return f"Error approving run: {str(e)}", 500


@app.route("/reject", methods=["GET"])
def reject():
    """
    When user clicks "Reject" in Teams, their browser goes to:
      GET /reject?run_id=<RUN_ID>
    Steps:
      1) Lookup ephemeral token & callback URL in Redis/memory.
      2) PATCH Terraform/HCP with status='failed'.
      3) Return a message to the user.
    """
    run_id = request.args.get("run_id")
    if not run_id:
        return "Missing 'run_id' parameter", 400

    data = get_token(run_id)
    if not data:
        return ("No pending run task for this run_id. Possibly "
                "already finalized or expired."), 404

    access_token = data["access_token"]
    callback_url = data["callback_url"]

    patch_body = {
        "data": {
            "type": "task-results",
            "attributes": {
                "status": "failed",
                "message": f"Run {run_id} rejected via Teams link."
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/vnd.api+json"
    }

    try:
        resp = requests.patch(callback_url, json=patch_body, headers=headers)
        resp.raise_for_status()

        # Clean up
        remove_token(run_id)
        print(patch_body["data"]["attributes"]["message"])
        return f"Run {run_id} REJECTED. You can close this page."
    except Exception as e:
        return f"Error rejecting run: {str(e)}", 500


if __name__ == "__main__":
    # For local dev or demos. For production, run e.g.:
    # gunicorn --bind 0.0.0.0:8080 app:app
    app.run(port=8080, debug=True)
