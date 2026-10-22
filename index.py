import os
import base64
import requests
import re
import math
from flask import Flask, request

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
latest_chat_history = "Ready. Send an image to Telegram!"

def evaluate_math_expression(expr):
    """Safely evaluate standard math expressions in Python, supporting degrees for trig and ^ for exponents."""
    try:
        cleaned = expr.strip()
        cleaned = cleaned.replace('^', '**')
        
        safe_dict = {
            "sin": lambda x: math.sin(math.radians(x)),
            "cos": lambda x: math.cos(math.radians(x)),
            "tan": lambda x: math.tan(math.radians(x)),
            "asin": lambda x: math.degrees(math.asin(x)),
            "acos": lambda x: math.degrees(math.acos(x)),
            "atan": lambda x: math.degrees(math.atan(x)),
            "sqrt": math.sqrt,
            "log": math.log10,
            "ln": math.log,
            "pi": math.pi,
            "e": math.e,
            "abs": abs,
            "round": round,
        }
        
        for name in dir(math):
            if not name.startswith('_'):
                safe_dict[name] = getattr(math, name)
        
        result = eval(cleaned, {"__builtins__": {}}, safe_dict)
        
        if isinstance(result, float) and result.is_integer():
            result = int(result)
            
        return str(result)
    except Exception:
        return None

def clean_for_display(text):
    if not text:
        return "No text returned"
    
    text = text.replace(r"\times", "*").replace(r"\div", "/")
    text = text.replace(r"\approx", "~").replace(r"\cos", "cos")
    text = text.replace(r"\sin", "sin").replace(r"\tan", "tan")
    text = text.replace("$$", "").replace("$", "").replace("**", "")
    
    text = text.replace(r"\boxed", "").replace("{", "").replace("}", "")
    text = text.replace("---", "").replace("###", "")
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    
    text = text.replace("•", "-").replace("—", "-").replace("–", "-")
    text = text.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
    
    text = re.sub(r'(\d+)\s+(\d+\.\d+)\s*=', r'\1 * \2 =', text)
    
    lines = text.split('\n')
    cleaned_lines = [re.sub(r'[^\x00-\x7F]+', ' ', line) for line in lines]
    cleaned_lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in cleaned_lines]
    cleaned_lines = [line for line in cleaned_lines if line]
    
    return "\n".join(cleaned_lines)

# 1. Main ESP32 Endpoint (Handles direct text math expressions)
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
                
                direct_result = evaluate_math_expression(user_expression)
                if direct_result is not None:
                    solution_text = direct_result
                else:
                    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
                    
                    prompt = (
                        f"Solve directly: {user_expression}. "
                        "STRICT FORMATTING INSTRUCTIONS:\n"
                        "- NO introductory or concluding sentences.\n"
                        "- Use structured steps, equations, and summary tables only.\n"
                        "- Plain text, no conversational filler or yapping.\n"
                        "- Use explicit multiplication (*) and exponents (^).\n"
                        "- For trig, treat inputs as degrees and include radians in parentheses: X deg (Y rad)."
                    )
                    
                    payload = {
                        "contents": [{
                            "parts": [{"text": prompt}]
                        }]
                    }
                    
                    headers = {"Content-Type": "application/json"}
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
            else:
                solution_text = "Invalid Request Format"
                
        except requests.exceptions.Timeout:
            solution_text = "Error: AI response timeout"
        except Exception as e:
            solution_text = f"Error: {str(e)}"
        
        latest_chat_history = solution_text
        return solution_text, 200

# Explicit Poll Route for ESP32 Telegram Viewer sync
@app.route("/poll", methods=["GET"])
def poll_handler():
    global latest_chat_history
    return latest_chat_history, 200

# 2. Telegram Webhook Endpoint (Receives photos OR uncompressed files/documents)
@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    global latest_chat_history
    data = request.get_json()
    
    if not data or "message" not in data:
        return "OK", 200

    message = data["message"]
    chat_id = message["chat"]["id"]
    
    try:
        file_id = None
        
        # Check if sent as an uncompressed document/file
        if "document" in message:
            doc = message["document"]
            mime_type = doc.get("mime_type", "")
            if mime_type.startswith("image/"):
                file_id = doc["file_id"]
                
        # Fallback to standard compressed photos if not sent as a document
        elif "photo" in message and len(message["photo"]) > 0:
            photo = message["photo"][-1]
            file_id = photo["file_id"]

        caption = message.get("caption", message.get("text", "Solve this problem."))

        if file_id:
            file_info_res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}")
            file_info = file_info_res.json()
            
            if file_info.get("ok"):
                file_path = file_info["result"]["file_path"]
                image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
                
                # Fetch raw uncompressed image data
                img_res = requests.get(image_url)
                base64_image = base64.b64encode(img_res.content).decode('utf-8')
                
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
                
                prompt = (
                    f"User Caption / Request: {caption}\n"
                    "CRITICAL ENGINEERING SOLVER & MULTI-PROBLEM INSTRUCTIONS:\n"
                    "1. NO SKIPPING: If the worksheet contains multiple problems (e.g., Problem 1 AND Problem 2), you MUST solve ALL visible problems completely. Do NOT skip any problem unless explicitly told to in the caption.\n"
                    "2. SEPARATION: Use clear headers for each (e.g., 'PROBLEM 1' and 'PROBLEM 2').\n"
                    "3. RIGOROUS STATICS RULES:\n"
                    "   - Read node dimensions, loads, and angles carefully from the image.\n"
                    "   - Enforce correct sign conventions for moments (ΣM = 0) and equilibrium (ΣFx = 0, ΣFy = 0).\n"
                    "4. OUTPUT FORMAT FOR EACH PROBLEM:\n"
                    "   - Support Reactions\n"
                    "   - Method of Joints (Step-by-step)\n"
                    "   - Summary Table of Member Forces (Member | Force | State)\n"
                    "- NO conversational filler or yapping."
                )

                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                        ]
                    }]
                }
                
                response = requests.post(gemini_url, json=payload, timeout=30)
                gemini_res = response.json()
                
                if "error" in gemini_res:
                    error_msg = gemini_res['error'].get('message', 'Unknown API Error')
                    answer = f"API Error: {error_msg}"
                else:
                    candidates = gemini_res.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "No response")
                        answer = clean_for_display(content)
                    else:
                        answer = "Vision processing failed: No candidates returned."
                    
                latest_chat_history = answer
                
                # Send structured answer back to Telegram
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": answer
                })

    except Exception as e:
        print("Webhook Exception Error:", str(e))

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
