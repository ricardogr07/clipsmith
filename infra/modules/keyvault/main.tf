data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                = "clipsmith-${var.environment}-kv"
  resource_group_name = var.resource_group_name
  location            = var.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  access_policy {
    tenant_id          = data.azurerm_client_config.current.tenant_id
    object_id          = data.azurerm_client_config.current.object_id
    secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
  }

  access_policy {
    tenant_id          = data.azurerm_client_config.current.tenant_id
    object_id          = var.aci_sp_object_id
    secret_permissions = ["Get", "List"]
  }
}

resource "azurerm_key_vault_secret" "secrets" {
  for_each     = var.secrets
  name         = replace(each.key, "_", "-")
  value        = each.value
  key_vault_id = azurerm_key_vault.main.id
}
