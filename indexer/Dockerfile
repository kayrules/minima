FROM python:3.11-slim-buster

WORKDIR /usr/src/app
RUN pip install --upgrade pip

ARG EMBEDDING_MODEL_ID

RUN pip install huggingface_hub

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT 8002
ENV CURRENT_HOST 0.0.0.0
ENV WORKERS 1

# Initialize models and NLTK data on startup (uses cache if available)
CMD ["sh", "-c", "python init_models.py && uvicorn app:app --loop asyncio --reload --workers ${WORKERS} --host $CURRENT_HOST --port $PORT --proxy-headers"]