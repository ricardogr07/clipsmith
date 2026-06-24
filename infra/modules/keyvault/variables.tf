variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "environment" {
  type = string
}

variable "aci_sp_object_id" {
  type = string
}

variable "mi_object_id" {
  type        = string
  description = "Object ID of the User-Assigned Managed Identity (GitHub runner + persistent ACI)"
}

variable "secrets" {
  type      = map(string)
  sensitive = true
  default   = {}
}
