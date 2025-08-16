FROM python:3.11-slim

WORKDIR /usr/src/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies directly
RUN pip install --upgrade pip
RUN pip install fastapi>=0.116.0 uvicorn[standard]>=0.35.0 sse-starlette>=3.0.0 httpx>=0.28.0 mcp>=1.0.0 pydantic>=2.10.2

# Copy source code
COPY src/ ./src/

# Expose port
EXPOSE 8002

# Environment variables
ENV PYTHONPATH=/usr/src/app
ENV PYTHONUNBUFFERED=TRUE

# Command to run the server
CMD ["python", "src/minima/server.py"]