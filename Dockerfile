FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PyMuPDF and Node.js
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend and build it
COPY frontend/package*.json frontend/
RUN cd frontend && npm install

COPY frontend/ frontend/
RUN cd frontend && npm run build

# Copy application code
COPY *.py .
COPY .env* ./

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
