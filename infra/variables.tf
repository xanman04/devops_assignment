variable "prefix" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,19}$", var.prefix))
    error_message = "Use the confirmed IE username with dots replaced by hyphens."
  }
}

variable "region" { type = string }
variable "sql_region" { type = string }
variable "ui_storage" { type = string }
variable "image_namespace" {
  type = string
  validation {
    condition     = can(regex("^ghcr.io/[a-z0-9_.-]+$", var.image_namespace))
    error_message = "Use the lowercase GHCR owner namespace."
  }
}
variable "git_sha" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.git_sha))
    error_message = "Deployment requires the full tested commit SHA."
  }
}
variable "sql_admin_password" {
  type      = string
  sensitive = true
}
variable "discovery_password" {
  type      = string
  sensitive = true
}
variable "groups_password" {
  type      = string
  sensitive = true
}
variable "discovery_secret" {
  type      = string
  sensitive = true
}
variable "groups_secret" {
  type      = string
  sensitive = true
}

locals {
  services = toset(["discovery", "groups"])
  group    = "rg-${var.prefix}"
  passwords = {
    discovery = var.discovery_password
    groups    = var.groups_password
  }
  signing_keys = {
    discovery = var.discovery_secret
    groups    = var.groups_secret
  }
  hosts = { for name in local.services : name => "${var.prefix}-${name}.${azurerm_container_app_environment.main.default_domain}" }
  tags  = { owner = var.prefix, assignment = "bassline-2", managed_by = "terraform" }
}

variable "bootstrap_mode" {
  type        = bool
  default     = false
  description = "Initial setup only: course placeholder until contained SQL users exist."
}
