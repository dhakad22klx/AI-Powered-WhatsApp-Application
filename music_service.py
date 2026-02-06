import os
from typing import List

import httpx

class LastFMService:
    BASE_URL = "http://ws.audioscrobbler.com/2.0/"

    def __init__(self):
        self.api_key = os.getenv("LASTFM_API_KEY")
        if not self.api_key:
            raise ValueError("LASTFM_API_KEY not set")
    
    async def _get(self, params : dict):
        params.update({
            "api_key": self.api_key,
            "format": "json"
        })

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_top_tracks_by_artist(
        self,
        artist: str,
        limit: int = 5
    ) -> List[str]:
        try:
            data = await self._get({
                "method": "artist.gettoptracks",
                "artist": artist,
                "limit": limit
            })

            print("data : ", data)
            return [
                {
                    "track_name": t["name"],
                    "artist": t["artist"]["name"],
                    "track_url": t["url"]
                }
                for t in data.get("toptracks", {}).get("track", [])
            ]
        except Exception as e:
            print(f"[LastFM] artist error: {e}")
            return []
    
