# BetaSlot-Sniper.py
# Automated Google Play Beta Program Slot Hunter
# Auto-detect default Windows browser, auto-download matching webdriver, reuse profile,
# monitor Google Play beta opt-in URLs and try to join when slot opens.

from datetime import datetime
import os, sys, time, subprocess, urllib.request, urllib.error, zipfile, shutil, json, webbrowser, re
import winreg
import http.cookiejar
from urllib.parse import urlencode
import argparse

# ---- USER CONFIG ----
PACKAGES = [
    "com.google.android.googlequicksearchbox",
    "com.google.android.projection.gearhead",
]

CHECK_INTERVAL = 30  # seconds between full loops
PER_PACKAGE_DELAY = 2
DOM_WAIT = 20  # Increased wait time for page loading
PAGE_LOAD_TIMEOUT = 40

# If you want to force a particular browser, set to "edge" / "chrome" / "firefox"
FORCE_BROWSER = None

# Behaviour flags (defaults) - can be changed via CLI args
EXIT_ON_JOIN = False        # if True, exit immediately when a join action happens
EXIT_ON_ALREADY = False     # if True, exit immediately when an already-enrolled package is detected

# Where drivers will be downloaded & extracted
DRIVER_BASE_DIR = os.path.join(os.path.expanduser("~"), ".selenium_drivers")
os.makedirs(DRIVER_BASE_DIR, exist_ok=True)

# ---- Colored Console Output ----
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def log_success(*args, **kwargs):
    print(f"{Colors.GREEN}[ SUCCESS ]{Colors.RESET} [{datetime.now()}]", *args, **kwargs)

def log_warning(*args, **kwargs):
    print(f"{Colors.YELLOW}[ WARNING ]{Colors.RESET} [{datetime.now()}]", *args, **kwargs)

def log_error(*args, **kwargs):
    print(f"{Colors.RED}[  ERROR  ]{Colors.RESET} [{datetime.now()}]", *args, **kwargs)

def log_info(*args, **kwargs):
    print(f"{Colors.CYAN}[   INFO  ]{Colors.RESET} [{datetime.now()}]", *args, **kwargs)

def log_debug(*args, **kwargs):
    print(f"{Colors.BLUE}[  DEBUG  ]{Colors.RESET} [{datetime.now()}]", *args, **kwargs)

# Backward compatibility
def log(*args, **kwargs):
    log_info(*args, **kwargs)

def print_welcome():
    """Display welcome banner"""
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*100}")
    print(f"🚀 WELCOME TO BETA-SLOT SNIPER")
    print(f"{'='*100}{Colors.RESET}")
    print(f"{Colors.WHITE}• Monitoring {len(PACKAGES)} packages for beta slot availability")
    print(f"• Check interval: {CHECK_INTERVAL} seconds")
    print(f"• Press Ctrl+C to stop monitoring")
    print(f"{Colors.CYAN}{'='*100}{Colors.RESET}")

def testing_url(pkg):
    return f"https://play.google.com/apps/testing/{pkg}"

# Function to kill browser processes
def kill_browser_processes(browser_name):
    try:
        import psutil
        browser_name = browser_name.lower()
        if browser_name == "edge":
            processes = ["msedge", "msedge.exe"]
        elif browser_name == "chrome":
            processes = ["chrome", "chrome.exe"]
        elif browser_name == "firefox":
            processes = ["firefox", "firefox.exe"]
        else:
            return
            
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'].lower() in processes:
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(2)  # Wait for processes to terminate
    except ImportError:
        log_warning("psutil not installed. Install with: pip install psutil")
    except Exception as e:
        log_error("Error killing browser processes:", e)

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

