import os
import google.generativeai as genai
from http.server import BaseHTTPRequestHandler

# Configure your Gemini API key from environment variables
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Read the raw JPEG bytes sent directly from the ESP32-S3
            content_length = int(self.headers.get('Content-Length', 0))
            image_data = self.rfile.read(content_length)

            if not image_data:
                self.send_response(400)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Error: Received empty image payload.")
                return

            # Initialize Gemini 3.8 Flash model
            generation_config = {
                "temperature": 0.1,
                "max_output_tokens": 512,
            }
            
            # Using Gemini 3.8 Flash for high-speed circuit and math problem-solving
            model = genai.GenerativeModel(
                model_name='gemini-3.8-flash',
                generation_config=generation_config
            )

            # Pass the raw image bytes alongside a clear engineering prompt
            prompt = (
                "You are a concise engineering calculator. "
                "Analyze the circuit diagram or math problem in this image and provide "
                "a step-by-step solution. Use plain text ONLY. "
                "Do NOT use markdown symbols, bold tags, backticks, asterisks, or LaTeX formatting."
            )

            # Send the image payload to Gemini
            response = model.generate_content([
                prompt,
                {
                    "mime_type": "image/jpeg",
                    "data": image_data
                }
            ])

            solution_text = response.text.strip() if response and response.text else "No solution generated."

            # Send the plain-text response back to the ESP32-S3 display
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(solution_text.encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Google API Error: {str(e)}".encode('utf-8'))

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"ESP32 Calculator Cloud Bridge is Online (Gemini 3.8 Flash)")
