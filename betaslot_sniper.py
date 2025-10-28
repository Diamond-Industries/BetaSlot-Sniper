# BetaSlot-Sniper.py
# Automated Google Play Beta Program Slot Hunter
# Multi-browser, multi-platform support with package selection

from datetime import datetime
import os, sys, time, subprocess, urllib.request, urllib.error, zipfile, shutil, json, webbrowser, re
import http.cookiejar
from urllib.parse import urlencode
import argparse
import platform

# Platform detection
if sys.platform.startswith('win'):
    import winreg
    PLATFORM = "windows"
elif sys.platform.startswith('linux'):
    PLATFORM = "linux"
elif sys.platform.startswith('darwin'):
    PLATFORM = "macos"
else:
    PLATFORM = "unknown"

# ---- DEFAULT PACKAGES (User can select from these) ----
PREDEFINED_PACKAGES = {
    "Google App": "com.google.android.googlequicksearchbox",
    "Android Auto": "com.google.android.projection.gearhead", 
    "Google Messages": "com.google.android.apps.messaging",
    "Google Phone": "com.google.android.dialer",
    "YouTube": "com.google.android.youtube",
    "Google Maps": "com.google.android.apps.maps",
    "Google Home": "com.google.android.apps.chromecast.app",
    "Instagram": "com.instagram.android",
    "Snapchat": "com.snapchat.android",
    "Spotify": "com.spotify.music",
    "TikTok": "com.zhiliaoapp.musically"
}

# Will be populated based on user selection
PACKAGES = []

CHECK_INTERVAL = 30  # seconds between full loops
PER_PACKAGE_DELAY = 2
DOM_WAIT = 20  # Increased wait time for page loading
PAGE_LOAD_TIMEOUT = 40

# Comprehensive browser support with all channels
SUPPORTED_BROWSERS = {
    "chrome": ["stable", "beta", "dev"],
    "edge": ["stable", "beta", "dev", "canary"],
    "brave": ["stable", "beta", "nightly"],
    "opera": ["stable", "gx"],
    "firefox": ["stable", "developer", "nightly"],
    "librewolf": ["stable"]
}

# Default browser selection
FORCE_BROWSER = None
BROWSER_CHANNEL = "stable"

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
    print(f"{Colors.WHITE}• Platform: {PLATFORM}")
    print(f"• Monitoring {len(PACKAGES)} packages for beta slot availability")
    print(f"• Check interval: {CHECK_INTERVAL} seconds")
    print(f"• Press Ctrl+C to stop monitoring")
    print(f"{Colors.CYAN}{'='*100}{Colors.RESET}")

def testing_url(pkg):
    return f"https://play.google.com/apps/testing/{pkg}"

# ---- Package Selection Function ----
def select_packages():
    """Interactive package selection for the user"""
    global PACKAGES
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}📦 PACKAGE SELECTION{Colors.RESET}")
    print(f"{Colors.WHITE}Choose apps to monitor for beta slots:{Colors.RESET}")
    
    # Display predefined packages with numbers
    predefined_items = list(PREDEFINED_PACKAGES.items())
    for i, (name, pkg) in enumerate(predefined_items, 1):
        print(f"{Colors.CYAN}{i:2d}.{Colors.RESET} {name:30} {Colors.BLUE}({pkg}){Colors.RESET}")
    
    print(f"{Colors.CYAN} 0.{Colors.RESET} Custom package input")
    print(f"{Colors.CYAN}99.{Colors.RESET} Select ALL packages")
    
    while True:
        try:
            choice = input(f"\n{Colors.GREEN}Enter your choice (comma-separated numbers, 0 for custom, 99 for all): {Colors.RESET}").strip()
            
            if choice == "99":
                # Select all predefined packages
                PACKAGES = list(PREDEFINED_PACKAGES.values())
                print(f"{Colors.GREEN}Selected ALL {len(PACKAGES)} packages.{Colors.RESET}")
                break
                
            elif choice == "0":
                # Custom package input
                custom = input(f"{Colors.GREEN}Enter the custom package ID(s) (comma-separated): {Colors.RESET}").strip()
                custom_packages = [pkg.strip() for pkg in custom.split(',') if pkg.strip()]
                PACKAGES.extend(custom_packages)
                print(f"{Colors.GREEN}Added {len(custom_packages)} custom packages.{Colors.RESET}")
                break
                
            else:
                # Parse number selections
                selected_indices = []
                for part in choice.split(','):
                    part = part.strip()
                    if part.isdigit():
                        idx = int(part)
                        if 1 <= idx <= len(predefined_items):
                            selected_indices.append(idx - 1)
                
                if selected_indices:
                    PACKAGES = [predefined_items[i][1] for i in selected_indices]
                    package_names = [predefined_items[i][0] for i in selected_indices]
                    print(f"{Colors.GREEN}Selected {len(PACKAGES)} packages: {', '.join(package_names)}{Colors.RESET}")
                    break
                else:
                    print(f"{Colors.RED}Invalid selection. Please try again.{Colors.RESET}")
                    
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Selection cancelled.{Colors.RESET}")
            sys.exit(0)
        except Exception as e:
            print(f"{Colors.RED}Error: {e}. Please try again.{Colors.RESET}")

