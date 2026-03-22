import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from anthropic import AnthropicFoundry

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ─── AnthropicFoundry client (per official docs) ─────────────────────────
# Uses AZURE_ANTHROPIC_ENDPOINT + AZURE_AI_API_KEY
# Endpoint format: https://{resource}.services.ai.azure.com/anthropic/v1
_base_url = os.environ["AZURE_ANTHROPIC_ENDPOINT"]
# base_url for the SDK should be the /anthropic/ root (without /v1)
if _base_url.endswith("/v1"):
    _base_url = _base_url[:-3]
elif _base_url.endswith("/v1/"):
    _base_url = _base_url[:-4]

client = AnthropicFoundry(
    api_key=os.environ["AZURE_AI_API_KEY"],
    base_url=_base_url,
)

MODEL_NAME = os.environ.get("CLAUDE_MODEL_NAME", "claude-opus-4-6")

SYSTEM_PROMPT = """You are a helpful AI assistant powered by Claude with RAG capabilities.

When context from uploaded documents is provided, use it to answer accurately.
Cite document sources when possible.
If the context doesn't contain enough information, say so honestly.
If an image is provided, analyze it thoroughly."""


def _get_text(content):
    """Extract text from content that may be a string or list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else
            (block.text if hasattr(block, "text") else str(block))
            for block in content
        )
    return str(content)


def stream_response(user_prompt, chat_history=None, context="", image_data=None):
    """Stream Claude response token by token using Anthropic SDK."""
    messages = []

    if chat_history:
        for user_msg, assistant_msg in chat_history:
            messages.append({"role": "user", "content": user_msg})
            if assistant_msg:
                messages.append({"role": "assistant", "content": assistant_msg})

    # Build user message content
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
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": b64},
            })

    messages.append({"role": "user", "content": content_parts})

    with client.messages.stream(
        model=MODEL_NAME,
        max_tokens=16384,
        system=SYSTEM_PROMPT,
        messages=messages,
        temperature=0.7,
    ) as stream:
        for text in stream.text_stream:
            yield text

    # Get final message for usage
    response = stream.get_final_message()
    if response and response.usage:
        yield {
            "__usage__": {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
                "total": response.usage.input_tokens + response.usage.output_tokens,
            }
        }


def get_suggestions(chat_history):
    """Generate 3 follow-up prompt suggestions."""
    # Build a summary of the conversation for the suggestion request
    conv_summary = ""
    for user_msg, assistant_msg in chat_history:
        conv_summary += f"User: {user_msg}\nAssistant: {assistant_msg}\n\n"

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=512,
        system=(
            "Based on the conversation so far, suggest exactly 3 short follow-up questions "
            "the user might want to ask next. Return ONLY the 3 questions, one per line, "
            "numbered 1. 2. 3. No other text."
        ),
        messages=[{
            "role": "user",
            "content": f"Here is the conversation so far:\n\n{conv_summary}\n\nSuggest 3 follow-up questions.",
        }],
        temperature=0.7,
    )

    raw = _get_text(response.content)
    lines = [line.strip() for line in raw.strip().split("\n") if line.strip()]
    suggestions = []
    for line in lines[:3]:
        cleaned = line.lstrip("0123456789.)- ").strip()
        if cleaned:
            suggestions.append(cleaned)
    return suggestions


# ─── Document Generation Prompts ─────────────────────────────────────────

DOC_PROMPTS = {
    "pdf": (
        "Generate structured content for a professional PDF document. Return ONLY valid JSON, no markdown fences.\n\n"
        "Format:\n"
        '{"title": "Document Title", "sections": ['
        '{"heading": "Section Heading", "body": "Paragraph content...", '
        '"bullets": ["Key point 1", "Key point 2"], '
        '"table": {"headers": ["Col1", "Col2"], "rows": [["val1", "val2"]]}}'
        "]}\n\n"
        'Fields "bullets" and "table" are optional per section. '
        'Create 4-8 sections with clear headings, detailed body paragraphs, '
        'bullet points for key takeaways, and tables for data. '
        'Write professional, comprehensive content.'
    ),
    "docx": (
        "Generate structured content for a Word document. Return ONLY valid JSON, no markdown fences.\n\n"
        "Format:\n"
        '{"title": "Document Title", "sections": ['
        '{"heading": "Section Heading", "level": 1, "content": ['
        '{"type": "paragraph", "text": "..."}, '
        '{"type": "bullets", "items": ["Bullet 1", "Bullet 2"]}, '
        '{"type": "numbered", "items": ["Step 1", "Step 2"]}, '
        '{"type": "table", "headers": ["Col1"], "rows": [["val1"]]}'
        "]}]}\n\n"
        "Create rich content with multiple content types per section."
    ),
    "xlsx": (
        "Generate structured content for an Excel spreadsheet. Return ONLY valid JSON, no markdown fences.\n\n"
        "Format:\n"
        '{"sheets": [{"name": "Sheet Name", "headers": ["Col1", "Col2"], '
        '"rows": [["value1", "value2"]]}]}\n\n'
        "Create well-organized data with clear headers. Use plain numbers for numeric values."
    ),
    "pptx": (
        "Generate structured content for a professional PowerPoint presentation. Return ONLY valid JSON, no markdown fences.\n\n"
        "Format:\n"
        '{"title": "Presentation Title", "subtitle": "A compelling subtitle", "slides": ['
        '{"title": "Slide Title", "layout": "title_and_content", '
        '"bullets": ["Point 1", "Point 2"], "notes": "Speaker notes..."}'
        "]}\n\n"
        'Layout options: "title_and_content" (default), "section" (section divider).\n'
        "Guidelines:\n"
        "- Create 8-12 slides for a complete presentation\n"
        "- Start with an agenda/overview slide after the title\n"
        "- Use 'section' layout to divide major topics\n"
        "- Keep bullets concise: max 4-5 per slide, each under 15 words\n"
        "- Write detailed speaker notes (2-3 sentences per slide)\n"
        "- End with a summary/key takeaways slide and a thank-you slide\n"
        "- Make titles action-oriented and specific (not generic like 'Overview')"
    ),
    "csv": (
        "Generate structured content for a CSV file. Return ONLY valid JSON, no markdown fences.\n\n"
        "Format:\n"
        '{"headers": ["Column 1", "Column 2"], "rows": [["val1", "val2"]]}\n\n'
        "Create well-organized tabular data."
    ),
    "json": (
        "Generate structured JSON data. Return ONLY valid JSON, no markdown fences.\n\n"
        "Format:\n"
        '{"data": <your structured JSON data>}\n\n'
        "Create well-organized, meaningful JSON data."
    ),
    "png": (
        "Generate structured content for a chart. Return ONLY valid JSON, no markdown fences.\n\n"
        "Format:\n"
        '{"chart_type": "bar", "title": "Chart Title", "xlabel": "X Label", "ylabel": "Y Label", '
        '"data": {"labels": ["A", "B", "C"], "datasets": [{"label": "Series 1", "values": [10, 20, 30]}]}}\n\n'
        'Chart types: "bar", "line", "pie", "scatter". For pie charts, use only one dataset.'
    ),
}


# Optimized token limits per format for faster generation
_FORMAT_MAX_TOKENS = {
    "pdf": 4096,
    "docx": 4096,
    "xlsx": 2048,
    "pptx": 4096,
    "csv": 2048,
    "json": 2048,
    "png": 1024,
}

# ─── Auto Format Detection ───────────────────────────────────────────────

_FORMAT_KEYWORDS = {
    "pptx": [
        "presentation", "ppt", "pptx", "powerpoint", "slides", "slide deck",
        "deck", "pitch deck", "keynote",
    ],
    "pdf": [
        "pdf", "report", "document", "whitepaper", "white paper", "memo",
        "letter", "proposal", "brochure", "summary report",
    ],
    "docx": [
        "docx", "doc", "word", "word document", "article", "essay", "manual",
        "guide", "handbook", "sop", "procedure",
    ],
    "xlsx": [
        "xlsx", "xls", "excel", "spreadsheet", "workbook", "financial model",
        "budget", "tracker", "ledger",
    ],
    "csv": [
        "csv", "comma separated", "tabular data", "data file", "dataset",
    ],
    "json": [
        "json", "api response", "structured data", "schema", "config file",
    ],
    "png": [
        "chart", "graph", "plot", "diagram", "bar chart", "pie chart",
        "line chart", "scatter plot", "visualization", "visualize",
    ],
}


def detect_format(prompt, file_names=None):
    """Detect the desired output format from the user's prompt.

    Uses keyword matching first, then falls back to LLM if ambiguous.
    Returns one of: pdf, docx, xlsx, pptx, csv, json, png.
    """
    prompt_lower = prompt.lower()

    # Check for explicit file extension mentions first
    for fmt in ["pptx", "docx", "xlsx", "csv", "json", "pdf", "png"]:
        if f".{fmt}" in prompt_lower or f" {fmt} " in f" {prompt_lower} ":
            return fmt

    # Score each format by keyword matches
    scores = {}
    for fmt, keywords in _FORMAT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in prompt_lower)
        # Boost for multi-word keyword matches
        score += sum(2 for kw in keywords if len(kw.split()) > 1 and kw in prompt_lower)
        if score > 0:
            scores[fmt] = score

    # If uploaded files hint at a format conversion, consider them
    if file_names:
        src_exts = {f.rsplit(".", 1)[-1].lower() for f in file_names if "." in f}
        # "convert" / "transform" / "turn into" patterns
        convert_words = ["convert", "transform", "turn into", "change to", "make a", "create a", "generate a"]
        is_convert = any(w in prompt_lower for w in convert_words)
        if is_convert:
            # If converting FROM pptx, they likely want a different format
            # Boost non-source formats
            for fmt in scores:
                if fmt not in src_exts:
                    scores[fmt] = scores.get(fmt, 0) + 1

    if scores:
        best = max(scores, key=scores.get)
        return best

    # No keyword matches — ask the LLM for a quick classification
    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=20,
            system=(
                "You classify user requests into document output formats. "
                "Reply with ONLY one word: pdf, docx, xlsx, pptx, csv, json, or png. "
                "Nothing else."
            ),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        detected = _get_text(response.content).strip().lower().rstrip(".")
        if detected in _FORMAT_MAX_TOKENS:
            return detected
    except Exception:
        pass

    # Ultimate fallback
    return "pdf"


def generate_document_content(prompt, format_type, context="", file_names=None):
    """Use LLM to generate structured content for document creation.

    Args:
        prompt: User description of what to generate.
        format_type: Output format (pdf, docx, xlsx, pptx, csv, json, png).
        context: RAG context from uploaded files.
        file_names: Names of uploaded files (for format/structure hints).

    Returns:
        Parsed JSON dict with structured content.
    """
    system_prompt = DOC_PROMPTS.get(format_type, DOC_PROMPTS["pdf"])

    user_message = prompt
    if context:
        file_label = ", ".join(file_names) if file_names else "uploaded documents"
        user_message = (
            f"REFERENCE CONTENT from uploaded files ({file_label}):\n"
            f"────────────────────────────────────\n"
            f"{context}\n"
            f"────────────────────────────────────\n\n"
            f"INSTRUCTIONS: Use the reference content above as source material. "
            f"Based on the user's request, you may need to:\n"
            f"- Create a new document using data/facts from the source files\n"
            f"- Convert the content into a different document format\n"
            f"- Improve, reorganize, or enhance the source content\n"
            f"- Extract and summarize key information\n\n"
            f"Preserve important data, numbers, names, and facts from the source. "
            f"Organize the output professionally.\n\n"
            f"User request: {prompt}"
        )

    max_tok = _FORMAT_MAX_TOKENS.get(format_type, 4096)

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=max_tok,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        temperature=0.7,
    )

    raw = _get_text(response.content)

    # Extract JSON from response (handle markdown fences if present)
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)```', raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)
    raw = raw.strip()

    return json.loads(raw)
