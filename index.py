import os
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)

# Configure Gemini API using environment variable set in Render dashboard
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Using a stable, supported flash model for fast cloud math/vision evaluation
model = genai.GenerativeModel("gemini-1.5-flash")


@app.route("/", methods=["POST"])
def handle_calc_request():
  try:
    # Safely decode incoming payload from ESP32
    raw_data = request.data.decode("utf-8") if request.data else ""
    prompt = raw_data.strip() if raw_data else ""

    if not prompt:
      return "Error: Empty expression received", 400

    # Generate content using Gemini
    response = model.generate_content(prompt)

    # Safely check if response and response.text exist before calling strip()
    if response and hasattr(response, "text") and response.text:
      return response.text.strip(), 200
    else:
      return "Error: Empty response from AI model", 500

  except Exception as e:
    # Catch any runtime/API exceptions and return a clean error string to the ESP32
    return f"Bridge Server Error: {str(e)}", 500


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
