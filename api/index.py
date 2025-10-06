from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error
import re

TARGET_SOURCE_DOMAIN = 'www.faselhds.life'
ROBOTS_TAG = "<meta name='robots' content='index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' />"
GOOGLE_VERIFY = "<meta name='google-site-verification' content='4aeE1nom200vJpqjv46jujHDGVAuIdF2tA8rycTjFnE' />"

HEADER_BOX = '''
<div class="container-fluid py-3 text-center" dir="rtl" style="background:#0052cc;">
  <div class="d-flex flex-wrap justify-content-center gap-3">
    <a href="https://z.3isk.news/" title="مسلسلات تركية" class="px-3 py-2 rounded fw-bold text-white" style="background:#007bff;text-decoration:none;">مسلسلات تركية</a>
    <a href="https://z.3isk.news/series/3isk-se-esref-ruya-watch/" title="حلم اشرف" class="px-3 py-2 rounded fw-bold text-white" style="background:#28a745;text-decoration:none;">حلم اشرف</a>
    <a href="https://z.3isk.news/video/episode-3isk-uzak-sehir-season-1-episode-33-watch/" title="المدينة البعيدة الحلقة 33" class="px-3 py-2 rounded fw-bold text-white" style="background:#ff5722;text-decoration:none;">المدينة البعيدة الحلقة 33</a>
  </div>
</div>
'''

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            path = self.path
            if path.startswith('/api'):
                path = path[4:] or '/'
            
            # ✅ Serve Google verification file directly
            if path == "/googlec592fabc25eec3b8.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"google-site-verification: googlec592fabc25eec3b8.html")
                return
            
            target_url = f"https://{TARGET_SOURCE_DOMAIN}{path}"
            
            # Get current Vercel domain (worker origin)
            host = self.headers.get('host', 'localhost')
            proto = self.headers.get('x-forwarded-proto', 'https')
            worker_origin = f"{proto}://{host}"
            
            # Make upstream request
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
                
                # Replace all faselhds.* domains with Vercel domain
                html = re.sub(r'https://(?:www\.)?faselhds\.[a-z]+', worker_origin, html, flags=re.I)
                
                # Remove existing robots and verification
                html = re.sub(r'<meta[^>]*name=["\']robots["\'][^>]*>', '', html, flags=re.I)
                html = re.sub(r'<meta[^>]*name=["\']google-site-verification["\'][^>]*>', '', html, flags=re.I)
                
                # Inject robots + verify tags
                html = re.sub(r'(<head[^>]*>)', rf'\1\n{ROBOTS_TAG}\n{GOOGLE_VERIFY}\n', html, count=1, flags=re.I)
                
                # Add your header box
                html = re.sub(r'(<body[^>]*>)', rf'\1\n{HEADER_BOX}', html, count=1, flags=re.I)
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=UTF-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
                return
            
            # ✅ Handle XML / RSS / Sitemap
            if any(x in content_type for x in ['xml', 'rss', 'text/plain']) or path.endswith('.xml'):
                text = body.decode("utf-8", errors="ignore")
                
                # Replace faselhds.* with your Vercel domain
                text = re.sub(r'https://(?:www\.)?faselhds\.[a-z]+', worker_origin, text, flags=re.I)
                
                # Replace GitHub links → Vercel domain
                text = re.sub(r'https?://segavid\.github\.io/3isk', worker_origin, text, flags=re.I)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/xml; charset=UTF-8')
                self.end_headers()
                self.wfile.write(text.encode('utf-8'))
                return
            
            # ✅ Binary fallback (CSS, JS, Images, Video, etc.)
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
