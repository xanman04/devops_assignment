mock_provider "azurerm" {
  mock_data "azurerm_resource_group" {
    defaults = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test-ieu2023" }
  }
  mock_data "azurerm_storage_account" {
    defaults = { primary_web_endpoint = "https://testieu2023ui.z1.web.core.windows.net/" }
  }
  mock_resource "azurerm_container_app_environment" {
    defaults = {
      id             = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test-ieu2023/providers/Microsoft.App/managedEnvironments/test-ieu2023-env"
      default_domain = "example.westeurope.azurecontainerapps.io"
    }
  }
  mock_resource "azurerm_mssql_server" {
    defaults = {
      id                          = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test-ieu2023/providers/Microsoft.Sql/servers/test-ieu2023-sql"
      fully_qualified_domain_name = "test-ieu2023-sql.database.windows.net"
    }
  }
  mock_resource "azurerm_log_analytics_workspace" {
    defaults = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test-ieu2023/providers/Microsoft.OperationalInsights/workspaces/test-ieu2023-logs" }
  }
}
mock_provider "azapi" {}

variables {
  prefix             = "test-ieu2023"
  region             = "westeurope"
  sql_region         = "northeurope"
  ui_storage         = "testieu2023ui"
  image_namespace    = "ghcr.io/testowner"
  git_sha            = "0000000000000000000000000000000000000000"
  sql_admin_password = "Fake-only-admin-password!123"
  discovery_password = "Fake-only-discovery-password!123"
  groups_password    = "Fake-only-groups-password!123"
  discovery_secret   = "Fake-only-signing-discovery-key"
  groups_secret      = "Fake-only-signing-groups-key"
}

run "student_runtime" {
  command = plan
  assert {
    condition     = length(azurerm_container_app.service) == 2 && length(azapi_resource.database) == 2
    error_message = "Exactly two domain apps and two databases are allowed."
  }
  assert {
    condition     = alltrue([for app in azurerm_container_app.service : app.template[0].min_replicas == 0 && app.template[0].max_replicas == 1])
    error_message = "Every service must scale between zero and one replica."
  }
  assert {
    condition     = alltrue([for db in azapi_resource.database : db.body.properties.useFreeLimit && db.body.properties.freeLimitExhaustionBehavior == "AutoPause" && db.body.sku.capacity == 1 && db.body.properties.minCapacity == 0.5])
    error_message = "Student databases must use the bounded free offer, never paid overflow."
  }
  assert {
    condition     = alltrue([for db in azapi_resource.database : !contains(keys(db.body.properties), "maxSizeBytes") && !contains(keys(db.body.properties), "autoPauseDelay")])
    error_message = "Do not override the student offer's fixed storage/pause settings."
  }
  assert {
    condition     = alltrue([for app in azurerm_container_app.service : app.template[0].container[0].image == "ghcr.io/testowner/bassline-${app.template[0].container[0].name}:0000000000000000000000000000000000000000"])
    error_message = "Production images must be tagged with the tested full SHA."
  }
  assert {
    condition     = alltrue([for app in azurerm_container_app.service : length([for env in app.template[0].container[0].env : env if env.name == "DATABASE_URL" && env.secret_name == "database-url"]) == 1])
    error_message = "Database URLs must be secret references."
  }
}

run "initial_placeholder" {
  command = plan
  variables { bootstrap_mode = true }
  assert {
    condition     = alltrue([for app in azurerm_container_app.service : app.ingress[0].target_port == 80 && app.template[0].container[0].image == "mcr.microsoft.com/k8se/quickstart:latest"])
    error_message = "Initial setup uses the course placeholder until SQL identities exist."
  }
}
