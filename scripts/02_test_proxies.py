import os
import sys
import json
import asyncio
import base64
import time
from typing import List, Tuple, Optional, Dict
from urllib.parse import urlparse, parse_qs

from .utils import log_error, log_test_summary

# --- تنظیمات ---
SING_BOX_EXECUTABLE = './sing-box'
RAW_PROXIES_FILE = 'output/raw_proxies.txt'
OUTPUT_FILES = {
    'all': 'output/github_all.txt',
    'top_500': 'output/github_top_500.txt',
    'top_100': 'output/github_top_100.txt'
}
TEMP_DIR = 'temp_configs'
LOCAL_SOCKS_PORT_START = 2080
TEST_URL = 'https://www.youtube.com/'
PROGRESS_UPDATE_INTERVAL = 100
DEBUG_MODE = False

# --- تنظیمات کلیدی ---
CONCURRENT_TESTS = 250
# --- <<< شرط جدید: حداکثر پینگ مجاز >>> ---
MAX_LATENCY_MS = 2000

def check_singbox_executable() -> bool:
    if not os.path.exists(SING_BOX_EXECUTABLE) or not os.access(SING_BOX_EXECUTABLE, os.X_OK):
        msg = f"Sing-box executable not found or not executable at '{SING_BOX_EXECUTABLE}'"
        print(f"❌ CRITICAL: {msg}")
        log_error("Test Setup", msg)
        return False
    return True

def parse_proxy_link(proxy_link: str) -> Optional[Dict]:
    # این تابع کامل و صحیح است و بدون تغییر باقی می‌ماند
    try:
        if proxy_link.startswith('vmess://'): return None
        parsed = urlparse(proxy_link)
        protocol_map = {'ss': 'shadowsocks', 'vless': 'vless', 'trojan': 'trojan', 'hy': 'hysteria', 'hy2': 'hysteria2'}
        protocol = protocol_map.get(parsed.scheme)
        if not protocol: return None
        params = parse_qs(parsed.query)
        outbound_config = {"type": protocol, "tag": "proxy-out", "server": parsed.hostname, "server_port": parsed.port}
        if protocol == 'vless': outbound_config['uuid'] = parsed.username
        elif protocol == 'trojan': outbound_config['password'] = parsed.username
        elif protocol == 'shadowsocks':
            try:
                decoded_user = base64.urlsafe_b64decode(parsed.username + '===').decode('utf-8')
                method, password = decoded_user.split(':', 1)
                outbound_config['method'] = method; outbound_config['password'] = password
            except: return None
        VALID_TRANSPORT_TYPES = {'ws', 'grpc', 'quic'}
        transport_type = params.get('type', [None])[0]
        if transport_type and transport_type != 'tcp':
            if transport_type not in VALID_TRANSPORT_TYPES: return None
            transport_config = {"type": transport_type}
            if 'host' in params: transport_config['headers'] = {'Host': params['host'][0]}
            if 'path' in params: transport_config['path'] = params['path'][0]
            outbound_config['transport'] = transport_config
        if 'security' in params and params['security'][0] == 'tls':
            tls_config = {"enabled": True}
            if 'sni' in params: tls_config['server_name'] = params['sni'][0]
            if 'allowInsecure' in params and params['allowInsecure'][0] == '1': tls_config['insecure'] = True
            if 'transport' in outbound_config: outbound_config['transport']['tls'] = tls_config
            else: outbound_config['tls'] = tls_config
        return outbound_config
    except Exception: return None

def create_singbox_config(outbound_config: Dict, port: int, temp_file_path: str) -> None:
    # این تابع صحیح است و بدون تغییر باقی می‌ماند
    config = {
        "inbounds": [{"type": "socks", "listen": "127.0.0.1", "listen_port": port, "tag": "socks-in"}],
        "outbounds": [outbound_config],
        "route": {"rules": [{"inbound": ["socks-in"], "outbound": "proxy-out"}]}
    }
    with open(temp_file_path, 'w', encoding='utf-8') as f:
        json.dump(config, f)

