import os
import requests
import time
import json
import random
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from datetime import datetime, date
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
URL = os.getenv("URL")
URL2 = os.getenv("URL2")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

class SessionManager:
    def __init__(self):
        self.driver = None
        self.session_start_time = None
        self.last_check_time = None
        self.session_file = "session_info.json"
        
    def load_session_info(self):
        """Load session info from file if it exists."""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Could not load session info: {e}")
        return None
    
    def save_session_info(self, session_info):
        """Save session info to file."""
        try:
            with open(self.session_file, 'w') as f:
                json.dump(session_info, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save session info: {e}")
    
    def is_session_expired(self, max_age_minutes=30):
        """Check if session should be considered expired based on age."""
        if not self.session_start_time:
            return True
        
        session_age = datetime.now() - self.session_start_time
        return session_age.total_seconds() > (max_age_minutes * 60)
    
    def should_renew_session(self):
        """Determine if we should renew the session."""
        # Check if session is too old
        if self.is_session_expired():
            print(f"🕐 Session expired (older than 30 minutes)")
            return True
        
        # Check if we haven't checked in a while
        if self.last_check_time:
            time_since_check = datetime.now() - self.last_check_time
            if time_since_check.total_seconds() > (5 * 60):  # 5 minutes
                print(f"🕐 Haven't checked session in {time_since_check.total_seconds()/60:.1f} minutes")
                return True
        
        return False

def login_and_setup_session(driver):
    """Handle the login process and return True if successful."""
    wait = WebDriverWait(driver, 20)
    
    try:
        
        # Wait for the OK modal to appear 
        try:
            # Try multiple selectors for the OK button
            ok_button = None
            selectors_to_try = [
                "//button[normalize-space()='OK']",
                "//button[contains(text(), 'OK')]",
                "//button[contains(@class, 'ui-button')]",
                "//button[@type='button']"
            ]
            
            for selector in selectors_to_try:
                try:
                    # Use shorter timeout for each selector attempt
                    ok_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"✅ Found OK button with selector: {selector}")
                    break
                except Exception as e:
                    print(f"⚠️ Selector failed: {selector} - {str(e)[:50]}...")
                    continue
            
            if ok_button:
                ok_button.click() 
                print("✅ OK modal clicked successfully")
            else:
                print(f"ℹ️ No OK modal found via Selenium - trying JavaScript approach")
                # Try JavaScript click as fallback
                try:
                    driver.execute_script("""
                        var buttons = document.querySelectorAll('button');
                        for (var i = 0; i < buttons.length; i++) {
                            var button = buttons[i];
                            if (button.textContent.trim() === 'OK' || button.textContent.includes('OK')) {
                                button.click();
                                console.log('Clicked OK button via JavaScript');
                                break;
                            }
                        }
                    """)
                    print("✅ OK button clicked via JavaScript")
                except Exception as js_error:
                    print(f"⚠️ JavaScript click failed: {js_error}")
                    print(f"ℹ️ Continuing without OK button")
                # Don't return False, just continue with login process
                
        except Exception as e:
            print(f"ℹ️ No OK modal appeared: {e}")
            return False

        # Wait for the form fields
        email_input = wait.until(EC.presence_of_element_located((By.ID, "user_email")))
        password_input = driver.find_element(By.ID, "user_password")

        # Fill in login details
        email_input.send_keys(EMAIL)
        password_input.send_keys(PASSWORD)

        # Click the policy checkbox
        policy_wrapper = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.icheckbox"))
        )
        policy_wrapper.click()

        # Click Sign In button
        sign_in_button = driver.find_element(By.NAME, "commit")
        sign_in_button.click()

        # Wait for dropdown to appear (indicates successful login)
        dropdown = wait.until(
            EC.presence_of_element_located((By.ID, "appointments_consulate_appointment_facility_id"))
        )
        
        # Select Astana
        select = Select(dropdown)
        select.select_by_visible_text("Astana")
        
        return True
        
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False

