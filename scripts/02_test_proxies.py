import os
import subprocess
import json
import time
import threading
from urllib.parse import urlparse, parse_qs, unquote
from utils import log_error
import random

# --- تنظیمات ---
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
XRAY_PROXIES_FILE = 'output/temp_xray_proxies.txt'
HYSTERIA_PROXIES_FILE = 'output/temp_hysteria_proxies.txt'
XRAY_RESULTS_FILE = 'output/xray_results.json'
HYSTERIA_RESULTS_FILE = 'output/hysteria_results.json'

OUTPUT_ALL_FILE = 'output/github_all.txt'
OUTPUT_TOP_500_FILE = 'output/github_top_500.txt'
OUTPUT_TOP_100_FILE = 'output/github_top_100.txt'

XRAY_TESTER_PATH = './base/xray-tester'
HYSTERIA_CLIENT_PATH = './base/hysteria-client'
HYSTERIA_LOCAL_PORT = 10809 # یک پورت مجزا برای Hysteria

def categorize_proxies():
    # ... (بدون تغییر) ...
    print("Categorizing proxies..."); try:
        with open(RAW_PROXIES_FILE, 'r') as f: all_proxies = [line.strip() for line in f if line.strip()]
        xray_proxies = [p for p in all_proxies if p.startswith(('vmess://', 'vless://', 'trojan://', 'ss://'))]
        hysteria_proxies = [p for p in all_proxies if p.startswith(('hysteria://', 'hy2://'))]
        with open(XRAY_PROXIES_FILE, 'w') as f: f.write('\n'.join(xray_proxies))
        print(f"  -> Found {len(xray_proxies)} Xray-based proxies.")
        with open(HYSTERIA_PROXIES_FILE, 'w') as f: f.write('\n'.join(hysteria_proxies))
        print(f"  -> Found {len(hysteria_proxies)} Hysteria-based proxies.")
        return len(xray_proxies) > 0, len(hysteria_proxies) > 0
    except Exception as e: log_error("Categorization", "Failed to categorize proxies.", str(e)); return False, False

def test_xray_proxies():
    print("\n--- Testing Xray Proxies ---")
    try:
        command = [ XRAY_TESTER_PATH, "-f", XRAY_PROXIES_FILE, "-o", XRAY_RESULTS_FILE ]
        # اجرای ابزار v2ray-ping که ما به xray-tester تغییر نام دادیم
        # این ابزار به صورت پیش‌فرض تست سرعت و پینگ انجام می‌دهد
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=1200) # 20 دقیقه تایم‌اوت
        print("Xray test finished successfully.")
        # print(result.stdout) # برای دیباگ خروجی خود ابزار
        return True
    except subprocess.TimeoutExpired:
        log_error("Xray Test", "Xray tester timed out after 20 minutes.")
        return False
    except subprocess.CalledProcessError as e:
        # --- تغییر اصلی: چاپ خطای دقیق ---
        log_error("Xray Test", "Xray tester failed with an error.", e.stderr)
        return False
    except Exception as e:
        log_error("Xray Test", "An unexpected error occurred.", str(e))
        return False

def test_single_hysteria(proxy_url: str) -> int:
    """یک پروکسی Hysteria را تست کرده و پینگ را برمی‌گرداند."""
    config_path = f"output/temp_hy_config_{threading.get_ident()}.json"
    process = None
    try:
        # ساخت کانفیگ موقت برای Hysteria
        command = [HYSTERIA_CLIENT_PATH, "export-client-config", "--url", proxy_url, "-o", config_path]
        subprocess.run(command, check=True, capture_output=True)

        # اجرای کلاینت با کانفیگ ساخته شده
        client_command = [HYSTERIA_CLIENT_PATH, "client", "-c", config_path]
        process = subprocess.Popen(client_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2) # فرصت برای اجرا

        # تست اتصال از طریق پروکسی محلی SOCKS5
        proxies = {'http': f'socks5://127.0.0.1:1080', 'https': f'socks5://127.0.0.1:1080'}
        start_time = time.time()
        # ما در کلاینت hysteria پورت socks را روی 1080 تنظیم کرده ایم
        # این پورت پیش‌فرض خود کلاینت است
        import requests
        requests.get("https://www.google.com/generate_204", proxies=proxies, timeout=15)
        latency = int((time.time() - start_time) * 1000)
        return latency
    except Exception:
        return -1
    finally:
        if process: process.terminate(); process.wait()
        if os.path.exists(config_path): os.remove(config_path)

