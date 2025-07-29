# scripts/02_test_proxies.py

import subprocess
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import random
import string
import time
import os

from .utils import get_proxies_from_file, save_proxies_to_file, save_json_to_file

SING_BOX_PATH = "./sing-box"

def generate_random_filename(prefix="temp_sb_config_", extension=".json"):
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{random_str}{extension}"

def test_proxy(proxy: str) -> dict:
    """
    ✅ بازگشت به منطق تست اصلی با استفاده از 'sing-box run' و تست اتصال با curl.
    """
    temp_config_filename = generate_random_filename()
    config_path = Path(temp_config_filename)
    
    # تعریف یک پورت محلی رندوم برای جلوگیری از تداخل در تست‌های موازی
    local_port = random.randint(10000, 20000)

    # ساختار کانفیگ کامل برای اجرای sing-box به عنوان یک کلاینت
    config = {
        "log": {"disabled": True},
        "inbounds": [{
            "type": "http",
            "tag": "http-in",
            "listen": "127.0.0.1",
            "listen_port": local_port
        }],
        "outbounds": [
            {"type": "proxy", "tag": "proxy", "url": proxy},
            {"type": "direct", "tag": "direct"}
        ],
        "routing": {
            "rules": [{
                "outbound": "proxy"
            }]
        }
    }
    
    process = None
    try:
        config_path.write_text(json.dumps(config), encoding='utf-8')
        
        # اجرای sing-box در پس‌زمینه
        command = [SING_BOX_PATH, "run", "-c", str(config_path)]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # یک لحظه کوتاه برای اطمینان از اجرای کامل sing-box
        time.sleep(2)

        # تست اتصال از طریق پراکسی محلی با curl
        # ما زمان اتصال (connect time) را به عنوان معیاری برای پینگ در نظر می‌گیریم
        curl_command = [
            "curl",
            "-s", # حالت سکوت
            "--proxy", f"http://127.0.0.1:{local_port}",
            "http://cp.cloudflare.com/",
            "--connect-timeout", "5", # مهلت ۵ ثانیه برای اتصال
            "-o", "/dev/null", # عدم ذخیره خروجی
            "-w", "%{time_connect}" # چاپ زمان اتصال
        ]
        
        curl_proc = subprocess.run(curl_command, capture_output=True, text=True, timeout=10)

        # اگر curl با موفقیت اجرا شد (کد خروجی 0)
        if curl_proc.returncode == 0:
            try:
                # تبدیل زمان اتصال به میلی‌ثانیه
                delay = int(float(curl_proc.stdout) * 1000)
                print(f"✅ SUCCESS: پینگ برای {proxy[:40]}... برابر است با: {delay}ms")
                return {"proxy": proxy, "status": "active", "delay": delay}
            except (ValueError, TypeError):
                # اگر خروجی curl عدد معتبری نبود
                return {"proxy": proxy, "status": "dead", "delay": -1}

        return {"proxy": proxy, "status": "dead", "delay": -1}

    except Exception:
        return {"proxy": proxy, "status": "dead", "delay": -1}
    finally:
        # اطمینان از بسته شدن فرآیند sing-box در هر حالتی
        if process:
            process.kill()
        if config_path.exists():
            config_path.unlink()

def main():
    print("🚀 شروع تست پراکسی‌های اصلی (V2Ray) با روش 'run'...")
    
    proxies_file_path = Path("output/fetched_proxies.txt")
    proxies_to_test = get_proxies_from_file(proxies_file_path)

    if not proxies_to_test:
        print("هیچ پراکسی برای تست یافت نشد.")
        save_json_to_file([], Path("output/github_results.json"))
        save_proxies_to_file([], Path("output/github_all.txt"))
        # ... (بقیه فایل‌های خالی)
        return

    working_proxies_results = []
    
    # کاهش تعداد workerها به دلیل سنگین‌تر بودن این روش تست
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(test_proxy, proxies_to_test)
    
    for result in results:
        if result["status"] == "active":
            working_proxies_results.append(result)
            
    working_proxies_results.sort(key=lambda p: p["delay"])
    
    final_proxy_strings = [p["proxy"] for p in working_proxies_results]
    
    json_output_path = Path("output/github_results.json")
    save_json_to_file(working_proxies_results, json_output_path)
    print(f"📄 نتایج کامل (پراکسی + پینگ) در فایل {json_output_path} ذخیره شد.")

    save_proxies_to_file(final_proxy_strings, Path("output/github_all.txt"))
    save_proxies_to_file(final_proxy_strings[:500], Path("output/github_top_500.txt"))
    save_proxies_to_file(final_proxy_strings[:100], Path("output/github_top_100.txt"))
    print("📄 لیست پراکسی‌های فعال در فایل‌های github_all.txt و ... ذخیره شد.")

if __name__ == "__main__":
    main()