def check_appointments_only(driver):
    """Check for appointments without logging in (assumes already logged in)."""
    try:
        now = datetime.now().strftime("%H:%M:%S")
        # Check if session is still valid
        if not check_session_validity(driver):
            print(f"❌ Session is no longer valid at {now}")
            return False
        
        # Get available dates
        available_dates = get_available_dates_via_js(driver, facility_id="134", expedite="false")
        
        # Check if session expired (401) or transient network error (0)
        if available_dates == 'SESSION_EXPIRED':
            return 'SESSION_EXPIRED'
        if available_dates == 'NETWORK_ERROR':
            print(f"🌐 Network error detected at {now}")
            return 'NETWORK_ERROR'
        
        if available_dates is not None and isinstance(available_dates, list) and len(available_dates) > 0:
            print(f"✅ Found {len(available_dates)} available date(s)")
            
            # Cycle through all available dates to find an acceptable one
            acceptable_date = None
            acceptable_time = None
            
            for date_info in available_dates:
                current_date = date_info['date']
                print(f"\n🔍 Checking date: {current_date}")
                
                # Check if this date is acceptable
                if is_date_acceptable(current_date):
                    print(f"✅ Date {current_date} is acceptable, checking for available times...")
                    
                    # Get available times for this date
                    available_times = get_available_times_via_js(driver, facility_id="134", date=current_date, expedite="false")
                    
                    if available_times is not None and isinstance(available_times, dict) and 'available_times' in available_times:
                        times_list = available_times['available_times']
                        if len(times_list) > 0:
                            print(f"⏰ Found {len(times_list)} available time(s) for {current_date}")
                            
                            # Get the last available time
                            last_time = times_list[-1]
                            print(f"⏰ Last available time: {last_time}")
                            
                            # This date and time are acceptable
                            acceptable_date = current_date
                            acceptable_time = last_time
                            break
                        else:
                            print(f"⏰ No available times found for {current_date}")
                    else:
                        print(f"⏰ No available times found for {current_date}")
                else:
                    print(f"❌ Date {current_date} is not acceptable, trying next date...")
            
            # If we found an acceptable date and time, schedule the appointment
            if acceptable_date and acceptable_time:
                print(f"\n🎯 Scheduling appointment for {acceptable_date} at {acceptable_time}")
                
                # Schedule the appointment
                schedule_result = schedule_appointment_via_js(driver, facility_id="134", date=acceptable_date, time=acceptable_time)
                
                if schedule_result:
                    print("✅ Appointment scheduled successfully!")
                    telegram_message = f"🎉 APPOINTMENT SCHEDULED!\n\n"
                    telegram_message += f"📅 Date: {acceptable_date}\n"
                    telegram_message += f"⏰ Time: {acceptable_time}\n"
                    telegram_message += f"🔍 Check the console output for details."
                    send_telegram_message(telegram_message)
                    return True
                else:
                    print("❌ Failed to schedule appointment")
                    telegram_message = f"❌ Failed to schedule appointment for {acceptable_date} at {acceptable_time}"
                    send_telegram_message(telegram_message)
            else:
                print(f"\n❌ No acceptable dates found among {len(available_dates)} available dates")
                print("💡 All available dates either:")
                print("   - Fall in the unacceptable period (Dec 20 - Jan 15)")
                print("   - Have no available times")
        # else:
        #     print(f"📭 No available dates found at {now}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking appointments: {e}")
        return False

def check_session_validity(driver):
    """
    Check if the current session is still valid by making a simple API call.
    Returns True if session is valid, False otherwise.
    """
    try:
        # Check if we're still on the appointment page
        current_url = driver.current_url
        if "appointment" not in current_url:
            print(f"🔍 Session invalid: not on appointment page, URL: {current_url}")
            return False
        
        # Check if we can find the dropdown (indicates we're logged in)
        try:
            dropdown = driver.find_element(By.ID, "appointments_consulate_appointment_facility_id")
            if not dropdown.is_displayed():
                print("🔍 Session invalid: dropdown not visible")
                return False
        except:
            print("🔍 Session invalid: dropdown not found")
            return False
        
        # # Simple session check - just try to get available dates
        # result = get_available_dates_via_js(driver, facility_id="134", expedite="false")
        
        # # For session validation, we just need to know if the API call worked
        # # Even an empty array [] means the session is valid
        # if result is None:
        #     print(f"🔍 Session might be invalid result: {result}")
        #     return False
        # else:
        return True
        
    except Exception as e:
        print(f"🔍 Session check failed: {e}")
        return False

