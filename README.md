# LangChain + Azure AI Foundry Samples

A collection of sample applications built with the latest **LangChain** and **Microsoft Azure AI Foundry** platform.

## Key Technologies

| Technology | Version / Detail |
|---|---|
| **Microsoft Azure AI Foundry** | New unified AI platform (successor to Azure OpenAI Studio) |
| **OpenAI Responses API** | Latest API format (replaces Chat Completions API) — structured content blocks, built-in tool use |
| **LangChain** | v1.2+ with `langchain-azure-ai` v1.1+ (`AzureAIOpenAIApiChatModel`) |
| **Streaming** | Enabled on all models — real-time token-by-token output with usage tracking |
| **Gradio** | v6.9+ for the web GUI |
| **Authentication** | `DefaultAzureCredential` (supports `az login`, managed identity, service principal) |

## Samples

| Sample | Description |
|---|---|
| [langchain-chat-app-version1](langchain-chat-app-version1/) | Streaming chat with Responses API + AI follow-up suggestions |
| [langchain-rag-app-version1](langchain-rag-app-version1/) | RAG app — upload 20+ file types & images, FAISS vectorization, vision, token tracking |

## Common Prerequisites

- **Python 3.12+**
- **Azure AI Foundry** project ([ai.azure.com](https://ai.azure.com)) with a deployed chat model (e.g., `gpt-4.1`, `gpt-4o`, `gpt-5.2`)
- **Azure CLI** — run `az login` before starting any sample

## Quick Start (All Samples)

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/langchain-azure-samples.git
cd langchain-azure-samples
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 3. Set up environment variables

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your Azure AI Foundry credentials:

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<your-resource>.services.ai.azure.com/api/projects/<your-project>
AZURE_AI_API_KEY=<your-api-key>
MODEL_DEPLOYMENT_NAME=gpt-4.1
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/openai/v1
EMBEDDING_MODEL=text-embedding-ada-002
```

> **Where to find these:** [Azure AI Foundry](https://ai.azure.com) → Your project → Settings → Endpoints & Keys.

### 4. Azure login

```bash
az login
```

### 5. Run a sample

```bash
cd langchain-chat-app-version1   # or any sample folder
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:7860** in your browser.

## Environment Variables Reference

| Variable | Required | Used By | Description |
|---|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Yes | All | Azure AI Foundry project endpoint |
| `AZURE_AI_API_KEY` | Yes | All | API key for your Azure AI resource |
| `MODEL_DEPLOYMENT_NAME` | Yes | All | Deployed chat model name (e.g., `gpt-4.1`) |
| `AZURE_OPENAI_ENDPOINT` | Yes | RAG app | OpenAI-compatible endpoint (for embeddings) |
| `EMBEDDING_MODEL` | No | RAG app | Embedding model name (default: `text-embedding-ada-002`) |
| `AZURE_OPENAI_API_VERSION` | No | RAG app | API version (default: `2024-06-01`) |

## What's New — Azure AI Foundry & Responses API

These samples use Microsoft's latest AI platform and API:

- **Azure AI Foundry** replaces the old Azure OpenAI Studio. It provides a unified project-based endpoint for chat models, embeddings, vision, and more.
- **Responses API** is the new default (replaces the Chat Completions API). It returns content as structured blocks instead of plain strings, supports built-in tools, and enables native streaming with token usage metadata.
- **`langchain-azure-ai`** v1.1+ provides `AzureAIOpenAIApiChatModel` — the new LangChain integration class for Azure AI Foundry's Responses API.
- **Streaming** is enabled for all models with `stream_usage=True`, so every response includes real-time token counts.

## License

This project is for learning and demonstration purposes.