# ---- Browser Selection Function ----
def select_browser():
    """Interactive browser selection with auto-detection option"""
    global FORCE_BROWSER, BROWSER_CHANNEL
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}🌐 BROWSER SELECTION{Colors.RESET}")
    
    # First, offer auto-detection
    print(f"{Colors.WHITE}Would you like to auto-detect your default browser or choose manually?{Colors.RESET}")
    print(f"{Colors.CYAN}1.{Colors.RESET} Auto-detect default browser")
    print(f"{Colors.CYAN}2.{Colors.RESET} Choose browser manually")
    
    while True:
        try:
            detection_choice = input(f"{Colors.GREEN}Enter choice [1]: {Colors.RESET}").strip()
            if not detection_choice:
                detection_choice = "1"
                
            if detection_choice == "1":
                # Auto-detect
                detected_browser = detect_default_browser()
                if detected_browser:
                    print(f"{Colors.GREEN}Auto-detected browser: {detected_browser.capitalize()}{Colors.RESET}")
                    FORCE_BROWSER = detected_browser
                    
                    # Auto-select stable channel for detected browser
                    channels = SUPPORTED_BROWSERS.get(detected_browser, ["stable"])
                    BROWSER_CHANNEL = "stable"
                    print(f"{Colors.GREEN}Using {BROWSER_CHANNEL} channel{Colors.RESET}")
                    return
                else:
                    print(f"{Colors.RED}Could not auto-detect browser. Please select manually.{Colors.RESET}")
                    # Fall through to manual selection
                    
            if detection_choice == "2" or not FORCE_BROWSER:
                # Manual selection
                print(f"\n{Colors.WHITE}Available browsers:{Colors.RESET}")
                browsers = list(SUPPORTED_BROWSERS.keys())
                for i, browser in enumerate(browsers, 1):
                    channels = SUPPORTED_BROWSERS[browser]
                    print(f"{Colors.CYAN}{i:2d}.{Colors.RESET} {browser.capitalize():12} {Colors.BLUE}(channels: {', '.join(channels)}){Colors.RESET}")
                
                while True:
                    try:
                        browser_choice = input(f"\n{Colors.GREEN}Select browser (number or name): {Colors.RESET}").strip().lower()
                        
                        # Handle numeric input
                        if browser_choice.isdigit():
                            idx = int(browser_choice) - 1
                            if 0 <= idx < len(browsers):
                                FORCE_BROWSER = browsers[idx]
                                break
                            else:
                                print(f"{Colors.RED}Invalid number. Please try again.{Colors.RESET}")
                        else:
                            # Handle text input
                            if browser_choice in browsers:
                                FORCE_BROWSER = browser_choice
                                break
                            else:
                                print(f"{Colors.RED}Unknown browser. Available: {', '.join(browsers)}{Colors.RESET}")
                                
                    except KeyboardInterrupt:
                        print(f"\n{Colors.YELLOW}Selection cancelled.{Colors.RESET}")
                        sys.exit(0)
                    except Exception as e:
                        print(f"{Colors.RED}Error: {e}. Please try again.{Colors.RESET}")
                
                # Channel selection for supported browsers
                if FORCE_BROWSER in SUPPORTED_BROWSERS and len(SUPPORTED_BROWSERS[FORCE_BROWSER]) > 1:
                    channels = SUPPORTED_BROWSERS[FORCE_BROWSER]
                    print(f"\n{Colors.WHITE}Available channels for {FORCE_BROWSER}: {', '.join(channels)}{Colors.RESET}")
                    
                    while True:
                        try:
                            channel_choice = input(f"{Colors.GREEN}Select channel [{channels[0]}]: {Colors.RESET}").strip().lower()
                            if not channel_choice:  # Default to first channel
                                BROWSER_CHANNEL = channels[0]
                                break
                            elif channel_choice in channels:
                                BROWSER_CHANNEL = channel_choice
                                break
                            else:
                                print(f"{Colors.RED}Invalid channel. Choose from: {', '.join(channels)}{Colors.RESET}")
                        except KeyboardInterrupt:
                            BROWSER_CHANNEL = channels[0]
                            break
                else:
                    BROWSER_CHANNEL = "stable"
                
                print(f"{Colors.GREEN}Selected browser: {FORCE_BROWSER} ({BROWSER_CHANNEL}){Colors.RESET}")
                return
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Selection cancelled.{Colors.RESET}")
            sys.exit(0)
        except Exception as e:
            print(f"{Colors.RED}Error: {e}. Please try again.{Colors.RESET}")

# Function to kill browser processes
def kill_browser_processes(browser_name):
    try:
        import psutil
        browser_name = browser_name.lower()
        
        # Map browser names to process names
        process_map = {
            "edge": ["msedge", "msedge.exe"],
            "chrome": ["chrome", "chrome.exe", "google-chrome", "google-chrome-stable", "google-chrome-beta", "google-chrome-dev"],
            "firefox": ["firefox", "firefox.exe", "firefox-bin"],
            "librewolf": ["librewolf", "librewolf.exe"],
            "opera": ["opera", "opera.exe", "opera gx", "operagx", "opera-gx"],
            "brave": ["brave", "brave.exe", "brave-browser", "brave-browser-stable", "brave-browser-beta", "brave-browser-nightly"]
        }
        
        processes = process_map.get(browser_name, [])
        if not processes:
            return
            
        for proc in psutil.process_iter(['name']):
            try:
                proc_name = proc.info['name'].lower()
                if any(p in proc_name for p in processes):
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(2)  # Wait for processes to terminate
    except ImportError:
        log_warning("psutil not installed. Install with: pip install psutil")
    except Exception as e:
        log_error("Error killing browser processes:", e)

# Determine default browser (Windows)
def detect_default_browser_windows():
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
        if "opera" in pid:
            return "opera"
        if "brave" in pid:
            return "brave"
        if "librewolf" in pid:
            return "librewolf"
    except Exception:
        pass
    return None

