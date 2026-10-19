import base64
import json
import os
from http.server import BaseHTTPRequestHandler
import requests


class handler(BaseHTTPRequestHandler):

  def do_POST(self):
    content_length = int(self.headers.get("Content-Length", 0))
    raw_data = self.rfile.read(content_length)

    if not raw_data:
      self.send_response(400)
      self.end_headers()
      self.wfile.write(b"No image data received")
      return

    # Clean base64 encoding on the server side
    b64_image = base64.b64encode(raw_data).decode("utf-8")

    api_key = os.environ.get("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{
            "parts": [
                {
                    "text": (
                        "Solve this circuit/engineering problem step-by-step"
                        " using plain text only. No markdown, no backticks, no"
                        " LaTeX."
                    )
                },
                {
                    "inline_data": {"mime_type": "image/jpeg", "data": b64_image}
                },
            ]
        }]
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
      resp_json = response.json()
      try:
        answer = resp_json["candidates"][0]["content"]["parts"][0]["text"]
      except Exception:
        answer = "Error parsing Gemini response"

      self.send_response(200)
      self.send_header("Content-Type", "text/plain")
      self.end_headers()
      self.wfile.write(answer.encode("utf-8"))
    else:
      self.send_response(response.status_code)
      self.send_header("Content-Type", "text/plain")
      self.end_headers()
      self.wfile.write(f"Google API Error: {response.text}".encode("utf-8"))