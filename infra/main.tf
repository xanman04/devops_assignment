# Initial setup owns the resource group, UI/state Storage account and OIDC identity.
# This root owns only the student's runtime resources within that group.
data "azurerm_resource_group" "own" { name = local.group }
data "azurerm_storage_account" "ui" {
  name                = var.ui_storage
  resource_group_name = local.group
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.prefix}-logs"
  resource_group_name = local.group
  location            = var.region
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.1
  tags                = local.tags
  lifecycle { prevent_destroy = true }
}

resource "azurerm_container_app_environment" "main" {
  name                       = "${var.prefix}-env"
  resource_group_name        = local.group
  location                   = var.region
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.tags
  lifecycle { prevent_destroy = true }
}

resource "azurerm_mssql_server" "main" {
  name                         = "${var.prefix}-sql"
  resource_group_name          = local.group
  location                     = var.sql_region
  version                      = "12.0"
  administrator_login          = "bassline_admin"
  administrator_login_password = var.sql_admin_password
  minimum_tls_version          = "1.2"
  tags                         = local.tags
  lifecycle { prevent_destroy = true }
}

# AzAPI exposes the student free-offer flags absent from AzureRM's SQL resource.
# Never set maxSizeBytes/autoPauseDelay: the free offer controls both values.
resource "azapi_resource" "database" {
  for_each  = local.services
  type      = "Microsoft.Sql/servers/databases@2023-08-01"
  name      = "${var.prefix}-${each.key}-db"
  parent_id = azurerm_mssql_server.main.id
  location  = var.sql_region
  tags      = local.tags
  body = {
    sku = { name = "GP_S_Gen5_1", tier = "GeneralPurpose", family = "Gen5", capacity = 1 }
    properties = {
      minCapacity                      = 0.5
      useFreeLimit                     = true
      freeLimitExhaustionBehavior      = "AutoPause"
      requestedBackupStorageRedundancy = "Local"
      collation                        = "SQL_Latin1_General_CP1_CI_AS"
    }
  }
  lifecycle { prevent_destroy = true }
}

resource "azurerm_mssql_firewall_rule" "azure" {
  name             = "${var.prefix}-azure-services"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_container_app" "service" {
  for_each                     = local.services
  name                         = "${var.prefix}-${each.key}"
  resource_group_name          = local.group
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = local.tags
  secret {
    name  = "database-url"
    value = "mssql://bassline_${each.key}:${urlencode(local.passwords[each.key])}@${azurerm_mssql_server.main.fully_qualified_domain_name}:1433/${var.prefix}-${each.key}-db"
  }
  secret {
    name  = "django-key"
    value = local.signing_keys[each.key]
  }
  ingress {
    external_enabled           = true
    target_port                = var.bootstrap_mode ? 80 : 8000
    transport                  = "http"
    allow_insecure_connections = false
    traffic_weight {
      latest_revision = true
      percentage      = 100

    }
    # Intentionally no ingress CORS block: application middleware owns preflight.
  }
  template {
    min_replicas = 0
    max_replicas = 1
    container {
      name   = each.key
      image  = var.bootstrap_mode ? "mcr.microsoft.com/k8se/quickstart:latest" : "${var.image_namespace}/bassline-${each.key}:${var.git_sha}"
      cpu    = 0.25
      memory = "0.5Gi"
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"

      }
      env {
        name        = "DJANGO_SECRET_KEY"
        secret_name = "django-key"

      }
      env {
        name  = "PORT"
        value = "8000"

      }
      env {
        name  = "VERSION"
        value = var.git_sha

      }
      env {
        name  = "ALLOWED_HOSTS"
        value = "${local.hosts[each.key]},localhost,127.0.0.1"

      }
      env {
        name  = "UI_ORIGIN"
        value = trimsuffix(data.azurerm_storage_account.ui.primary_web_endpoint, "/")

      }
      dynamic "env" {
        for_each = each.key == "discovery" ? { SEED_TAXONOMY = "1", TRUST_CONTAINER_APPS_INGRESS = "1" } : { DISCOVERY_URL = "https://${local.hosts.discovery}", DISCOVERY_TIMEOUT_S = "5" }
        content {
          name  = env.key
          value = env.value
        }
      }
      startup_probe {
        transport               = "HTTP"
        port                    = var.bootstrap_mode ? 80 : 8000
        path                    = var.bootstrap_mode ? "/" : "/health"
        interval_seconds        = 10
        timeout                 = 5
        failure_count_threshold = 30
      }
      readiness_probe {
        transport               = "HTTP"
        port                    = var.bootstrap_mode ? 80 : 8000
        path                    = var.bootstrap_mode ? "/" : "/health"
        interval_seconds        = 15
        timeout                 = 5
        failure_count_threshold = 3
        success_count_threshold = 1
      }
    }
  }
  depends_on = [azapi_resource.database, azurerm_mssql_firewall_rule.azure]
  lifecycle { prevent_destroy = true }
}
