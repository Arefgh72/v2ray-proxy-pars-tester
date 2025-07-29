# scripts/02_test_proxies.py

import os
import json
import asyncio
import time
from pathlib import Path
import signal
import psutil

# --- ایمپورت‌ها بر اساس فایل شما، با اصلاح جزئی برای پروژه ---
from typing import List, Dict
from collections import Counter
from utils import get_proxies_from_file, save_proxies_to_file, save_json_to_file

# --- تمام ثابت‌ها دقیقا از فایل شما کپی شده‌اند ---
TEMP_DIR = 'temp_configs'
LOCAL_SOCKS_PORT_START = 2080
TEST_URL = 'http://cp.cloudflare.com/'
PROGRESS_UPDATE_INTERVAL = 100
DEBUG_MODE = False

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

# --- تابع تست بازنویسی شده با async/await، مطابق ساختار فایل شما ---
async def test_proxy(proxy: str, index: int, total_proxies: int) -> Dict:
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
        
        # ✅ استفاده از asyncio برای اجرای فرآیند در پس‌زمینه
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await asyncio.sleep(1)

        curl_command = [
            "curl", "-s", "--proxy", f"http://127.0.0.1:{local_port}",
            TEST_URL, "--connect-timeout", "5",
            "-o", "/dev/null", "-w", "%{time_connect}"
        ]
        
        # ✅ استفاده از asyncio برای اجرای curl
        curl_proc = await asyncio.create_subprocess_exec(
            *curl_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(curl_proc.communicate(), timeout=10)

        if curl_proc.returncode == 0 and stdout:
            delay = int(float(stdout.decode()) * 1000)
            return {"proxy": proxy, "status": "active", "delay": delay}
        
        return {"proxy": proxy, "status": "dead", "delay": -1}

    except Exception as e:
        if DEBUG_MODE:
            print(f"ERROR: {proxy} -> {e}")
        return {"proxy": proxy, "status": "dead", "delay": -1}
    finally:
        if process:
            kill_proc_tree(process.pid)
        if config_path.exists():
            config_path.unlink()

# --- تابع main بازنویسی شده با async/await، مطابق ساختار فایل شما ---
async def main():
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    print("🚀 شروع تست پراکسی‌های اصلی (V2Ray) با ساختار asyncio...")
    proxies_file_path = Path("output/fetched_proxies.txt")
    proxies_to_test = get_proxies_from_file(proxies_file_path)
    total_proxies = len(proxies_to_test)

    if not proxies_to_test:
        save_json_to_file([], Path("output/github_results.json"))
        save_proxies_to_file([], Path("output/github_all.txt"))
        return

    working_proxies_results = []
    
    # ✅ اجرای همزمان تست‌ها با asyncio.gather
    tasks = [test_proxy(proxy, i, total_proxies) for i, proxy in enumerate(proxies_to_test)]
    
    count = 0
    # استفاده از asyncio.as_completed برای نمایش پیشرفت
    for future in asyncio.as_completed(tasks):
        result = await future
        if result and result["status"] == "active":
            working_proxies_results.append(result)

        count += 1
        if count % PROGRESS_UPDATE_INTERVAL == 0:
            print(f"پیشرفت: {count}/{total_proxies} پراکسی تست شد...")

    print(f"تست تمام شد. تعداد پراکسی‌های فعال یافت شده: {len(working_proxies_results)}")

    working_proxies_results.sort(key=lambda p: p["delay"])
    final_proxy_strings = [p["proxy"] for p in working_proxies_results]
    
    save_json_to_file(working_proxies_results, Path("output/github_results.json"))
    save_proxies_to_file(final_proxy_strings, Path("output/github_all.txt"))
    save_proxies_to_file(final_proxy_strings[:500], Path("output/github_top_500.txt"))
    save_proxies_to_file(final_proxy_strings[:100], Path("output/github_top_100.txt"))
    print("📄 نتایج تست V2Ray ذخیره شدند.")

    for file in os.listdir(TEMP_DIR):
        os.remove(os.path.join(TEMP_DIR, file))
    os.rmdir(TEMP_DIR)

if __name__ == "__main__":
    # ✅ اجرای اسکریپت با asyncio
    asyncio.run(main())
