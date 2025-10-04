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
            print("ℹ️ No OK modal appeared, quitting...")
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
            
            # Make API call to get available dates
            available_dates = get_available_dates(driver, facility_id="134", expedite="false")
            
            if available_dates is not None:
                # Check if we have actual dates (not just empty array)
                if isinstance(available_dates, list) and len(available_dates) > 0:
                    telegram_message = f"📅 Available appointment dates found!\n\n"
                    telegram_message += f"🔍 Found {len(available_dates)} available dates."
                    #send_telegram_message(telegram_message)
                else:
                    print("📭 No available dates found")
                    #send_telegram_message("📭 No available appointment dates found")
            else:
                print("❌ API call failed")
                #send_telegram_message("❌ Failed to fetch appointment dates")
                
        except TimeoutException:
            print("⚠️ Dropdown not found (possible logout/session expired). quiting...")
            # driver.save_screenshot("error.png")  # save screenshot for debugging
            driver.quit()
            return  #



        # try:
        #     calendar_container = WebDriverWait(driver, 10).until(
        #         lambda d: d.find_element(By.ID, "consulate_date_time")
        #     )

        #     WebDriverWait(driver, 10).until(
        #         lambda d: "block" in calendar_container.get_attribute("style")
        #     )

        #     print(f"✅ Calendar is available at {now}")
        #     send_telegram_message("✅ Calendar is available")

        # except TimeoutException:
        #     print(f"❌ Calendar is not availabe at {now}")
            #send_telegram_message("❌ Calendar stayed HIDDEN (display:none)")


        # wait until the button is present in DOM
        # schedule_button = wait.until(
        #     EC.presence_of_element_located((By.ID, "appointments_submit"))
        # )

        # check if it's enabled or disabled
        # if schedule_button.is_enabled():
        #     print("✅ Schedule Appointment button is ENABLED, clicking it...")
        #     send_telegram_message("✅ Schedule Appointment button is ENABLED, clicking it...")                
        #     schedule_button.click()
        #     send_html_to_telegram(driver) 
        # else:
        #     print(f"❌ Button is DISABLED at {now}")
            # send_telegram_message("❌ Schedule Appointment button is DISABLED")
            # send_html_to_telegram(driver)  

    finally:
        #input("Browser is open. Inspect the modal, then press Enter to continue...")
        # Optional: wait a moment after clicking (human-like pause)
        time.sleep(2)
        input("🔎 Script finished. Press Enter to close the browser...")
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

def get_available_dates(driver, facility_id="134", expedite="false"):
    """
    Makes API call to get available appointment dates for the selected facility.
    
    Args:
        driver: Selenium WebDriver instance with active session
        facility_id: Facility ID (134 for Astana, 135 for Almaty)
        expedite: Whether to check for expedited appointments
    
    Returns:
        dict: Available dates data or None if failed
    """
    try:
        # Extract cookies from the Selenium session
        selenium_cookies = driver.get_cookies()
        
        # Convert Selenium cookies to requests format
        cookies_dict = {}
        for cookie in selenium_cookies:
            cookies_dict[cookie['name']] = cookie['value']
        
        # Construct the API URL
        api_url = f"https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment/days/{facility_id}.json"
        params = {"appointments[expedite]": expedite}
        
        
        # Extract CSRF token from the page
        csrf_token = None
        try:
            csrf_meta = driver.find_element(By.CSS_SELECTOR, 'meta[name="csrf-token"]')
            csrf_token = csrf_meta.get_attribute('content')
        except Exception as e:
            print(f"⚠️ Could not extract CSRF token: {e}")
        
        # Make the API request with all browser headers
        response = requests.get(
            api_url,
            params=params,
            cookies=cookies_dict,
            headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
                'Host': 'ais.usvisa-info.com',
                'Referer': 'https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment',
                'Sec-Ch-Ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"macOS"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                **({'X-Csrf-Token': csrf_token} if csrf_token else {})
            }
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"📊 Available dates response: {data}")
                return data
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON response: {e}")
                print(f"📄 Raw response length: {len(response.text)}")
                print(f"📄 Raw response content: '{response.text}'")
                print(f"📄 Response headers: {dict(response.headers)}")
                # If it's just an empty response, return empty list
                if not response.text.strip():
                    print("📭 Treating empty response as no available dates")
                    return []
                return None
        else:
            print(f"❌ API call failed with status {response.status_code}")
            print(f"📄 Response: {response.text[:500]}...")
            return None
            
    except Exception as e:
        print(f"❌ Error making API call: {e}")
        return None


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