def main_persistent_session():
    """Main function that keeps browser open and checks appointments in a loop."""
    driver = None
    session_start_time = datetime.now()
    check_interval = 15  # Check every 5 minutes (300 seconds) to avoid rate limiting
    max_session_age = 120 * 60  # 45 minutes (conservative estimate)
    consecutive_failures = 0
    max_consecutive_failures = 3 
    
    try:
        # Login once
        print(f"🔐 Starting persistent session at {session_start_time.strftime('%H:%M')}")
        driver = create_driver()
        
        if not URL2:
            print("❌ URL2 environment variable is not set!")
            return
        
        try:
            driver.get(URL2)
            
            # Give the page extra time to fully render
            time.sleep(3)  # Wait 3 seconds for JavaScript to finish loading
            
            # Wait for the page to be fully interactive
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception as wait_error:
                print(f"⚠️ Page load wait failed: {wait_error}")
                print("🔄 Continuing anyway...")
            
        except Exception as nav_error:
            print(f"❌ Navigation failed: {nav_error}")
            return
        
        if not login_and_setup_session(driver):
            print("❌ Login failed")
            return
    
        print(f"🔄 Will check every {check_interval} seconds. Will quit after {max_session_age/60:.0f} minutes")
        print(f"🛡️ Rate limiting protection: max {max_consecutive_failures} consecutive failures")
        
        # Main monitoring loop
        consecutive_network_errors = 0  # track status 0 errors
        while True:
            current_time = datetime.now()
            session_age = (current_time - session_start_time).total_seconds()
            
            # Check if we should quit before session expires
            if session_age > max_session_age:
                print(f"⏰ Session age: {session_age/60:.1f} minutes - quitting to avoid expiration")
                break
            
            print(f"\n🔄 Checking appointments at {current_time.strftime('%H:%M:%S')} (session age: {session_age/60:.1f}min)")
            
            # Check for appointments
            try:
                appointment_result = check_appointments_only(driver)
                
                # Check if session expired (401 response)
                if appointment_result == 'SESSION_EXPIRED':
                    print("🔐 Session expired (401) - quitting loop")
                    break
                
                # Handle transient network errors (status 0)
                if appointment_result == 'NETWORK_ERROR':
                    consecutive_network_errors += 1
                    print(f"🌐 Network error (0) attempt {consecutive_network_errors}/3")
                    if consecutive_network_errors >= 3:
                        print("❌ 3 consecutive network errors - quitting loop")
                        break
                    # try again on next iteration without counting as general failure
                    continue
                
                if not appointment_result:
                    consecutive_failures += 1
                    print(f"❌ Session may have expired (failure #{consecutive_failures}/{max_consecutive_failures})")
                    
                    if consecutive_failures >= max_consecutive_failures:
                        print("❌ Too many consecutive failures, breaking loop")
                        break
                    else:
                        print("🔄 Will retry on next check...")
                else:
                    # Reset failure counter on successful check
                    consecutive_failures = 0
                    consecutive_network_errors = 0
                    
            except Exception as e:
                consecutive_failures += 1
                # Extract just the main error message without stack trace
                error_message = str(e)
                if "Message:" in error_message:
                    main_message = error_message.split("Message:")[1].split("(Session info:")[0].strip()
                    print(f"❌ Error during appointment check: {main_message}")
                else:
                    print(f"❌ Error during appointment check: {error_message}")
                
                print(f"🔄 Error #{consecutive_failures}/{max_consecutive_failures}")
                
                # If it's a connection/network error, try to continue
                if "timeout" in error_message.lower() or "connection" in error_message.lower():
                    print("🔄 Network error detected, will retry on next check...")
                    if consecutive_failures >= max_consecutive_failures:
                        print("❌ Too many consecutive failures, breaking loop")
                        break
                    continue
                else:
                    if consecutive_failures >= max_consecutive_failures:
                        print("❌ Too many consecutive failures, breaking loop")
                        break
                    print("🔄 Will retry on next check...")
            
            # Wait for next check with some randomness to avoid predictable patterns
            random_delay = random.uniform(0, 30)  # Add 0-60 seconds of randomness
            # total_delay = check_interval + random_delay
            total_delay = check_interval
            print(f"⏳ Waiting {total_delay:.0f} seconds until next check...")
            time.sleep(total_delay)
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        # Extract just the main error message without stack trace
        error_message = str(e)
        if "Message:" in error_message:
            main_message = error_message.split("Message:")[1].split("(Session info:")[0].strip()
            print(f"❌ Error in persistent session: {main_message}")
        else:
            print(f"❌ Error in persistent session: {error_message}")
    finally:
        # Clean up
        if driver:
            try:
                print("🔚 Closing browser...")
                input("Press Enter to close the browser...")
                driver.quit()
                print("✅ Browser closed successfully")
            except Exception as e:
                print(f"⚠️ Error closing driver: {e}")
                try:
                    import subprocess
                    subprocess.run(["pkill", "-f", "chrome"], check=False)
                    print("🧹 Killed remaining Chrome processes")
                except:
                    pass

