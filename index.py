import os
import base64
import requests
import re
from flask import Flask, request

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
latest_chat_history = "Ready"

def clean_for_display(text):
    if not text:
        return "No text returned"
    
    text = text.replace(r"\times", "*").replace(r"\div", "/")
    text = text.replace(r"\approx", "~").replace(r"\cos", "cos")
    text = text.replace(r"\sin", "sin").replace(r"\tan", "tan")
    text = text.replace("$$", "").replace("$", "").replace("**", "").replace("*", "")
    text = text.replace(r"\boxed", "").replace("{", "").replace("}", "")
    text = text.replace("---", "").replace("###", "")
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    
    text = text.replace("•", "-").replace("—", "-").replace("–", "-")
    text = text.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
    
    cleaned = re.sub(r'[^\x00-\x7F]+', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

@app.route("/", methods=["GET", "POST"])
def bridge_handler():
    global latest_chat_history
    
    if request.method == "GET":
        return latest_chat_history, 200

    if request.method == "POST":
        try:
            content_type = request.headers.get("Content-Type", "")
            
            # Updated to use gemini-3.8-flash
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={GEMINI_API_KEY}"

            if "text/plain" in content_type:
                user_expression = request.data.decode("utf-8", errors="ignore") if request.data else ""
                if not user_expression:
                    return "No expression", 200
                
                prompt = f"Solve directly and concisely: {user_expression}. Give short steps and the final answer. Plain text only, no markdown."
                
                payload = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }]
                }
            else:
                image_bytes = request.data
                if not image_bytes:
                    return "No image", 200

                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                prompt = "Analyze this image and provide a short numerical solution in plain text."
                
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": base64_image
                                }
                            }
                        ]
                    }]
                }

            headers = {
                "Content-Type": "application/json"
            }

            response = requests.post(gemini_url, headers=headers, json=payload, timeout=15)
            res_json = response.json()
            
            if "error" in res_json:
                return f"API Error: {res_json['error'].get('message', 'Unknown')}", 200

            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    content = parts[0].get("text", "")
                    solution_text = clean_for_display(content)
                else:
                    solution_text = "Model Blank: No parts returned"
            else:
                solution_text = "API Error: No candidates"
                
        except requests.exceptions.Timeout:
            solution_text = "Error: AI response timeout"
        except Exception as e:
            solution_text = f"Error: {str(e)}"
        
        latest_chat_history = solution_text
        return solution_text, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
