import os
import base64
import requests
import re
from flask import Flask, request

app = Flask(__name__)

# Pulls Venice API key (falls back to checking OPENROUTER_API_KEY if variable name wasn't changed)
VENICE_API_KEY = os.environ.get("VENICE_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
latest_chat_history = "Ready"

def clean_for_display(text):
    if not text:
        return "No text returned"
    
    # Filter out any stray system/safety text lines
    lines = text.split('\n')
    filtered_lines = [line for line in lines if "user safety" not in line.lower() and "safety:" not in line.lower()]
    text = "\n".join(filtered_lines)
    
    # Clean math syntax for text displays
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
            
            venice_url = "https://api.venice.ai/api/v1/chat/completions"
            model_name = "venice-uncensored-1-2"  # Fast, reliable unserved text/chat model

            if "text/plain" in content_type:
                user_expression = request.data.decode("utf-8", errors="ignore") if request.data else ""
                if not user_expression:
                    return "No expression", 200
                
                prompt = f"Solve directly and concisely: {user_expression}. Short steps and final answer only. Plain text, no markdown."
                
                payload = {
                    "model": model_name,
                    "max_tokens": 400,
                    "messages": [{"role": "user", "content": prompt}]
                }
            else:
                image_bytes = request.data
                if not image_bytes:
                    return "No image", 200

                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                prompt = "Analyze this image and provide a short numerical solution in plain text."
                
                payload = {
                    "model": model_name, 
                    "max_tokens": 400,
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
                "Authorization": f"Bearer {VENICE_API_KEY}",
                "Content-Type": "application/json"
            }

            response = requests.post(venice_url, headers=headers, json=payload, timeout=15)
            res_json = response.json()
            
            if "error" in res_json:
                return f"API Error: {res_json['error'].get('message', 'Unknown')}", 200

            choices = res_json.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content")
                if content and len(content.strip()) > 0:
                    solution_text = clean_for_display(content)
                else:
                    solution_text = f"Model Blank (Reason: {choices[0].get('finish_reason', 'unknown')})"
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
