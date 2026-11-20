output "public_url" { value = trimsuffix(data.azurerm_storage_account.ui.primary_web_endpoint, "/") }
output "service_urls" { value = { for name in local.services : name => "https://${local.hosts[name]}" } }
output "sql_host" { value = azurerm_mssql_server.main.fully_qualified_domain_name }
output "database_names" { value = { for name in local.services : name => "${var.prefix}-${name}-db" } }
