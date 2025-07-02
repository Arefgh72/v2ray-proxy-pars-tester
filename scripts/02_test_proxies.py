import os
import sys
import json
import subprocess
import base64
import time
from typing import List, Tuple, Optional

from .utils import log_error, log_test_summary

# --- تنظیمات و ثابت‌ها ---
SING_BOX_EXECUTABLE = './sing-box'
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
OUTPUT_FILES = {
    'all': 'output/github_all.txt',
    'top_500': 'output/github_top_500.txt',
    'top_100': 'output/github_top_100.txt'
}
TEMP_CONFIG_FILE = 'temp_singbox_config.json'
LOCAL_SOCKS_PORT = 2080 # یک پورت برای پراکسی محلی
TEST_URL = 'http://cp.cloudflare.com/generate_204' # URL سبک برای تست

error_log_count = 0
MAX_ERROR_LOGS = 5 # تعداد لاگ‌های دیباگ را کم می‌کنیم
PROGRESS_UPDATE_INTERVAL = 100

def check_singbox_executable() -> bool:
    if not os.path.exists(SING_BOX_EXECUTABLE) or not os.access(SING_BOX_EXECUTABLE, os.X_OK):
        msg = f"Sing-box executable not found or not executable at '{SING_BOX_EXECUTABLE}'"
        print(f"❌ CRITICAL: {msg}")
        log_error("Test Setup", msg)
        return False
    return True

def create_singbox_config(proxy_link: str) -> None:
    """کانفیگی می‌سازد که یک ورودی SOCKS محلی را به پراکسی مورد تست متصل می‌کند."""
    config = {
        "log": {"level": "warn"},
        "inbounds": [{
            "type": "socks",
            "tag": "socks-in",
            "listen": "127.0.0.1",
            "listen_port": LOCAL_SOCKS_PORT
        }],
        "outbounds": [{
            "type": "auto",
            "tag": "proxy-out",
            "server": proxy_link
        }],
        "routing": {
            "rules": [{
                "inbound": ["socks-in"],
                "outbound": "proxy-out"
            }]
        }
    }
    with open(TEMP_CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def test_single_proxy(proxy_link: str) -> Optional[int]:
    global error_log_count
    create_singbox_config(proxy_link)
    
    # --- <<< تغییر اصلی: اجرای sing-box به عنوان سرور در پس‌زمینه >>> ---
    singbox_process = None
    try:
        # دستور صحیح برای اجرای سرور
        cmd_run = [SING_BOX_EXECUTABLE, 'run', '-c', TEMP_CONFIG_FILE]
        singbox_process = subprocess.Popen(cmd_run, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # کمی صبر می‌کنیم تا سرور بالا بیاید
        time.sleep(0.8)

        # --- استفاده از curl برای تست پراکسی محلی ---
        proxy_address = f"socks5h://127.0.0.1:{LOCAL_SOCKS_PORT}"
        cmd_curl = [
            'curl',
            '--proxy', proxy_address,
            '--connect-timeout', '7', # ۷ ثانیه برای اتصال
            '-m', '10', # حداکثر ۱۰ ثانیه برای کل عملیات
            '--head', # فقط هدرها را بگیر، سریعتر است
            '--silent', # هیچ خروجی‌ای چاپ نکن
            '--output', '/dev/null', # خروجی را دور بریز
            '--write-out', '%{time_total}', # فقط زمان کل را چاپ کن
            TEST_URL
        ]
        
        result = subprocess.run(cmd_curl, capture_output=True, text=True, check=False)

        # اگر curl موفق بود (کد بازگشتی 0) و خروجی داشت
        if result.returncode == 0 and result.stdout:
            try:
                # تبدیل زمان از ثانیه به میلی‌ثانیه
                total_time_sec = float(result.stdout.replace(',', '.'))
                return int(total_time_sec * 1000)
            except (ValueError, IndexError):
                return None
        
        return None # اگر curl ناموفق بود

    except Exception:
        # هر خطای دیگری در این فرآیند
        return None
    finally:
        # --- بسیار مهم: اطمینان از بسته شدن پردازش sing-box ---
        if singbox_process:
            singbox_process.kill()
            singbox_process.wait()

# بقیه توابع (save_results_as_base64 و main) بدون تغییر باقی می‌مانند
def save_results_as_base64(sorted_proxies: List[str]) -> None:
    print("\n[INFO] Saving results to output files (Base64 encoded)...")
    all_content = "\n".join(sorted_proxies)
    all_base64 = base64.b64encode(all_content.encode('utf-8')).decode('utf-8')
    with open(OUTPUT_FILES['all'], 'w') as f:
        f.write(all_base64)
    print(f"  -> Saved {len(sorted_proxies)} proxies to '{OUTPUT_FILES['all']}'.")
    top_500 = sorted_proxies[:500]
    if top_500:
        top_500_content = "\n".join(top_500)
        top_500_base64 = base64.b64encode(top_500_content.encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILES['top_500'], 'w') as f:
            f.write(top_500_base64)
        print(f"  -> Saved {len(top_500)} proxies to '{OUTPUT_FILES['top_500']}'.")
    top_100 = sorted_proxies[:100]
    if top_100:
        top_100_content = "\n".join(top_100)
        top_100_base64 = base64.b64encode(top_100_content.encode('utf-8')).decode('utf-8')
        with open(OUTPUT_FILES['top_100'], 'w') as f:
            f.write(top_100_base64)
        print(f"  -> Saved {len(top_100)} proxies to '{OUTPUT_FILES['top_100']}'.")

def main():
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
        
        if tested_count % PROGRESS_UPDATE_INTERVAL == 0 or tested_count == total_proxies:
            percentage = (tested_count / total_proxies) * 100
            progress_line = f"🔄 [PROGRESS] Tested: {tested_count}/{total_proxies} ({percentage:.2f}%) | Healthy: {healthy_count}"
            sys.stdout.write('\r' + progress_line)
            sys.stdout.flush()

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
    stats = {'passed_count': 0}
    if healthy_proxies:
        healthy_proxies.sort(key=lambda item: item[1])
        latencies = [item[1] for item in healthy_proxies]
        stats = {
            'passed_count': healthy_count,
            'avg_latency': sum(latencies) / len(latencies),
            'min_latency': min(latencies),
            'max_latency': max(latencies)
        }
        sorted_proxy_links = [item[0] for item in healthy_proxies]
        save_results_as_base64(sorted_proxy_links)
    else:
        print("\n[INFO] No healthy proxies found. Output files will be empty.")
        save_results_as_base64([])
    log_test_summary(
        cycle_number=os.getenv('GITHUB_RUN_NUMBER', 0),
        raw_count=total_proxies,
        github_stats=stats,
        iran_stats={}
    )
    print("\n--- Finished 02_test_proxies.py ---")


if __name__ == "__main__":
    main()
