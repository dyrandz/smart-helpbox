from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests, json, os
import hashlib
from pathlib import Path
import faiss
from pydantic import BaseModel
from typing import List, Optional
from services import (
    get_organisation_id_by_name,
    get_adviser_id_by_name,
    get_adviser_id_by_email,
    get_client_id_by_name,
    get_client_id_by_email
)

from llama_index.core import VectorStoreIndex, Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.faiss.base import FaissVectorStore
from llama_index.core.storage.storage_context import StorageContext
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Use host.docker.internal when running in Docker, localhost when running locally
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234")
MODEL = "mistral-7b-instruct-v0.3"
ROUTE_DATA_PATH = "routes.json"
VECTOR_STORE_PATH = "vector_store"
VECTOR_STORE_HASH_PATH = "vector_store_hash.txt"

# Use Gemini API instead of LM Studio
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your_gemini_api_key")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Create vector store directory if it doesn't exist
Path(VECTOR_STORE_PATH).mkdir(exist_ok=True)

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def save_vector_store_hash(hash_value):
    """Save the hash of the routes.json file"""
    with open(VECTOR_STORE_HASH_PATH, "w") as f:
        f.write(hash_value)

def load_vector_store_hash():
    """Load the saved hash of the routes.json file"""
    if os.path.exists(VECTOR_STORE_HASH_PATH):
        with open(VECTOR_STORE_HASH_PATH, "r") as f:
            return f.read().strip()
    return None

def build_vector_index():
    """Build and save the vector index"""
    # Load and convert to Documents
    with open(ROUTE_DATA_PATH, "r") as f:
        route_data = json.load(f)

    documents = [
        Document(
            text=f"{r['title']}. {r['description']} Tags: {', '.join(r.get('tags', []))}",
            metadata={
                "url": r["url"],
                "title": r["title"],
                "description": r["description"],
                "tags": r.get("tags", []),
                "service": r.get("service"),
                "hasAccess": r.get("hasAccess", [])
            }
        )
        for r in route_data
    ]

    embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    # Create FAISS index
    dimension = 384  # dimension for all-MiniLM-L6-v2 embeddings
    faiss_index = faiss.IndexFlatL2(dimension)
    
    # Create FAISS vector store with the index
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # Build index with better parameters
    index = VectorStoreIndex.from_documents(
        documents, 
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True  # Show progress during indexing
    )
    
    # Save the index
    index.storage_context.persist(persist_dir=VECTOR_STORE_PATH)
    
    # Save the hash of routes.json
    current_hash = calculate_file_hash(ROUTE_DATA_PATH)
    save_vector_store_hash(current_hash)
    
    return index

def load_or_build_index():
    """Load existing index or build new one if needed"""
    # Check if vector store exists and has files
    vector_store_exists = os.path.exists(VECTOR_STORE_PATH) and os.listdir(VECTOR_STORE_PATH)
    
    if not vector_store_exists:
        print("No existing vector store found. Building new index...")
        return build_vector_index()
    
    try:
        # Try to load existing index
        vector_store = FaissVectorStore.from_persist_dir(VECTOR_STORE_PATH)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        
        # Check if routes.json has changed
        current_hash = calculate_file_hash(ROUTE_DATA_PATH)
        saved_hash = load_vector_store_hash()
        
        if current_hash != saved_hash:
            print("routes.json has changed. Rebuilding index...")
            return build_vector_index()
            
        return index
    except Exception as e:
        print(f"Error loading vector store: {e}. Rebuilding index...")
        return build_vector_index()

# Initialize the index with better retrieval parameters
index = load_or_build_index()
# Set top_k to 3 to get more focused matches
retriever = index.as_retriever(similarity_top_k=3)

@app.post("/rebuild-index")
def rebuild_index():
    """Endpoint to manually rebuild the vector index"""
    global index, retriever
    index = build_vector_index()
    retriever = index.as_retriever(similarity_top_k=3)
    return {"status": "success", "message": "Vector index rebuilt successfully"}

