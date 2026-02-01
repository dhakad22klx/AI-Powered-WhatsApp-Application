import os
from io import BytesIO

import httpx
import uvicorn
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Query,
    Request,
    Response
)
from pyngrok import ngrok
from PIL import Image

from chat_history import WhatsAppMemory


# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
API_VERSION = os.getenv("API_VERSION", "v21.0")
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"


@asynccontextmanager
async def lifespan(app : FastAPI):
    # Startup
    app.state.http_client = httpx.AsyncClient()
    yield

    # Shutdown
    await app.state.http_client.aclose()

def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client

app = FastAPI(lifespan=lifespan)
memory = WhatsAppMemory()


# --- WEBHOOK VERIFICATION ---
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


# --- MAIN WEBHOOK RECEIVER ---
@app.post("/webhook")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
    client: httpx.AsyncClient = Depends(get_http_client)
):
    
    data = await request.json()
    print("data : ", data)

    try:
        value = data['entry'][0]['changes'][0]['value']
        if 'messages' in value:
            message = value['messages'][0]
            sender_phone = message['from']
            incoming_msg_id = message['id']
            msg_type = message.get('type')

            # 1. HANDLE TEXT
            if msg_type == 'text':
                text_body = message['text']['body'].lower()

                # Extract sender's profile name
                sender_name = value['contacts'][0]['profile']['name'] if 'contacts' in value else "Unknown"

                background_tasks.add_task(
                    handle_text_chat,
                    client,
                    sender_phone,
                    sender_name,
                    text_body, 
                    incoming_msg_id
                )

            # 2. HANDLE STICKER COMMAND (/s on an image)
            elif msg_type == 'image':
                caption = message['image'].get('caption', "").lower()
                print("Received image")
                if "/s" in caption:
                    # Simple parser: /s PackName | PublisherName
                    parts = caption.replace("/s", "").strip().split("|")
                    
                    pack_name = parts[0].strip() if len(parts) > 0 and parts[0] else "Creater"
                    publisher = parts[1].strip() if len(parts) > 1 else "Deepak Dhakad"
                    media_id = message['image']['id']

                    background_tasks.add_task(
                        handle_sticker_request,
                        client,
                        sender_phone,
                        media_id,
                        pack_name,
                        publisher
                    )

    except (KeyError, IndexError):
        pass

    return {"status": "success"}

# --- BACKGROUND LOGIC ---

async def handle_text_chat(
    client : httpx.AsyncClient,
    phone,
    sender_name,
    text,
    msg_id
):
    """Processes Text and sends text reply."""
    # Optional: Get context from memory
    USE_CONTEXT = True  # <-- change to False to disable context
    context = memory.get_context(phone, text)
    reply_text = f"Got it, {sender_name}!. You said: {text}"
    if USE_CONTEXT:
        context = memory.get_context(phone, text)
        reply_text += f"\n(Relevant Informatoin found in chat in history: {context})"
    
    await send_whatsapp_message(
        client=client,
        to_number=phone,
        text=reply_text,
        reply_to_id=msg_id
    )
    memory.save_message(phone, text)


async def handle_sticker_request(
    client : httpx.AsyncClient,
    phone,
    media_id,
    pack_name = "Creater",
    publisher="Deepak Dhakad"
):
    """Processes image to sticker transformation."""
    try:
        # A. Get Download URL
        media_info_url = f"{BASE_URL}/{media_id}"
        headers = {"Authorization": f"Bearer {TOKEN}"}
        resp = await client.get(
            media_info_url,
            headers=headers
        )
        download_url = resp.json().get("url")
        print(f"Received Download URL : {download_url}")

        # B. Download & Process Image
        img_resp = await client.get(download_url, headers=headers)
        img = Image.open(BytesIO(img_resp.content)).convert("RGBA")
        print(f"Processed Image")

        # Resize/Pad to exactly 512x512 transparent WebP - Sticker Canva
        img.thumbnail((512, 512), Image.Resampling.LANCZOS)
        sticker = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        sticker.paste(img, ((512 - img.width) // 2, (512 - img.height) // 2))

        webp_io = BytesIO()
        sticker.save(webp_io, format="WEBP")
        webp_data = webp_io.getvalue()

        # C. Upload Sticker to Meta
        upload_url = f"{BASE_URL}/{PHONE_NUMBER_ID}/media"
        files = {
            "file": ("sticker.webp", webp_data, "image/webp"),
            "messaging_product": (None, "whatsapp"),
        }
        upload_resp = await client.post(
            upload_url,
            headers=headers, 
            files=files
        )
        new_media_id = upload_resp.json().get("id")
        print("Uploaded sticker to meta")

        # D. Send Sticker
        await client.post(
            f"{BASE_URL}/{PHONE_NUMBER_ID}/messages",
            headers=headers,
            json={
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "sticker",
                "sticker": {"id": new_media_id}
            }
        )
        print("Sent requested sticker")

    except Exception as e:
        print(f"Sticker Error: {e}")

async def send_whatsapp_message(
    client : httpx.AsyncClient,
    to_number,
    text,
    reply_to_id=""
):
    """Async text sender."""
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    if reply_to_id:
        payload["context"] = {"message_id": reply_to_id}
    
    await client.post(
        f"{BASE_URL}/{PHONE_NUMBER_ID}/messages",
        headers=headers,
        json=payload
    )


# if __name__ == "__main__":
#     PORT = 8000

#     if os.getenv("NGROK_AUTH_TOKEN"):
#         ngrok.set_auth_token(os.getenv("NGROK_AUTH_TOKEN"))

#     public_url = ngrok.connect(PORT).public_url
#     print(f"Webhook URL: {public_url}/webhook")
#     uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    uvicorn.run(
        "start:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )