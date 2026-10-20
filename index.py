import os
from google import genai
from google.genai import types
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Server Error: GEMINI_API_KEY environment variable is missing in Vercel settings.")
                return

            # Initialize the modern GenAI client
            client = genai.Client(api_key=api_key)

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length <= 0:
                self.send_response(400)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Error: Received empty or invalid Content-Length.")
                return

            image_data = self.rfile.read(content_length)

            if len(image_data) != content_length:
                self.send_response(400)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Error: Incomplete image payload received.")
                return

            prompt = (
                "You are a concise engineering calculator. "
                "Analyze the circuit diagram or math problem in this image and provide "
                "a step-by-step solution. Use plain text ONLY. "
                "Do NOT use markdown symbols, bold tags, backticks, asterisks, or LaTeX formatting."
            )

            # Build the image part using the new types definition
            image_part = types.Part.from_bytes(
                data=image_data,
                mime_type="image/jpeg",
            )

            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=[prompt, image_part],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=512,
                )
            )

            solution_text = response.text.strip() if response and response.text else "No solution generated."

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(solution_text.encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Python Execution Error: {str(e)}".encode('utf-8'))

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"ESP32 Calculator Cloud Bridge is Online (Gemini 3.8 Flash)")
