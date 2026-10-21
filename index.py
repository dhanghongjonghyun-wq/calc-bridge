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
    text = text.replace("≈", "=")
    text = text.replace("**", "").replace("*", "")
    
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
            backup_models = [
                "google/gemma-4-31b-it:free",
                "openrouter/free"
            ]

            formatting_rule = " STRICT REQUIREMENT: Plain text only. No markdown, asterisks, bold tags, or approx symbols."

            if "text/plain" in content_type:
                user_expression = request.data.decode("utf-8", errors="ignore") if request.data else ""
                if not user_expression:
                    return "No expression", 200
                
                prompt = f"Solve concisely: {user_expression}. Short steps and final answer only.{formatting_rule}"
                
                payload = {
                    "models": backup_models,
                    "max_tokens": 200,  # Tightened to prevent length cutoffs
                    "messages": [{"role": "user", "content": prompt}]
                }
            else:
                image_bytes = request.data
                if not image_bytes:
                    return "No image", 200

                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                prompt = f"Analyze this image and provide a short numerical solution.{formatting_rule}"
                
                payload = {
                    "models": backup_models, 
                    "max_tokens": 200,
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

            or_response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=15)
            
            res_json = or_response.json()
            if "error" in res_json:
                return f"API Error: {res_json['error'].get('message', 'Unknown')}", 200

            choices = res_json.get("choices", [])
            if choices:
                choice = choices[0]
                message = choice.get("message", {})
                content = message.get("content")
                
                if not content:
                    content = choice.get("text", "")

                # Display whatever content came back, even if finish_reason was length
                if content and len(content.strip()) > 0:
                    solution_text = clean_for_display(content)
                else:
                    solution_text = f"Model Blank (Reason: {choice.get('finish_reason', 'unknown')})"
            else:
                solution_text = "API Error: No choices"
                
        except requests.exceptions.Timeout:
            solution_text = "Error: AI response timeout"
        except Exception as e:
            solution_text = f"Error: {str(e)}"
        
        latest_chat_history = solution_text
        return solution_text, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
