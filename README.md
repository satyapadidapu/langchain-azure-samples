# LangChain + Azure AI Foundry Samples

A collection of sample applications demonstrating **LangChain** with **Azure AI Foundry** (GPT models, embeddings, RAG, vision).

## Samples

| Sample | Description |
|---|---|
| [langchain-chat-app-version1](langchain-chat-app-version1/) | Streaming chat app with follow-up suggestions |
| [langchain-rag-app-version1](langchain-rag-app-version1/) | RAG app — upload files (PDF, DOCX, Excel, images, code) and ask questions |

## Common Prerequisites

- **Python 3.12+**
- **Azure AI Foundry** project with a deployed chat model (e.g., `gpt-4.1`, `gpt-4o`)
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

## License

This project is for learning and demonstration purposes.
