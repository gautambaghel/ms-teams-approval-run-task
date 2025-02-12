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
# Helper functions for ephemeral data
#
def store_token(run_id, data, ttl_seconds=600):
    if REDIS_ENABLED and redis_client:
        import json
        redis_client.setex(run_id, ttl_seconds, json.dumps(data))
    else:
        pending_callbacks_memory[run_id] = data

def get_token(run_id):
    if REDIS_ENABLED and redis_client:
        import json
        raw = redis_client.get(run_id)
        if raw is None:
            return None
        return json.loads(raw)
    else:
        return pending_callbacks_memory.get(run_id)

def remove_token(run_id):
    if REDIS_ENABLED and redis_client:
        redis_client.delete(run_id)
    else:
        if run_id in pending_callbacks_memory:
            del pending_callbacks_memory[run_id]


#
# Flask App
#
app = Flask(__name__)

# External config
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")
BASE_PUBLIC_URL = os.environ.get("BASE_PUBLIC_URL", "")
HMAC_KEY = os.environ.get("HMAC_KEY", "")

# Toggle for skipping or auto-approving non-speculative runs
FILTER_SPECULATIVE_PLANS_ONLY = os.environ.get("FILTER_SPECULATIVE_PLANS_ONLY", "false").lower() in ("1", "true", "yes")

# Warning if HMAC_KEY not present
if not HMAC_KEY:
    print("WARNING: No HMAC_KEY configured. HMAC signature verification is DISABLED.")

if FILTER_SPECULATIVE_PLANS_ONLY:
    print("WARNING: Filtering for speculative plans only.")


@app.before_request
def verify_hmac():
    """
    Enforce HMAC checks ONLY on the POST /teams-approval route. 
    """
    if request.path == "/teams-approval" and request.method == "POST":
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
                return "Invalid HMAC signature", 403

            return  # Valid HMAC → continue

        # CASE 2: neither side has HMAC
        elif not inbound_has_hmac and not local_key_configured:
            return  # No HMAC → continue

        # CASE 3: inbound has HMAC, local doesn’t
        elif inbound_has_hmac and not local_key_configured:
            return "Inbound signature provided, but local key is not configured.", 403

        # CASE 4: local has HMAC, inbound doesn’t
        else:  # not inbound_has_hmac and local_key_configured
            return "No HMAC signature was provided, but we require one.", 403


