# scripts/02_test_hysteria.py

import subprocess
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import random
import string
import time
import os
import signal

from utils import get_proxies_from_file, save_proxies_to_file, save_json_to_file

HYSTERIA_CLIENT_PATH = "./hysteria-client"

def generate_random_filename(prefix="temp_hy_config_", extension=".json"):
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{random_str}{extension}"

def test_hysteria_proxy(proxy: str) -> dict:
    """
    ✅ بر اساس منطق فایل اصلی شما با اضافه کردن لاگ‌های دقیق برای عیب‌یابی.
    """
    temp_config_filename = generate_random_filename()
    config_path = Path(temp_config_filename)
    local_port = random.randint(20001, 30000)

    config = {
        "server": proxy,
        "insecure": True,
        "inbound": {"type": "socks5", "listen": f"127.0.0.1:{local_port}"}
    }
    
    process = None
    try:
        config_path.write_text(json.dumps(config), encoding='utf-8')
        
        command = [HYSTERIA_CLIENT_PATH, "client", "-c", str(config_path)]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
        
        time.sleep(2)

        curl_command = [
            "curl", "-s", "--socks5-hostname", f"127.0.0.1:{local_port}",
            "http://cp.cloudflare.com/", "--connect-timeout", "5",
            "-o", "/dev/null", "-w", "%{time_connect}"
        ]
        curl_proc = subprocess.run(curl_command, capture_output=True, text=True, timeout=10)

        if curl_proc.returncode == 0 and curl_proc.stdout:
            delay = int(float(curl_proc.stdout) * 1000)
            return {"proxy": proxy, "status": "active", "delay": delay}

        return {"proxy": proxy, "status": "dead", "delay": -1}

    except Exception:
        return {"proxy": proxy, "status": "dead", "delay": -1}
    finally:
        if process and process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        if config_path.exists():
            config_path.unlink()

def main():
    print("🚀 شروع تست پراکسی‌های Hysteria با روش فایل اصلی...")
    proxies_file_path = Path("output/fetched_hysteria.txt")
    proxies_to_test = get_proxies_from_file(proxies_file_path)

    if not proxies_to_test:
        save_json_to_file([], Path("output/hysteria_results.json"))
        save_proxies_to_file([], Path("output/hysteria_all.txt"))
        return

    working_proxies_results = []
    # کاهش تعداد workerها برای اطمینان از پایداری
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = executor.map(test_hysteria_proxy, proxies_to_test)
    
    active_count = 0
    for result in results:
        if result["status"] == "active":
            working_proxies_results.append(result)
            active_count += 1
            
    print(f"تست تمام شد. تعداد پراکسی‌های فعال یافت شده: {active_count}")

    working_proxies_results.sort(key=lambda p: p["delay"])
    final_proxy_strings = [p["proxy"] for p in working_proxies_results]
    
    save_json_to_file(working_proxies_results, Path("output/hysteria_results.json"))
    save_proxies_to_file(final_proxy_strings, Path("output/hysteria_all.txt"))
    print("📄 نتایج تست Hysteria ذخیره شدند.")

if __name__ == "__main__":
    main()
