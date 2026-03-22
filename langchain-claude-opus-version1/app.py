import re
import gradio as gr
from llm_backend import stream_response, get_suggestions, _get_text, generate_document_content, detect_format
from rag_engine import process_files, retrieve_context, is_image
from doc_generator import generate_document
from design_extractor import extract_design, describe_design

# Global state — Chat tab
vector_store = None
image_data_list = []
uploaded_file_names = []

# Global state — Generate tab
gen_vector_store = None
gen_file_names = []
gen_file_paths = []        # Keep original paths for design extraction
gen_extracted_design = None  # Design dict from uploaded PPTX/DOCX


def on_files_uploaded(files):
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
    global vector_store, image_data_list, uploaded_file_names
    global gen_vector_store, gen_file_names, gen_file_paths, gen_extracted_design
    vector_store = None
    image_data_list = []
    uploaded_file_names = []
    gen_vector_store = None
    gen_file_names = []
    gen_file_paths = []
    gen_extracted_design = None
    return (
        [], "", None,
        gr.update(visible=False), "",
        gr.update(visible=False), "", "", "",
        None, "",
    )


def _strip_tooltip(text):
    return re.sub(r'\s*---\s*🔢 \*\*\d+ tokens\*\*.*$', '', text, flags=re.DOTALL)


def _build_paired_history(chat_history):
    paired = []
    for i in range(0, len(chat_history) - 1, 2):
        u = chat_history[i]
        a = chat_history[i + 1]
        if u["role"] == "user" and a["role"] == "assistant":
            a_text = _strip_tooltip(_get_text(a["content"]))
            paired.append((_get_text(u["content"]), a_text))
    return paired


def user_submit(message, chat_history):
    chat_history = chat_history + [{"role": "user", "content": message}]
    return "", chat_history


def bot_respond(chat_history):
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

    if usage_info:
        badge = (f"\n\n---\n"
                 f"🔢 **{usage_info['total']} tokens** "
                 f"(Input: {usage_info['input']} | Output: {usage_info['output']})")
        partial += badge
        chat_history[-1] = {"role": "assistant", "content": partial}
        yield chat_history


def update_suggestions(chat_history):
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


def generate_doc(prompt):
    """Auto-detect format from prompt and generate the document."""
    if not prompt.strip():
        return None, "❌ Please describe what document to generate."

    try:
        # Prefer Generate-tab files; fall back to Chat-tab files
        vs = gen_vector_store or vector_store
        names = gen_file_names if gen_file_names else (uploaded_file_names if uploaded_file_names else None)

        # Auto-detect output format from the prompt
        format_type = detect_format(prompt, file_names=names)

        context = ""
        if vs:
            context = retrieve_context(vs, prompt, k=8)

        # Add design description to context if available
        design_desc = describe_design(gen_extracted_design) if gen_extracted_design else ""
        if design_desc:
            context = f"DESIGN TEMPLATE INFO:\n{design_desc}\n\n{context}" if context else design_desc

        content_json = generate_document_content(
            prompt, format_type, context=context, file_names=names
        )
        filepath = generate_document(
            content_json, format_type, design=gen_extracted_design
        )
        ref_note = ""
        if names:
            ref_note = f" (using {', '.join(names)} as reference)"
        if gen_extracted_design:
            ref_note += f" | Design from: {gen_extracted_design.get('source', 'uploaded file')}"
        return filepath, f"✅ Generated **{format_type.upper()}** file successfully!{ref_note}"
    except Exception as e:
        return None, f"❌ Error generating document: {e}"