# Enhanced browser version detection
def get_browser_version(exe_path):
    """Enhanced browser version detection with multiple fallback methods"""
    if not exe_path or not os.path.exists(exe_path):
        return None
        
    try:
        # Method 1: Try --version flag (most reliable)
        try:
            result = subprocess.check_output([exe_path, "--version"], 
                                        stderr=subprocess.STDOUT, 
                                        timeout=5,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
            version_text = result.decode(errors="ignore").strip()
            version_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', version_text)
            if version_match:
                return version_match.group(1)
        except Exception:
            pass
            
        # Method 2: Try --product-version flag
        try:
            result = subprocess.check_output([exe_path, "--product-version"],
                                        stderr=subprocess.STDOUT,
                                        timeout=5,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
            version_text = result.decode(errors="ignore").strip()
            version_match = re.search(r'(\d+\.\d+\.\d+\.\d+|\d+\.\d+\.\d+|\d+\.\d+)', version_text)
            if version_match:
                return version_match.group(1)
        except Exception:
            pass
            
        # Method 3: Windows registry lookup (for Edge)
        if "edge" in exe_path.lower():
            try:
                import winreg
                key_path = r"SOFTWARE\Microsoft\Edge\BLBeacon"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    version, _ = winreg.QueryValueEx(key, "version")
                    return version
            except Exception:
                pass
                
        # Method 4: File properties via PowerShell
        try:
            result = subprocess.check_output([
                'powershell', 
                '-command', 
                f'(Get-Item "{exe_path}").VersionInfo.ProductVersion'
            ], stderr=subprocess.STDOUT, timeout=5, shell=True)
            version_text = result.decode(errors="ignore").strip()
            version_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', version_text)
            if version_match:
                return version_match.group(1)
        except Exception:
            pass
            
    except Exception as e:
        log_error(f"Could not query browser version for {exe_path}: {e}")
    
    return None

# download utility
def download_file(url, dest_path, show_log=True):
    try:
        if show_log:
            log_info("Downloading", url)
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
            log_success("Saved to", dest_path)
        return True
    except Exception as e:
        log_error("Download failed:", e)
        return False

# extract zip
def extract_zip(zip_path, dest_dir):
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest_dir)
        return True
    except Exception as e:
        log_error("Unzip failed:", e)
        return False

# ---- Enhanced driver downloaders ----
def ensure_edge_driver(browser_exe, browser_version):
    """Enhanced Edge WebDriver download with better version matching"""
    if not browser_version:
        try:
            latest_url = "https://msedgedriver.azureedge.net/LATEST_STABLE"
            with urllib.request.urlopen(latest_url, timeout=10) as r:
                browser_version = r.read().decode().strip()
        except Exception as e:
            log_error("Failed to get latest stable Edge version:", e)
            return None

    # First try: Exact version match
    zip_url = f"https://msedgedriver.azureedge.net/{browser_version}/edgedriver_win64.zip"
    dest_zip = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{browser_version}.zip")
    out_dir = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{browser_version}")
    
    if os.path.exists(out_dir):
        candidate = os.path.join(out_dir, "msedgedriver.exe")
        if os.path.exists(candidate):
            return candidate
            
    # Try downloading the exact version
    if download_file(zip_url, dest_zip, show_log=True):
        if extract_zip(dest_zip, out_dir):
            for root, dirs, files in os.walk(out_dir):
                if "msedgedriver.exe" in files:
                    log_success(f"Successfully downloaded Edge WebDriver {browser_version}")
                    return os.path.join(root, "msedgedriver.exe")
    
    # Second try: Major version matching with fallback
    major = browser_version.split('.')[0] if browser_version else None
    if major:
        try:
            # Try getting the latest release for this major version
            latest_url = f"https://msedgedriver.azureedge.net/LATEST_RELEASE_{major}"
            with urllib.request.urlopen(latest_url, timeout=10) as r:
                latest_ver = r.read().decode().strip()
            
            log_info(f"Trying WebDriver for major version {major}: {latest_ver}")
            
            zip_url = f"https://msedgedriver.azureedge.net/{latest_ver}/edgedriver_win64.zip"
            dest_zip = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{latest_ver}.zip")
            out_dir = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{latest_ver}")
            
            if os.path.exists(out_dir):
                candidate = os.path.join(out_dir, "msedgedriver.exe")
                if os.path.exists(candidate):
                    return candidate
                    
            if download_file(zip_url, dest_zip, show_log=True):
                if extract_zip(dest_zip, out_dir):
                    for root, dirs, files in os.walk(out_dir):
                        if "msedgedriver.exe" in files:
                            log_success(f"Successfully downloaded Edge WebDriver {latest_ver} for major version {major}")
                            return os.path.join(root, "msedgedriver.exe")
        except Exception as e:
            log_error(f"Failed to get Edge driver for major version {major}: {e}")
    
    # Final fallback: Use latest stable
    try:
        log_info("Attempting to download latest stable WebDriver as fallback")
        latest_url = "https://msedgedriver.azureedge.net/LATEST_STABLE"
        with urllib.request.urlopen(latest_url, timeout=10) as r:
            latest_stable = r.read().decode().strip()
        
        zip_url = f"https://msedgedriver.azureedge.net/{latest_stable}/edgedriver_win64.zip"
        dest_zip = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{latest_stable}.zip")
        out_dir = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{latest_stable}")
        
        if download_file(zip_url, dest_zip, show_log=True):
            if extract_zip(dest_zip, out_dir):
                for root, dirs, files in os.walk(out_dir):
                    if "msedgedriver.exe" in files:
                        log_success(f"Successfully downloaded latest stable Edge WebDriver: {latest_stable}")
                        return os.path.join(root, "msedgedriver.exe")
    except Exception as e:
        log_error("All Edge WebDriver download attempts failed:", e)
    
    return None

def ensure_chrome_driver(browser_version):
    """Enhanced ChromeDriver download with better version handling"""
    if not browser_version:
        return None
        
    major = browser_version.split('.')[0] if browser_version else None
    if not major:
        return None
        
    try:
        # Get the latest ChromeDriver for this major version
        url_version = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major}"
        with urllib.request.urlopen(url_version, timeout=10) as r:
            dr_version = r.read().decode().strip()
        
        log_info(f"Downloading ChromeDriver {dr_version} for Chrome {browser_version}")
        
        zip_url = f"https://chromedriver.storage.googleapis.com/{dr_version}/chromedriver_win32.zip"
        dest_zip = os.path.join(DRIVER_BASE_DIR, f"chromedriver_{dr_version}.zip")
        out_dir = os.path.join(DRIVER_BASE_DIR, f"chromedriver_{dr_version}")
        
        if os.path.exists(out_dir):
            candidate = os.path.join(out_dir, "chromedriver.exe")
            if os.path.exists(candidate):
                return candidate
                
        if download_file(zip_url, dest_zip, show_log=True):
            if extract_zip(dest_zip, out_dir):
                for root, dirs, files in os.walk(out_dir):
                    if "chromedriver.exe" in files:
                        log_success(f"Successfully downloaded ChromeDriver {dr_version}")
                        return os.path.join(root, "chromedriver.exe")
                        
    except Exception as e:
        log_error(f"Could not fetch ChromeDriver for major version {major}: {e}")
        return None
        
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
                        log_success(f"Successfully downloaded geckodriver {tag}")
                        return os.path.join(root, "geckodriver.exe")
    except Exception as e:
        log_error("Failed to fetch geckodriver:", e)
        
    return None