def test_api_with_browser_cookies():
    """
    Test function to try the API call with the exact cookies you provided.
    This can help debug if the issue is with cookie extraction.
    """
    # Your exact cookies from the browser
    cookies_string = "_gid=GA1.2.841742009.1759209219; _gat=1; _ga_W1JNKHTW0Y=GS2.2.s1759469772$o25$g0$t1759469772$j60$l0$h0; _yatri_session=cQRpVYWA2CRnwVRTHHVAh4BjCw6fPHrxRAE%2F4ksa4fnBGzull6XEpuH%2F1Mpw5CSCFpipKJOu%2F%2BSVUu2sZP0%2BPuY%2BRuicPTxWG3Ci7k6r2E0DXma%2BT4tv6YEUPhXd1ldVFXwGMQ5nLgpbOKvMZk5LAJlLmEy%2BTFBAgZPMb9vHAK0GU5si%2FfyCrAEGaiyfQU7G6FKfFfIlp8ShMHujy3FKHxxuiNzjnlK%2FtUdIF5iLO9Wa4idkGa7PnuHLTeHPTNT2vlJ72AoXq75vVVq8NPRtTH%2FP8CD%2FrbMq4Qz%2BiCrPHme%2FbqxAxniHvmWflUdi39uwyCJxJ2krg%2BuzA2Yy29yK%2FbEIijNexjQtaANVCWVl%2FXsMZ6jzdnlJNMBFjFA5o4PTSbiAH9GWiSG4A3GeP9ic0MP6JwzOKyj6U3E%2Btc6LaYM6PeF%2BO1xCS7Jh6U%2BmuhMwHVESgUy2jDa7VjPm5AeZX4KrfdGIkaQJbcefaUyofK6KGxPAy7mLQlneLnLoGg8owaFT31An2fYjFNgHuup0F5hAw1WJVF34MwaCnplRE59K7AuZ%2FwGU47pGltH2k3ow8Rb9XW038O7yEdZp4YB65WvqlMphRh3GK6bERMTLpjUSu8jNi84FN%2BOC84aeLFm28%2BzNTgUh3kFE0rwKi43UK4NJx66cHAAy6%2FcnU8TywKXRW8EIwrxqQ64LfoxUgemQZqS%2FIowpvPVdz17oReZR4i3eJEk37%2Fgn5JXTOTQ8rv%2BZzV1YvbQSEknEXnfE72bEsLYf8ix1WGiZKlQqN7hwOLoqaCz3SA5HSkftLUIzoFNFsJBRw5VC39CBlHT7s9doIYg%3D--BFuFSMZ5AvkTlIbi--K1fP9m%2BFLJJhSV6sxhHyNg%3D%3D; _ga_CSLL4ZEK4L=GS2.1.s1759469772$o26$g1$t1759469787$j45$l0$h0; _ga=GA1.2.214441629.1753293753"
    
    print("🧪 Testing API call with browser cookies...")
    return get_available_dates_standalone(cookies_string, facility_id="134", expedite="false")

def get_available_dates_standalone(cookies_string, facility_id="134", expedite="false"):
    """
    Standalone function to get available dates using cookies string.
    This can be used independently of Selenium automation.
    
    Args:
        cookies_string: Cookie string from browser (e.g., "_gid=GA1.2.841742009.1759209219; _gat=1; ...")
        facility_id: Facility ID (134 for Astana, 135 for Almaty)
        expedite: Whether to check for expedited appointments
    
    Returns:
        dict: Available dates data or None if failed
    """
    try:
        # Parse cookies string into dictionary
        cookies_dict = {}
        if cookies_string:
            for cookie in cookies_string.split(';'):
                if '=' in cookie:
                    name, value = cookie.strip().split('=', 1)
                    cookies_dict[name] = value
        
        # Construct the API URL
        api_url = f"https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment/days/{facility_id}.json"
        params = {"appointments[expedite]": expedite}
        
        print(f"🔍 Making standalone API call to: {api_url}")
        print(f"📋 Parameters: {params}")
        
        # Make the API request
        response = requests.get(
            api_url,
            params=params,
            cookies=cookies_dict,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://ais.usvisa-info.com/en-kz/niv/schedule/70570056/appointment'
            }
        )
        
        print(f"📊 API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ Successfully retrieved available dates data")
                return data
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON response: {e}")
                print(f"📄 Raw response: {response.text[:500]}...")
                # If it's just an empty response, return empty list
                if not response.text.strip():
                    print("📭 Treating empty response as no available dates")
                    return []
                return None
        else:
            print(f"❌ API call failed with status {response.status_code}")
            print(f"📄 Response: {response.text[:500]}...")
            return None
            
    except Exception as e:
        print(f"❌ Error making standalone API call: {e}")
        return None

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

