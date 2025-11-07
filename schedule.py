import os
import requests
import time
import json
import random
import logging
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, date
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

# Setup logging to file with yymmdd.log format
def setup_logging():
    """Setup logging with current date filename"""
    log_filename = datetime.now().strftime("%y%m%d.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%H:%M:%S',  # Only time, no date (date is in filename)
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()  # Also print to console
        ]
    )
    return log_filename

def check_and_rotate_log():
    """Check if we need to rotate to a new log file for a new day"""
    current_date_log = datetime.now().strftime("%y%m%d.log")
    
    # Get the current log file from the first file handler
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler):
            current_log_file = handler.baseFilename
            if not current_log_file.endswith(current_date_log):
                log_info(f"📅 New day detected! Rotating from {os.path.basename(current_log_file)} to {current_date_log}")
                
                # Remove old handlers
                logging.getLogger().handlers.clear()
                
                # Setup new logging with new date
                setup_logging()
                break

# Initial logging setup
current_log_file = setup_logging()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
URL = os.getenv("URL")
URL2 = os.getenv("URL2")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

# Helper function to log messages
def log_info(message):
    """Log message to both file and console"""
    logging.info(message)

def log_error(message):
    """Log error message to both file and console"""
    logging.error(message)

def log_warning(message):
    """Log warning message to both file and console"""
    logging.warning(message)


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
                    log_info(f"✅ Found OK button with selector: {selector}")
                    break
                except Exception as e:
                    log_warning(f"⚠️ Selector failed: {selector} - {str(e)[:50]}...")
                    continue
            
            if ok_button:
                ok_button.click() 
                log_info("✅ OK modal clicked successfully")
            else:
                log_info(f"ℹ️ No OK modal found via Selenium - trying JavaScript approach")
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
                    log_info("✅ OK button clicked via JavaScript")
                except Exception as js_error:
                    log_warning(f"⚠️ JavaScript click failed: {js_error}")
                    log_info(f"ℹ️ Continuing without OK button")
                # Don't return False, just continue with login process
                
        except Exception as e:
            log_info(f"ℹ️ No OK modal appeared: {e}")
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
        log_error(f"❌ Login failed: {e}")
        return False

def check_appointments_only(driver):
    """Check for appointments without logging in (assumes already logged in)."""
    try:
        now = datetime.now().strftime("%H:%M:%S")
        # Check if session is still valid
        if not check_session_validity(driver):
            log_error(f"❌ Session is no longer valid at {now}")
            return False
        
        # Get available dates
        available_dates = get_available_dates_via_js(driver, facility_id="134", expedite="false")
        
        # Check if session expired (401) or transient network error (0)
        if available_dates == 'SESSION_EXPIRED':
            return 'SESSION_EXPIRED'
        if available_dates == 'NETWORK_ERROR':
            return 'NETWORK_ERROR'
        
        if available_dates is not None and isinstance(available_dates, list) and len(available_dates) > 0:
            log_info(f"✅ Found {len(available_dates)} available date(s)")
            
            # Cycle through all available dates to find an acceptable one
            acceptable_date = None
            acceptable_time = None
            
            for date_info in available_dates:
                current_date = date_info['date']
                log_info(f"\n🔍 Checking date: {current_date}")
                
                # Check if this date is acceptable
                if is_date_acceptable(current_date):
                    log_info(f"✅ Date {current_date} is acceptable, checking for available times...")
                    
                    # Get available times for this date
                    available_times = get_available_times_via_js(driver, facility_id="134", date=current_date, expedite="false")
                    
                    if available_times is not None and isinstance(available_times, dict) and 'available_times' in available_times:
                        times_list = available_times['available_times']
                        if len(times_list) > 0:
                            log_info(f"⏰ Found {len(times_list)} available time(s) for {current_date}")
                            
                            # Get the last available time
                            last_time = times_list[-1]
                            log_info(f"⏰ Last available time: {last_time}")
                            
                            # This date and time are acceptable
                            acceptable_date = current_date
                            acceptable_time = last_time
                            break
                        else:
                            log_info(f"⏰ No available times found for {current_date}")
                    else:
                        log_info(f"⏰ No available times found for {current_date}")
                else:
                    log_info(f"❌ Date {current_date} is not acceptable, trying next date...")
            
            # If we found an acceptable date and time, schedule the appointment
            if acceptable_date and acceptable_time:
                log_info(f"\n🎯 Scheduling appointment for {acceptable_date} at {acceptable_time}")
                
                # Schedule the appointment
                schedule_result = schedule_appointment_via_js(driver, facility_id="134", date=acceptable_date, time=acceptable_time)
                
                if schedule_result:
                    log_info("✅ Appointment scheduled successfully!")
                    telegram_message = f"🎉 APPOINTMENT SCHEDULED!\n\n"
                    telegram_message += f"📅 Date: {acceptable_date}\n"
                    telegram_message += f"⏰ Time: {acceptable_time}\n"
                    telegram_message += f"🔍 Check the console output for details."
                    send_telegram_message(telegram_message)
                    return True
                else:
                    log_error("❌ Failed to schedule appointment")
                    telegram_message = f"❌ Failed to schedule appointment for {acceptable_date} at {acceptable_time}"
                    send_telegram_message(telegram_message)
            else:
                log_info(f"\n❌ No acceptable dates found among {len(available_dates)} available dates")
                log_info("💡 All available dates either:")
                log_info("   - Fall in the unacceptable period (Dec 20 - Jan 15)")
                log_info("   - Have no available times")
        
        return True
        
    except Exception as e:
        log_error(f"❌ Error checking appointments: {e}")
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
            log_warning(f"🔍 Session invalid: not on appointment page, URL: {current_url}")
            return False
        
        # Check if we can find the dropdown (indicates we're logged in)
        try:
            dropdown = driver.find_element(By.ID, "appointments_consulate_appointment_facility_id")
            if not dropdown.is_displayed():
                log_warning("🔍 Session invalid: dropdown not visible")
                return False
        except:
            log_warning("🔍 Session invalid: dropdown not found")
            return False
        
        return True
        
    except Exception as e:
        log_warning(f"🔍 Session check failed: {e}")
        return False

