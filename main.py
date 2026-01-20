"""
PDF Extractor API
A FastAPI service for extracting and cleaning text from PDF files.

Endpoints:
- POST /extract - Extract text from PDF (returns raw markdown)
- POST /extract-and-clean - Extract + apply text cleaning
- POST /extract-with-ai - Extract + clean with AI (Gemini, Groq, or SambaNova)
- POST /clean - Clean existing text (no PDF, just text input)
- GET /health - Health check
"""

import os
from pathlib import Path
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from extractor import extract_pdf_to_markdown
from text_cleaner import clean_text

# Load environment variables
load_dotenv()

# Check if we have a built frontend
FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"
SERVE_FRONTEND = FRONTEND_DIR.exists()

app = FastAPI(
    title="PDF Extractor API",
    description="Extract and clean text from PDF files",
    version="1.0.0"
)

# CORS - allow all origins for flexibility (restrict in production if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response models
class ExtractionResponse(BaseModel):
    markdown: str
    page_count: int
    error: Optional[str] = None


class CleanResponse(BaseModel):
    cleaned_text: str
    original_length: int
    cleaned_length: int


class AICleanResponse(BaseModel):
    markdown: str
    page_count: int
    cleaned_text: str
    model_used: str
    error: Optional[str] = None


# Prompt presets (same as frontend)
PROMPT_PRESETS = {
    "clean": """Convert this raw PDF extraction into clean markdown optimized for LLM consumption.

Keep: All meaningful information a human would want to read - specs, instructions, explanations, tables, formulas, procedures, etc.

Remove: Noise and garbage - repetitive data dumps, raw coordinate/index sequences, meaningless character patterns, encoding artifacts, or any data that provides no informational value without its original visual context.

When you remove something, briefly note what was there (e.g., "[raw data table removed]").

Use your judgment. Preserve substance, discard noise. Output clean, well-structured markdown.""",
    "summarize": "Summarize this document in 5-10 bullet points, focusing on the key information.",
    "extract_specs": "Extract all technical specifications from this document and format them as a structured table in markdown.",
}