def example_standalone_usage():
    """
    Example of how to use the standalone API function.
    Replace the cookies string with actual cookies from your browser session.
    """
    # Example cookies string (replace with actual cookies from browser)
    cookies_string = "_gid=GA1.2.841742009.1759209219; _gat=1; _ga_W1JNKHTW0Y=GS2.2.s1759469772$o25$g0$t1759469772$j60$l0$h0; _yatri_session=cQRpVYWA2CRnwVRTHHVAh4BjCw6fPHrxRAE%2F4ksa4fnBGzull6XEpuH%2F1Mpw5CSCFpipKJOu%2F%2BSVUu2sZP0%2BPuY%2BRuicPTxWG3Ci7k6r2E0DXma%2BT4tv6YEUPhXd1ldVFXwGMQ5nLgpbOKvMZk5LAJlLmEy%2BTFBAgZPMb9vHAK0GU5si%2FfyCrAEGaiyfQU7G6FKfFfIlp8ShMHujy3FKHxxuiNzjnlK%2FtUdIF5iLO9Wa4idkGa7PnuHLTeHPTNT2vlJ72AoXq75vVVq8NPRtTH%2FP8CD%2FrbMq4Qz%2BiCrPHme%2FbqxAxniHvmWflUdi39uwyCJxJ2krg%2BuzA2Yy29yK%2FbEIijNexjQtaANVCWVl%2FXsMZ6jzdnlJNMBFjFA5o4PTSbiAH9GWiSG4A3GeP9ic0MP6JwzOKyj6U3E%2Btc6LaYM6PeF%2BO1xCS7Jh6U%2BmuhMwHVESgUy2jDa7VjPm5AeZX4KrfdGIkaQJbcefaUyofK6KGxPAy7mLQlneLnLoGg8owaFT31An2fYjFNgHuup0F5hAw1WJVF34MwaCnplRE59K7AuZ%2FwGU47pGltH2k3ow8Rb9XW038O7yEdZp4YB65WvqlMphRh3GK6bERMTLpjUSu8jNi84FN%2BOC84aeLFm28%2BzNTgUh3kFE0rwKi43UK4NJx66cHAAy6%2FcnU8TywKXRW8EIwrxqQ64LfoxUgemQZqS%2FIowpvPVdz17oReZR4i3eJEk37%2Fgn5JXTOTQ8rv%2BZzV1YvbQSEknEXnfE72bEsLYf8ix1WGiZKlQqN7hwOLoqaCz3SA5HSkftLUIzoFNFsJBRw5VC39CBlHT7s9doIYg%3D--BFuFSMZ5AvkTlIbi--K1fP9m%2BFLJJhSV6sxhHyNg%3D%3D; _ga_CSLL4ZEK4L=GS2.1.s1759469772$o26$g1$t1759469787$j45$l0$h0; _ga=GA1.2.214441629.1753293753"
    
    # Get available dates for Astana (facility_id=134)
    available_dates = get_available_dates_standalone(cookies_string, facility_id="134", expedite="false")
    
    if available_dates:
        process_available_dates(available_dates)
    else:
        print("❌ Failed to get available dates")

if __name__ == "__main__":
    # Uncomment the line below to test standalone API usage
    # example_standalone_usage()
    
    # Uncomment the line below to test with browser cookies
    # test_api_with_browser_cookies()
    
    # Run the main Selenium automation
    main()