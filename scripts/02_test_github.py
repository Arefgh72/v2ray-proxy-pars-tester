import os
import requests
import zipfile
import subprocess
import json
import time
import threading
import sys
import base64
from urllib.parse import urlparse, parse_qs, unquote
from utils import log_error

# --- تنظیمات ---
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
# ... (بقیه تنظیمات مثل قبل)
OUTPUT_ALL_FILE = 'output/github_all.txt'
OUTPUT_TOP_500_FILE = 'output/github_top_500.txt'
OUTPUT_TOP_100_FILE = 'output/github_top_100.txt'

XRAY_EXECUTABLE_PATH = './xray'
XRAY_LOCAL_PORT = 10808
TEST_URL = 'http://cp.cloudflare.com/'
TIMEOUT_SECONDS = 10
MAX_LATENCY_MS = 2000

# --- متغیرهای سراسری برای نمایش پیشرفت (فقط شمارنده‌ها) ---
total_proxies_to_test = 0
tested_proxies_count = 0
# قفل از اینجا حذف شد

# ... (توابع download_and_extract_xray و create_xray_config و test_proxy مثل قبل بدون تغییر باقی می‌مانند)
def download_and_extract_xray():
    if os.path.exists(XRAY_EXECUTABLE_PATH):
        # print("Xray executable already exists. Skipping download.")
        return True
    print("Downloading Xray-core...")
    try:
        api_url = "https://api.github.com/repos/XTLS/Xray-core/releases/latest"
        response = requests.get(api_url, timeout=20)
        response.raise_for_status()
        assets = response.json()['assets']
        download_url = None
        for asset in assets:
            if "Xray-linux-64.zip" in asset['name']:
                download_url = asset['browser_download_url']
                break
        if not download_url:
            log_error("Xray Download", "Could not find Xray-linux-64.zip in the latest release.")
            return False
        print(f"Downloading from: {download_url}")
        r = requests.get(download_url, stream=True, timeout=60)
        r.raise_for_status()
        with open("xray.zip", "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Extracting Xray...")
        with zipfile.ZipFile("xray.zip", 'r') as zip_ref:
            zip_ref.extract('xray')
        os.chmod(XRAY_EXECUTABLE_PATH, 0o755)
        os.remove("xray.zip")
        print("Xray downloaded and extracted successfully.")
        return True
    except Exception as e:
        log_error("Xray Download", "Failed to download or extract Xray.", str(e))
        return False

def create_xray_config(proxy_url: str, config_filename: str):
    try:
        parsed_url = urlparse(proxy_url)
        protocol = parsed_url.scheme
        outbound_config = {"protocol": protocol, "settings": {}, "streamSettings": {}}
        if protocol == "vmess":
            decoded_config = json.loads(base64.b64decode(parsed_url.netloc).decode('utf-8'))
            outbound_config["settings"]["vnext"] = [{"address": decoded_config.get("add"), "port": int(decoded_config.get("port")), "users": [{"id": decoded_config.get("id"), "alterId": int(decoded_config.get("aid")), "security": "auto"}]}]
            stream_settings = {"network": decoded_config.get("net", "tcp"), "security": decoded_config.get("tls", "none")}
            if stream_settings["network"] == "ws":
                stream_settings["wsSettings"] = {"path": decoded_config.get("path", "/"), "headers": {"Host": decoded_config.get("host", "")}}
            outbound_config["streamSettings"] = stream_settings
        elif protocol == "vless" or protocol == "trojan":
            password = parsed_url.username
            address = parsed_url.hostname
            port = parsed_url.port
            params = parse_qs(parsed_url.query)
            server_field = "vnext" if protocol == "vless" else "servers"
            user_field = "users" if protocol == "vless" else "password"
            user_value = [{"id": password, "flow": params.get("flow", [None])[0]}] if protocol == "vless" else password
            outbound_config["settings"][server_field] = [{"address": address, "port": port, user_field: user_value}]
            stream_settings = {"network": params.get("type", ["tcp"])[0], "security": params.get("security", ["none"])[0]}
            if stream_settings["security"] == "tls":
                stream_settings["tlsSettings"] = {"serverName": params.get("sni", [address])[0]}
            if stream_settings["network"] == "ws":
                stream_settings["wsSettings"] = {"path": params.get("path", ["/"])[0], "headers": {"Host": params.get("host", [address])[0]}}
            outbound_config["streamSettings"] = stream_settings
        elif protocol == "ss":
            user_info_raw = unquote(parsed_url.username or "")
            if '@' in parsed_url.netloc:
                decoded_user_info = base64.b64decode(user_info_raw).decode('utf-8')
            else:
                decoded_user_info = user_info_raw
            method, password = decoded_user_info.split(':', 1)
            address = parsed_url.hostname
            port = parsed_url.port
            outbound_config["settings"]["servers"] = [{"method": method, "password": password, "address": address, "port": port}]
            outbound_config["streamSettings"] = {"network": "tcp"}
        else:
            return False
        config = {"inbounds": [{"port": XRAY_LOCAL_PORT, "protocol": "http", "settings": {"allowTransparent": False}}], "outbounds": [outbound_config]}
        with open(config_filename, 'w') as f:
            json.dump(config, f)
        return True
    except Exception:
        return False

