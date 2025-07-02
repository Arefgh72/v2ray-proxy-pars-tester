import os
import sys
import json
import subprocess
import base64
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
error_log_count = 0
MAX_ERROR_LOGS = 20
PROGRESS_UPDATE_INTERVAL = 100

def check_singbox_executable() -> bool:
    if not os.path.exists(SING_BOX_EXECUTABLE):
        print(f"❌ CRITICAL: '{SING_BOX_EXECUTABLE}' not found.")
        log_error("Test Setup", f"Sing-box executable not found at '{SING_BOX_EXECUTABLE}'.")
        return False
    if not os.access(SING_BOX_EXECUTABLE, os.X_OK):
        print(f"❌ CRITICAL: '{SING_BOX_EXECUTABLE}' is not executable.")
        log_error("Test Setup", f"Sing-box is not executable.")
        return False
    return True

def create_singbox_config(proxy_link: str) -> None:
    # این کانفیگ درست است. ما یک outbound برای تست داریم با تگ speed-test
    config = {
        "outbounds": [
            {
                "tag": "proxy-to-test",
                "type": "auto",
                "server": proxy_link
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
    global error_log_count
    create_singbox_config(proxy_link)

    # --- <<< تغییر اصلی و نهایی: استفاده از دستور صحیح sing-box >>> ---
    # دستور صحیح 'measure' است، نه 'url-test'.
    # ما باید outbound ای که می‌خواهیم تست شود را هم مشخص کنیم (-outbound speed-test).
    command = [
        SING_BOX_EXECUTABLE,
        'measure',
        '-config', TEMP_CONFIG_FILE,
        '-outbound', 'speed-test' # این خط به sing-box می‌گوید کدام outbound را تست کند
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
        
        # خروجی موفق دستور measure معمولا یک خط حاوی پینگ است
        if result.returncode == 0 and 'ms' in result.stdout:
            try:
                # خروجی چیزی شبیه "delay: 123ms" است
                latency = int(result.stdout.strip().split('ms')[0].split(':')[-1].strip())
                return latency
            except (ValueError, IndexError):
                return None # اگر پارس کردن شکست خورد
        
        # اگر تست ناموفق بود، خطا را چاپ می‌کنیم (برای عیب‌یابی)
        if error_log_count < MAX_ERROR_LOGS:
            sys.stdout.write('\n')
            print(f"DEBUG: Test failed for proxy: {proxy_link[:60]}...")
            print(f"DEBUG: Sing-box stdout:\n---\n{result.stdout.strip()}\n---")
            print(f"DEBUG: Sing-box stderr:\n---\n{result.stderr.strip()}\n---")
            error_log_count += 1
        return None

    except subprocess.TimeoutExpired:
        if error_log_count < MAX_ERROR_LOGS:
            sys.stdout.write('\n')
            print(f"DEBUG: Timeout expired for proxy: {proxy_link[:60]}...")
            error_log_count += 1
        return None
    except Exception as e:
        if error_log_count < MAX_ERROR_LOGS:
            sys.stdout.write('\n')
            print(f"DEBUG: Subprocess error for proxy: {proxy_link[:60]}... Error: {e}")
            error_log_count += 1
        log_error("Proxy Test", f"Error testing proxy: {proxy_link[:40]}...", str(e))
        return None

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
