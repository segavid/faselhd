from http.server import BaseHTTPRequestHandler
import json
import re
import base64
import urllib.request
from urllib.parse import urlparse, unquote, parse_qs

# === CONFIG ===
TARGET = "https://gesseh.com"
GOOGLE_VERIFY = "<meta name='google-site-verification' content='4aeE1nom200vJpqjv46jujHDGVAuIdF2tA8rycTjFnE' />"
ROBOTS_TAG = "<meta name='robots' content='index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' />"
HEADER_BOX = ""

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

# === HELPERS ===
def base64_decode(s):
    try:
        normalized = s.replace(" ", "").replace("%3D", "=").replace("-", "+").replace("_", "/")
        return base64.b64decode(normalized).decode("utf-8", errors="ignore")
    except Exception:
        return None

def build_server_url(server):
    name = (server.get("name") or "").lower()
    sid = server.get("id", "")
    if re.match(r"^https?://", sid, re.I):
        return sid
    if "estream" in name:
        return f"https://arabveturk.com/embed-{sid}.html"
    if "arab" in name:
        return f"https://v.turkvearab.com/embed-{sid}.html"
    if "ok" in name:
        return f"https://ok.ru/videoembed/{sid}"
    if "red" in name:
        return f"https://iplayerhls.com/e/{sid}"
    return sid

def get_worker_domain(headers, host):
    proto = headers.get('x-forwarded-proto', ['https'])[0] if isinstance(headers.get('x-forwarded-proto'), list) else headers.get('x-forwarded-proto', 'https')
    return f"{proto}://{host}"

def replace_episode_links(match, worker_domain):
    before, quote, encoded, after = match.groups()
    decoded = base64_decode(unquote(encoded))
    if not decoded:
        return match.group(0)
    clean_url = re.sub(r"https?://(?:www\.)?gesseh\.(com|net)", worker_domain, decoded, flags=re.I)
    return f'<a {before}href="{clean_url}"{after}>'

def replace_player_block(match, worker_domain):
    enc_match = re.search(r"post=([^\"'\s]+)", match.group(0), re.I)
    if not enc_match:
        return match.group(0)
    decoded = base64_decode(enc_match.group(1))
    if not decoded:
        return match.group(0)
    try:
        data = json.loads(decoded)
    except Exception:
        return match.group(0)

    servers = []
    for s in data.get("servers", []):
        url = build_server_url(s)
        if url:
            servers.append({"name": s.get("name", ""), "url": url})

    if not servers:
        return match.group(0)

    servers_html = []
    for i, s in enumerate(servers):
        safe_url = s["url"].replace('"', "&quot;")
        safe_name = s["name"].replace("<", "&lt;").replace(">", "&gt;")
        servers_html.append(f"""
<div class="srv-row">
  <b>{safe_name}</b>
  <input type="text" readonly value="{safe_url}" class="srv-url" id="u{i}">
  <button onclick="navigator.clipboard.writeText(document.getElementById('u{i}').value);this.textContent='✓'">نسخ</button>
</div>""")

    player_html = f"""
<style>
.notice-bar{{background:#222;color:#fff;padding:10px;text-align:center;font-size:15px}}
.getEmbed{{max-width:800px;margin:0 auto;padding:10px}}
.srv-row{{display:flex;align-items:center;gap:6px;margin:5px 0;flex-wrap:wrap}}
.srv-row b{{min-width:70px;font-size:14px;flex-shrink:0}}
.srv-url{{width:300px;max-width:100%;padding:5px;font-size:11px;overflow:hidden;text-overflow:ellipsis}}
.srv-row button{{background:#ff004c;color:#fff;border:0;padding:5px 10px;cursor:pointer;border-radius:3px;font-size:13px;white-space:nowrap}}
.srv-row button:hover{{background:#222}}
@media(max-width:600px){{.srv-url{{width:200px}}}}
</style>
<div class="notice-bar">يرجى نسخ السيرفر وفتحه في المتصفح</div>
<div class="getEmbed">{''.join(servers_html)}</div>
"""
    return player_html + '<div class="singleInfo"'