def hysteria_worker(proxy_queue, results_list, progress_lock):
    """تابع کارگر برای تست موازی پروکسی‌های Hysteria."""
    global tested_proxies_count, total_proxies_to_test
    while not proxy_queue.empty():
        try:
            proxy = proxy_queue.get_nowait()
            latency = test_single_hysteria(proxy)
            if latency > 0:
                results_list.append({"proxy": proxy, "latency": latency})
                print(f"  SUCCESS (Hysteria) | {latency:4d}ms | {proxy[:50]}...")
            
            with progress_lock:
                tested_proxies_count += 1
                if tested_proxies_count % 50 == 0:
                    percentage = (tested_proxies_count / (total_proxies_to_test or 1)) * 100
                    print(f"  Progress: {tested_proxies_count}/{total_proxies_to_test} ({percentage:.2f}%) tested.")
        except Exception:
            pass
        finally:
            proxy_queue.task_done()

def test_hysteria_proxies():
    print("\n--- Testing Hysteria Proxies ---")
    from queue import Queue
    proxy_queue = Queue()
    results = []
    
    try:
        with open(HYSTERIA_PROXIES_FILE, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        for p in proxies:
            proxy_queue.put(p)
            
        threads = []
        num_threads = 15 # تست هیستریا سنگین‌تر است، تعداد تردها کمتر باشد
        progress_lock = threading.Lock()
        
        for _ in range(num_threads):
            t = threading.Thread(target=hysteria_worker, args=(proxy_queue, results, progress_lock))
            t.daemon = True
            t.start()
            threads.append(t)
            
        proxy_queue.join()

        with open(HYSTERIA_RESULTS_FILE, 'w') as f:
            json.dump(results, f)
        print("Hysteria test finished.")
        return True
    except Exception as e:
        log_error("Hysteria Test", "An unexpected error occurred.", str(e))
        return False

def combine_and_save_results():
    # ... (این تابع تقریباً بدون تغییر است) ...
    print("\n--- Combining and Saving Results ---"); all_results = []
    try:
        if os.path.exists(XRAY_RESULTS_FILE):
            with open(XRAY_RESULTS_FILE, 'r') as f:
                xray_data = json.load(f)
            for item in xray_data:
                if isinstance(item, dict) and item.get("delay") and item["delay"] > 0:
                    all_results.append({"proxy": item["config"], "latency": item["delay"]})
    except Exception as e: log_error("Result Combination", "Failed to parse Xray results.", str(e))
    try:
        if os.path.exists(HYSTERIA_RESULTS_FILE):
            with open(HYSTERIA_RESULTS_FILE, 'r') as f:
                all_results.extend(json.load(f))
    except Exception as e: log_error("Result Combination", "Failed to parse Hysteria results.", str(e))
    print(f"Total {len(all_results)} working proxies found from all testers.")
    if not all_results:
        print("No working proxies found. Saving empty files."); open(OUTPUT_ALL_FILE, 'w').close(); open(OUTPUT_TOP_500_FILE, 'w').close(); open(OUTPUT_TOP_100_FILE, 'w').close()
        return
    sorted_results = sorted(all_results, key=lambda x: x['latency']); sorted_proxies = [item['proxy'] for item in sorted_results]
    print("Saving final sorted lists...");
    with open(OUTPUT_ALL_FILE, 'w') as f: f.write('\n'.join(sorted_proxies)); print(f"  -> Saved {len(sorted_proxies)} to '{OUTPUT_ALL_FILE}'")
    top_500 = sorted_proxies[:500];
    with open(OUTPUT_TOP_500_FILE, 'w') as f: f.write('\n'.join(top_500)); print(f"  -> Saved {len(top_500)} to '{OUTPUT_TOP_500_FILE}'")
    top_100 = sorted_proxies[:100];
    with open(OUTPUT_TOP_100_FILE, 'w') as f: f.write('\n'.join(top_100)); print(f"  -> Saved {len(top_100)} to '{OUTPUT_TOP_100_FILE}'")

def main():
    global total_proxies_to_test
    xray_exists, hysteria_exists = categorize_proxies()
    # تعداد کل پروکسی‌ها برای نمایش درصد پیشرفت
    with open(RAW_PROXIES_FILE, 'r') as f:
        total_proxies_to_test = len(f.readlines())

    if xray_exists: test_xray_proxies()
    else: print("No Xray-based proxies to test.")
    if hysteria_exists: test_hysteria_proxies()
    else: print("No Hysteria-based proxies to test.")
    combine_and_save_results()
    print("\n--- All tasks finished ---")

if __name__ == "__main__":
    main()
