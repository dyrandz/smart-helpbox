# 📘 Smart Help Box — RAG + Local LLM (LM Studio)

This project demonstrates a smart help box assistant powered by:

- ✅ **LlamaIndex** for RAG (Retrieval-Augmented Generation)
- ✅ **FAISS** for fast vector similarity search
- ✅ **HuggingFace sentence transformers** for embedding queries
- ✅ **LM Studio** for running a local LLM (itlwas/openchat-3.5-1210-Q4_K_M-GGUF)
- ✅ **FastAPI** as a simple API layer to expose endpoints

---

## 🚀 How It Works (Flow)

```
+-----------------------+                         
|  User types question  |                        
+-----------------------+                        
            |                                  
            v                                  
+-------------------------------+               
| Embed query with HuggingFace | (sentence-transformers)
+-------------------------------+               
            |                                  
            v                                  
+-----------------------------+                 
|     Search FAISS index     | (llama-index + faiss-cpu)
+-----------------------------+                 
            |                                  
            v                                  
+-----------------------------+                 
| Build context from top-k    | (retriever returns metadata)
+-----------------------------+                 
            |                                  
            v                                  
+-----------------------------+                 
| Build optimized prompt      | (concise, formatted response)
+-----------------------------+                 
            |                                  
            v                                  
+-----------------------------+                 
| Call local LLM via LM Studio| (itlwas/openchat-3.5-1210-Q4_K_M-GGUF)
+-----------------------------+                 
            |                                  
            v                                  
+-----------------------------+                 
|   Return formatted response | (FastAPI endpoint)
+-----------------------------+
```

---

## 📂 Vector Store Structure

The application uses a persistent vector store to maintain embeddings between runs. The vector store is located in the `vector_store` directory and contains:

1. `default__vector_store.json`
   - Contains the FAISS index configuration
   - Stores vector embeddings
   - Maintains metadata about the stored vectors
   - Includes information about the embedding model used

2. `docstore.json`
   - Stores the original documents (routes data)
   - Contains document metadata (URLs, titles)
   - Maintains document IDs and their relationships

3. `index_store.json`
   - Contains index configuration
   - Stores information about vector organization
   - Maintains custom settings for the vector store

The vector store is automatically:
- Created on first run
- Loaded on subsequent runs
- Updated when routes.json changes
- Rebuilt via the `/rebuild-index` endpoint

---

## 🧪 Quick Start with Docker

### 1. ✅ Clone the Repo

### 2. ✅ Start LM Studio
1. Download and install [LM Studio](https://lmstudio.ai/)
2. Load the `itlwas/openchat-3.5-1210-Q4_K_M-GGUF` model
3. Start the local server on port 1234

### 3. ✅ Start the Application
```bash
docker-compose up --build
```

### 4. 🔁 Test the Endpoints

#### Ask Endpoint
```
GET http://localhost:8000/ask?query=add a client
```

Example Response:
```
{
    "llm_response": {
        "suggestions": [
            {
                "title": "Register Client",
                "path": "/clients/register",
                "description": "Allows users to add a new client to the CRM system."
            }
        ],
        "explanation": "Based on your request to add a client, I found the Register Client page which allows you to add new clients to the system."
    }
}
```

#### Rebuild Index Endpoint
```
POST http://localhost:8000/rebuild-index
```

Example Response:
```
{
    "status": "success",
    "message": "Vector index rebuilt successfully"
}
```

Use the rebuild endpoint when:
- You've modified routes.json
- You want to force a fresh vector store
- The vector store needs to be updated

---

## 📦 Dependencies (requirements.txt)
```txt
fastapi
uvicorn
requests
sentence-transformers
faiss-cpu
llama-index-core==0.12.32
llama-index-embeddings-huggingface==0.5.3
llama-index-vector-stores-faiss==0.3.0
```

---

## 🔍 Project Structure
```
smart-helpbox/
├── app/
│   ├── main.py           # FastAPI application and endpoints
│   ├── routes.json       # Route definitions and descriptions
│   └── vector_store/     # Persistent vector store directory
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🔄 Vector Store Management

The vector store is automatically managed by the application:

1. **First Run**
   - Creates new vector store
   - Generates embeddings from routes.json
   - Saves to disk

2. **Subsequent Runs**
   - Loads existing vector store
   - Checks if routes.json has changed
   - Rebuilds only if necessary

3. **Manual Rebuild**
   - Call `/rebuild-index` endpoint
   - Forces fresh vector store creation
   - Updates all embeddings

4. **File Changes**
   - Detects changes to routes.json
   - Automatically rebuilds on next startup
   - Maintains consistency with source data

---

## 🧠 Features
- 🔒 Concise, professional responses
- 📚 Smart route suggestions based on user queries
- ⚡ Fast response times with local LLM
- 🎯 Formatted output for easy integration
- 🔄 Docker support for consistent deployment

---

## 🚀 Restarting After Shutdown

### ✅ Quick Restart
If you need to restart the application, simply run:

```bash
docker-compose up -d
```

Make sure LM Studio is running on your machine with the `itlwas/openchat-3.5-1210-Q4_K_M-GGUF` model loaded and the server started on port 1234.

---

## 🧑‍💻 Contributors
This project was bootstrapped by [Dyrandz] — contributions welcome!

---

## 📄 License
MIT License — Open source, free to use and modify.


Llamaindex (RAG) Guide: https://docs.google.com/presentation/d/1A81x30FEVVAYQIKDVy5bzJERmsPmHDB8bpiHzHf2nXA/edit#slide=id.p
