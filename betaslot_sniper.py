# watch_play_beta_any_browser_auto.py
# Auto-detect default Windows browser, auto-download matching webdriver, reuse profile,
# monitor Google Play beta opt-in URLs and try to join when slot opens.

from datetime import datetime
import os, sys, time, subprocess, urllib.request, urllib.error, zipfile, shutil, json, webbrowser, re
import winreg
import http.cookiejar
from urllib.parse import urlencode

# ---- USER CONFIG ----
PACKAGES = [
    "com.google.android.googlequicksearchbox",
]

CHECK_INTERVAL = 30  # seconds between full loops
PER_PACKAGE_DELAY = 2
DOM_WAIT = 20  # Increased wait time for page loading
PAGE_LOAD_TIMEOUT = 40

# If you want to force a particular browser, set to "edge" / "chrome" / "firefox"
FORCE_BROWSER = None

# Where drivers will be downloaded & extracted
DRIVER_BASE_DIR = os.path.join(os.path.expanduser("~"), ".selenium_drivers")
os.makedirs(DRIVER_BASE_DIR, exist_ok=True)

# ---- Helpers ----
def log(*args, **kwargs):
    print(f"[{datetime.now()}]", *args, **kwargs)

def testing_url(pkg):
    return f"https://play.google.com/apps/testing/{pkg}"

# Determine default browser from registry
def detect_default_browser():
    try:
        key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        prog_id, _ = winreg.QueryValueEx(key, "ProgId")
        winreg.CloseKey(key)
        pid = prog_id.lower()
        if "edge" in pid:
            return "edge"
        if "chrome" in pid:
            return "chrome"
        if "firefox" in pid:
            return "firefox"
    except Exception:
        pass
    return None

# Get Edge installation path from registry
def get_edge_path_from_registry():
    try:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            path, _ = winreg.QueryValueEx(key, None)
            return path
    except Exception:
        pass
    return None

