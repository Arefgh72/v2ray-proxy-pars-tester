import os
import subprocess
import json
import time
# --- تغییر اصلی: استفاده از curl_cffi ---
from curl_cffi.requests import Session
from urllib.parse import urlparse
from scripts.xray_config_builder import build_xray_config
from scripts.hysteria_config_builder import build_hysteria_config
from utils import log_error

# ... (تنظیمات مثل قبل) ...
XRAY_CORE_PATH = './base/xray-core'
HYSTERIA_CLIENT_PATH = './base/hysteria-client'
LATENCY_TEST_URL = 'https://www.google.com/generate_204'
TIMEOUT_SECONDS = 30

def test_single_proxy(proxy_url: str):
    print(f"\n--- Attempting to test proxy: {proxy_url[:70]}...")
    thread_id = 1
    protocol = urlparse(proxy_url).scheme
    config_path = f"output/temp_config_{thread_id}.json"
    local_port = 20000 + thread_id
    process = None
    
    print("Step 1: Building config...")
    config = None
    if protocol in ['vless', 'vmess', 'trojan', 'ss']:
        config = build_xray_config(proxy_url, local_port)
    elif protocol in ['hysteria', 'hy2', 'hysteria2']:
        config = build_hysteria_config(proxy_url, local_port)
    
    if not config:
        print("!!!!!! CONFIG BUILDING FAILED. !!!!!!")
        return

    os.makedirs('output', exist_ok=True)
    with open(config_path, 'w') as f: json.dump(config, f)
    print(f"Config file created successfully.")
    
    command = []
    if protocol in ['vless', 'vmess', 'trojan', 'ss']:
        command = [XRAY_CORE_PATH, "run", "-c", config_path]
    elif protocol in ['hysteria', 'hy2', 'hysteria2']:
        command = [HYSTERIA_CLIENT_PATH, "-c", config_path]
    
    print(f"Step 2: Running command: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(3)
    
    print("Step 3: Attempting connection via proxy...")
    proxy_address = f'socks5://127.0.0.1:{local_port}'
    
    try:
        # --- تغییر اصلی: استفاده از Session و impersonate ---
        session = Session(proxies={'http': proxy_address, 'https': proxy_address})
        start_time = time.time()
        response = session.get(LATENCY_TEST_URL, timeout=TIMEOUT_SECONDS, impersonate="chrome110")
        latency = int((time.time() - start_time) * 1000)
        
        print("\n\n\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"!!!!!! HOLY ****, IT WORKED! Latency: {latency}ms !!!!!!")
        print(f"!!!!!! Status Code: {response.status_code} !!!!!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n\n")

    except Exception as e:
        print("\n\n\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!!!!! TEST FAILED AGAIN! CAPTURED EXCEPTION: !!!!!!")
        print(f"!!!!!! Type: {type(e).__name__} !!!!!!")
        print(f"!!!!!! Error Message: {e} !!!!!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n\n")
        
    finally:
        print("Step 4: Cleaning up...")
        if process:
            print("Terminating core process...")
            stdout, stderr = process.communicate(timeout=5)
            print(f"--- Core STDOUT ---\n{stdout if stdout else 'No output.'}")
            print(f"--- Core STDERR ---\n{stderr if stderr else 'No output.'}")
        if os.path.exists(config_path):
            os.remove(config_path)
        print("Cleanup finished.")

def main():
    print("--- Starting FINAL DEBUG RUN ---")
    proxy_to_test = os.getenv("PROXY_TO_TEST")
    if proxy_to_test:
        test_single_proxy(proxy_to_test)
    else:
        print("!!!!!! ERROR: No proxy URL found in PROXY_TO_TEST. !!!!!!")

if __name__ == "__main__":
    main()
