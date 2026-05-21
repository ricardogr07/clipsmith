resource "azurerm_container_registry" "main" {
  name                = "clipsmith${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = true
}