@app.get("/ask")
async def ask_question(query: str):
    try:
        logger.info(f"Received query: {query}")
        
        # Step 1: Retrieve relevant content using LlamaIndex
        nodes = retriever.retrieve(query)
        logger.info(f"Found {len(nodes)} relevant nodes")
        
        if not nodes:
            return {"llm_response": {"suggestions": [], "explanation": "No relevant pages were found for your request."}}
        
        # Step 2: Build context string for Gemini
        context = ""
        for node in nodes:
            meta = node.metadata
            # Include the complete route object
            route_obj = {
                "title": meta.get('title'),
                "url": meta.get('url'),
                "description": meta.get('description', ''),
                "service": meta.get('service'),
                "hasAccess": meta.get('hasAccess', []),
                "tags": meta.get('tags', [])
            }
            context += f"{json.dumps(route_obj, indent=2)}\n\n"
        
        logger.info("Context being sent to Gemini:")
        logger.info(context)
        
        # Create a prompt that includes the routes and instructions for parameter extraction
        prompt = f"""
        Based on the following query: "{query}"
        
        Here are the relevant routes found:
        {context}
        
        Please:
        1. Find the most relevant route(s)
        2. For each route, use the exact service name from the route's service field
        3. Extract the parameter from the query if needed
        4. Return the suggestions in the specified format
        5. Provide a short, friendly explanation that feels helpful and natural — imagine you're assisting the user, not giving a technical report.
        
        Return the response in this exact JSON format:
        {{
            "suggestions": [
                {{
                    "title": "Route title",
                    "path": "Route URL with :id placeholder (e.g. /app/contacts/:id/summary)",
                    "description": "Route description",
                    "service": "Exact service name from the route's service field",
                    "param": "Extracted parameter (name or email)"
                }}
            ],
            "explanation": "Friendly explanation of why these pages are a good match for the user's request."
        }}
        """

        logger.info("Sending prompt to Gemini API:")
        logger.info(prompt)

        # Call Gemini API
        res = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "topK": 1,
                    "topP": 1,
                    "maxOutputTokens": 1024,
                }
            }
        )
        
        logger.info(f"Gemini API response status: {res.status_code}")
        if res.status_code != 200:
            logger.error(f"Gemini API error: {res.text}")
            raise HTTPException(status_code=500, detail=f"Gemini API error: {res.text}")
            
        response_json = res.json()
        logger.info("Raw Gemini API response:")
        logger.info(json.dumps(response_json, indent=2))
        
        # Extract the response text from Gemini's format
        candidates = response_json.get("candidates", [])
        if not candidates:
            logger.error("No candidates in Gemini response")
            raise HTTPException(status_code=500, detail="No candidates in Gemini response")
            
        content = candidates[0].get("content", {})
        if not content:
            logger.error("No content in first candidate")
            raise HTTPException(status_code=500, detail="No content in first candidate")
            
        parts = content.get("parts", [])
        if not parts:
            logger.error("No parts in content")
            raise HTTPException(status_code=500, detail="No parts in content")
            
        response_text = parts[0].get("text", "")
        if not response_text:
            logger.error("No text in first part")
            raise HTTPException(status_code=500, detail="No text in first part")
            
        logger.info(f"Extracted response text: {response_text}")
        
        # Clean up the response text if needed
        response_text = response_text.strip()
        # Remove markdown code block if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # Remove ```json
        elif response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove ```
        response_text = response_text.strip()
        
        # Debug log the cleaned response
        logger.info(f"Cleaned response text: {response_text}")
        
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Response text that failed to parse: {response_text}")
            raise HTTPException(status_code=500, detail=f"Failed to parse Gemini response: {str(e)}")
        
        # Process each suggestion
        processed_suggestions = []
        for suggestion in response_data.get("suggestions", []):
            if suggestion.get("service") and suggestion.get("param"):
                logger.info(f"Processing suggestion with service: {suggestion['service']}, param: {suggestion['param']}")
                # Get the ID using the appropriate service
                if suggestion["service"] == "get_organisation_id_by_name":
                    id = get_organisation_id_by_name(suggestion["param"])
                elif suggestion["service"] == "get_adviser_id_by_name":
                    id = get_adviser_id_by_name(suggestion["param"])
                elif suggestion["service"] == "get_adviser_id_by_email":
                    id = get_adviser_id_by_email(suggestion["param"])
                elif suggestion["service"] == "get_client_id_by_name":
                    id = get_client_id_by_name(suggestion["param"])
                elif suggestion["service"] == "get_client_id_by_email":
                    id = get_client_id_by_email(suggestion["param"])
                else:
                    id = None
                
                logger.info(f"Retrieved ID: {id}")
                
                # Replace :id in the path with the actual ID
                if id is not None:
                    suggestion["path"] = suggestion["path"].replace(":id", str(id))
            
            processed_suggestions.append(suggestion)
        
        response_data["suggestions"] = processed_suggestions
        return response_data

    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

class RouteSuggestion(BaseModel):
    title: str
    path: str
    description: str

class Suggestion(BaseModel):
    title: str
    path: str
    description: str
    service: Optional[str] = None
    param: Optional[str] = None

class LLMResponse(BaseModel):
    suggestions: List[Suggestion]
    explanation: Optional[str] = None
