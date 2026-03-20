# LangChain Chat App (Version 1)

Streaming chat app powered by **Azure AI Foundry + LangChain** with AI-generated follow-up suggestions.

> **First time?** Complete the [common setup](../README.md#quick-start-all-samples) in the root README before running this sample.

## Features

- Real-time streaming responses (token by token)
- Multi-turn conversation with full history
- AI-generated follow-up suggestions after each response
- One-click suggestion to continue the conversation

## Quick Start

```bash
cd langchain-chat-app-version1
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

## How It Works

1. Type a message and press **Send** (or Enter)
2. The response streams in real time
3. After each response, 3 follow-up suggestions appear — click one to continue

## Project Structure

```
langchain-chat-app-version1/
├── app.py              # Gradio GUI — chat interface with streaming
├── llm_backend.py      # LLM setup, streaming, and suggestion generation
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
