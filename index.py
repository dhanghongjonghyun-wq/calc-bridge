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
        return "No text returned"
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
                user_expression = request.data.decode("utf-8", errors="ignore") if request.data else ""
                if not user_expression:
                    return "No expression", 200
                
                prompt = f"Calculate: {user_expression}. Step by step."
                
                payload = {
                    "model": "openrouter/free",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}]
                }
            else:
                image_bytes = request.data
                if not image_bytes:
                    return "No image", 200

                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                prompt = "Analyze this image and solve step by step."
                
                payload = {
                    "model": "openrouter/free", 
                    "max_tokens": 1500,
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

            or_response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=20)
            res_json = or_response.json()
            
            if "error" in res_json:
                return f"API Error: {res_json['error'].get('message', 'Unknown')}", 200

            choices = res_json.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content")
                reasoning = message.get("reasoning") # Capture thinking steps from reasoning models
                
                # Fallback to reasoning text if content is blank due to length cutoff
                target_text = content if content else reasoning
                
                if target_text:
                    solution_text = clean_for_display(target_text)
                else:
                    solution_text = f"Model Blank (Reason: {choices[0].get('finish_reason', 'unknown')})"
            else:
                solution_text = "API Error: No choices"
                
        except Exception as e:
            solution_text = f"Error: {str(e)}"
        
        latest_chat_history = solution_text
        return solution_text, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
