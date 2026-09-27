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
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    
    driver = None
    try:
        driver = uc.Chrome(options=options)
        driver.get("https://s.amizone.net/")
        
        # 1. Bypass Turnstile and Login
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "cf-turnstile-response"))
        )
        time.sleep(3) # Wait for token generation
        
        driver.find_element(By.ID, "loginform-username").send_keys(creds.username)
        driver.find_element(By.ID, "loginform-password").send_keys(creds.password)
        driver.find_element(By.ID, "loginbtn").click()

        # 2. Handle Dashboard Popups
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "fc-view-container"))
        )
        
        actions = ActionChains(driver)
        actions.send_keys(Keys.ESCAPE).perform()
        time.sleep(1)
        actions.move_by_offset(10, 10).click().perform()
        time.sleep(2) # Allow calendar to populate

        # 3. Extract Timetable HTML
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, "lxml")
        
        events = []
        calendar_elements = soup.find_all("a", class_="fc-time-grid-event")
        
        for event in calendar_elements:
            time_text = event.find("div", class_="fc-time").get_text(strip=True) if event.find("div", class_="fc-time") else "No Time"
            title_text = event.find("div", class_="fc-title").get_text(strip=True) if event.find("div", class_="fc-title") else "No Title"
            events.append({"time": time_text, "title": title_text})

        if not events:
            return {"message": "Logged in, but no classes found in the calendar view.", "data": []}

        return {"message": "Scraping successful", "data": events}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if driver:
            driver.quit()