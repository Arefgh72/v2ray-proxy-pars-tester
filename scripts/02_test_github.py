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
OUTPUT_ALL_FILE = 'output/github_all.txt'
OUTPUT_TOP_500_FILE = 'output/github_top_500.txt'
OUTPUT_TOP_100_FILE = 'output/github_top_100.txt'

XRAY_EXECUTABLE_PATH = './xray'
XRAY_LOCAL_PORT = 10808
TEST_URL = 'http://cp.cloudflare.com/'
TIMEOUT_SECONDS = 25
MAX_LATENCY_MS = 3000

total_proxies_to_test = 0
tested_proxies_count = 0
# progress_lock در تابع main ایجاد خواهد شد

def download_and_extract_xray():
    """
    آخرین نسخه Xray-core برای لینوکس 64 بیتی را از گیت‌هاب دانلود و استخراج می‌کند.
    این نسخه کامل و صحیح است.
    """
    if os.path.exists(XRAY_EXECUTABLE_PATH):
        return True
    
    print("Downloading Xray-core...")
    try:
        api_url = "https://api.github.com/repos/XTLS/Xray-core/releases/latest"
        response = requests.get(api_url, timeout=20)
        response.raise_for_status()
        assets = response.json()['assets']
        
        download_url = next((asset['browser_download_url'] for asset in assets if "Xray-linux-64.zip" in asset['name']), None)
        
        if not download_url:
            log_error("Xray Download", "Could not find Xray-linux-64.zip in the latest GitHub release.")
            return False
            
        print(f"Downloading from: {download_url}")
        with requests.get(download_url, stream=True, timeout=60) as r:
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
        return True # <-- این خط در نسخه قبلی فراموش شده بود

    except Exception as e:
        log_error("Xray Download", "An error occurred during download or extraction.", str(e))
        return False

def parse_proxy_link_to_xray_outbound(proxy_url: str):
    # ... (این تابع بدون تغییر باقی می‌ماند) ...
    try:
        parsed_url = urlparse(proxy_url)
        protocol = parsed_url.scheme
        params = parse_qs(parsed_url.query)
        network = params.get("type", [None])[0] or params.get("net", ["tcp"])[0]
        security = params.get("security", ["none"])[0]
        address = parsed_url.hostname
        port = parsed_url.port
        uuid_or_pass = unquote(parsed_url.username or "")
        stream_settings = {"network": network, "security": security}
        if security == 'tls':
            sni = params.get('sni', [None])[0] or params.get('host', [address])[0]
            alpn = params.get('alpn', [None])[0]
            tls_settings = {"serverName": sni}
            if alpn: tls_settings["alpn"] = alpn.split(',')
            stream_settings['tlsSettings'] = tls_settings
        if network == 'ws':
            host = params.get('host', [sni if security == 'tls' else address])[0]
            path = params.get('path', ['/'])[0]
            stream_settings['wsSettings'] = {"path": path, "headers": {"Host": host}}
        elif network == 'grpc':
            service_name = params.get('serviceName', [''])[0]
            stream_settings['grpcSettings'] = {"serviceName": service_name, "multiMode": (params.get("mode", ["gun"])[0] == "multi")}
        outbound_settings = {}
        if protocol == "vless":
            outbound_settings = {"vnext": [{"address": address, "port": port, "users": [{"id": uuid_or_pass, "flow": params.get("flow", [None])[0]}]}]}
        elif protocol == "vmess":
            vmess_json = json.loads(base64.b64decode(parsed_url.netloc).decode('utf-8'))
            outbound_settings = {"vnext": [{"address": vmess_json.get("add", address), "port": int(vmess_json.get("port", port)), "users": [{"id": vmess_json.get("id", uuid_or_pass), "alterId": int(vmess_json.get("aid", 0)), "security": vmess_json.get("scy", "auto")}]}]}
        elif protocol == "trojan":
            outbound_settings = {"servers": [{"address": address, "port": port, "password": uuid_or_pass}]}
        elif protocol == "ss":
            if '@' in parsed_url.netloc:
                decoded_user_info = base64.b64decode(unquote(parsed_url.netloc.split('@')[0])).decode('utf-8')
            else:
                decoded_user_info = uuid_or_pass
            method, password = decoded_user_info.split(':', 1)
            outbound_settings = {"servers": [{"method": method, "password": password, "address": address, "port": port}]}
        else:
            return None
        return {"protocol": protocol, "settings": outbound_settings, "streamSettings": stream_settings}
    except Exception as e:
        log_error("Smart Parser", f"Failed for proxy: {proxy_url[:60]}...", str(e))
        return None

