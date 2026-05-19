FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt ./backend-requirements.txt
COPY rag/requirements.txt ./rag-requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential zlib1g-dev \
    && pip install --no-cache-dir torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r backend-requirements.txt -r rag-requirements.txt \
    && apt-get purge -y --auto-remove build-essential zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
COPY backend/ ./backend/
COPY rag/ ./rag/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
