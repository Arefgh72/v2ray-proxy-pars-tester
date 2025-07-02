# scripts/hysteria_config_builder.py
from urllib.parse import urlparse, parse_qs

def build_hysteria_config(proxy_url: str, local_port: int):
    """
    یک کانفیگ کلاینت Hysteria 2 را از روی URL می‌سازد.
    """
    try:
        parsed = urlparse(proxy_url)
        params = parse_qs(parsed.query)

        server = f"{parsed.hostname}:{parsed.port}"
        auth = parsed.username or ""
        
        # استخراج پارامترهای اصلی
        sni = params.get("sni", [parsed.hostname])[0]
        insecure = params.get("insecure", ['0'])[0] == '1'
        
        config = {
            "server": server,
            "auth": auth,
            "tls": {
                "sni": sni,
                "insecure": insecure
            },
            "socks5": {
                "listen": f"127.0.0.1:{local_port}"
            }
        }
        
        # اضافه کردن پارامترهای اختیاری
        if "obfs" in params:
            config["obfs"] = { "type": "salamander", "password": params["obfs"][0] }
        if "up" in params or "down" in params:
            config["bandwidth"] = {
                "up": params.get("up", ["100 mbps"])[0],
                "down": params.get("down", ["100 mbps"])[0]
            }
            
        return config
    except Exception:
        return None
