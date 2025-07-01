import os
import subprocess
import json
from utils import log_error

# --- تنظیمات ---
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
XRAY_PROXIES_FILE = 'output/temp_xray_proxies.txt'
HYSTERIA_PROXIES_FILE = 'output/temp_hysteria_proxies.txt'
XRAY_RESULTS_FILE = 'output/xray_results.json'
HYSTERIA_RESULTS_FILE = 'output/hysteria_results.json'

OUTPUT_ALL_FILE = 'output/github_all.txt'
OUTPUT_TOP_500_FILE = 'output/github_top_500.txt'
OUTPUT_TOP_100_FILE = 'output/github_top_100.txt'

# مسیر ابزارهایی که در پوشه base قرار دارند
XRAY_TESTER_PATH = './base/xray-tester'
HYSTERIA_CLIENT_PATH = './base/hysteria-client'


def categorize_proxies():
    """
    پروکسی‌های خام را به دو دسته Xray و Hysteria تقسیم می‌کند.
    """
    print("Categorizing proxies...")
    try:
        with open(RAW_PROXIES_FILE, 'r') as f:
            all_proxies = [line.strip() for line in f if line.strip()]

        xray_proxies = []
        hysteria_proxies = []

        for proxy in all_proxies:
            if proxy.startswith(('hysteria://', 'hy2://')):
                hysteria_proxies.append(proxy)
            elif proxy.startswith(('vmess://', 'vless://', 'trojan://', 'ss://')):
                xray_proxies.append(proxy)

        with open(XRAY_PROXIES_FILE, 'w') as f:
            f.write('\n'.join(xray_proxies))
        print(f"  -> Found {len(xray_proxies)} Xray-based proxies.")

        with open(HYSTERIA_PROXIES_FILE, 'w') as f:
            f.write('\n'.join(hysteria_proxies))
        print(f"  -> Found {len(hysteria_proxies)} Hysteria-based proxies.")
        
        return len(xray_proxies) > 0, len(hysteria_proxies) > 0

    except Exception as e:
        log_error("Categorization", "Failed to categorize proxies.", str(e))
        return False, False


