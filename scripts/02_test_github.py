import os
import requests
import zipfile
import subprocess
import json
import time
import threading
import sys
from utils import log_error

# --- تنظیمات ---
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
OUTPUT_ALL_FILE = 'output/github_all.txt'
OUTPUT_TOP_500_FILE = 'output/github_top_500.txt'
OUTPUT_TOP_100_FILE = 'output/github_top_100.txt'

XRAY_EXECUTABLE_PATH = './xray'
XRAY_CONFIG_FILE = 'temp_config.json'
XRAY_LOCAL_PORT = 10808  # پورت محلی برای Xray
TEST_URL = 'https://speed.cloudflare.com/'  # یک URL سبک برای تست اتصال و پینگ
TIMEOUT_SECONDS = 10  # حداکثر زمان انتظار برای تست هر پروکسی
MAX_LATENCY_MS = 2000  # حداکثر پینگ قابل قبول (میلی‌ثانیه)

# --- توابع ---

def download_and_extract_xray():
    """
    آخرین نسخه Xray-core برای لینوکس 64 بیتی را از گیت‌هاب دانلود و استخراج می‌کند.
    """
    if os.path.exists(XRAY_EXECUTABLE_PATH):
        print("Xray executable already exists. Skipping download.")
        return True

    print("Downloading Xray-core...")
    # دریافت اطلاعات آخرین نسخه از API گیت‌هاب
    try:
        api_url = "https://api.github.com/repos/XTLS/Xray-core/releases/latest"
        response = requests.get(api_url, timeout=20)
        response.raise_for_status()
        assets = response.json()['assets']
        
        # پیدا کردن فایل zip برای لینوکس 64 بیتی
        download_url = None
        for asset in assets:
            if "Xray-linux-64.zip" in asset['name']:
                download_url = asset['browser_download_url']
                break
        
        if not download_url:
            log_error("Xray Download", "Could not find Xray-linux-64.zip in the latest release.")
            return False

        # دانلود فایل
        print(f"Downloading from: {download_url}")
        r = requests.get(download_url, stream=True, timeout=60)
        r.raise_for_status()
        with open("xray.zip", "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        # استخراج فایل zip
        print("Extracting Xray...")
        with zipfile.ZipFile("xray.zip", 'r') as zip_ref:
            zip_ref.extract('xray') # فقط فایل اجرایی xray را استخراج می‌کنیم
        
        os.chmod(XRAY_EXECUTABLE_PATH, 0o755)  # دادن دسترسی اجرایی
        os.remove("xray.zip")
        print("Xray downloaded and extracted successfully.")
        return True

    except Exception as e:
        log_error("Xray Download", "Failed to download or extract Xray.", str(e))
        return False

def create_xray_config(proxy_url: str):
    """
    یک فایل کانفیگ موقت برای Xray با پروکسی داده شده ایجاد می‌کند.
    """
    # این تابع باید بر اساس نوع پروکسی (vmess, vless, ...) کانفیگ مناسب را بسازد.
    # برای سادگی، فعلاً فقط vmess را پیاده‌سازی می‌کنیم.
    # TODO: پشتیبانی از پروتکل‌های دیگر (vless, trojan) را اضافه کنید.
    
    if "vmess://" in proxy_url:
        try:
            # یک پارسر ساده برای vmess (نیاز به بهبود دارد)
            # این بخش بسیار ساده شده و ممکن است برای همه لینک‌های vmess کار نکند.
            # برای پروژه‌های جدی‌تر، استفاده از یک کتابخانه پارسر vmess توصیه می‌شود.
            config_str = proxy_url.replace("vmess://", "")
            decoded_config = json.loads(base64.b64decode(config_str).decode('utf-8'))
            
            config = {
                "inbounds": [
                    {
                        "port": XRAY_LOCAL_PORT,
                        "protocol": "http",
                        "settings": {"allowTransparent": False}
                    }
                ],
                "outbounds": [
                    {
                        "protocol": "vmess",
                        "settings": {
                            "vnext": [
                                {
                                    "address": decoded_config.get("add"),
                                    "port": int(decoded_config.get("port", 443)),
                                    "users": [
                                        {
                                            "id": decoded_config.get("id"),
                                            "alterId": int(decoded_config.get("aid", 0)),
                                            "security": "auto"
                                        }
                                    ]
                                }
                            ]
                        },
                        "streamSettings": {
                            "network": decoded_config.get("net", "tcp"),
                            "security": decoded_config.get("tls", "none"),
                            "wsSettings": {
                                "path": decoded_config.get("path", "/")
                            } if decoded_config.get("net") == "ws" else None
                        }
                    }
                ]
            }

            with open(XRAY_CONFIG_FILE, 'w') as f:
                json.dump(config, f)
            return True
        except Exception as e:
            # log_error("Config Creation", f"Failed to parse or create config for proxy: {proxy_url[:30]}", str(e))
            return False # لاگ کردن این خطاها خروجی را شلوغ می‌کند، پس فعلاً غیرفعال است
    
    # اگر پروتکل پشتیبانی نشود
    return False


def test_proxy(proxy_url: str) -> int:
    """
    یک پروکسی را با استفاده از Xray تست می‌کند و پینگ آن را برمی‌گرداند.
    در صورت شکست، -1 برمی‌گرداند.
    """
    if not create_xray_config(proxy_url):
        return -1

    process = None
    try:
        # اجرای Xray در یک پروسه جداگانه
        process = subprocess.Popen([XRAY_EXECUTABLE_PATH, "-config", XRAY_CONFIG_FILE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1) # به Xray فرصت می‌دهیم تا کامل اجرا شود

        start_time = time.time()
        proxies = {
            "http": f"http://127.0.0.1:{XRAY_LOCAL_PORT}",
            "https": f"http://127.0.0.1:{XRAY_LOCAL_PORT}"
        }
        response = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT_SECONDS)
        end_time = time.time()
        
        if response.status_code == 200:
            latency = int((end_time - start_time) * 1000)
            return latency
        return -1

    except requests.exceptions.RequestException:
        return -1
    finally:
        if process:
            process.terminate()
            process.wait() # منتظر می‌مانیم تا پروسه کاملاً بسته شود
        if os.path.exists(XRAY_CONFIG_FILE):
            os.remove(XRAY_CONFIG_FILE)

def worker(proxy_queue, results_list):
    """
    تابعی که هر ترد برای تست پروکسی‌ها اجرا می‌کند.
    """
    while not proxy_queue.empty():
        proxy = proxy_queue.get()
        latency = test_proxy(proxy)
        if 0 < latency < MAX_LATENCY_MS:
            results_list.append({'proxy': proxy, 'latency': latency})
            print(f"  SUCCESS | Latency: {latency:4d}ms | Proxy: {proxy[:40]}...")
        else:
            # print(f"  FAILED  | Proxy: {proxy[:40]}...") # برای خلوت شدن خروجی، چاپ نمی‌شود
            pass
        proxy_queue.task_done()

def main():
    print("\n--- Running 02_test_github.py ---")

    if not download_and_extract_xray():
        sys.exit(1) # اگر دانلود Xray با شکست مواجه شد، خارج می‌شویم

    try:
        with open(RAW_PROXIES_FILE, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        print(f"Found {len(proxies)} proxies in '{RAW_PROXIES_FILE}' to test.")
    except FileNotFoundError:
        log_error("GitHub Test", f"'{RAW_PROXIES_FILE}' not found. Run 01_fetch_proxies.py first.")
        return

    # استفاده از تردینگ برای سرعت بخشیدن به فرآیند تست
    from queue import Queue
    proxy_queue = Queue()
    for p in proxies:
        proxy_queue.put(p)
    
    results = []
    threads = []
    num_threads = 50 # تعداد تردهای همزمان (قابل تنظیم)

    print(f"Starting test with {num_threads} threads...")
    for _ in range(num_threads):
        t = threading.Thread(target=worker, args=(proxy_queue, results))
        t.daemon = True
        t.start()
        threads.append(t)

    proxy_queue.join() # منتظر می‌مانیم تا همه پروکسی‌ها تست شوند

    print("\nTest finished.")
    print(f"Found {len(results)} working proxies.")

    if not results:
        print("No working proxies found. Exiting.")
        return

    # مرتب‌سازی نتایج بر اساس کمترین پینگ
    sorted_results = sorted(results, key=lambda x: x['latency'])
    sorted_proxies = [item['proxy'] for item in sorted_results]

    # --- ذخیره نتایج ---
    print("Saving results...")
    
    # 1. تمام پروکسی‌های فعال
    with open(OUTPUT_ALL_FILE, 'w') as f:
        f.write('\n'.join(sorted_proxies))
    print(f"  -> Saved {len(sorted_proxies)} proxies to '{OUTPUT_ALL_FILE}'")

    # 2. 500 پروکسی برتر
    top_500 = sorted_proxies[:500]
    with open(OUTPUT_TOP_500_FILE, 'w') as f:
        f.write('\n'.join(top_500))
    print(f"  -> Saved {len(top_500)} proxies to '{OUTPUT_TOP_500_FILE}'")
    
    # 3. 100 پروکسی برتر
    top_100 = sorted_proxies[:100]
    with open(OUTPUT_TOP_100_FILE, 'w') as f:
        f.write('\n'.join(top_100))
    print(f"  -> Saved {len(top_100)} proxies to '{OUTPUT_TOP_100_FILE}'")

    print("--- Finished 02_test_github.py ---")


if __name__ == "__main__":
    # برای اجرای مستقل این فایل، نیاز به نصب کتابخانه requests دارید
    # pip install requests
    # توجه: این اسکریپت ممکن است زمان زیادی برای اجرا نیاز داشته باشد
    import base64 # برای تابع create_xray_config
    main()
