import os
import uvicorn
import requests
from fastapi import FastAPI, Request, Response, Query
from dotenv import load_dotenv
from pyngrok import ngrok

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
# Optional: Get ngrok auth token from .env for a seamless setup
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN") 

API_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """Initial verification for Meta to trust your server."""
    print("WEBHOOK_VERIFIED")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("WEBHOOK_VERIFIED")
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

@app.post("/webhook")
async def receive_message(request: Request):
    """Processes incoming messages and sends a reply."""
    data = await request.json()
    
    # Helpful for debugging: print the incoming JSON to your Ubuntu terminal
    print(f"Incoming data: {data}") 

    try:
        entry = data['entry'][0]['changes'][0]['value']
        if 'messages' in entry:
            message = entry['messages'][0]
            sender_phone = message['from']
            text_body = message['text']['body'].lower()

            # Extract sender's profile name
            sender_name = entry['contacts'][0]['profile']['name'] if 'contacts' in entry else "World"

            # if "hi" in text_body:
            #     # REPLACED fixed number with sender_phone
            #     send_whatsapp_message(sender_phone, f"Hello {sender_name}!")
            send_whatsapp_message(sender_phone, f"""
                                  Hello {sender_name}!, You sent this message below : 
                                  \n 
                                  {text_body}""")

    except (KeyError, IndexError):
        pass

    return {"status": "success"}

def send_whatsapp_message(to_number, text):
    """Sends a text message using the WhatsApp Cloud API."""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,  # Dynamically use the sender's number
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

if __name__ == "__main__":
    # --- NGROK SETUP ---
    PORT = 8000
    
    if NGROK_AUTH_TOKEN:
        ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    
    # Open a tunnel on the specified port
    public_url = ngrok.connect(PORT).public_url
    print(f"\n🚀 WhatsApp Bot is Live!")
    print(f"🔗 Public URL: {public_url}")
    print(f"👉 Meta Webhook URL: {public_url}/webhook")
    print(f"🔑 Verify Token: {VERIFY_TOKEN}\n")

    # Run the FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=PORT)