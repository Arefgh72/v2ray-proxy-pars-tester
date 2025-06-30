import datetime
import os

# --- تنظیمات ---
LOG_DIR = 'output'  # نام پوشه‌ای که تمام لاگ‌ها و خروجی‌ها در آن ذخیره می‌شوند
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error.log")
TEST_SUMMARY_LOG_FILE = os.path.join(LOG_DIR, "test_summary.log")


def _ensure_log_directory_exists():
    """
    اطمینان حاصل می‌کند که پوشه لاگ (output) وجود دارد.
    اگر وجود نداشته باشد، آن را ایجاد می‌کند. این کار از خطای FileNotFoundError جلوگیری می‌کند.
    """
    os.makedirs(LOG_DIR, exist_ok=True)


def log_error(stage: str, message: str, error_details: str = ""):
    """
    یک خطای مشخص را در فایل لاگ خطا ثبت می‌کند. حالت فایل 'a' (append) است تا لاگ‌های قبلی حفظ شوند.

    Args:
        stage (str): مرحله‌ای از فرآیند که خطا در آن رخ داده (مثلاً "Fetch Proxies", "GitHub Test").
        message (str): پیام اصلی و خوانا برای خطا.
        error_details (str, optional): جزئیات فنی بیشتر درباره خطا.
    """
    _ensure_log_directory_exists()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = f"[{timestamp}] [Stage: {stage}] [Error: {message}]\n"
    if error_details:
        log_entry += f"  Details: {error_details}\n"
    log_entry += "-" * 60 + "\n"  # جداکننده برای خوانایی بهتر

    try:
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        # همچنین خطا را در کنسول چاپ می‌کنیم تا در لاگ‌های گیت‌هاب اکشن هم دیده شود
        print(f"ERROR LOGGED: {stage} - {message}")
    except Exception as e:
        print(f"CRITICAL: Failed to write to error log file: {e}")


def log_test_summary(cycle_number: int, raw_count: int, github_stats: dict, iran_stats: dict):
    """
    خلاصه نتایج تست هر دوره را در فایل لاگ تست ثبت می‌کند (حالت append).

    Args:
        cycle_number (int): شماره اجرای ورک‌فلو (برای پیگیری).
        raw_count (int): تعداد کل پروکسی‌های خام استخراج شده.
        github_stats (dict): دیکشنری شامل آمار تست گیت‌هاب.
        iran_stats (dict): دیکشنری شامل آمار تست ایران.
    """
    _ensure_log_directory_exists()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = f"================== Cycle #{cycle_number} | {timestamp} ==================\n"
    log_entry += f"Total Raw Proxies Fetched: {raw_count}\n\n"

    # --- بخش آمار تست گیت‌هاب ---
    log_entry += "[ GitHub Test Summary ]\n"
    if github_stats.get('passed_count', 0) > 0:
        log_entry += f"  - Proxies Passed: {github_stats.get('passed_count', 0)}\n"
        log_entry += f"  - Average Latency: {github_stats.get('avg_latency', 0.0):.2f} ms\n"
        log_entry += f"  - Min Latency: {github_stats.get('min_latency', 0)} ms\n"
        log_entry += f"  - Max Latency: {github_stats.get('max_latency', 0)} ms\n"
    else:
        log_entry += "  - No proxies passed the GitHub test.\n"
    log_entry += "\n"

    # --- بخش آمار تست ایران ---
    # این بخش در فاز دوم پروژه تکمیل خواهد شد.
    log_entry += "[ Iran Test Summary ]\n"
    if iran_stats.get('passed_count', 0) > 0:
        log_entry += f"  - Proxies Passed: {iran_stats.get('passed_count', 0)}\n"
        log_entry += f"  - Average Latency: {iran_stats.get('avg_latency', 0.0):.2f} ms\n"
        log_entry += f"  - Min Latency: {iran_stats.get('min_latency', 0)} ms\n"
        log_entry += f"  - Max Latency: {iran_stats.get('max_latency', 0)} ms\n"
        log_entry += f"  - Average Download Speed: {iran_stats.get('avg_speed', 0.0):.2f} Mbps\n"
    else:
        # متنی که نشان می‌دهد این بخش هنوز اجرا نشده یا ناموفق بوده است
        log_entry += "  - Iran test was not run or no proxies passed.\n"
    
    log_entry += "====================================================================\n\n"

    try:
        with open(TEST_SUMMARY_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print("TEST SUMMARY LOGGED.")
    except Exception as e:
        # اگر در نوشتن لاگ اصلی هم خطا رخ داد، آن را در لاگ خطا ثبت می‌کنیم
        log_error("Logging", "Failed to write to test summary log file.", str(e))