# Determine default browser (Linux)
def detect_default_browser_linux():
    try:
        # Try xdg-settings
        result = subprocess.run(['xdg-settings', 'get', 'default-web-browser'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            browser = result.stdout.strip().lower()
            if 'chrome' in browser or 'google-chrome' in browser:
                return 'chrome'
            elif 'firefox' in browser:
                return 'firefox'
            elif 'opera' in browser:
                return 'opera'
            elif 'brave' in browser:
                return 'brave'
            elif 'librewolf' in browser:
                return 'librewolf'
            elif 'edge' in browser:
                return 'edge'
    except Exception:
        pass
    
    # Fallback: check common browsers
    common_browsers = [
        'google-chrome', 'google-chrome-stable', 'google-chrome-beta', 'google-chrome-dev',
        'firefox', 'firefox-esr', 
        'opera', 'opera-stable', 'opera-gx',
        'brave-browser', 'brave-browser-stable', 'brave-browser-beta', 'brave-browser-nightly',
        'librewolf',
        'microsoft-edge', 'microsoft-edge-stable', 'microsoft-edge-beta', 'microsoft-edge-dev'
    ]
    for browser in common_browsers:
        try:
            subprocess.run(['which', browser], check=True, capture_output=True, timeout=5)
            # Return base name
            if 'chrome' in browser:
                return 'chrome'
            elif 'firefox' in browser:
                return 'firefox'
            elif 'opera' in browser:
                return 'opera'
            elif 'brave' in browser:
                return 'brave'
            elif 'librewolf' in browser:
                return 'librewolf'
            elif 'edge' in browser:
                return 'edge'
        except subprocess.CalledProcessError:
            continue
    return None

# Determine default browser (macOS)
def detect_default_browser_macos():
    try:
        script = '''
        tell application "System Events"
            set defaultBrowser to do shell script "defaults read \\
                ~/Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure \\
                | awk -F'\"' '/http;/{print window[(NR)-1)]}' | tail -1"
            return defaultBrowser
        end tell
        '''
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            browser = result.stdout.strip().lower()
            if 'chrome' in browser:
                return 'chrome'
            elif 'firefox' in browser:
                return 'firefox'
            elif 'safari' in browser:
                return 'safari'
            elif 'opera' in browser:
                return 'opera'
            elif 'brave' in browser:
                return 'brave'
            elif 'librewolf' in browser:
                return 'librewolf'
            elif 'edge' in browser:
                return 'edge'
    except Exception:
        pass
    
    # Fallback: check common applications
    applications = [
        "/Applications/Google Chrome.app",
        "/Applications/Firefox.app", 
        "/Applications/Opera.app",
        "/Applications/Brave Browser.app",
        "/Applications/LibreWolf.app",
        "/Applications/Microsoft Edge.app"
    ]
    for app in applications:
        if os.path.exists(app):
            if "Chrome" in app:
                return "chrome"
            elif "Firefox" in app:
                return "firefox"
            elif "Opera" in app:
                return "opera"
            elif "Brave" in app:
                return "brave"
            elif "LibreWolf" in app:
                return "librewolf"
            elif "Edge" in app:
                return "edge"
    return None

def detect_default_browser():
    if PLATFORM == "windows":
        return detect_default_browser_windows()
    elif PLATFORM == "linux":
        return detect_default_browser_linux()
    elif PLATFORM == "macos":
        return detect_default_browser_macos()
    return None

# Get browser installation path from registry (Windows)
def get_browser_path_windows(browser, channel):
    base_paths = [
        os.getenv("ProgramFiles", r"C:\Program Files"),
        os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.path.expanduser("~")
    ]
    
    browser_paths = {
        "edge": {
            "stable": [
                r"Microsoft\Edge\Application\msedge.exe",
            ],
            "beta": [
                r"Microsoft\Edge Beta\Application\msedge.exe",
            ],
            "dev": [
                r"Microsoft\Edge Dev\Application\msedge.exe",
            ],
            "canary": [
                r"Microsoft\Edge Canary\Application\msedge.exe",
            ]
        },
        "chrome": {
            "stable": [
                r"Google\Chrome\Application\chrome.exe",
            ],
            "beta": [
                r"Google\Chrome Beta\Application\chrome.exe",
            ],
            "dev": [
                r"Google\Chrome Dev\Application\chrome.exe",
            ]
        },
        "firefox": {
            "stable": [
                r"Mozilla Firefox\firefox.exe",
            ],
            "developer": [
                r"Firefox Developer Edition\firefox.exe",
            ],
            "nightly": [
                r"Firefox Nightly\firefox.exe",
            ]
        },
        "opera": {
            "stable": [
                r"Opera\launcher.exe",
            ],
            "gx": [
                r"Opera GX\launcher.exe",
            ]
        },
        "brave": {
            "stable": [
                r"BraveSoftware\Brave-Browser\Application\brave.exe",
            ],
            "beta": [
                r"BraveSoftware\Brave-Browser-Beta\Application\brave.exe",
            ],
            "nightly": [
                r"BraveSoftware\Brave-Browser-Nightly\Application\brave.exe",
            ]
        },
        "librewolf": {
            "stable": [
                r"LibreWolf\librewolf.exe",
            ]
        }
    }
    
    # Try registry first for some browsers
    if browser == "edge":
        try:
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                path, _ = winreg.QueryValueEx(key, None)
                if os.path.exists(path):
                    return path
        except Exception:
            pass
    
    # Search file system
    paths_to_try = browser_paths.get(browser, {}).get(channel, [])
    for base in base_paths:
        for rel_path in paths_to_try:
            full_path = os.path.join(base, rel_path)
            if os.path.exists(full_path):
                return full_path
    
    return None

# Get browser installation path (Linux)
def get_browser_path_linux(browser, channel):
    browser_commands = {
        "chrome": {
            "stable": ["google-chrome", "google-chrome-stable", "chrome"],
            "beta": ["google-chrome-beta"],
            "dev": ["google-chrome-unstable", "google-chrome-dev"]
        },
        "firefox": {
            "stable": ["firefox", "firefox-esr"],
            "developer": ["firefox-developer-edition", "firefox-dev"],
            "nightly": ["firefox-nightly"]
        },
        "opera": {
            "stable": ["opera"],
            "gx": ["opera-gx"]
        },
        "brave": {
            "stable": ["brave-browser", "brave-browser-stable", "brave"],
            "beta": ["brave-browser-beta"],
            "nightly": ["brave-browser-nightly"]
        },
        "librewolf": {
            "stable": ["librewolf"]
        },
        "edge": {
            "stable": ["microsoft-edge", "microsoft-edge-stable"],
            "beta": ["microsoft-edge-beta"],
            "dev": ["microsoft-edge-dev"],
            "canary": ["microsoft-edge-canary"]
        }
    }
    
    commands = browser_commands.get(browser, {}).get(channel, [])
    for cmd in commands:
        try:
            result = subprocess.run(['which', cmd], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            continue
    
    return None

# Get browser installation path (macOS)
def get_browser_path_macos(browser, channel):
    applications_path = "/Applications"
    browser_apps = {
        "chrome": {
            "stable": "Google Chrome.app/Contents/MacOS/Google Chrome",
            "beta": "Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta", 
            "dev": "Google Chrome Dev.app/Contents/MacOS/Google Chrome Dev"
        },
        "firefox": {
            "stable": "Firefox.app/Contents/MacOS/firefox",
            "developer": "Firefox Developer Edition.app/Contents/MacOS/firefox",
            "nightly": "Firefox Nightly.app/Contents/MacOS/firefox"
        },
        "opera": {
            "stable": "Opera.app/Contents/MacOS/Opera",
            "gx": "Opera GX.app/Contents/MacOS/Opera GX"
        },
        "brave": {
            "stable": "Brave Browser.app/Contents/MacOS/Brave Browser",
            "beta": "Brave Browser Beta.app/Contents/MacOS/Brave Browser Beta",
            "nightly": "Brave Browser Nightly.app/Contents/MacOS/Brave Browser Nightly"
        },
        "edge": {
            "stable": "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "beta": "Microsoft Edge Beta.app/Contents/MacOS/Microsoft Edge Beta",
            "dev": "Microsoft Edge Dev.app/Contents/MacOS/Microsoft Edge Dev",
            "canary": "Microsoft Edge Canary.app/Contents/MacOS/Microsoft Edge Canary"
        },
        "librewolf": {
            "stable": "LibreWolf.app/Contents/MacOS/librewolf"
        }
    }
    
    app_paths = browser_apps.get(browser, {}).get(channel, [])
    if isinstance(app_paths, str):
        app_paths = [app_paths]
    
    for app_path in app_paths:
        full_path = os.path.join(applications_path, app_path)
        if os.path.exists(full_path):
            return full_path
    
    return None

# Try common browser executable locations
def find_browser_binary(browser, channel="stable"):
    if PLATFORM == "windows":
        return get_browser_path_windows(browser, channel)
    elif PLATFORM == "linux":
        return get_browser_path_linux(browser, channel)
    elif PLATFORM == "macos":
        return get_browser_path_macos(browser, channel)
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
                                        timeout=5)
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
                                        timeout=5)
            version_text = result.decode(errors="ignore").strip()
            version_match = re.search(r'(\d+\.\d+\.\d+\.\d+|\d+\.\d+\.\d+|\d+\.\d+)', version_text)
            if version_match:
                return version_match.group(1)
        except Exception:
            pass
            
        # Method 3: Windows registry lookup
        if PLATFORM == "windows" and "edge" in exe_path.lower():
            try:
                key_path = r"SOFTWARE\Microsoft\Edge\BLBeacon"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    version, _ = winreg.QueryValueEx(key, "version")
                    return version
            except Exception:
                pass
                
        # Method 4: File properties via system commands
        if PLATFORM == "windows":
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
        elif PLATFORM in ["linux", "macos"]:
            try:
                # Try dpkg on Linux
                if PLATFORM == "linux":
                    browser_name = os.path.basename(exe_path)
                    result = subprocess.check_output(['dpkg', '-s', browser_name], 
                                                   stderr=subprocess.STDOUT, timeout=5)
                    version_text = result.decode(errors="ignore")
                    version_match = re.search(r'Version:\s*([\d.]+)', version_text)
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

# extract tar.gz
def extract_tar_gz(tar_path, dest_dir):
    try:
        import tarfile
        with tarfile.open(tar_path, 'r:gz') as tar:
            tar.extractall(dest_dir)
        return True
    except Exception as e:
        log_error("Tar extract failed:", e)
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

    # Determine platform-specific download
    if PLATFORM == "windows":
        zip_name = "edgedriver_win64.zip"
        driver_name = "msedgedriver.exe"
    elif PLATFORM == "linux":
        zip_name = "edgedriver_linux64.zip"
        driver_name = "msedgedriver"
    elif PLATFORM == "macos":
        if platform.machine().lower() in ['arm64', 'aarch64']:
            zip_name = "edgedriver_mac64_m1.zip"
        else:
            zip_name = "edgedriver_mac64.zip"
        driver_name = "msedgedriver"
    else:
        log_error(f"Unsupported platform for Edge: {PLATFORM}")
        return None

    # First try: Exact version match
    zip_url = f"https://msedgedriver.azureedge.net/{browser_version}/{zip_name}"
    dest_zip = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{browser_version}.zip")
    out_dir = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{browser_version}")
    
    if os.path.exists(out_dir):
        candidate = os.path.join(out_dir, driver_name)
        if os.path.exists(candidate):
            return candidate
            
    # Try downloading the exact version
    if download_file(zip_url, dest_zip, show_log=True):
        if extract_zip(dest_zip, out_dir):
            for root, dirs, files in os.walk(out_dir):
                if driver_name in files:
                    driver_path = os.path.join(root, driver_name)
                    if PLATFORM != "windows":
                        os.chmod(driver_path, 0o755)  # Make executable on Unix
                    log_success(f"Successfully downloaded Edge WebDriver {browser_version}")
                    return driver_path
    
    # Second try: Major version matching with fallback
    major = browser_version.split('.')[0] if browser_version else None
    if major:
        try:
            # Try getting the latest release for this major version
            latest_url = f"https://msedgedriver.azureedge.net/LATEST_RELEASE_{major}"
            with urllib.request.urlopen(latest_url, timeout=10) as r:
                latest_ver = r.read().decode().strip()
            
            log_info(f"Trying WebDriver for major version {major}: {latest_ver}")
            
            zip_url = f"https://msedgedriver.azureedge.net/{latest_ver}/{zip_name}"
            dest_zip = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{latest_ver}.zip")
            out_dir = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{latest_ver}")
            
            if os.path.exists(out_dir):
                candidate = os.path.join(out_dir, driver_name)
                if os.path.exists(candidate):
                    return candidate
                    
            if download_file(zip_url, dest_zip, show_log=True):
                if extract_zip(dest_zip, out_dir):
                    for root, dirs, files in os.walk(out_dir):
                        if driver_name in files:
                            driver_path = os.path.join(root, driver_name)
                            if PLATFORM != "windows":
                                os.chmod(driver_path, 0o755)
                            log_success(f"Successfully downloaded Edge WebDriver {latest_ver} for major version {major}")
                            return driver_path
        except Exception as e:
            log_error(f"Failed to get Edge driver for major version {major}: {e}")
    
    # Final fallback: Use latest stable
    try:
        log_info("Attempting to download latest stable WebDriver as fallback")
        latest_url = "https://msedgedriver.azureedge.net/LATEST_STABLE"
        with urllib.request.urlopen(latest_url, timeout=10) as r:
            latest_stable = r.read().decode().strip()
        
        zip_url = f"https://msedgedriver.azureedge.net/{latest_stable}/{zip_name}"
        dest_zip = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{latest_stable}.zip")
        out_dir = os.path.join(DRIVER_BASE_DIR, f"msedgedriver_{latest_stable}")
        
        if download_file(zip_url, dest_zip, show_log=True):
            if extract_zip(dest_zip, out_dir):
                for root, dirs, files in os.walk(out_dir):
                    if driver_name in files:
                        driver_path = os.path.join(root, driver_name)
                        if PLATFORM != "windows":
                            os.chmod(driver_path, 0o755)
                        log_success(f"Successfully downloaded latest stable Edge WebDriver: {latest_stable}")
                        return driver_path
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
        
        # Determine platform-specific download
        if PLATFORM == "windows":
            zip_name = "chromedriver_win32.zip"
            driver_name = "chromedriver.exe"
        elif PLATFORM == "linux":
            zip_name = "chromedriver_linux64.zip"
            driver_name = "chromedriver"
        elif PLATFORM == "macos":
            if platform.machine().lower() in ['arm64', 'aarch64']:
                zip_name = "chromedriver_mac_arm64.zip"
            else:
                zip_name = "chromedriver_mac64.zip"
            driver_name = "chromedriver"
        else:
            log_error(f"Unsupported platform for Chrome: {PLATFORM}")
            return None
        
        zip_url = f"https://chromedriver.storage.googleapis.com/{dr_version}/{zip_name}"
        dest_zip = os.path.join(DRIVER_BASE_DIR, f"chromedriver_{dr_version}.zip")
        out_dir = os.path.join(DRIVER_BASE_DIR, f"chromedriver_{dr_version}")
        
        if os.path.exists(out_dir):
            candidate = os.path.join(out_dir, driver_name)
            if os.path.exists(candidate):
                return candidate
                
        if download_file(zip_url, dest_zip, show_log=True):
            if extract_zip(dest_zip, out_dir):
                for root, dirs, files in os.walk(out_dir):
                    if driver_name in files:
                        driver_path = os.path.join(root, driver_name)
                        if PLATFORM != "windows":
                            os.chmod(driver_path, 0o755)
                        log_success(f"Successfully downloaded ChromeDriver {dr_version}")
                        return driver_path
                        
    except Exception as e:
        log_error(f"Could not fetch ChromeDriver for major version {major}: {e}")
        return None
        
    return None

def ensure_gecko_driver(browser_name="firefox"):
    """GeckoDriver for Firefox and LibreWolf"""
    try:
        api = "https://api.github.com/repos/mozilla/geckodriver/releases/latest"
        with urllib.request.urlopen(api, timeout=10) as r:
            data = json.load(r)
        assets = data.get("assets", [])
        
        # Determine platform-specific asset
        asset_patterns = {
            "windows": "win64.zip",
            "linux": "linux64.tar.gz", 
            "macos": "macos.tar.gz"
        }
        
        target_asset = None
        for a in assets:
            name = a.get("name","").lower()
            if PLATFORM in asset_patterns and asset_patterns[PLATFORM] in name:
                target_asset = a.get("browser_download_url")
                break
                
        if not target_asset:
            return None
            
        tag = data.get("tag_name","latest").lstrip("v")
        
        if PLATFORM == "windows":
            dest_file = os.path.join(DRIVER_BASE_DIR, f"geckodriver_{tag}.zip")
            extract_func = extract_zip
            driver_name = "geckodriver.exe"
        else:
            dest_file = os.path.join(DRIVER_BASE_DIR, f"geckodriver_{tag}.tar.gz")
            extract_func = extract_tar_gz
            driver_name = "geckodriver"
            
        out_dir = os.path.join(DRIVER_BASE_DIR, f"geckodriver_{tag}")
        
        if os.path.exists(out_dir):
            candidate = os.path.join(out_dir, driver_name)
            if os.path.exists(candidate):
                return candidate
                
        if download_file(target_asset, dest_file):
            if extract_func(dest_file, out_dir):
                for root, dirs, files in os.walk(out_dir):
                    if driver_name in files:
                        driver_path = os.path.join(root, driver_name)
                        if PLATFORM != "windows":
                            os.chmod(driver_path, 0o755)
                        log_success(f"Successfully downloaded geckodriver {tag} for {browser_name}")
                        return driver_path
    except Exception as e:
        log_error(f"Failed to fetch geckodriver for {browser_name}:", e)
        
    return None

def ensure_opera_driver(browser_version):
    """OperaDriver download"""
    try:
        # OperaDriver uses Chromium versioning
        if not browser_version:
            return None
            
        major = browser_version.split('.')[0]
        
        # Get OperaDriver version from their API
        api_url = "https://api.github.com/repos/operasoftware/operachromiumdriver/releases/latest"
        with urllib.request.urlopen(api_url, timeout=10) as r:
            data = json.load(r)
            
        assets = data.get("assets", [])
        
        # Determine platform-specific asset
        asset_name = None
        if PLATFORM == "windows":
            asset_name = "operadriver_win64.zip"
        elif PLATFORM == "linux":
            asset_name = "operadriver_linux64.zip"
        elif PLATFORM == "macos":
            asset_name = "operadriver_mac64.zip"
            
        download_url = None
        for asset in assets:
            if asset.get("name") == asset_name:
                download_url = asset.get("browser_download_url")
                break
                
        if not download_url:
            return None
            
        tag = data.get("tag_name", "latest")
        dest_zip = os.path.join(DRIVER_BASE_DIR, f"operadriver_{tag}.zip")
        out_dir = os.path.join(DRIVER_BASE_DIR, f"operadriver_{tag}")
        driver_name = "operadriver.exe" if PLATFORM == "windows" else "operadriver"
        
        if os.path.exists(out_dir):
            candidate = os.path.join(out_dir, driver_name)
            if os.path.exists(candidate):
                return candidate
                
        if download_file(download_url, dest_zip):
            if extract_zip(dest_zip, out_dir):
                for root, dirs, files in os.walk(out_dir):
                    if driver_name in files:
                        driver_path = os.path.join(root, driver_name)
                        if PLATFORM != "windows":
                            os.chmod(driver_path, 0o755)
                        log_success(f"Successfully downloaded OperaDriver {tag}")
                        return driver_path
                        
    except Exception as e:
        log_error(f"Could not fetch OperaDriver: {e}")
        
    return None

# Enhanced driver preparation with better error handling
def prepare_driver_for(browser, channel="stable"):
    """Enhanced driver preparation with comprehensive error handling"""
    log_info(f"Preparing driver for {browser} ({channel})")
    
    # Find browser binary
    bin_path = find_browser_binary(browser, channel)
    if not bin_path:
        log_error(f"Could not find browser binary for {browser} ({channel})")
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
        "edge": ["msedgedriver*", "edgedriver*"],
        "chrome": ["chromedriver*"],
        "firefox": ["geckodriver*"],
        "librewolf": ["geckodriver*"],
        "opera": ["operadriver*"],
        "brave": ["chromedriver*"]  # Brave uses ChromeDriver
    }
    
    patterns = driver_patterns.get(browser, [])
    for pattern in patterns:
        for root, dirs, files in os.walk(DRIVER_BASE_DIR):
            for file in files:
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
            
    elif browser in ["firefox", "librewolf"]:
        driver = ensure_gecko_driver(browser)
        if driver:
            log_success(f"Successfully obtained geckodriver: {driver}")
            return {"driver_path": driver, "binary": bin_path, "version": version}
        else:
            log_error(f"Could not download {browser} driver automatically")
            log_info("Please download it manually from: https://github.com/mozilla/geckodriver/releases")
            log_info(f"Place it in: {DRIVER_BASE_DIR}")
            return None
            
    elif browser == "opera":
        driver = ensure_opera_driver(version)
        if driver:
            log_success(f"Successfully obtained operadriver: {driver}")
            return {"driver_path": driver, "binary": bin_path, "version": version}
        else:
            log_error("Could not download Opera driver automatically")
            log_info("Please download it manually from: https://github.com/operasoftware/operachromiumdriver/releases")
            log_info(f"Place it in: {DRIVER_BASE_DIR}")
            return None
            
    elif browser == "brave":
        # Brave uses ChromeDriver
        driver = ensure_chrome_driver(version)
        if driver:
            log_success(f"Successfully obtained chromedriver for Brave: {driver}")
            return {"driver_path": driver, "binary": bin_path, "version": version}
        else:
            log_error("Could not download Brave driver automatically")
            log_info("Brave uses ChromeDriver. Please download it manually from: https://chromedriver.chromium.org/")
            log_info(f"Place it in: {DRIVER_BASE_DIR}")
            return None
    
    log_error(f"Could not prepare driver for {browser}")
    return None

