import os
import uvicorn
import requests
from fastapi import FastAPI, Request, Response, Query
from dotenv import load_dotenv
from pyngrok import ngrok
from chat_history import WhatsAppMemory

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN") 
API_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"

# Load environment variables from .env file
load_dotenv()
app = FastAPI()

# Initialize the memory module
memory = WhatsAppMemory()

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """Initial verification for Meta to trust your server."""
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
            incoming_msg_id = message['id']  # <--- Capture this ID

            # Extract sender's profile name
            sender_name = entry['contacts'][0]['profile']['name'] if 'contacts' in entry else "World"

            USE_CONTEXT = False  # <-- change to False to disable context

            previous_relevant_messages = None
            if USE_CONTEXT:
                # GetContext
                previous_relevant_messages = memory.get_context(sender_phone, text_body)

            msg_body = f"Hello {sender_name}!, You sent this message: {text_body}."

            if previous_relevant_messages:
                msg_body += f"\nAnd context: {previous_relevant_messages}"

            send_whatsapp_message(sender_phone, msg_body, incoming_msg_id)
            memory.save_message(sender_phone, text_body)

    except (KeyError, IndexError):
        pass

    return {"status": "success"}

def send_whatsapp_message(to_number, text, reply_to_id=""):
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


    # Add the context object if we want to reply to a specific message
    if reply_to_id!="":
        payload["context"] = {"message_id": reply_to_id}
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

if __name__ == "__main__":
    # --- NGROK SETUP ---
    PORT = 8000
    
    if NGROK_AUTH_TOKEN:
        ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    
    # Open a tunnel on the specified port
    public_url = ngrok.connect(PORT).public_url
    print(f"\n WhatsApp Bot is Live!")
    print(f" Public URL: {public_url}")
    print(f" Meta Webhook URL: {public_url}/webhook")
    print(f"Verify Token: {VERIFY_TOKEN}\n")

    # Run the FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=PORT)