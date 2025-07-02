import os
import sys
import json
import subprocess
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
TEMP_CONFIG_FILE = 'temp_singbox_config.json'
LOCAL_SOCKS_PORT = 2080
TEST_URL = 'https://www.youtube.com/'
PROGRESS_UPDATE_INTERVAL = 100
DEBUG_MODE = True

def check_singbox_executable() -> bool:
    if not os.path.exists(SING_BOX_EXECUTABLE) or not os.access(SING_BOX_EXECUTABLE, os.X_OK):
        msg = f"Sing-box executable not found or not executable at '{SING_BOX_EXECUTABLE}'"
        print(f"❌ CRITICAL: {msg}")
        log_error("Test Setup", msg)
        return False
    return True

def parse_proxy_link(proxy_link: str) -> Optional[Dict]:
    """
    لینک پراکسی را به یک دیکشنری معتبر برای کانفیگ sing-box تجزیه می‌کند.
    این تابع بازنویسی شده تا بر اساس مستندات واقعی کار کند.
    """
    try:
        if proxy_link.startswith('vmess://'):
            try:
                decoded_link = base64.b64decode(proxy_link.replace('vmess://', '')).decode('utf-8')
                vmess_config = json.loads(decoded_link)
                config = {
                    "type": "vmess", "tag": "proxy-out",
                    "server": vmess_config.get('add'),
                    "server_port": int(vmess_config.get('port', 443)),
                    "uuid": vmess_config.get('id'),
                    "security": vmess_config.get('scy', 'auto'),
                    "alter_id": int(vmess_config.get('aid', 0))
                }
                if vmess_config.get('net') and vmess_config.get('net') != 'tcp':
                    config['transport'] = {
                        "type": vmess_config.get('net'),
                        "path": vmess_config.get('path'),
                        "headers": {"Host": vmess_config.get('host')} if vmess_config.get('host') else None
                    }
                if vmess_config.get('tls') == 'tls':
                    config.setdefault('transport', {})['tls'] = {"enabled": True, "server_name": vmess_config.get('sni', vmess_config.get('host'))}
                return config
            except: return None # اگر پارس کردن vmess شکست خورد
        
        parsed = urlparse(proxy_link)
        protocol = parsed.scheme
        if protocol not in ['vless', 'trojan', 'ss', 'hysteria', 'hy2', 'hysteria2']: return None
        
        params = parse_qs(parsed.query)
        outbound_config = {
            "type": "hysteria2" if protocol in ['hy2', 'hysteria2'] else ('hysteria' if protocol == 'hy' else protocol),
            "tag": "proxy-out", "server": parsed.hostname, "server_port": parsed.port
        }
        
        if protocol in ['vless', 'trojan']:
            outbound_config['uuid' if protocol == 'vless' else 'password'] = parsed.username
        elif protocol == 'ss':
            #
            decoded_user = base64.urlsafe_b64decode(parsed.username + '===').decode('utf-8')
            method, password = decoded_user.split(':', 1)
            outbound_config['method'] = method
            outbound_config['password'] = password

        transport_config = {}
        if 'type' in params and params['type'][0] == 'ws':
            transport_config['type'] = 'ws'
            if 'path' in params: transport_config['path'] = params['path'][0]
            if 'host' in params: transport_config['headers'] = {'Host': params['host'][0]}
        
        if 'security' in params and params['security'][0] == 'tls':
            transport_config.setdefault('tls', {})['enabled'] = True
            if 'sni' in params: transport_config.setdefault('tls', {})['server_name'] = params['sni'][0]
            if 'allowInsecure' in params and params['allowInsecure'][0] == '1': transport_config.setdefault('tls', {})['insecure'] = True
            if 'alpn' in params: transport_config.setdefault('tls', {})['alpn'] = params['alpn'][0].split(',')

        if transport_config: outbound_config['transport'] = transport_config
        
        return outbound_config
    except Exception:
        return None

def create_singbox_config(outbound_config: Dict) -> None:
    config = {
        "inbounds": [{"type": "socks", "listen": "127.0.0.1", "listen_port": LOCAL_SOCKS_PORT, "tag": "socks-in"}],
        "outbounds": [outbound_config],
        "routing": {"rules": [{"inbound": ["socks-in"], "outbound": "proxy-out"}]}
    }
    with open(TEMP_CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def test_single_proxy(proxy_link: str) -> Optional[int]:
    outbound_config = parse_proxy_link(proxy_link)
    if not outbound_config: return None
    create_singbox_config(outbound_config)
    singbox_process = None
    try:
        cmd_run = [SING_BOX_EXECUTABLE, 'run', '-c', TEMP_CONFIG_FILE]
        singbox_process = subprocess.Popen(cmd_run, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, universal_newlines=True)
        time.sleep(0.5)

        proxy_address = f"socks5h://127.0.0.1:{LOCAL_SOCKS_PORT}"
        cmd_curl = ['curl', '--proxy', proxy_address, '--connect-timeout', '5', '-m', '8', '--head', '--silent', '--output', '/dev/null', '--write-out', '%{time_total}', TEST_URL]
        curl_result = subprocess.run(cmd_curl, capture_output=True, text=True, check=False)
        singbox_process.kill()

        if curl_result.returncode == 0 and curl_result.stdout:
            try: return int(float(curl_result.stdout.replace(',', '.')) * 1000)
            except: return None
        
        if DEBUG_MODE:
            _, singbox_stderr = singbox_process.communicate(timeout=2)
            if "FATAL" in singbox_stderr or "level=fatal" in singbox_stderr:
                sys.stdout.write('\n')
                print("="*20 + " DEBUG INFO " + "="*20)
                print(f"Proxy: {proxy_link[:80]}...")
                print(f"CURL Exit Code: {curl_result.returncode} | CURL Stderr: {curl_result.stderr.strip()}")
                if singbox_stderr: print(f"Sing-box Stderr: {singbox_stderr.strip()}")
                print("="*21 + " DEBUG END " + "="*22 + "\n")
        
        return None
    except Exception: return None
    finally:
        if singbox_process and singbox_process.poll() is None:
            singbox_process.kill()
            singbox_process.wait()

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
