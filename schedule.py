import os
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
URL = os.getenv("URL")
URL2 = os.getenv("URL2")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def main():
    driver = webdriver.Chrome()  # Selenium Manager will locate ChromeDriver automatically
    wait = WebDriverWait(driver, 10)

    try:
        #driver.get("https://ais.usvisa-info.com/en-kz/niv/users/sign_in")
        driver.get(URL2)
        #input("Browser is open. Inspect the modal, then press Enter to continue...")

        # wait for the OK modal to appear
        ok_button = WebDriverWait(driver, 20).until(
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

        # Optional: wait a moment after clicking (human-like pause)
        import time
        time.sleep(2)

        # Click Sign In button
        sign_in_button = driver.find_element(By.NAME, "commit")
        sign_in_button.click()

        # wait for dropdown and select Astana
        dropdown = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "appointments_consulate_appointment_facility_id"))
        )
        select = Select(dropdown)
        select.select_by_visible_text("Astana")

        # wait until the button is present in DOM
        schedule_button = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "appointments_submit"))
        )

        # check if it's enabled or disabled
        if schedule_button.is_enabled():
            click_schedule_button(schedule_button)
        else:
            print("❌ Schedule Appointment button is DISABLED")
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": "❌ Schedule Appointment button is DISABLED"}
)        

    finally:
        input("Browser is open. Inspect the modal, then press Enter to continue...")
        driver.quit()

def click_schedule_button(schedule_button):
    print("✅ Schedule Appointment button is ENABLED, clicking it...")
    schedule_button.click()

if __name__ == "__main__":
    main()