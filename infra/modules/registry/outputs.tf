output "login_server" {
  value = azurerm_container_registry.main.login_server
}

output "admin_username" {
  value = azurerm_container_registry.main.admin_username
}

output "admin_password" {
  value     = azurerm_container_registry.main.admin_password
  sensitive = true
}
