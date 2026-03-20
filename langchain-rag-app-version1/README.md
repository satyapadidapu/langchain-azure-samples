# LangChain RAG App (Version 1)

RAG chat app powered by **Azure AI Foundry + LangChain**. Upload any file — PDF, DOCX, Excel, images, code — and ask questions. Documents are vectorized for retrieval, images are analyzed with vision.

> **First time?** Complete the [common setup](../README.md#quick-start-all-samples) in the root README before running this sample.

## Features

- **RAG**: Upload documents → auto-vectorized → relevant context retrieved per question
- **20+ file types**: PDF, DOCX, TXT, CSV, XLSX, PPTX, HTML, Markdown, JSON, Python, JS, XML, YAML, logs
- **Image analysis**: PNG, JPG, GIF, WebP, BMP — analyzed using GPT vision
- **Streaming responses** with token usage tracking (hover the 🔢 badge)
- **AI-generated follow-up suggestions** after each response
- **Auto-process**: Files are processed the moment you upload — no extra button needed

## Quick Start

```bash
cd langchain-rag-app-version1
pip install -r requirements.txt
python app.py
# Open http://127.0.0.1:7860
```

## Environment Variables

This sample uses variables from the `.env` file in the repo root:

| Variable | Required | Description |
|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Yes | Azure AI Foundry project endpoint |
| `AZURE_AI_API_KEY` | Yes | API key for your Azure AI resource |
| `MODEL_DEPLOYMENT_NAME` | Yes | Deployed chat model (e.g., `gpt-4.1`) |
| `AZURE_OPENAI_ENDPOINT` | Yes | OpenAI-compatible endpoint (for embeddings) |
| `EMBEDDING_MODEL` | No | Embedding model name (default: `text-embedding-ada-002`) |

## How It Works

1. **Attach files** using the 📎 upload next to the prompt — auto-processed on upload
2. **Ask questions** about your documents
3. **Click suggestions** for follow-up questions
4. **Upload images** to analyze them alongside your question
5. **Clear Chat & Files** to reset everything

## Architecture

```
User uploads files
       │
       ├── Documents → Chunked → Embedded → FAISS Vector Store
       └── Images → Base64 encoded ─┐
                                     │
User asks a question ────────────────┤
       │                             │
       ├── Query → Similarity search → Top-K relevant chunks
       └── Prompt + Context + Images → GPT → Streaming response
```

## Supported File Types

| Category | Extensions |
|---|---|
| Documents | `.pdf`, `.docx`, `.doc`, `.txt`, `.md` |
| Data | `.csv`, `.xlsx`, `.xls`, `.json`, `.xml`, `.yaml`, `.yml` |
| Presentations | `.pptx`, `.html`, `.htm` |
| Code | `.py`, `.js`, `.log` |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp` |

## File Size Limits

| File Type | Recommended Max | Notes |
|---|---|---|
| Text documents (PDF, DOCX, TXT, CSV, MD) | ~50–100 MB | Larger files take longer to embed |
| Spreadsheets (XLSX, XLS) | ~30 MB | Memory-intensive parsing |
| Presentations (PPTX) | ~30 MB | Memory-intensive parsing |
| Images (PNG, JPG, GIF, WebP, BMP) | ~20 MB | Base64-encoded for the vision API |
| Code / logs (PY, JS, JSON, XML, YAML) | ~50 MB | Treated as plain text |

Gradio upload limit: ~200 MB per file. Documents are chunked into 1,000-character pieces automatically, so the 8,191-token embedding limit is handled transparently.

## Project Structure

```
langchain-rag-app-version1/
├── app.py              # Gradio GUI — file upload + chat
├── llm_backend.py      # LLM setup, streaming, token tracking, suggestions
├── rag_engine.py       # Document loading, chunking, FAISS vectorization, retrieval
├── requirements.txt    # Python dependencies
└── README.md
```

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in an activated venv |
| `KeyError: 'AZURE_AI_PROJECT_ENDPOINT'` | Create `.env` in the repo root — see [setup](../README.md#quick-start-all-samples) |
| `Connection reset by peer` | Connect to VPN / corporate network |
| `DefaultAzureCredential` error | Run `az login` |
| Embedding errors | Verify `EMBEDDING_MODEL` matches a deployed model in your Azure AI project |
| Image not analyzed | Ensure the chat model supports vision (e.g., `gpt-4.1`, `gpt-4o`) |