def main_persistent_session():
    """Main function that keeps browser open and checks appointments in a loop."""
    driver = None
    session_start_time = datetime.now()
    check_interval = 15  # Check every 5 minutes (300 seconds) to avoid rate limiting
    max_session_age = 120 * 60  # 45 minutes (conservative estimate)
    consecutive_failures = 0
    # max_consecutive_failures = 3 
    
    try:
        # Login once
        logging.info(f"🔐 Starting persistent session")
        driver = create_driver()
        
        if not URL2:
            log_error("❌ URL2 environment variable is not set!")
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
                log_warning(f"⚠️ Page load wait failed: {wait_error}")
                log_info("🔄 Continuing anyway...")
            
        except Exception as nav_error:
            # Extract just the main error message without stack trace
            error_message = str(nav_error)
            if "Message:" in error_message:
                main_message = error_message.split("Message:")[1].split("(Session info:")[0].strip()
                log_error(f"❌ Navigation failed: {main_message}")
            else:
                log_error(f"❌ Navigation failed: {error_message}")
            return
        
        if not login_and_setup_session(driver):
            log_error("❌ Login failed")
            return
    
        log_info(f"🔄 Will check every {check_interval} seconds. Will quit after {max_session_age/60:.0f} minutes")
        
        # Main monitoring loop
        consecutive_network_errors = 0  # track status 0 errors
        while True:
            current_time = datetime.now()
            session_age = (current_time - session_start_time).total_seconds()
            
            # Check if we should quit before session expires
            if session_age > max_session_age:
                log_info(f"⏰ Session age: {session_age/60:.1f} minutes - quitting to avoid expiration")
                break
            
            # Check for appointments
            try:
                appointment_result = check_appointments_only(driver)
                
                # Check if session expired (401 response)
                if appointment_result == 'SESSION_EXPIRED':
                    log_info("🔐 Session expired (401) - quitting loop")
                    break
                
                # Handle transient network errors (status 0)
                if appointment_result == 'NETWORK_ERROR':
                    consecutive_network_errors += 1
                    log_warning(f"🌐 Network error (0) attempt {consecutive_network_errors}")
                    # if consecutive_network_errors >= 3:
                    #     log_error("❌ 3 consecutive network errors - quitting loop")
                    #     break
                    # try again on next iteration without counting as general failure
                    continue
                
                if not appointment_result:
                    consecutive_failures += 1
                    log_warning(f"❌ Session may have expired (failure #{consecutive_failures})")
                    
                    # if consecutive_failures >= max_consecutive_failures:
                    #     log_error("❌ Too many consecutive failures, breaking loop")
                    #     break
                    # else:
                    #     log_info("🔄 Will retry on next check...")
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
                    log_error(f"❌ Error during appointment check: {main_message}")
                else:
                    log_error(f"❌ Error during appointment check: {error_message}")
                
                log_warning(f"🔄 Error #{consecutive_failures}")
                
                # If it's a connection/network error, try to continue
                if "timeout" in error_message.lower() or "connection" in error_message.lower():
                    log_info("🔄 Network error detected, will retry on next check...")
                    # if consecutive_failures >= max_consecutive_failures:
                    #     log_error("❌ Too many consecutive failures, breaking loop")
                    #     break
                    continue
                else:
                    # if consecutive_failures >= max_consecutive_failures:
                    #     log_error("❌ Too many consecutive failures, breaking loop")
                    #     break
                    log_info("🔄 Will retry on next check...")
            
            # Wait for next check with some randomness to avoid predictable patterns
            random_delay = random.uniform(0, 30)  # Add 0-60 seconds of randomness
            # total_delay = check_interval + random_delay
            total_delay = check_interval
            # log_info(f"⏰ session age: {session_age/60:.1f}min, waiting {total_delay:.0f} seconds until next check...")
            log_info(f"⏰ session age: {session_age/60:.1f}min")
            time.sleep(total_delay)
            
    except KeyboardInterrupt:
        log_info("\n🛑 Interrupted by user")
    except Exception as e:
        # Extract just the main error message without stack trace
        error_message = str(e)
        if "Message:" in error_message:
            main_message = error_message.split("Message:")[1].split("(Session info:")[0].strip()
            log_error(f"❌ Error in persistent session: {main_message}")
        else:
            log_error(f"❌ Error in persistent session: {error_message}")
    finally:
        # Clean up
        if driver:
            try:
                log_info("🔚 Closing browser...")
                # input("Press Enter to close the browser...")
                driver.quit()
                log_info("✅ Browser closed successfully")
            except Exception as e:
                log_warning(f"⚠️ Error closing driver: {e}")
                try:
                    import subprocess
                    subprocess.run(["pkill", "-f", "chrome"], check=False)
                    log_info("🧹 Killed remaining Chrome processes")
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
            log_info(f"❌ Date {appointment_date_str} falls in unacceptable period (Dec 20 - Jan 15")
            return False
        else:
            log_info(f"✅ Date {appointment_date_str} is acceptable")
            return True
            
    except ValueError as e:
        log_warning(f"⚠️ Could not parse date {appointment_date_str}: {e}")
        return False