def test_proxy(proxy_url: str) -> int:
    thread_id = threading.get_ident()
    config_filename = f"temp_config_{thread_id}.json"
    if not create_xray_config(proxy_url, config_filename):
        return -1
    process = None
    try:
        process = subprocess.Popen([XRAY_EXECUTABLE_PATH, "-config", config_filename], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        start_time = time.time()
        proxies = {"http": f"http://127.0.0.1:{XRAY_LOCAL_PORT}", "https": f"http://127.0.0.1:{XRAY_LOCAL_PORT}"}
        response = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT_SECONDS)
        end_time = time.time()
        if response.status_code == 200:
            return int((end_time - start_time) * 1000)
        return -1
    except requests.exceptions.RequestException:
        return -1
    finally:
        if process:
            process.terminate()
            process.wait()
        if os.path.exists(config_filename):
            os.remove(config_filename)


# تابع worker حالا یک آرگومان جدید برای قفل می‌گیرد
def worker(proxy_queue, results_list, progress_lock):
    global tested_proxies_count, total_proxies_to_test

    while not proxy_queue.empty():
        try:
            proxy = proxy_queue.get_nowait()
            latency = test_proxy(proxy)
            if 0 < latency < MAX_LATENCY_MS:
                results_list.append({'proxy': proxy, 'latency': latency})

            with progress_lock:
                tested_proxies_count += 1
                if tested_proxies_count % 100 == 0 or (total_proxies_to_test <= 200 and tested_proxies_count % 10 == 0):
                    percentage = (tested_proxies_count / total_proxies_to_test) * 100
                    print(f"  Progress: {tested_proxies_count}/{total_proxies_to_test} ({percentage:.2f}%) tested.")
        
        except Exception:
            pass
        finally:
            proxy_queue.task_done()

def main():
    global total_proxies_to_test
    
    print("\n--- Running 02_test_github.py ---") # این اولین خروجی خواهد بود
    
    if not download_and_extract_xray():
        sys.exit(1)
    try:
        with open(RAW_PROXIES_FILE, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        total_proxies_to_test = len(proxies)
        print(f"Found {total_proxies_to_test} proxies in '{RAW_PROXIES_FILE}' to test.")
    except FileNotFoundError:
        log_error("GitHub Test", f"'{RAW_PROXIES_FILE}' not found. Run 01_fetch_proxies.py first.")
        return
    
    if total_proxies_to_test == 0:
        print("No proxies to test. Exiting.")
        return
        
    from queue import Queue
    proxy_queue = Queue()
    for p in proxies:
        proxy_queue.put(p)
    
    results = []
    threads = []
    num_threads = 50
    progress_lock = threading.Lock() # <-- قفل اینجا ایجاد می‌شود

    print(f"Starting test with {num_threads} threads...")
    for _ in range(num_threads):
        # قفل به عنوان آرگومان به تابع worker پاس داده می‌شود
        t = threading.Thread(target=worker, args=(proxy_queue, results, progress_lock))
        t.daemon = True
        t.start()
        threads.append(t)
    
    proxy_queue.join()
    
    # اطمینان از چاپ آخرین گزارش پیشرفت
    if total_proxies_to_test > 0:
        print(f"\nFinal Progress: {tested_proxies_count}/{total_proxies_to_test} (100.00%) tested.")

    print("\nTest finished.")
    print(f"Found {len(results)} working proxies.")
    if not results:
        print("No working proxies found. Exiting.")
        return
        
    sorted_results = sorted(results, key=lambda x: x['latency'])
    sorted_proxies = [item['proxy'] for item in sorted_results]
    
    print("Saving results...")
    with open(OUTPUT_ALL_FILE, 'w') as f: f.write('\n'.join(sorted_proxies))
    print(f"  -> Saved {len(sorted_proxies)} proxies to '{OUTPUT_ALL_FILE}'")
    
    top_500 = sorted_proxies[:500]
    with open(OUTPUT_TOP_500_FILE, 'w') as f: f.write('\n'.join(top_500))
    print(f"  -> Saved {len(top_500)} proxies to '{OUTPUT_TOP_500_FILE}'")
    
    top_100 = sorted_proxies[:100]
    with open(OUTPUT_TOP_100_FILE, 'w') as f: f.write('\n'.join(top_100))
    print(f"  -> Saved {len(top_100)} proxies to '{OUTPUT_TOP_100_FILE}'")
    
    print("--- Finished 02_test_github.py ---")

if __name__ == "__main__":
    main()
