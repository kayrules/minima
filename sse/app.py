import logging
import asyncio
import json
import time
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from typing import AsyncGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sse-server")

app = FastAPI(title="Minima SSE Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration - should match your existing Minima setup
INDEXER_URL = os.getenv("INDEXER_URL", "http://localhost:8001")

class QueryRequest(BaseModel):
    query: str
    stream: bool = True

async def format_sse_data(data: dict) -> str:
    """Format data as Server-Sent Events"""
    return f"data: {json.dumps(data)}\n\n"

async def query_indexer(query: str) -> dict:
    """Query the indexer service for relevant documents"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{INDEXER_URL}/query",
                json={"query": query},
                timeout=30.0
            )
            return response.json()
        except Exception as e:
            logger.error(f"Error querying indexer: {e}")
            return {"error": str(e)}

async def stream_query_results(query: str) -> AsyncGenerator[str, None]:
    """Stream query results as SSE"""
    try:
        # Send initial status
        yield await format_sse_data({
            "type": "status",
            "message": "Starting query processing...",
            "timestamp": time.time()
        })
        
        # Query the indexer
        yield await format_sse_data({
            "type": "status", 
            "message": "Searching documents...",
            "timestamp": time.time()
        })
        
        # Get results from indexer
        results = await query_indexer(query)
        
        if "error" in results:
            yield await format_sse_data({
                "type": "error",
                "message": results["error"],
                "timestamp": time.time()
            })
            return
        
        # Stream the results
        yield await format_sse_data({
            "type": "results",
            "data": results,
            "timestamp": time.time()
        })
        
        # Send completion status
        yield await format_sse_data({
            "type": "complete",
            "message": "Query processing completed",
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Error in stream_query_results: {e}")
        yield await format_sse_data({
            "type": "error",
            "message": str(e),
            "timestamp": time.time()
        })

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Minima SSE Server",
        "status": "running",
        "endpoints": {
            "query_stream": "/stream/query",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "indexer": INDEXER_URL
        }
    }

@app.post("/stream/query")
async def stream_query(request: QueryRequest):
    """Stream query results using Server-Sent Events"""
    logger.info(f"Received streaming query: {request.query}")
    
    return StreamingResponse(
        stream_query_results(request.query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx buffering disable
        }
    )

@app.get("/stream/query")
async def stream_query_get(query: str):
    """Stream query results using Server-Sent Events (GET method)"""
    logger.info(f"Received streaming query (GET): {query}")
    
    return StreamingResponse(
        stream_query_results(query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)