# Enhanced driver preparation with better error handling
def prepare_driver_for(browser):
    """Enhanced driver preparation with comprehensive error handling"""
    log_info(f"Preparing driver for {browser}")
    
    # Find browser binary
    bin_path = find_browser_binary(browser)
    if not bin_path:
        log_error(f"Could not find browser binary for {browser}")
        return None
        
    log_info(f"Found browser binary: {bin_path}")
    
    # Get browser version
    version = get_browser_version(bin_path)
    if not version:
        log_warning(f"Could not determine {browser} version")
        # Continue anyway, the downloader will try to get latest stable
    else:
        log_info(f"Browser version: {version}")
    
    # Check for existing drivers with more flexible matching
    driver_files = []
    driver_patterns = {
        "edge": ["msedgedriver*.exe", "edgedriver*.exe"],
        "chrome": ["chromedriver*.exe"],
        "firefox": ["geckodriver*.exe"]
    }
    
    patterns = driver_patterns.get(browser, [])
    for pattern in patterns:
        for root, dirs, files in os.walk(DRIVER_BASE_DIR):
            for file in files:
                if file.lower().endswith('.exe'):
                    full_path = os.path.join(root, file)
                    driver_files.append(full_path)
    
    # Use the first found driver
    if driver_files:
        driver_path = driver_files[0]
        log_success(f"Found existing driver: {driver_path}")
        return {"driver_path": driver_path, "binary": bin_path, "version": version}
    
    # If no existing driver found, try to download
    log_info(f"No existing driver found, attempting to download...")
    
    if browser == "edge":
        driver = ensure_edge_driver(bin_path, version)
        if driver:
            log_success(f"Successfully obtained msedgedriver: {driver}")
            return {"driver_path": driver, "binary": bin_path, "version": version}
        else:
            log_error("Could not download Edge driver automatically")
            log_info("Please download it manually from: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
            log_info(f"Place it in: {DRIVER_BASE_DIR}")
            return None
            
    elif browser == "chrome":
        driver = ensure_chrome_driver(version)
        if driver:
            log_success(f"Successfully obtained chromedriver: {driver}")
            return {"driver_path": driver, "binary": bin_path, "version": version}
        else:
            log_error("Could not download Chrome driver automatically")
            log_info("Please download it manually from: https://chromedriver.chromium.org/")
            log_info(f"Place it in: {DRIVER_BASE_DIR}")
            return None
            
    elif browser == "firefox":
        driver = ensure_gecko_driver()
        if driver:
            log_success(f"Successfully obtained geckodriver: {driver}")
            return {"driver_path": driver, "binary": bin_path, "version": version}
        else:
            log_error("Could not download Firefox driver automatically")
            log_info("Please download it manually from: https://github.com/mozilla/geckodriver/releases")
            log_info(f"Place it in: {DRIVER_BASE_DIR}")
            return None
    
    log_error(f"Could not prepare driver for {browser}")
    return None

# Selenium driver creation with explicit driver path + profile reuse
def create_selenium_driver(browser, prepared):
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
    except Exception as e:
        log_error("Selenium not installed or import failed:", e)
        return None

    # Try to create driver with retries
    for attempt in range(3):  # Try up to 3 times
        try:
            driver_path = prepared.get("driver_path")
            binary = prepared.get("binary")

            if browser == "edge":
                from selenium.webdriver.edge.service import Service as EdgeService
                from selenium.webdriver.edge.options import Options as EdgeOptions
                opts = EdgeOptions()
                if binary:
                    opts.binary_location = binary
                
                # Enhanced Edge options for better compatibility and to suppress warnings
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.add_argument("--remote-debugging-port=9222")
                opts.add_argument("--disable-blink-features=AutomationControlled")
                opts.add_argument("--log-level=3")  # Suppress browser logs
                opts.add_argument("--disable-logging")
                opts.add_argument("--disable-gpu")
                opts.add_argument("--disable-software-rasterizer")
                opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
                opts.add_experimental_option('useAutomationExtension', False)
                
                # Suppress WebDriver manager logs
                import logging
                selenium_logger = logging.getLogger('selenium')
                selenium_logger.setLevel(logging.WARNING)
                
                # attempt to reuse profile folder automatically (detect common locations)
                profile_parent, profile_dir = choose_chromium_profile(browser)
                if profile_parent:
                    opts.add_argument(f"--user-data-dir={profile_parent}")
                    if profile_dir:
                        opts.add_argument(f"--profile-directory={profile_dir}")
                
                service = EdgeService(executable_path=driver_path, service_args=['--silent'])
                
                try:
                    driver = webdriver.Edge(service=service, options=opts)
                    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                    # Hide automation indicators
                    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    return driver
                except Exception as e:
                    log_error(f"Edge driver creation failed: {e}")
                    return None

            if browser == "chrome":
                from selenium.webdriver.chrome.service import Service as ChromeService
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                opts = ChromeOptions()
                if binary:
                    opts.binary_location = binary
                
                # Add arguments to prevent crashes and suppress logs
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.add_argument("--log-level=3")
                opts.add_argument("--disable-logging")
                opts.add_argument("--disable-gpu")
                opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
                
                profile_parent, profile_dir = choose_chromium_profile(browser)
                if profile_parent:
                    opts.add_argument(f"--user-data-dir={profile_parent}")
                    if profile_dir:
                        opts.add_argument(f"--profile-directory={profile_dir}")
                
                service = ChromeService(executable_path=driver_path, service_args=['--silent'])
                driver = webdriver.Chrome(service=service, options=opts)
                driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                return driver

            if browser == "firefox":
                from selenium.webdriver.firefox.service import Service as FirefoxService
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
                
                opts = FirefoxOptions()
                # Add arguments to prevent crashes
                opts.add_argument("--no-sandbox")
                opts.add_argument("--log-level=3")
                
                fx_profile = find_firefox_profile()
                fp = FirefoxProfile(fx_profile) if fx_profile else None
                service = FirefoxService(executable_path=driver_path, service_args=['--silent'])
                driver = webdriver.Firefox(service=service, firefox_profile=fp, options=opts)
                driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                return driver

        except Exception as e:
            log_error(f"Failed to create Selenium driver (attempt {attempt + 1}/3):", e)
            if attempt < 2:  # Not the last attempt
                log_warning("Killing browser processes and retrying...")
                kill_browser_processes(browser)
                time.sleep(3)  # Wait before retrying
            else:
                log_error("All attempts failed.")
    
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

# ---- Enhanced detection & click logic using Selenium ----
def enhanced_selenium_check_and_click(driver, pkg):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    url = testing_url(pkg)
    log_info(f"Checking: {pkg}")
    
    try:
        driver.get(url)
        WebDriverWait(driver, DOM_WAIT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception as e:
        log_error(f"Page load failed: {e}")
        return False

    page_text = driver.page_source.upper()
    body_text = driver.find_element(By.TAG_NAME, "body").text.upper()

    # Enhanced SUCCESS detection
    success_indicators = [
        "YOU'RE A TESTER", "YOU ARE A TESTER", "SUCCESSFULLY JOINED", 
        "THANKS FOR JOINING", "WELCOME TO THE BETA", "YOU'VE JOINED THE BETA",
        "ENROLLMENT SUCCESSFUL", "NOW A BETA TESTER", "PARTICIPATING IN THIS PROGRAM"
    ]
    
    for indicator in success_indicators:
        if indicator in page_text:
            return "ALREADY_TESTER"

    # Enhanced FULL/BLOCKED detection with specific Android Auto message
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
        "NOT ACCEPTING",
        "REACHED THE MAXIMUM NUMBER OF TESTERS",
        "ISN'T ACCEPTING ANY MORE TESTERS",
        "THANKS FOR YOUR INTEREST IN BECOMING A TESTER"
    ]
    
    for pattern in full_patterns:
        if pattern in body_text:
            log_warning(f"{pkg}: Beta program is FULL")
            return False

    # Enhanced AVAILABLE detection
    available_patterns = [
        "BECOME A TESTER", "JOIN THE BETA", "JOIN BETA", "JOIN TESTING",
        "PARTICIPATE IN BETA", "BETA TESTER PROGRAM", "ACCEPT INVITATION",
        "JOIN THE TEST", "JOIN THE PROGRAM", "JOIN PROGRAM", "JOIN NOW",
        "SIGN UP", "BECOME A BETA TESTER", "PARTICIPATE IN THE BETA",
        "I'M IN", "ACCEPT", "PARTICIPATE", "ENROLL", "OPT-IN"
    ]
    
    # Check if beta is available
    beta_available = False
    for pattern in available_patterns:
        if pattern in body_text:
            beta_available = True
            log_info(f"Beta available detected for {pkg}")
            break

    if not beta_available:
        return False

    # Enhanced form detection and submission strategies
    join_strategies = [
        # Strategy 1: Direct form submission
        lambda: submit_beta_form(driver),
        # Strategy 2: Button clicking
        lambda: click_beta_buttons(driver),
        # Strategy 3: JavaScript execution
        lambda: js_beta_join(driver),
    ]
    
    for strategy in join_strategies:
        try:
            result = strategy()
            if result:
                log_success(f"Join action performed for {pkg}")
                # Verify success after action
                time.sleep(3)
                driver.refresh()
                page_text = driver.page_source.upper()
                
                # Check if we successfully joined
                for indicator in success_indicators:
                    if indicator in page_text:
                        log_success(f"🎉 SUCCESS! Joined beta program for {pkg}!")
                        return "SUCCESS"
                
                log_warning("Action performed but success not confirmed. Opening browser for manual verification.")
                webbrowser.open(url)
                return "MANUAL_VERIFICATION_NEEDED"
        except Exception as e:
            continue
    
    # If all strategies fail but beta is available, open browser
    log_warning("Could not automate join process. Opening browser for manual attempt.")
    webbrowser.open(url)
    return "MANUAL_ATTEMPT_NEEDED"

def submit_beta_form(driver):
    """Try to find and submit beta join forms"""
    from selenium.webdriver.common.by import By
    
    forms = driver.find_elements(By.CSS_SELECTOR, "form")
    for form in forms:
        form_html = form.get_attribute('outerHTML').upper()
        if any(keyword in form_html for keyword in ['BETA', 'TEST', 'JOIN', 'ENROLL', 'PARTICIPATE']):
            # Find submit buttons
            submits = form.find_elements(By.CSS_SELECTOR, 
                "input[type='submit'], button[type='submit'], input[type='button']")
            for submit in submits:
                if submit.is_displayed() and submit.is_enabled():
                    log_info("Found beta form - submitting")
                    submit.click()
                    return True
    return False

def click_beta_buttons(driver):
    """Click buttons with beta-related text"""
    from selenium.webdriver.common.by import By
    
    buttons = driver.find_elements(By.XPATH, 
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'join') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'beta') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'enroll') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'become') or "
        "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'participate')]")
    
    for button in buttons:
        try:
            if button.is_displayed() and button.is_enabled():
                button_text = button.text.upper()
                if any(keyword in button_text for keyword in ['JOIN', 'BETA', 'ENROLL', 'BECOME', 'PARTICIPATE']):
                    log_info(f"Clicking beta button: {button_text}")
                    button.click()
                    return True
        except:
            continue
    return False

