#!/bin/bash
set -euo pipefail
export SQLCMDPASSWORD="$(cat /run/sqladmin/password)"
discovery_password="$(cat /run/discovery/password)"
groups_password="$(cat /run/groups/password)"
for value in "$discovery_password" "$groups_password"; do
    if [[ ! "$value" =~ ^[A-Za-z0-9_-]{32,128}$ ]]; then
        echo 'Invalid local database credential format.' >&2
        exit 1
    fi
done
exec /opt/mssql-tools18/bin/sqlcmd -S sqlserver -U sa -C -b \
    -v DiscoveryPassword="$discovery_password" GroupsPassword="$groups_password" \
    -i /bootstrap/init.sql