# Try common browser executable locations
def find_browser_binary(browser):
    user = os.path.expanduser("~")
    candidates = []
    if browser == "edge":
        # Try registry first
        reg_path = get_edge_path_from_registry()
        if reg_path and os.path.exists(reg_path):
            return reg_path
            
        candidates = [
            os.path.join(os.getenv("ProgramFiles", r"C:\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(os.getenv("ProgramFiles", r"C:\Program Files"), "Microsoft", "Edge Dev", "Application", "msedge.exe"),
            os.path.join(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Microsoft", "Edge Dev", "Application", "msedge.exe"),
            os.path.join(os.getenv("ProgramFiles", r"C:\Program Files"), "Microsoft", "Edge Beta", "Application", "msedge.exe"),
            os.path.join(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Microsoft", "Edge Beta", "Application", "msedge.exe"),
        ]
    elif browser == "chrome":
        candidates = [
            os.path.join(os.getenv("ProgramFiles", r"C:\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(user, "AppData", "Local", "Google", "Chrome SxS", "Application", "chrome.exe"),  # Canary
            os.path.join(user, "AppData", "Local", "Google", "Chrome", "Application", "chrome.exe"),
        ]
    elif browser == "firefox":
        candidates = [
            os.path.join(os.getenv("ProgramFiles", r"C:\Program Files"), "Mozilla Firefox", "firefox.exe"),
            os.path.join(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Mozilla Firefox", "firefox.exe"),
            os.path.join(user, "AppData", "Local", "Mozilla Firefox", "firefox.exe"),
        ]
    # return first existing
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

def get_browser_version(exe_path):
    if not exe_path or not os.path.exists(exe_path):
        return None
        
    try:
        # Try different version query methods
        methods = [
            # Method 1: --version flag
            lambda: subprocess.check_output([exe_path, "--version"], 
                                          stderr=subprocess.STDOUT, 
                                          timeout=5,
                                          creationflags=subprocess.CREATE_NO_WINDOW),
            # Method 2: --product-version flag  
            lambda: subprocess.check_output([exe_path, "--product-version"],
                                          stderr=subprocess.STDOUT,
                                          timeout=5,
                                          creationflags=subprocess.CREATE_NO_WINDOW),
            # Method 3: WMIC (for Windows)
            lambda: subprocess.check_output(['wmic', 'datafile', 'where', f'name="{exe_path}"', 'get', 'Version', '/value'],
                                          stderr=subprocess.STDOUT,
                                          timeout=5,
                                          creationflags=subprocess.CREATE_NO_WINDOW),
            # Method 4: PowerShell (for Windows)
            lambda: subprocess.check_output([
                'powershell', 
                '-command', 
                f'(Get-ItemProperty "{exe_path}").VersionInfo.ProductVersion'
            ], stderr=subprocess.STDOUT, timeout=5),
        ]
        
        for method in methods:
            try:
                out = method()
                s = out.decode(errors="ignore").strip()
                
                # Extract version using regex
                version_match = re.search(r'(\d+\.\d+\.\d+\.\d+|\d+\.\d+\.\d+|\d+\.\d+)', s)
                if version_match:
                    return version_match.group(1)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
                
    except Exception as e:
        log("Could not query browser version:", e)
    
    return None

# download utility
def download_file(url, dest_path, show_log=True):
    try:
        if show_log:
            log("Downloading", url)
        with urllib.request.urlopen(url, timeout=30) as r:
            total = r.getheader("Content-Length")
            total = int(total) if total and total.isdigit() else None
            chunk = 8192
            with open(dest_path, "wb") as f:
                downloaded = 0
                while True:
                    data = r.read(chunk)
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
        if show_log:
            log("Saved to", dest_path)
        return True
    except Exception as e:
        log("Download failed:", e)
        return False

# extract zip
def extract_zip(zip_path, dest_dir):
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest_dir)
        return True
    except Exception as e:
        log("Unzip failed:", e)
        return False

# ---- driver downloaders ----
def ensure_edge_driver(browser_exe, browser_version):
    # If browser_version is None, try to get the latest stable version
    if not browser_version:
        try:
            latest_url = "https://msedgedriver.azureedge.net/LATEST_STABLE"
            with urllib.request.urlopen(latest_url, timeout=10) as r:
                browser_version = r.read().decode().strip()
        except Exception as e:
            log("Failed to get latest stable Edge version:", e)
            return None

    # Try exact version first
    zip_url = f"https://msedgedriver.azureedge.net/{browser_version}/edgedriver_win64.zip"
    dest_zip = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{browser_version}.zip")
    out_dir = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{browser_version}")
    
    if os.path.exists(out_dir):
        candidate = os.path.join(out_dir, "msedgedriver.exe")
        if os.path.exists(candidate):
            return candidate
            
    # Try downloading the exact version
    if download_file(zip_url, dest_zip, show_log=False):
        if extract_zip(dest_zip, out_dir):
            for root, dirs, files in os.walk(out_dir):
                if "msedgedriver.exe" in files:
                    return os.path.join(root, "msedgedriver.exe")
    
    # If exact version not found, try major version
    major = browser_version.split(".")[0] if browser_version else None
    if major:
        try:
            latest_url = f"https://msedgedriver.azureedge.net/LATEST_RELEASE_{major}"
            with urllib.request.urlopen(latest_url, timeout=10) as r:
                latest_ver = r.read().decode().strip()
            
            zip_url = f"https://msedgedriver.azureedge.net/{latest_ver}/edgedriver_win64.zip"
            dest_zip = os.path.join(DRIVER_BASE_DIR, f"msedgeddriver_{latest_ver}.zip")
            out_dir = os.path.join(DRIVER_BASE_DIR, f"msedgeddriver_{latest_ver}")
            
            if os.path.exists(out_dir):
                candidate = os.path.join(out_dir, "msedgedriver.exe")
                if os.path.exists(candidate):
                    return candidate
                    
            if download_file(zip_url, dest_zip):
                if extract_zip(dest_zip, out_dir):
                    for root, dirs, files in os.walk(out_dir):
                        if "msedgedriver.exe" in files:
                            return os.path.join(root, "msedgedriver.exe")
        except Exception as e:
            log("Failed to get Edge driver for major version:", e)
    
    return None

def ensure_chrome_driver(browser_version):
    if not browser_version:
        return None
        
    major = browser_version.split(".")[0] if browser_version else None
    if not major:
        return None
        
    # get LATEST_RELEASE_{major}
    try:
        url_version = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major}"
        with urllib.request.urlopen(url_version, timeout=10) as r:
            dr_version = r.read().decode().strip()
    except Exception as e:
        log("Could not fetch chromedriver latest for major:", e)
        return None
        
    zip_url = f"https://chromedriver.storage.googleapis.com/{dr_version}/chromedriver_win32.zip"
    dest_zip = os.path.join(DRIVER_BASE_DIR, f"chromedriver_{dr_version}.zip")
    out_dir = os.path.join(DRIVER_BASE_DIR, f"chromedriver_{dr_version}")
    
    if os.path.exists(out_dir):
        candidate = os.path.join(out_dir, "chromedriver.exe")
        if os.path.exists(candidate):
            return candidate
            
    if download_file(zip_url, dest_zip):
        if extract_zip(dest_zip, out_dir):
            for root, dirs, files in os.walk(out_dir):
                if "chromedriver.exe" in files:
                    return os.path.join(root, "chromedriver.exe")
                    
    return None

def ensure_gecko_driver():
    # Query GitHub API for latest geckodriver release and pick win64 zip asset
    try:
        api = "https://api.github.com/repos/mozilla/geckodriver/releases/latest"
        with urllib.request.urlopen(api, timeout=10) as r:
            data = json.load(r)
        assets = data.get("assets", [])
        win_asset = None
        for a in assets:
            name = a.get("name","").lower()
            if name.endswith("win64.zip"):
                win_asset = a.get("browser_download_url")
                break
        if not win_asset:
            return None
        tag = data.get("tag_name","latest").lstrip("v")
        dest_zip = os.path.join(DRIVER_BASE_DIR, f"geckodriver_{tag}.zip")
        out_dir = os.path.join(DRIVER_BASE_DIR, f"geckodriver_{tag}")
        
        if os.path.exists(out_dir):
            candidate = os.path.join(out_dir, "geckodriver.exe")
            if os.path.exists(candidate):
                return candidate
                
        if download_file(win_asset, dest_zip):
            if extract_zip(dest_zip, out_dir):
                for root, dirs, files in os.walk(out_dir):
                    if "geckodriver.exe" in files:
                        return os.path.join(root, "geckodriver.exe")
    except Exception as e:
        log("Failed to fetch geckodriver:", e)
        
    return None

# Try to prepare driver for the given browser
def prepare_driver_for(browser):
    log("Preparing driver for", browser)
    bin_path = find_browser_binary(browser)
    
    if not bin_path:
        log("Could not find browser binary for", browser)
        return None
        
    log("Found browser binary:", bin_path)
    version = get_browser_version(bin_path)
    log("Browser version:", version)
    
    # First, check if driver already exists in the driver directory
    driver_files = []
    if browser == "edge":
        driver_pattern = os.path.join(DRIVER_BASE_DIR, "msedgedriver*.exe")
        driver_files = [f for f in [os.path.join(DRIVER_BASE_DIR, "msedgedriver.exe")] if os.path.exists(f)]
        driver_files.extend([f for f in [os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{version}.exe")] if os.path.exists(f)])
        
    elif browser == "chrome":
        driver_pattern = os.path.join(DRIVER_BASE_DIR, "chromedriver*.exe")
        driver_files = [f for f in [os.path.join(DRIVER_BASE_DIR, "chromedriver.exe")] if os.path.exists(f)]
        driver_files.extend([f for f in [os.path.join(DRIVER_BASE_DIR, f"chromedriver_{version}.exe")] if os.path.exists(f)])
        
    elif browser == "firefox":
        driver_pattern = os.path.join(DRIVER_BASE_DIR, "geckodriver*.exe")
        driver_files = [f for f in [os.path.join(DRIVER_BASE_DIR, "geckodriver.exe")] if os.path.exists(f)]
    
    # Check for any driver file in the directory
    for root, dirs, files in os.walk(DRIVER_BASE_DIR):
        for file in files:
            if browser == "edge" and "msedgedriver" in file.lower() and file.endswith(".exe"):
                driver_files.append(os.path.join(root, file))
            elif browser == "chrome" and "chromedriver" in file.lower() and file.endswith(".exe"):
                driver_files.append(os.path.join(root, file))
            elif browser == "firefox" and "geckodriver" in file.lower() and file.endswith(".exe"):
                driver_files.append(os.path.join(root, file))
    
    # Use the first found driver
    if driver_files:
        driver_path = driver_files[0]
        log("Found existing driver:", driver_path)
        return {"driver_path": driver_path, "binary": bin_path}
    
    # If no existing driver found, try to download
    if browser == "edge":
        driver = ensure_edge_driver(bin_path, version)
        if driver:
            log("Got msedgedriver:", driver)
            return {"driver_path": driver, "binary": bin_path}
        else:
            log("Could not download Edge driver automatically")
            log("Please download it manually from: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
            log("Place it in:", DRIVER_BASE_DIR)
            return None
    elif browser == "chrome":
        driver = ensure_chrome_driver(version)
        if driver:
            log("Got chromedriver:", driver)
            return {"driver_path": driver, "binary": bin_path}
        else:
            log("Could not download Chrome driver automatically")
            log("Please download it manually from: https://chromedriver.chromium.org/")
            log("Place it in:", DRIVER_BASE_DIR)
            return None
    elif browser == "firefox":
        driver = ensure_gecko_driver()
        if driver:
            log("Got geckodriver:", driver)
            return {"driver_path": driver, "binary": bin_path}
        else:
            log("Could not download Firefox driver automatically")
            log("Please download it manually from: https://github.com/mozilla/geckodriver/releases")
            log("Place it in:", DRIVER_BASE_DIR)
            return None
            
    log("Could not prepare driver for", browser)
    return None

# Selenium driver creation with explicit driver path + profile reuse
def create_selenium_driver(browser, prepared):
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
    except Exception as e:
        log("Selenium not installed or import failed:", e)
        return None

    try:
        driver_path = prepared.get("driver_path")
        binary = prepared.get("binary")

        if browser == "edge":
            from selenium.webdriver.edge.service import Service as EdgeService
            from selenium.webdriver.edge.options import Options as EdgeOptions
            opts = EdgeOptions()
            if binary:
                opts.binary_location = binary
            # attempt to reuse profile folder automatically (detect common locations)
            profile_parent, profile_dir = choose_chromium_profile(browser)
            if profile_parent:
                opts.add_argument(f"--user-data-dir={profile_parent}")
                if profile_dir:
                    opts.add_argument(f"--profile-directory={profile_dir}")
            service = EdgeService(executable_path=driver_path)
            driver = webdriver.Edge(service=service, options=opts)
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            return driver

        if browser == "chrome":
            from selenium.webdriver.chrome.service import Service as ChromeService
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            opts = ChromeOptions()
            if binary:
                opts.binary_location = binary
            profile_parent, profile_dir = choose_chromium_profile(browser)
            if profile_parent:
                opts.add_argument(f"--user-data-dir={profile_parent}")
                if profile_dir:
                    opts.add_argument(f"--profile-directory={profile_dir}")
            service = ChromeService(executable_path=driver_path)
            driver = webdriver.Chrome(service=service, options=opts)
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            return driver

        if browser == "firefox":
            from selenium.webdriver.firefox.service import Service as FirefoxService
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
            opts = FirefoxOptions()
            fx_profile = find_firefox_profile()
            fp = FirefoxProfile(fx_profile) if fx_profile else None
            service = FirefoxService(executable_path=driver_path)
            driver = webdriver.Firefox(service=service, firefox_profile=fp, options=opts)
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            return driver

    except Exception as e:
        log("Failed to create Selenium driver:", e)
        return None

# helper to pick chromium user-data folder and profile directory
def choose_chromium_profile(browser):
    user = os.path.expanduser("~")
    dirs = {
        "chrome": os.path.join(user, "AppData", "Local", "Google", "Chrome", "User Data"),
        "chrome_canary": os.path.join(user, "AppData", "Local", "Google", "Chrome SxS", "User Data"),
        "edge": os.path.join(user, "AppData", "Local", "Microsoft", "Edge", "User Data"),
        "edge_dev": os.path.join(user, "AppData", "Local", "Microsoft", "Edge Dev", "User Data"),
        "edge_beta": os.path.join(user, "AppData", "Local", "Microsoft", "Edge Beta", "User Data"),
    }
    if browser == "chrome":
        if os.path.exists(dirs["chrome"]):
            return dirs["chrome"], "Default"
        if os.path.exists(dirs["chrome_canary"]):
            return dirs["chrome_canary"], "Default"
    if browser == "edge":
        if os.path.exists(dirs["edge_dev"]):
            return dirs["edge_dev"], "Default"
        if os.path.exists(dirs["edge_beta"]):
            return dirs["edge_beta"], "Default"
        if os.path.exists(dirs["edge"]):
            return dirs["edge"], "Default"
    return None, None

# Find Firefox profile
def find_firefox_profile():
    user = os.path.expanduser("~")
    ff_profile_path = os.path.join(user, "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
    if os.path.exists(ff_profile_path):
        for profile in os.listdir(ff_profile_path):
            if profile.endswith(".default-release") or profile.endswith(".default"):
                return os.path.join(ff_profile_path, profile)
    return None

# ---- detection & click logic using Selenium ----
def selenium_check_and_click(driver, pkg):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    url = testing_url(pkg)
    log("Loading (selenium)", url)
    try:
        driver.get(url)
    except Exception as e:
        log("driver.get failed:", e)
        return False

    try:
        WebDriverWait(driver, DOM_WAIT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except Exception:
        pass

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.upper()
    except Exception:
        body_text = ""

    # Check for full messages
    full_patterns = [
        "BETA PROGRAM IS CURRENTLY FULL",
        "BETA PROGRAM IS FULL",
        "THE BETA PROGRAM FOR THIS APP IS CURRENTLY FULL",
        "BETA TESTER LIMIT HAS BEEN REACHED",
        "NO MORE TESTERS ARE BEING ACCEPTED",
        "BETA TESTING IS FULL",
        "BETA IS FULL",
        "TESTING IS FULL",
        "CLOSED",
        "NOT ACCEPTING"
    ]
    
    for pattern in full_patterns:
        if pattern in body_text:
            log(f"{pkg}: beta FULL (selenium).")
            return False

    # Try to find and submit the form directly using Selenium only
    try:
        # Look for the form with class 'joinForm'
        forms = driver.find_elements(By.CSS_SELECTOR, "form.joinForm")
        if forms:
            log("Found join form - attempting to submit using Selenium")
            
            # Find the submit button and click it
            submit_buttons = forms[0].find_elements(By.CSS_SELECTOR, "input[type='submit'].action")
            if submit_buttons:
                log("Clicking submit button")
                submit_buttons[0].click()
                time.sleep(5)  # Wait for form submission
                
                # Check for success indicators
                success_indicators = [
                    "YOU'RE A TESTER",
                    "YOU ARE A TESTER",
                    "SUCCESSFULLY JOINED",
                    "THANKS FOR JOINING"
                ]
                
                page_source = driver.page_source.upper()
                for indicator in success_indicators:
                    if indicator in page_source:
                        log("Successfully joined beta program!")
                        return True
                
                log("Form submitted but success not confirmed. Opening browser for manual verification.")
                webbrowser.open(url)
                return True
                
    except Exception as e:
        log("Error submitting form with Selenium:", e)

    # Try multiple click strategies as fallback
    xpath_strategies = [
        # Button with join/beta text
        "//input[@type='submit' and @class='action']",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'join') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'become') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'participate')]",
        
        # Any element with beta join text
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'beta') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'join') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'become'))]",
        
        # Form submit buttons
        "//input[@type='submit' or @type='button']",
        
        # Any clickable element that might be the join button
        "//*[@role='button' or @class*='button' or contains(@class, 'btn')]"
    ]

    for xpath in xpath_strategies:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for element in elements:
                try:
                    if element.is_displayed() and element.is_enabled():
                        log("Found clickable element - attempting to click.")
                        element.click()
                        time.sleep(5)  # Wait longer for form submission
                        log("Clicked successfully! Checking if enrollment was successful.")
                        
                        # Check for success
                        driver.refresh()
                        time.sleep(3)
                        
                        success_indicators = [
                            "YOU'RE A TESTER",
                            "YOU ARE A TESTER",
                            "SUCCESSFULLY JOINED",
                            "THANKS FOR JOINING"
                        ]
                        
                        page_source = driver.page_source.upper()
                        for indicator in success_indicators:
                            if indicator in page_source:
                                log("Successfully joined beta program!")
                                return True
                        
                        log("Clicked but success not confirmed. Opening browser for manual verification.")
                        webbrowser.open(url)
                        return True
                except Exception as e:
                    continue
        except Exception:
            continue

    # If no click worked but we see join text, open browser
    join_patterns = [
        "BECOME A TESTER", "Become a tester", "JOIN THE BETA", "Join the beta", "JOIN BETA", "Join beta", "JOIN TESTING", "Join testing",
        "PARTICIPATE IN BETA", "Participate in beta", "BETA TESTER PROGRAM", "Beta tester program", "ACCEPT INVITATION", "Accept invitation"
    ]
    
    for pattern in join_patterns:
        if pattern in body_text:
            log("Detected opt-in text but couldn't click automatically. Opening for manual finish.")
            webbrowser.open(url)
            return True

    log("No opt-in found (selenium).")
    return False

# ---- fallback http check ----
def fetch_page_text(url, timeout=15):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            b = resp.read()
            text = b.decode("utf-8", errors="replace")
            return text.upper()
    except Exception as e:
        log("HTTP fetch failed:", e)
        return None

def http_check(pkg):
    url = testing_url(pkg)
    log("Loading (http)", url)
    text = fetch_page_text(url)
    if not text:
        log("Couldn't fetch", url)
        return False
    
    # More comprehensive check for "full" messages
    full_patterns = [
        "BETA PROGRAM IS CURRENTLY FULL",
        "BETA PROGRAM IS FULL",
        "THE BETA PROGRAM FOR THIS APP IS CURRENTLY FULL",
        "BETA TESTER LIMIT HAS BEEN REACHED",
        "NO MORE TESTERS ARE BEING ACCEPTED",
        "BETA TESTING IS FULL",
        "BETA IS FULL",
        "TESTING IS FULL",
        "CLOSED",
        "NOT ACCEPTING"
    ]
    
    for pattern in full_patterns:
        if pattern in text:
            log(f"{pkg}: beta FULL (http).")
            return False
    
    # Check for the specific form HTML pattern
    if 'FORM METHOD="POST" ACTION="/APPS/TESTING/' in text and 'CLASS="JOINFORM"' in text:
        log("Found beta join form - opening page.")
        webbrowser.open(url)
        return True
    
    # More comprehensive check for "join" opportunities
    join_patterns = [
        "BECOME A TESTER",
        "Become a tester",
        "JOIN THE BETA",
        "Join the beta",
        "JOIN BETA",
        "Join beta",
        "JOIN TESTING",
        "Join testing",
        "PARTICIPATE IN BETA",
        "Participate in beta",
        "BETA TESTER PROGRAM",
        "Beta tester program",
        "JOIN THE TEST",
        "Join the test",
        "JOIN THE TESTING",
        "Join the testing",
        "JOIN THE PROGRAM",
        "Join the program",
        "ACCEPT INVITATION",
        "Accept invitation",
        "JOIN PROGRAM",
        "Join program",
        "JOIN",
        "Join",
        "JOIN NOW",
        "Join now",
        "SIGN UP",
        "Sign up",
        "BECOME A BETA TESTER",
        "Become a beta tester",
        "PARTICIPATE IN THE BETA",
        "Participate in the beta",
        "I'M IN",
        "I'm in",
        "ACCEPT",
        "Accept",
        "PARTICIPATE",
        "Participate"
    ]
    
    for pattern in join_patterns:
        if pattern in text:
            log("Possible slot for", pkg, "- opening page.")
            webbrowser.open(url)
            return True
    
    # Check for button-like elements that might indicate availability
    button_patterns = [
        "BUTTON", "Button", "SUBMIT", "Submit", "FORM", "Form", "OPT-IN", "Opt-in", "ENROLL", "Enroll", "REGISTER", "Register"
    ]
    
    for pattern in button_patterns:
        if pattern in text:
            log("Found interactive element for", pkg, "- opening page for manual check.")
            webbrowser.open(url)
            return True
    
    log("No opt-in found (http). Text patterns not matched.")
    return False

# ---- Main flow ----
def main():
    browser = FORCE_BROWSER or (sys.argv[1].lower() if len(sys.argv) > 1 else None)
    if not browser:
        browser = detect_default_browser()
    log("Detected/selected browser:", browser)

    prepared = None
    selenium_driver = None

    if browser in ("edge", "chrome", "firefox"):
        prepared = prepare_driver_for(browser)
        if prepared:
            log("Prepared driver:", prepared.get("driver_path"))
            selenium_driver = create_selenium_driver(browser, prepared)
            if selenium_driver:
                log("Selenium driver created successfully.")
            else:
                log("Failed to create Selenium driver - will fallback to HTTP polling.")
        else:
            log("Could not prepare driver automatically - will fallback to HTTP polling.")
    else:
        log("Unsupported or undetected default browser. Using HTTP polling fallback.")

    try:
        while True:
            for pkg in PACKAGES:
                try:
                    if selenium_driver:
                        ok = selenium_check_and_click(selenium_driver, pkg)
                    else:
                        ok = http_check(pkg)
                    if ok:
                        log("Action taken for", pkg, "- exiting.")
                        return
                except Exception as e:
                    log("Error checking", pkg, ":", e)
                time.sleep(PER_PACKAGE_DELAY)
            log("Loop complete. Sleeping", CHECK_INTERVAL, "seconds.")
            time.sleep(CHECK_INTERVAL)
    finally:
        try:
            if selenium_driver:
                selenium_driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    main()