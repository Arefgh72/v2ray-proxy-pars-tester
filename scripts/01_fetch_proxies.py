import base64
import requests
import os
from utils import log_error

# --- تنظیمات ---
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
        log_error("Fetch Proxies", "Error reading subscription links.", str(e))
        return []

def fetch_and_decode_link(link: str) -> list[str]:
    """
    محتوای یک لینک سابسکریپشن را دریافت می‌کند.
    ابتدا تلاش می‌کند با Base64 دیکد کند، اگر نشد به عنوان متن ساده در نظر می‌گیرد.
    """
    try:
        print(f"Fetching: {link[:70]}...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'}
        response = requests.get(link, timeout=20, headers=headers)
        response.raise_for_status()
        
        content = response.text
        proxies = []

        try:
            # تلاش اول: دیکد کردن با Base64
            decoded_content = base64.b64decode(content).decode('utf-8')
            proxies = decoded_content.splitlines()
            print(f"  -> Decoded as Base64.")
        except (base64.binascii.Error, UnicodeDecodeError):
            # اگر دیکد Base64 شکست خورد، محتوا را به عنوان متن ساده در نظر بگیر
            proxies = content.splitlines()
            print(f"  -> Could not decode as Base64, processing as Plain Text.")

        # فیلتر کردن نهایی برای اطمینان از فرمت صحیح پروکسی‌ها
        valid_proxies = [p.strip() for p in proxies if p.strip().startswith(('vmess://', 'vless://', 'trojan://', 'ss://'))]
        print(f"  -> Found {len(valid_proxies)} valid proxies.")
        return valid_proxies

    except requests.exceptions.RequestException as e:
        log_error("Fetch Proxies (Network)", f"Failed to fetch from link: {link}", str(e))
        return []
    except Exception as e:
        log_error("Fetch Proxies (Other)", f"An unexpected error with link: {link}", str(e))
        return []

def main():
    """
    تابع اصلی برای اجرای کامل فرآیند استخراج پروکسی‌ها.
    """
    print("--- Running 01_fetch_proxies.py ---")
    os.makedirs('output', exist_ok=True)

    subscription_links = get_subscription_links()
    if not subscription_links:
        print("No subscription links found. Exiting.")
        with open(RAW_PROXIES_OUTPUT_PATH, 'w') as f: f.write('')
        return

    all_proxies = []
    for link in subscription_links:
        proxies_from_link = fetch_and_decode_link(link)
        all_proxies.extend(proxies_from_link)

    unique_proxies = list(dict.fromkeys(all_proxies))
    print(f"\nTotal unique proxies fetched: {len(unique_proxies)}")

    try:
        with open(RAW_PROXIES_OUTPUT_PATH, 'w', encoding='utf-8') as f:
            for proxy in unique_proxies:
                f.write(proxy + '\n')
        print(f"Successfully saved {len(unique_proxies)} unique proxies to '{RAW_PROXIES_OUTPUT_PATH}'.")
    except Exception as e:
        log_error("Save Raw Proxies", f"Failed to save proxies to '{RAW_PROXIES_OUTPUT_PATH}'.", str(e))

    print("--- Finished 01_fetch_proxies.py ---")

if __name__ == "__main__":
    main()
