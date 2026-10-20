import os
import requests
from flask import Flask, request, Response
from google import genai
from google.genai import types

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

@app.route("/", methods=["GET", "POST"])
def bridge_handler():
    if request.method == "GET":
        return "Telegram Calculator Bot Bridge is Online!", 200

    # Handle incoming Telegram Webhook updates
    update = request.get_json(silent=True)
    if update and "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]

        # Check if the user sent a photo
        if "photo" in message:
            # Get the highest resolution photo available
            photo = message["photo"][-1]
            file_id = photo["file_id"]

            # Get file path from Telegram API
            file_info_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
            file_res = requests.get(file_info_url).json()

            if file_res.get("ok"):
                file_path = file_res["result"]["file_path"]
                download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"

                # Download the image bytes
                image_bytes = requests.get(download_url).content

                # Process with Gemini
                api_key = os.environ.get("GEMINI_API_KEY")
                client = genai.Client(api_key=api_key)

                prompt = (
                    "You are a concise engineering calculator. "
                    "Analyze the circuit diagram or math problem in this image and provide "
                    "a step-by-step solution. Use plain text ONLY. "
                    "Do NOT use markdown symbols, bold tags, backticks, asterisks, or LaTeX formatting."
                )

                image_part = types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg",
                )

                response = client.models.generate_content(
                    model='gemini-flash-latest',
                    contents=[prompt, image_part],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=512,
                    )
                )

                solution_text = response.text.strip() if response and response.text else "No solution generated."

                # Send reply back to Telegram
                send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                requests.post(send_url, json={
                    "chat_id": chat_id,
                    "text": solution_text
                })

        elif "text" in message:
            # Handle optional text queries if you type a math problem directly
            chat_id = message["chat"]["id"]
            text = message["text"]

            api_key = os.environ.get("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)

            response = client.models.generate_content(
                model='gemini-flash-latest',
                contents=[text],
            )
            solution_text = response.text.strip() if response and response.text else "No response."

            send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(send_url, json={
                "chat_id": chat_id,
                "text": solution_text
            })

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
