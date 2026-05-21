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
