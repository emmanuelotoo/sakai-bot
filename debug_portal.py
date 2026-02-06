"""Debug - deep dive: check iframes, JS, and network requests during login."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import json

from sakai_bot.config import get_settings

settings = get_settings()
base_url = settings.sakai_base_url

options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
# Enable network logging
options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

print("Opening browser...")
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options,
)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

try:
    print("Navigating to portal...")
    driver.get(f"{base_url}/portal")
    time.sleep(3)
    
    # Check for iframes
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"Number of iframes: {len(iframes)}")
    for i, iframe in enumerate(iframes):
        print(f"  iframe {i}: src={iframe.get_attribute('src')}, id={iframe.get_attribute('id')}")
    
    # Get FULL page source to analyze
    page_source = driver.page_source
    
    # Look for JavaScript that handles form submission
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page_source, 'lxml')
    
    # Check all scripts
    print(f"\nScript tags: {len(soup.find_all('script'))}")
    for script in soup.find_all('script'):
        src = script.get('src', '')
        content = script.string or ''
        if 'login' in content.lower() or 'submit' in content.lower() or 'eid' in content.lower() or 'password' in content.lower():
            print(f"\n  Script with login-related content:")
            print(f"    src: {src}")
            print(f"    content: {content[:500]}")
    
    # Check the form more carefully
    form = soup.find('form')
    if form:
        print(f"\nForm details:")
        print(f"  action: {form.get('action')}")
        print(f"  method: {form.get('method')}")
        print(f"  id: {form.get('id')}")
        print(f"  class: {form.get('class')}")
        print(f"  onsubmit: {form.get('onsubmit')}")
        
        # Get ALL attributes
        print(f"  All attrs: {dict(form.attrs)}")
        
        # Get all input fields, including type, name, value
        for inp in form.find_all(['input', 'button', 'select', 'textarea']):
            print(f"  <{inp.name}: {dict(inp.attrs)}>")
    
    # Check if there's a login modal or popup
    modals = soup.find_all(class_=lambda x: x and 'modal' in str(x).lower())
    print(f"\nModal elements: {len(modals)}")
    for modal in modals:
        modal_id = modal.get('id', 'none')
        print(f"  Modal id={modal_id}, class={modal.get('class')}")
    
    # Check for any event listeners via JS
    print("\nChecking JS event listeners on form...")
    try:
        result = driver.execute_script("""
            var form = document.querySelector('form');
            if (!form) return 'no form found';
            
            // Check onsubmit
            var info = {
                'onsubmit': form.onsubmit ? form.onsubmit.toString() : null,
                'action': form.action,
                'method': form.method,
                'encoding': form.encoding,
                'target': form.target,
            };
            
            // Check if there's a submit event listener
            var submitBtn = form.querySelector('button[type=submit], input[type=submit]');
            if (submitBtn) {
                info['submitBtn'] = {
                    'type': submitBtn.type,
                    'value': submitBtn.value,
                    'text': submitBtn.textContent,
                    'onclick': submitBtn.onclick ? submitBtn.onclick.toString() : null,
                };
            }
            
            return JSON.stringify(info, null, 2);
        """)
        print(f"  {result}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Now fill in and submit, then capture network logs
    print("\n=== Filling in form ===")
    eid_field = driver.find_element(By.ID, "eid")
    pw_field = driver.find_element(By.ID, "pw")
    
    eid_field.clear()
    eid_field.send_keys(settings.sakai_username)
    time.sleep(0.5)
    pw_field.clear()
    pw_field.send_keys(settings.sakai_password)
    time.sleep(1)
    
    # Submit
    submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    submit_btn.click()
    time.sleep(5)
    
    print(f"\nAfter submit:")
    print(f"  URL: {driver.current_url}")
    print(f"  Title: {driver.title}")
    
    # Get network logs
    print("\n=== Network Logs (login-related) ===")
    logs = driver.get_log("performance")
    for log in logs:
        try:
            msg = json.loads(log["message"])["message"]
            if msg["method"] == "Network.requestWillBeSent":
                url = msg["params"]["request"]["url"]
                method = msg["params"]["request"]["method"]
                if "login" in url.lower() or "xlogin" in url.lower() or "relogin" in url.lower() or "session" in url.lower():
                    print(f"\n  {method} {url}")
                    if "postData" in msg["params"]["request"]:
                        print(f"    POST data: {msg['params']['request']['postData']}")
                    headers = msg["params"]["request"].get("headers", {})
                    print(f"    Content-Type: {headers.get('Content-Type', 'N/A')}")
            elif msg["method"] == "Network.responseReceived":
                url = msg["params"]["response"]["url"]
                status = msg["params"]["response"]["status"]
                if "login" in url.lower() or "xlogin" in url.lower() or "relogin" in url.lower() or "session" in url.lower():
                    print(f"  Response: {status} {url}")
        except:
            pass
    
    time.sleep(5)

finally:
    driver.quit()
    print("\nBrowser closed.")
