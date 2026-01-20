# PDF Extractor API

A FastAPI service for extracting and cleaning text from PDF files. Ready for Railway deployment.

## Features

- **PDF to Markdown extraction** using PyMuPDF
- **Text cleaning** removes garbage (headers/footers, data dumps, encoding artifacts)
- **AI cleaning** with Gemini 2.0 Flash or Groq (Llama 3.3)
- **CORS enabled** for browser access

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/health` | GET | Health check |
| `/extract` | POST | Extract text from PDF |
| `/extract-and-clean` | POST | Extract + pattern-based cleaning |
| `/extract-with-ai` | POST | Extract + AI cleaning |
| `/clean` | POST | Clean existing text |

## Local Development

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env file and add your API keys (optional)
cp .env.example .env

# Run the server
python main.py
```

Server runs at `http://localhost:8000`

## Usage Examples

### Extract PDF (curl)

```bash
curl -X POST "http://localhost:8000/extract" \
  -F "file=@document.pdf"
```

### Extract + Clean

```bash
curl -X POST "http://localhost:8000/extract-and-clean" \
  -F "file=@document.pdf"
```

### Extract with AI

```bash
curl -X POST "http://localhost:8000/extract-with-ai" \
  -F "file=@document.pdf" \
  -F "model=gemini" \
  -F "prompt_preset=clean" \
  -F "api_key=YOUR_GEMINI_API_KEY"
```

### Clean existing text

```bash
curl -X POST "http://localhost:8000/clean" \
  -F "text=Your text here..."
```

## Deploy to Railway

1. Copy this folder to a new repository
2. Push to GitHub
3. Connect to Railway
4. Add environment variables (optional):
   - `GEMINI_API_KEY` - for server-side AI processing
   - `GROQ_API_KEY` - for server-side AI processing

Railway will automatically:
- Detect the Dockerfile
- Build and deploy
- Set the PORT environment variable
- Health check at `/health`

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PORT` | Server port (Railway sets this) | Auto |
| `GEMINI_API_KEY` | Gemini API key | Optional |
| `GROQ_API_KEY` | Groq API key | Optional |

Note: API keys can be passed per-request if not set as env vars.

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
