terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "4.18.0"
    }
  }
}

provider "azurerm" {
  features {}
  resource_provider_registrations = "core"
  resource_providers_to_register = [
    "Microsoft.Cache",
    "Microsoft.App", # Required for Container Apps
  ]
}

locals {
  container_image = "${var.run_task_container_registry}/${var.run_task_container_image}"
}

data "azurerm_resource_group" "run_task" {
  name = var.resource_group
}

data "azurerm_subnet" "run_task" {
  name                 = var.subnet
  virtual_network_name = var.virtual_network
  resource_group_name  = data.azurerm_resource_group.run_task.name
}

resource "azurerm_user_assigned_identity" "run_task" {
  location            = data.azurerm_resource_group.run_task.location
  resource_group_name = data.azurerm_resource_group.run_task.name
  name                = "teams-approval-run-task-identity"
}

resource "azurerm_redis_cache" "run_task" {
  name                 = "hcp-tf-run-task-cache"
  location             = data.azurerm_resource_group.run_task.location
  resource_group_name  = data.azurerm_resource_group.run_task.name
  capacity             = 0
  family               = "C"
  sku_name             = "Standard"
  non_ssl_port_enabled = false
  minimum_tls_version  = "1.2"
  identity {
    type = "UserAssigned"
    identity_ids = [
      azurerm_user_assigned_identity.run_task.id,
    ]
  }

  redis_configuration {
  }
}

# Log Analytics workspace for Container Apps
resource "azurerm_log_analytics_workspace" "run_task" {
  name                = "teams-approval-run-task-logs"
  location            = data.azurerm_resource_group.run_task.location
  resource_group_name = data.azurerm_resource_group.run_task.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# Container Apps Environment
resource "azurerm_container_app_environment" "run_task" {
  name                       = "teams-approval-run-task-env"
  location                   = data.azurerm_resource_group.run_task.location
  resource_group_name        = data.azurerm_resource_group.run_task.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.run_task.id

  infrastructure_subnet_id = data.azurerm_subnet.run_task.id
}

# Container App
resource "azurerm_container_app" "run_task" {
  name                         = "teams-approval-run-task"
  container_app_environment_id = azurerm_container_app_environment.run_task.id
  resource_group_name          = data.azurerm_resource_group.run_task.name
  revision_mode                = "Single"

  identity {
    type = "UserAssigned"
    identity_ids = [
      azurerm_user_assigned_identity.run_task.id,
    ]
  }

  template {
    container {
      name   = "teams-approval-run-task"
      image  = local.container_image
      cpu    = "1.0"
      memory = "2Gi"

      env {
        name  = "REDIS_URL"
        value = "rediss://${azurerm_redis_cache.run_task.hostname}:${azurerm_redis_cache.run_task.ssl_port}"
      }
      env {
        name  = "BASE_PUBLIC_URL"
        value = var.run_task_base_public_url
      }
      env {
        name  = "FILTER_SPECULATIVE_PLANS_ONLY"
        value = var.filter_speculative_plans_only
      }
      env {
        name        = "REDIS_PASSWORD"
        secret_name = "redis-password"
      }
      env {
        name        = "TEAMS_WEBHOOK_URL"
        secret_name = "teams-webhook-url"
      }
      env {
        name        = "HMAC_KEY"
        secret_name = "hmac-key"
      }
    }

    min_replicas = 3
    max_replicas = 5

    http_scale_rule {
      name                = "http-rule"
      concurrent_requests = 100
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  secret {
    name  = "redis-password"
    value = azurerm_redis_cache.run_task.primary_access_key
  }

  secret {
    name  = "teams-webhook-url"
    value = var.run_task_teams_webhook_url
  }

  secret {
    name  = "hmac-key"
    value = var.run_task_hmac_key
  }


}

output "container_image" {
  value = local.container_image
}

output "default_domain_url" {
  value = "https://${azurerm_container_app.run_task.latest_revision_fqdn}"
}
