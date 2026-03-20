import os
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# Load .env from parent directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

credential = DefaultAzureCredential()

model = AzureAIOpenAIApiChatModel(
    project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=credential,
    model=os.environ["MODEL_DEPLOYMENT_NAME"],
    temperature=0.7,
    stream_usage=True,
)

SYSTEM_PROMPT = """You are a helpful AI assistant with RAG (Retrieval Augmented Generation) capabilities.

When context from uploaded documents is provided, use it to answer the user's question accurately.
Always cite which part of the document your answer is based on when possible.
If the context doesn't contain enough information to answer, say so honestly.
If an image is provided, analyze it thoroughly and respond based on what you see."""


def _get_text(content):
    """Extract text from content that may be a string or list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def stream_response(user_prompt, chat_history=None, context="", image_data=None):
    """Stream LLM response token by token.

    Args:
        user_prompt: The user's input text.
        chat_history: List of (user_msg, assistant_msg) tuples for context.
        context: Retrieved document context from RAG.
        image_data: List of (base64_str, mime_type, filename) for images.

    Yields:
        Text chunks as they arrive from the model.
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    if chat_history:
        for user_msg, assistant_msg in chat_history:
            messages.append(HumanMessage(content=user_msg))
            if assistant_msg:
                messages.append(AIMessage(content=assistant_msg))

    # Build the user message with optional context and images
    content_parts = []

    if context:
        content_parts.append({
            "type": "text",
            "text": f"**Relevant document context:**\n\n{context}\n\n**User question:** {user_prompt}",
        })
    else:
        content_parts.append({"type": "text", "text": user_prompt})

    if image_data:
        for b64, mime, filename in image_data:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            })

    # Use multimodal message if images present, otherwise plain text
    if image_data:
        messages.append(HumanMessage(content=content_parts))
    else:
        text = content_parts[0]["text"]
        messages.append(HumanMessage(content=text))

    usage = None
    for chunk in model.stream(messages):
        # Capture token usage from the last chunk that carries it
        meta = getattr(chunk, "usage_metadata", None)
        if meta:
            usage = meta
        if chunk.text:
            yield chunk.text

    # After streaming, yield a sentinel with usage info
    if usage:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total = input_tokens + output_tokens
        yield {"__usage__": {"input": input_tokens, "output": output_tokens, "total": total}}


def get_suggestions(chat_history):
    """Generate 3 follow-up prompt suggestions based on conversation history."""
    messages = [SystemMessage(content=(
        "Based on the conversation so far, suggest exactly 3 short follow-up questions "
        "the user might want to ask next. Return ONLY the 3 questions, one per line, "
        "numbered 1. 2. 3. No other text."
    ))]

    for user_msg, assistant_msg in chat_history:
        messages.append(HumanMessage(content=user_msg))
        if assistant_msg:
            messages.append(AIMessage(content=assistant_msg))

    response = model.invoke(messages)
    raw = response.content
    if isinstance(raw, list):
        raw = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in raw
        )
    lines = [line.strip() for line in raw.strip().split("\n") if line.strip()]
    suggestions = []
    for line in lines[:3]:
        cleaned = line.lstrip("0123456789.)- ").strip()
        if cleaned:
            suggestions.append(cleaned)
    return suggestions
