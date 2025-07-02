import os
import sys
import json
import subprocess
import base64
from typing import List, Tuple, Optional, Dict

# --- وارد کردن ماژول لاگر شخصی شما ---
# این فرض می‌کند که اسکریپت از ریشه پروژه اجرا می‌شود
try:
    from scripts.utils import log_error, log_test_summary
except ImportError:
    print("CRITICAL: Could not import from scripts.utils. Make sure you run the script from the project root.")
    sys.exit(1)

# --- تنظیمات و ثابت‌ها ---
# مسیر فایل اجرایی sing-box (فرض می‌کنیم در ریشه پروژه قرار خواهد گرفت)
SING_BOX_EXECUTABLE = './sing-box'
# فایل ورودی
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
# نام فایل‌های خروجی نهایی
OUTPUT_FILES = {
    'all': 'output/github_all.txt',
    'top_500': 'output/github_top_500.txt',
    'top_100': 'output/github_top_100.txt'
}
# فایل کانفیگ موقت برای sing-box
TEMP_CONFIG_FILE = 'temp_singbox_config.json'


def check_singbox_executable() -> bool:
    """بررسی می‌کند که آیا فایل اجرایی sing-box وجود دارد و قابل اجراست یا نه."""
    if not os.path.exists(SING_BOX_EXECUTABLE):
        print(f"❌ CRITICAL: '{SING_BOX_EXECUTABLE}' not found. Please download it and place it in the project root.")
        log_error("Test Setup", f"Sing-box executable not found at '{SING_BOX_EXECUTABLE}'.")
        return False
    if not os.access(SING_BOX_EXECUTABLE, os.X_OK):
        print(f"❌ CRITICAL: '{SING_BOX_EXECUTABLE}' is not executable. Please run 'chmod +x {SING_BOX_EXECUTABLE}'.")
        log_error("Test Setup", f"Sing-box is not executable.")
        return False
    return True

def create_singbox_config(proxy_link: str) -> None:
    """یک فایل کانفیگ موقت JSON برای تست یک پراکسی توسط sing-box ایجاد می‌کند."""
    config = {
        "outbounds": [
            {
                "type": "urltest",
                "tag": "url-test-group",
                "outbounds": [proxy_link],  # تست تنها یک پراکسی در هر زمان
                "url": "https://www.google.com/generate_204", # یک URL سبک برای تست پینگ
                "interval": "10m" # فاصله زیاد برای اینکه فقط یکبار تست کند
            }
        ]
    }
    # برای پراکسی‌های VLESS/VMESS ممکن است نیاز به فیلدهای بیشتری باشد
    # اما sing-box به اندازه کافی هوشمند است که لینک کامل را پارس کند.
    # برای سادگی، لینک را مستقیماً به عنوان outbound استفاده می‌کنیم.
    
    # کد بالا کار نمی‌کند. باید پراکسی را به عنوان یک outbound مجزا تعریف کرد.
    # ساختار صحیح کانفیگ:
    config = {
        "outbounds": [
            {
                "tag": "proxy-to-test",
                "type": "auto",  # اجازه می‌دهیم sing-box نوع را از روی لینک تشخیص دهد
                "server": proxy_link # لینک کامل پراکسی
            },
            {
                "type": "urltest",
                "tag": "speed-test",
                "outbounds": ["proxy-to-test"],
                "url": "http://cp.cloudflare.com/generate_204"
            }
        ]
    }

    with open(TEMP_CONFIG_FILE, 'w') as f:
        json.dump(config, f)


def test_single_proxy(proxy_link: str) -> Optional[int]:
    """
    یک پراکسی را با sing-box تست کرده و در صورت موفقیت، پینگ (latency) را برمی‌گرداند.
    در صورت شکست، None را برمی‌گرداند.
    """
    create_singbox_config(proxy_link)
    
    command = [
        SING_BOX_EXECUTABLE,
        'url-test',
        '-config', TEMP_CONFIG_FILE
    ]

    try:
        # اجرای دستور با timeout
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
        
        if result.returncode == 0:
            output_lines = result.stdout.strip().split('\n')
            # دنبال خطی می‌گردیم که شامل پینگ است
            for line in output_lines:
                if 'ms' in line:
                    # استخراج عدد پینگ از خط (مثلاً ' proxy-to-test  123 ms')
                    try:
                        latency = int(line.split('ms')[0].strip().split()[-1])
                        return latency
                    except (ValueError, IndexError):
                        continue # اگر پارس کردن شکست خورد، خط بعدی را امتحان کن
        return None
    except subprocess.TimeoutExpired:
        return None # پراکسی که تایم‌اوت شود، ناموفق است
    except Exception:
        # هر خطای دیگری در اجرای subprocess
        return None

