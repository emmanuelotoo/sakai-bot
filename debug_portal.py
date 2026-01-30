"""Debug - check what URLs we get redirected to, look for CAS/SSO."""

import requests
from bs4 import BeautifulSoup
from sakai_bot.config import get_settings

settings = get_settings()
base_url = settings.sakai_base_url

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
})

# Check if there's a redirect to CAS/SSO when trying to access a protected page
print("=== Checking for SSO/CAS redirects ===")

# Try to access the my workspace which requires login
resp = session.get(f"{base_url}/portal/site/~", allow_redirects=False)
print(f"Status: {resp.status_code}")
if resp.status_code in (301, 302, 303, 307, 308):
    print(f"Redirects to: {resp.headers.get('Location')}")
print()

# Follow redirects and see where we end up
resp = session.get(f"{base_url}/portal/site/~")
print(f"Final URL: {resp.url}")

soup = BeautifulSoup(resp.text, 'lxml')

# Check for CAS-related elements
print("\n=== Looking for SSO indicators ===")
for link in soup.find_all('a'):
    href = link.get('href', '')
    if 'cas' in href.lower() or 'sso' in href.lower() or 'auth' in href.lower() or 'idp' in href.lower():
        print(f"Found link: {href}")

for form in soup.find_all('form'):
    action = form.get('action', '')
    print(f"Form action: {action}")
    
# Check page content for SSO hints
page_text = soup.get_text().lower()
if 'central authentication' in page_text or 'single sign' in page_text:
    print("Page mentions SSO/CAS")
    
# Print the full page body to see what's there
print("\n=== Page HTML snippet ===")
print(resp.text[:2000])
