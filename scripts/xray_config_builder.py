import base64
from urllib.parse import urlparse, parse_qs, unquote
import json

def build_xray_config(proxy_url: str, local_port: int):
    """
    یک کانفیگ کامل Xray را از لینک پروکسی می‌سازد.
    """
    try:
        parsed_url = urlparse(proxy_url)
        protocol = parsed_url.scheme
        params = parse_qs(parsed_url.query)

        network = params.get("type", [None])[0] or params.get("net", ["tcp"])[0]
        security = params.get("security", ["none"])[0]
        
        address = parsed_url.hostname
        port = parsed_url.port
        uuid_or_pass = unquote(parsed_url.username or "")
        
        stream_settings = {"network": network, "security": security}
        
        if security == 'tls':
            sni = params.get('sni', [None])[0] or params.get('host', [address])[0]
            alpn = params.get('alpn', [None])[0]
            tls_settings = {"serverName": sni}
            if alpn: tls_settings["alpn"] = alpn.split(',')
            stream_settings['tlsSettings'] = tls_settings

        if network == 'ws':
            host = params.get('host', [sni if security == 'tls' else address])[0]
            path = params.get('path', ['/'])[0]
            stream_settings['wsSettings'] = {"path": path, "headers": {"Host": host}}
        elif network == 'grpc':
            service_name = params.get('serviceName', [''])[0]
            stream_settings['grpcSettings'] = {"serviceName": service_name, "multiMode": (params.get("mode", ["gun"])[0] == "multi")}

        outbound_settings = {}
        if protocol == "vless":
            outbound_settings = {"vnext": [{"address": address, "port": port, "users": [{"id": uuid_or_pass, "flow": params.get("flow", [None])[0]}]}]}
        elif protocol == "vmess":
            vmess_json = json.loads(base64.b64decode(parsed_url.netloc).decode('utf-8'))
            outbound_settings = {"vnext": [{"address": vmess_json.get("add", address), "port": int(vmess_json.get("port", port)), "users": [{"id": vmess_json.get("id", uuid_or_pass), "alterId": int(vmess_json.get("aid", 0)), "security": vmess_json.get("scy", "auto")}]}]}
        elif protocol == "trojan":
            outbound_settings = {"servers": [{"address": address, "port": port, "password": uuid_or_pass}]}
        elif protocol == "ss":
            if '@' in parsed_url.netloc:
                decoded_user_info = base64.b64decode(unquote(parsed_url.netloc.split('@')[0])).decode('utf-8')
            else:
                decoded_user_info = uuid_or_pass
            method, password = decoded_user_info.split(':', 1)
            outbound_settings = {"servers": [{"method": method, "password": password, "address": address, "port": port}]}
        else:
            return None
        
        outbound = {"protocol": protocol, "settings": outbound_settings, "streamSettings": stream_settings}
        
        return {"inbounds": [{"port": local_port, "protocol": "socks", "settings": {"auth": "noauth", "udp": True}}], "outbounds": [outbound]}

    except Exception:
        return None
