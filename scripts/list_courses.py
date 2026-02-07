import requests, json
from sakai_bot.config import get_settings

s = get_settings()
sess = requests.Session()
sess.headers.update({"User-Agent": "Mozilla/5.0"})
sess.post(f"{s.sakai_base_url}/portal/xlogin", data={"eid": s.sakai_username, "pw": s.sakai_password})

# Try fetching with higher limit and pagination
page = 1
all_sites = []
while True:
    r = sess.get(f"{s.sakai_base_url}/direct/site.json?_limit=50&_start={len(all_sites)}")
    sites = json.loads(r.text).get("site_collection", [])
    if not sites:
        break
    all_sites.extend(sites)
    if len(sites) < 50:
        break
    page += 1

print(f"Total: {len(all_sites)} courses\n")
for i, site in enumerate(all_sites):
    print(f"  {i+1}. {site['title']}")
