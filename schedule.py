import os
import requests
import time
import json
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from datetime import datetime
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC

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
    now = datetime.now().strftime("%H:%M")

    try:
        #driver.get("https://ais.usvisa-info.com/en-kz/niv/users/sign_in")
        driver.get(URL2)
        #input("Browser is open. Inspect the modal, then press Enter to continue...")

        # driver.save_screenshot("headless_debug.png")
        # wait for the OK modal to appear 
        try:
            ok_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='OK']"))
            )
            ok_button.click() 
        except Exception:
            print(f"ℹ️ No OK modal appeared at {now}")
            driver.quit()
            return  #                    

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
        try:
            dropdown = wait.until(
                EC.presence_of_element_located((By.ID, "appointments_consulate_appointment_facility_id"))
            )
            select = Select(dropdown)
            select.select_by_visible_text("Astana")
            
            
            # Try JavaScript approach first (browser-native fetch)
            available_dates = get_available_dates_via_js(driver, facility_id="134", expedite="false")
            
            
            if available_dates is not None:
                # Check if we have actual dates (not just empty array)
                if isinstance(available_dates, list) and len(available_dates) > 0:
                    #print(f"✅ Found {len(available_dates)} available date(s)")
                    
                    # Get the first available date
                    first_date = available_dates[0]['date']
                    print(f"📅 First available date: {first_date}")
                    
                    # Get available times for this date
                    available_times = get_available_times_via_js(driver, facility_id="134", date=first_date, expedite="false")
                    
                    if available_times is not None and isinstance(available_times, dict) and 'available_times' in available_times:
                        times_list = available_times['available_times']
                        if len(times_list) > 0:
                            #print(f"⏰ Found {len(times_list)} available time(s) for {first_date}")
                            
                            # Get the last available time
                            last_time = times_list[-1]
                            # print(f"⏰ Last available time: {last_time}")
                        else:
                            print(f"⏰ No available times found for {first_date}")
                            last_time = None
                    else:
                        print(f"⏰ No available times found for {first_date}")
                        last_time = None
                    
                    # Only schedule if we have a valid time
                    if last_time is not None:
                        # Schedule the appointment
                        schedule_result = schedule_appointment_via_js(driver, facility_id="134", date=first_date, time=last_time)
                        
                        if schedule_result:
                            print("✅ Appointment scheduled successfully!")
                            telegram_message = f"🎉 APPOINTMENT SCHEDULED!\n\n"
                            telegram_message += f"📅 Date: {first_date}\n"
                            telegram_message += f"⏰ Time: {last_time}\n"
                            telegram_message += f"🔍 Check the console output for details."
                            send_telegram_message(telegram_message)
                        else:
                            print("❌ Failed to schedule appointment")
                            telegram_message = f"❌ Failed to schedule appointment for {first_date} at {last_time}"
                            send_telegram_message(telegram_message)
                        print(f"🎯 Ready to schedule appointment for {first_date} at {last_time}")
                    else:
                        print(f"⏰ No valid time found for {first_date}")
                        telegram_message = f"📅 Available appointment dates found!\n\n"
                        telegram_message += f"🔍 Found {len(available_dates)} available dates.\n"
                        telegram_message += f"📅 First date: {first_date}\n"
                        telegram_message += f"⏰ No available times for this date"
                        #send_telegram_message(telegram_message)
                else:
                    print(f"📭 No available dates found at {now}")
                    #send_telegram_message("📭 No available appointment dates found")
            else:
                print("❌ API call failed")
                #send_telegram_message("❌ Failed to fetch appointment dates")
                
        except TimeoutException:
            print("⚠️ Dropdown not found (possible logout/session expired). quiting...")
            # driver.save_screenshot("error.png")  # save screenshot for debugging
            driver.quit()
            return  #



    finally:
        #input("Browser is open. Inspect the modal, then press Enter to continue...")
        # Optional: wait a moment after clicking (human-like pause)
        time.sleep(2)
        # input("🔎 Script finished. Press Enter to close the browser...")
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


def get_available_dates_via_js(driver, facility_id="134", expedite="false"):
    """
    Makes API call using JavaScript fetch in the browser context.
    This should work exactly like the UI does.
    """
    try:
        #print("🌐 Making API call via JavaScript fetch...")
        
        # Execute JavaScript to make the API call in the browser context
        js_code = f"""
        var xhr = new XMLHttpRequest();
        xhr.open('GET', 'https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment/days/{facility_id}.json?appointments[expedite]={expedite}', false);
        xhr.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.send();
        
        if (xhr.status === 200) {{
            try {{
                return JSON.parse(xhr.responseText);
            }} catch (e) {{
                console.error('JSON parse error:', e);
                return null;
            }}
        }} else {{
            console.error('HTTP error:', xhr.status, xhr.responseText);
            return null;
        }}
        """
        
        result = driver.execute_script(js_code)
        # print(f"🌐 JavaScript API call result: {result}")
        return result
        
    except Exception as e:
        print(f"❌ JavaScript API call failed: {e}")
        return None

