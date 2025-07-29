# scripts/02_test_hysteria.py

import subprocess
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import random
import string
import time
import os

# توابع کمکی را از فایل utils وارد می‌کنیم
from .utils import get_proxies_from_file, save_proxies_to_file, save_json_to_file

# مسیر فایل اجرایی کلاینت Hysteria
HYSTERIA_CLIENT_PATH = "./hysteria-client"

def generate_random_filename(prefix="temp_hy_config_", extension=".json"):
    """یک نام فایل تصادفی برای جلوگیری از تداخل در اجرای موازی ایجاد می‌کند."""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{random_str}{extension}"

def test_hysteria_proxy(proxy: str) -> dict:
    """
    ✅ آپدیت شده: پراکسی Hysteria را با اجرای کامل کلاینت و تست اتصال با curl می‌سنجد.
    """
    temp_config_filename = generate_random_filename()
    config_path = Path(temp_config_filename)
    
    # تعریف یک پورت محلی رندوم برای پراکسی SOCKS5
    local_port = random.randint(20001, 30000)

    # ساختار کانفیگ کامل برای اجرای کلاینت Hysteria
    # یک ورودی SOCKS5 محلی ایجاد می‌کند که تمام ترافیک را به سرور پراکسی اصلی می‌فرستد
    config = {
        "server": proxy,
        "insecure": True,
        "inbound": {
            "type": "socks5",
            "listen": f"127.0.0.1:{local_port}"
        }
    }
    
    process = None
    try:
        config_path.write_text(json.dumps(config), encoding='utf-8')
        
        # اجرای کلاینت Hysteria در پس‌زمینه
        command = [HYSTERIA_CLIENT_PATH, "client", "-c", str(config_path)]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # یک لحظه کوتاه برای اطمینان از اجرای کامل کلاینت
        time.sleep(2)

        # تست اتصال از طریق پراکسی محلی SOCKS5 با curl
        curl_command = [
            "curl",
            "-s",
            # ✅ استفاده از پراکسی socks5
            "--socks5-hostname", f"127.0.0.1:{local_port}",
            "http://cp.cloudflare.com/",
            "--connect-timeout", "5",
            "-o", "/dev/null",
            "-w", "%{time_connect}"
        ]
        
        curl_proc = subprocess.run(curl_command, capture_output=True, text=True, timeout=10)

        if curl_proc.returncode == 0:
            try:
                delay = int(float(curl_proc.stdout) * 1000)
                print(f"✅ SUCCESS: پینگ برای {proxy[:40]}... برابر است با: {delay}ms")
                return {"proxy": proxy, "status": "active", "delay": delay}
            except (ValueError, TypeError):
                return {"proxy": proxy, "status": "dead", "delay": -1}

        return {"proxy": proxy, "status": "dead", "delay": -1}

    except Exception:
        return {"proxy": proxy, "status": "dead", "delay": -1}
    finally:
        # اطمینان از بسته شدن فرآیند کلاینت در هر حالتی
        if process:
            process.kill()
        if config_path.exists():
            config_path.unlink()

def main():
    """
    تابع اصلی برای اجرای موازی تست‌ها، مرتب‌سازی و ذخیره نتایج.
    """
    print("🚀 شروع تست پراکسی‌های Hysteria با روش 'run'...")
    
    proxies_file_path = Path("output/fetched_hysteria.txt")
    proxies_to_test = get_proxies_from_file(proxies_file_path)

    if not proxies_to_test:
        print("هیچ پراکسی Hysteria برای تست یافت نشد.")
        save_json_to_file([], Path("output/hysteria_results.json"))
        save_proxies_to_file([], Path("output/hysteria_all.txt"))
        return

    working_proxies_results = []
    
    # کاهش تعداد workerها به دلیل سنگین‌تر بودن این روش تست
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(test_hysteria_proxy, proxies_to_test)
    
    for result in results:
        if result["status"] == "active":
            working_proxies_results.append(result)
            
    working_proxies_results.sort(key=lambda p: p["delay"])
    
    final_proxy_strings = [p["proxy"] for p in working_proxies_results]
    
    json_output_path = Path("output/hysteria_results.json")
    save_json_to_file(working_proxies_results, json_output_path)
    print(f"📄 نتایج کامل Hysteria (پراکسی + پینگ) در فایل {json_output_path} ذخیره شد.")

    txt_output_path = Path("output/hysteria_all.txt")
    save_proxies_to_file(final_proxy_strings, txt_output_path)
    print(f"📄 لیست پراکسی‌های فعال Hysteria در فایل {txt_output_path} ذخیره شد.")

if __name__ == "__main__":
    main()
