import os
import base64
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

@app.route("/", methods=["GET", "POST"])
def bridge_handler():
    if request.method == "GET":
        return "Telegram Calculator Bridge via OpenRouter is Online!", 200

    update = request.get_json(silent=True)
    if update and "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        
        # Handle Photo Inputs from Telegram
        if "photo" in message:
            photo = message["photo"][-1]
            file_id = photo["file_id"]
            
            # Get file path from Telegram API
            file_info_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
            file_res = requests.get(file_info_url).json()
            
            if file_res.get("ok"):
                file_path = file_res["result"]["file_path"]
                download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                
                # Download image bytes and encode to base64 data URI
                image_bytes = requests.get(download_url).content
                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                image_data_url = f"data:image/jpeg;base64,{base64_image}"
                
                prompt = (
                    "You are a concise engineering calculator. "
                    "Analyze the circuit diagram or math problem in this image and provide "
                    "a step-by-step solution. Use plain text ONLY. "
                    "Do NOT use markdown symbols, bold tags, backticks, asterisks, or LaTeX formatting."
                )
                
                # Call OpenRouter API
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "openrouter/free", 
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
                
                # Send solution back to Telegram
                send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                requests.post(send_url, json={
                    "chat_id": chat_id,
                    "text": solution_text
                })

        # Handle Direct Text Inputs
        elif "text" in message:
            text = message["text"]
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": text}]
            }
            or_response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            res_json = or_response.json()
            
            try:
                solution_text = res_json["choices"][0]["message"]["content"].strip()
            except Exception:
                solution_text = "No response generated."
                
            send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(send_url, json={
                "chat_id": chat_id,
                "text": solution_text
            })

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
