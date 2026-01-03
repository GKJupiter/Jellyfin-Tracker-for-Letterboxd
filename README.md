#     Jellyfin Tracker for Letterboxd 🎬

Automatically sync your Jellyfin movie watch status to Letterboxd using Python and Playwright.

## 📋 How it Works
This script acts as a "middleware." When you watch a movie on Jellyfin and reach your defined progress threshold (e.g. 85%), Jellyfin sends a webhook to this script. The script then:
1. Launches a background (headless) browser.
2. Logs into your Letterboxd account.
3. Searches for the movie (using Title + Production Year for accuracy).
4. Marks the movie as "Watched."

## 🚀 Installation & Setup

### 1. Install Dependencies
Open your terminal in the project folder and run:
```bash
pip install -r requirements.txt
playwright install chromium
```

## ⚙️ Configuration
Before running `main.py`, you must edit `configuration.json` file to include your credentials:

1. Open `configuration.json` file.
2. Update the following values:
   * **`watch_threshold`**: The percentage of the movie you must watch to trigger the log (Default is `85`).
   * **`JellyfinUser1`**: Your Jellyfin profile name.
   * **`your_letterboxd_username`**: Your Letterboxd username.
   * **`your_letterboxd_password`**: Your Letterboxd password.
4. Save


### 2. Configure Jellyfin

  Go to your Jellyfin Dashboard -> Webhooks (Webhooks is an extension you need to download).

  Click Add Generic Destination.

  Webhook Name: Letterboxd Tracker (or anything you want it doesn't matter)

  Webhook URL: `http://localhost:5000/webhook` (If you are using this app on another device change `localhost` to that device's IPv4 address)

  Notification Type: Check "Playback Progress".

  Item Type: Check `Movies`.

  Check `Send All Properties (ignores templates)`.

  Save.


    
### 3. Run the Tracker
In your terminal, run the following command to start the server:
```bash
python main.py
```
