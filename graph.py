from typing import TypedDict, Optional, List, Dict
from langgraph.graph import StateGraph, END

from music_service import LastFMService
from chat_history import WhatsAppMemory

class MusicState(TypedDict):
    phone: str
    text: str
    mood: Optional[str]
    artists: List[str]
    genres: List[str]
    recommendations: List[Dict]
    final_reply: str


class MusicRecommendationGraph:
    def __init__(self):
        self.music_service = LastFMService()
        self.memory = WhatsAppMemory()
        self.graph = StateGraph(MusicState)
        self._build_graph()

    # ---------- NODES ----------

    def parse_intent(self, state: MusicState) -> MusicState:
        text = state["text"].lower()

        mood = None
        if "sad" in text:
            mood = "sad"
        elif "happy" in text:
            mood = "happy"

        artists = []
        if "arijit" in text:
            artists.append("Arijit Singh")

        return {
            **state,
            "mood": mood,
            "artists": artists
        }

    def update_memory(self, state: MusicState) -> MusicState:
        # uncomment if need to save message in db
        # self.memory.save_message(state["phone"], state["text"])
        return state

    async def fetch_music(self, state: MusicState) -> MusicState:
        recs: List[str] = []

        for artist in state["artists"]:
            tracks = await self.music_service.get_top_tracks_by_artist(artist)
            recs.extend(tracks)

        return {
            **state,
            "recommendations": recs[:5]
        }

    def generate_reply(self, state: MusicState) -> MusicState:
        recs = state.get("recommendations", [])

        if not recs:
            reply = "Tell me an artist, genre, or mood 🎧. I will provide songs for you. (Eg - Arijit singh)"
        else:
            lines = ["🎶 Recommended for you:\n"]

            for i, track in enumerate(recs, start=1):
                lines.append(
                    f"{i}️ : {track['track_name']} – {track['artist']}\n"
                    f"▶️ Listen: {track['track_url']}\n"
                )

            reply = "\n".join(lines)

        return {
            **state,
            "final_reply": reply
        }


    # ---------- GRAPH ----------
    def _build_graph(self):
        self.graph.add_node("parse_intent", self.parse_intent)
        self.graph.add_node("update_memory", self.update_memory)
        self.graph.add_node("fetch_music", self.fetch_music)
        self.graph.add_node("generate_reply", self.generate_reply)

        self.graph.set_entry_point("parse_intent")
        self.graph.add_edge("parse_intent", "update_memory")
        self.graph.add_edge("update_memory", "fetch_music")
        self.graph.add_edge("fetch_music", "generate_reply")
        self.graph.add_edge("generate_reply", END)

        self.app = self.graph.compile()

    async def run(self, phone: str, text: str) -> str:
        result = await self.app.ainvoke({
            "phone": phone,
            "text": text,
            "mood": None,
            "artists": [],
            "genres": [],
            "recommendations": [],
            "final_reply": ""
        })
        return result["final_reply"]
