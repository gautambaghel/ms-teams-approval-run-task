locals {
  container_image = "${var.run_task_container_registry}/${var.run_task_container_image}"
  resource_group  = var.create_resource_group ? azurerm_resource_group.run_task[0].name : data.azurerm_resource_group.run_task[0].name
  subnet          = var.create_network_resources ? azurerm_subnet.run_task[0].id : data.azurerm_subnet.run_task[0].id
}

data "azurerm_resource_group" "run_task" {
  count = var.create_resource_group ? 0 : 1
  name  = var.resource_group
}

resource "azurerm_resource_group" "run_task" {
  count    = var.create_resource_group ? 1 : 0
  name     = var.resource_group
  location = var.location
}

data "azurerm_subnet" "run_task" {
  count                = var.create_network_resources ? 0 : 1
  name                 = var.subnet
  virtual_network_name = var.virtual_network
  resource_group_name  = var.create_resource_group ? azurerm_resource_group.run_task[0].name : data.azurerm_resource_group.run_task[0].name
}

resource "azurerm_virtual_network" "run_task" {
  count               = var.create_network_resources ? 1 : 0
  name                = "run-task-vnet"
  address_space       = var.vnet_prefixes
  location            = var.location
  resource_group_name = azurerm_resource_group.run_task[0].name
}

resource "azurerm_subnet" "run_task" {
  count                = var.create_network_resources ? 1 : 0
  name                 = "run-task-subnet"
  resource_group_name  = azurerm_resource_group.run_task[0].name
  virtual_network_name = azurerm_virtual_network.run_task[0].name
  address_prefixes     = var.subnet_address_prefixes
}

resource "random_string" "hmac_key" {
  length  = 16
  special = false
  upper   = false
}

locals {
  hmac_key = var.run_task_hmac_key != "" ? var.run_task_hmac_key : random_string.hmac_key.result
}

resource "azurerm_user_assigned_identity" "run_task" {
  location            = var.location
  resource_group_name = local.resource_group
  name                = "teams-approval-run-task-identity"
}

resource "azurerm_redis_cache" "run_task" {
  name                 = "hcp-tf-run-task-cache"
  location             = var.location
  resource_group_name  = local.resource_group
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
  location            = var.location
  resource_group_name = local.resource_group
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# Container Apps Environment
resource "azurerm_container_app_environment" "run_task" {
  name                       = "teams-approval-run-task-env"
  location                   = var.location
  resource_group_name        = local.resource_group
  log_analytics_workspace_id = azurerm_log_analytics_workspace.run_task.id

  infrastructure_subnet_id = local.subnet
}

# Container App
resource "azurerm_container_app" "run_task" {
  name                         = "teams-approval-run-task"
  container_app_environment_id = azurerm_container_app_environment.run_task.id
  resource_group_name          = local.resource_group
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
    value = local.hmac_key
  }

  dynamic "secret" {
    for_each = var.private_container_registry_password != "" ? [1] : []
    content {
      name  = "private-registry-password"
      value = var.private_container_registry_password
    }
  }

  dynamic "registry" {
    for_each = var.use_private_registry && var.private_container_registry != "" && var.private_container_registry_username != "" && var.private_container_registry_password != "" ? [1] : []
    content {
      server               = var.private_container_registry
      username             = var.private_container_registry_username
      password_secret_name = "private-registry-password"
    }
  }
}

output "container_image" {
  value = local.container_image
}

output "default_domain_url" {
  value = "https://${azurerm_container_app.run_task.latest_revision_fqdn}"
}

output "hmac_key" {
  value     = local.hmac_key
  sensitive = true
}
