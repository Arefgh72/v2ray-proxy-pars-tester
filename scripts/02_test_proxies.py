import os
import subprocess
import json
import time
import threading
import requests
from urllib.parse import urlparse
from utils import log_error

# --- تنظیمات ---
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
XRAY_PROXIES_FILE = 'output/temp_xray_proxies.txt'
HYSTERIA_PROXIES_FILE = 'output/temp_hysteria_proxies.txt'

OUTPUT_ALL_FILE = 'output/github_all.txt'
OUTPUT_TOP_500_FILE = 'output/github_top_500.txt'
OUTPUT_TOP_100_FILE = 'output/github_top_100.txt'

# مسیر ابزارهای رسمی در پوشه base
XRAY_CORE_PATH = './base/xray-core'
HYSTERIA_CLIENT_PATH = './base/hysteria-client'

# تنظیمات تست
LATENCY_TEST_URL = 'https://www.google.com/generate_204'
TIMEOUT_SECONDS = 15
MAX_LATENCY_MS = 3500

# متغیرهای سراسری برای نمایش پیشرفت
tested_proxies_count = 0
total_proxies_to_test = 0
progress_lock = threading.Lock()

def categorize_proxies():
    """پروکسی‌های خام را به دو دسته Xray و Hysteria تقسیم می‌کند."""
    print("Categorizing proxies...")
    try:
        with open(RAW_PROXIES_FILE, 'r') as f:
            all_proxies = [line.strip() for line in f if line.strip()]

        global total_proxies_to_test
        total_proxies_to_test = len(all_proxies)

        xray_proxies = [p for p in all_proxies if p.startswith(('vmess://', 'vless://', 'trojan://', 'ss://'))]
        hysteria_proxies = [p for p in all_proxies if p.startswith('hy2://') or p.startswith('hysteria2://')]

        with open(XRAY_PROXIES_FILE, 'w') as f: f.write('\n'.join(xray_proxies))
        print(f"  -> Found {len(xray_proxies)} Xray-based proxies.")

        with open(HYSTERIA_PROXIES_FILE, 'w') as f: f.write('\n'.join(hysteria_proxies))
        print(f"  -> Found {len(hysteria_proxies)} Hysteria 2 proxies.")
        
        return len(xray_proxies) > 0, len(hysteria_proxies) > 0
    except Exception as e:
        log_error("Categorization", "Failed to categorize proxies.", str(e))
        return False, False