def main_persistent_session():
    """
    Main persistent session that runs indefinitely until an appointment is scheduled.
    Restarts browser session when it expires (401) or after 60 minutes.
    """
    session_start_time = datetime.now()
    log_info(f"🔐 Starting persistent session at {session_start_time.strftime('%H:%M')}")
    
    while True:  # Main loop - only exits when appointment is scheduled
        driver = None
        session_start = datetime.now()
        
        try:
            # Login and setup session
            log_info("🚀 Starting new browser session...")
            driver = create_driver()
            wait = WebDriverWait(driver, 20)
            
            # Navigate to login page
            driver.get(URL2)
            log_info(f"🌐 Navigated to {URL2}")
            
            # Handle OK modal if it appears
            try:
                ok_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='OK']"))
                )
                ok_button.click()
                log_info("✅ Clicked OK modal")
            except Exception:
                log_info("ℹ️ No OK modal appeared, continuing...")

            # Login process
            email_input = wait.until(EC.presence_of_element_located((By.ID, "user_email")))
            password_input = driver.find_element(By.ID, "user_password")
            
            email_input.send_keys(EMAIL)
            password_input.send_keys(PASSWORD)
            
            # Click policy checkbox
            policy_wrapper = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.icheckbox"))
            )
            policy_wrapper.click()
            
            # Sign in
            sign_in_button = driver.find_element(By.NAME, "commit")
            sign_in_button.click()
            log_info("🔐 Login completed")
            
            # Select Astana from dropdown
            dropdown = wait.until(
                EC.presence_of_element_located((By.ID, "appointments_consulate_appointment_facility_id"))
            )
            select = Select(dropdown)
            select.select_by_visible_text("Astana")
            log_info("🏛️ Selected Astana facility")
            
            # Now start the checking loop for this session
            appointment_scheduled = check_appointments_loop(driver, session_start)
            
            if appointment_scheduled:
                log_info("🎉 Appointment scheduled! Exiting main loop.")
                break
            else:
                log_info("🔄 Session ended, restarting...")
                
        except Exception as e:
            error_message = str(e)
            if "Message:" in error_message:
                main_message = error_message.split("Message:")[1].split("(Session info:")[0].strip()
                log_error(f"❌ Session error: {main_message}")
                
                # Check if it's a connection error that needs a delay
                if "ERR_CONNECTION_REFUSED" in main_message or "ERR_CONNECTION_RESET" in main_message or "timeout" in main_message.lower():
                    log_info("⏳ Connection error detected, waiting 5 minutes before retry...")
                    time.sleep(300)  # Wait 5 minutes before retrying
            else:
                log_error(f"❌ Session error: {error_message}")
                
                # # Check if it's a connection error that needs a delay
                # if "connection" in error_message.lower() or "timeout" in error_message.lower():
                #     log_info("⏳ Connection error detected, waiting 60 seconds before retry...")
                #     time.sleep(60)  # Wait 1 minute before retrying
        
        finally:
            # Clean up driver
            if driver:
                try:
                    driver.quit()
                    # log_info("🧹 Browser session closed")
                except Exception as e:
                    log_warning(f"⚠️ Error closing driver: {e}")
                    try:
                        import subprocess
                        subprocess.run(["pkill", "-f", "chrome"], check=False)
                        log_info("🧹 Killed remaining Chrome processes")
                    except:
                        pass


