# scripts/03_merge_and_sort.py

import json
from pathlib import Path

# توابع کمکی را از فایل utils وارد می‌کنیم
from .utils import save_proxies_to_file, save_summary_log

def load_results_from_json(path: Path) -> list:
    """
    نتایج تست را از یک فایل JSON بارگذاری می‌کند.
    """
    if not path.exists():
        print(f"فایل {path} یافت نشد، از آن صرف نظر می‌شود.")
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"خطا در خواندن فایل {path}: {e}")
        return []
        
def count_lines_in_file(path: Path) -> int:
    """تعداد خطوط غیرخالی یک فایل را شمارش می‌کند."""
    if not path.exists():
        return 0
    with open(path, 'r', encoding='utf-8') as f:
        return len([line for line in f if line.strip()])

def main():
    """
    تابع اصلی برای ادغام، مرتب‌سازی و ذخیره پراکسی‌های نهایی و لاگ کامل.
    """
    print("🚀 شروع فرآیند ادغام و مرتب‌سازی نهایی پراکسی‌ها...")

    # --- خواندن فایل‌ها برای محاسبه آمار دقیق ---
    total_fetched_hysteria = count_lines_in_file(Path("output/fetched_hysteria.txt"))
    total_fetched_v2ray = count_lines_in_file(Path("output/fetched_proxies.txt"))

    hysteria_results = load_results_from_json(Path("output/hysteria_results.json"))
    github_results = load_results_from_json(Path("output/github_results.json"))

    # --- ادغام و مرتب‌سازی ---
    all_results = hysteria_results + github_results
    
    if not all_results:
        print("هیچ پراکسی فعالی برای ادغام یافت نشد.")
        stats_hy = {'fetched': total_fetched_hysteria, 'working': 0}
        stats_v2 = {'fetched': total_fetched_v2ray, 'working': 0}
        stats_final = {'total_unique': 0}
        save_summary_log(Path("output/final_summary.log"), hysteria_stats=stats_hy, v2ray_stats=stats_v2, final_stats=stats_final)
        # ایجاد فایل‌های خروجی خالی
        save_proxies_to_file([], Path("output/mix_all.txt"))
        save_proxies_to_file([], Path("output/mix_top100.txt"))
        save_proxies_to_file([], Path("output/mix_top500.txt"))
        save_proxies_to_file([], Path("output/mix_top1000.txt"))
        return

    all_results.sort(key=lambda p: p.get("delay", 9999))

    unique_proxies = []
    seen_proxies = set()
    for result in all_results:
        proxy_str = result.get("proxy")
        if proxy_str and proxy_str not in seen_proxies:
            unique_proxies.append(proxy_str)
            seen_proxies.add(proxy_str)
    
    # --- ذخیره فایل‌های پراکسی ---
    save_proxies_to_file(unique_proxies, Path("output/mix_all.txt"))
    save_proxies_to_file(unique_proxies[:100], Path("output/mix_top100.txt"))
    save_proxies_to_file(unique_proxies[:500], Path("output/mix_top500.txt"))
    save_proxies_to_file(unique_proxies[:1000], Path("output/mix_top1000.txt"))
    print(f"✅ فایل‌های خروجی mix با {len(unique_proxies)} پراکسی منحصر به فرد ایجاد شدند.")

    # --- استفاده از تابع جدید برای ذخیره لاگ کامل و دقیق ---
    hysteria_stats = {'fetched': total_fetched_hysteria, 'working': len(hysteria_results)}
    v2ray_stats = {'fetched': total_fetched_v2ray, 'working': len(github_results)}
    final_stats = {'total_unique': len(unique_proxies)}
    
    save_summary_log(Path("output/final_summary.log"), hysteria_stats=hysteria_stats, v2ray_stats=v2ray_stats, final_stats=final_stats)

if __name__ == "__main__":
    main()