async def test_single_proxy_async(proxy_index: int, proxy_link: str) -> Optional[Tuple[str, int]]:
    # این تابع صحیح است و بدون تغییر باقی می‌ماند
    outbound_config = parse_proxy_link(proxy_link)
    if not outbound_config: return None
    port = LOCAL_SOCKS_PORT_START + proxy_index
    temp_file_path = os.path.join(TEMP_DIR, f'config_{proxy_index}.json')
    create_singbox_config(outbound_config, port, temp_file_path)
    singbox_process = None
    try:
        cmd_run = [SING_BOX_EXECUTABLE, 'run', '-c', temp_file_path]
        singbox_process = await asyncio.create_subprocess_exec(*cmd_run, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.sleep(0.5)
        proxy_address = f"socks5h://127.0.0.1:{port}"
        cmd_curl = ['curl', '--proxy', proxy_address, '--connect-timeout', '5', '-m', '8', '--head', '--silent', '--output', '/dev/null', '--write-out', '%{time_total}', TEST_URL]
        proc_curl = await asyncio.create_subprocess_exec(*cmd_curl, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc_curl.communicate()
        if proc_curl.returncode == 0 and stdout:
            try:
                latency = int(float(stdout.decode().replace(',', '.')) * 1000)
                return proxy_link, latency
            except (ValueError, IndexError): return None
        return None
    except asyncio.CancelledError: return None
    except Exception: return None
    finally:
        if singbox_process and singbox_process.returncode is None:
            singbox_process.kill()
            await singbox_process.wait()

def save_results_as_base64(sorted_proxies: List[str]) -> None:
    # این تابع صحیح است و بدون تغییر باقی می‌ماند
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

async def main_async():
    print("\n--- Running 02_test_proxies.py (Parallel & Filtered) ---")
    if not check_singbox_executable(): sys.exit(1)
    os.makedirs(TEMP_DIR, exist_ok=True)
    try:
        with open(RAW_PROXIES_FILE, 'r') as f:
            proxies_to_test = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"❌ ERROR: Input file not found: '{RAW_PROXIES_FILE}'.")
        log_error("Test Proxies", f"Input file '{RAW_PROXIES_FILE}' not found.")
        return

    total_proxies = len(proxies_to_test)
    if total_proxies == 0: print("No proxies to test."); return
    print(f"[INFO] Starting parallel test for {total_proxies} proxies with {CONCURRENT_TESTS} workers...")

    healthy_proxies: List[Tuple[str, int]] = []
    
    semaphore = asyncio.Semaphore(CONCURRENT_TESTS)
    tested_count = 0
    # --- <<< تغییر ۱: اضافه کردن شمارنده پراکسی‌های با کیفیت >>> ---
    qualified_count = 0
    
    async def worker(proxy_index, proxy_link):
        nonlocal tested_count, qualified_count
        async with semaphore:
            result = await test_single_proxy_async(proxy_index, proxy_link)
            if result:
                healthy_proxies.append(result)
                # اگر پینگ زیر حد مجاز بود، شمارنده کیفیت را اضافه کن
                if result[1] < MAX_LATENCY_MS:
                    qualified_count += 1

            tested_count += 1
            if tested_count % PROGRESS_UPDATE_INTERVAL == 0 or tested_count == total_proxies:
                percentage = (tested_count / total_proxies) * 100
                # --- <<< تغییر ۲: نمایش شمارنده جدید در پروگرس بار >>> ---
                progress_line = f"🔄 [PROGRESS] Tested: {tested_count}/{total_proxies} ({percentage:.2f}%) | Healthy: {len(healthy_proxies)} | Qualified (<{MAX_LATENCY_MS}ms): {qualified_count}"
                sys.stdout.write('\r' + progress_line)
                sys.stdout.flush()

    tasks = [worker(i, proxy) for i, proxy in enumerate(proxies_to_test)]
    await asyncio.gather(*tasks)

    # پاکسازی فایل‌های موقت
    for item in os.listdir(TEMP_DIR):
        try: os.remove(os.path.join(TEMP_DIR, item))
        except: pass
    try: os.rmdir(TEMP_DIR)
    except: pass
    
    print("\n\n📊 [SUMMARY] Test Complete.")
    print("-" * 35)
    print(f"  Total Proxies Scanned: {total_proxies}")
    print(f"  Total Healthy Proxies: {len(healthy_proxies)}")

    # --- <<< تغییر ۳: فیلتر کردن پراکسی‌ها قبل از ذخیره‌سازی >>> ---
    print(f"\n[INFO] Filtering healthy proxies with latency < {MAX_LATENCY_MS}ms...")
    qualified_proxies = [p for p in healthy_proxies if p[1] < MAX_LATENCY_MS]
    print(f"  -> Found {len(qualified_proxies)} qualified proxies.")

    if total_proxies > 0:
        success_rate = (len(qualified_proxies) / total_proxies) * 100
        print(f"  Overall Success Rate (Qualified): {success_rate:.2f}%")
    print("-" * 35)

    stats = {'passed_count': 0}
    if qualified_proxies:
        qualified_proxies.sort(key=lambda item: item[1])
        latencies = [item[1] for item in qualified_proxies]
        stats = {'passed_count': len(qualified_proxies), 'avg_latency': sum(latencies) / len(qualified_proxies), 'min_latency': min(latencies), 'max_latency': max(latencies)}
        sorted_proxy_links = [item[0] for item in qualified_proxies]
        save_results_as_base64(sorted_proxy_links)
    else:
        print("\n[INFO] No qualified proxies found. Output files will be empty.")
        save_results_as_base64([])
        
    log_test_summary(cycle_number=os.getenv('GITHUB_RUN_NUMBER', 0), raw_count=total_proxies, github_stats=stats, iran_stats={})
    print("\n--- Finished 02_test_proxies.py ---")


if __name__ == "__main__":
    asyncio.run(main_async())
