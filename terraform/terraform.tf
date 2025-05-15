resource "tfe_organization_run_task" "run_task" {
  organization = var.tfc_organization_name
  name         = "teams-approval-run-task"
  description  = "Run Task for Teams Approval"
  url          = "https://${azurerm_container_app.run_task.latest_revision_fqdn}/teams-approval"
  hmac_key     = local.hmac_key
  enabled      = true
}
