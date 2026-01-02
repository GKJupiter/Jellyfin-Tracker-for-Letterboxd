import uvicorn
import urllib.parse
import asyncio
import os
from fastapi import FastAPI, Request
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

app = FastAPI()

# --- CONFIGURATION FROM .ENV ---
WATCH_THRESHOLD = int(os.getenv("WATCH_THRESHOLD", 85))
LETTERBOXD_USER = os.getenv("LB_USER")
LETTERBOXD_PASS = os.getenv("LB_PASS")

# Global lock to prevent multiple browsers running at once
browser_lock = asyncio.Lock()
handled_movies = set()

async def mark_on_letterboxd(movie_name, movie_year):
    async with browser_lock:  # Only one browser task can run at a time
        print(f"🎬 [Browser] Starting task for: {movie_name} ({movie_year})")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, slow_mo=100)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            try:
                # 1. LOGIN
                print("⏳ Login Phase...")
                await page.goto("https://letterboxd.com/sign-in/", wait_until="domcontentloaded")
                
                try:
                    await page.wait_for_selector(".cc-btn", timeout=2000)
                    await page.click(".cc-btn")
                except:
                    pass

                await page.wait_for_selector("input[name='username']")
                await page.fill("input[name='username']", LETTERBOXD_USER)
                await page.fill("input[name='password']", LETTERBOXD_PASS)
                await page.keyboard.press("Enter")
                
                await page.wait_for_url("https://letterboxd.com/", wait_until="domcontentloaded", timeout=15000)
                print("✅ Login Successful!")

                # 2. SEARCH
                search_query = f"{movie_name} {movie_year}" if movie_year else movie_name
                print(f"🔍 Searching for '{search_query}'...")
                encoded_name = urllib.parse.quote(search_query)
                await page.goto(f"https://letterboxd.com/search/{encoded_name}/", wait_until="domcontentloaded")
                
                try:
                    await page.wait_for_selector(".results li .film-poster", timeout=5000)
                except:
                    pass

                results = page.locator(".results li .film-poster")
                if await results.count() == 0:
                    print(f"❌ ERROR: No results for {movie_name}")
                    return

                await results.first.click()
                
                # 3. MARK WATCHED
                print("👀 Looking for 'Watch' button...")
                await page.wait_for_selector(".sidebar", state="visible", timeout=10000)
                
                watch_btn = page.locator(".action-watched")
                if await watch_btn.count() > 0:
                    class_text = await watch_btn.get_attribute("class")
                    if " -on" in class_text:
                        print("✅ ALREADY watched.")
                    else:
                        await watch_btn.click()
                        print("✅ SUCCESS: Marked via Icon!")
                        await asyncio.sleep(2)
                else:
                    try:
                        await page.locator(".sidebar").get_by_text("Watch", exact=True).click()
                        print("✅ SUCCESS: Marked via Text!")
                    except:
                        print("❌ Failed to find button.")

            except Exception as e:
                print(f"❌ ERROR: {e}")
            finally:
                await browser.close()

@app.post("/webhook")
async def receive_jellyfin_data(request: Request):
    try:
        data = await request.json()
        item_name = data.get("Name")
        production_year = data.get("Year")
        user_name = data.get("NotificationUsername")
        current_ticks = data.get("PlaybackPositionTicks", 0)
        total_ticks = data.get("RunTimeTicks", 1) 
        
        session_id = f"{user_name}_{item_name}"
        percent = (current_ticks / total_ticks) * 100 if total_ticks > 0 else 0

        if percent >= WATCH_THRESHOLD:
            if session_id not in handled_movies:
                print(f"🚀 TARGET REACHED: {item_name} ({percent:.1f}%)")
                handled_movies.add(session_id)
                # Run the browser task in the background
                asyncio.create_task(mark_on_letterboxd(item_name, production_year))
        
        elif percent < 5:
            if session_id in handled_movies:
                handled_movies.remove(session_id)

        return {"status": "ok"}
    except Exception as e:
        return {"status": "error"}

if __name__ == "__main__":
    print(f"Tracker Active. Threshold: {WATCH_THRESHOLD}%")
    uvicorn.run(app, host="0.0.0.0", port=5000)
