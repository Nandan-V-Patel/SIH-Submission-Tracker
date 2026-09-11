import os
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PS_ID = os.getenv("PS_ID", "SIH26054")
FILE_PATH = "prev.txt"
INTERVAL_SECONDS = 50  # 5 minutes

URL = "https://www.sih.gov.in/sih2026PS"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def send_telegram_alert(message):
    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(telegram_url, json=payload, timeout=10)
        res.raise_for_status()
    except Exception as err:
        print(f"Failed to send Telegram alert: {err}")

def fetch_submission_count():
    response = requests.get(URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    ps_cell = soup.find("td", string=PS_ID)
    
    if not ps_cell:
        print(f"Problem statement ID {PS_ID} not found in table.")
        return None
    
    count_cell = ps_cell.find_next_sibling("td")
    if not count_cell:
        return None
    
    # "6/500" -> 6
    raw_count = count_cell.get_text(strip=True)
    return int(raw_count.split("/")[0])

def check_and_update():
    curr_num = fetch_submission_count()
    if curr_num is None:
        return

    # Read previous baseline safely
    with open(FILE_PATH, "a+") as f:
        f.seek(0)
        content = f.read().strip()

    # Alert if count increased
    if content and curr_num >= int(content):
        diff = curr_num - int(content)
        alert_msg = (
            f"🚨 *SIH Alert!* New submission for `{PS_ID}`!\n\n"
            f"• *Previous count:* {content}\n"
            f"• *Current count:* {curr_num}\n"
            f"• *New submissions:* +{diff}"
        )
        print(f"Change detected! Alerting team: {content} -> {curr_num}")
        send_telegram_alert(alert_msg)
    elif not content:
        print(f"Baseline established at {curr_num} submissions. Monitoring started.")
    else:
        print(f"No changes. Count is still {curr_num}.")

    # Persist the latest count
    with open(FILE_PATH, "w") as f:
        f.write(str(curr_num))

class SimplePingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"SIH Tracker is running 24/7.")

def run_loop():
    print(f"Starting SIH background loop for PS ID: {PS_ID}...")
    while True:
        try:
            check_and_update()
        except Exception as e:
            print(f"Error in tracking loop: {e}")
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    # Start the scraping loop in a daemon thread
    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()

    # Bind HTTP server to port specified by Render (default 10000 or 8080)
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimplePingHandler)
    print(f"Web listener active on port {port}")
    server.serve_forever()