def get_available_times_via_js(driver, facility_id="134", date="2025-12-18", expedite="false"):
    """
    Makes API call to get available appointment times for a specific date using JavaScript.
    
    Args:
        driver: Selenium WebDriver instance with active session
        facility_id: Facility ID (134 for Astana, 135 for Almaty)
        date: Date in YYYY-MM-DD format
        expedite: Whether to check for expedited appointments
    
    Returns:
        list: Available times data or None if failed
    """
    try:
        
        # Execute JavaScript to make the API call in the browser context
        js_code = f"""
        var xhr = new XMLHttpRequest();
        xhr.open('GET', 'https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment/times/{facility_id}.json?date={date}&appointments[expedite]={expedite}', false);
        xhr.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.send();
        
        if (xhr.status === 200) {{
            try {{
                return JSON.parse(xhr.responseText);
            }} catch (e) {{
                console.error('JSON parse error:', e);
                return null;
            }}
        }} else {{
            console.error('HTTP error:', xhr.status, xhr.responseText);
            return null;
        }}
        """
        
        result = driver.execute_script(js_code)
        print(f"🌐 Available times result: {result}")
        return result
        
    except Exception as e:
        print(f"❌ JavaScript API call for times failed: {e}")
        return None

def schedule_appointment_via_js(driver, facility_id="134", date="2025-12-08", time="08:00"):
    """
    Makes POST request to schedule an appointment using JavaScript.
    
    Args:
        driver: Selenium WebDriver instance with active session
        facility_id: Facility ID (134 for Astana, 135 for Almaty)
        date: Date in YYYY-MM-DD format
        time: Time in HH:MM format
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"📝 Scheduling appointment for {date} at {time}")
        
        # Get CSRF token from the page
        csrf_token = None
        try:
            csrf_meta = driver.find_element(By.CSS_SELECTOR, 'meta[name="csrf-token"]')
            csrf_token = csrf_meta.get_attribute('content')
            print(f"🔐 Using CSRF token: {csrf_token[:20]}...")
        except Exception as e:
            print(f"⚠️ Could not extract CSRF token: {e}")
            return False
        
        # Execute JavaScript to make the POST request
        js_code = f"""
        var xhr = new XMLHttpRequest();
        xhr.open('POST', 'https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment', false);
        xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.setRequestHeader('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7');
        xhr.setRequestHeader('Origin', 'https://ais.usvisa-info.com');
        xhr.setRequestHeader('Referer', 'https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment');
        xhr.withCredentials = true;
        
        var formData = 'authenticity_token={csrf_token}&confirmed_limit_message=1&use_consulate_appointment_capacity=true&appointments[consulate_appointment][facility_id]={facility_id}&appointments[consulate_appointment][date]={date}&appointments[consulate_appointment][time]={time}&commit=Schedule+Appointment';
        
        xhr.send(formData);
        
        return {{
            status: xhr.status,
            responseText: xhr.responseText,
            finalUrl: xhr.responseURL || window.location.href,
            headers: xhr.getAllResponseHeaders()
        }};
        """
        
        result = driver.execute_script(js_code)
        print(f"📊 Schedule response status: {result['status']}")
        print(f"📊 Final URL: {result['finalUrl']}")
        print(f"📊 Response headers: {result['headers']}")
        
        # Debug: Check current page URL and cookies
        current_url = driver.current_url
        print(f"🌐 Current page URL: {current_url}")
        
        # Check if we're still logged in by looking for logout link or user info
        try:
            logout_element = driver.find_element(By.CSS_SELECTOR, "a[href*='sign_out']")
            print("✅ Still logged in (logout link found)")
        except:
            print("❌ Not logged in (no logout link found)")
        
        if result['status'] in [200, 302]:
            # Save the response HTML to file
            with open("appointment_result.html", "w", encoding="utf-8") as f:
                f.write(result['responseText'])
            print("💾 Appointment result saved to appointment_result.html")
            
            # Send the HTML file via Telegram
            send_html_to_telegram(driver, "appointment_result.html")
            
            return True
        else:
            print(f"❌ Schedule request failed with status {result['status']}")
            print(f"📄 Response: {result['responseText'][:500]}...")
            return False
            
    except Exception as e:
        print(f"❌ Error scheduling appointment: {e}")
        return False


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

    # Create the driver using Selenium Manager (automatically handles ChromeDriver)
    driver = webdriver.Chrome(options=options)

    # Minimize the window so it doesn't block your screen
    try:
        driver.minimize_window()
    except Exception as e:
        # On some platforms/minor driver versions minimize might throw — ignore safely
        print(f"⚠️ Could not minimize window: {e}")

    return driver


if __name__ == "__main__":

    
    # Run the main Selenium automation
    main()