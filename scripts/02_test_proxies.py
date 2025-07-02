import os
import subprocess
import json
import time
import threading
import requests
from urllib.parse import urlparse
from utils import log_error

# --- تغییر اصلی اینجاست ---
from xray_config_builder import build_xray_config
from hysteria_config_builder import build_hysteria_config

# --- تنظیمات ---
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
# ... (بقیه تنظیمات بدون تغییر)
OUTPUT_ALL_FILE = 'output/github_all.txt'
OUTPUT_TOP_500_FILE = 'output/github_top_500.txt'
OUTPUT_TOP_100_FILE = 'output/github_top_100.txt'

XRAY_CORE_PATH = './base/xray-core'
HYSTERIA_CLIENT_PATH = './base/hysteria-client'

LATENCY_TEST_URL = 'https://www.google.com/generate_204'
TIMEOUT_SECONDS = 20
MAX_LATENCY_MS = 5000 # افزایش آستانه برای تست‌های واقعی‌تر

tested_proxies_count = 0
total_proxies_to_test = 0
progress_lock = threading.Lock()

def test_single_proxy(proxy_url: str) -> int:
    thread_id = threading.get_ident()
    protocol = urlparse(proxy_url).scheme
    
    config_path = f"output/temp_config_{thread_id}.json"
    local_port = 20000 + thread_id
    process = None
    
    try:
        if protocol in ['hysteria', 'hy2', 'hysteria2']:
            hy_config = build_hysteria_config(proxy_url, local_port)
            if not hy_config: return -1
            with open(config_path, 'w') as f: json.dump(hy_config, f)
            command = [HYSTERIA_CLIENT_PATH, "-c", config_path] # حالت کلاینت پیش‌فرض است
            proxy_address = f'socks5://127.0.0.1:{local_port}'
        
        elif protocol in ['vmess', 'vless', 'trojan', 'ss']:
            xray_config = build_xray_config(proxy_url, local_port)
            if not xray_config: return -1
            with open(config_path, 'w') as f: json.dump(xray_config, f)
            command = [XRAY_CORE_PATH, "run", "-c", config_path]
            proxy_address = f'socks5://127.0.0.1:{local_port}' # هر دو هسته از socks5 پشتیبانی می‌کنند
        
        else:
            return -1

        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.5)
        
        proxies = {'http': proxy_address, 'https': proxy_address}
        start_time = time.time()
        response = requests.get(LATENCY_TEST_URL, proxies=proxies, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        latency = int((time.time() - start_time) * 1000)
        
        return latency if 0 < latency < MAX_LATENCY_MS else -1

    except Exception:
        return -1
    finally:
        if process: process.terminate(); process.wait()
        if os.path.exists(config_path): os.remove(config_path)

def worker(proxy_queue, results_list):
    # ... (بدون تغییر) ...
    global tested_proxies_count, total_proxies_to_test, progress_lock
    while not proxy_queue.empty():
        try:
            proxy = proxy_queue.get_nowait()
            latency = test_single_proxy(proxy)
            if latency > 0:
                results_list.append({"proxy": proxy, "latency": latency})
                print(f"  SUCCESS | {latency:4d}ms | {proxy[:55]}...")
        except Exception:
            pass
        finally:
            with progress_lock:
                tested_proxies_count += 1
                if tested_proxies_count % 100 == 0:
                    percentage = (tested_proxies_count / (total_proxies_to_test or 1)) * 100
                    print(f"  Progress: {tested_proxies_count}/{total_proxies_to_test} ({percentage:.2f}%) tested.")
            proxy_queue.task_done()

def run_tests():
    # ... (بدون تغییر) ...
    print("\n--- Starting All Proxy Tests ---")
    try:
        with open(RAW_PROXIES_FILE, 'r') as f: all_proxies = [line.strip() for line in f if line.strip()]
        global total_proxies_to_test; total_proxies_to_test = len(all_proxies)
        if not all_proxies: print("No proxies to test."); return []
        from queue import Queue
        proxy_queue = Queue()
        for p in all_proxies: proxy_queue.put(p)
        results = []; threads = []
        num_threads = 40
        print(f"Starting test with {num_threads} threads...")
        for _ in range(num_threads):
            t = threading.Thread(target=worker, args=(proxy_queue, results)); t.daemon = True; t.start(); threads.append(t)
        proxy_queue.join()
        return results
    except Exception as e:
        log_error("Test Runner", "An error occurred during testing.", str(e))
        return []

def combine_and_save_results(all_results):
    # ... (بدون تغییر) ...
    print(f"\n--- Combining and Saving Results ---\nTotal {len(all_results)} working proxies found.")
    if not all_results:
        for path in [OUTPUT_ALL_FILE, OUTPUT_TOP_500_FILE, OUTPUT_TOP_100_FILE]: open(path, 'w').close()
        print("No working proxies found. Saved empty files."); return
    sorted_results = sorted(all_results, key=lambda x: x['latency']); sorted_proxies = [item['proxy'] for item in sorted_results]
    print("Saving final sorted lists...")
    with open(OUTPUT_ALL_FILE, 'w') as f: f.write('\n'.join(sorted_proxies)); print(f"  -> Saved {len(sorted_proxies)} to '{OUTPUT_ALL_FILE}'")
    top_500 = sorted_proxies[:500];
    with open(OUTPUT_TOP_500_FILE, 'w') as f: f.write('\n'.join(top_500)); print(f"  -> Saved {len(top_500)} to '{OUTPUT_TOP_500_FILE}'")
    top_100 = sorted_proxies[:100];
    with open(OUTPUT_TOP_100_FILE, 'w') as f: f.write('\n'.join(top_100)); print(f"  -> Saved {len(top_100)} to '{OUTPUT_TOP_100_FILE}'")

def main():
    # دیگر نیازی به دسته‌بندی نداریم، همه را با هم تست می‌کنیم
    final_results = run_tests()
    combine_and_save_results(final_results)
    print("\n--- All tasks finished ---")

if __name__ == "__main__":
    main()
