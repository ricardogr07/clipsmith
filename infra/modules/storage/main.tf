resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_storage_account" "main" {
  name                     = "clipsmith${var.environment}${random_string.suffix.result}"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_share" "work" {
  name                 = "clipsmith-work"
  storage_account_name = azurerm_storage_account.main.name
  quota                = 100
}

resource "azurerm_storage_share" "out" {
  name                 = "clipsmith-out"
  storage_account_name = azurerm_storage_account.main.name
  quota                = 50
}
