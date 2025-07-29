# scripts/02_test_proxies.py

import subprocess
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import random
import string

# توابع کمکی را از فایل utils وارد می‌کنیم
from .utils import get_proxies_from_file, save_proxies_to_file, save_json_to_file

# مسیر فایل اجرایی sing-box که در ورک‌فلو دانلود می‌شود
SING_BOX_PATH = "./sing-box"

def generate_random_filename(prefix="temp_sb_config_", extension=".json"):
    """یک نام فایل تصادفی برای جلوگیری از تداخل در اجرای موازی ایجاد می‌کند."""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{random_str}{extension}"

def test_proxy(proxy: str) -> dict:
    """
    یک پراکسی (VLESS, VMess, etc.) را با استفاده از sing-box تست می‌کند.
    یک دیکشنری شامل اطلاعات پراکسی، وضعیت و تأخیر (delay) برمی‌گرداند.
    """
    temp_config_filename = generate_random_filename()
    config_path = Path(temp_config_filename)

    # ساختار کانفیگ مورد نیاز برای sing-box
    config = {
        "outbounds": [
            {
                "type": "urltest",
                "tag": "urltest",
                "outbounds": [proxy],
                "url": "http://cp.cloudflare.com/",
                "interval": "10s",
                "tolerance": 100
            }
        ]
    }

    try:
        config_path.write_text(json.dumps(config), encoding='utf-8')
        
        command = [
            SING_BOX_PATH,
            "urltest",
            "-c",
            str(config_path)
        ]
        
        proc = subprocess.run(
            command,
            timeout=10,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        if proc.returncode != 0:
            return {"proxy": proxy, "status": "dead", "delay": -1}

        delay_match = re.search(r"delay (\d+)ms", proc.stdout)
        
        if delay_match:
            delay = int(delay_match.group(1))
            print(f"✅ SUCCESS: پینگ برای {proxy[:40]}... برابر است با: {delay}ms")
            return {"proxy": proxy, "status": "active", "delay": delay}
        else:
            return {"proxy": proxy, "status": "dead", "delay": -1}

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return {"proxy": proxy, "status": "dead", "delay": -1}
    except Exception as e:
        print(f"خطای ناشناخته در تست {proxy[:40]}... : {e}")
        return {"proxy": proxy, "status": "dead", "delay": -1}
    finally:
        if config_path.exists():
            config_path.unlink()

def main():
    """
    تابع اصلی برای اجرای موازی تست‌ها، مرتب‌سازی و ذخیره نتایج.
    """
    print("🚀 شروع تست پراکسی‌های اصلی (V2Ray)...")
    
    proxies_file_path = Path("output/fetched_proxies.txt")
    proxies_to_test = get_proxies_from_file(proxies_file_path)

    if not proxies_to_test:
        print("هیچ پراکسی برای تست یافت نشد. فایل‌های خروجی خالی ایجاد می‌شوند.")
        save_json_to_file([], Path("output/github_results.json"))
        save_proxies_to_file([], Path("output/github_all.txt"))
        save_proxies_to_file([], Path("output/github_top_100.txt"))
        save_proxies_to_file([], Path("output/github_top_500.txt"))
        return

    working_proxies_results = []
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        results = executor.map(test_proxy, proxies_to_test)
    
    for result in results:
        if result["status"] == "active":
            working_proxies_results.append(result)
            
    working_proxies_results.sort(key=lambda p: p["delay"])
    
    final_proxy_strings = [p["proxy"] for p in working_proxies_results]
    
    # ذخیره نتایج در فرمت JSON برای استفاده در اسکریپت ادغام‌گر
    json_output_path = Path("output/github_results.json")
    save_json_to_file(working_proxies_results, json_output_path)
    print(f"📄 نتایج کامل (پراکسی + پینگ) در فایل {json_output_path} ذخیره شد.")

    # ذخیره فایل‌های متنی ساده برای استفاده مستقیم
    save_proxies_to_file(final_proxy_strings, Path("output/github_all.txt"))
    save_proxies_to_file(final_proxy_strings[:500], Path("output/github_top_500.txt"))
    save_proxies_to_file(final_proxy_strings[:100], Path("output/github_top_100.txt"))
    print("📄 لیست پراکسی‌های فعال در فایل‌های github_all.txt، github_top_500.txt و github_top_100.txt ذخیره شد.")

if __name__ == "__main__":
    main()
