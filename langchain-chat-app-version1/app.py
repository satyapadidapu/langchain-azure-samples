import gradio as gr
from llm_backend import stream_response, get_suggestions


def _get_text(content):
    """Extract text from Gradio's content format (can be a string or list of text objects)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content)
    return str(content)


def _build_paired_history(chat_history):
    """Build (user, assistant) tuples from chat history."""
    paired = []
    for i in range(0, len(chat_history) - 1, 2):
        u = chat_history[i]
        a = chat_history[i + 1]
        if u["role"] == "user" and a["role"] == "assistant":
            paired.append((_get_text(u["content"]), _get_text(a["content"])))
    return paired


def user_submit(message, chat_history):
    """Add user message to chat and clear input."""
    chat_history = chat_history + [{"role": "user", "content": message}]
    return "", chat_history


def bot_respond(chat_history):
    """Stream bot response."""
    user_message = _get_text(chat_history[-1]["content"])
    paired = _build_paired_history(chat_history[:-1])

    chat_history = chat_history + [{"role": "assistant", "content": ""}]
    partial = ""
    for token in stream_response(user_message, paired):
        partial += token
        chat_history[-1] = {"role": "assistant", "content": partial}
        yield chat_history


def update_suggestions(chat_history):
    """After bot responds, generate follow-up suggestions based on conversation."""
    if not chat_history or len(chat_history) < 2:
        return gr.update(visible=False), "", "", ""

    paired = _build_paired_history(chat_history)
    if not paired:
        return gr.update(visible=False), "", "", ""

    suggestions = get_suggestions(paired)
    while len(suggestions) < 3:
        suggestions.append("")

    return (
        gr.update(visible=True),
        suggestions[0],
        suggestions[1],
        suggestions[2],
    )


def use_suggestion(suggestion):
    """Fill the textbox with a suggested prompt."""
    return suggestion


with gr.Blocks(title="LangChain Chat") as app:
    gr.Markdown("# 💬 LangChain Chat with GPT-4.1")
    gr.Markdown("Ask anything — responses stream in real time.")

    chatbot = gr.Chatbot(height=450)

    suggestion_row = gr.Row(visible=False)
    with suggestion_row:
        sug1 = gr.Button("", size="sm", variant="secondary")
        sug2 = gr.Button("", size="sm", variant="secondary")
        sug3 = gr.Button("", size="sm", variant="secondary")

    msg = gr.Textbox(placeholder="Type your prompt here...", label="Your Prompt", lines=2)
    with gr.Row():
        submit_btn = gr.Button("Send", variant="primary")
        clear_btn = gr.ClearButton([chatbot, msg], value="Clear Chat")

    # Send flow: submit → bot responds → generate suggestions
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

    # Clicking a suggestion sends it as the next prompt
    for btn in [sug1, sug2, sug3]:
        btn.click(use_suggestion, btn, msg).then(
            user_submit, [msg, chatbot], [msg, chatbot]
        ).then(
            bot_respond, chatbot, chatbot
        ).then(
            update_suggestions, chatbot, [suggestion_row, sug1, sug2, sug3]
        )

    # Hide suggestions on clear
    clear_btn.click(lambda: gr.update(visible=False), None, suggestion_row)

if __name__ == "__main__":
    app.launch()
