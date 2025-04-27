from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests, json, os
import hashlib
from pathlib import Path
import faiss

from llama_index.core import VectorStoreIndex, Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.faiss.base import FaissVectorStore
from llama_index.core.storage.storage_context import StorageContext

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
MODEL = "openchat-3.5-1210"
ROUTE_DATA_PATH = "routes.json"
VECTOR_STORE_PATH = "vector_store"
VECTOR_STORE_HASH_PATH = "vector_store_hash.txt"

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
            metadata={"url": r["url"], "title": r["title"], "description": r["description"], "tags": r.get("tags", [])}
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
# Set top_k to 5 to get more potential matches
retriever = index.as_retriever(similarity_top_k=5)

@app.post("/rebuild-index")
def rebuild_index():
    """Endpoint to manually rebuild the vector index"""
    global index, retriever
    index = build_vector_index()
    retriever = index.as_retriever(similarity_top_k=5)
    return {"status": "success", "message": "Vector index rebuilt successfully"}

@app.get("/ask")
def ask(query: str = Query(..., description="User input intent")):
    try:
        print(f"\n🔍 Searching for: {query}")
        
        # Step 1: Retrieve only relevant content
        nodes = retriever.retrieve(query)
        
        print(f"\n📚 Found {len(nodes)} matches")
        for node in nodes:
            print(f"Match score: {node.score if hasattr(node, 'score') else 'N/A'}")
            print(f"Content: {node.text}")
            print("---")

        if not nodes:
            return {"llm_response": {"suggestions": [], "explanation": "No relevant pages were found for your request."}}

        # Step 2: Build context string for LLM
        context = ""
        for node in nodes:
            meta = node.metadata
            tags = meta.get('tags', [])
            context += f"- Title: {meta.get('title')}\n  URL: {meta.get('url')}\n  Description: {meta.get('description', '')}\n"
            if tags:
                context += f"  Tags for matching: {', '.join(tags)}\n"
            context += "\n"

        # Step 3: Strict prompt for clean responses
        prompt = f"""You are a smart helpbox assistant. Your role is to provide quick, precise navigation suggestions.

User Query: "{query}"

Available Routes (ONLY use the Description field in your response, ignore Tags):
{context}

CRITICAL INSTRUCTIONS:
1. Your response must be a valid JSON object with the following structure:
   {{
     "suggestions": [
       {{
         "title": "Page Title",
         "url": "/path/to/page",
         "description": "Page description"
       }}
     ],
     "explanation": "A short, friendly, professional explanation of why you suggested these results."
   }}

2. The description in your response must ONLY be the text from the Description field
3. NEVER include Tags in your response
4. Use Tags for matching - if the query contains keywords that match ANY of the page's tags, consider it a relevant match
5. DO NOT include any explanations or thinking process outside the 'explanation' property
6. DO NOT use any markup or special formatting
7. If no matches are found, return: {{"suggestions": [], "explanation": "No relevant pages were found for your request."}}
8. IMPORTANT: Ensure your response is a complete, valid JSON object with matching opening and closing braces
9. CRITICAL: Only suggest pages that are DIRECTLY relevant to the user's query. Do not suggest unrelated pages.
10. If the query contains specific keywords, only suggest pages where those keywords appear in:
    - The page title
    - The page description
    - The page tags (even though you don't output them)

Example correct response (note the complete JSON structure with matching braces):
For query "view calendar":
{{
  "suggestions": [
    {{
      "title": "View Calendar",
      "url": "/calendar",
      "description": "Displays the calendar view with all scheduled events and appointments"
    }},
    {{
      "title": "Calendar Settings",
      "url": "/calendar/settings",
      "description": "Configure calendar display preferences and notification settings"
    }}
  ],
  "explanation": "These pages were suggested because they are directly related to viewing and managing calendar information, which matches your query exactly."
}}

For query "no matching pages":
{{
  "suggestions": [],
  "explanation": "No relevant pages were found for your request."
}}
"""

        # Step 4: Call LM Studio API
        res = requests.post(
            f"{LM_STUDIO_URL}/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You are a strict helpbox assistant. Your response must be a valid JSON object containing an array of suggestions, with no additional text or thinking process."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2
            }
        )
        response_json = res.json()

        # Debug output
        print("\n🧠 Final Prompt Sent to LLM:\n", prompt)
        print("\n📥 Raw LLM Response:\n", response_json)

        try:
            # Extract the response from LM Studio's format and parse it
            llm_response = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
            print("\n🔍 LLM Content Response:\n", llm_response)
            
            if not llm_response:
                return {"llm_response": {"suggestions": [], "explanation": "No response from the AI model."}}
            
            # Clean up the response string
            llm_response = llm_response.strip()
            
            # Ensure the JSON is complete by checking for matching braces
            brace_count = llm_response.count('{') - llm_response.count('}')
            if brace_count > 0:
                # Add missing closing braces
                llm_response += '}' * brace_count
            elif brace_count < 0:
                # Remove extra closing braces
                llm_response = llm_response[:brace_count]
            
            try:
                # First try to parse as is
                parsed_response = json.loads(llm_response)
            except json.JSONDecodeError:
                # If that fails, try to clean up the response more aggressively
                print("\n⚠️ Initial parse failed, attempting to clean response")
                try:
                    # Remove any whitespace and normalize newlines
                    llm_response = ' '.join(llm_response.split())
                    # Handle escaped characters
                    import codecs
                    unescaped = codecs.decode(llm_response, 'unicode_escape')
                    parsed_response = json.loads(unescaped)
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"\n❌ JSON Parse Error after cleaning: {str(e)}")
                    print(f"Raw response that failed to parse: {llm_response}")
                    return {"llm_response": {"suggestions": [], "explanation": "Failed to parse the AI model response."}}
            
            # Validate the response structure
            if "suggestions" not in parsed_response or "explanation" not in parsed_response:
                print("\n⚠️ Invalid response structure from LLM")
                return {"llm_response": {"suggestions": [], "explanation": "Invalid response format from the AI model."}}
                
            return {"llm_response": parsed_response}
            
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON Parse Error: {str(e)}")
            print(f"Raw response that failed to parse: {llm_response}")
            return {"llm_response": {"suggestions": [], "explanation": "Failed to parse the AI model response."}}
        except Exception as e:
            print(f"\n❌ Unexpected Error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
