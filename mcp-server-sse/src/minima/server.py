import logging
import json
import asyncio
from typing import Annotated, AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from mcp.server import Server
from requestor import request_data
from pydantic import BaseModel, Field
from mcp.shared.exceptions import McpError
from mcp.server import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    JSONRPCMessage,
)

logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# Create FastAPI app
app = FastAPI(title="Minima MCP Server with SSE", version="0.0.1")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create MCP Server
mcp_server = Server("minima-sse")

class Query(BaseModel):
    text: Annotated[
        str, 
        Field(description="context to find")
    ]

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="minima-query",
            description="Find a context in local files (PDF, CSV, DOCX, MD, TXT)",
            inputSchema=Query.model_json_schema(),
        )
    ]
    
@mcp_server.list_prompts()
async def list_prompts() -> list[Prompt]:
    logging.info("List of prompts")
    return [
        Prompt(
            name="minima-query",
            description="Find a context in a local files",
            arguments=[
                PromptArgument(
                    name="context", description="Context to search", required=True
                )
            ]
        )            
    ]
    
@mcp_server.call_tool()
async def call_tool(name, arguments: dict) -> list[TextContent]:
    if name != "minima-query":
        logging.error(f"Unknown tool: {name}")
        raise ValueError(f"Unknown tool: {name}")

    logging.info("Calling tools")
    try:
        args = Query(**arguments)
    except ValueError as e:
        logging.error(str(e))
        raise McpError(INVALID_PARAMS, str(e))
        
    context = args.text
    logging.info(f"Context: {context}")
    if not context:
        logging.error("Context is required")
        raise McpError(INVALID_PARAMS, "Context is required")

    output = await request_data(context)
    if "error" in output:
        logging.error(output["error"])
        raise McpError(INTERNAL_ERROR, output["error"])
    
    logging.info(f"Get prompt: {output}")    
    result_data = output['result']
    if 'error' in result_data:
        raise McpError(INTERNAL_ERROR, result_data['error'])
    
    output_text = result_data['output']
    result = []
    result.append(TextContent(type="text", text=output_text))
    return result
    
@mcp_server.get_prompt()
async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
    if not arguments or "context" not in arguments:
        logging.error("Context is required")
        raise McpError(INVALID_PARAMS, "Context is required")
        
    context = arguments["context"]

    output = await request_data(context)
    if "error" in output:
        error = output["error"]
        logging.error(error)
        return GetPromptResult(
            description=f"Failed to find a {context}",
            messages=[
                PromptMessage(
                    role="user", 
                    content=TextContent(type="text", text=error),
                )
            ]
        )

    logging.info(f"Get prompt: {output}")    
    result_data = output['result']
    if 'error' in result_data:
        return GetPromptResult(
            description=f"Failed to find a {context}",
            messages=[
                PromptMessage(
                    role="user", 
                    content=TextContent(type="text", text=result_data['error']),
                )
            ]
        )
    
    output_text = result_data['output']
    return GetPromptResult(
        description=f"Found content for this {context}",
        messages=[
            PromptMessage(
                role="user", 
                content=TextContent(type="text", text=output_text)
            )
        ]
    )

class SSEMCPTransport:
    """SSE-based transport for MCP server"""
    
    def __init__(self):
        self.request_queue = asyncio.Queue()
        self.response_queue = asyncio.Queue()
        
    async def read_message(self) -> JSONRPCMessage:
        """Read a message from the request queue"""
        message_data = await self.request_queue.get()
        return JSONRPCMessage.model_validate(message_data)
    
    async def write_message(self, message: JSONRPCMessage) -> None:
        """Write a message to the response queue"""
        await self.response_queue.put(message.model_dump())
    
    async def add_request(self, request_data: dict) -> None:
        """Add a request to the queue"""
        await self.request_queue.put(request_data)
    
    async def get_response(self) -> dict:
        """Get a response from the queue"""
        return await self.response_queue.get()

# Global transport instance
transport = SSEMCPTransport()

@app.get("/")
async def root():
    return {"message": "Minima MCP Server with SSE", "version": "0.0.1"}

@app.post("/mcp/request")
async def handle_mcp_request(request_data: dict):
    """Handle incoming MCP requests"""
    try:
        logging.info(f"Received MCP request: {request_data}")
        await transport.add_request(request_data)
        
        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(transport.get_response(), timeout=30.0)
            logging.info(f"Sending MCP response: {response}")
            return response
        except asyncio.TimeoutError:
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": "Internal error: request timeout"
                }
            }
    except Exception as e:
        logging.error(f"Error handling request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

@app.get("/mcp/sse")
async def mcp_sse_endpoint(request: Request):
    """SSE endpoint for MCP communication"""
    
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Initialize the MCP server
            await mcp_server.run(
                transport,
                transport,
                InitializationOptions(
                    server_name="minima-sse",
                    server_version="0.0.1",
                    capabilities=mcp_server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
        except Exception as e:
            logging.error(f"MCP server error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return EventSourceResponse(event_generator())

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "server": "minima-sse"}

@app.post("/query")
async def direct_query(query: Query):
    """Direct query endpoint bypassing MCP transport"""
    try:
        logging.info(f"Direct query: {query.text}")
        output = await request_data(query.text)
        
        if "error" in output:
            return {"error": output["error"]}
        
        result_data = output['result']
        if 'error' in result_data:
            return {"error": result_data['error']}
        
        result = result_data['output']
        return {"result": result}
    except Exception as e:
        logging.error(f"Error in direct query: {e}")
        return {"error": str(e)}

@app.get("/query/sse/{query_text}")
async def query_sse(query_text: str, request: Request):
    """SSE endpoint for streaming query results"""
    
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Send initial message
            yield json.dumps({'status': 'processing', 'query': query_text})
            
            # Process the query
            output = await request_data(query_text)
            
            if "error" in output:
                yield json.dumps({'error': output['error']})
            else:
                result_data = output['result']
                if 'error' in result_data:
                    yield json.dumps({'error': result_data['error']})
                else:
                    result = result_data['output']
                    yield json.dumps({'result': result, 'status': 'completed'})
                
        except Exception as e:
            logging.error(f"SSE query error: {e}")
            yield json.dumps({'error': str(e)})
    
    return EventSourceResponse(event_generator())

# Background task to process MCP messages
async def process_mcp_messages():
    """Background task to process MCP server messages"""
    try:
        await mcp_server.run(
            transport,
            transport,
            InitializationOptions(
                server_name="minima-sse",
                server_version="0.0.1",
                capabilities=mcp_server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
    except Exception as e:
        logging.error(f"Error in MCP message processing: {e}")

@app.on_event("startup")
async def startup_event():
    """Start background tasks on app startup"""
    logging.info("Starting Minima MCP SSE Server...")

def main():
    """Main entry point for the SSE server"""
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )

if __name__ == "__main__":
    main()