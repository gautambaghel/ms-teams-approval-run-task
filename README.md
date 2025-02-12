# HCP Terraform MS Teams Approval Integration

This application serves as a run task integration between HCP Terraform/Terraform Enterprise and Microsoft Teams, enabling approval workflows for Terraform runs directly through Teams notifications.

![HCP Terraform Teams Approval Workflow](images/pre-plan-approval.gif)

## Features

- Receives run task webhooks from HCP Terraform/Terraform Enterprise
- Posts interactive approval messages to MS Teams channels
- Supports approval/rejection via clickable links in Teams
- Optional Redis integration for distributed deployments
- HMAC request verification for security
- Containerized deployment using Red Hat UBI base image
- Example Infrastructure as Code deployment to Azure Container Apps (can be adapted for other platforms)
- Optional filtering for speculative plans only
- Auto-approval for non-speculative runs when filtering is enabled

## Prerequisites

- Python 3.12+
- Microsoft Teams webhook URL
- HCP Terraform/Terraform Enterprise account with run tasks enabled
- (Optional) Redis instance for distributed deployments
- Container hosting platform of your choice (example provided for Azure Container Apps)

## Configuration

The application uses environment variables for configuration:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TEAMS_WEBHOOK_URL` | MS Teams incoming webhook URL | Yes | - |
| `BASE_PUBLIC_URL` | Public URL where the app is accessible | Yes | - |
| `HMAC_KEY` | Secret key for HMAC verification | No* | - |
| `REDIS_URL` | Redis connection URL | No | - |
| `REDIS_PASSWORD` | Redis authentication password | No | - |
| `FILTER_SPECULATIVE_PLANS_ONLY` | Only require approval for speculative plans | No | false |

*While HMAC_KEY is optional, it's strongly recommended for production deployments.

## Deployment Options

This application can be deployed in several ways:

### Direct Python Execution

The simplest deployment method, suitable for development, testing, or simple environments:

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export TEAMS_WEBHOOK_URL="your-teams-webhook-url"
export BASE_PUBLIC_URL="http://localhost:8080"
# Optional: Enable speculative plan filtering
export FILTER_SPECULATIVE_PLANS_ONLY="true"
```

4. Run the application:
```bash
# Development server
python app.py

# Production server
gunicorn --bind 0.0.0.0:8080 app:app
```

### Containerized Deployment (Recommended for Production)

Containerization is the recommended approach for production deployments as it provides:
- Consistent runtime environment
- Easy scaling and management
- Platform independence
- Simple deployment to container orchestration platforms

Build the container:
```bash
podman build -t terraform-teams-integration .
```

Run the container:
```bash
podman run -p 8080:8080 \
  -e TEAMS_WEBHOOK_URL="your-teams-webhook-url" \
  -e BASE_PUBLIC_URL="your-public-url" \
  terraform-teams-integration
```

### Production Platform Deployment

The application can be deployed to any platform that supports Python applications or containerized workloads. This repository includes an example deployment to Azure Container Apps using Terraform, but the application can be adapted to run on other platforms such as:

- Cloud container services (AWS ECS, Google Cloud Run)
- Kubernetes clusters
- Traditional VM or bare metal hosts
- Platform-as-a-Service providers

#### Example: Azure Container Apps Deployment

The included Terraform configuration demonstrates deployment to Azure Container Apps:

- Creates an Azure Container App Environment
- Deploys Redis Cache for state management
- Sets up Log Analytics for monitoring
- Configures secure secret management
- Establishes auto-scaling rules

Deploy using Terraform:
```bash
terraform init
terraform plan
terraform apply
```

### Example Deployment Configuration

The included Azure Container Apps Terraform configuration requires these variables:

- `resource_group`
- `virtual_network`
- `subnet`
- `teams_webhook_url`
- `run_task_container_registry`
- `run_task_container_image`
- `run_task_domain_suffix`
- `run_task_hmac_key`

When deploying to other platforms, you'll need to adapt the infrastructure code to your chosen platform's requirements while ensuring:

1. The container is accessible via HTTPS
2. Environment variables are properly configured
3. Redis is available if distributed deployment is needed
4. Proper monitoring and logging are set up

## API Endpoints

### POST /teams-approval
Receives run task webhooks from HCP Terraform/Terraform Enterprise.

Full API and data model is documented in the [HashiCorp Run Task API documentation](https://developer.hashicorp.com/terraform/cloud-docs/integrations/run-tasks)

Request body example:
```json
{
  "access_token": "<ephemeral_token>",
  "task_result_callback_url": "<callback URL>",
  "run_id": "run-ABC123",
  "run_created_by": "jdoe",
  "is_speculative": false,
  "workspace_name": "my-workspace",
  "stage": "pre-plan",
  "run_message": "Triggered via UI",
  "vcs_pull_request_url": "...",
  "vcs_commit_url": "...",
  "workspace_app_url": "..."
}
```

Teams message format:
```
Workspace **my-workspace** has requested approval.
Run ID: **run-ABC123**
Stage: **pre-plan**
Speculative: **Yes**
Triggered by: **jdoe**
Run Message: Example message
[Open Workspace](workspace_url)
[View Pull Request](pr_url)
[Approve](approve_url) | [Reject](reject_url)
```

### GET /approve
Endpoint for approving Terraform runs.

Query parameters:
- `run_id`: The ID of the run to approve

### GET /reject
Endpoint for rejecting Terraform runs.

Query parameters:
- `run_id`: The ID of the run to reject

## Security Considerations

1. HMAC Verification:
   - Enable HMAC verification by setting the `HMAC_KEY` environment variable
   - HCP Terraform/Terraform Enterprise will sign requests with this key
   - Requests without valid signatures will be rejected

2. Ephemeral Tokens:
   - Access tokens from Terraform are stored temporarily (10 minute TTL)
   - Tokens are removed after use
   - Redis enables secure token storage in distributed deployments

3. TLS:
   - Always deploy behind TLS in production
   - Azure Container Apps provides TLS termination
   - Redis connections use TLS by default

## Monitoring and Logging

- Application logs are sent to stdout/stderr
- Platform-specific monitoring options:
  - When using Azure (example deployment):
    - Logs are collected by Log Analytics
    - Container App metrics are available
    - Redis Cache metrics are monitored
  - Other platforms:
    - Use your platform's native monitoring solutions
    - Consider using cloud-native logging aggregation
    - Monitor Redis metrics if using distributed deployment

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

Mozilla Public License Version 2.0