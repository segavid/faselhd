import re
import requests
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

app = FastAPI()

TARGET = "https://www.faselhds.biz"
ROBOTS_TAG = "<meta name='robots' content='index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' />"
GOOGLE_VERIFY = "<meta name='google-site-verification' content='HWrhtgkCPV2OT-OWRzV60Vdl1pWxt35-aEZ7NNDTHWs' />"
HEADER_BOX = """
<div style="width:100%;background:#0000ff;color:#fff;padding:20px;text-align:center;font-size:22px;font-weight:bold;direction:rtl;">
  <a href="https://z.3isk.news/" title="قصة عشق" style="color:#fff;text-decoration:none;">قصة عشق</a>
</div>
"""

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str):
    query = request.url.query
    upstream_url = f"{TARGET}/{path}"
    if query:
        upstream_url += f"?{query}"

    # ✅ Spoof real browser headers to bypass Cloudflare
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Referer": TARGET + "/",
        "Origin": TARGET,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    method = request.method
    data = await request.body() if method not in ["GET", "HEAD"] else None

    try:
        with requests.request(method, upstream_url, headers=browser_headers, data=data, stream=True, timeout=25) as upstream:
            content_type = (upstream.headers.get("content-type") or "").lower()

            # ✅ Handle HTML pages
            if "text/html" in content_type:
                body = upstream.text
                origin = "https://faselhd.vercel.app"

                body = re.sub(r"https:\/\/(?:www\.)?faselhds\.[a-z]+", origin, body)
                body = re.sub(r"<meta[^>]*name=['\"]robots['\"][^>]*>", "", body, flags=re.I)
                body = re.sub(r"<meta[^>]*name=['\"]google-site-verification['\"][^>]*>", "", body, flags=re.I)
                body = re.sub(r"<head>", f"<head>\n{ROBOTS_TAG}\n{GOOGLE_VERIFY}", body, flags=re.I)
                body = re.sub(r"<body[^>]*>", lambda m: m.group(0) + "\n" + HEADER_BOX, body, count=1, flags=re.I)

                return Response(content=body, media_type="text/html; charset=utf-8", status_code=upstream.status_code)

            # ✅ Handle XML / RSS / Sitemap
            elif any(x in content_type for x in ["xml", "rss", "text/plain"]):
                text = upstream.text
                origin = "https://faselhd.vercel.app"
                text = re.sub(r"https:\/\/(?:www\.)?faselhds\.[a-z]+", origin, text)
                return Response(content=text, media_type="application/xml; charset=utf-8", status_code=upstream.status_code)

            # ✅ Handle media, JS, CSS, images (stream mode)
            else:
                def generate():
                    for chunk in upstream.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                return StreamingResponse(generate(), media_type=content_type, status_code=upstream.status_code)

    except Exception as e:
        return Response(f"Error fetching from target: {e}", status_code=502)
