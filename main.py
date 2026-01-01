import uvicorn
import urllib.parse
import asyncio
from fastapi import FastAPI, Request
from playwright.async_api import async_playwright

app = FastAPI()

# ==========================================
# CONFIGURATION
# ==========================================
WATCH_THRESHOLD = 85
LETTERBOXD_USER = "YOUR_USERID"
LETTERBOXD_PASS = "YOUR_PASSWORD"
# ==========================================

handled_movies = set()

async def mark_on_letterboxd(movie_name, movie_year):
    print(f"🎬 [Browser] Starting task for: {movie_name} ({movie_year})")
    
    async with async_playwright() as p:
        # headless=False so you can see it working
        browser = await p.chromium.launch(headless=True, slow_mo=100)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        try:
            # --- 1. LOGIN ---
            print("⏳ Login Phase...")
            await page.goto("https://letterboxd.com/sign-in/", wait_until="domcontentloaded")
            
            # Dismiss Cookie Banner
            try:
                await page.wait_for_selector(".cc-btn", timeout=2000)
                await page.click(".cc-btn")
            except:
                pass

            # Login
            await page.wait_for_selector("input[name='username']")
            await page.fill("input[name='username']", LETTERBOXD_USER)
            await page.fill("input[name='password']", LETTERBOXD_PASS)
            await page.keyboard.press("Enter")
            
            # Wait for redirect
            await page.wait_for_url("https://letterboxd.com/", wait_until="domcontentloaded", timeout=15000)
            print("✅ Login Successful!")

            # --- 2. SEARCH (The Fix: Patience) ---
            # Construct search query
            if movie_year:
                search_query = f"{movie_name} {movie_year}"
            else:
                search_query = movie_name
                
            print(f"🔍 Searching for '{search_query}'...")
            encoded_name = urllib.parse.quote(search_query)
            await page.goto(f"https://letterboxd.com/search/{encoded_name}/", wait_until="domcontentloaded")
            
            # --- CRITICAL FIX: Wait for results to actually load ---
            print("⏳ Waiting for posters to appear...")
            try:
                # Wait up to 5 seconds for a poster to appear
                await page.wait_for_selector(".results li .film-poster", timeout=5000)
            except:
                print("⚠️ Search loading timed out. Checking if results exist anyway...")

            # Now we check
            results = page.locator(".results li .film-poster")
            if await results.count() == 0:
                print("❌ ERROR: No results found! (Check spelling or Letterboxd URL)")
                # Keep browser open for 10s so you can see what happened
                await asyncio.sleep(10)
                return

            # Click the first poster
            await results.first.click()
            
            # --- 3. MARK WATCHED ---
            print("👀 Page loaded. Looking for 'Watch' button...")
            
            # Wait for sidebar
            await page.wait_for_selector(".sidebar", state="visible", timeout=10000)
            
            # Try finding the "Eye" icon container
            watch_btn = page.locator(".action-watched")
            
            if await watch_btn.count() > 0:
                class_text = await watch_btn.get_attribute("class")
                if " -on" in class_text:
                    print("✅ Movie was ALREADY marked watched.")
                else:
                    await watch_btn.click()
                    print("✅ SUCCESS: Clicked the Eye icon!")
                    await asyncio.sleep(2) # Wait for save
            else:
                print("❌ ERROR: Could not find the 'Eye' icon.")
                # Strategy 2: Look for text "Watch"
                try:
                    text_btn = page.locator(".sidebar").get_by_text("Watch", exact=True)
                    await text_btn.click()
                    print("✅ SUCCESS: Clicked via Text Search!")
                except:
                    print("❌ Text search failed too.")

        except Exception as e:
            print(f"❌ CRITICAL ERROR: {e}")
            await page.screenshot(path="error_crash.png")
            
        finally:
            await browser.close()

@app.post("/webhook")
async def receive_jellyfin_data(request: Request):
    try:
        data = await request.json()
        item_name = data.get("Name")
        production_year = data.get("ProductionYear")
        user_name = data.get("NotificationUsername")
        current_ticks = data.get("PlaybackPositionTicks", 0)
        total_ticks = data.get("RunTimeTicks", 1) 
        
        session_id = f"{user_name}_{item_name}"

        if total_ticks > 0:
            percent = (current_ticks / total_ticks) * 100
        else:
            percent = 0.0

        if percent >= WATCH_THRESHOLD:
            if session_id not in handled_movies:
                print(f"🚀 TARGET REACHED: {item_name} ({percent:.1f}%)")
                await mark_on_letterboxd(item_name, production_year)
                handled_movies.add(session_id)
        
        elif percent < 5:
            if session_id in handled_movies:
                handled_movies.remove(session_id)

        return {"status": "ok"}
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error"}

if __name__ == "__main__":
    print(f"Tracker Active. Waiting for {WATCH_THRESHOLD}%...")
    uvicorn.run(app, host="0.0.0.0", port=5000)
