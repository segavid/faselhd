import re
import requests
from fastapi import FastAPI, Request, Response

app = FastAPI()

TARGET = "https://www.faselhds.biz"
ROBOTS_TAG = "<meta name='robots' content='index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' />"
GOOGLE_VERIFY = "<meta name='google-site-verification' content='HWrhtgkCPV2OT-OWRzV60Vdl1pWxt35-aEZ7NNDTHWs' />"
HEADER_BOX = """
<div style="width:100%;background:#0000ff;color:#fff;padding:20px;text-align:center;font-size:22px;font-weight:bold;direction:rtl;">
  <a href="https://z.3isk.news/" title="قصة عشق" style="color:#fff;text-decoration:none;">قصة عشق</a>
</div>
"""

@app.get("/{path:path}")
@app.post("/{path:path}")
async def proxy(request: Request, path: str):
    query_string = request.url.query
    upstream = f"{TARGET}/{path}"
    if query_string:
        upstream += f"?{query_string}"

    headers = dict(request.headers)
    headers["Referer"] = TARGET + "/"

    method = request.method
    data = await request.body()

    try:
        resp = requests.request(method, upstream, headers=headers, data=data, timeout=20)
    except Exception as e:
        return Response(f"Error fetching target: {e}", status_code=500)

    content_type = resp.headers.get("content-type", "").lower()
    body = resp.content

    if "text/html" in content_type:
        html = resp.text
        origin = str(request.base_url).rstrip("/")

        # Replace faselhds.* → Vercel URL
        html = re.sub(r"https:\/\/(?:www\.)?faselhds\.[a-z]+", origin, html)

        # Remove old meta tags
        html = re.sub(r"<meta[^>]*name=['\"]robots['\"][^>]*>", "", html, flags=re.I)
        html = re.sub(r"<meta[^>]*name=['\"]google-site-verification['\"][^>]*>", "", html, flags=re.I)

        # Inject meta tags
        html = re.sub(r"<head>", f"<head>\n{ROBOTS_TAG}\n{GOOGLE_VERIFY}", html, flags=re.I)

        # Inject banner
        if re.search(r"<body[^>]*>", html, re.I):
            html = re.sub(r"<body[^>]*>", lambda m: m.group(0) + "\n" + HEADER_BOX, html, count=1, flags=re.I)
        else:
            html = HEADER_BOX + html

        return Response(content=html, media_type="text/html; charset=utf-8", status_code=resp.status_code)

    elif any(x in content_type for x in ["xml", "rss", "text/plain"]):
        text_body = resp.text
        origin = str(request.base_url).rstrip("/")
        text_body = re.sub(r"https:\/\/(?:www\.)?faselhds\.[a-z]+", origin, text_body)
        return Response(content=text_body, media_type="application/xml; charset=utf-8", status_code=resp.status_code)

    else:
        return Response(content=body, media_type=content_type, status_code=resp.status_code)
