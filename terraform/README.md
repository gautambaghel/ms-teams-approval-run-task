<!-- BEGIN_TF_DOCS -->
A Terraform module to show an example deployment of this run task into the Azure Container App service.

## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_azurerm"></a> [azurerm](#requirement\_azurerm) | 4.18.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_azurerm"></a> [azurerm](#provider\_azurerm) | 4.18.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [azurerm_container_app.run_task](https://registry.terraform.io/providers/hashicorp/azurerm/4.18.0/docs/resources/container_app) | resource |
| [azurerm_container_app_environment.run_task](https://registry.terraform.io/providers/hashicorp/azurerm/4.18.0/docs/resources/container_app_environment) | resource |
| [azurerm_log_analytics_workspace.run_task](https://registry.terraform.io/providers/hashicorp/azurerm/4.18.0/docs/resources/log_analytics_workspace) | resource |
| [azurerm_redis_cache.run_task](https://registry.terraform.io/providers/hashicorp/azurerm/4.18.0/docs/resources/redis_cache) | resource |
| [azurerm_user_assigned_identity.run_task](https://registry.terraform.io/providers/hashicorp/azurerm/4.18.0/docs/resources/user_assigned_identity) | resource |
| [azurerm_resource_group.run_task](https://registry.terraform.io/providers/hashicorp/azurerm/4.18.0/docs/data-sources/resource_group) | data source |
| [azurerm_subnet.run_task](https://registry.terraform.io/providers/hashicorp/azurerm/4.18.0/docs/data-sources/subnet) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_filter_speculative_plans_only"></a> [filter\_speculative\_plans\_only](#input\_filter\_speculative\_plans\_only) | Whether to only filter speculative plans. | `bool` | `false` | no |
| <a name="input_resource_group"></a> [resource\_group](#input\_resource\_group) | The name of the resource group in which the resources will be created. | `string` | n/a | yes |
| <a name="input_run_task_base_public_url"></a> [run\_task\_base\_public\_url](#input\_run\_task\_base\_public\_url) | The publically resolvable domain name for the run task used to construct approval URLs. | `string` | n/a | yes |
| <a name="input_run_task_container_image"></a> [run\_task\_container\_image](#input\_run\_task\_container\_image) | The container image to use for the run task. | `string` | `"teams-approval-run-task:latest"` | no |
| <a name="input_run_task_container_registry"></a> [run\_task\_container\_registry](#input\_run\_task\_container\_registry) | The container registry to use for the run task. | `string` | `"quay.io/benjamin_holmes"` | no |
| <a name="input_run_task_hmac_key"></a> [run\_task\_hmac\_key](#input\_run\_task\_hmac\_key) | The HMAC key to verify incoming requests are valid and correct | `string` | n/a | yes |
| <a name="input_run_task_teams_webhook_url"></a> [run\_task\_teams\_webhook\_url](#input\_run\_task\_teams\_webhook\_url) | The URL of the Teams Incoming Webhook to post to. | `string` | n/a | yes |
| <a name="input_subnet"></a> [subnet](#input\_subnet) | The name of the subnet in which the resources will be created. | `string` | n/a | yes |
| <a name="input_virtual_network"></a> [virtual\_network](#input\_virtual\_network) | The name of the virtual network in which the resources will be created. | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_container_image"></a> [container\_image](#output\_container\_image) | n/a |
| <a name="output_default_domain_url"></a> [default\_domain\_url](#output\_default\_domain\_url) | n/a |
<!-- END_TF_DOCS -->