def test_single_proxy(proxy_url: str) -> int:
    """یک پروکسی تکی (Xray یا Hysteria) را با ساخت کانفیگ موقت تست می‌کند."""
    thread_id = threading.get_ident()
    protocol = urlparse(proxy_url).scheme
    
    if protocol in ['hysteria', 'hy2']:
        config_path = f"output/temp_hy_config_{thread_id}.json"
        client_path = HYSTERIA_CLIENT_PATH
        local_port = 10809 + thread_id
        # کلاینت Hysteria خودش از روی URL کانفیگ می‌سازد و اجرا می‌کند
        command = [client_path, "-c", proxy_url, "socks5", "--listen", f"127.0.0.1:{local_port}"]
    elif protocol in ['vmess', 'vless', 'trojan', 'ss']:
        from scripts.xray_config_builder import build_xray_config # ایمپورت تابع کمکی
        config_path = f"output/temp_xray_config_{thread_id}.json"
        client_path = XRAY_CORE_PATH
        local_port = 20809 + thread_id
        
        xray_config = build_xray_config(proxy_url, local_port)
        if not xray_config:
            return -1 # اگر ساخت کانفیگ شکست خورد
        
        with open(config_path, 'w') as f: json.dump(xray_config, f)
        command = [client_path, "run", "-c", config_path]
    else:
        return -1

    process = None
    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        
        proxies = {'http': f'socks5://127.0.0.1:{local_port}', 'https': f'socks5://127.0.0.1:{local_port}'}
        start_time = time.time()
        response = requests.get(LATENCY_TEST_URL, proxies=proxies, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        latency = int((time.time() - start_time) * 1000)
        return latency
    except Exception:
        return -1
    finally:
        if process: process.terminate(); process.wait()
        if os.path.exists(config_path): os.remove(config_path)

def worker(proxy_queue, results_list):
    """تابع کارگر که پروکسی‌ها را از صف برداشته و تست می‌کند."""
    global tested_proxies_count, total_proxies_to_test, progress_lock
    while not proxy_queue.empty():
        try:
            proxy = proxy_queue.get_nowait()
            latency = test_single_proxy(proxy)
            
            if 0 < latency < MAX_LATENCY_MS:
                results_list.append({"proxy": proxy, "latency": latency})
                print(f"  SUCCESS | {latency:4d}ms | {proxy[:55]}...")

            with progress_lock:
                tested_proxies_count += 1
                if tested_proxies_count % 100 == 0:
                    percentage = (tested_proxies_count / total_proxies_to_test) * 100
                    print(f"  Progress: {tested_proxies_count}/{total_proxies_to_test} ({percentage:.2f}%) tested.")
        except Exception:
            pass # از کرش کردن ترد جلوگیری می‌کند
        finally:
            proxy_queue.task_done()

def run_tests():
    """تست تمام پروکسی‌ها را به صورت موازی مدیریت می‌کند."""
    print("\n--- Starting All Proxy Tests ---")
    try:
        with open(RAW_PROXIES_FILE, 'r') as f:
            all_proxies = [line.strip() for line in f if line.strip()]
        
        if not all_proxies:
            print("No proxies to test.")
            return []

        from queue import Queue
        proxy_queue = Queue()
        for p in all_proxies:
            proxy_queue.put(p)

        results = []
        threads = []
        num_threads = 40 # تعداد تردها
        
        print(f"Starting test with {num_threads} threads...")
        for _ in range(num_threads):
            t = threading.Thread(target=worker, args=(proxy_queue, results))
            t.daemon = True
            t.start()
            threads.append(t)
            
        proxy_queue.join() # منتظر می‌مانیم تا تمام آیتم‌های صف پردازش شوند
        return results

    except Exception as e:
        log_error("Test Runner", "An unexpected error occurred during testing.", str(e))
        return []

def combine_and_save_results(all_results):
    """نتایج را مرتب و ذخیره می‌کند."""
    print("\n--- Combining and Saving Results ---")
    print(f"Total {len(all_results)} working proxies found from all testers.")
    
    if not all_results:
        for path in [OUTPUT_ALL_FILE, OUTPUT_TOP_500_FILE, OUTPUT_TOP_100_FILE]:
            open(path, 'w').close()
        print("No working proxies found. Saved empty files.")
        return

    sorted_results = sorted(all_results, key=lambda x: x['latency'])
    sorted_proxies = [item['proxy'] for item in sorted_results]

    print("Saving final sorted lists...")
    with open(OUTPUT_ALL_FILE, 'w') as f: f.write('\n'.join(sorted_proxies))
    print(f"  -> Saved {len(sorted_proxies)} to '{OUTPUT_ALL_FILE}'")
    
    top_500 = sorted_proxies[:500]
    with open(OUTPUT_TOP_500_FILE, 'w') as f: f.write('\n'.join(top_500))
    print(f"  -> Saved {len(top_500)} to '{OUTPUT_TOP_500_FILE}'")
    
    top_100 = sorted_proxies[:100]
    with open(OUTPUT_TOP_100_FILE, 'w') as f: f.write('\n'.join(top_100))
    print(f"  -> Saved {len(top_100)} to '{OUTPUT_TOP_100_FILE}'")

def main():
    # ما دیگر نیازی به دسته‌بندی نداریم. همه را با هم تست می‌کنیم.
    # این کار باعث می‌شود که کد بسیار ساده‌تر شود.
    # ما فقط به یک فایل کمکی برای ساخت کانفیگ Xray نیاز داریم.
    
    # برای این کار، ما باید یک فایل جدید بسازیم
    # scripts/xray_config_builder.py
    # و تابع `parse_proxy_link_to_xray_outbound` را به آن منتقل کنیم
    # و نام آن را به build_xray_config تغییر دهیم.
    
    # من این کار را در کد بالا انجام داده‌ام.
    
    # پس شما به یک فایل جدید دیگر هم نیاز دارید.
    
    # فایل: scripts/xray_config_builder.py
    # محتوا:
    # import base64
    # from urllib.parse import urlparse, parse_qs, unquote
    # import json
    #
    # def build_xray_config(proxy_url: str, local_port: int):
    #     # ... تمام منطق پارسر هوشمند ما اینجا قرار می‌گیرد ...
    #     # و در نهایت یک دیکشنری کانفیگ Xray را برمی‌گرداند
    
    # این کار کد را ماژولار و تمیز نگه می‌دارد.
    
    # اجرای تست‌ها
    final_results = run_tests()
    
    # ذخیره نتایج
    combine_and_save_results(final_results)
    
    print("\n--- All tasks finished ---")


if __name__ == "__main__":
    main()
