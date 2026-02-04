"""
═══════════════════════════════════════════════════════════════
 অদম্য প্রেস — Book Translation Web App v2.0
 Features: Batch Review, Pause/Resume, Download after each batch
═══════════════════════════════════════════════════════════════
"""

import streamlit as st
import anthropic
import fitz  # PyMuPDF
import re
import os
import io
import time
import json
from datetime import datetime
from docx import Document as DocxDocument
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="অদম্য প্রেস — Book Translator",
    page_icon="📚",
    layout="wide",
)

# ═══════════════════════════════════════════════════════════════
# CUSTOM CSS
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<style>
    .stApp { background-color: #0a0f0d; color: #e0e0e0; }
    .main-title { text-align: center; color: #4CAF50; font-size: 2.2rem; margin-bottom: 0; }
    .sub-title { text-align: center; color: #888; font-size: 1rem; margin-top: 0; }
    .stat-box {
        background: #1a2520;
        border: 1px solid #2d4a3e;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .stat-number { font-size: 2.5rem; font-weight: bold; color: #4CAF50; }
    .stat-label { font-size: 0.85rem; color: #888; }
    .cost-box {
        background: linear-gradient(135deg, #1a3a2a, #1a2520);
        border: 1px solid #4CAF50;
        border-radius: 10px;
        padding: 15px 20px;
        margin: 15px 0;
        color: #c0e0cc;
    }
    .batch-review {
        background: #1a2520;
        border: 1px solid #2d4a3e;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
        max-height: 500px;
        overflow-y: auto;
    }
    .success-box {
        background: #1a3a2a;
        border: 1px solid #4CAF50;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
    }
    .log-entry { font-family: monospace; font-size: 0.85rem; }
    div[data-testid="stExpander"] { border: 1px solid #2d4a3e; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# TRANSLATION SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are a professional English-to-Bangla book translator for অদম্য প্রেস (Odommo Press).

## TRANSLATION RULES

### Language Priority: Reader-Friendly First
Use whichever language makes each word/phrase easiest to understand for Bangladeshi readers:

- **Use English** when the English word is more commonly understood: Focus, Energy, Goal, Priority, Distraction, Pattern, Reflect, Productivity, Environment, Routine, Mindset, Personality, Confidence, Resilience, Accountability, Motivation, Discipline, Process, Comfort Zone, Trigger, Emotion, Stress, Balance, Relationship, Communication, Trust, Support, Challenge, Growth, Leadership, Strategy, Marketing, Brand, etc.
- **Use Bangla** for sentence structure, connectors, verbs (করুন, বুঝুন, তৈরি করুন), common everyday words, and emotional/descriptive language.
- **AVOID** forcing hard/complex Bangla. Use "Distraction" not "বিক্ষিপ্ততা", "Resilience" not "স্থিতিস্থাপকতা", "Productivity" not "উৎপাদনশীলতা".

### Formatting
- Page marker: === পৃষ্ঠা [Bangla numeral] === at start of each page
- Bangla numerals: ০১২৩৪৫৬৭৮৯
- Numbered lists: ১. ২. ৩.
- Quotes: "বাংলা অনুবাদ" — Author Name
- Preserve ALL bold (**text**), italic (*text*), headings (#), and structure exactly
- Keep paragraph breaks as in original

### OUTPUT FORMAT
For each page, output:

=== পৃষ্ঠা [number in Bangla] ===

[translated content preserving all formatting]

---

Translate ALL pages given. Do not skip any page. Do not add commentary."""

# ═══════════════════════════════════════════════════════════════
# VALID MODEL STRINGS (UPDATED)
# ═══════════════════════════════════════════════════════════════
MODELS = {
    "Sonnet 4.5 (Best Quality)": "claude-sonnet-4-5-20250929",
    "Haiku 4.5 (Fastest/Cheapest)": "claude-haiku-4-5-20251001",
}

# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def extract_pages(pdf_file, start_page, end_page):
    """Extract text from PDF pages."""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    pages = []
    total = doc.page_count
    actual_end = min(end_page, total)
    for i in range(start_page - 1, actual_end):
        page = doc[i]
        text = page.get_text("text").strip()
        if text:
            pages.append((i + 1, text))
    doc.close()
    return pages, total


def translate_batch(client, model, batch_pages):
    """Send a batch of pages to Claude API for translation."""
    pages_text = ""
    for page_num, text in batch_pages:
        pages_text += f"\n\n--- PAGE {page_num} ---\n{text}"

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Translate these {len(batch_pages)} pages to Bangla. Maintain exact page-by-page structure:\n{pages_text}"
        }]
    )

    raw_text = response.content[0].text
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    # Cost calculation
    if "sonnet" in model:
        cost = (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
    else:
        cost = (input_tokens * 0.80 / 1_000_000) + (output_tokens * 4.0 / 1_000_000)

    return raw_text, input_tokens, output_tokens, cost


def parse_translation(raw_text):
    """Parse translated text into page-by-page sections."""
    pages = []
    # Split by page markers
    pattern = r'===\s*পৃষ্ঠা\s*([০-৯]+)\s*==='
    parts = re.split(pattern, raw_text)

    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            page_num = parts[i]
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if content:
                # Remove trailing --- separator
                content = re.sub(r'\n---\s*$', '', content).strip()
                pages.append({"page": page_num, "content": content})
    else:
        # Fallback: treat entire text as one page
        pages.append({"page": "?", "content": raw_text.strip()})

    return pages


def bangla_to_int(bangla_str):
    """Convert Bangla numeral string to integer."""
    mapping = {'০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
               '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'}
    result = ""
    for ch in str(bangla_str):
        result += mapping.get(ch, ch)
    try:
        return int(result)
    except ValueError:
        return 0


def int_to_bangla(num):
    """Convert integer to Bangla numeral string."""
    mapping = {'0': '০', '1': '১', '2': '২', '3': '৩', '4': '৪',
               '5': '৫', '6': '৬', '7': '৭', '8': '৮', '9': '৯'}
    result = ""
    for ch in str(num):
        result += mapping.get(ch, ch)
    return result


def build_docx(translated_pages, book_title, book_author):
    """Build a DOCX file from translated pages."""
    doc = DocxDocument()

    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Noto Sans Bengali'
    font.size = Pt(11)

    # Set margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Title page
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_para.space_before = Pt(100)
    run = title_para.add_run(book_title)
    run.font.size = Pt(24)
    run.bold = True
    run.font.name = 'Noto Sans Bengali'

    author_para = doc.add_paragraph()
    author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = author_para.add_run(book_author)
    run.font.size = Pt(14)
    run.font.name = 'Noto Sans Bengali'

    press_para = doc.add_paragraph()
    press_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    press_para.space_before = Pt(40)
    run = press_para.add_run("অদম্য প্রেস")
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x4C, 0xAF, 0x50)
    run.font.name = 'Noto Sans Bengali'

    doc.add_page_break()

    # Content pages
    for page_data in translated_pages:
        page_num = page_data["page"]
        content = page_data["content"]

        # Page header
        header_para = doc.add_paragraph()
        header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = header_para.add_run(f"পৃষ্ঠা {page_num}")
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        run.font.name = 'Noto Sans Bengali'

        # Process content line by line
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Heading detection
            if line.startswith('# '):
                p = doc.add_paragraph()
                run = p.add_run(line[2:])
                run.bold = True
                run.font.size = Pt(16)
                run.font.name = 'Noto Sans Bengali'
                p.space_before = Pt(12)
                p.space_after = Pt(6)
            elif line.startswith('## '):
                p = doc.add_paragraph()
                run = p.add_run(line[3:])
                run.bold = True
                run.font.size = Pt(14)
                run.font.name = 'Noto Sans Bengali'
                p.space_before = Pt(10)
                p.space_after = Pt(4)
            elif line.startswith('### '):
                p = doc.add_paragraph()
                run = p.add_run(line[4:])
                run.bold = True
                run.font.size = Pt(12)
                run.font.name = 'Noto Sans Bengali'
                p.space_before = Pt(8)
                p.space_after = Pt(4)
            else:
                p = doc.add_paragraph()
                # Handle bold markers
                parts = re.split(r'(\*\*.*?\*\*)', line)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        run = p.add_run(part[2:-2])
                        run.bold = True
                    else:
                        run = p.add_run(part)
                    run.font.size = Pt(11)
                    run.font.name = 'Noto Sans Bengali'
                p.paragraph_format.line_spacing = 1.15

        # Page break between pages
        doc.add_page_break()

    # Save to buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# INITIALIZE SESSION STATE
# ═══════════════════════════════════════════════════════════════
if "all_translated" not in st.session_state:
    st.session_state.all_translated = []
if "current_batch" not in st.session_state:
    st.session_state.current_batch = 0
if "translation_status" not in st.session_state:
    st.session_state.translation_status = "idle"  # idle, translating, reviewing, complete
if "logs" not in st.session_state:
    st.session_state.logs = []
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0.0
if "total_input_tokens" not in st.session_state:
    st.session_state.total_input_tokens = 0
if "total_output_tokens" not in st.session_state:
    st.session_state.total_output_tokens = 0
if "pages_data" not in st.session_state:
    st.session_state.pages_data = []
if "batch_result" not in st.session_state:
    st.session_state.batch_result = []
if "num_batches" not in st.session_state:
    st.session_state.num_batches = 0


# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════
st.markdown('<h1 class="main-title">📚 অদম্য প্রেস — Book Translator</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">English → Bangla | Powered by Claude AI</p>', unsafe_allow_html=True)
st.divider()

# ═══════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ Settings")

    # API Key
    default_key = os.environ.get("ANTHROPIC_API_KEY", "")
    api_key = st.text_input(
        "🔑 Anthropic API Key",
        value=default_key,
        type="password",
        help="Get from console.anthropic.com"
    )

    st.divider()

    # Model selection
    model_choice = st.selectbox("🤖 Model", list(MODELS.keys()))
    model = MODELS[model_choice]

    st.divider()

    # Book metadata
    book_title = st.text_input("📖 Book Title (Bangla)", value="")
    book_author = st.text_input("✍️ Author Name", value="")

    st.divider()

    # Page range
    col1, col2 = st.columns(2)
    with col1:
        start_page = st.number_input("Start Page", min_value=1, value=1)
    with col2:
        end_page = st.number_input("End Page", min_value=1, value=100)

    st.divider()

    # ⭐ BATCH SIZE SELECTION
    batch_size = st.selectbox(
        "📦 Review After Every",
        [5, 10, 15, 20],
        index=1,
        help="Translation pauses after this many pages for your review"
    )

    st.divider()

    # Reset button
    if st.button("🔄 Reset Everything", use_container_width=True):
        for key in ["all_translated", "current_batch", "translation_status", "logs",
                     "total_cost", "total_input_tokens", "total_output_tokens",
                     "pages_data", "batch_result", "num_batches"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    st.divider()
    st.markdown("""
    **💰 Cost Guide:**

    | Model | Per 100 pages |
    |-------|:----------:|
    | Sonnet 4.5 | ~$2-5 |
    | Haiku 4.5 | ~$0.30-1.50 |
    """)

# ═══════════════════════════════════════════════════════════════
# MAIN AREA
# ═══════════════════════════════════════════════════════════════

# File upload
uploaded_file = st.file_uploader("📄 Upload English PDF Book", type=["pdf"])

if uploaded_file:
    # Extract pages on first upload
    if not st.session_state.pages_data:
        with st.spinner("📖 Extracting pages..."):
            pages_data, total_pdf_pages = extract_pages(uploaded_file, start_page, end_page)
            st.session_state.pages_data = pages_data
            st.session_state.total_pdf_pages = total_pdf_pages

    pages_data = st.session_state.pages_data
    num_pages = len(pages_data)
    num_batches = (num_pages + batch_size - 1) // batch_size
    st.session_state.num_batches = num_batches

    # Cost estimation
    if "sonnet" in model:
        est_cost = num_pages * 0.0114
    else:
        est_cost = num_pages * 0.0035

    # Stats display
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-box"><div class="stat-label">📄 Total Pages</div><div class="stat-number">{st.session_state.get("total_pdf_pages", "?")}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-box"><div class="stat-label">📑 Pages to Translate</div><div class="stat-number">{num_pages}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-box"><div class="stat-label">📦 Review Batches</div><div class="stat-number">{num_batches}</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-box"><div class="stat-label">💰 Est. Cost</div><div class="stat-number">${est_cost:.2f}</div></div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="cost-box">
        📊 <strong>Plan:</strong> {num_pages} pages → {num_batches} batches of {batch_size} pages each
        | Model: <strong>{model_choice}</strong> | ⏸️ Pauses after every {batch_size} pages for review
    </div>
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════
    # TRANSLATION CONTROLS
    # ═══════════════════════════════════════════════════════════

    status = st.session_state.translation_status
    current_batch = st.session_state.current_batch

    # Progress bar
    if current_batch > 0:
        progress = current_batch / num_batches
        st.progress(progress, text=f"Progress: {current_batch}/{num_batches} batches complete ({current_batch * batch_size} pages)")

    # ─── START / CONTINUE BUTTON ───
    if status in ["idle", "reviewing"]:
        if current_batch >= num_batches:
            st.session_state.translation_status = "complete"
        else:
            button_label = "🚀 Start Translation" if status == "idle" else f"▶️ Continue — Translate Batch {current_batch + 1}/{num_batches}"

            if st.button(button_label, type="primary", use_container_width=True):
                if not api_key:
                    st.error("❌ Please enter your Anthropic API Key in the sidebar.")
                else:
                    st.session_state.translation_status = "translating"
                    st.rerun()

    # ─── TRANSLATING ───
    if status == "translating":
        batch_idx = st.session_state.current_batch
        b_start = batch_idx * batch_size
        b_end = min(b_start + batch_size, num_pages)
        batch_pages = pages_data[b_start:b_end]
        page_nums = [p[0] for p in batch_pages]

        st.info(f"🔄 **Translating Batch {batch_idx + 1}/{num_batches}** — Pages {page_nums[0]}–{page_nums[-1]}...")

        try:
            client = anthropic.Anthropic(api_key=api_key)
            raw, in_t, out_t, cost = translate_batch(client, model, batch_pages)
            parsed = parse_translation(raw)

            # Store results
            st.session_state.all_translated.extend(parsed)
            st.session_state.batch_result = parsed
            st.session_state.total_cost += cost
            st.session_state.total_input_tokens += in_t
            st.session_state.total_output_tokens += out_t
            st.session_state.current_batch += 1

            log_entry = f"✅ Batch {batch_idx + 1}: Pages {page_nums[0]}–{page_nums[-1]} — {len(parsed)} pages — ${cost:.4f}"
            st.session_state.logs.append(log_entry)

            # Move to review mode
            st.session_state.translation_status = "reviewing"
            st.rerun()

        except anthropic.AuthenticationError:
            st.error("❌ Invalid API key. Please check your Anthropic API key in the sidebar.")
            st.session_state.translation_status = "reviewing"
        except anthropic.NotFoundError as e:
            st.error(f"❌ Model not found: {model}. Error: {str(e)}")
            st.session_state.translation_status = "reviewing"
        except Exception as e:
            log_entry = f"❌ Batch {batch_idx + 1}: Error — {str(e)}"
            st.session_state.logs.append(log_entry)
            st.error(f"Batch {batch_idx + 1} failed: {e}")
            st.session_state.translation_status = "reviewing"

    # ─── REVIEW MODE ───
    if status == "reviewing" and st.session_state.batch_result:
        batch_num = st.session_state.current_batch
        st.success(f"✅ **Batch {batch_num}/{num_batches} Complete** — Review the translation below, then continue or download.")

        # Show translated text for review
        st.markdown("### 📝 Review Translation")
        with st.expander(f"📖 Batch {batch_num} — Translated Pages (click to expand)", expanded=True):
            for page_data in st.session_state.batch_result:
                st.markdown(f"**━━━ পৃষ্ঠা {page_data['page']} ━━━**")
                st.markdown(page_data["content"])
                st.markdown("---")

        # Download current progress as DOCX
        st.markdown("### 📥 Download")
        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            # Download all translated so far
            if st.session_state.all_translated:
                docx_buffer = build_docx(
                    st.session_state.all_translated,
                    book_title or "Translated Book",
                    book_author or "Author"
                )
                total_pages_done = len(st.session_state.all_translated)
                filename = f"{book_title or 'translation'}_pages_1-{total_pages_done}.docx"
                st.download_button(
                    label=f"📥 Download All ({total_pages_done} pages so far)",
                    data=docx_buffer,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        with col_dl2:
            # Download only this batch
            if st.session_state.batch_result:
                batch_docx = build_docx(
                    st.session_state.batch_result,
                    book_title or "Translated Book",
                    book_author or "Author"
                )
                st.download_button(
                    label=f"📥 Download Batch {batch_num} Only",
                    data=batch_docx,
                    file_name=f"batch_{batch_num}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        # Progress summary
        remaining = num_batches - batch_num
        st.markdown(f"""
        <div class="cost-box">
            📊 <strong>Progress:</strong> {batch_num}/{num_batches} batches done |
            📄 {len(st.session_state.all_translated)} pages translated |
            📦 {remaining} batches remaining |
            💰 Total cost so far: <strong>${st.session_state.total_cost:.4f}</strong>
        </div>
        """, unsafe_allow_html=True)

    # ─── COMPLETE ───
    if status == "complete" or (status == "reviewing" and st.session_state.current_batch >= num_batches):
        st.session_state.translation_status = "complete"

        st.balloons()
        st.markdown(f"""
        <div class="success-box">
            <h3 style="color: #4CAF50; margin-top:0;">🎉 Translation Complete!</h3>
            <p>📄 Total pages: <strong>{len(st.session_state.all_translated)}</strong></p>
            <p>📦 Batches: <strong>{st.session_state.current_batch}</strong></p>
            <p>💰 Total cost: <strong>${st.session_state.total_cost:.4f}</strong></p>
            <p>🔤 Tokens: {st.session_state.total_input_tokens:,} input + {st.session_state.total_output_tokens:,} output</p>
        </div>
        """, unsafe_allow_html=True)

        # Final download
        if st.session_state.all_translated:
            docx_buffer = build_docx(
                st.session_state.all_translated,
                book_title or "Translated Book",
                book_author or "Author"
            )
            st.download_button(
                label="📥 Download Complete Translation (DOCX)",
                data=docx_buffer,
                file_name=f"{book_title or 'translation'}_complete.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                type="primary",
            )

    # ─── LOGS ───
    if st.session_state.logs:
        with st.expander("📋 Translation Logs", expanded=False):
            for log in st.session_state.logs:
                if log.startswith("✅"):
                    st.success(log)
                else:
                    st.error(log)

else:
    # Welcome screen
    st.markdown("""
    ### 👋 How to Use

    1. **Enter your API Key** in the sidebar (get from [console.anthropic.com](https://console.anthropic.com))
    2. **Upload** your English PDF book
    3. **Set** book title, author, page range, and batch size in the sidebar
    4. **Click** "Start Translation" — it translates one batch then **PAUSES**
    5. **Review** the translation preview on screen
    6. **Download** the DOCX or click "Continue" for the next batch
    7. **Repeat** until all pages are done

    ---

    ### ⭐ What's New in v2.0

    - **Batch Review:** Translation pauses after every 5 or 10 pages (your choice)
    - **Preview:** See translated text on screen before downloading
    - **Partial Download:** Download DOCX after each batch or wait for complete book
    - **Fixed Models:** Updated to latest Claude model versions

    ---

    *Built for অদম্য প্রেস (Odommo Press) | Online Tech Academy*
    """)

# Footer
st.divider()
st.markdown(
    "<p style='text-align:center; color:#666; font-size:0.8rem;'>"
    "অদম্য প্রেস Book Translator v2.0 | Powered by Claude AI | Online Tech Academy</p>",
    unsafe_allow_html=True
)
