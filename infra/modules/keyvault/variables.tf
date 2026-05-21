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

variable "secrets" {
  type      = map(string)
  sensitive = true
  default   = {}
}
