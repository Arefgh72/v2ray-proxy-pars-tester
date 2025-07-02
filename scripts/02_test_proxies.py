import os
import subprocess
import json
import time
import threading
import requests
from urllib.parse import urlparse
# ما به این دو فایل نیاز داریم چون تست واقعی انجام می‌دهیم
from scripts.xray_config_builder import build_xray_config
from scripts.hysteria_config_builder import build_hysteria_config
from utils import log_error

# --- تنظیمات ---
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
# ... (بقیه مسیرهای فایل خروجی اهمیتی ندارند چون فایلی ساخته نمی‌شود)
XRAY_CORE_PATH = './base/xray-core'
HYSTERIA_CLIENT_PATH = './base/hysteria-client'
LATENCY_TEST_URL = 'https://www.google.com/generate_204'
TIMEOUT_SECONDS = 30 # زمان کافی برای تست

def test_single_proxy(proxy_url: str):
    """
    یک پروکسی را تست کرده و در صورت بروز هرگونه خطا، آن را با جزئیات کامل چاپ می‌کند.
    """
    print(f"\n--- Attempting to test proxy: {proxy_url[:70]}...")
    thread_id = threading.get_ident()
    protocol = urlparse(proxy_url).scheme
    config_path = f"output/temp_config_{thread_id}.json"
    local_port = 20000 + thread_id
    process = None
    
    # --- مرحله ۱: ساخت کانفیگ ---
    print("Step 1: Building config...")
    config = None
    if protocol in ['vless', 'vmess', 'trojan', 'ss']:
        config = build_xray_config(proxy_url, local_port)
    elif protocol in ['hysteria', 'hy2', 'hysteria2']:
        config = build_hysteria_config(proxy_url, local_port)
    
    if not config:
        print("!!!!!! CONFIG BUILDING FAILED. Parser could not understand the link. !!!!!!")
        return

    with open(config_path, 'w') as f: json.dump(config, f)
    print("Config file created successfully.")
    
    # --- مرحله ۲: اجرای هسته ---
    command = []
    if protocol in ['vless', 'vmess', 'trojan', 'ss']:
        command = [XRAY_CORE_PATH, "run", "-c", config_path]
    elif protocol in ['hysteria', 'hy2', 'hysteria2']:
        command = [HYSTERIA_CLIENT_PATH, "-c", config_path]
    
    print(f"Step 2: Running command: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(3) # زمان کافی برای اجرای کامل هسته
    
    # --- مرحله ۳: تست اتصال ---
    print("Step 3: Attempting connection via proxy...")
    proxy_address = f'socks5://127.0.0.1:{local_port}'
    proxies = {'http': proxy_address, 'https': proxy_address}
    
    try:
        start_time = time.time()
        response = requests.get(LATENCY_TEST_URL, proxies=proxies, timeout=TIMEOUT_SECONDS)
        latency = int((time.time() - start_time) * 1000)
        
        print("\n\n\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"!!!!!! UNEXPECTED SUCCESS! Latency: {latency}ms !!!!!!")
        print(f"!!!!!! Status Code: {response.status_code} !!!!!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n\n")

    except Exception as e:
        # --- بخش کلیدی: چاپ خطای دقیق ---
        print("\n\n\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!!!!! TEST FAILED! CAPTURED EXCEPTION: !!!!!!")
        print(f"!!!!!! Type: {type(e).__name__} !!!!!!")
        print(f"!!!!!! Error Message: {e} !!!!!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n\n")
        
    finally:
        # --- مرحله ۴: پاک‌سازی ---
        print("Step 4: Cleaning up...")
        if process:
            print("Terminating core process...")
            # خواندن خروجی‌های هسته برای دیباگ بیشتر
            stdout, stderr = process.communicate()
            print(f"--- Core STDOUT ---\n{stdout}")
            print(f"--- Core STDERR ---\n{stderr}")
            process.terminate()
            process.wait()
        if os.path.exists(config_path):
            os.remove(config_path)
        print("Cleanup finished.")

def main():
    print("--- Starting DEBUG RUN ---")
    try:
        with open(RAW_PROXIES_FILE, 'r') as f:
            first_proxy = f.readline().strip()
        if first_proxy:
            test_single_proxy(first_proxy)
        else:
            print("No proxy found in the input file.")
    except Exception as e:
        log_error("Debug Runner", "Failed to read or run test.", str(e))

if __name__ == "__main__":
    main()
