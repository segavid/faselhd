from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error
import re

TARGET_SOURCE_DOMAIN = 'www.faselhds.life'
ROBOTS_TAG = "<meta name='robots' content='index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' />"
GOOGLE_VERIFY = "<meta name='google-site-verification' content='4aeE1nom200vJpqjv46jujHDGVAuIdF2tA8rycTjFnE' />"

HEADER_BOX = '''
<div style="width:100%;background:#blue;color:#fff;padding:20px;text-align:center;font-size:22px;font-weight:bold;direction:rtl;">
  <a href="https://z.3isk.news/" title="قصة عشق" style="color:#fff;text-decoration:none;">قصة عشق</a>
</div>
'''

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            path = self.path
            if path.startswith('/api'):
                path = path[4:] or '/'
            
            target_url = f"https://{TARGET_SOURCE_DOMAIN}{path}"
            
            # Get worker domain
            host = self.headers.get('host', 'localhost')
            proto = self.headers.get('x-forwarded-proto', 'https')
            worker_origin = f"{proto}://{host}"
            
            # Make request with forced Referer
            req = urllib.request.Request(
                target_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "*/*",
                    "Referer": "https://www.faselhds.life/"
                }
            )
            
            try:
                response = urllib.request.urlopen(req, timeout=10)
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error {e.code}".encode())
                return
            
            content_type = response.headers.get("Content-Type", "").lower()
            body = response.read()
            
            # ✅ Handle HTML
            if "text/html" in content_type:
                html = body.decode("utf-8", errors="ignore")
                
                # Rewrite ANY faselhds.* domain → worker domain
                html = re.sub(
                    r'https://(?:www\.)?faselhds\.[a-z]+',
                    worker_origin,
                    html,
                    flags=re.IGNORECASE
                )
                
                # Remove existing robots & google verify
                html = re.sub(
                    r'<meta[^>]*name=["\']robots["\'][^>]*>',
                    '',
                    html,
                    flags=re.IGNORECASE
                )
                html = re.sub(
                    r'<meta[^>]*name=["\']google-site-verification["\'][^>]*>',
                    '',
                    html,
                    flags=re.IGNORECASE
                )
                
                # Inject robots + google verify inside <head>
                html = re.sub(
                    r'(<head[^>]*>)',
                    rf'\1\n{ROBOTS_TAG}\n{GOOGLE_VERIFY}\n',
                    html,
                    count=1,
                    flags=re.IGNORECASE
                )
                
                # Add banner box after <body>
                html = re.sub(
                    r'(<body[^>]*>)',
                    rf'\1\n{HEADER_BOX}',
                    html,
                    count=1,
                    flags=re.IGNORECASE
                )
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=UTF-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
                return
            
            # ✅ Handle XML / RSS / Sitemap
            if any(x in content_type for x in ['xml', 'rss', 'text/plain']) or path.endswith('.xml'):
                text = body.decode("utf-8", errors="ignore")
                
                # Replace all faselhds.* links → worker domain
                text = re.sub(
                    r'https://(?:www\.)?faselhds\.[a-z]+',
                    worker_origin,
                    text,
                    flags=re.IGNORECASE
                )
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/xml; charset=UTF-8')
                self.end_headers()
                self.wfile.write(text.encode('utf-8'))
                return
            
            # ✅ Binary files (CSS, JS, video, images)
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(body)
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            error_msg = f"Error: {str(e)}"
            self.wfile.write(error_msg.encode())