# Platform-specific profile paths
def get_chromium_profile_paths(browser, channel):
    """Get Chromium-based browser profile paths for all platforms"""
    user = os.path.expanduser("~")
    
    profile_paths = {
        "windows": {
            "chrome": {
                "stable": os.path.join(user, "AppData", "Local", "Google", "Chrome", "User Data"),
                "beta": os.path.join(user, "AppData", "Local", "Google", "Chrome Beta", "User Data"),
                "dev": os.path.join(user, "AppData", "Local", "Google", "Chrome Dev", "User Data"),
            },
            "edge": {
                "stable": os.path.join(user, "AppData", "Local", "Microsoft", "Edge", "User Data"),
                "beta": os.path.join(user, "AppData", "Local", "Microsoft", "Edge Beta", "User Data"),
                "dev": os.path.join(user, "AppData", "Local", "Microsoft", "Edge Dev", "User Data"),
                "canary": os.path.join(user, "AppData", "Local", "Microsoft", "Edge Canary", "User Data")
            },
            "opera": {
                "stable": os.path.join(user, "AppData", "Roaming", "Opera Software", "Opera Stable"),
                "gx": os.path.join(user, "AppData", "Roaming", "Opera Software", "Opera GX Stable")
            },
            "brave": {
                "stable": os.path.join(user, "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data"),
                "beta": os.path.join(user, "AppData", "Local", "BraveSoftware", "Brave-Browser-Beta", "User Data"),
                "nightly": os.path.join(user, "AppData", "Local", "BraveSoftware", "Brave-Browser-Nightly", "User Data")
            }
        },
        "linux": {
            "chrome": {
                "stable": os.path.join(user, ".config", "google-chrome"),
                "beta": os.path.join(user, ".config", "google-chrome-beta"),
                "dev": os.path.join(user, ".config", "google-chrome-unstable")
            },
            "edge": {
                "stable": os.path.join(user, ".config", "microsoft-edge"),
                "beta": os.path.join(user, ".config", "microsoft-edge-beta"),
                "dev": os.path.join(user, ".config", "microsoft-edge-dev")
            },
            "opera": {
                "stable": os.path.join(user, ".config", "opera"),
                "gx": os.path.join(user, ".config", "opera-gx")
            },
            "brave": {
                "stable": os.path.join(user, ".config", "BraveSoftware", "Brave-Browser"),
                "beta": os.path.join(user, ".config", "BraveSoftware", "Brave-Browser-Beta"),
                "nightly": os.path.join(user, ".config", "BraveSoftware", "Brave-Browser-Nightly")
            }
        },
        "macos": {
            "chrome": {
                "stable": os.path.join(user, "Library", "Application Support", "Google", "Chrome"),
                "beta": os.path.join(user, "Library", "Application Support", "Google", "Chrome Beta"),
                "dev": os.path.join(user, "Library", "Application Support", "Google", "Chrome Dev"),
            },
            "edge": {
                "stable": os.path.join(user, "Library", "Application Support", "Microsoft Edge"),
                "beta": os.path.join(user, "Library", "Application Support", "Microsoft Edge Beta"),
                "dev": os.path.join(user, "Library", "Application Support", "Microsoft Edge Dev"),
                "canary": os.path.join(user, "Library", "Application Support", "Microsoft Edge Canary")
            },
            "opera": {
                "stable": os.path.join(user, "Library", "Application Support", "com.operasoftware.Opera"),
                "gx": os.path.join(user, "Library", "Application Support", "com.operasoftware.OperaGX")
            },
            "brave": {
                "stable": os.path.join(user, "Library", "Application Support", "BraveSoftware", "Brave-Browser"),
                "beta": os.path.join(user, "Library", "Application Support", "BraveSoftware", "Brave-Browser-Beta"),
                "nightly": os.path.join(user, "Library", "Application Support", "BraveSoftware", "Brave-Browser-Nightly")
            }
        }
    }
    
    return profile_paths.get(PLATFORM, {}).get(browser, {}).get(channel)

