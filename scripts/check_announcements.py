"""Check announcements - try multiple API endpoints and params."""
import requests, json
from bs4 import BeautifulSoup
from sakai_bot.config import get_settings

s = get_settings()
sess = requests.Session()
sess.headers.update({"User-Agent": "Mozilla/5.0"})
sess.post(f"{s.sakai_base_url}/portal/xlogin", data={"eid": s.sakai_username, "pw": s.sakai_password})

# Get filtered courses
r = sess.get(f"{s.sakai_base_url}/direct/site.json?_limit=50&_start=0")
all_sites = json.loads(r.text).get("site_collection", [])
courses = [site for site in all_sites if s.current_semester in site.get("title", "")]

for course in courses:
    sid = course["id"]
    title = course["title"]
    print(f"\n{'='*60}")
    print(f"  {title} (id: {sid})")
    print(f"{'='*60}")
    
    # Method 1: REST API
    r = sess.get(f"{s.sakai_base_url}/direct/announcement/site/{sid}.json")
    if r.status_code == 200:
        anns = json.loads(r.text).get("announcement_collection", [])
        print(f"  REST API: {len(anns)} announcements")
    else:
        print(f"  REST API: HTTP {r.status_code}")

    # Method 2: REST API with no limit
    r = sess.get(f"{s.sakai_base_url}/direct/announcement/site/{sid}.json?_limit=100&n=100")
    if r.status_code == 200:
        anns = json.loads(r.text).get("announcement_collection", [])
        print(f"  REST API (limit=100): {len(anns)} announcements")

    # Method 3: Check what tools exist on this site
    r = sess.get(f"{s.sakai_base_url}/direct/site/{sid}.json")
    if r.status_code == 200:
        site_data = json.loads(r.text)
        pages = site_data.get("sitePages", [])
        for page in pages:
            page_title = page.get("title", "")
            tools = page.get("tools", [])
            for tool in tools:
                tool_id = tool.get("toolId", "")
                if "annc" in tool_id.lower() or "announcement" in tool_id.lower() or "announcement" in page_title.lower():
                    placement_id = tool.get("id", "")
                    print(f"  Found announcement tool: {tool_id} (placement: {placement_id})")
                    
                    # Try accessing with the placement ID
                    r2 = sess.get(f"{s.sakai_base_url}/direct/announcement/site/{sid}.json?_limit=100")
                    if r2.status_code == 200:
                        anns2 = json.loads(r2.text).get("announcement_collection", [])
                        print(f"    -> {len(anns2)} announcements via placement")

    # Method 4: Scrape the actual Announcements tool page
    r = sess.get(f"{s.sakai_base_url}/portal/site/{sid}/tool-reset/sakai.announcements")
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, "lxml")
        # Look for announcement rows in the table
        rows = soup.select('tr')
        ann_rows = []
        for row in rows:
            cells = row.select('td')
            if cells:
                ann_rows.append([c.get_text(strip=True)[:80] for c in cells])
        if ann_rows:
            print(f"  HTML Announcements page: {len(ann_rows)} rows")
            for row in ann_rows[:5]:
                print(f"    -> {row}")
        else:
            # Maybe it uses a different structure
            body_text = soup.get_text(strip=True)[:500]
            print(f"  HTML page body preview: {body_text[:200]}")
    else:
        print(f"  HTML Announcements tool: HTTP {r.status_code}")

    # Method 5: Try the announcements tool with different tool IDs
    for tool_name in ["sakai.announcements", "sakai.synoptic.announcement"]:
        r = sess.get(f"{s.sakai_base_url}/portal/site/{sid}/tool-reset/{tool_name}")
        if r.status_code == 200 and len(r.text) > 500:
            soup = BeautifulSoup(r.text, "lxml")
            # Look for any content containers
            containers = soup.select('.portletBody, #content, .Mrphs-toolBody')
            for c in containers:
                links = c.select('a')
                if links:
                    print(f"  {tool_name}: found {len(links)} links")
                    for link in links[:3]:
                        print(f"    -> {link.get_text(strip=True)[:80]}")

# Also check the "Message of the Day" channel and merged channels
print(f"\n{'='*60}")
print("  Checking merged/alternate announcement channels")
print(f"{'='*60}")
for course in courses:
    sid = course["id"]
    title = course["title"]
    # Try message_channel endpoint
    for channel in ["main", "motd"]:
        r = sess.get(f"{s.sakai_base_url}/direct/announcement/site/{sid}/channel/{channel}.json")
        if r.status_code == 200:
            data = json.loads(r.text)
            if isinstance(data, dict):
                anns = data.get("announcement_collection", [])
                print(f"  {title} ({channel}): {len(anns)} announcements")

# Full user feed with details
print(f"\n{'='*60}")
print("  User-level feed (full)")  
print(f"{'='*60}")
r = sess.get(f"{s.sakai_base_url}/direct/announcement/user.json?n=50&_limit=50")
if r.status_code == 200:
    user_anns = json.loads(r.text).get("announcement_collection", [])
    print(f"  Total: {len(user_anns)}")
    for a in user_anns:
        print(f"  - [{a.get('siteTitle','?')}] {a.get('title','?')[:60]}")
        print(f"    siteId: {a.get('siteId','?')}, channel: {a.get('announcementId','?')[:80]}")
