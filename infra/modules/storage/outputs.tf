output "account_name" { value = azurerm_storage_account.main.name }
output "account_key" {
  value     = azurerm_storage_account.main.primary_access_key
  sensitive = true
}
output "work_share" { value = azurerm_storage_share.work.name }
output "out_share"  { value = azurerm_storage_share.out.name }
