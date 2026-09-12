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

    def do_HEAD(self):
        # Fixes the 501 error from UptimeRobot
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        # Silence raw HTTP spam from internet scanners to keep logs clean
        return

def run_loop():
    print(f"--> Background thread launched for PS ID: {PS_ID}", flush=True)
    
    # One-time boot alert to verify Telegram connection instantly
    send_telegram_alert(f"🚀 *Tracker online on Render!*\nMonitoring `{PS_ID}` 24/7.")
    
    while True:
        try:
            print("--> Fetching latest data from SIH...", flush=True)
            check_and_update()
        except Exception as e:
            print(f"--> Error in loop: {e}", flush=True)
        
        print(f"--> Sleeping for {INTERVAL_SECONDS} seconds...", flush=True)
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()

    port = int(os.getenv("PORT", 10000))
    print(f"Web listener bound to port {port}", flush=True)
    server = HTTPServer(("0.0.0.0", port), SimplePingHandler)
    server.serve_forever()