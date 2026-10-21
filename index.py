import os
import base64
import requests
import re
from flask import Flask, request

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
latest_chat_history = "No calculations performed yet."

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
        content_type = request.headers.get("Content-Type", "")
        
        # Case 1: Text Query from AI Calculator Mode
        if "text/plain" in content_type:
            user_expression = request.data.decode("utf-8")
            if not user_expression:
                return "No expression received", 400
                
            prompt = (
                "You are a precise engineering and scientific calculator. "
                f"Evaluate this expression and explain the solution step-by-step: {user_expression}. "
                "Use PLAIN ASCII TEXT ONLY. Do NOT use markdown asterisks (*), hashtags, "
                "bold formatting, backticks, bullet points, or LaTeX math blocks."
            )
            
            payload = {
                "model": "google/gemma-4-31b-it:free",  # Stable free multimodal model
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]
            }
            
        # Case 2: Image Query from OV5640 Camera Mode
        else:
            image_bytes = request.data
            if not image_bytes:
                return "No image data received", 400

            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            image_data_url = f"data:image/jpeg;base64,{base64_image}"
            
            prompt = (
                "You are a concise engineering calculator. "
                "Analyze the equation or circuit diagram in this image "
                "and provide a step-by-step numerical solution. "
                "Use PLAIN ASCII TEXT ONLY. No markdown, asterisks, bullets, or LaTeX."
            )
            
            payload = {
                "model": "google/gemma-4-31b-it:free", 
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data_url}}
                        ]
                    }
                ]
            }

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            or_response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions", 
                headers=headers, 
                json=payload, 
                timeout=40
            )
            res_json = or_response.json()
            
            # Debug log to Render console if something unexpected happens
            if "error" in res_json:
                return f"API Error: {res_json['error'].get('message', 'Unknown')}", 500

            choices = res_json.get("choices")
            if choices and len(choices) > 0:
                message = choices[0].get("message", {})
                content = message.get("content")
                if content:
                    solution_text = clean_for_display(content)
                else:
                    solution_text = f"Error: Empty content from model. Raw: {res_json}"
            else:
                solution_text = f"API Error: Invalid response -> {res_json}"
                
        except Exception as e:
            solution_text = f"Bridge Exception: {str(e)}"
        
        latest_chat_history = solution_text
        return solution_text, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
