# scripts/03_merge_and_sort.py

import json
from pathlib import Path

# توابع کمکی را از فایل utils وارد می‌کنیم
from .utils import save_proxies_to_file

def load_results_from_json(path: Path) -> list:
    """
    نتایج تست را از یک فایل JSON بارگذاری می‌کند.
    در صورت عدم وجود فایل، یک لیست خالی برمی‌گرداند.
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

def main():
    """
    تابع اصلی برای ادغام، مرتب‌سازی و ذخیره پراکسی‌های نهایی.
    """
    print("🚀 شروع فرآیند ادغام و مرتب‌سازی نهایی پراکسی‌ها...")

    # تعریف مسیر فایل‌های ورودی JSON
    hysteria_results_path = Path("output/hysteria_results.json")
    github_results_path = Path("output/github_results.json")

    # بارگذاری نتایج از هر دو فایل
    hysteria_results = load_results_from_json(hysteria_results_path)
    github_results = load_results_from_json(github_results_path)

    # ادغام نتایج هر دو تستر در یک لیست واحد
    all_results = hysteria_results + github_results
    
    if not all_results:
        print("هیچ پراکسی فعالی برای ادغام یافت نشد. عملیات متوقف شد.")
        # ایجاد فایل‌های خروجی خالی
        save_proxies_to_file([], Path("output/mix_all.txt"))
        save_proxies_to_file([], Path("output/mix_top100.txt"))
        save_proxies_to_file([], Path("output/mix_top500.txt"))
        save_proxies_to_file([], Path("output/mix_top1000.txt"))
        return

    # مرتب‌سازی لیست کامل بر اساس پینگ (delay) از کم به زیاد
    all_results.sort(key=lambda p: p.get("delay", 9999))

    # حذف پراکسی‌های تکراری احتمالی با حفظ ترتیب
    unique_proxies = []
    seen_proxies = set()
    for result in all_results:
        proxy_str = result.get("proxy")
        if proxy_str and proxy_str not in seen_proxies:
            unique_proxies.append(proxy_str)
            seen_proxies.add(proxy_str)
    
    # تعریف مسیر فایل‌های خروجی نهایی
    output_path_all = Path("output/mix_all.txt")
    output_path_top100 = Path("output/mix_top100.txt")
    output_path_top500 = Path("output/mix_top500.txt")
    output_path_top1000 = Path("output/mix_top1000.txt")

    # ذخیره پراکسی‌های مرتب‌شده در فایل‌های خروجی
    save_proxies_to_file(unique_proxies, output_path_all)
    save_proxies_to_file(unique_proxies[:100], output_path_top100)
    save_proxies_to_file(unique_proxies[:500], output_path_top500)
    save_proxies_to_file(unique_proxies[:1000], output_path_top1000)

    print("\n--- خلاصه عملیات ادغام ---")
    print(f"تعداد کل پراکسی‌های فعال منحصر به فرد: {len(unique_proxies)}")
    print(f"✅ فایل‌های خروجی mix_all, mix_top100, mix_top500, و mix_top1000 با موفقیت ایجاد شدند.")


if __name__ == "__main__":
    main()
