#instructions:
#using a script from a different program, so adjust it to cater to my situation
#need username and password stored in a private key
#url = "https://bogmayer.bevtrack.net/reports-visits
# Locate the export button as before (btnExport)
#Then need to click btnDoExport

import os
import time
import glob
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

DOWNLOAD_DIR = os.path.join(os.getcwd(), "VisitsData")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def wait_for_new_csv(directory, start_time, timeout=60):
    """Wait for a CSV newer than start_time to appear in directory."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        csvs = glob.glob(os.path.join(directory, "*.csv"))
        new_csvs = [f for f in csvs if os.path.getmtime(f) > start_time]
        # Ignore .crdownload (in-progress Chrome downloads)
        complete = [f for f in new_csvs if not f.endswith(".crdownload")]
        if complete:
            return max(complete, key=os.path.getmtime)
        time.sleep(2)
    raise FileNotFoundError(f"No new CSV appeared in {directory} within {timeout}s")

def download_visits_report():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # FIX 1: Tell Chrome exactly where to save downloads
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    wait = WebDriverWait(driver, 30)
    
    # FIX 2: Record time before download so we can identify the new file
    download_start = time.time()

    try:
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
        print("Logged in.")
        time.sleep(5)

        print("Navigating to visits report...")
        driver.get("https://bogmayer.bevtrack.net/reports-visits")
        time.sleep(5)

        # FIX 3: Set the date range to TODAY before exporting
        # Adjust these selectors to match the actual fields on the page
        try:
            today = datetime.now().strftime("%m/%d/%Y")
            start_date = driver.find_element(By.ID, "startDate")  # update selector
            end_date = driver.find_element(By.ID, "endDate")      # update selector
            start_date.clear()
            start_date.send_keys(today)
            end_date.clear()
            end_date.send_keys(today)
            # If there's an "Apply" or "Filter" button, click it here
            print(f"Date range set to {today}")
            time.sleep(2)
        except Exception as e:
            print(f"Warning: could not set date range ({e}) — export may use default range")

        print("Clicking export...")
        download_btn = wait.until(EC.element_to_be_clickable((By.ID, "btnExport")))
        download_btn.click()

    finally:
        # FIX 4: Wait for the new file specifically, then quit
        print("Waiting for new CSV in VisitsData/...")
        try:
            newest_csv = wait_for_new_csv(DOWNLOAD_DIR, download_start, timeout=60)
            print(f"Download complete: {newest_csv}")
        finally:
            driver.quit()

    # Rename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = os.path.join(DOWNLOAD_DIR, f"VisitsReport_{timestamp}.csv")
    os.rename(newest_csv, target)
    return target

if __name__ == "__main__":
    path = download_visits_report()
    print(f"Final path: {path}")
