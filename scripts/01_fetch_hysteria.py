# scripts/01_fetch_hysteria.py

from pathlib import Path
from base64 import b64decode
from curl_cffi.requests import get
from utils import get_proxies_from_file, save_proxies_to_file

def get_and_decode_proxies(url: str) -> list[str]:
    """
    از یک لینک اشتراک، پراکسی‌ها را دریافت کرده و به صورت هوشمند رمزگشایی می‌کند.
    """
    try:
        response = get(url, impersonate="chrome110", timeout=30)
        response.raise_for_status()
        content = response.content
        
        # ✅ منطق جدید: ابتدا تلاش برای دکود Base64
        try:
            decoded_content = b64decode(content).decode("utf-8")
        except (ValueError, TypeError):
            # اگر دکود Base64 شکست خورد، فرض می‌کنیم متن ساده است
            decoded_content = content.decode("utf-8")
            
        return decoded_content.strip().split("\n")
    except Exception as e:
        print(f"خطا در دریافت یا رمزگشایی از {url}: {e}")
        return []

def main():
    print("🚀 شروع جمع‌آوری پراکسی‌ها از منابع Hysteria (بدون فیلتر)...")
    subscription_file_path = Path("config/hysteria_subscriptions.txt")
    output_proxies_path = Path("output/fetched_hysteria.txt")
    subscription_links = get_proxies_from_file(subscription_file_path)
    all_proxies_from_hysteria_sources = set()
    
    for link in subscription_links:
        print(f"در حال دریافت از: {link}")
        proxies = get_and_decode_proxies(link)
        for proxy in proxies:
            proxy = proxy.strip()
            if proxy:
                all_proxies_from_hysteria_sources.add(proxy)

    save_proxies_to_file(list(all_proxies_from_hysteria_sources), output_proxies_path)
    print(f"✅ پراکسی‌های دریافت شده از منابع Hysteria با موفقیت در {output_proxies_path} ذخیره شدند.")
    print(f"تعداد پراکسی‌های منحصر به فرد یافت شده: {len(all_proxies_from_hysteria_sources)}")

if __name__ == "__main__":
    main()
