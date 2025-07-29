# scripts/utils.py

import json
from pathlib import Path

def get_proxies_from_file(path: Path) -> list[str]:
    """
    پراکسی‌ها را از یک فایل متنی می‌خواند و خطوط خالی را نادیده می‌گیرد.
    """
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        # فقط خطوطی را که پس از حذف فاصله‌های اضافی، خالی نیستند، برمی‌گرداند
        return [line.strip() for line in f if line.strip()]

def save_proxies_to_file(proxies: list[str], path: Path):
    """
    لیستی از پراکسی‌ها را در یک فایل متنی ذخیره می‌کند، هر کدام در یک خط.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(proxies))

def save_json_to_file(data: list[dict], path: Path):
    """
    داده‌های ساختار یافته (لیستی از دیکشنری‌ها) را در یک فایل JSON ذخیره می‌کند.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def save_summary_log(path: Path, **kwargs):
    """
    یک لاگ خلاصه کامل و تفکیک‌شده ایجاد می‌کند.
    آمار هر بخش را به صورت جداگانه دریافت و در فایل نهایی می‌نویسد.
    """
    summary_parts = []
    
    if 'hysteria_stats' in kwargs:
        stats = kwargs['hysteria_stats']
        summary_parts.append(
            f"--- Hysteria Test Summary ---\n"
            f"Total Fetched: {stats.get('fetched', 0)}\n"
            f"Working: {stats.get('working', 0)}\n"
        )
        
    if 'v2ray_stats' in kwargs:
        stats = kwargs['v2ray_stats']
        summary_parts.append(
            f"--- V2Ray/Main Test Summary ---\n"
            f"Total Fetched: {stats.get('fetched', 0)}\n"
            f"Working: {stats.get('working', 0)}\n"
        )
        
    if 'final_stats' in kwargs:
        stats = kwargs['final_stats']
        summary_parts.append(
            f"--- Final Merged Summary ---\n"
            f"Total Unique Working Proxies: {stats.get('total_unique', 0)}\n"
        )
        
    summary_content = "\n".join(summary_parts)
    
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(summary_content, encoding='utf-8')
    print("\n" + summary_content)
    print(f"✅ خلاصه کامل در فایل {path} ذخیره شد.")
