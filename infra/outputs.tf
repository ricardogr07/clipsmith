output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "storage_account_name" {
  value = module.storage.account_name
}

output "storage_account_key" {
  value     = module.storage.account_key
  sensitive = true
}

output "work_share" {
  value = module.storage.work_share
}

output "out_share" {
  value = module.storage.out_share
}

output "acr_login_server" {
  value = module.registry.login_server
}

output "acr_admin_username" {
  value = module.registry.admin_username
}

output "acr_admin_password" {
  value     = module.registry.admin_password
  sensitive = true
}

output "key_vault_uri" {
  value = module.keyvault.vault_uri
}

output "mi_client_id" {
  value       = azurerm_user_assigned_identity.github_runner.client_id
  description = "Client ID of the User-Assigned Managed Identity — use as AZURE_CLIENT_ID in GitHub secrets and container env"
}

output "mi_resource_id" {
  value       = azurerm_user_assigned_identity.github_runner.id
  description = "Full resource ID of the MI — pass to --assign-identity in az container create"
}
