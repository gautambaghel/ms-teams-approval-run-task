# Terraform Cloud MS Teams Approval Integration

This application serves as a run task integration between HashiCorp Terraform Cloud/Enterprise and Microsoft Teams, enabling approval workflows for Terraform runs directly through Teams notifications.

## Features

- Receives run task webhooks from Terraform Cloud/Enterprise
- Posts interactive approval messages to MS Teams channels
- Supports approval/rejection via clickable links in Teams
- Optional Redis integration for distributed deployments
- HMAC request verification for security
- Containerized deployment using Red Hat UBI base image
- Infrastructure as Code deployment to Azure Container Apps

## Prerequisites

- Python 3.12+
- Microsoft Teams webhook URL
- Terraform Cloud/Enterprise account with run tasks enabled
- (Optional) Redis instance for distributed deployments
- Azure subscription (for deployment)

## Configuration

The application uses environment variables for configuration:

| Variable | Description | Required |
|----------|-------------|----------|
| `TEAMS_WEBHOOK_URL` | MS Teams incoming webhook URL | Yes |
| `BASE_PUBLIC_URL` | Public URL where the app is accessible | Yes |
| `HMAC_KEY` | Secret key for HMAC verification | No* |
| `REDIS_URL` | Redis connection URL | No |
| `REDIS_PASSWORD` | Redis authentication password | No |

*While HMAC_KEY is optional, it's strongly recommended for production deployments.

## Local Development

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export TEAMS_WEBHOOK_URL="your-teams-webhook-url"
export BASE_PUBLIC_URL="http://localhost:8080"
```

4. Run the development server:
```bash
python app.py
```

## Docker Build & Run

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

## Production Deployment

The application is designed to be deployed to Azure Container Apps using Terraform. The included Terraform configuration:

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

### Required Terraform Variables

- `resource_group`
- `virtual_network`
- `subnet`
- `teams_webhook_url`
- `run_task_container_registry`
- `run_task_container_image`
- `run_task_domain_suffix`
- `run_task_hmac_key`

## API Endpoints

### POST /run-task-check
Receives run task webhooks from Terraform Cloud/Enterprise.

Request body example:
```json
{
  "access_token": "<ephemeral_token>",
  "task_result_callback_url": "<callback URL>",
  "run_id": "run-ABC123",
  "run_created_by": "jdoe",
  "is_speculative": false,
  "run_message": "Triggered via UI",
  "vcs_pull_request_url": "...",
  "vcs_commit_url": "...",
  "workspace_app_url": "..."
}
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
   - Terraform Cloud/Enterprise will sign requests with this key
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
- When deployed to Azure:
  - Logs are collected by Log Analytics
  - Container App metrics are available
  - Redis Cache metrics are monitored

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License