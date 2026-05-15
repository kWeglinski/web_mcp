FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for chromadb and sentence-transformers
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create a directory for ChromaDB persistence and ensure it exists
RUN mkdir -p /app/chroma_db

# Set environment variables to defaults if not provided
ENV MEM0_LLM_MODEL=llama3:8b \
    MEM0_BASE_URL=http://host.docker.internal:1234/v1 \
    MEM0_EMBED_MODEL=BAAI/bge-small-en-v1.5 \
    MEM0_API_KEY=local-secret \
    MEM0_CHROMA_PATH=/app/chroma_db

# Command to run the server
CMD ["python", "server.py"]
