import uvicorn
import urllib.parse
import asyncio
import json
import os
import sys
from fastapi import FastAPI, Request
from playwright.async_api import async_playwright

app = FastAPI()

# ==========================================
# CONFIGURATION
# ==========================================
WATCH_THRESHOLD = 85  # Change this number here to adjust sensitivity
# ==========================================

# Global lock: Only one browser session at a time
browser_lock = asyncio.Lock()
handled_movies = set()

def load_user_map():
    # Get the folder where main.py is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "users.json")
    
    print(f"📂 Debug: Looking for config at: {file_path}")

    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: users.json NOT found at {file_path}")
        print("👉 Make sure the file is in that specific folder!")
        return {}
    except json.JSONDecodeError:
        print(f"❌ ERROR: users.json is found but has bad grammar (syntax error).")
        return {}

async def mark_on_letterboxd(movie_name, movie_year, lb_user, lb_pass):
    async with browser_lock:
        print(f"🎬 [Browser] Logging in as {lb_user} for: {movie_name}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, slow_mo=100)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            try:
                # 1. LOGIN
                await page.goto("https://letterboxd.com/sign-in/", wait_until="domcontentloaded")
                
                try:
                    await page.wait_for_selector(".cc-btn", timeout=2000)
                    await page.click(".cc-btn")
                except:
                    pass

                await page.wait_for_selector("input[name='username']")
                await page.fill("input[name='username']", lb_user)
                await page.fill("input[name='password']", lb_pass)
                await page.keyboard.press("Enter")
                
                await page.wait_for_url("https://letterboxd.com/", wait_until="domcontentloaded", timeout=15000)
                print(f"✅ Login Successful for {lb_user}!")

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
                    print(f"❌ ERROR: No results for '{movie_name}'")
                    return

                await results.first.click()
                
                # 3. MARK WATCHED
                await page.wait_for_selector(".sidebar", state="visible", timeout=10000)
                watch_btn = page.locator(".action-watched")
                
                if await watch_btn.count() > 0:
                    class_text = await watch_btn.get_attribute("class")
                    if " -on" in class_text:
                        print("✅ ALREADY watched.")
                    else:
                        await watch_btn.click()
                        print("✅ SUCCESS: Marked Watched!")
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
        production_year = data.get("ProductionYear")
        jellyfin_user = data.get("NotificationUsername")
        current_ticks = data.get("PlaybackPositionTicks", 0)
        total_ticks = data.get("RunTimeTicks", 1) 
        
        session_id = f"{jellyfin_user}_{item_name}"
        percent = (current_ticks / total_ticks) * 100 if total_ticks > 0 else 0

        if percent >= WATCH_THRESHOLD:
            if session_id not in handled_movies:
                user_map = load_user_map()
                
                if jellyfin_user in user_map:
                    print(f"🚀 TARGET REACHED: {item_name} (User: {jellyfin_user})")
                    creds = user_map[jellyfin_user]
                    handled_movies.add(session_id)
                    asyncio.create_task(mark_on_letterboxd(
                        item_name, 
                        production_year, 
                        creds["lb_user"], 
                        creds["lb_pass"]
                    ))
                else:
                    if session_id not in handled_movies:
                         print(f"⚠️ Unmapped user: {jellyfin_user}")
                         handled_movies.add(session_id)
        
        elif percent < 5:
            if session_id in handled_movies:
                handled_movies.remove(session_id)

        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}

if __name__ == "__main__":
    print(f"Tracker Active. Multi-User Mode. Threshold: {WATCH_THRESHOLD}%")
    uvicorn.run(app, host="0.0.0.0", port=5000)
