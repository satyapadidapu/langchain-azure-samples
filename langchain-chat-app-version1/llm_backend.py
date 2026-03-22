import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

credential = DefaultAzureCredential()

model = AzureAIOpenAIApiChatModel(
    project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=credential,
    model=os.environ["MODEL_DEPLOYMENT_NAME"],
    temperature=0.7,
    stream_usage=True,
)

SYSTEM_PROMPT = "You are a helpful AI assistant. Answer clearly and concisely."


def stream_response(user_prompt, chat_history=None):
    """Stream LLM response token by token.

    Args:
        user_prompt: The user's input text.
        chat_history: List of (user_msg, assistant_msg) tuples for context.

    Yields:
        Text chunks as they arrive from the model.
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    if chat_history:
        for user_msg, assistant_msg in chat_history:
            messages.append(HumanMessage(content=user_msg))
            if assistant_msg:
                from langchain_core.messages import AIMessage
                messages.append(AIMessage(content=assistant_msg))

    messages.append(HumanMessage(content=user_prompt))

    usage = None
    for chunk in model.stream(messages):
        meta = getattr(chunk, "usage_metadata", None)
        if meta:
            usage = meta
        if chunk.text:
            yield chunk.text

    # Yield a sentinel with token usage info after streaming completes
    if usage:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total = input_tokens + output_tokens
        yield {"__usage__": {"input": input_tokens, "output": output_tokens, "total": total}}


def get_suggestions(chat_history):
    """Generate 3 follow-up prompt suggestions based on conversation history.

    Args:
        chat_history: List of (user_msg, assistant_msg) tuples.

    Returns:
        List of 3 suggested follow-up prompts.
    """
    messages = [SystemMessage(content=(
        "Based on the conversation so far, suggest exactly 3 short follow-up questions "
        "the user might want to ask next. Return ONLY the 3 questions, one per line, "
        "numbered 1. 2. 3. No other text."
    ))]

    for user_msg, assistant_msg in chat_history:
        messages.append(HumanMessage(content=user_msg))
        if assistant_msg:
            from langchain_core.messages import AIMessage
            messages.append(AIMessage(content=assistant_msg))

    response = model.invoke(messages)
    # content can be a string or a list of content blocks (Responses API)
    raw = response.content
    if isinstance(raw, list):
        raw = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in raw
        )
    lines = [line.strip() for line in raw.strip().split("\n") if line.strip()]
    # Strip numbering like "1. ", "2. ", "3. "
    suggestions = []
    for line in lines[:3]:
        cleaned = line.lstrip("0123456789.)- ").strip()
        if cleaned:
            suggestions.append(cleaned)
    return suggestions