def js_beta_join(driver):
    """Try to join beta using JavaScript"""
    try:
        # Try to find and click any element that might be the join button
        script = """
        var elements = document.querySelectorAll('button, input[type="submit"], a, div[role="button"]');
        for (var i = 0; i < elements.length; i++) {
            var element = elements[i];
            var text = (element.textContent || element.innerText || element.value || '').toLowerCase();
            if (text.includes('join') || text.includes('beta') || text.includes('enroll') || text.includes('become')) {
                element.click();
                return true;
            }
        }
        return false;
        """
        result = driver.execute_script(script)
        if result:
            log_info("JavaScript join attempt successful")
            return True
    except Exception as e:
        pass
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
        log_error("HTTP fetch failed:", e)
        return None

def http_check(pkg):
    url = testing_url(pkg)
    log_info("HTTP check:", pkg)
    text = fetch_page_text(url)
    if not text:
        log_error("Couldn't fetch", url)
        return False
    
    # Check if already a tester
    already_tester_patterns = [
        "YOU'RE A TESTER", "YOU ARE A TESTER", "ALREADY A TESTER",
        "ALREADY PARTICIPATING", "ALREADY JOINED", "YOU ARE PARTICIPATING",
        "PARTICIPATING IN THIS PROGRAM"
    ]
    
    for pattern in already_tester_patterns:
        if pattern in text:
            return "ALREADY_TESTER"
    
    # Enhanced FULL detection with Android Auto specific message
    full_patterns = [
        "BETA PROGRAM IS CURRENTLY FULL", "BETA PROGRAM IS FULL",
        "THE BETA PROGRAM FOR THIS APP IS CURRENTLY FULL", "BETA TESTER LIMIT HAS BEEN REACHED",
        "NO MORE TESTERS ARE BEING ACCEPTED", "BETA TESTING IS FULL", "BETA IS FULL",
        "TESTING IS FULL", "CLOSED", "NOT ACCEPTING", "REACHED THE MAXIMUM NUMBER OF TESTERS",
        "ISN'T ACCEPTING ANY MORE TESTERS", "THANKS FOR YOUR INTEREST IN BECOMING A TESTER"
    ]
    
    for pattern in full_patterns:
        if pattern in text:
            log_warning(f"{pkg}: beta FULL (http).")
            return False
    
    # Check for beta availability
    join_patterns = [
        "BECOME A TESTER", "JOIN THE BETA", "JOIN BETA", "JOIN TESTING",
        "PARTICIPATE IN BETA", "BETA TESTER PROGRAM", "ACCEPT INVITATION",
        "JOIN THE TEST", "JOIN THE PROGRAM", "JOIN PROGRAM", "JOIN NOW",
        "SIGN UP", "BECOME A BETA TESTER", "PARTICIPATE IN THE BETA",
        "I'M IN", "ACCEPT", "PARTICIPATE", "ENROLL", "OPT-IN"
    ]
    
    for pattern in join_patterns:
        if pattern in text:
            log_success(f"Possible slot for {pkg} - opening page.")
            webbrowser.open(url)
            return True
    
    # Check for form elements
    if 'FORM METHOD="POST" ACTION="/APPS/TESTING/' in text and 'CLASS="JOINFORM"' in text:
        log_success("Found beta join form - opening page.")
        webbrowser.open(url)
        return True
    
    return False

