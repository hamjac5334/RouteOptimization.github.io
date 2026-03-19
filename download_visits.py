#instructions:
#using a script from a different program, so adjust it to cater to my situation
#need username and password stored in a private key
#url = "https://bogmayer.bevtrack.net/reports-visits
# Locate the export button as before (btnExport)
#Then need to click btnDoExport

import os
import time
import tempfile
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import requests

DOWNLOAD_DIR = os.path.join(os.getcwd(), "VisitsData")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_visits_report():
    """Selenium login → steal cookies → requests CSV download"""
    
    # Step 1: Selenium for login (your existing working code)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 30)
    
    try:
        print("Opening login page...")
        driver.get("https://bogmayer.bevtrack.net/")
        time.sleep(3)
        
        # Login (your working code)
        username = os.getenv("BT_USERNAME")
        password = os.getenv("BT_PASSWORD")
        if not username or not password:
            raise RuntimeError("Missing BT_USERNAME or BT_PASSWORD")
            
        try:
            username_elem = wait.until(EC.presence_of_element_located((By.ID, "email")))
            password_elem = wait.until(EC.presence_of_element_located((By.ID, "pass")))
            username_elem.clear()
            username_elem.send_keys(username)
            password_elem.clear()
            password_elem.send_keys(password)
            password_elem.submit()
            print("Logged in successfully.")
            time.sleep(5)
        except:
            print("Already logged in or login not required.")
        
        # Navigate to visits page
        print("Navigating to visits report...")
        driver.get("https://bogmayer.bevtrack.net/reports-visits")
        time.sleep(5)
        
        # Step 2: Extract cookies and create requests session
        print("Downloading CSV via exact browser request...")

# EXACT endpoint + headers from your screenshot
export_response = session.post(
    "https://bogmayer.bevtrack.net/exportVisits.php",  # ← Correct endpoint!
    headers={
        'Content-Type': 'application/json',           # ← JSON, not form data!
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://bogmayer.bevtrack.net',
        'Referer': 'https://bogmayer.bevtrack.net/reports-visits',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    },
    json={"format": "csv"},  # ← This 159KB JSON payload gets auto-serialized
    timeout=120              # Large payload needs more time
)
export_response.raise_for_status()

# Verify CSV content
content_preview = export_response.content[:500].decode('utf-8', errors='ignore')
if '<!DOCTYPE html>' in content_preview or '<html' in content_preview:
    print("ERROR: Got HTML. Need exact 159KB JSON payload.")
    raise RuntimeError("HTML instead of CSV")

print(f"Saved {len(export_response.content)} bytes")
with open(filepath, "wb") as f:
    f.write(export_response.content))
        
        # Step 4: Save file directly (bypasses Chrome download entirely)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"VisitsReport_{timestamp}.csv"
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        
        with open(filepath, "wb") as f:
            f.write(export_response.content)
        
        print(f"Visits report saved to: {filepath}")
        return filepath
        
    finally:
        driver.quit()

if __name__ == "__main__":
    path = download_visits_report()
    print(f"Final path: {path}")
