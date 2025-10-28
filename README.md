# 🚀 **BetaSlot-Sniper**

Automatically join **Google Play beta programs** the moment a slot opens — no more endless manual refreshing!

---

## 🧠 Overview

**BetaSlot-Sniper** monitors selected apps on the Google Play Store and automatically joins their beta programs when spots become available.

It uses your **real browser profile** (so you stay logged in) and handles driver downloads automatically.

---

## ⚙️ Quick Start

### 1. Install dependencies

```bash
pip install selenium psutil requests
```

### 2. Run the script

```bash
python BetaSlot-Sniper.py
```

### 3. Follow the prompts

* Select apps to monitor (numbers or **99** for all)
* Choose browser (**auto-detect** or **manual**)
* Let it run — the script will handle everything automatically!

---

## ⚠️ Important Notes

* You **must be logged into** your Google account in the selected browser for it to work
* **Automatic WebDriver download** is included
* If it fails, you’ll be prompted with **manual setup instructions**

---

## 🧩 Advanced Usage

```bash
# Monitor specific packages
python BetaSlot-Sniper.py --packages "com.instagram.android,com.spotify.music"

# Use a specific browser & channel
python BetaSlot-Sniper.py --browser chrome --channel stable

# Exit after first success
python BetaSlot-Sniper.py --once

# View all available options
python BetaSlot-Sniper.py --help
```

---

## 🌐 Supported Browsers

| Browser       | Channels                   |
| ------------- | -------------------------- |
| **Chrome**    | Stable, Beta, Dev          |
| **Edge**      | Stable, Beta, Dev, Canary  |
| **Brave**     | Stable, Beta, Nightly      |
| **Firefox**   | Stable, Developer, Nightly |
| **Opera**     | Stable, GX                 |
| **LibreWolf** | Stable                     |

---

## 🔍 How It Works

* Checks **Google Play beta pages every 30 seconds**
* Automatically joins when slots open
* Uses your **existing browser profile**
* **Downloads WebDrivers automatically**
* Fully compatible with **Windows, macOS, and Linux**

---

## 📱 Predefined Apps

* Google App
* Android Auto
* Google Messages
* YouTube
* Google Maps
* Google Home
* Instagram
* Snapchat
* Spotify
* TikTok
* *(+ Custom package support!)*

---

## 💡 Pro Tips

* Use the `--once` flag to join **only one beta** and exit afterward
* Keep it running to **monitor multiple apps continuously**
* Pair it with a **headless browser** for silent background operation

---

## 🧾 Version History

**v0.1** — Initial Release 🎉

---

## 🛠️ Use Responsibly

This tool is for personal use only.
Please respect Google Play’s terms of service — and enjoy your beta access! 😎