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
        
        # Handle Photo Inputs from Telegram
        if "photo" in message:
            photo = message["photo"][-1]
            file_id = photo["file_id"]
            
            file_info_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
            file_res = requests.get(file_info_url).json()
            
            if file_res.get("ok"):
                file_path = file_res["result"]["file_path"]
                download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                
                image_bytes = requests.get(download_url).content
                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                image_data_url = f"data:image/jpeg;base64,{base64_image}"
                
                prompt = (
                    "You are a concise engineering calculator. "
                    "Analyze the circuit diagram or math problem in this image and provide "
                    "a step-by-step solution. Use plain text ONLY. "
                    "Do NOT use markdown symbols, bold tags, backticks, asterisks, or LaTeX formatting."
                )
                
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "openrouter/free", 
                    "max_tokens": 1024,  # Prevents long multi-step solutions from cutting off early
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
                
                or_response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                res_json = or_response.json()
                
                try:
                    solution_text = res_json["choices"][0]["message"]["content"].strip()
                except Exception:
                    solution_text = f"Error processing image response: {res_json}"
                
                # Cache the complete history buffer for the calculator
                latest_chat_history = f"Q: [Photo Analysis]\n{solution_text}"

                # Send solution back to Telegram
                send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                requests.post(send_url, json={
                    "chat_id": chat_id,
                    "text": solution_text
                })

        # Handle Direct Text Inputs from Telegram
        elif "text" in message:
            text = message["text"]
            
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "openrouter/free",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": text}]
            }
            or_response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            res_json = or_response.json()
            
            try:
                solution_text = res_json["choices"][0]["message"]["content"].strip()
            except Exception:
                solution_text = "No response generated."
                
            latest_chat_history = f"Q: {text}\n{solution_text}"

            send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(send_url, json={
                "chat_id": chat_id,
                "text": solution_text
            })

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
