#     Jellyfin Tracker for Letterboxd 🎬

Automatically sync your Jellyfin movie watch status to Letterboxd using Python and Playwright.

## 📋 How it Works
This script acts as a "middleware." When you watch a movie on Jellyfin and reach your defined progress threshold (e.g. 85%), Jellyfin sends a webhook to this script. The script then:
1. Launches a background (headless) browser.
2. Logs into your Letterboxd account.
3. Searches for the movie (using Title + Production Year for accuracy).
4. Marks the movie as "Watched."

## ⚙️ Configuration
Before running, you must edit the `main.py` file to include your credentials:

1. Open `main.py`.
2. Locate the `CONFIGURATION` block (Lines 11-16).
3. Update the following values:
   * **`WATCH_THRESHOLD`**: The percentage of the movie you must watch to trigger the log (Default is `85`).
   * **`LETTERBOXD_USER`**: Your Letterboxd username.
   * **`LETTERBOXD_PASS`**: Your Letterboxd password.

## 🚀 Installation & Setup

### 1. Install Dependencies
Open your terminal in the project folder and run:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Run the Tracker
In your terminal, run the following command to start the server:
```bash
python main.py
```

3. Configure Jellyfin

    Go to your Jellyfin Dashboard -> Webhooks (Webhooks is an extension you need to download).

    Click Add Generic Destination.

    Webhook Name: Tracker

    Webhook URL: http://localhost:5000/webhook

    Notification Type: Check "Playback Progress".

    Item Type: Check "Movies".

    Send All Properties: Check this box.

    Save.
