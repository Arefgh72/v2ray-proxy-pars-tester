import base64
import requests
import os
from utils import log_error

# --- تنظیمات ---
# مسیر فایل ورودی که لینک‌های سابسکریپشن در آن قرار دارد
SUBSCRIPTIONS_FILE_PATH = 'config/subscriptions.txt'
# مسیر فایل خروجی موقت که تمام پروکسی‌های خام در آن ذخیره می‌شوند
RAW_PROXIES_OUTPUT_PATH = 'output/raw_proxies.txt'

def get_subscription_links():
    """
    لینک‌های سابسکریپشن را از فایل ورودی می‌خواند و برمی‌گرداند.
    خطوط خالی و کامنت‌ها (#) را نادیده می‌گیرد.
    """
    try:
        with open(SUBSCRIPTIONS_FILE_PATH, 'r') as f:
            links = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print(f"Found {len(links)} subscription links in '{SUBSCRIPTIONS_FILE_PATH}'.")
        return links
    except FileNotFoundError:
        log_error(
            stage="Fetch Proxies",
            message=f"Subscription file not found at '{SUBSCRIPTIONS_FILE_PATH}'. Please create it."
        )
        return []
    except Exception as e:
        log_error(
            stage="Fetch Proxies",
            message="An unexpected error occurred while reading subscription links.",
            error_details=str(e)
        )
        return []

def fetch_and_decode_link(link: str) -> list[str]:
    """
    محتوای یک لینک سابسکریپشن را دریافت، با Base64 دیکد، و به لیستی از پروکسی‌ها تبدیل می‌کند.
    """
    try:
        print(f"Fetching: {link[:50]}...")
        # یک User-Agent معتبر اضافه می‌کنیم تا برخی سرورها درخواست را بلاک نکنند
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'}
        response = requests.get(link, timeout=20, headers=headers)
        response.raise_for_status()  # اگر کد وضعیت خطا بود (مثلاً 404), متوقف می‌شود

        # دیکد کردن محتوای Base64
        decoded_content = base64.b64decode(response.content).decode('utf-8')
        
        # جدا کردن پروکسی‌ها بر اساس خط جدید و فیلتر کردن لینک‌های معتبر
        proxies = [p.strip() for p in decoded_content.splitlines() if p.strip().startswith(('vmess://', 'vless://', 'trojan://', 'ss://'))]
        print(f"  -> Found {len(proxies)} valid proxies.")
        return proxies

    except requests.exceptions.RequestException as e:
        log_error("Fetch Proxies (Network)", f"Failed to fetch from link: {link}", str(e))
        return []
    except (base64.binascii.Error, UnicodeDecodeError) as e:
        log_error("Fetch Proxies (Decoding)", f"Failed to decode content from link: {link}", str(e))
        return []
    except Exception as e:
        log_error("Fetch Proxies (Other)", f"An unexpected error occurred with link: {link}", str(e))
        return []

def main():
    """
    تابع اصلی برای اجرای کامل فرآیند استخراج پروکسی‌ها.
    """
    print("--- Running 01_fetch_proxies.py ---")
    
    # اطمینان از وجود پوشه output
    os.makedirs('output', exist_ok=True)

    subscription_links = get_subscription_links()
    if not subscription_links:
        print("No subscription links found. Exiting.")
        # یک فایل خالی ایجاد می‌کنیم تا مراحل بعدی با خطا مواجه نشوند
        with open(RAW_PROXIES_OUTPUT_PATH, 'w') as f:
            f.write('')
        return

    all_proxies = []
    for link in subscription_links:
        proxies_from_link = fetch_and_decode_link(link)
        all_proxies.extend(proxies_from_link)

    # حذف پروکسی‌های تکراری برای جلوگیری از تست‌های اضافه
    unique_proxies = list(dict.fromkeys(all_proxies))
    
    print(f"\nTotal unique proxies fetched: {len(unique_proxies)}")

    # ذخیره پروکسی‌های منحصر به فرد در فایل خروجی
    try:
        with open(RAW_PROXIES_OUTPUT_PATH, 'w', encoding='utf-8') as f:
            for proxy in unique_proxies:
                f.write(proxy + '\n')
        print(f"Successfully saved {len(unique_proxies)} unique proxies to '{RAW_PROXIES_OUTPUT_PATH}'.")
    except Exception as e:
        log_error(
            stage="Save Raw Proxies",
            message=f"Failed to save proxies to '{RAW_PROXIES_OUTPUT_PATH}'.",
            error_details=str(e)
        )

    print("--- Finished 01_fetch_proxies.py ---")

if __name__ == "__main__":
    # این بخش فقط زمانی اجرا می‌شود که اسکریپت به صورت مستقیم ران شود
    # برای تست کردن اسکریپت به صورت مستقل عالی است
    # قبل از اجرای این فایل، باید فایل utils.py در همان پوشه (scripts) وجود داشته باشد
    main()