def test_proxy(proxy_url: str) -> tuple[int, str]:
    # ... (این تابع بدون تغییر باقی می‌ماند) ...
    thread_id = threading.get_ident()
    config_filename = f"temp_config_{thread_id}.json"
    outbound_config = parse_proxy_link_to_xray_outbound(proxy_url)
    if not outbound_config:
        return -1, "CONFIG_FAILED"
    xray_config = {"inbounds": [{"port": XRAY_LOCAL_PORT, "protocol": "http"}], "outbounds": [outbound_config]}
    with open(config_filename, 'w') as f: json.dump(xray_config, f)
    process = None
    try:
        process = subprocess.Popen([XRAY_EXECUTABLE_PATH, "-config", config_filename], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        start_time = time.time()
        proxies = {"http": f"http://127.0.0.1:{XRAY_LOCAL_PORT}", "https": f"http://127.0.0.1:{XRAY_LOCAL_PORT}"}
        response = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT_SECONDS)
        end_time = time.time()
        if response.status_code == 200:
            return int((end_time - start_time) * 1000), "SUCCESS"
        else:
            return -1, f"HTTP_{response.status_code}"
    except requests.exceptions.Timeout:
        return -1, "TIMEOUT"
    except requests.exceptions.RequestException:
        return -1, "CONN_ERROR"
    finally:
        if process: process.terminate(); process.wait()
        if os.path.exists(config_filename): os.remove(config_filename)

def worker(proxy_queue, results_list, progress_lock):
    # ... (این تابع بدون تغییر باقی می‌ماند) ...
    global tested_proxies_count, total_proxies_to_test
    while not proxy_queue.empty():
        try:
            proxy = proxy_queue.get_nowait()
            latency, status = test_proxy(proxy)
            if status == "SUCCESS" and latency < MAX_LATENCY_MS:
                results_list.append({'proxy': proxy, 'latency': latency})
                print(f"  SUCCESS | {latency:4d}ms | {proxy[:60]}...")
            with progress_lock:
                tested_proxies_count += 1
                if tested_proxies_count % 100 == 0:
                    percentage = (tested_proxies_count / total_proxies_to_test) * 100
                    print(f"  Progress: {tested_proxies_count}/{total_proxies_to_test} ({percentage:.2f}%) tested.")
        except Exception:
            pass
        finally:
            proxy_queue.task_done()

def main():
    # ... (این تابع بدون تغییر باقی می‌ماند) ...
    global total_proxies_to_test
    print("\n--- Running 02_test_github.py (Hiddify-style Smart Parser) ---")
    if not download_and_extract_xray():
        sys.exit(1)
    try:
        with open(RAW_PROXIES_FILE, 'r') as f: proxies = [line.strip() for line in f if line.strip()]
        total_proxies_to_test = len(proxies)
        print(f"Found {total_proxies_to_test} proxies to test.")
    except FileNotFoundError:
        log_error("GitHub Test", f"'{RAW_PROXIES_FILE}' not found.")
        return
    if total_proxies_to_test == 0:
        print("No proxies to test.")
        return
    from queue import Queue
    proxy_queue = Queue()
    for p in proxies: proxy_queue.put(p)
    results = []
    threads = []
    num_threads = 50
    progress_lock = threading.Lock()
    print(f"Starting test with {num_threads} threads...")
    for _ in range(num_threads):
        t = threading.Thread(target=worker, args=(proxy_queue, results, progress_lock))
        t.daemon = True
        t.start()
        threads.append(t)
    proxy_queue.join()
    if total_proxies_to_test > 0:
        print(f"\nFinal Progress: 100.00% tested.")
    print(f"\nTest finished. Found {len(results)} working proxies.")
    if not results:
        print("No working proxies found.")
    sorted_results = sorted(results, key=lambda x: x['latency'])
    sorted_proxies = [item['proxy'] for item in sorted_results]
    print("Saving results...")
    with open(OUTPUT_ALL_FILE, 'w') as f: f.write('\n'.join(sorted_proxies))
    print(f"  -> Saved {len(sorted_proxies)} to '{OUTPUT_ALL_FILE}'")
    top_500 = sorted_proxies[:500]
    with open(OUTPUT_TOP_500_FILE, 'w') as f: f.write('\n'.join(top_500))
    print(f"  -> Saved {len(top_500)} to '{OUTPUT_TOP_500_FILE}'")
    top_100 = sorted_proxies[:100]
    with open(OUTPUT_TOP_100_FILE, 'w') as f: f.write('\n'.join(top_100))
    print(f"  -> Saved {len(top_100)} to '{OUTPUT_TOP_100_FILE}'")
    print("--- Finished 02_test_github.py ---")

if __name__ == "__main__":
    main()
