import os
from flask import Flask, request, Response
from google import genai
from google.genai import types

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def bridge_handler():
    if request.method == "GET":
        return "ESP32 Calculator Cloud Bridge is Online (Flask + Gemini Flash)", 200

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return "Server Error: GEMINI_API_KEY environment variable is missing in Vercel settings.", 500

        client = genai.Client(api_key=api_key)

        image_data = request.data
        if not image_data or len(image_data) < 1000:
            return "Error: Received empty or corrupted image buffer from ESP32.", 400

        prompt = (
            "You are a concise engineering calculator. "
            "Analyze the circuit diagram or math problem in this image and provide "
            "a step-by-step solution. Use plain text ONLY. "
            "Do NOT use markdown symbols, bold tags, backticks, asterisks, or LaTeX formatting."
        )

        image_part = types.Part.from_bytes(
            data=image_data,
            mime_type="image/jpeg",
        )

        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=[prompt, image_part],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=512,
            )
        )

        solution_text = response.text.strip() if response and response.text else "No solution generated."
        return Response(solution_text, mimetype="text/plain; charset=utf-8"), 200

    except Exception as e:
        return f"Python Execution Error: {str(e)}", 500

# Required for Vercel serverless WSGI routing
if __name__ == "__main__":
    app.run()
