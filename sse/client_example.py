#!/usr/bin/env python3
"""
Python SSE Client Example for Minima
Usage: python client_example.py "your query here"
"""

import requests
import json
import sys
import time

def stream_query(query: str, base_url: str = "http://localhost:8003"):
    """Stream query results using Server-Sent Events"""
    
    url = f"{base_url}/stream/query"
    params = {"query": query}
    
    print(f"🔍 Streaming query: {query}")
    print(f"📡 Connecting to: {url}")
    print("-" * 50)
    
    try:
        with requests.get(url, params=params, stream=True) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    
                    # SSE format: "data: {json_data}"
                    if line_str.startswith('data: '):
                        try:
                            data = json.loads(line_str[6:])  # Remove "data: " prefix
                            handle_sse_message(data)
                        except json.JSONDecodeError as e:
                            print(f"❌ Error parsing JSON: {e}")
                            print(f"Raw line: {line_str}")
                    
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
    except KeyboardInterrupt:
        print("\n🛑 Search interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def handle_sse_message(data: dict):
    """Handle different types of SSE messages"""
    
    message_type = data.get('type', 'unknown')
    timestamp = data.get('timestamp', time.time())
    
    # Format timestamp
    formatted_time = time.strftime('%H:%M:%S', time.localtime(timestamp))
    
    if message_type == 'status':
        print(f"📡 [{formatted_time}] {data.get('message', 'Status update')}")
        
    elif message_type == 'results':
        print(f"✅ [{formatted_time}] Results received:")
        results = data.get('data', {}).get('result', [])
        
        if isinstance(results, list):
            for i, result in enumerate(results, 1):
                print(f"\n📄 Result {i}:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(results, indent=2, ensure_ascii=False))
            
    elif message_type == 'error':
        print(f"❌ [{formatted_time}] Error: {data.get('message', 'Unknown error')}")
        
    elif message_type == 'complete':
        print(f"✅ [{formatted_time}] {data.get('message', 'Completed')}")
        print("-" * 50)
        
    else:
        print(f"🔔 [{formatted_time}] Unknown message type: {message_type}")
        print(json.dumps(data, indent=2, ensure_ascii=False))

def main():
    """Main function"""
    
    if len(sys.argv) != 2:
        print("Usage: python client_example.py \"your query here\"")
        print("Example: python client_example.py \"RHB investment\"")
        sys.exit(1)
    
    query = sys.argv[1]
    stream_query(query)

if __name__ == "__main__":
    main()