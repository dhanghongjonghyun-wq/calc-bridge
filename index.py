import os
import base64
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Store the latest conversation in memory for the calculator to pull via GET
latest_chat_history = "No messages yet. Send a photo or text via Telegram!"

@app.route("/", methods=["GET", "POST"])
def bridge_handler():
    global latest_chat_history
    
    # Handle GET request from ESP32 Calculator (Viewing Chat History)
    if request.method == "GET":
        return latest_chat_history, 200

    update = request.get_json(silent=True)
    if update and "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://esp32-calc-bridge.onrender.com",
            "X-Title": "ESP32 Telegram Calc"
        }
        
        solution_text = ""
        
        # Handle Photo Inputs from Telegram
        if "photo" in message:
            photo = message["photo"][-1]
            file_id = photo["file_id"]
            
            file_info_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
            file_res = requests.get(file_info_url, timeout=10).json()
            
            if file_res.get("ok"):
                file_path = file_res["result"]["file_path"]
                download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                
                image_bytes = requests.get(download_url, timeout=15).content
                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                image_data_url = f"data:image/jpeg;base64,{base64_image}"
                
                prompt = (
                    "Solve the math or electric circuit problem shown in this diagram step-by-step. "
                    "Output the calculation concisely. "
                    "Use plain text strictly. No markdown, no bold, no LaTeX, no asterisks."
                )
                
                payload = {
                    "model": "deepseek/deepseek-v4.1-flash-1017",  # Updated to DeepSeek V4.1 Flash
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
                
                try:
                    or_response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=25)
                    res_json = or_response.json()
                    
                    if "choices" in res_json and len(res_json["choices"]) > 0:
                        msg_content = res_json["choices"][0]["message"].get("content")
                        if msg_content:
                            solution_text = msg_content.strip()
                        else:
                            solution_text = "AI Error: Response content was empty or filtered."
                    else:
                        error_msg = res_json.get('error', {}).get('message', 'Unknown response structure')
                        solution_text = f"AI Error: {error_msg}"
                except Exception as e:
                    solution_text = f"Connection error processing image: {str(e)}"
                
                latest_chat_history = f"Q: [Photo Analysis]\n{solution_text}"

        # Handle Direct Text Inputs from Telegram
        elif "text" in message:
            text = message["text"]
            
            payload = {
                "model": "deepseek/deepseek-v4.1-flash-1017",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": text}]
            }
            
            try:
                or_response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=20)
                res_json = or_response.json()
                
                if "choices" in res_json and len(res_json["choices"]) > 0:
                    msg_content = res_json["choices"][0]["message"].get("content")
                    if msg_content:
                        solution_text = msg_content.strip()
                    else:
                        solution_text = "AI Error: Response content was empty."
                else:
                    error_msg = res_json.get('error', {}).get('message', 'Unknown response structure')
                    solution_text = f"AI Error: {error_msg}"
            except Exception as e:
                solution_text = f"Connection error processing text: {str(e)}"
                
            latest_chat_history = f"Q: {text}\n{solution_text}"

        # Send clean text back to Telegram if a valid solution was generated
        if solution_text:
            send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(send_url, json={
                "chat_id": chat_id,
                "text": solution_text
            }, timeout=10)

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