# === MAIN HANDLER ===
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Parse path and query
            path = self.path.split('?')[0]
            query = self.path.split('?')[1] if '?' in self.path else ""
            
            # Remove /api prefix if present
            if path.startswith('/api'):
                path = path[4:] or '/'
            
            full_query = f"?{query}" if query else ""
            upstream = f"{TARGET}{path}{full_query}"

            # Get worker domain
            host = self.headers.get('host', 'localhost')
            worker_domain = get_worker_domain(dict(self.headers), host)
            
            print(f"Upstream: {upstream}")

            req = urllib.request.Request(upstream, headers={"Referer": TARGET, "User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "").lower()
                body = response.read()

                # Handle HTML
                if "text/html" in content_type:
                    body = body.decode("utf-8", errors="ignore")

                    # Replace all gesseh.com or gesseh.net to worker domain
                    body = re.sub(r"https?://(?:www\.)?gesseh\.(com|net)", worker_domain, body, flags=re.I)
                    body = re.sub(r"//(?:www\.)?gesseh\.(com|net)", worker_domain, body, flags=re.I)
                    body = re.sub(r'(src|href)=["\']/([^"\']+)["\']', rf'\1="{worker_domain}/\2"', body, flags=re.I)

                    # Replace homepage link
                    body = re.sub(
                        r'<a\s+title="الرئيسية"\s+href="/">الرئيسية</a>',
                        '<a title="قصة عشق الاصلي" href="https://z.3isk.news/video/">قصة عشق الاصلي</a>',
                        body, flags=re.I
                    )

                    # Decode encoded links
                    body = re.sub(
                        r'<a\s+([^>]*?)href=(["\'])https?://arbandroid\.com/[^"\']+\?url=([^"\']+)\2([^>]*)>',
                        lambda m: replace_episode_links(m, worker_domain),
                        body, flags=re.I
                    )

                    # Replace fake block
                    body = re.sub(
                        r'<script[^>]*type=["\']litespeed/javascript["\'][^>]*>[\s\S]*?</script>\s*<div class="secContainer bg">[\s\S]*?<div class="singleInfo"',
                        lambda m: replace_player_block(m, worker_domain),
                        body, flags=re.I
                    )

                    # Remove old meta & canonical
                    body = re.sub(r"<meta[^>]*name=['\"]robots['\"][^>]*>", "", body, flags=re.I)
                    body = re.sub(r"<meta[^>]*name=['\"]google-site-verification['\"][^>]*>", "", body, flags=re.I)
                    body = re.sub(r"<link[^>]*rel=['\"]canonical['\"][^>]*>", "", body, flags=re.I)

                    # Inject meta and verification tag
                    body = re.sub(
                        r"<head>",
                        f"<head>\n{ROBOTS_TAG}\n{GOOGLE_VERIFY}\n<link rel='canonical' href='{worker_domain}/video/' />",
                        body, count=1, flags=re.I
                    )

                    # Add header banner
                    body = HEADER_BOX + "\n" + body

                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=UTF-8')
                    for k, v in NO_CACHE_HEADERS.items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(body.encode('utf-8'))
                    return

                # Handle XML / RSS
                if any(x in content_type for x in ["xml", "rss", "text/plain"]):
                    body = body.decode("utf-8", errors="ignore")
                    body = re.sub(r"https?://(?:www\.)?gesseh\.(com|net)", worker_domain, body, flags=re.I)
                    body = re.sub(r"//(?:www\.)?gesseh\.(com|net)", worker_domain, body, flags=re.I)

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/xml; charset=UTF-8')
                    for k, v in NO_CACHE_HEADERS.items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(body.encode('utf-8'))
                    return

                # Binary fallback
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                for k, v in NO_CACHE_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)
                return

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            for k, v in NO_CACHE_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode())
            return