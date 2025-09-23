import os
import requests
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from datetime import datetime

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
URL = os.getenv("URL")
URL2 = os.getenv("URL2")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

def main():
    driver = create_driver()  # Selenium Manager will locate ChromeDriver automatically
    wait = WebDriverWait(driver, 20)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        #driver.get("https://ais.usvisa-info.com/en-kz/niv/users/sign_in")
        driver.get(URL2)
        #input("Browser is open. Inspect the modal, then press Enter to continue...")

        # driver.save_screenshot("headless_debug.png")
        # wait for the OK modal to appear
        ok_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='OK']"))
        )
        ok_button.click()   

        # Wait for the form fields
        email_input = wait.until(EC.presence_of_element_located((By.ID, "user_email")))
        password_input = driver.find_element(By.ID, "user_password")

        # Fill in login details
        email_input.send_keys(EMAIL)
        password_input.send_keys(PASSWORD)

        # ✅ Click the visible styled checkbox wrapper (not the hidden input)
        policy_wrapper = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.icheckbox"))
        )
        policy_wrapper.click()

        # # Optional: wait a moment after clicking (human-like pause)
        # import time
        # time.sleep(2)

        # Click Sign In button
        sign_in_button = driver.find_element(By.NAME, "commit")
        sign_in_button.click()

        # wait for dropdown and select Astana
        dropdown = wait.until(
            EC.presence_of_element_located((By.ID, "appointments_consulate_appointment_facility_id"))
        )
        select = Select(dropdown)
        select.select_by_visible_text("Astana")

        # wait until the button is present in DOM
        schedule_button = wait.until(
            EC.presence_of_element_located((By.ID, "appointments_submit"))
        )

        # check if it's enabled or disabled
        if schedule_button.is_enabled():
            print("✅ Schedule Appointment button is ENABLED, clicking it...")
            send_telegram_message("✅ Schedule Appointment button is ENABLED, clicking it...")                
            schedule_button.click()
            send_html_to_telegram(driver) 
        else:
            print(f"❌ Schedule Appointment button is DISABLED at {now}")
            # send_telegram_message("❌ Schedule Appointment button is DISABLED")
            # send_html_to_telegram(driver)  

    finally:
        #input("Browser is open. Inspect the modal, then press Enter to continue...")
        # Optional: wait a moment after clicking (human-like pause)
        time.sleep(2)
        driver.quit()

def send_html_to_telegram(driver, filename="page.html"):
    # get full page source
    html = driver.page_source
    
    # save to file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    # send file to Telegram
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    with open(filename, "rb") as f:
        response = requests.post(url, data={"chat_id": CHAT_ID}, files={"document": f})

    if response.status_code == 200:
        print("📄 Sent page HTML to Telegram successfully!")
    else:
        print(f"⚠️ Failed to send HTML: {response.text}")

def send_telegram_message(message: str):
    """
    Sends a text message into a Telegram group.
    """
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


def create_driver():
    """
    Create a normal (non-headless) Chrome WebDriver and minimize its window.
    Minimizing keeps the browser visible to the OS (so the site won't block headless),
    but it won't bother you on the screen.
    """
    options = Options()

    # Optional: set a deterministic window size (helps with layout/click issues)
    options.add_argument("--window-size=1920,1080")

    # Optional: disable infobars / automation banner
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Create the driver (Selenium Manager locates chromedriver automatically)
    driver = webdriver.Chrome(options=options)

    # Minimize the window so it doesn't block your screen
    try:
        driver.minimize_window()
    except Exception as e:
        # On some platforms/minor driver versions minimize might throw — ignore safely
        print(f"⚠️ Could not minimize window: {e}")

    return driver

if __name__ == "__main__":
    main()