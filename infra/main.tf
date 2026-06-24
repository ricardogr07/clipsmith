data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "main" {
  name     = "${var.resource_group_name}-${var.environment}"
  location = var.location
}

resource "azurerm_user_assigned_identity" "github_runner" {
  name                = "clipsmith-github-runner-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
}

resource "azurerm_role_assignment" "github_contributor" {
  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github_runner.principal_id
}

module "storage" {
  source              = "./modules/storage"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
}

module "registry" {
  source              = "./modules/registry"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
}

module "keyvault" {
  source              = "./modules/keyvault"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  aci_sp_object_id    = var.aci_sp_object_id
  mi_object_id        = azurerm_user_assigned_identity.github_runner.principal_id
  secrets             = var.secrets
}
