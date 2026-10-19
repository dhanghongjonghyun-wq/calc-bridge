import base64
import json
import os
import requests


def app(environ, start_response):
  # Read incoming binary data from the ESP32
  try:
    content_length = int(environ.get("CONTENT_LENGTH", 0))
  except (ValueError, TypeError):
    content_length = 0

  body = environ["wsgi.input"].read(content_length)

  if not body:
    start_response("400 Bad Request", [("Content-Type", "text/plain")])
    return [b"No image data received"]

  # Base64 encode the raw image bytes server-side
  b64_image = base64.b64encode(body).decode("utf-8")

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
    try:
      resp_json = response.json()
      answer = resp_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
      answer = "Error parsing Gemini response"

    start_response("200 OK", [("Content-Type", "text/plain")])
    return [answer.encode("utf-8")]
  else:
    start_response(
        f"{response.status_code} Error", [("Content-Type", "text/plain")]
    )
    return [f"Google API Error: {response.text}".encode("utf-8")]
