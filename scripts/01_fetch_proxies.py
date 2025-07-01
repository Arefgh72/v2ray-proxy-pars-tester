import base64
import requests
import os
from utils import log_error

SUBSCRIPTIONS_FILE_PATH = 'config/subscriptions.txt'
RAW_PROXIES_OUTPUT_PATH = 'output/raw_proxies.txt'

def get_subscription_links():
    # ... (بدون تغییر) ...
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
    clean_link = link.split('#')[0].strip()
    try:
        print(f"Fetching: {clean_link[:80]}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
            'Accept': 'text/plain'
        }
        response = requests.get(clean_link, timeout=20, headers=headers)
        response.raise_for_status()
        
        content = response.text
        proxies = []

        try:
            decoded_content = base64.b64decode(content).decode('utf-8')
            proxies = decoded_content.splitlines()
            print(f"  -> Decoded as Base64.")
        except (base64.binascii.Error, UnicodeDecodeError):
            proxies = content.splitlines()
            print(f"  -> Processed as Plain Text.")

        # --- تغییر اصلی اینجاست: اضافه کردن پروتکل‌های جدید ---
        VALID_PROTOCOLS = ('vmess://', 'vless://', 'trojan://', 'ss://', 'hy://', 'hysteria://', 'hy2://')
        valid_proxies = [p.strip() for p in proxies if p.strip().startswith(VALID_PROTOCOLS)]
        
        print(f"  -> Found {len(valid_proxies)} valid proxies.")
        return valid_proxies

    except requests.exceptions.RequestException as e:
        log_error("Fetch Proxies (Network)", f"Failed to fetch from link: {clean_link}", str(e))
        return []
    except Exception as e:
        log_error("Fetch Proxies (Other)", f"An unexpected error with link: {clean_link}", str(e))
        return []

def main():
    # ... (بدون تغییر) ...
    print("--- Running 01_fetch_proxies.py ---")
    os.makedirs('output', exist_ok=True)
    subscription_links = get_subscription_links()
    if not subscription_links:
        print("No subscription links found. Exiting.")
        with open(RAW_PROXIES_OUTPUT_PATH, 'w') as f: f.write('')
        return

    all_proxies = []
    for link in subscription_links:
        all_proxies.extend(fetch_and_decode_link(link))

    unique_proxies = list(dict.fromkeys(all_proxies))
    print(f"\nTotal unique proxies fetched: {len(unique_proxies)}")

    with open(RAW_PROXIES_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        for proxy in unique_proxies:
            f.write(proxy + '\n')
    print(f"Successfully saved {len(unique_proxies)} proxies to '{RAW_PROXIES_OUTPUT_PATH}'.")
    print("--- Finished 01_fetch_proxies.py ---")

if __name__ == "__main__":
    main()