def is_date_acceptable(appointment_date_str):
    """
    Check if the appointment date meets our criteria.
    
    Args:
        appointment_date_str: Date string in format "YYYY-MM-DD"
        
    Returns:
        bool: True if date is acceptable, False otherwise
    """
    try:
        # Parse the appointment date
        appointment_date = datetime.strptime(appointment_date_str, "%Y-%m-%d").date()
        
        # Define the unacceptable period (Dec 25 through Jan 12)
        # We'll check for any year, so we need to handle year boundaries
        current_year = appointment_date.year
        
        # Create the unacceptable period dates
        start_date = date(2025, 12, 20)
        end_date = date(2026, 1, 15)  # Next year's Jan 12
        
        # Check if the appointment date falls in the unacceptable period
        if start_date <= appointment_date <= end_date:
            print(f"❌ Date {appointment_date_str} falls in unacceptable period (Dec 20 - Jan 15")
            return False
        else:
            print(f"✅ Date {appointment_date_str} is acceptable")
            return True
            
    except ValueError as e:
        print(f"⚠️ Could not parse date {appointment_date_str}: {e}")
        return False

def main():
    driver = None
    now = datetime.now().strftime("%H:%M")
    
    try:
        driver = create_driver()  # Selenium Manager will locate ChromeDriver automatically
        wait = WebDriverWait(driver, 20)
        
        # print(f"🔄 Starting automation at {now}")
        
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
                    print(f"✅ Found {len(available_dates)} available date(s)")
                    
                    # Cycle through all available dates to find an acceptable one
                    acceptable_date = None
                    acceptable_time = None
                    
                    for date_info in available_dates:
                        current_date = date_info['date']
                        print(f"\n🔍 Checking date: {current_date}")
                        
                        # Check if this date is acceptable
                        if is_date_acceptable(current_date):
                            print(f"✅ Date {current_date} is acceptable, checking for available times...")
                            
                            # Get available times for this date
                            available_times = get_available_times_via_js(driver, facility_id="134", date=current_date, expedite="false")
                            
                            if available_times is not None and isinstance(available_times, dict) and 'available_times' in available_times:
                                times_list = available_times['available_times']
                                if len(times_list) > 0:
                                    print(f"⏰ Found {len(times_list)} available time(s) for {current_date}")
                                    
                                    # Get the last available time
                                    last_time = times_list[-1]
                                    print(f"⏰ Last available time: {last_time}")
                                    
                                    # This date and time are acceptable
                                    acceptable_date = current_date
                                    acceptable_time = last_time
                                    break
                                else:
                                    print(f"⏰ No available times found for {current_date}")
                            else:
                                print(f"⏰ No available times found for {current_date}")
                        else:
                            print(f"❌ Date {current_date} is not acceptable, trying next date...")
                    
                    # If we found an acceptable date and time, schedule the appointment
                    if acceptable_date and acceptable_time:
                        print(f"\n🎯 Scheduling appointment for {acceptable_date} at {acceptable_time}")
                        
                        # Schedule the appointment
                        schedule_result = schedule_appointment_via_js(driver, facility_id="134", date=acceptable_date, time=acceptable_time)
                        
                        if schedule_result:
                            print("✅ Appointment scheduled successfully!")
                            telegram_message = f"🎉 APPOINTMENT SCHEDULED!\n\n"
                            telegram_message += f"📅 Date: {acceptable_date}\n"
                            telegram_message += f"⏰ Time: {acceptable_time}\n"
                            telegram_message += f"🔍 Check the console output for details."
                            send_telegram_message(telegram_message)
                        else:
                            print("❌ Failed to schedule appointment")
                            telegram_message = f"❌ Failed to schedule appointment for {acceptable_date} at {acceptable_time}"
                            send_telegram_message(telegram_message)
                else:
                    print(f"📭 No available dates found at {now}")
            else:
                print(f"❌ API call failed at {now}")
                
        except TimeoutException:
            print("⚠️ Dropdown not found (possible logout/session expired). quiting...")
            driver.quit()
            return  #
            
    except Exception as e:
        # Extract just the main error message without stack trace
        error_message = str(e)
        if "Message:" in error_message:
            # For Selenium errors, extract just the main message
            main_message = error_message.split("Message:")[1].split("(Session info:")[0].strip()
            error_msg = f"❌ Connection error at {now}: {main_message}"
        else:
            error_msg = f"❌ Connection error at {now}: {error_message}"
        print(error_msg)
        
        # Clean up driver if it exists
        if driver:
            try:
                driver.quit()
            except:
                pass
        return



    finally:
        #input("Browser is open. Inspect the modal, then press Enter to continue...")
        # Optional: wait a moment after clicking (human-like pause)
        time.sleep(2)
        # input("🔎 Script finished. Press Enter to close the browser...")
        
        # Safely quit the driver
        if driver:
            try:
                driver.quit()
                # print("✅ Driver closed successfully")
            except Exception as e:
                print(f"⚠️ Error closing driver: {e}")
                # Force kill any remaining Chrome processes
                try:
                    import subprocess
                    subprocess.run(["pkill", "-f", "chrome"], check=False)
                    print("🧹 Killed remaining Chrome processes")
                except:
                    pass

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
        # Execute JavaScript to make the API call in the browser context
        js_code = f"""
        try {{
            var xhr = new XMLHttpRequest();
            xhr.open('GET', 'https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment/days/{facility_id}.json?appointments[expedite]={expedite}', false);
            xhr.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            xhr.send();

            // Return both status and response data
            var result = {{
                status: xhr.status,
                response: null,
                success: false
            }};
            
            if (xhr.status === 200 || xhr.status === 304) {{
                try {{
                    result.response = JSON.parse(xhr.responseText);
                    result.success = true;
                }} catch (e) {{
                    result.response = xhr.responseText;
                }}
            }} else {{
                result.response = xhr.responseText;
            }}
            
            return result;
        }} catch (e) {{
            return {{
                status: 0,
                response: null,
                success: false,
                error: e.toString()
            }};
        }}
        """
        
        result = driver.execute_script(js_code)
        now = datetime.now().strftime('%H:%M:%S')
        print(f"📊 API Result: {result} at {now}")
        
        # Handle 401 (session expired) and 0 (network error)
        if result and isinstance(result, dict):
            status = result.get('status')
            if status == 401:
                return 'SESSION_EXPIRED'
            if status == 0:
                # Transient network failure; let caller decide retry policy
                print("🌐 Network error (0) - treating as transient NETWORK_ERROR")
                return 'NETWORK_ERROR'
        
        # Return just the response data for compatibility with existing code
        if result and isinstance(result, dict) and 'response' in result:
            return result['response']
        else:
            return result
        
    except Exception as e:
        # Clean error handling - just return None without logging
        print(f"❌ get_available_dates_via_js exception: {e}")
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
        try {{
            var xhr = new XMLHttpRequest();
            xhr.open('GET', 'https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment/times/{facility_id}.json?date={date}&appointments[expedite]={expedite}', false);
            xhr.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            xhr.send();
            
            if (xhr.status === 200 || xhr.status === 304) {{
                try {{
                    return JSON.parse(xhr.responseText);
                }} catch (e) {{
                    return null;
                }}
            }} else {{
                return null;
            }}
        }} catch (e) {{
            return null;
        }}
        """
        
        result = driver.execute_script(js_code)
        return result
        
    except Exception as e:
        # Clean error handling - just return None without logging
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
        console.log('api response status: ' + xhr.status);
        console.log('api response text: ' + xhr.responseText);
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
    
    # Add stability options for frequent runs
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")  # Faster loading
    # Note: We need JavaScript for API calls, so don't disable it
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    
    # Set timeouts
    options.add_argument("--page-load-strategy=eager")
    
    # Optional: disable infobars / automation banner
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Disable logging to reduce noise
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-logging')
    options.add_argument('--log-level=3')

    # Create the driver using Selenium Manager (automatically handles ChromeDriver)
    driver = webdriver.Chrome(options=options)
    
    # Set timeouts - increased for slow page rendering
    driver.set_page_load_timeout(60)  # 60 seconds for page load
    driver.implicitly_wait(15)  # 15 seconds for element finding

    # Minimize the window so it doesn't block your screen
    # try:
    #     driver.minimize_window()
    # except Exception as e:
    #     # On some platforms/minor driver versions minimize might throw — ignore safely
    #     print(f"⚠️ Could not minimize window: {e}")

    return driver


if __name__ == "__main__":
    # Run the persistent session automation (keeps browser open, checks in loop)
    main_persistent_session()
    
    # Uncomment one of the lines below to use different versions:
    # main()  # Original version (login every time)