def check_appointments_loop(driver, session_start):
    """
    Check for appointments in a loop until session expires or appointment is scheduled.
    Returns True if appointment was scheduled, False if session ended.
    """
    check_interval = 15  # Check every 30 seconds
    max_session_age = 60 * 60  # 60 minutes in seconds
    consecutive_failures = 0
    # max_consecutive_failures = 3
    
    while True:
        current_time = datetime.now()
        session_age = (current_time - session_start).total_seconds()
        
        # Check if session is too old (60 minutes)
        if session_age > max_session_age:
            log_info(f"⏰ Session age {session_age/60:.1f}min exceeded 60min limit, restarting...")
            # Check if we need to rotate log file for new day
            check_and_rotate_log()
            return False
        
        log_info(f"🔍 Checking appointments (session age: {session_age/60:.1f}min)")
        
        try:
            # Check for appointments
            appointment_result = check_appointments_only(driver)
            
            if appointment_result == 'SESSION_EXPIRED':
                log_warning("🔐 Session expired (401), restarting...")
                return False
            elif appointment_result == 'NETWORK_ERROR':
                log_warning("🌐 Network error, retrying...")
                consecutive_failures += 1
                # if consecutive_failures >= max_consecutive_failures:
                #     log_error("❌ Too many network errors, restarting session...")
                #     return False
            elif appointment_result == True:
                # Appointment was scheduled successfully
                log_info("🎉 Appointment scheduled successfully!")
                return True
            else:
                # No appointments found, reset failure counter
                consecutive_failures = 0
                # log_info("📭 No appointments available, continuing to check...")
                
        except Exception as e:
            consecutive_failures += 1
            log_error(f"❌ Error checking appointments: {e}")
            
            # if consecutive_failures >= max_consecutive_failures:
            #     log_error("❌ Too many consecutive failures, restarting session...")
            #     return False
        
        # Wait before next check
        # log_info(f"⏳ Waiting {check_interval} seconds until next check...")
        time.sleep(check_interval)


def check_appointments_only(driver):
    """
    Check for appointments without re-logging in.
    Returns True if appointment scheduled, False if no appointments, 
    'SESSION_EXPIRED' if 401, 'NETWORK_ERROR' if network issues.
    """
    try:
        # Get available dates
        available_dates = get_available_dates_via_js(driver, facility_id="134", expedite="false")
        
        if available_dates == 'SESSION_EXPIRED':
            return 'SESSION_EXPIRED'
        if available_dates == 'NETWORK_ERROR':
            return 'NETWORK_ERROR'
        
        if available_dates is not None and isinstance(available_dates, list) and len(available_dates) > 0:
            log_info(f"✅ Found {len(available_dates)} available date(s)")
            
            # Find acceptable date and time
            for date_info in available_dates:
                current_date = date_info['date']
                log_info(f"🔍 Checking date: {current_date}")
                
                if is_date_acceptable(current_date):
                    log_info(f"✅ Date {current_date} is acceptable, checking times...")
                    
                    # Get available times
                    available_times = get_available_times_via_js(driver, facility_id="134", date=current_date, expedite="false")
                    
                    if available_times == 'SESSION_EXPIRED':
                        return 'SESSION_EXPIRED'
                    if available_times == 'NETWORK_ERROR':
                        return 'NETWORK_ERROR'
                    
                    if available_times and isinstance(available_times, dict) and 'available_times' in available_times:
                        times_list = available_times['available_times']
                        if len(times_list) > 0:
                            last_time = times_list[-1]
                            log_info(f"⏰ Found time: {last_time}")
                            
                            # Schedule the appointment
                            log_info(f"🎯 Scheduling appointment for {current_date} at {last_time}")
                            schedule_result = schedule_appointment_via_js(driver, facility_id="134", date=current_date, time=last_time)
                            
                            if schedule_result:
                                log_info("✅ Appointment scheduled successfully!")
                                telegram_message = f"🎉 APPOINTMENT SCHEDULED!\n\n"
                                telegram_message += f"📅 Date: {current_date}\n"
                                telegram_message += f"⏰ Time: {last_time}\n"
                                send_telegram_message(telegram_message)
                                return True
                            else:
                                log_error("❌ Failed to schedule appointment")
                                return False
                        else:
                            log_info(f"⏰ No times available for {current_date}")
                    else:
                        log_info(f"⏰ No times available for {current_date}")
                else:
                    log_info(f"❌ Date {current_date} not acceptable")
        # else:
        #     log_info("📭 No available dates found")
            
        return False
        
    except Exception as e:
        log_error(f"❌ Error in check_appointments_only: {e}")
        return False


