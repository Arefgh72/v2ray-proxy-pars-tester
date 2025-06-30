# استفاده از کتابخانه curl_cffi به جای requests برای جعل هویت مرورگر
from curl_cffi import requests
import base64
import os
from utils import log_error

# مسیر فایل‌های ورودی و خروجی
SUBSCRIPTIONS_FILE_PATH = 'config/subscriptions.txt'
RAW_PROXIES_OUTPUT_PATH = 'output/raw_proxies.txt'

def get_subscription_links():
    """
    لینک‌های سابسکریپشن را از فایل ورودی می‌خواند.
    """
    try:
        with open(SUBSCRIPTIONS_FILE_PATH, 'r') as f:
            links = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print(f"Found {len(links)} subscription links in '{SUBSCRIPTIONS_FILE_PATH}'.")
        return links
    except FileNotFoundError:
        log_error("Fetch Proxies", f"Subscription file not found: '{SUBSCRIPTIONS_FILE_PATH}'.")
        return []
    except Exception as e:
        log_error("Fetch Proxies", "Error reading subscription links.", f"{type(e).__name__}: {e}")
        return []

def fetch_and_decode_link(link: str) -> list[str]:
    """
    محتوای یک لینک را با جعل هویت مرورگر Chrome دریافت کرده و پردازش می‌کند.
    """
    # حذف بخش # از انتهای URL
    clean_link = link.split('#')[0].strip()
    try:
        print(f"Fetching: {clean_link[:80]}...")
        
        # ارسال درخواست با جعل هویت مرورگر کروم نسخه 110
        response = requests.get(clean_link, impersonate="chrome110", timeout=25)
        response.raise_for_status()
        
        content = response.text
        proxies = []

        # تلاش برای دیکد کردن محتوا به عنوان Base64
        try:
            decoded_content = base64.b64decode(content).decode('utf-8')
            proxies = decoded_content.splitlines()
            print(f"  -> Decoded as Base64.")
        # اگر شکست خورد، آن را به عنوان متن ساده پردازش کن
        except Exception:
            proxies = content.splitlines()
            print(f"  -> Processed as Plain Text.")

        # فیلتر کردن نهایی برای اطمینان از فرمت صحیح پروکسی‌ها
        valid_proxies = [p.strip() for p in proxies if p.strip().startswith(('vmess://', 'vless://', 'trojan://', 'ss://'))]
        print(f"  -> Found {len(valid_proxies)} valid proxies.")
        return valid_proxies

    except Exception as e:
        # ثبت خطای دقیق‌تر در صورت بروز مشکل در شبکه یا درخواست
        log_error("Fetch Proxies (Network)", f"Failed to fetch from link: {clean_link}", f"{type(e).__name__}: {e}")
        return []

def main():
    """
    تابع اصلی برای اجرای کامل فرآیند.
    """
    print("--- Running 01_fetch_proxies.py (Impersonating Chrome) ---")
    os.makedirs('output', exist_ok=True)
    
    subscription_links = get_subscription_links()
    if not subscription_links:
        print("No subscription links found. Exiting.")
        return

    all_proxies = []
    for link in subscription_links:
        all_proxies.extend(fetch_and_decode_link(link))

    # حذف پروکسی‌های تکراری
    unique_proxies = list(dict.fromkeys(all_proxies))
    print(f"\nTotal unique proxies fetched: {len(unique_proxies)}")

    # ذخیره نتایج
    with open(RAW_PROXIES_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        for proxy in unique_proxies:
            f.write(proxy + '\n')
    print(f"Successfully saved {len(unique_proxies)} proxies to '{RAW_PROXIES_OUTPUT_PATH}'.")
    print("--- Finished 01_fetch_proxies.py ---")

if __name__ == "__main__":
    main()
