variable "run_task_teams_webhook_url" {
  description = "The URL of the Teams Incoming Webhook to post to."
  type        = string
}

variable "tfc_organization_name" {
  description = "The name of the TFC organization."
  type        = string
}

variable "location" {
  description = "The Azure region in which the resources will be created."
  type        = string
  default     = "East US"
}

variable "create_resource_group" {
  description = "Whether to create a new resource group."
  type        = bool
  default     = false

}
variable "resource_group" {
  description = "The name of the resource group in which the resources will be created."
  type        = string
  default     = "run-task-rg"
}

variable "create_network_resources" {
  description = "Whether to create new network resources."
  type        = bool
  default     = false
}

variable "virtual_network" {
  description = "The name of the virtual network in which the resources will be created."
  type        = string
  default     = "run-task-vnet"
}

variable "subnet" {
  description = "The name of the subnet in which the resources will be created."
  type        = string
  default     = "run-task-subnet"
}

variable "vnet_prefixes" {
  description = "The address prefixes to use for the vnet."
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "subnet_address_prefixes" {
  description = "The address prefixes to use for the subnet."
  type        = list(string)
  default     = ["10.0.0.0/23"]
}

variable "run_task_container_image" {
  description = "The container image to use for the run task."
  type        = string
  default     = "teams-approval-run-task:latest"
}

variable "run_task_container_registry" {
  description = "The container registry to use for the run task."
  type        = string
  default     = "quay.io/hashicorp-dev"
}

variable "run_task_hmac_key" {
  description = "The HMAC key to verify incoming requests are valid and correct"
  type        = string
  default     = ""
}

variable "filter_speculative_plans_only" {
  description = "Whether to only filter speculative plans."
  type        = bool
  default     = false
}

variable "use_private_registry" {
  description = "Whether to use a private registry."
  type        = bool
  default     = false
}

variable "private_container_registry" {
  description = "The container registry to use for the run task."
  type        = string
  default     = "quay.io"
}

variable "private_container_registry_username" {
  description = "The username for the private container registry."
  type        = string
  default     = ""
}

variable "private_container_registry_password" {
  description = "The password for the private container registry."
  type        = string
  default     = ""
  sensitive   = true
}
