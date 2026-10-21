import os
import base64
import requests
import re
from flask import Flask, request

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
latest_chat_history = "Ready"

def clean_for_display(text):
    if not text:
        return ""
    text = text.replace("•", "-").replace("—", "-").replace("–", "-")
    text = text.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
    cleaned = re.sub(r'[^\x00-\x7F]+', '?', text)
    return cleaned.strip()

@app.route("/", methods=["GET", "POST"])
def bridge_handler():
    global latest_chat_history
    
    if request.method == "GET":
        return latest_chat_history, 200

    if request.method == "POST":
        try:
            content_type = request.headers.get("Content-Type", "")
            
            if "text/plain" in content_type:
                user_expression = request.data.decode("utf-8") if request.data else ""
                if not user_expression:
                    return "No expression", 400
                
                # Strict, concise prompt to prevent empty/long responses
                prompt = f"Calculate step by step: {user_expression}. Output plain text only, no markdown."
                
                payload = {
                    "model": "openrouter/free",
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": prompt}]
                }
            else:
                image_bytes = request.data
                if not image_bytes:
                    return "No image", 400

                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                prompt = "Analyze this image and solve step by step in plain text."
                
                payload = {
                    "model": "openrouter/free", 
                    "max_tokens": 512,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                            ]
                        }
                    ]
                }

            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }

            or_response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
            res_json = or_response.json()
            
            if "error" in res_json:
                return f"API Error: {res_json['error'].get('message', 'Unknown')}", 200

            # Safe extraction logic ensuring we catch nested data properly
            choices = res_json.get("choices", [])
            solution_text = ""
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content")
                if content:
                    solution_text = clean_for_display(content)
                else:
                    # Fallback check for alternative choice formats
                    solution_text = clean_for_display(choices[0].get("text", ""))

            if not solution_text:
                solution_text = f"Error: Empty output. Raw: {str(res_json)[:100]}"
                
        except Exception as e:
            solution_text = f"Error: {str(e)}"
        
        latest_chat_history = solution_text
        return solution_text, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
