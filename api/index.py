import os
import re
from flask import Flask, request, Response
import requests # Need to install: pip install requests

# --- Configuration Constants ---
TARGET = "https://www.faselhds.biz"

ROBOTS_TAG = "<meta name='robots' content='index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' />"
GOOGLE_VERIFY = "<meta name='google-site-verification' content='HWrhtgkCPV2OT-OWRzV60Vdl1pWxt35-aEZ7NNDTHWs' />"
HEADER_BOX = """
<div style="width:100%;background:#blue;color:#fff;padding:20px;text-align:center;font-size:22px;font-weight:bold;direction:rtl;">
  <a href="https://z.3isk.news/" title="قصة عشق" style="color:#fff;text-decoration:none;">قصة عشق</a>
</div>
"""
# Regex pattern to match the target domain variations
# https://www.faselhds.[a-z]+ or https://faselhds.[a-z]+
DOMAIN_REPLACEMENT_PATTERN = re.compile(r"https?:\/\/(?:www\.)?faselhds\.[a-z]+", re.IGNORECASE)

app = Flask(__name__)

@app.route("/", defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route("/<path:path>", methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def handle_request(path):
    """
    Handles all incoming HTTP requests, proxies them to the TARGET, and modifies 
    the content (HTML/XML) before sending the response back.
    """
    
    # 1. Determine the upstream URL
    # Construct the URL by appending the path and query string to the TARGET
    upstream_url = f"{TARGET}/{path}"
    if request.query_string:
        upstream_url += f"?{request.query_string.decode('utf-8')}"
    
    # Get the scheme (http or https) and host of the worker (Vercel) domain
    # This is used for replacing links in the content
    worker_origin = request.url_root.rstrip('/')

    # 2. Prepare headers for the upstream request
    new_headers = dict(request.headers)
    # Set the Referer header as in the original JS code
    new_headers["Referer"] = "https://www.faselhds.biz/"
    # It's good practice to remove hop-by-hop headers if they exist
    hop_by_hop = ['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade', 'content-encoding', 'content-length']
    for h in hop_by_hop:
        new_headers.pop(h, None)

    # 3. Proxy the request
    try:
        # Use requests to make the upstream call
        resp = requests.request(
            method=request.method,
            url=upstream_url,
            headers=new_headers,
            data=request.get_data(), # Pass request body for POST/PUT/etc.
            stream=True, # Enable streaming for non-text content
            allow_redirects=False # Keep logic simpler, let the worker handle redirects if needed
        )
    except requests.exceptions.RequestException as e:
        # Handle connection errors
        return Response(f"Proxy Error: {e}", status=503)

    # 4. Process the response content
    
    content_type = resp.headers.get("Content-Type", "").lower()
    
    # Get response headers from upstream, excluding `Content-Length` (it will be recalculated)
    response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in ('content-length',)}

    # --- ✅ Handle HTML ---
    if "text/html" in content_type:
        body = resp.text
        
        # Rewrite ALL faselhds.* domain → worker domain
        body = DOMAIN_REPLACEMENT_PATTERN.sub(worker_origin, body)

        # Remove existing robots & google verify meta tags
        body = re.sub(r"<meta[^>]*name=['\"]robots['\"][^>]*>", "", body, flags=re.IGNORECASE)
        body = re.sub(r"<meta[^>]*name=['\"]google-site-verification['\"][^>]*>", "", body, flags=re.IGNORECASE)

        # Inject robots + google verify inside <head>
        body = re.sub(r"<head>", r"<head>\n" + ROBOTS_TAG + "\n" + GOOGLE_VERIFY, body, count=1, flags=re.IGNORECASE)

        # Add banner box after <body>
        if "<body" in body.lower():
            # Use a function replacement to handle any <body> tag attributes
            def add_header_box(match):
                return match.group(0) + "\n" + HEADER_BOX
            body = re.sub(r"<body[^>]*>", add_header_box, body, count=1, flags=re.IGNORECASE)
        else:
            body = HEADER_BOX + body # Prepend if <body> not found

        # Explicitly set content type for the modified HTML
        response_headers["Content-Type"] = "text/html; charset=UTF-8"
        
        return Response(body, status=resp.status_code, headers=response_headers)

    # --- ✅ Handle XML / RSS / Sitemap ---
    if any(tag in content_type for tag in ["xml", "rss", "text/plain"]):
        body = resp.text
        
        # Replace all faselhds.* links → worker domain
        body = DOMAIN_REPLACEMENT_PATTERN.sub(worker_origin, body)

        # Explicitly set content type for the modified XML/Text
        response_headers["Content-Type"] = "application/xml; charset=UTF-8"

        return Response(body, status=resp.status_code, headers=response_headers)

    # --- ✅ Pass through everything else (CSS, JS, video, images) ---
    
    # Return the raw content streamed from the upstream response
    # The generator expression yields chunks of data from the upstream
    return Response(
        resp.iter_content(chunk_size=8192), 
        status=resp.status_code, 
        headers=response_headers
    )

if __name__ == '__main__':
    # This block is for local testing only
    app.run(debug=True)
