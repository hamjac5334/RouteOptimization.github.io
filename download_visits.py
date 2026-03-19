#instructions:
#using a script from a different program, so adjust it to cater to my situation
#need username and password stored in a private key
#url = "https://bogmayer.bevtrack.net/reports-visits
# Locate the export button as before (btnExport)
#Then need to click btnDoExport

import os
import requests
from datetime import datetime

DOWNLOAD_DIR = os.path.join(os.getcwd(), "VisitsData")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_visits_report(url="https://bogmayer.bevtrack.net/reports-visits"):
    """
    Download visits CSV directly via HTTP POST to BevTrack's export endpoint.
    """
    session = requests.Session()
    
    # Step 1: Get login cookie / session
    print("Getting login session...")
    session.get("https://bogmayer.bevtrack.net/")
    
    # Step 2: Login (same creds as before)
    login_data = {
        "email": os.getenv("BT_USERNAME"),
        "pass": os.getenv("BT_PASSWORD"),
    }
    login_resp = session.post("https://bogmayer.bevtrack.net/login", data=login_data)
    if "login" in login_resp.url or login_resp.status_code != 200:
        raise RuntimeError("Login failed")
    
    # Step 3: Navigate to reports-visits (gets the right session state)
    session.get(url)
    
    # Step 4: POST to export endpoint (this is the magic URL from your screenshot)
    export_data = {
        # These are likely the same params as your browser sent
        # You may need to adjust based on your filters
        "format": "csv",
        # Add other filters from your screenshot if needed
    }
    print("Requesting CSV export...")
    resp = session.post("https://bogmayer.bevtrack.net/reports/export", 
                       data=export_data, 
                       timeout=60)
    resp.raise_for_status()
    
    # Step 5: Save with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"VisitsReport_{timestamp}.csv"
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    
    with open(filepath, "wb") as f:
        f.write(resp.content)
    
    print(f"Visits report saved to: {filepath}")
    return filepath

if __name__ == "__main__":
    path = download_visits_report()
    print(path)
