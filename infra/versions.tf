terraform {
  required_version = "= 1.14.1"
  backend "azurerm" {}
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "= 4.46.0" }
    azapi   = { source = "Azure/azapi", version = "= 2.7.0" }
  }
}

provider "azurerm" {
  features {}
  resource_provider_registrations = "none"
  storage_use_azuread             = true
  use_oidc                        = true
}

provider "azapi" {
  use_oidc                   = true
  skip_provider_registration = true
}
