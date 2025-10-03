import os
import json
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
URL2 = os.getenv("URL2")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

# --- Driver creation ---
def create_driver():
    options = Options()
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    try:
        driver.minimize_window()
    except Exception as e:
        print(f"⚠️ Could not minimize window: {e}")
    return driver

# --- Telegram helpers ---
def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("📩 Telegram message sent successfully!")
        else:
            print(f"⚠️ Failed to send message: {response.text}")
    except Exception as e:
        print(f"⚠️ Error sending message: {e}")

# --- Browser API fetch ---
def fetch_api_with_driver(driver, url):
    """Fetch JSON from URL inside the logged-in browser."""
    script = """
      const url = arguments[0];
      const callback = arguments[1];
      fetch(url, {
        credentials: 'same-origin',
        headers: { 'accept': 'application/json, text/javascript, */*; q=0.01' }
      })
      .then(r => r.json())
      .then(data => callback(JSON.stringify(data)))
      .catch(err => callback(JSON.stringify({error: err.toString()})));
    """
    result = driver.execute_async_script(script, url)
    return json.loads(result)

# --- Helpers ---
def get_first_business_day(dates):
    for entry in dates:
        if entry.get("business_day"):
            return entry["date"]
    return None

def schedule_appointment(driver, schedule_url, facility_id, date, time_slot):
    """Send POST request via browser to schedule an appointment."""
    csrf_token = driver.execute_script(
        "return document.querySelector('meta[name=\"csrf-token\"]').getAttribute('content');"
    )

    payload = {
        "authenticity_token": csrf_token,
        "confirmed_limit_message": "1",
        "use_consulate_appointment_capacity": "true",
        "appointments[consulate_appointment][facility_id]": str(facility_id),
        "appointments[consulate_appointment][date]": date,
        "appointments[consulate_appointment][time]": time_slot,
        "commit": "Schedule Appointment",
    }

    # Build URL-encoded payload string
    payload_str = "&".join([f"{k}={v}" for k, v in payload.items()])

    script = f"""
        const url = "{schedule_url}";
        const payload = "{payload_str}";
        const callback = arguments[0];
        fetch(url, {{
            method: 'POST',
            credentials: 'same-origin',
            headers: {{
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }},
            body: payload
        }})
        .then(r => r.text())
        .then(html => callback({{status: 'ok', html: html}}))
        .catch(err => callback({{status: 'error', error: err.toString()}}));
    """
    result = driver.execute_async_script(script)
    return result

# --- Main ---
def main():
    driver = create_driver()
    wait = WebDriverWait(driver, 20)

    try:
        driver.get(URL2)
        now = datetime.now().strftime("%H:%M")

        # Handle modal if present
        try:
            ok_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='OK']")))
            ok_button.click()
        except Exception:
            print(f"ℹ️ No OK modal appeared at {now}")

        # Login
        email_input = wait.until(EC.presence_of_element_located((By.ID, "user_email")))
        password_input = driver.find_element(By.ID, "user_password")
        email_input.send_keys(EMAIL)
        password_input.send_keys(PASSWORD)

        # Accept policy
        policy_wrapper = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.icheckbox")))
        policy_wrapper.click()

        # Submit login
        sign_in_button = driver.find_element(By.NAME, "commit")
        sign_in_button.click()

        # --- 1. Fetch available dates ---
        days_api = "https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment/days/134.json?appointments[expedite]=false"
        available_days = fetch_api_with_driver(driver, days_api)
        if not available_days:
            print("❌ No available dates")
            return

        first_day = get_first_business_day(available_days)
        print(f"✅ First available date: {first_day}")

        # --- 2. Fetch available times ---
        times_api = f"https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment/times/134.json?date={first_day}&appointments[expedite]=false"
        available_times = fetch_api_with_driver(driver, times_api)
        if not available_times.get("available_times"):
            print(f"❌ No available times on {first_day}")
            return

        first_time = available_times["available_times"][0]
        print(f"✅ First available time: {first_time}")

        # --- 3. Schedule appointment ---
        # schedule_url = "https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment"
        # result = schedule_appointment(driver, schedule_url, 134, first_day, first_time)

        # if result.get("status") == "ok":
        #     print(f"🎯 Appointment scheduled for {first_day} at {first_time}")
        #     send_telegram_message(f"🎯 Appointment scheduled for {first_day} at {first_time}")
        # else:
        #     print(f"❌ Failed to schedule appointment: {result.get('error')}")

        

    finally:
        input("🔎 Script finished. Press Enter to close the browser...")
        driver.quit()

if __name__ == "__main__":
    main()