def get_firefox_profile_paths(browser):
    """Get Firefox-based browser profile paths for all platforms"""
    user = os.path.expanduser("~")
    
    if browser == "firefox":
        if PLATFORM == "windows":
            return os.path.join(user, "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
        elif PLATFORM == "linux":
            return os.path.join(user, ".mozilla", "firefox")
        elif PLATFORM == "macos":
            return os.path.join(user, "Library", "Application Support", "Firefox", "Profiles")
    elif browser == "librewolf":
        if PLATFORM == "windows":
            return os.path.join(user, "AppData", "Roaming", "librewolf", "Profiles")
        elif PLATFORM == "linux":
            return os.path.join(user, ".librewolf")
        elif PLATFORM == "macos":
            return os.path.join(user, "Library", "Application Support", "librewolf", "Profiles")
    
    return None

# helper to pick chromium user-data folder and profile directory
def choose_chromium_profile(browser, channel):
    profile_parent = get_chromium_profile_paths(browser, channel)
    if profile_parent and os.path.exists(profile_parent):
        return profile_parent, "Default"
    return None, None

# Find Firefox profile
def find_firefox_profile(browser):
    profile_parent = get_firefox_profile_paths(browser)
    if profile_parent and os.path.exists(profile_parent):
        for profile in os.listdir(profile_parent):
            if profile.endswith(".default-release") or profile.endswith(".default"):
                return os.path.join(profile_parent, profile)
    return None

# Selenium driver creation with explicit driver path + profile reuse
def create_selenium_driver(browser, prepared, channel="stable"):
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

            if browser in ["edge", "chrome", "opera", "brave"]:
                # Chromium-based browsers
                if browser == "edge":
                    from selenium.webdriver.edge.service import Service as EdgeService
                    from selenium.webdriver.edge.options import Options as EdgeOptions
                    opts = EdgeOptions()
                    service_class = EdgeService
                elif browser == "chrome":
                    from selenium.webdriver.chrome.service import Service as ChromeService
                    from selenium.webdriver.chrome.options import Options as ChromeOptions
                    opts = ChromeOptions()
                    service_class = ChromeService
                elif browser == "opera":
                    from selenium.webdriver.chrome.service import Service as ChromeService
                    from selenium.webdriver.chrome.options import Options as ChromeOptions
                    opts = ChromeOptions()
                    service_class = ChromeService
                elif browser == "brave":
                    from selenium.webdriver.chrome.service import Service as ChromeService
                    from selenium.webdriver.chrome.options import Options as ChromeOptions
                    opts = ChromeOptions()
                    service_class = ChromeService
                    # Brave specific options
                    opts.binary_location = binary
                
                if binary and browser != "brave":  # Brave already set above
                    opts.binary_location = binary
                
                # Enhanced Chromium options for better compatibility
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.add_argument("--remote-debugging-port=9222")
                opts.add_argument("--disable-blink-features=AutomationControlled")
                opts.add_argument("--log-level=3")
                opts.add_argument("--disable-logging")
                opts.add_argument("--disable-gpu")
                opts.add_argument("--disable-software-rasterizer")
                opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
                opts.add_experimental_option('useAutomationExtension', False)
                
                # Suppress WebDriver manager logs
                import logging
                selenium_logger = logging.getLogger('selenium')
                selenium_logger.setLevel(logging.WARNING)
                
                # attempt to reuse profile folder automatically
                profile_parent, profile_dir = choose_chromium_profile(browser, channel)
                if profile_parent:
                    opts.add_argument(f"--user-data-dir={profile_parent}")
                    if profile_dir:
                        opts.add_argument(f"--profile-directory={profile_dir}")
                
                service = service_class(executable_path=driver_path, service_args=['--silent'])
                
                try:
                    if browser == "edge":
                        driver = webdriver.Edge(service=service, options=opts)
                    elif browser in ["chrome", "brave"]:
                        driver = webdriver.Chrome(service=service, options=opts)
                    elif browser == "opera":
                        # Opera requires special handling
                        driver = webdriver.Chrome(service=service, options=opts)
                    
                    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                    # Hide automation indicators
                    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    return driver
                except Exception as e:
                    log_error(f"{browser} driver creation failed: {e}")
                    return None

            if browser in ["firefox", "librewolf"]:
                from selenium.webdriver.firefox.service import Service as FirefoxService
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
                
                opts = FirefoxOptions()
                if binary:
                    opts.binary_location = binary
                    
                # Add arguments to prevent crashes
                opts.add_argument("--no-sandbox")
                opts.add_argument("--log-level=3")
                
                fx_profile = find_firefox_profile(browser)
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
    global PACKAGES, FORCE_BROWSER, BROWSER_CHANNEL
    
    # Interactive setup if no CLI args provided
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ['-h', '--help']):
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}")
        print("BETA-SLOT SNIPER - Interactive Setup")
        print(f"{'='*80}{Colors.RESET}")
        
        select_packages()
        if not PACKAGES:
            log_error("No packages selected. Exiting.")
            return
            
        select_browser()
        if not FORCE_BROWSER:
            log_error("No browser selected. Exiting.")
            return
    
    print_welcome()
    
    # If packages weren't selected interactively, use CLI or default
    if not PACKAGES:
        # You can set default packages here or use CLI args
        PACKAGES = [
            "com.google.android.googlequicksearchbox",
            "com.google.android.projection.gearhead",
        ]
    
    # Determine browser
    browser = FORCE_BROWSER or (sys.argv[1].lower() if len(sys.argv) > 1 else None)
    if not browser:
        browser = detect_default_browser()
        
    if not browser:
        log_warning("Could not detect default browser. Using HTTP polling fallback.")
        browser = None
    else:
        log_info(f"Using browser: {browser} ({BROWSER_CHANNEL})")

    prepared = None
    selenium_driver = None

    if browser and browser in SUPPORTED_BROWSERS:
        prepared = prepare_driver_for(browser, BROWSER_CHANNEL)
        if prepared:
            log_info(f"Prepared driver: {prepared.get('driver_path')}")
            # Kill any existing browser processes before creating driver
            kill_browser_processes(browser)
            selenium_driver = create_selenium_driver(browser, prepared, BROWSER_CHANNEL)
            if selenium_driver:
                log_success("Selenium driver created successfully.")
            else:
                log_error("Failed to create Selenium driver - will fallback to HTTP polling.")
        else:
            log_error("Could not prepare driver automatically - will fallback to HTTP polling.")
    else:
        log_warning("Unsupported or undetected browser. Using HTTP polling fallback.")

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
                            selenium_driver = create_selenium_driver(browser, prepared, BROWSER_CHANNEL)
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
            else:
                # 🆕 SUCCESS MESSAGE: All packages completed
                print(f"\n{Colors.BOLD}{Colors.GREEN}{'🎉'*20}")
                print("🎊 MISSION ACCOMPLISHED! 🎊")
                print(f"{'🎉'*20}{Colors.RESET}")
                print(f"{Colors.GREEN}All {len(PACKAGES)} packages have been successfully processed!")
                print(f"• Joined beta programs or already enrolled")
                print(f"• Monitoring completed successfully")
                print(f"Thank you for using BetaSlot-Sniper!{Colors.RESET}")
                break
                
    except KeyboardInterrupt:
        log_info("Monitoring stopped by user.")
        # 🆕 PROGRESS MESSAGE: Show what was completed when interrupted
        if remaining:
            completed_count = len(PACKAGES) - len(remaining)
            print(f"\n{Colors.YELLOW}Progress: {completed_count}/{len(PACKAGES)} packages completed")
            print(f"Remaining packages: {', '.join(sorted(remaining))}{Colors.RESET}")
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
    parser.add_argument("--browser", type=str, choices=list(SUPPORTED_BROWSERS.keys()),
                        help="Force specific browser")
    parser.add_argument("--channel", type=str, 
                        help="Browser channel (stable, beta, dev, canary, nightly, gx)")
    parser.add_argument("--packages", type=str,
                        help="Comma-separated package names to monitor")
    args = parser.parse_args()

    # Set globals according to flags
    if args.once:
        EXIT_ON_JOIN = True
        EXIT_ON_ALREADY = True
    else:
        EXIT_ON_JOIN = args.exit_on_join
        EXIT_ON_ALREADY = args.exit_on_already

    # Set browser from CLI args if provided
    if args.browser:
        FORCE_BROWSER = args.browser
    if args.channel:
        BROWSER_CHANNEL = args.channel
        
    # Set packages from CLI args if provided
    if args.packages:
        PACKAGES = [pkg.strip() for pkg in args.packages.split(',') if pkg.strip()]

    main()