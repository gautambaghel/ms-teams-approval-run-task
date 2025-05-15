terraform {
  cloud {
    organization = "tfc-integration-sandbox"

    workspaces {
      project = "Azure"
      name    = "azure-workspace02"
    }
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "4.18.0"
    }
    tfe = {
      source  = "hashicorp/tfe"
      version = "0.65.2"
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
