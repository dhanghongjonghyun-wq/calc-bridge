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

# Persistent session for faster API requests
session = requests.Session()

# Model Endpoint
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Note: Curly braces are doubled {{ }} so Python's .format() doesn't crash on them
ENGINEERING_PROMPT_TEMPLATE = (
    "User Caption / Request: {{caption}}\n"
    "CIRCUIT SOLVER INSTRUCTIONS:\n"
    "1. ACCURATE POLARITIES & KVL TRACE:\n"
    "   - Long line = Positive (+), Short line = Negative (-).\n"
    "   - When tracing clockwise, entering a negative terminal is -V; entering a positive terminal is +V.\n"
    "   - Note: Entering the negative terminal of the 36V source on top going clockwise is a potential rise (+36V).\n"
    "2. FORMATTING RULES (STRICT PLAIN TEXT):\n"
    "   - DO NOT use LaTeX formatting like \\cdot, \\text{{}}, \\Omega, or backslashes. Write multiplication explicitly with '*' or spaces, and units plainly (e.g., 20.00 V, 8.00 ohms, A).\n"
    "   - NO conversational filler, no introductory/concluding remarks, and no yapping.\n"
    "   - List givens compactly.\n"
    "   - NO fractions allowed (e.g. no '-100/22').\n"
    "   - ALL numerical values and final answers MUST be rounded to EXACTLY TWO DECIMAL PLACES.\n"
    "3. OUTPUT STRUCTURE:\n"
    "   - Givens list\n"
    "   - Constraint Equation\n"
    "   - Supermesh KVL Equation & Step-by-Step Solution\n"
    "   - Final Summary Table (Parameter | Value | Unit)"
)

def evaluate_math_expression(expr):
    """Safely evaluate standard math expressions in Python, supporting degrees for trig and ^ for exponents."""
    try:
        cleaned = expr.strip().replace('^', '**')
        
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
        if isinstance(result, float):
            result = round(result, 2)
            if result.is_integer():
                result = int(result)
        return str(result)
    except Exception:
        return None

def convert_fractions_to_decimals(text):
    """Converts standalone fractions to 2-decimal floating point numbers as a failsafe."""
    def replacer(match):
        num = float(match.group(1))
        den = float(match.group(2))
        if den == 0:
            return match.group(0)
        val = num / den
        return f"{val:.2f}"
    
    return re.sub(r'(-?\d+)\s*/\s*(\d+)', replacer, text)

def clean_for_display(text):
    if not text:
        return "No text returned"
    
    # Aggressively strip out LaTeX artifact wrappers (\cdot, \text{}, \Omega, etc.)
    text = text.replace(r"\cdot", "*")
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\Omega\b', 'ohms', text, flags=re.IGNORECASE)
    text = re.sub(r'\\omega\b', 'ohms', text, flags=re.IGNORECASE)
    text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)
    
    # Clean standard LaTeX math formatting
    text = text.replace(r"\times", "*").replace(r"\div", "/")
    text = text.replace(r"\approx", "~").replace(r"\cos", "cos")
    text = text.replace(r"\sin", "sin").replace(r"\tan", "tan")
    text = text.replace("$$", "").replace("$", "").replace("**", "")
    text = text.replace(r"\boxed", "").replace("{", "").replace("}", "")
    text = text.replace("---", "").replace("###", "")
    text = text.replace("\\", "")  # Strip any remaining stray backslashes
    
    text = text.replace("•", "-")
    text = text.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
    
    text = convert_fractions_to_decimals(text)
    
    lines = text.split('\n')
    cleaned_lines = [re.sub(r'[^\x00-\x7F]+', ' ', line) for line in lines]
    cleaned_lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in cleaned_lines]
    return "\n".join([line for line in cleaned_lines if line])

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
                    prompt = (
                        f"Solve directly: {user_expression}. "
                        "STRICT FORMATTING:\n"
                        "- No backslashes, \cdot, or LaTeX text blocks.\n"
                        "- No intro/outro sentences or yapping.\n"
                        "- Round all numbers to exactly two decimal places. No fractions."
                    )
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.0,
                            "topP": 0.1
                        }
                    }
                    response = session.post(GEMINI_API_URL, json=payload, timeout=15)
                    res_json = response.json()
                    
                    if "error" in res_json:
                        return f"API Error: {res_json['error'].get('message', 'Unknown')}", 200

                    candidates = res_json.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        solution_text = clean_for_display(content)
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

# 2. Telegram Webhook Endpoint
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
        
        if "document" in message and message["document"].get("mime_type", "").startswith("image/"):
            file_id = message["document"]["file_id"]
        elif "photo" in message and len(message["photo"]) > 0:
            file_id = message["photo"][-1]["file_id"]

        caption = message.get("caption", message.get("text", "Solve this problem."))

        if file_id:
            file_info_res = session.get(f"{TELEGRAM_API_BASE}/getFile?file_id={file_id}")
            file_info = file_info_res.json()
            
            if file_info.get("ok"):
                file_path = file_info["result"]["file_path"]
                image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
                
                img_res = session.get(image_url)
                base64_image = base64.b64encode(img_res.content).decode('utf-8')
                
                prompt = ENGINEERING_PROMPT_TEMPLATE.format(caption=caption)
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.0,
                        "topP": 0.1,
                        "topK": 1
                    }
                }
                
                response = session.post(GEMINI_API_URL, json=payload, timeout=30)
                gemini_res = response.json()
                
                if "error" in gemini_res:
                    answer = f"API Error: {gemini_res['error'].get('message', 'Unknown API Error')}"
                    print(f"Gemini Error Log: {answer}")
                else:
                    candidates = gemini_res.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "No response")
                        answer = clean_for_display(content)
                    else:
                        answer = "Vision processing failed: No candidates returned."
                    
                latest_chat_history = answer
                
                session.post(f"{TELEGRAM_API_BASE}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": answer
                })

    except Exception as e:
        print(f"Webhook Exception Error: {str(e)}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
