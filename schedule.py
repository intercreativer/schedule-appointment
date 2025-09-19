import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
URL = os.getenv("URL")
URL2 = os.getenv("URL2")

def main():
    driver = webdriver.Chrome()  # Selenium Manager will locate ChromeDriver automatically
    wait = WebDriverWait(driver, 10)

    try:
        #driver.get("https://ais.usvisa-info.com/en-kz/niv/users/sign_in")
        driver.get(URL2)

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

        # Wait until redirected (example: dashboard URL contains "/dashboard")
        wait.until(EC.url_contains("/dashboard"))
        print("✅ Login attempted successfully (check browser to confirm).")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()