def save_results_as_base64(sorted_proxies: List[str]) -> None:
    """نتایج مرتب‌شده را در فایل‌های خروجی با فرمت Base64 ذخیره می‌کند."""
    print("\n[INFO] Saving results to output files (Base64 encoded)...")

    # ذخیره تمام پراکسی‌های سالم
    all_content = "\n".join(sorted_proxies)
    all_base64 = base64.b64encode(all_content.encode('utf-8')).decode('utf-8')
    with open(OUTPUT_FILES['all'], 'w') as f:
        f.write(all_base64)
    print(f"  -> Saved {len(sorted_proxies)} proxies to '{OUTPUT_FILES['all']}'.")

    # ذخیره ۵۰۰ پراکسی برتر
    top_500 = sorted_proxies[:500]
    if top_500:
        top_500_content = "\n".join(top_500)
        top_500_base64 = base64.b64encode(top_500_content.encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILES['top_500'], 'w') as f:
            f.write(top_500_base64)
        print(f"  -> Saved {len(top_500)} proxies to '{OUTPUT_FILES['top_500']}'.")

    # ذخیره ۱۰۰ پراکسی برتر
    top_100 = sorted_proxies[:100]
    if top_100:
        top_100_content = "\n".join(top_100)
        top_100_base64 = base64.b64encode(top_100_content.encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILES['top_100'], 'w') as f:
            f.write(top_100_base64)
        print(f"  -> Saved {len(top_100)} proxies to '{OUTPUT_FILES['top_100']}'.")

def main():
    """تابع اصلی برای اجرای کل فرآیند تست."""
    print("\n--- Running 02_test_proxies.py ---")
    
    if not check_singbox_executable():
        sys.exit(1)

    try:
        with open(RAW_PROXIES_FILE, 'r') as f:
            proxies_to_test = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"❌ ERROR: Input file not found: '{RAW_PROXIES_FILE}'.")
        log_error("Test Proxies", f"Input file '{RAW_PROXIES_FILE}' not found.")
        return

    total_proxies = len(proxies_to_test)
    if total_proxies == 0:
        print("No proxies to test.")
        return

    print(f"[INFO] Starting test for {total_proxies} proxies...")

    healthy_proxies: List[Tuple[str, int]] = []
    tested_count = 0
    healthy_count = 0

    for proxy in proxies_to_test:
        tested_count += 1
        latency = test_single_proxy(proxy)
        
        if latency is not None:
            healthy_count += 1
            healthy_proxies.append((proxy, latency))

        # --- بخش گزارش‌دهی پیشرفت لحظه‌ای ---
        percentage = (tested_count / total_proxies) * 100
        progress_line = f"🔄 [PROGRESS] Tested: {tested_count}/{total_proxies} ({percentage:.2f}%) | Healthy: {healthy_count}"
        sys.stdout.write('\r' + progress_line)
        sys.stdout.flush()

    # پاک کردن فایل کانفیگ موقت
    if os.path.exists(TEMP_CONFIG_FILE):
        os.remove(TEMP_CONFIG_FILE)

    print("\n\n📊 [SUMMARY] Test Complete.")
    print("-" * 35)
    print(f"  Total Proxies Scanned: {total_proxies}")
    print(f"  Total Healthy Proxies: {healthy_count}")
    if total_proxies > 0:
        success_rate = (healthy_count / total_proxies) * 100
        print(f"  Success Rate: {success_rate:.2f}%")
    print("-" * 35)

    if healthy_proxies:
        # مرتب‌سازی بر اساس پینگ (کمتر بهتر است)
        healthy_proxies.sort(key=lambda item: item[1])
        
        # استخراج آمار برای لاگ دائمی
        latencies = [item[1] for item in healthy_proxies]
        stats = {
            'passed_count': healthy_count,
            'avg_latency': sum(latencies) / len(latencies),
            'min_latency': min(latencies),
            'max_latency': max(latencies)
        }
        
        # ذخیره نتایج در فایل‌های خروجی
        sorted_proxy_links = [item[0] for item in healthy_proxies]
        save_results_as_base64(sorted_proxy_links)

    else:
        # اگر هیچ پراکسی سالمی پیدا نشد
        stats = {'passed_count': 0}
        print("\n[INFO] No healthy proxies found. Output files will be empty.")
        # ایجاد فایل‌های خالی برای جلوگیری از خطای 404 در لینک‌های اشتراک
        save_results_as_base64([])


    # ثبت خلاصه در لاگ دائمی با استفاده از تابع شما
    log_test_summary(
        cycle_number=os.getenv('GITHUB_RUN_NUMBER', 0),
        raw_count=total_proxies,
        github_stats=stats,
        iran_stats={}  # این بخش فعلا خالی است
    )
    
    print("\n--- Finished 02_test_proxies.py ---")


if __name__ == "__main__":
    main()
