import os
import subprocess
import json
import time
import requests
from urllib.parse import urlparse
from utils import log_error

# وارد کردن صحیح ماژول‌های کمکی که در همان پوشه scripts قرار دارند
from xray_config_builder import build_xray_config
from hysteria_config_builder import build_hysteria_config

# --- تنظیمات ---
XRAY_CORE_PATH = './base/xray-core'
HYSTERIA_CLIENT_PATH = './base/hysteria-client'
LATENCY_TEST_URL = 'https://www.google.com/generate_204'
TIMEOUT_SECONDS = 30 # زمان کافی برای تست

def test_single_proxy(proxy_url: str):
    """
    یک پروکسی را تست کرده و در صورت بروز هرگونه خطا، آن را با جزئیات کامل چاپ می‌کند.
    """
    print(f"\n--- Attempting to test proxy: {proxy_url[:70]}...")
    thread_id = 1 # یک شناسه ثابت برای حالت دیباگ
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

    # اطمینان از وجود پوشه output
    os.makedirs('output', exist_ok=True)
    with open(config_path, 'w') as f: json.dump(config, f, indent=2)
    print(f"Config file created successfully at {config_path}")
    print("--- Config Content ---")
    print(json.dumps(config, indent=2))
    print("----------------------")
    
    # --- مرحله ۲: اجرای هسته ---
    command = []
    proxy_address = f'socks5://127.0.0.1:{local_port}'
    
    if protocol in ['vless', 'vmess', 'trojan', 'ss']:
        command = [XRAY_CORE_PATH, "run", "-c", config_path]
    elif protocol in ['hysteria', 'hy2', 'hysteria2']:
        command = [HYSTERIA_CLIENT_PATH, "-c", config_path, "client"]
    
    print(f"Step 2: Running command: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(3) # زمان کافی برای اجرای کامل هسته
    
    # --- مرحله ۳: تست اتصال ---
    print(f"Step 3: Attempting connection via proxy: {proxy_address}")
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
            stdout, stderr = process.communicate(timeout=5)
            print(f"--- Core STDOUT ---\n{stdout if stdout else 'No output.'}")
            print(f"--- Core STDERR ---\n{stderr if stderr else 'No output.'}")
            process.terminate()
            process.wait()
        if os.path.exists(config_path):
            os.remove(config_path)
        print("Cleanup finished.")

def main():
    print("--- Starting SINGLE PROXY DEBUG RUN ---")
    # خواندن پروکسی از متغیر محیطی که در main.yml تعریف شده
    proxy_to_test = os.getenv("PROXY_TO_TEST")
    
    if proxy_to_test:
        test_single_proxy(proxy_to_test)
    else:
        print("!!!!!! ERROR: No proxy URL found in PROXY_TO_TEST environment variable. !!!!!!")

if __name__ == "__main__":
    main()
