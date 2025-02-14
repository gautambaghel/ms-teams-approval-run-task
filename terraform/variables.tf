variable "resource_group" {
  description = "The name of the resource group in which the resources will be created."
  type        = string
}

variable "subnet" {
  description = "The name of the subnet in which the resources will be created."
  type        = string
}

variable "virtual_network" {
  description = "The name of the virtual network in which the resources will be created."
  type        = string
}

variable "run_task_teams_webhook_url" {
  description = "The URL of the Teams Incoming Webhook to post to."
  type        = string

}

variable "run_task_container_image" {
  description = "The container image to use for the run task."
  type        = string
  default     = "teams-approval-run-task:latest"
}

variable "run_task_container_registry" {
  description = "The container registry to use for the run task."
  type        = string
  default     = "quay.io/benjamin_holmes"

}

variable "run_task_hmac_key" {
  description = "The HMAC key to verify incoming requests are valid and correct"
  type        = string
}

variable "run_task_base_public_url" {
  description = "The publically resolvable domain name for the run task used to construct approval URLs."
  type        = string
}

variable "filter_speculative_plans_only" {
  description = "Whether to only filter speculative plans."
  type        = bool
  default     = false
}