def on_gen_files_uploaded(files):
    """Process files uploaded in the Generate Document tab."""
    global gen_vector_store, gen_file_names, gen_file_paths, gen_extracted_design
    if not files:
        gen_vector_store = None
        gen_file_names = []
        gen_file_paths = []
        gen_extracted_design = None
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
        gen_vector_store, _, gen_file_names = process_files(file_paths)
        gen_file_paths = file_paths

        # Extract design from the first PPTX/DOCX found
        gen_extracted_design = None
        for fp in file_paths:
            design = extract_design(fp)
            if design:
                gen_extracted_design = design
                break
    except Exception as e:
        return gr.update(visible=True), f"❌ Error: {e}"

    parts = [f"✅ {len(gen_file_names)} file(s) loaded — {', '.join(gen_file_names)}"]
    if gen_extracted_design:
        parts.append(f"🎨 Design extracted from **{gen_extracted_design['source']}**")
    return gr.update(visible=True), " | ".join(parts)


# ─── GUI ─────────────────────────────────────────────────────────────────

with gr.Blocks(title="Claude RAG & Document Generator") as app:
    gr.Markdown("# 🧠 Claude RAG Chat & Document Generator")
    gr.Markdown(
        "Powered by **Anthropic Claude Opus** on **Microsoft Foundry** + **LangChain**. "
        "Chat with your files, or generate documents (PDF, DOCX, XLSX, PPTX, CSV, JSON, charts)."
    )

    with gr.Tabs():
        # ─── Chat Tab ────────────────────────────────────────
        with gr.Tab("💬 Chat"):
            chatbot = gr.Chatbot(height=450)

            suggestion_row = gr.Row(visible=False)
            with suggestion_row:
                sug1 = gr.Button("", size="sm", variant="secondary")
                sug2 = gr.Button("", size="sm", variant="secondary")
                sug3 = gr.Button("", size="sm", variant="secondary")

            file_status_row = gr.Row(visible=False)
            with file_status_row:
                file_status = gr.Markdown("")

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

        # ─── Generate Tab ────────────────────────────────────
        with gr.Tab("📝 Generate Document"):
            gr.Markdown(
                "**Describe what you need** — the AI will figure out the right format and generate it.\n\n"
                "Upload reference files to use their content or design as a starting point.\n\n"
                "**Try:** *\"Create a 10-slide presentation on AI trends\"* · "
                "*\"Make an Excel budget tracker for Q2\"* · "
                "*\"Write a project proposal as a PDF\"* · "
                "*\"Generate a pie chart of market share\"*"
            )

            gen_file_status_row = gr.Row(visible=False)
            with gen_file_status_row:
                gen_file_status = gr.Markdown("")

            gen_file_upload = gr.File(
                label="📎 Upload reference files (optional — for content or design reuse)",
                file_count="multiple",
                file_types=[
                    ".pdf", ".docx", ".doc", ".txt", ".csv",
                    ".xlsx", ".xls", ".pptx", ".html", ".htm",
                    ".md", ".json", ".py", ".js", ".xml", ".yaml", ".yml", ".log",
                ],
            )

            gen_prompt = gr.Textbox(
                placeholder="Describe what to create... e.g., 'Create a presentation about Q1 results with 10 slides'",
                label="What to generate",
                lines=4,
            )

            gen_btn = gr.Button("🚀 Generate", variant="primary")

            gen_status = gr.Markdown("")
            gen_file = gr.File(label="📥 Download Generated File", interactive=False)

    # ─── Events ──────────────────────────────────────────────────

    file_upload.change(on_files_uploaded, file_upload, [file_status_row, file_status])
    gen_file_upload.change(on_gen_files_uploaded, gen_file_upload, [gen_file_status_row, gen_file_status])

    clear_btn.click(
        clear_all, None,
        [chatbot, msg, file_upload, file_status_row, file_status,
         suggestion_row, sug1, sug2, sug3,
         gen_file, gen_status],
    )

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

    for btn in [sug1, sug2, sug3]:
        btn.click(use_suggestion, btn, msg).then(
            user_submit, [msg, chatbot], [msg, chatbot]
        ).then(
            bot_respond, chatbot, chatbot
        ).then(
            update_suggestions, chatbot, [suggestion_row, sug1, sug2, sug3]
        )

    gen_btn.click(generate_doc, [gen_prompt], [gen_file, gen_status])

if __name__ == "__main__":
    app.launch()