@app.get("/api")
async def api_info():
    """API info endpoint"""
    return {
        "name": "PDF Extractor API",
        "version": "1.0.0",
        "endpoints": {
            "POST /extract": "Extract text from PDF",
            "POST /extract-and-clean": "Extract + clean text",
            "POST /extract-with-ai": "Extract + AI cleaning (Gemini/Groq/SambaNova)",
            "POST /clean": "Clean existing text",
            "GET /health": "Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/extract", response_model=ExtractionResponse)
async def extract_pdf(file: UploadFile = File(...)):
    """
    Extract text from a PDF file.
    Returns raw markdown with basic cleanup.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    contents = await file.read()
    result = extract_pdf_to_markdown(pdf_bytes=contents)

    if result["error"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return ExtractionResponse(
        markdown=result["markdown"],
        page_count=result["page_count"],
        error=result["error"]
    )


@app.post("/extract-and-clean", response_model=ExtractionResponse)
async def extract_and_clean_pdf(file: UploadFile = File(...)):
    """
    Extract text from PDF and apply text cleaning.
    No AI involved - just pattern-based garbage removal.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    contents = await file.read()
    result = extract_pdf_to_markdown(pdf_bytes=contents)

    if result["error"]:
        raise HTTPException(status_code=500, detail=result["error"])

    # Apply text cleaning
    cleaned = clean_text(result["markdown"])

    return ExtractionResponse(
        markdown=cleaned,
        page_count=result["page_count"],
        error=None
    )


@app.post("/clean", response_model=CleanResponse)
async def clean_existing_text(text: str = Form(...)):
    """
    Clean existing text (no PDF extraction).
    Useful for cleaning AI responses or previously extracted text.
    """
    cleaned = clean_text(text)

    return CleanResponse(
        cleaned_text=cleaned,
        original_length=len(text),
        cleaned_length=len(cleaned)
    )


@app.post("/extract-with-ai", response_model=AICleanResponse)
async def extract_with_ai(
    file: UploadFile = File(...),
    model: str = Form(default="gemini"),
    prompt_preset: str = Form(default="clean"),
    custom_prompt: Optional[str] = Form(default=None),
    api_key: Optional[str] = Form(default=None)
):
    """
    Extract text from PDF and clean with AI.

    Args:
        file: PDF file to extract
        model: "gemini", "groq", or "sambanova"
        prompt_preset: "clean", "summarize", or "extract_specs"
        custom_prompt: Custom prompt (overrides preset)
        api_key: API key (or use env var GEMINI_API_KEY / GROQ_API_KEY / SAMBANOVA_API_KEY)
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Get API key from form or environment
    if model == "gemini":
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise HTTPException(status_code=400, detail="Gemini API key required")
    elif model == "groq":
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise HTTPException(status_code=400, detail="Groq API key required")
    elif model == "sambanova":
        key = api_key or os.getenv("SAMBANOVA_API_KEY")
        if not key:
            raise HTTPException(status_code=400, detail="SambaNova API key required")
    else:
        raise HTTPException(status_code=400, detail="Model must be 'gemini', 'groq', or 'sambanova'")

    # Extract PDF
    contents = await file.read()
    result = extract_pdf_to_markdown(pdf_bytes=contents)

    if result["error"]:
        raise HTTPException(status_code=500, detail=result["error"])

    # Get prompt
    prompt = custom_prompt if custom_prompt else PROMPT_PRESETS.get(prompt_preset, PROMPT_PRESETS["clean"])

    # Process with AI
    try:
        if model == "gemini":
            ai_result = await process_with_gemini(result["markdown"], prompt, key)
        elif model == "groq":
            ai_result = await process_with_groq(result["markdown"], prompt, key)
        else:
            ai_result = await process_with_sambanova(result["markdown"], prompt, key)

        # Post-process with text cleaner
        cleaned = clean_text(ai_result)

        return AICleanResponse(
            markdown=result["markdown"],
            page_count=result["page_count"],
            cleaned_text=cleaned,
            model_used=model,
            error=None
        )

    except Exception as e:
        return AICleanResponse(
            markdown=result["markdown"],
            page_count=result["page_count"],
            cleaned_text="",
            model_used=model,
            error=str(e)
        )


async def process_with_gemini(content: str, prompt: str, api_key: str) -> str:
    """Process content with Gemini 2.0 Flash"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{prompt}\n\n---\n\nDocument content:\n\n{content}"
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 65536
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload)

        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get("error", {}).get("message", f"Gemini API error: {response.status_code}")
            raise Exception(error_msg)

        data = response.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")


async def process_with_groq(content: str, prompt: str, api_key: str) -> str:
    """Process content with Groq (Llama 3.3)"""
    url = "https://api.groq.com/openai/v1/chat/completions"

    # Groq has smaller context, may need chunking for large docs
    # For now, process as single request (will fail if too large)
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that processes documents. Be thorough and precise."
            },
            {
                "role": "user",
                "content": f"{prompt}\n\n---\n\nDocument content:\n\n{content}"
            }
        ],
        "temperature": 0.3,
        "max_tokens": 8192
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get("error", {}).get("message", f"Groq API error: {response.status_code}")
            raise Exception(error_msg)

        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


async def process_with_sambanova(content: str, prompt: str, api_key: str) -> str:
    """Process content with SambaNova (Llama 3.3 70B)"""
    url = "https://api.sambanova.ai/v1/chat/completions"

    payload = {
        "model": "Meta-Llama-3.3-70B-Instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that processes documents. Be thorough and precise."
            },
            {
                "role": "user",
                "content": f"{prompt}\n\n---\n\nDocument content:\n\n{content}"
            }
        ],
        "temperature": 0.3,
        "max_tokens": 8192
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get("error", {}).get("message", f"SambaNova API error: {response.status_code}")
            raise Exception(error_msg)

        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


# Serve frontend static files if available
if SERVE_FRONTEND:
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/")
    async def serve_frontend():
        """Serve the frontend application"""
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{path:path}")
    async def serve_frontend_routes(path: str):
        """Catch-all for frontend routes"""
        file_path = FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