# ---- Main flow ----
def main():
    print_welcome()
    
    browser = FORCE_BROWSER or (sys.argv[1].lower() if len(sys.argv) > 1 else None)
    if not browser:
        browser = detect_default_browser()
    log_info(f"Detected/selected browser: {browser}")

    prepared = None
    selenium_driver = None

    if browser in ("edge", "chrome", "firefox"):
        prepared = prepare_driver_for(browser)
        if prepared:
            log_info(f"Prepared driver: {prepared.get('driver_path')}")
            # Kill any existing browser processes before creating driver
            kill_browser_processes(browser)
            selenium_driver = create_selenium_driver(browser, prepared)
            if selenium_driver:
                log_success("Selenium driver created successfully.")
            else:
                log_error("Failed to create Selenium driver - will fallback to HTTP polling.")
        else:
            log_error("Could not prepare driver automatically - will fallback to HTTP polling.")
    else:
        log_warning("Unsupported or undetected default browser. Using HTTP polling fallback.")

    # Use a set of remaining packages so we can skip ones already done
    remaining = set(PACKAGES)

    try:
        while remaining:
            for pkg in list(remaining):
                try:
                    if selenium_driver:
                        try:
                            selenium_driver.current_url
                        except Exception:
                            log_error("Selenium driver crashed. Recreating...")
                            try:
                                selenium_driver.quit()
                            except Exception:
                                pass
                            kill_browser_processes(browser)
                            selenium_driver = create_selenium_driver(browser, prepared)
                            if not selenium_driver:
                                log_error("Failed to recreate Selenium driver - switching to HTTP polling.")

                        if selenium_driver:
                            ok = enhanced_selenium_check_and_click(selenium_driver, pkg)
                        else:
                            ok = http_check(pkg)
                    else:
                        ok = http_check(pkg)

                    # If the checker signals you're already a tester
                    if ok == "ALREADY_TESTER":
                        if EXIT_ON_ALREADY:
                            log_success(f"Already a tester for {pkg} - exiting as requested.")
                            # attempt to clean up selenium driver
                            try:
                                if selenium_driver:
                                    selenium_driver.quit()
                            except Exception:
                                pass
                            return
                        else:
                            log_success(f"Already a tester for {pkg} - removing from watch list.")
                            remaining.remove(pkg)
                            continue

                    # If a join action was successful
                    if ok in ["SUCCESS", "MANUAL_VERIFICATION_NEEDED", "MANUAL_ATTEMPT_NEEDED"]:
                        log_success(f"Action taken for {pkg}")
                        if EXIT_ON_JOIN:
                            try:
                                if selenium_driver:
                                    selenium_driver.quit()
                            except Exception:
                                pass
                            return
                        else:
                            remaining.remove(pkg)
                            continue

                except Exception as e:
                    log_error(f"Error checking {pkg}: {e}")
                time.sleep(PER_PACKAGE_DELAY)

            if remaining:
                log_info(f"Still watching: {', '.join(sorted(remaining))}")
                log_info(f"Sleeping {CHECK_INTERVAL} seconds.")
                time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        log_info("Monitoring stopped by user.")
    finally:
        try:
            if selenium_driver:
                selenium_driver.quit()
                log_info("Selenium driver closed.")
        except Exception:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BetaSlot-Sniper")
    parser.add_argument("--exit-on-join", action="store_true",
                        help="Exit immediately when script successfully joins a beta")
    parser.add_argument("--exit-on-already", action="store_true",
                        help="Exit immediately if any package is already a tester")
    parser.add_argument("--once", action="store_true",
                        help="Alias for --exit-on-join and --exit-on-already (exit on first event)")
    args = parser.parse_args()

    # Set globals according to flags
    if args.once:
        EXIT_ON_JOIN = True
        EXIT_ON_ALREADY = True
    else:
        EXIT_ON_JOIN = args.exit_on_join
        EXIT_ON_ALREADY = args.exit_on_already

    main()