def main():
    """
    Legacy main function - now just calls the persistent session.
    """
    main_persistent_session()

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
        log_info("📄 Sent page HTML to Telegram successfully!")
    else:
        log_warning(f"⚠️ Failed to send HTML: {response.text}")


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
        log_info(f"📊 API Result: {result}")
        
        # Handle 401 (session expired) and 0 (network error)
        if result and isinstance(result, dict):
            status = result.get('status')
            if status == 401:
                return 'SESSION_EXPIRED'
            if status == 0:
                # Transient network failure; let caller decide retry policy
                return 'NETWORK_ERROR'
        
        # Return just the response data for compatibility with existing code
        if result and isinstance(result, dict) and 'response' in result:
            return result['response']
        else:
            return result
        
    except Exception as e:
        # Clean error handling - just return None without logging
        log_error(f"❌ get_available_dates_via_js exception: {e}")
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
        log_info(f"📝 Scheduling appointment for {date} at {time}")
        
        # Get CSRF token from the page
        csrf_token = None
        try:
            csrf_meta = driver.find_element(By.CSS_SELECTOR, 'meta[name="csrf-token"]')
            csrf_token = csrf_meta.get_attribute('content')
            log_info(f"🔐 Using CSRF token: {csrf_token[:20]}...")
        except Exception as e:
            log_warning(f"⚠️ Could not extract CSRF token: {e}")
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
        log_info(f"📊 Schedule response status: {result['status']}")
        log_info(f"📊 Final URL: {result['finalUrl']}")
        log_info(f"📊 Response headers: {result['headers']}")
        
        # Debug: Check current page URL and cookies
        current_url = driver.current_url
        log_info(f"🌐 Current page URL: {current_url}")
        
        # Check if we're still logged in by looking for logout link or user info
        try:
            logout_element = driver.find_element(By.CSS_SELECTOR, "a[href*='sign_out']")
            log_info("✅ Still logged in (logout link found)")
        except:
            log_warning("❌ Not logged in (no logout link found)")
        
        if result['status'] in [200, 302]:
            # Save the response HTML to file
            with open("appointment_result.html", "w", encoding="utf-8") as f:
                f.write(result['responseText'])
            log_info("💾 Appointment result saved to appointment_result.html")
            
            # Send the HTML file via Telegram
            send_html_to_telegram(driver, "appointment_result.html")
            
            return True
        else:
            log_error(f"❌ Schedule request failed with status {result['status']}")
            log_error(f"📄 Response: {result['responseText'][:500]}...")
            return False
            
    except Exception as e:
        log_error(f"❌ Error scheduling appointment: {e}")
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
            log_info("📩 Telegram message sent successfully!")
        else:
            log_warning(f"⚠️ Failed to send message: {response.text}")
    except Exception as e:
        log_warning(f"⚠️ Error sending message: {e}")



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

    # Create the driver using webdriver-manager to automatically handle ChromeDriver version matching
    # This will ignore the outdated driver in PATH and download the correct version
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Set timeouts - increased for slow page rendering
    driver.set_page_load_timeout(60)  # 60 seconds for page load
    driver.implicitly_wait(15)  # 15 seconds for element finding

    # Minimize the window so it doesn't block your screen
    # try:
    #     driver.minimize_window()
    # except Exception as e:
    #     # On some platforms/minor driver versions minimize might throw — ignore safely

    return driver


if __name__ == "__main__":
    # Run the persistent session automation (keeps browser open, checks in loop)
    main_persistent_session()
    
    # Uncomment one of the lines below to use different versions:
    # main()  # Original version (login every time)