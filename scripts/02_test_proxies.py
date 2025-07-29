# scripts/02_test_proxies.py

import subprocess
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import signal
import psutil
import time

# ✅ تمام ثابت‌ها و توابع کمکی دقیقا از فایل شما کپی شده‌اند
TEMP_DIR = 'temp_configs'
LOCAL_SOCKS_PORT_START = 2080
TEST_URL = 'https://www.youtube.com/' # استفاده از یک URL استاندارد برای تست
PROGRESS_UPDATE_INTERVAL = 100
DEBUG_MODE = False

from .utils import get_proxies_from_file, save_proxies_to_file, save_json_to_file

def kill_proc_tree(pid, sig=signal.SIGTERM, include_parent=True):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.send_signal(sig)
        if include_parent:
            parent.send_signal(sig)
    except psutil.NoSuchProcess:
        pass

# ✅ تابع تست دقیقا با منطق فایل شما، فقط خروجی آن تغییر کرده است
def test_proxy(proxy, index, total_proxies):
    # استفاده از پورت ترتیبی، دقیقا مانند فایل شما
    local_port = LOCAL_SOCKS_PORT_START + index
    config_path = Path(TEMP_DIR) / f"config_{local_port}.json"
    
    config = {
        "log": {"disabled": True},
        "inbounds": [{"type": "http", "tag": "http-in", "listen": "127.0.0.1", "listen_port": local_port}],
        "outbounds": [{"type": "proxy", "tag": "proxy", "url": proxy}],
        "routing": {"rules": [{"outbound": "proxy"}]}
    }
    
    process = None
    try:
        config_path.write_text(json.dumps(config), encoding='utf-8')
        command = ["./sing-box", "run", "-c", str(config_path)]
        
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1) # یک ثانیه انتظار برای اجرای کامل

        curl_command = [
            "curl", "-s", "--proxy", f"http://127.0.0.1:{local_port}",
            TEST_URL, "--connect-timeout", "5",
            "-o", "/dev/null", "-w", "%{time_connect}"
        ]
        curl_proc = subprocess.run(curl_command, capture_output=True, text=True, timeout=10)
        
        # ✅ تغییر اصلی اینجاست: به جای True/False، یک دیکشنری کامل برمی‌گردانیم
        if curl_proc.returncode == 0 and curl_proc.stdout:
            delay = int(float(curl_proc.stdout) * 1000)
            return {"proxy": proxy, "status": "active", "delay": delay}
        
        return {"proxy": proxy, "status": "dead", "delay": -1}

    except Exception:
        return {"proxy": proxy, "status": "dead", "delay": -1}
    finally:
        if process:
            kill_proc_tree(process.pid)
        if config_path.exists():
            config_path.unlink()

def main():
    # ✅ ساختار تابع main دقیقا از فایل شما پیروی می‌کند
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    print("🚀 شروع تست پراکسی‌های اصلی (V2Ray) با روش فایل اصلی شما...")
    proxies_file_path = Path("output/fetched_proxies.txt")
    proxies_to_test = get_proxies_from_file(proxies_file_path)
    total_proxies = len(proxies_to_test)

    if not proxies_to_test:
        save_json_to_file([], Path("output/github_results.json"))
        save_proxies_to_file([], Path("output/github_all.txt"))
        return

    # ✅ بخش اضافه شده برای جمع‌آوری نتایج در فرمت جدید
    working_proxies_results = []
    
    with ThreadPoolExecutor(max_workers=30) as executor:
        # ارسال index و total_proxies به تابع تست، دقیقا مانند فایل شما
        futures = {executor.submit(test_proxy, proxy, i, total_proxies): proxy for i, proxy in enumerate(proxies_to_test)}
        
        count = 0
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            
            # ✅ بخش اضافه شده برای جمع‌آوری نتایج موفق
            if result and result["status"] == "active":
                working_proxies_results.append(result)

            count += 1
            if count % PROGRESS_UPDATE_INTERVAL == 0:
                print(f"پیشرفت: {count}/{total_proxies} پراکسی تست شد...")

    print(f"تست تمام شد. تعداد پراکسی‌های فعال یافت شده: {len(working_proxies_results)}")

    # ✅ بخش اضافه شده برای ذخیره خروجی‌ها در فرمت‌های مورد نیاز
    working_proxies_results.sort(key=lambda p: p["delay"])
    final_proxy_strings = [p["proxy"] for p in working_proxies_results]
    
    save_json_to_file(working_proxies_results, Path("output/github_results.json"))
    save_proxies_to_file(final_proxy_strings, Path("output/github_all.txt"))
    save_proxies_to_file(final_proxy_strings[:500], Path("output/github_top_500.txt"))
    save_proxies_to_file(final_proxy_strings[:100], Path("output/github_top_100.txt"))
    print("📄 نتایج تست V2Ray ذخیره شدند.")

    # پاک‌سازی پوشه موقت
    for file in os.listdir(TEMP_DIR):
        os.remove(os.path.join(TEMP_DIR, file))
    os.rmdir(TEMP_DIR)


if __name__ == "__main__":
    import concurrent.futures
    main()
