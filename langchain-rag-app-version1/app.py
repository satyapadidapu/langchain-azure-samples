import re
import gradio as gr
from llm_backend import stream_response, get_suggestions, _get_text
from rag_engine import process_files, retrieve_context, is_image

# Global state for the current session
vector_store = None
image_data_list = []
uploaded_file_names = []


def on_files_uploaded(files):
    """Auto-process files as soon as they are uploaded."""
    global vector_store, image_data_list, uploaded_file_names

    if not files:
        return gr.update(visible=False), ""

    file_paths = []
    for f in files:
        if isinstance(f, str):
            file_paths.append(f)
        elif hasattr(f, "name"):
            file_paths.append(f.name)
        else:
            file_paths.append(str(f))

    try:
        vector_store, image_data_list, uploaded_file_names = process_files(file_paths)
    except Exception as e:
        return gr.update(visible=True), f"❌ Error: {e}"

    doc_count = len([f for f in uploaded_file_names if not is_image(f)])
    img_count = len(image_data_list)

    parts = []
    if doc_count:
        parts.append(f"{doc_count} doc(s) vectorized")
    if img_count:
        parts.append(f"{img_count} image(s) loaded")

    status = "✅ " + ", ".join(parts) + f" — {', '.join(uploaded_file_names)}"
    return gr.update(visible=True), status


def clear_all():
    """Clear chat, files, and RAG state."""
    global vector_store, image_data_list, uploaded_file_names
    vector_store = None
    image_data_list = []
    uploaded_file_names = []
    return [], "", None, gr.update(visible=False), "", gr.update(visible=False), "", "", ""


def _build_paired_history(chat_history):
    """Build (user, assistant) tuples from chat history."""
    paired = []
    for i in range(0, len(chat_history) - 1, 2):
        u = chat_history[i]
        a = chat_history[i + 1]
        if u["role"] == "user" and a["role"] == "assistant":
            a_text = _get_text(a["content"])
            # Strip tooltip HTML so it doesn't pollute conversation context
            a_text = _strip_tooltip(a_text)
            paired.append((_get_text(u["content"]), a_text))
    return paired


def user_submit(message, chat_history):
    """Add user message to chat and clear input."""
    chat_history = chat_history + [{"role": "user", "content": message}]
    return "", chat_history


def _strip_tooltip(text):
    """Remove the token-usage tooltip from message text."""
    return re.sub(r'\s*<span title="[^"]*" style="[^"]*">.*?</span>\s*$', '', text)


def bot_respond(chat_history):
    """Stream bot response with RAG context."""
    user_message = _get_text(chat_history[-1]["content"])
    paired = _build_paired_history(chat_history[:-1])

    context = ""
    if vector_store:
        context = retrieve_context(vector_store, user_message)

    chat_history = chat_history + [{"role": "assistant", "content": ""}]
    partial = ""
    usage_info = None
    for token in stream_response(user_message, paired, context=context, image_data=image_data_list):
        if isinstance(token, dict) and "__usage__" in token:
            usage_info = token["__usage__"]
        else:
            partial += token
            chat_history[-1] = {"role": "assistant", "content": partial}
            yield chat_history

    # Append token usage tooltip after streaming completes
    if usage_info:
        tooltip_text = (f"Tokens — Input: {usage_info['input']} | "
                        f"Output: {usage_info['output']} | "
                        f"Total: {usage_info['total']}")
        badge = (f'\n\n<span title="{tooltip_text}" style="cursor:help; '
                 f'font-size:0.75em; color:#888; border-bottom:1px dotted #888;">'
                 f'🔢 {usage_info["total"]} tokens</span>')
        partial += badge
        chat_history[-1] = {"role": "assistant", "content": partial}
        yield chat_history


def update_suggestions(chat_history):
    """Generate follow-up suggestions after bot responds."""
    if not chat_history or len(chat_history) < 2:
        return gr.update(visible=False), "", "", ""

    paired = _build_paired_history(chat_history)
    if not paired:
        return gr.update(visible=False), "", "", ""

    suggestions = get_suggestions(paired)
    while len(suggestions) < 3:
        suggestions.append("")

    return gr.update(visible=True), suggestions[0], suggestions[1], suggestions[2]


def use_suggestion(suggestion):
    return suggestion


# ─── GUI ─────────────────────────────────────────────────────────────────────

with gr.Blocks(title="LangChain RAG Chat") as app:
    gr.Markdown("# 📄 LangChain RAG Chat with GPT")
    gr.Markdown(
        "Upload files and ask questions. Documents are vectorized for RAG retrieval. "
        "Images are analyzed with vision. Files are processed automatically on upload."
    )

    chatbot = gr.Chatbot(height=500)

    suggestion_row = gr.Row(visible=False)
    with suggestion_row:
        sug1 = gr.Button("", size="sm", variant="secondary")
        sug2 = gr.Button("", size="sm", variant="secondary")
        sug3 = gr.Button("", size="sm", variant="secondary")

    # File status bar (hidden until files are uploaded)
    file_status_row = gr.Row(visible=False)
    with file_status_row:
        file_status = gr.Markdown("")

    # Prompt area with inline file upload
    with gr.Row():
        file_upload = gr.File(
            label="📎 Attach files",
            file_count="multiple",
            file_types=[
                ".pdf", ".docx", ".doc", ".txt", ".csv",
                ".xlsx", ".xls", ".pptx", ".html", ".htm",
                ".md", ".json", ".py", ".js", ".xml", ".yaml", ".yml", ".log",
                ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
            ],
            scale=1,
        )
        msg = gr.Textbox(
            placeholder="Ask about your files, or ask anything...",
            label="Your Prompt",
            lines=2,
            scale=3,
        )

    with gr.Row():
        submit_btn = gr.Button("Send", variant="primary")
        clear_btn = gr.Button("🗑️ Clear Chat & Files")

    # Auto-process files on upload (no button needed)
    file_upload.change(on_files_uploaded, file_upload, [file_status_row, file_status])

    # Clear everything: chat, textbox, files, status, suggestions
    clear_btn.click(
        clear_all,
        None,
        [chatbot, msg, file_upload, file_status_row, file_status,
         suggestion_row, sug1, sug2, sug3],
    )

    # Chat events
    submit_btn.click(user_submit, [msg, chatbot], [msg, chatbot]).then(
        bot_respond, chatbot, chatbot
    ).then(
        update_suggestions, chatbot, [suggestion_row, sug1, sug2, sug3]
    )
    msg.submit(user_submit, [msg, chatbot], [msg, chatbot]).then(
        bot_respond, chatbot, chatbot
    ).then(
        update_suggestions, chatbot, [suggestion_row, sug1, sug2, sug3]
    )

    # Suggestion buttons
    for btn in [sug1, sug2, sug3]:
        btn.click(use_suggestion, btn, msg).then(
            user_submit, [msg, chatbot], [msg, chatbot]
        ).then(
            bot_respond, chatbot, chatbot
        ).then(
            update_suggestions, chatbot, [suggestion_row, sug1, sug2, sug3]
        )

if __name__ == "__main__":
    app.launch()
