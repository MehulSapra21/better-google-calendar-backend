from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import time
import traceback # Added to capture detailed errors

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://better-google-calendar.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Credentials(BaseModel):
    username: str
    password: str

@app.get("/")
def read_root():
    return {"status": "Backend is running!"}

@app.post("/scrape")
def scrape_amizone(creds: Credentials):
    options = uc.ChromeOptions()
    # options.add_argument('--headless') 
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage') # CRITICAL FIX FOR DOCKER/RENDER
    
    # Disable the "Save Password" prompt
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = None
    try:
        driver = uc.Chrome(options=options)
        driver.get("https://s.amizone.net/")
        
        # 1. Wait for the page structure to load
        username_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "_UserName"))
        )

        # 2. Wait for Cloudflare Turnstile to pass
        def turnstile_passed(d):
            try:
                token = d.find_element(By.NAME, "cf-turnstile-response").get_attribute("value")
                return token != "" and token is not None
            except:
                return False
        
        WebDriverWait(driver, 30).until(turnstile_passed)
        
        # 3. Inject credentials and click
        username_field.send_keys(creds.username)
        driver.find_element(By.NAME, "_Password").send_keys(creds.password)
        
        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        submit_btn.click()

        # 4. Handle Dashboard Popups (Aggressive Mode)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "fc-view-container"))
        )
        time.sleep(2) 
        
        try:
            close_buttons = driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'close') or @data-dismiss='modal' or contains(@class, 'close')]")
            for btn in close_buttons:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.5)
        except Exception:
            pass

        try:
            driver.execute_script("""
                var overlays = document.querySelectorAll('.modal-backdrop, .modal, .bootbox');
                overlays.forEach(e => e.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = 'auto';
            """)
        except Exception:
            pass
        
        actions = ActionChains(driver)
        for _ in range(3):
            actions.send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
            
        time.sleep(3)

        # 5. Extract Timetable HTML (Supporting both Grid and List views)
        events = []
        days_checked = 0
        
        while days_checked < 7:
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, "lxml")
            
            calendar_elements = soup.find_all(lambda tag: tag.has_attr('class') and any(c in tag['class'] for c in ['fc-time-grid-event', 'fc-event', 'fc-list-item']))
            
            for event in calendar_elements:
                time_el = event.find(class_="fc-time") or event.find(class_="fc-list-item-time")
                title_el = event.find(class_="fc-title") or event.find(class_="fc-list-item-title")
                
                time_text = time_el.get_text(strip=True) if time_el else ""
                title_text = title_el.get_text(separator=" | ", strip=True) if title_el else ""
                
                if time_text or title_text:
                    events.append({
                        "time": time_text or "No Time", 
                        "title": title_text or "No Title"
                    })

            if events:
                break
                
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "button.fc-next-button")
                driver.execute_script("arguments[0].click();", next_btn)
                days_checked += 1
                time.sleep(3) 
            except Exception:
                break

        if not events:
            return {"message": f"Logged in and checked {days_checked + 1} day(s), but no classes were found.", "data": []}

        return {"message": f"Scraping successful (fast-forwarded {days_checked} day(s) to find classes)", "data": events}

    except Exception as e:
        # This will now capture the exact error and send it to the frontend
        error_msg = f"{type(e).__name__}: {str(e)}"
        print("====== SCRAPER CRASHED ======")
        if driver:
            print("CURRENT URL:", driver.current_url)
            print("PAGE SOURCE EXCERPT:")
            # Print the first 2000 characters of the HTML to see the Cloudflare block
            print(driver.page_source[:2000]) 
        
        import traceback
        print(traceback.format_exc()) 
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        if driver:
            driver.quit()