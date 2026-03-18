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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Directory where the downloaded visits CSV will be saved
DOWNLOAD_DIR = os.path.join(os.getcwd(), "VisitsData")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_credentials():
    """
    Read BevTrack credentials from environment variables.
    Set these in your shell, GitHub Actions secrets, or .env loader:
      BT_USERNAME, BT_PASSWORD
    """
    username = os.getenv("BT_USERNAME")
    password = os.getenv("BT_PASSWORD")
    if not username or not password:
        raise RuntimeError("Missing BT_USERNAME or BT_PASSWORD environment variables.")
    return username, password

def download_visits_report(
    url: str = "https://bogmayer.bevtrack.net/reports-visits",
    report_prefix: str = "VisitsReport",
    wait_seconds: int = 15,
) -> str:
    """
    Log into BevTrack, navigate to the visits report page, export CSV, and
    save it to DOWNLOAD_DIR with a timestamped filename.

    Returns the full path to the downloaded CSV.
    """
    username, password = get_credentials()

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Use a temporary user data dir so each run is clean
    user_data_dir = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={user_data_dir}")

    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 30)

    try:
        # Open login page
        print("Opening login page...")
        driver.get("https://bogmayer.bevtrack.net/")  # adjust if login URL differs
        time.sleep(3)

        # Attempt login
        try:
            username_elem = wait.until(EC.presence_of_element_located((By.ID, "email")))
            password_elem = wait.until(EC.presence_of_element_located((By.ID, "pass")))

            username_elem.clear()
            username_elem.send_keys(username)
            password_elem.clear()
            password_elem.send_keys(password, Keys.RETURN)

            print("Logged in successfully.")
            time.sleep(5)
        except Exception:
            print("Already logged in or login not required.")

        # Navigate to visits report
        print(f"Navigating to report URL: {url}")
        driver.get(url)
        time.sleep(5)

        # Wait for any overlay to disappear (FusionHTML etc.)
        try:
            wait.until(EC.invisibility_of_element_located((By.ID, "FusionHTML")))
            print("FusionHTML overlay is gone.")
        except Exception:
            print("FusionHTML overlay did not appear or is already gone.")

        # Locate and click export button inside Shadow DOM
        print("Locating export button...")
        download_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "btnExport"))
        )

        try:
            download_btn.click()
        except Exception:
            print("Standard click failed, trying JavaScript click.")
            driver.execute_script("arguments[0].scrollIntoView(true);", download_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", download_btn)

        # Wait for the download to complete
        print("Export clicked, waiting for download...")
        time.sleep(wait_seconds)  # may need tuning for large reports

    finally:
        driver.quit()

    # Find newest file in DOWNLOAD_DIR
    files = [
        os.path.join(DOWNLOAD_DIR, f)
        for f in os.listdir(DOWNLOAD_DIR)
        if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))
    ]
    if not files:
        raise FileNotFoundError("No file found in download directory.")

    newest_file = max(files, key=os.path.getctime)

    # Rename file with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    new_filename = f"{report_prefix}_{timestamp}.csv"
    new_filepath = os.path.join(DOWNLOAD_DIR, new_filename)
    os.rename(newest_file, new_filepath)
    print(f"Visits report saved to: {new_filepath}")

    return new_filepath

if __name__ == "__main__":
    path = download_visits_report()
    print(path)
