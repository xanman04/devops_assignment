"""Verify a disposable Compose/SQL Server stack, never a user's normal stack.

The project name must begin bassline-check- or bassline-ci-. No volumes are
deleted. Service tests explicitly flush only these disposable local databases.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

from check_service_boundary import request

ROOT = Path(__file__).resolve().parents[1]


def run(project, *, unit_tests=True):
    if not project.startswith(("bassline-check-", "bassline-ci-")):
        raise ValueError("Use a separate bassline-check- or bassline-ci- disposable project.")
    environment = os.environ.copy()
    environment.update(DISCOVERY_PORT="18000", GROUPS_PORT="18001", UI_PORT="18080",
                       UI_ORIGIN="http://localhost:18080")
    command = ["docker", "compose", "-p", project, "-f", str(ROOT/"docker-compose.yml")]

    def compose(*arguments, capture=False):
        result = subprocess.run(command+list(arguments), cwd=ROOT, env=environment,
                                check=True, text=True, capture_output=capture)
        return result.stdout if capture else ""

    def python(service, code):
        return compose("exec", "-T", service, "python", "-c", code, capture=True)

    discovery = "http://localhost:18000"
    groups = "http://localhost:18001"
    try:
        compose("build", "discovery", "groups")
        compose("up", "-d", "--wait", "sqlserver")
        compose("up", "--no-deps", "--exit-code-from", "db-init", "db-init")
        if unit_tests:
            for service, sources, tests in (
                ("discovery", "discovery,accounts,notifications,config", "discovery config"),
                ("groups", "groups,notifications,config", "config"),
            ):
                manifest = ROOT/"services"/service/"requirements-dev.txt"
                compose("run", "--rm", "--no-deps", "-e", "SQLSERVER_TEST_MODE=1",
                        "-e", "COVERAGE_FILE=/app/data/sqlserver.coverage",
                        "-v", str(manifest)+":/app/requirements-dev.txt:ro", service, "/bin/sh", "-c",
                        "python -m pip install --user --no-warn-script-location -r requirements-dev.txt > /tmp/test-tools.log"
                        f" && python -m coverage run --source={sources} --omit='*/migrations/*,*/test*.py'"
                        f" manage.py test {tests} --noinput && python -m coverage report --fail-under=70")
        compose("up", "-d", "--wait", "discovery", "groups", "ui")
        for service, other in (("discovery", "groups"), ("groups", "discovery")):
            verify = f"""
import os,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.db import connection,DatabaseError
assert os.getuid() != 0
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM [{other}].sys.tables')
except DatabaseError:
    pass
else:
    raise AssertionError('Cross-database access was granted')
print('Owned database isolation verified.')
"""
            print(python(service, verify).strip())
        # Credentials are generated inside Discovery and never printed by this checker.
        setup = """
import os,json,secrets,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from config.authentication import issue_token
from discovery import services
suffix=secrets.token_hex(6)
password=secrets.token_urlsafe(24)
owner=get_user_model().objects.create_superuser('compose-owner-'+suffix,password=password)
guest=get_user_model().objects.create_user('compose-guest-'+suffix,password=password)
category=services.save_category(actor=owner,data={'name':'Test-'+suffix,'color':'#123456','description':'Synthetic test'})
venue=services.save_venue(actor=owner,review_status='approved',data={'name':'Venue-'+suffix,'latitude':48,'longitude':2,'timezone':'Europe/Paris'})
start=timezone.now()+timedelta(days=2)
event=services.save_event(actor=owner,category_ids=[category.pk],data={'venue':venue,'title':'Compose test','description':'Synthetic test','starts_at':start,'ends_at':start+timedelta(hours=4)})
print(json.dumps({'event_id':event.pk,'owner':issue_token(owner.username,password),'guest':issue_token(guest.username,password)}))
"""
        fixture = json.loads(python("discovery", setup))
        data = {"event_id": fixture["event_id"], "name": "Compose group", "description": "Synthetic",
                "capacity": 4, "joining_mode": "public"}
        status, group = request(groups, "/api/groups/", data, fixture["owner"], "compose-"+str(fixture["event_id"]))
        assert status == 201, (status, group)
        group_id = group["id"]
        assert request(groups, f"/api/groups/{group_id}/join/", {}, fixture["guest"])[0] == 200
        assert request(groups, f"/api/groups/{group_id}/messages/", {"body": "Retained"}, fixture["guest"])[0] == 201
        with urlopen("http://localhost:18080/", timeout=5) as response:
            assert response.status == 200
        with urlopen("http://localhost:18080/config.js", timeout=5) as response:
            config = response.read().decode()
            assert discovery in config and groups in config
        migrations = """
import os,django,json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.db.migrations.recorder import MigrationRecorder
print(json.dumps(sorted(MigrationRecorder.Migration.objects.values_list('app','name'))))
"""
        before = {service: python(service, migrations) for service in ("discovery", "groups")}
        compose("restart", "discovery", "groups")
        for base in (discovery, groups):
            deadline = time.monotonic()+60
            while time.monotonic() < deadline:
                try:
                    if request(base, "/health")[0] == 200:
                        break
                except OSError:
                    pass
                time.sleep(.2)
            else:
                raise RuntimeError("Service failed to restart")
        for service in before:
            assert python(service, migrations) == before[service]
        status, chat = request(groups, f"/api/groups/{group_id}/chat/", token=fixture["guest"])
        assert status == 200 and len(chat["members"]) == 2 and chat["messages"][0]["body"] == "Retained"
        assert request(groups, "/api/groups/", data, fixture["owner"], "compose-"+str(fixture["event_id"]))[1]["id"] == group_id
        compose("stop", "discovery")
        assert request(groups, "/health")[0] == 200
        assert request(groups, f"/api/groups/{group_id}/")[0] == 200
        assert request(groups, f"/api/groups/{group_id}/join/", {}, fixture["guest"])[0] == 503
        compose("up", "-d", "--wait", "discovery")
        print("PASS: SQL Server suites, restricted logins, non-root images, static files/config, HTTP flow, restart/data retention and peer outage.")
    finally:
        # Retain volumes for inspection. Never wipe a DB to get tests passing.
        compose("down", "--remove-orphans")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="bassline-check-local")
    parser.add_argument("--skip-unit", action="store_true", help="Runtime-only recheck after SQL suites already passed.")
    arguments = parser.parse_args()
    run(arguments.project, unit_tests=not arguments.skip_unit)
