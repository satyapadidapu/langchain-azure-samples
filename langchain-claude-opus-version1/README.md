# 🧠 LangChain Claude RAG & Document Generator

A **Gradio**-powered app that uses **Anthropic Claude Opus** on **Microsoft Foundry** via the official **Anthropic SDK** for:

- **RAG Chat** — Upload documents and chat with context-aware responses, streaming, token tracking, and AI-generated follow-up suggestions.
- **Document Generation** — Describe what you need in plain English → the AI auto-detects the format and generates professionally styled documents. Upload reference files for content or design reuse.

---

## Key Technologies

| Technology | Purpose |
|---|---|
| **Anthropic Claude Opus 4** | LLM (deployed on Microsoft Foundry as a serverless endpoint) |
| **Anthropic SDK** (`AnthropicFoundry`) | Official Python SDK for Claude on Azure/Foundry |
| **LangChain** | Document loading, chunking, and embeddings for RAG |
| **Microsoft Foundry** | Cloud AI platform hosting the Claude model |
| **FAISS** | Fast vector similarity search for RAG retrieval |
| **Gradio 6.9** | Interactive web UI with Chat + Document Generation tabs |
| **fpdf2 / python-docx / openpyxl / python-pptx / matplotlib** | Professional document and chart generation |

---

## Features

### 💬 RAG Chat Tab
- Upload **18+ file types** (PDF, DOCX, XLSX, PPTX, CSV, TXT, HTML, images, code, and more)
- Automatic vectorization via **FAISS** + Azure OpenAI embeddings
- Real-time **streaming** responses with token usage badges
- **Image vision** — upload images and ask Claude about them
- **AI suggestions** — 3 follow-up prompts generated after each response

### 📝 Generate Document Tab (Claude Cowork-style)
- **No format dropdown** — just describe what you need, the AI auto-detects the output format
- Generates 7 formats: **PDF, DOCX, XLSX, PPTX, CSV, JSON, PNG chart**
- **Upload reference files** — content is used as source material for generation
- **🎨 Design reuse** — upload a PPTX and its color scheme, fonts, and layout are automatically extracted and applied to the new document
- **Professional styling:**
  - **PDF**: Title page, page numbers, accent-colored headers, styled tables with alternating stripes, bullet points
  - **PPTX**: Custom dark/light slides, accent bars, section dividers, styled bullets with markers, slide numbers
- One-click download of generated files

### 🔍 Auto Format Detection
The AI determines the right output format from your prompt:
| Prompt | Detected |
|---|---|
| "Create a 10-slide presentation on AI trends" | PPTX |
| "Write a project proposal" | PDF |
| "Make an Excel budget tracker" | XLSX |
| "Generate a pie chart of market share" | PNG |

---

## Supported Document Formats

| Format | Description | Library |
|--------|-------------|---------|
| **PDF** | Professional title page, sections, bullets, styled tables, page numbers | fpdf2 |
| **DOCX** | Rich Word docs with paragraphs, bullets, numbered lists, tables | python-docx |
| **XLSX** | Styled spreadsheets with colored headers, borders, auto-width | openpyxl |
| **PPTX** | Widescreen presentations with custom themes, section dividers, speaker notes | python-pptx |
| **CSV** | Tabular data with headers | csv (stdlib) |
| **JSON** | Structured JSON data | json (stdlib) |
| **PNG** | Bar, line, pie, and scatter charts | matplotlib |

---

## Quick Start

```bash
# 1. Activate the virtual environment
source ../foundry-langchain-env/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables in ../.env
#    (see .env.example in the repo root)

# 4. Run the app
python app.py
```

Open `http://127.0.0.1:7860` in your browser.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `AZURE_AI_API_KEY` | Yes | API key for the Foundry resource |
| `AZURE_ANTHROPIC_ENDPOINT` | Yes | Anthropic endpoint (e.g., `https://<resource>.services.ai.azure.com/anthropic/v1`) |
| `CLAUDE_MODEL_NAME` | No | Claude deployment name (default: `claude-opus-4-6`) |
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint for embeddings |
| `EMBEDDING_MODEL` | No | Embeddings model name (default: `text-embedding-ada-002`) |

---

## Architecture

```
app.py                → Gradio GUI (Chat + Document Generation tabs)
llm_backend.py        → Claude client, streaming, suggestions, auto format detection, doc content prompts
rag_engine.py         → FAISS vectorization, document loading, context retrieval
doc_generator.py      → Professional file generators (PDF, DOCX, XLSX, PPTX, CSV, JSON, PNG)
design_extractor.py   → Extract visual design (colors, fonts, layout) from uploaded PPTX files
```

**Chat flow:** User prompt → RAG context retrieval → Claude streaming → token badge → suggestions

**Document flow:** User prompt → auto-detect format → RAG context → Claude generates structured JSON → doc_generator renders styled file → download

**Design reuse flow:** Upload PPTX → extract colors/fonts/layout → apply to new document generation
