#instructions:
#using a script from a different program, so adjust it to cater to my situation
#need username and password stored in a private key
#url = "https://bogmayer.bevtrack.net/reports-visits
# Locate the export button as before (btnExport)
#Then need to click btnDoExport

import os
import time
import tempfile
import json
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
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Remove download dir prefs - let Chrome use default
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 30)
    
    try:
        # Your working login + navigate code...
        print("Opening login page...")
        driver.get("https://bogmayer.bevtrack.net/")
        time.sleep(3)
        
        username = os.getenv("BT_USERNAME")
        password = os.getenv("BT_PASSWORD")
        username_elem = wait.until(EC.presence_of_element_located((By.ID, "email")))
        password_elem = wait.until(EC.presence_of_element_located((By.ID, "pass")))
        username_elem.send_keys(username)
        password_elem.send_keys(password)
        password_elem.submit()
        print("Logged in successfully.")
        time.sleep(5)
        
        print("Navigating to visits...")
        driver.get("https://bogmayer.bevtrack.net/reports-visits")
        time.sleep(5)
        
        # Click export
        print("Clicking export...")
        download_btn = wait.until(EC.element_to_be_clickable((By.ID, "btnExport")))
        download_btn.click()
        
        # Wait 45s for Chrome to write ANYWHERE
        print("Waiting 45s for download...")
        time.sleep(45)
        
    finally:
        driver.quit()
    
    # SEARCH EVERYWHERE for CSV (not just VisitsData)
    import glob
    csv_files = []
    for pattern in ["*.[cC][sS][vV]", "downloads/*.[cC][sS][vV]", "/tmp/*.[cC][sS][vV]"]:
        csv_files.extend(glob.glob(pattern))
    
    if not csv_files:
        raise FileNotFoundError("No CSV found anywhere after 45s!")
    
    newest_csv = max(csv_files, key=os.path.getctime)
    print(f"Found CSV: {newest_csv}")
    
    # Move to VisitsData and rename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = os.path.join(DOWNLOAD_DIR, f"VisitsReport_{timestamp}.csv")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.rename(newest_csv, target)
    return target

if __name__ == "__main__":
    path = download_visits_report()
    print(f"Final path: {path}")
