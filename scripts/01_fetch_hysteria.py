# scripts/01_fetch_hysteria.py

from pathlib import Path
from base64 import b64decode
from curl_cffi.requests import get
from utils import get_proxies_from_file, save_proxies_to_file

def get_and_decode_proxies(url: str) -> list[str]:
    """
    از یک لینک اشتراک، پراکسی‌ها را دریافت و رمزگشایی می‌کند.
    """
    try:
        # برای جلوگیری از مسدود شدن، درخواست را شبیه مرورگر ارسال می‌کنیم.
        response = get(url, impersonate="chrome110", timeout=30)
        response.raise_for_status()
        
        # محتوای Base64 را رمزگشایی می‌کنیم.
        decoded_content = b64decode(response.content).decode("utf-8")
        return decoded_content.strip().split("\n")
    except Exception as e:
        print(f"خطا در دریافت یا رمزگشایی از {url}: {e}")
        return []

def main():
    """
    تابع اصلی برای اجرای فرآیند جمع‌آوری پراکسی‌ها از منابع Hysteria.
    """
    print("🚀 شروع جمع‌آوری پراکسی‌ها از منابع Hysteria (بدون فیلتر)...")
    
    # مسیر فایل ورودی که شما ساختید.
    subscription_file_path = Path("config/hysteria_subscriptions.txt")
    
    # مسیر فایل خروجی که پراکسی‌های جمع‌آوری شده در آن ذخیره می‌شوند.
    output_proxies_path = Path("output/fetched_hysteria.txt")
    
    # خواندن لینک‌های اشتراک از فایل.
    subscription_links = get_proxies_from_file(subscription_file_path)
    
    # از Set استفاده می‌کنیم تا پراکسی‌های تکراری به صورت خودکار حذف شوند.
    all_proxies_from_hysteria_sources = set()
    
    for link in subscription_links:
        print(f"در حال دریافت از: {link}")
        proxies = get_and_decode_proxies(link)
        for proxy in proxies:
            proxy = proxy.strip()
            # ✅ مطابق دستور شما، فیلتر حذف شد. هر پراکسی معتبری اضافه می‌شود.
            if proxy:
                all_proxies_from_hysteria_sources.add(proxy)

    # ذخیره لیست نهایی و منحصر به فرد پراکسی‌ها در فایل خروجی.
    save_proxies_to_file(list(all_proxies_from_hysteria_sources), output_proxies_path)
    print(f"✅ پراکسی‌های دریافت شده از منابع Hysteria با موفقیت در {output_proxies_path} ذخیره شدند.")
    print(f"تعداد پراکسی‌های منحصر به فرد یافت شده: {len(all_proxies_from_hysteria_sources)}")

if __name__ == "__main__":
    main()
