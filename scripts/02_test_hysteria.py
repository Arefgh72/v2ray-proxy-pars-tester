# scripts/02_test_hysteria.py

import subprocess
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import random
import string

# توابع کمکی را از فایل utils وارد می‌کنیم
from .utils import get_proxies_from_file, save_proxies_to_file, save_json_to_file

# مسیر فایل اجرایی کلاینت Hysteria که در ورک‌فلو دانلود می‌شود
HYSTERIA_CLIENT_PATH = "./hysteria-client"

def generate_random_filename(prefix="temp_hy_config_", extension=".json"):
    """یک نام فایل تصادفی برای جلوگیری از تداخل در اجرای موازی ایجاد می‌کند."""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{random_str}{extension}"

def test_hysteria_proxy(proxy: str) -> dict:
    """
    یک پراکسی Hysteria را با استفاده از کلاینت رسمی آن تست می‌کند.
    یک دیکشنری شامل اطلاعات پراکسی، وضعیت و تأخیر (delay) برمی‌گرداند.
    """
    # برای هر تست یک فایل کانفیگ موقت با نام تصادفی ایجاد می‌کنیم
    temp_config_filename = generate_random_filename()
    config_path = Path(temp_config_filename)

    # ساختار کانفیگ مورد نیاز برای کلاینت Hysteria نسخه ۲
    config = {
        "server": proxy,
        "insecure": True,
        "timeout": 8,
        "retry": 0,
        "speed_test": {
            "enabled": True,
            "url": "http://cachefly.cachefly.net/100mb.test", # یک فایل استاندارد برای تست سرعت
            "bytes": 1048576 # تست دانلود ۱ مگابایت
        }
    }
    
    try:
        # نوشتن کانفیگ در فایل موقت
        config_path.write_text(json.dumps(config), encoding='utf-8')
        
        # دستور اجرایی برای تست پراکسی با استفاده از کلاینت رسمی
        command = [
            HYSTERIA_CLIENT_PATH,
            "client",
            "-c",
            str(config_path)
        ]
        
        # اجرای دستور با مهلت زمانی کلی ۱۵ ثانیه
        # اگر پراکسی کار نکند یا فرمت آن Hysteria نباشد، این دستور خطا می‌دهد یا تایم‌اوت می‌شود
        proc = subprocess.run(
            command,
            timeout=15,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        # اگر دستور با موفقیت اجرا نشد، پراکسی را ناموفق در نظر بگیر
        if proc.returncode != 0:
            return {"proxy": proxy, "status": "dead", "delay": -1}

        # جستجو برای پینگ در خروجی استاندارد کلاینت
        # مثال خروجی: "Ping: 123ms"
        delay_match = re.search(r"Ping: (\d+)", proc.stdout)
        
        if delay_match:
            delay = int(delay_match.group(1))
            print(f"✅ SUCCESS: پینگ برای {proxy[:40]}... برابر است با: {delay}ms")
            return {"proxy": proxy, "status": "active", "delay": delay}
        else:
            # اگر پینگ در خروجی یافت نشد، پراکسی را ناموفق در نظر بگیر
            return {"proxy": proxy, "status": "dead", "delay": -1}

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        # اگر پراکسی در زمان مشخص پاسخ ندهد یا کلاینت با خطا خارج شود
        return {"proxy": proxy, "status": "dead", "delay": -1}
    except Exception as e:
        # سایر خطاهای پیش‌بینی نشده
        print(f"خطای ناشناخته در تست {proxy[:40]}... : {e}")
        return {"proxy": proxy, "status": "dead", "delay": -1}
    finally:
        # در هر صورت، فایل کانفیگ موقت را در پایان پاک می‌کنیم
        if config_path.exists():
            config_path.unlink()

def main():
    """
    تابع اصلی برای اجرای موازی تست‌ها، مرتب‌سازی و ذخیره نتایج.
    """
    print("🚀 شروع تست پراکسی‌های موجود در لیست Hysteria...")
    
    proxies_file_path = Path("output/fetched_hysteria.txt")
    proxies_to_test = get_proxies_from_file(proxies_file_path)

    if not proxies_to_test:
        print("هیچ پراکسی برای تست یافت نشد. فایل‌های خروجی خالی ایجاد می‌شوند.")
        save_proxies_to_file([], Path("output/hysteria_all.txt"))
        save_json_to_file([], Path("output/hysteria_results.json"))
        return

    working_proxies_results = []
    
    # اجرای موازی تست‌ها برای افزایش سرعت
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(test_hysteria_proxy, proxies_to_test)
    
    for result in results:
        if result["status"] == "active":
            working_proxies_results.append(result)
            
    # مرتب‌سازی پراکسی‌های فعال بر اساس تأخیر (پینگ) از کم به زیاد
    working_proxies_results.sort(key=lambda p: p["delay"])
    
    # استخراج رشته پراکسی‌های مرتب‌شده برای فایل txt
    final_proxy_strings = [p["proxy"] for p in working_proxies_results]
    
    # **ذخیره نتایج در دو فرمت**
    # ۱. فایل JSON برای استفاده در اسکریپت ادغام‌گر
    json_output_path = Path("output/hysteria_results.json")
    save_json_to_file(working_proxies_results, json_output_path)
    print(f"📄 نتایج کامل (پراکسی + پینگ) در فایل {json_output_path} ذخیره شد.")

    # ۲. فایل متنی ساده برای استفاده مستقیم
    txt_output_path = Path("output/hysteria_all.txt")
    save_proxies_to_file(final_proxy_strings, txt_output_path)
    print(f"📄 لیست پراکسی‌های فعال در فایل {txt_output_path} ذخیره شد.")

    # چاپ خلاصه نتایج
    print("\n--- خلاصه تست Hysteria ---")
    print(f"تعداد کل پراکسی‌های تست شده: {len(proxies_to_test)}")
    print(f"تعداد پراکسی‌های فعال: {len(working_proxies_results)}")
    print(f"تعداد پراکسی‌های غیرفعال: {len(proxies_to_test) - len(working_proxies_results)}")

if __name__ == "__main__":
    main()
