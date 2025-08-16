import httpx
import logging
import os


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use environment variable for Docker networking, fallback to localhost
INDEXER_URL = os.getenv("INDEXER_URL", "http://localhost:8001")
REQUEST_DATA_URL = f"{INDEXER_URL}/query"
REQUEST_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

async def request_data(query):
    payload = {
        "query": query
    }
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Requesting data from indexer with query: {query}")
            response = await client.post(REQUEST_DATA_URL, 
                                         headers=REQUEST_HEADERS, 
                                         json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Received data: {data}")
            return data

        except Exception as e:
            logger.error(f"HTTP error: {e}")
            return { "error": str(e) }