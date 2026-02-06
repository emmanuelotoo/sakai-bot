"""Debug - check announcements via Sakai REST API."""

import requests
import json
from sakai_bot.config import get_settings

settings = get_settings()
base_url = settings.sakai_base_url

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
})

# Login
print("Logging in...")
resp = session.post(
    f"{base_url}/portal/xlogin",
    data={"eid": settings.sakai_username, "pw": settings.sakai_password},
)

# Verify
resp = session.get(f"{base_url}/direct/session/current.json")
user = json.loads(resp.text)
print(f"Logged in as: {user.get('userEid')}\n")

# Get sites
resp = session.get(f"{base_url}/direct/site.json")
sites = json.loads(resp.text)
courses = sites.get("site_collection", [])
print(f"Total sites: {len(courses)}\n")

# Check announcements via REST API
print("=" * 60)
print("Checking announcements via REST API")
print("=" * 60)

# Method 1: Global announcements endpoint
print("\n--- /direct/announcement/user.json ---")
resp = session.get(f"{base_url}/direct/announcement/user.json")
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = json.loads(resp.text)
    colls = data.get("announcement_collection", [])
    print(f"Found {len(colls)} announcements")
    for ann in colls[:5]:
        print(f"  - [{ann.get('siteTitle', '?')}] {ann.get('title', '?')}")
        print(f"    Date: {ann.get('createdOn', '?')}")
else:
    print(f"Response: {resp.text[:300]}")

# Method 2: Per-site announcements
print("\n--- Per-site /direct/announcement/site/<siteId>.json ---")
for site in courses[:5]:
    site_id = site.get("id")
    title = site.get("title", "?")
    resp = session.get(f"{base_url}/direct/announcement/site/{site_id}.json")
    if resp.status_code == 200:
        data = json.loads(resp.text)
        anns = data.get("announcement_collection", [])
        if anns:
            print(f"\n  [{title}] - {len(anns)} announcements:")
            for ann in anns[:3]:
                print(f"    - {ann.get('title', '?')}")
    else:
        print(f"  [{title}] -> Status {resp.status_code}")

# Method 3: Check assignments too
print("\n" + "=" * 60)
print("Checking assignments via REST API")
print("=" * 60)

print("\n--- /direct/assignment/my.json ---")
resp = session.get(f"{base_url}/direct/assignment/my.json")
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = json.loads(resp.text)
    colls = data.get("assignment_collection", [])
    print(f"Found {len(colls)} assignments")
    for a in colls[:5]:
        print(f"  - [{a.get('context', '?')}] {a.get('title', '?')}")
else:
    print(f"Response: {resp.text[:300]}")

# Also check per-site assignments
print("\n--- Per-site assignments ---")
for site in courses[:5]:
    site_id = site.get("id")
    title = site.get("title", "?")
    resp = session.get(f"{base_url}/direct/assignment/site/{site_id}.json")
    if resp.status_code == 200:
        data = json.loads(resp.text)
        assigns = data.get("assignment_collection", [])
        if assigns:
            print(f"\n  [{title}] - {len(assigns)} assignments:")
            for a in assigns[:3]:
                print(f"    - {a.get('title', '?')} (due: {a.get('dueTimeString', '?')})")
    else:
        pass  # skip errors silently
