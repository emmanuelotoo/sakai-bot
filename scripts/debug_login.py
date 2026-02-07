"""Test login with corrected username."""

import requests
import json
from bs4 import BeautifulSoup
from sakai_bot.config import get_settings

settings = get_settings()
base_url = settings.sakai_base_url

print(f"Username: '{settings.sakai_username}'")
print(f"Password: '{settings.sakai_password}'")
print()

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
})

# POST login
print("Logging in...")
resp = session.post(
    f"{base_url}/portal/xlogin",
    data={
        "eid": settings.sakai_username,
        "pw": settings.sakai_password,
    },
    headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": base_url,
        "Referer": f"{base_url}/portal",
    },
)

soup = BeautifulSoup(resp.text, 'lxml')
title = soup.find('title')
print(f"Title: {title.text if title else 'None'}")

error = soup.find(class_='alertMessage')
if error:
    print(f"Error: {error.get_text(strip=True)}")

# Check session
resp2 = session.get(f"{base_url}/direct/session/current.json")
data = json.loads(resp2.text)
print(f"User: {data.get('userEid')}")

if data.get('userId'):
    print("\n=== LOGIN SUCCESS! ===")
    resp3 = session.get(f"{base_url}/direct/site.json")
    sites = json.loads(resp3.text)
    print(f"Found {len(sites.get('site_collection', []))} sites")
    for site in sites.get('site_collection', [])[:10]:
        print(f"  - {site.get('title')}")
else:
    print("\nLogin failed.")
