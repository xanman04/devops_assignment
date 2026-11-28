"""Recreate the Assignment 1 demo groups through the public APIs, as the demo accounts themselves.

Every group, join, approval, ban and message goes browser-style through Discovery sign-in and the Groups API, so
the normal rules and the Groups -> Discovery checks apply and no database is written directly. Safe to repeat:
it reads the current state first and only adds what is missing. Tokens and the password are never printed.
"""
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

FIXTURE = Path(__file__).resolve().parent / "demo_groups.json"


def call(base, path, data=None, token=None, key=None, attempts=8):
    """JSON request. Retries only cold-start style failures, which these idempotent steps tolerate."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if key:
        headers["Idempotency-Key"] = key
    body = None if data is None else json.dumps(data).encode()
    for attempt in range(attempts):
        try:
            with urlopen(Request(base + path, data=body, headers=headers), timeout=40) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code != 503 or attempt == attempts - 1:
                detail = error.read(300).decode(errors="replace")
                raise RuntimeError(f"{path} returned {error.code}: {detail}") from None
        except URLError:
            if data is not None and not key or attempt == attempts - 1:
                raise RuntimeError(f"{path} could not be reached.") from None
        time.sleep(5)


def seed(discovery, groups, password):
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    events = {e["title"]: e["id"] for e in call(discovery, "/api/browse/")["events"]}
    people = {}

    def person(username):
        if username not in people:
            token = call(discovery, "/api/auth/token/", {"username": username, "password": password})["token"]
            people[username] = {"token": token, "id": call(discovery, "/api/auth/identity/", token=token)["id"]}
        return people[username]

    summary = []
    for record in records:
        owner = person(record["owner"])
        event_id = events[record["event"]]
        group = call(groups, "/api/groups/", {"event_id": event_id, "name": record["name"],
            "description": record["description"], "capacity": record["capacity"], "joining_mode": record["joining_mode"]},
            owner["token"], key=f"demo-group-{event_id}-{record['owner']}")
        base = f"/api/groups/{group['id']}"

        def members():
            return {m["user_id"] for m in call(groups, base + "/chat/", token=owner["token"])["members"]}

        def join(username):
            applicant = person(username)
            if applicant["id"] in members():
                return
            if record["joining_mode"] == "public":
                call(groups, base + "/join/", {}, applicant["token"])
                return
            call(groups, base + "/request/", {}, applicant["token"])
            pending = [r for r in call(groups, base + "/requests/", token=owner["token"])["requests"]
                       if r["applicant_id"] == applicant["id"] and r["status"] == "pending"]
            for request in pending:
                call(groups, f"/api/requests/{request['id']}/review/", {"approve": True}, owner["token"])

        # Bans first: the person asks, is let in, then is removed, which leaves room for the others.
        for ban in record["banned"]:
            banned = person(ban["user"])
            if banned["id"] not in {b["user_id"] for b in call(groups, base + "/bans/", token=owner["token"])["bans"]}:
                join(ban["user"])
                call(groups, f"{base}/members/{banned['id']}/remove/", {"ban": True, "reason": ban["reason"]}, owner["token"])
        for username in record["members"]:
            join(username)
        existing = {(m["author_id"], m["body"]) for m in call(groups, base + "/chat/", token=owner["token"])["messages"]}
        for message in record["messages"]:
            author = person(message["author"])
            if (author["id"], message["body"]) not in existing:
                call(groups, base + "/messages/", {"body": message["body"]}, author["token"])
        chat = call(groups, base + "/chat/", token=owner["token"])
        summary.append({"group_id": group["id"], "name": record["name"], "event_id": event_id,
                        "members": len(chat["members"]), "messages": len(chat["messages"]),
                        "active_bans": len(call(groups, base + "/bans/", token=owner["token"])["bans"])})
    return summary


if __name__ == "__main__":
    print(json.dumps(seed(os.environ["DISCOVERY_URL"], os.environ["GROUPS_URL"], os.environ["DEMO_ACCOUNT_PASSWORD"])))