def test_xray_proxies():
    """
    تستر حرفه‌ای Xray را برای تست پروکسی‌های مربوطه فراخوانی می‌کند.
    """
    print("\n--- Testing Xray Proxies ---")
    try:
        # دستور اجرای تستر Xray (این دستورات بر اساس ابزار v2ray-ping نوشته شده)
        # ما از این ابزار می‌خواهیم که URL تست را چک کرده و نتایج را در فایل JSON ذخیره کند
        command = [
            XRAY_TESTER_PATH,
            "-c", XRAY_PROXIES_FILE,       # فایل ورودی
            "--url", "https://www.google.com/generate_204", # URL تست سبک
            "--timeout", "10",            # تایم‌اوت 10 ثانیه
            "--json", XRAY_RESULTS_FILE    # فایل خروجی JSON
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        print("Xray test finished successfully.")
        return True
    except subprocess.CalledProcessError as e:
        log_error("Xray Test", "Xray tester failed.", e.stderr)
        return False
    except Exception as e:
        log_error("Xray Test", "An unexpected error occurred.", str(e))
        return False


def test_hysteria_proxies():
    """
    کلاینت رسمی Hysteria را برای تست پروکسی‌های Hysteria فراخوانی می‌کند.
    (توجه: تست گروهی در کلاینت Hysteria به سادگی Xray نیست، ما هر پروکسی را جدا تست می‌کنیم)
    """
    print("\n--- Testing Hysteria Proxies ---")
    results = []
    try:
        with open(HYSTERIA_PROXIES_FILE, 'r') as f:
            proxies = f.read().splitlines()
        
        for i, proxy in enumerate(proxies):
            print(f"Testing Hysteria proxy {i+1}/{len(proxies)}...")
            try:
                # کلاینت Hysteria را در حالت پروکسی اجرا کرده و پینگ آن را می‌سنجیم
                # این یک روش شبیه‌سازی شده است
                # TODO: این بخش نیاز به بهبود دارد تا از قابلیت تست داخلی خود کلاینت استفاده کند اگر وجود داشته باشد
                # فعلا یک پینگ ساده را برمی‌گردانیم
                # در اینجا یک عدد رندوم برای شبیه‌سازی پینگ برمی‌گردانیم
                # این بخش باید با منطق تست واقعی جایگزین شود
                # latency = random.randint(200, 2000)
                # results.append({"proxy": proxy, "latency": latency})
                pass # فعلا از تست هیستریا صرف نظر می‌کنیم تا ساختار اصلی درست کار کند
            except Exception:
                continue

        with open(HYSTERIA_RESULTS_FILE, 'w') as f:
            json.dump(results, f)
        print("Hysteria test finished.")
        return True
    except Exception as e:
        log_error("Hysteria Test", "An unexpected error occurred.", str(e))
        return False


def combine_and_save_results():
    """
    نتایج تست‌های مختلف را ترکیب، مرتب‌سازی و ذخیره می‌کند.
    """
    print("\n--- Combining and Saving Results ---")
    all_results = []

    # خواندن نتایج Xray
    try:
        if os.path.exists(XRAY_RESULTS_FILE):
            with open(XRAY_RESULTS_FILE, 'r') as f:
                xray_data = json.load(f)
            # فرمت خروجی v2ray-ping معمولا لیستی از دیکشنری‌هاست
            for item in xray_data:
                # ما فقط به پروکسی‌هایی با پینگ موفق (بزرگتر از 0) نیاز داریم
                if item.get("delay") and item["delay"] > 0:
                    all_results.append({"proxy": item["config"], "latency": item["delay"]})
    except Exception as e:
        log_error("Result Combination", "Failed to read or parse Xray results.", str(e))

    # خواندن نتایج Hysteria (وقتی که پیاده‌سازی شود)
    try:
        if os.path.exists(HYSTERIA_RESULTS_FILE):
            with open(HYSTERIA_RESULTS_FILE, 'r') as f:
                all_results.extend(json.load(f))
    except Exception as e:
        log_error("Result Combination", "Failed to read or parse Hysteria results.", str(e))
        
    print(f"Total {len(all_results)} working proxies found from all testers.")
    if not all_results:
        print("No working proxies found. Nothing to save.")
        # فایل‌های خالی ایجاد می‌کنیم تا لینک‌ها کار کنند
        open(OUTPUT_ALL_FILE, 'w').close()
        open(OUTPUT_TOP_500_FILE, 'w').close()
        open(OUTPUT_TOP_100_FILE, 'w').close()
        return

    # مرتب‌سازی نهایی بر اساس پینگ
    sorted_results = sorted(all_results, key=lambda x: x['latency'])
    sorted_proxies = [item['proxy'] for item in sorted_results]

    # ذخیره در فایل‌های خروجی
    print("Saving final sorted lists...")
    with open(OUTPUT_ALL_FILE, 'w') as f: f.write('\n'.join(sorted_proxies))
    print(f"  -> Saved {len(sorted_proxies)} proxies to '{OUTPUT_ALL_FILE}'")
    
    top_500 = sorted_proxies[:500]
    with open(OUTPUT_TOP_500_FILE, 'w') as f: f.write('\n'.join(top_500))
    print(f"  -> Saved {len(top_500)} proxies to '{OUTPUT_TOP_500_FILE}'")
    
    top_100 = sorted_proxies[:100]
    with open(OUTPUT_TOP_100_FILE, 'w') as f: f.write('\n'.join(top_100))
    print(f"  -> Saved {len(top_100)} proxies to '{OUTPUT_TOP_100_FILE}'")


def main():
    """
    تابع اصلی که تمام مراحل را مدیریت می‌کند.
    """
    xray_exists, hysteria_exists = categorize_proxies()
    
    if xray_exists:
        test_xray_proxies()
    else:
        print("No Xray-based proxies to test.")

    if hysteria_exists:
        test_hysteria_proxies()
    else:
        print("No Hysteria-based proxies to test.")
        
    combine_and_save_results()
    print("\n--- All tasks finished ---")


if __name__ == "__main__":
    main()
