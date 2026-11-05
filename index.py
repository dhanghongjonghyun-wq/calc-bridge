import os
import base64
import requests
import re
import math
import time
from flask import Flask, request

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
latest_chat_history = "Ready. Send an image to Telegram!"

# Persistent session for faster API requests
session = requests.Session()

# Model Endpoint
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={GEMINI_API_KEY}"
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

ENGINEERING_PROMPT_TEMPLATE = (
    "User Caption / Request: {{caption}}\n"
    "CIRCUIT & TRUSS SOLVER INSTRUCTIONS:\n"
    "1. ACCURATE POLARITIES, KVL, KCL, & TRUSS MECHANICS:\n"
    "   - Long line = Positive (+), Short line = Negative (-).\n"
    "   - When tracing clockwise, entering a negative terminal is -V; entering a positive terminal is +V.\n"
    "2. STRICT FORMATTING & STRUCTURE:\n"
    "   - Follow this exact 3-section structure with NO conversational filler, intro/outro remarks, or yapping:\n"
    "     1st Givens\n"
    "     2nd Step-by-Step Formula Solution (Write out full, expanded steps: KVL / KCL / moment equations, substitution, distribution, combining terms, solving for variables explicitly).\n"
    "     3rd Final Answers\n"
    "   - DO NOT use LaTeX formatting like \\cdot, \\text{{}}, \\Omega, or backslashes. Write multiplication explicitly with '*' or spaces, and units plainly (e.g., 20.00 V, 8.00 ohms, kN, A, W).\n"
    "   - NO fractions allowed.\n"
    "   - ALL numerical values and final answers MUST be rounded to EXACTLY TWO DECIMAL PLACES.\n"
    "   - CRITICAL: Never stutter, duplicate decimal points, or output malformed numbers (e.g., NEVER write '70000.0.00.00' or '-100.0.00.00'). Always write clean single-decimal numbers like '70000.00'.\n"
    "   - FOR TRUSS PROBLEMS (METHOD OF JOINTS): \n"
    "     * You MUST systematically move joint by joint (A -> B -> C -> D -> E) and double-check vector signs ($+\\cos\\theta, -\\sin\\theta$). \n"
    "     * Exploit symmetry where applicable (e.g., mirror joints like B and D must match magnitudes). \n"
    "     * Every final member force answer MUST explicitly state whether it is in **Tension** or **Compression** (e.g., Fab = -4041.45 lb (Compression)).\n"
)

def post_with_retry(url, json_payload, retries=3, backoff=2):
    """Sends a POST request to Gemini with automatic retries if high demand or temporary errors occur."""
    for attempt in range(retries):
        try:
            response = session.post(url, json=json_payload, timeout=30)
            res_json = response.json()
            
            if "error" in res_json:
                err_msg = res_json['error'].get('message', '')
                if "high demand" in err_msg.lower() or "overloaded" in err_msg.lower() or "unavailable" in err_msg.lower():
                    if attempt < retries - 1:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
            return res_json
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(backoff)
                continue
            raise
        except Exception:
            raise
    return {"error": {"message": "API is busy after multiple retries."}}

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

def fix_malformed_numbers(text):
    """Aggressively catches and fixes any multi-dot decimal stutters (e.g., 70000.0.00.00 -> 70000.00)."""
    def sanitize_match(m):
        full_str = m.group(0)
        parts = full_str.split('.')
        if len(parts) > 2:
            integer_part = parts[0]
            decimal_part = parts[1] if len(parts[1]) > 0 else "00"
            return f"{integer_part}.{decimal_part[:2].ljust(2, '0')}"
        return full_str
    
    return re.sub(r'-?\b\d+(?:\.\d+){2,}\b', sanitize_match, text)

def clean_for_display(text):
    if not text:
        return "No text returned"
    
    text = fix_malformed_numbers(text)
    text = re.sub(r'-100\.0(?:\.\d+)+', '-100.00', text)
    text = re.sub(r'(-?\d+)\.(\d+)\.(\
    
