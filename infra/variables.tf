variable "resource_group_name" {
  description = "Name of the Azure resource group"
  type        = string
  default     = "clipsmith-rg"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Deployment environment (dev | prod)"
  type        = string
  default     = "dev"
}

variable "aci_sp_object_id" {
  description = "Object ID of the ACI service principal that reads Key Vault secrets"
  type        = string
}

variable "secrets" {
  description = "Map of secret name to value to store in Key Vault"
  type        = map(string)
  sensitive   = true
  default     = {}
}