def patch_terraform_callback(run_id, access_token, callback_url, status, message):
    """
    A helper function to send a PATCH to Terraform’s task callback URL.
    - `status` should be one of: ["passed", "failed"] (or "canceled").
    - `message` is a short description that Terraform will log.
    """
    patch_body = {
        "data": {
            "type": "task-results",
            "attributes": {
                "status": status,
                "message": message
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/vnd.api+json"
    }

    resp = requests.patch(callback_url, json=patch_body, headers=headers)
    resp.raise_for_status()


@app.route("/teams-approval", methods=["POST"])
def teams_approval():
    """
    Terraform/HCP calls this endpoint with JSON payload including:
      {
        "access_token": "<token>",
        "task_result_callback_url": "...",
        "run_id": "...",
        "is_speculative": false,
        "workspace_name": "some-workspace",
        ...
      }
    """
    try:
        payload = request.get_json() or {}
        access_token = payload.get("access_token")
        callback_url = payload.get("task_result_callback_url")
        run_id = payload.get("run_id", "unknown-run-id")
        stage  = payload.get("stage", "unknown-stage")
        workspace = payload.get("workspace_name", "unknown-workspace")
        is_speculative = payload.get("is_speculative", False)

        if not access_token or not callback_url:
            return "Missing 'access_token' or 'task_result_callback_url'", 400

        if access_token == "test-token" and stage == "test":
            print("Received test token; ignoring.")
            return "Test token received. No action taken.", 200

        # If user wants to only require approval for SPECULATIVE runs:
        if FILTER_SPECULATIVE_PLANS_ONLY and not is_speculative:
            # Instead of 'skipping', we automatically "pass" (auto-approve) 
            # so the pipeline doesn’t get stuck.
            try:
                patch_terraform_callback(
                    run_id,
                    access_token,
                    callback_url,
                    "passed",
                    f"Run {run_id} auto-approved (non-speculative)."
                )
                print(f"Auto-approved non-speculative run {run_id} from workspace {workspace}")
                return "Auto-approved non-speculative run", 200
            except Exception as e:
                return f"Error auto-approving run: {str(e)}", 500

        # Otherwise (speculative or filter is off), proceed with manual approval flow:
        store_token(run_id, {
            "access_token": access_token,
            "callback_url": callback_url
        })

        run_created_by = payload.get("run_created_by", "")
        run_message = payload.get("run_message", "")
        vcs_pull_request_url = payload.get("vcs_pull_request_url")
        vcs_commit_url = payload.get("vcs_commit_url")
        workspace_app_url = payload.get("workspace_app_url")

        # Build Approve/Reject links
        approve_link = f"{BASE_PUBLIC_URL}/approve?run_id={run_id}"
        reject_link  = f"{BASE_PUBLIC_URL}/reject?run_id={run_id}"

        message_lines = [
            f"Workspace **{workspace}** has requested approval.",
            f"Run ID: **{run_id}**",
            f"Stage: **{stage}**",
            f"Speculative: **{'Yes' if is_speculative else 'No'}**"
        ]
        if run_created_by:
            message_lines.append(f"Triggered by: **{run_created_by}**")
        if run_message:
            message_lines.append(f"Run Message: {run_message}")
        if workspace_app_url:
            message_lines.append(f"[Open Workspace]({workspace_app_url})")
        if vcs_pull_request_url:
            message_lines.append(f"[View Pull Request]({vcs_pull_request_url})")
        elif vcs_commit_url:
            message_lines.append(f"[View Commit]({vcs_commit_url})")

        # Approve/Reject links
        message_lines.append(f"[Approve]({approve_link}) | [Reject]({reject_link})")

        teams_message = {
            "text": "\n\n".join(message_lines)
        }

        # POST to Teams
        resp = requests.post(TEAMS_WEBHOOK_URL, json=teams_message)
        resp.raise_for_status()
        print(f"Posted approval request to Teams for run {run_id}.")
        return "Run task received. Posted message to Teams.", 200

    except Exception as e:
        return f"Error in teams_approval: {str(e)}", 500


@app.route("/approve", methods=["GET"])
def approve():
    """
    Approve route: PATCH run status to "passed".
    """
    run_id = request.args.get("run_id")
    if not run_id:
        return "Missing 'run_id' parameter", 400

    data = get_token(run_id)
    if not data:
        return "No pending run task for this run_id or it has expired.", 404

    access_token = data["access_token"]
    callback_url = data["callback_url"]
    approval_message = f"Run {run_id} approved via Teams link."

    try:
        patch_terraform_callback(
            run_id,
            access_token,
            callback_url,
            "passed",
            approval_message
        )
        remove_token(run_id)
        print(approval_message)
        return f"Run {run_id} APPROVED. You can close this page."
    except Exception as e:
        return f"Error approving run: {str(e)}", 500


@app.route("/reject", methods=["GET"])
def reject():
    """
    Reject route: PATCH run status to "failed".
    """
    run_id = request.args.get("run_id")
    if not run_id:
        return "Missing 'run_id' parameter", 400

    data = get_token(run_id)
    if not data:
        return "No pending run task for this run_id or it has expired.", 404

    access_token = data["access_token"]
    callback_url = data["callback_url"]
    rejection_message = f"Run {run_id} rejected via Teams link."

    try:
        patch_terraform_callback(
            run_id,
            access_token,
            callback_url,
            "failed",
            rejection_message
        )
        remove_token(run_id)
        print(rejection_message)
        return f"Run {run_id} REJECTED. You can close this page."
    except Exception as e:
        return f"Error rejecting run: {str(e)}", 500


if __name__ == "__main__":
    app.run(port=8080, debug=True)