import httpx
import os
from PIL import Image, ImageOps
from io import BytesIO

# Configuration (Use your actual values or env vars)
WHATSAPP_TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
API_VERSION = os.getenv("API_VERSION")


class StickerService:
    @staticmethod
    async def get_media_url(media_id: str):
        """Fetches the actual download URL for a media ID from Meta."""
        url = f"https://graph.facebook.com/{API_VERSION}/{media_id}"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            return resp.json().get("url")

    @staticmethod
    async def download_and_convert(media_url: str):
        """Downloads the image and converts it to a 512x512 WebP."""
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(media_url, headers=headers)
            if resp.status_code != 200:
                return None

            # Open image from memory
            img = Image.open(BytesIO(resp.content))
            
            # Resize and Pad to 512x512 (WhatsApp Requirement)
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            
            # Create a transparent 512x512 canvas
            sticker = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            # Center the image on the canvas
            sticker.paste(img, ((512 - img.width) // 2, (512 - img.height) // 2))
            
            output = BytesIO()
            sticker.save(output, format="WEBP")
            return output.getvalue()

    @staticmethod
    async def upload_sticker(webp_data: bytes):
        """Uploads the WebP file to Meta and returns a Media ID."""
        url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/media"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        files = {
            "file": ("sticker.webp", webp_data, "image/webp"),
            "messaging_product": (None, "whatsapp"),
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, files=files)
            return resp.json().get("id")

    @staticmethod
    async def send_sticker(to_number: str, media_id: str):
        """Sends the final sticker to the user."""
        url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "sticker",
            "sticker": {"id": media_id}
        }
        async with httpx.AsyncClient() as client:
            await client.post(url, headers=headers, json=payload)