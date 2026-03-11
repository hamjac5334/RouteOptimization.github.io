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

DOWNLOAD_DIR = os.path.join(os.getcwd(), "AutomatedEmailData")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_report(username, password, url, report_number=1):
    """
    Download a DSD report from a given URL and rename it uniquely.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    user_data_dir = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={user_data_dir}")

    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 30)

    try:
        # Login page
        print("Opening login page...")
        driver.get("https://dsdlink.com/Home?DashboardID=185125")
        time.sleep(3)

        try:
            username_elem = wait.until(EC.presence_of_element_located((By.ID, "ews-login-username")))
            password_elem = wait.until(EC.presence_of_element_located((By.ID, "ews-login-password")))
            username_elem.send_keys(username)
            password_elem.send_keys(password, Keys.RETURN)
            print("Logged in successfully.")
            time.sleep(5)
        except:
            print("Already logged in or login not required.")

        # Navigate to report
        print(f"Navigating to report URL: {url}")
        driver.get(url)
        time.sleep(5)

        # Export CSV
        print("Locating export button...")

        # Wait for overlays/popups to disappear (FusionHTML is a common one on this site)
        try:
            wait.until(EC.invisibility_of_element_located((By.ID, "FusionHTML")))
            print("FusionHTML overlay is gone.")
        except Exception:
            print("FusionHTML overlay did not appear or is already gone.")

        # Locate the export button as before
        export_btn_host = wait.until(EC.presence_of_element_located((By.ID, "ActionButtonExport")))
        export_btn_root = driver.execute_script("return arguments[0].shadowRoot", export_btn_host)
        download_btn = export_btn_root.find_element(By.CSS_SELECTOR, "button.button")

        try:
            download_btn.click()
        except Exception:
            # If click fails, try using JavaScript
            print("Standard click failed, trying JavaScript click.")
            driver.execute_script("arguments[0].scrollIntoView(true);", download_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", download_btn)

        csv_option = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.ews-menu-item[format="CSV"]')))
        csv_option.click()
        print("Export clicked, waiting for download...")
        time.sleep(15)  # adjust if large reports

    finally:
        driver.quit()

    # Detect newest file in DOWNLOAD_DIR
    files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR)]
    if not files:
        raise Exception("No file found in download directory.")
    newest_file = max(files, key=os.path.getctime)

    # Rename file uniquely
    date_str = datetime.now().strftime("%Y-%m-%d")
    new_filename = f"Report_{date_str}_{report_number}.csv"
    new_filepath = os.path.join(DOWNLOAD_DIR, new_filename)
    os.rename(newest_file, new_filepath)
    print(f"Report saved to: {new_filepath}")

    return new_filepath
