# --- تغییر اصلی: استفاده از curl_cffi ---
from curl_cffi.requests import get
import base64
import os
from utils import log_error

SUBSCRIPTIONS_FILE_PATH = 'config/subscriptions.txt'
RAW_PROXIES_OUTPUT_PATH = 'output/raw_proxies.txt'

def get_subscription_links():
    try:
        with open(SUBSCRIPTIONS_FILE_PATH, 'r') as f:
            links = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print(f"Found {len(links)} subscription links in '{SUBSCRIPTIONS_FILE_PATH}'.")
        return links
    except Exception as e:
        log_error("Fetch Proxies", "Error reading subscription file.", str(e))
        return []

def fetch_and_decode_link(link: str) -> list[str]:
    clean_link = link.split('#')[0].strip()
    try:
        print(f"Fetching: {clean_link[:80]}...")
        # --- تغییر اصلی: استفاده از impersonate برای تقلید از مرورگر کروم ---
        response = get(clean_link, timeout=30, impersonate="chrome110")
        response.raise_for_status()
        
        content = response.text
        proxies = []

        try:
            decoded_content = base64.b64decode(content).decode('utf-8')
            proxies = decoded_content.splitlines()
            print(f"  -> Decoded as Base64.")
        except Exception:
            proxies = content.splitlines()
            print(f"  -> Processed as Plain Text.")

        VALID_PROTOCOLS = ('vmess://', 'vless://', 'trojan://', 'ss://', 'hy://', 'hysteria://', 'hy2://')
        valid_proxies = [p.strip() for p in proxies if p.strip().startswith(VALID_PROTOCOLS)]
        print(f"  -> Found {len(valid_proxies)} valid proxies.")
        return valid_proxies

    except Exception as e:
        log_error("Fetch Proxies (Network)", f"Failed to fetch from link: {clean_link}", str(e))
        return []

def main():
    print("--- Running 01_fetch_proxies.py (with Browser Impersonation) ---")
    os.makedirs('output', exist_ok=True)
    subscription_links = get_subscription_links()
    if not subscription_links:
        print("No subscription links found."); return

    all_proxies = []
    for link in subscription_links:
        all_proxies.extend(fetch_and_decode_link(link))

    unique_proxies = list(dict.fromkeys(all_proxies))
    print(f"\nTotal unique proxies fetched: {len(unique_proxies)}")

    with open(RAW_PROXIES_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(unique_proxies))
    print(f"Successfully saved {len(unique_proxies)} proxies to '{RAW_PROXIES_OUTPUT_PATH}'.")
    print("--- Finished 01_fetch_proxies.py ---")

if __name__ == "__main__":
    main()
