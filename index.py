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
    
    # Automatically fix missing multiplication operators before an equals sign (e.g., "60 0.766 = 45.96" -> "60 * 0.766 = 45.96")
    text = re.sub(r'(\d+)\s+(\d+\.\d+)\s*=', r'\1 * \2 =', text)
    
    # Keep newlines intact while cleaning spacing and non-ASCII characters per line
    lines = text.split('\n')
    cleaned_lines = [re.sub(r'[^\x00-\x7F]+', ' ', line) for line in lines]
    cleaned_lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in cleaned_lines]
    cleaned_lines = [line for line in cleaned_lines if line]
    
    return "\n".join(cleaned_lines)

@app.route("/", methods=["GET", "POST"])
def bridge_handler():
    global latest_chat_history
    
    if request.method == "GET":
        return latest_chat_history, 200

    if request.method == "POST":
        try:
            content_type = request.headers.get("Content-Type", "")
            
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}"

            if "text/plain" in content_type:
                user_expression = request.data.decode("text/plain" if False else "utf-8", errors="ignore") if request.data else ""
                if not user_expression:
                    return "No expression", 200
                
                # Explicitly mandate operator usage in the prompt
                prompt = (
                    f"Solve directly and concisely: {user_expression}. "
                    "Give short steps and the final answer. Plain text only, no markdown. "
                    "CRITICAL: Always use explicit multiplication signs (*). Never omit operators or use spaces between numbers for multiplication."
                )
                
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
                prompt = "Analyze this image and provide a short numerical solution in plain text with explicit operators."
                
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
