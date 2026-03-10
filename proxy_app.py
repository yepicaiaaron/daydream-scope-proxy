from flask import Flask, request, jsonify, abort, Response
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

# The target URL for your Daydream Scope App on GCP
# This should be the internal or private IP/port if Render can reach it directly,
# or the public IP if the GCP firewall allows it only from Render's IPs.
TARGET_SCOPE_URL = os.environ.get("TARGET_SCOPE_URL", "http://34.44.193.2:8000")

@app.route("/api/v1/webrtc/offer", methods=["POST"])
def webrtc_offer():
    try:
        headers = {
            'Content-Type': request.content_type or 'application/sdp',
            'Accept': request.headers.get('Accept', 'application/sdp')
        }
        
        app.logger.info(f"Forwarding WebRTC offer to {TARGET_SCOPE_URL}/api/v1/webrtc/offer")
        response = requests.post(
            f"{TARGET_SCOPE_URL}/api/v1/webrtc/offer", 
            data=request.get_data(), 
            headers=headers,
            timeout=15  # Added timeout to prevent hanging and diagnose network issues
        )
        response.raise_for_status() 
        
        return Response(
            response.content, 
            response.status_code, 
            mimetype=response.headers.get('Content-Type', 'application/sdp')
        )
    except requests.exceptions.Timeout:
        app.logger.error(f"Timeout connecting to GCP at {TARGET_SCOPE_URL}")
        abort(504, description="Gateway Timeout connecting to Scope API")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error forwarding WebRTC offer: {e}")
        abort(500, description=str(e))

@app.route("/api/v1/prompt", methods=["POST"])
def prompt():
    if not request.is_json:
        abort(400, description="Request must be JSON")
    
    try:
        # Forward the request to the Daydream Scope App
        response = requests.post(f"{TARGET_SCOPE_URL}/api/v1/prompt", json=request.get_json())
        response.raise_for_status() # Raise an exception for HTTP errors
        
        # Return the response from the Daydream Scope App
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error forwarding prompt: {e}")
        abort(500, description=str(e))

# Generic route to catch all other /api/v1 calls if needed, and forward them
@app.route("/api/v1/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def forward_api_v1(subpath):
    # Ensure we're forwarding to the correct base URL and path
    forward_url = f"{TARGET_SCOPE_URL}/api/v1/{subpath}"
    
    headers = {key: value for key, value in request.headers if key != 'Host'}
    data = request.get_data()
    
    try:
        resp = requests.request(
            method=request.method,
            url=forward_url,
            headers=headers,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [
            (name, value) for name, value in resp.raw.headers.items()
            if name.lower() not in excluded_headers
        ]

        return Response(resp.content, resp.status_code, headers)

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error forwarding generic API call to {forward_url}: {e}")
        abort(500, description=str(e))

@app.route("/")
def hello():
    return "Daydream Scope Proxy is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
