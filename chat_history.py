import os
from datetime import datetime
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

class WhatsAppMemory:
    def __init__(self):
        # 1. Initialize Pinecone client
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index_name = "whatapp-bot-rag"
        
        # 2. Connect to the existing index
        # We assume the index was created with Integrated Embedding
        self.index = self.pc.Index(self.index_name)

    def save_message(self, phone_number, text):
        """
        Saves a user or bot message into a Pinecone namespace.
        Namespace = Phone Number (e.g., '919131880463')
        """
        # Create a unique record ID
        record_id = f"{phone_number}_{datetime.now().timestamp()}"
        
        # Prepare the record
        # Note: 'text' field is what Pinecone embeds automatically
        record = {
                "id": record_id,
                "text": text,
                "phone": phone_number,
                "timestamp": str(datetime.now())
            }
        
        try:
            # Using phone_number as namespace for isolation
            self.index.upsert_records(
                namespace=phone_number, 
                records=[record]
            )
            print(f"DEBUG: Saved msg to namespace {phone_number}")
        except Exception as e:
            print(f"ERROR saving to Pinecone: {e}")

    def get_context(self, phone_number, query_text, top_k=2): #Semandtic search as index is dense.
        """
        Searches ONLY the specific user's namespace for relevant past messages.
        """
        try:
            results = self.index.search(
                namespace=str(phone_number),
                query={
                    "inputs": {"text": query_text},
                    "top_k": top_k
                }
            )
            
            history_snippets = []
            
            # Check if we actually got hits back
            hits = results.get('result', {}).get('hits', [])
            
            for hit in hits:
                # IMPORTANT: Fields are in 'fields', not 'metadata'
                fields = hit.get('fields', {})
                
                # Access the data we flattened in the previous step
                content = fields.get('text', '') # This matches your field_map "text"
                
                if content:
                    history_snippets.append(f"{content}")
            
            # Reverse snippets if you want chronological order (Pinecone returns most relevant first)
            return "\n".join(history_snippets)
            
        except Exception as e:
            print(f"ERROR searching Pinecone: {e}")
            return ""

# Example usage:
# memory = WhatsAppMemory()
# memory.save_message("919131880463", "My instagram is @deepak", "user")
# context = memory.get_context("919131880463", "what is my instagram?")