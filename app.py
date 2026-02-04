"""
═══════════════════════════════════════════════════════════════
 অদম্য প্রেস — Book Translation Web App v2.1
 Fixes: Page numbering, Bold/Style, Progress bar, Translator name
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
import hashlib
from datetime import datetime
from docx import Document as DocxDocument
from docx.shared import Pt, Inches, RGBColor, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
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
    .translator-badge {
        background: linear-gradient(135deg, #1a2540, #1a2030);
        border: 1px solid #4a6fa5;
        border-radius: 10px;
        padding: 12px 20px;
        margin: 10px 0;
        color: #a0c0e0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .translator-badge .name { font-weight: bold; color: #70b0ff; font-size: 1.05rem; }

    /* ── Enhanced Progress Bar ── */
    .progress-container {
        background: #1a2520;
        border: 1px solid #2d4a3e;
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
    }
    .progress-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .progress-header .left { font-size: 1rem; color: #e0e0e0; }
    .progress-header .right { font-size: 0.9rem; color: #4CAF50; font-weight: bold; }
    .progress-bar-outer {
        background: #0d1512;
        border-radius: 8px;
        height: 28px;
        overflow: hidden;
        position: relative;
    }
    .progress-bar-inner {
        background: linear-gradient(90deg, #2d7a3e, #4CAF50, #66d470);
        height: 100%;
        border-radius: 8px;
        transition: width 0.5s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 50px;
    }
    .progress-bar-text {
        color: white;
        font-size: 0.8rem;
        font-weight: bold;
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    }
    .progress-stats {
        display: flex;
        justify-content: space-between;
        margin-top: 10px;
        font-size: 0.8rem;
        color: #888;
    }
    .progress-stats .item { text-align: center; }
    .progress-stats .value { color: #4CAF50; font-weight: bold; font-size: 0.95rem; }

    .success-box {
        background: #1a3a2a;
        border: 1px solid #4CAF50;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
    }
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

### CRITICAL FORMATTING RULES
You MUST preserve formatting using Markdown syntax:
- **Bold text** → wrap in double asterisks: **bold text**
- *Italic text* → wrap in single asterisks: *italic text*
- ***Bold italic*** → wrap in triple asterisks: ***bold italic***
- Headings → use # for H1, ## for H2, ### for H3
- Numbered lists → use Bangla numerals: ১. ২. ৩.
- Bullet lists → use • or -
- Quotes → use > at start of line, attribute as: > "বাংলা অনুবাদ" — Author Name
- Preserve ALL paragraph breaks exactly as original
- Chapter/section titles MUST be bold: **শিরোনাম**

### OUTPUT FORMAT
For each page, output EXACTLY this format:

=== পৃষ্ঠা [ORIGINAL PAGE NUMBER IN BANGLA] ===

[translated content with ALL markdown formatting preserved]

---

IMPORTANT:
- The page number after পৃষ্ঠা MUST match the ORIGINAL source PDF page number (e.g., if source is PAGE 21, output পৃষ্ঠা ২১)
- Translate ALL pages given. Do not skip any page.
- Do not add commentary or notes.
- Every heading, subheading, and important term must use **bold**
- Every emphasized word must use *italic*"""

# ═══════════════════════════════════════════════════════════════
# VALID MODEL STRINGS
# ═══════════════════════════════════════════════════════════════
MODELS = {
    "Sonnet 4.5 (Best Quality)": "claude-sonnet-4-5-20250929",
    "Haiku 4.5 (Fastest/Cheapest)": "claude-haiku-4-5-20251001",
}

# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def extract_pages(pdf_file, start_page, end_page):
    """Extract text from PDF pages. Returns list of (actual_page_num, text)."""
    pdf_file.seek(0)
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    pages = []
    total = doc.page_count
    actual_end = min(end_page, total)
    for i in range(start_page - 1, actual_end):
        page = doc[i]
        text = page.get_text("text").strip()
        if text:
            pages.append((i + 1, text))  # i+1 = actual PDF page number
    doc.close()
    return pages, total


def translate_batch(client, model, batch_pages):
    """Send a batch of pages to Claude API for translation."""
    pages_text = ""
    for page_num, text in batch_pages:
        pages_text += f"\n\n--- PAGE {page_num} (translate as পৃষ্ঠা {int_to_bangla(page_num)}) ---\n{text}"

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Translate these {len(batch_pages)} pages to Bangla. "
                f"CRITICAL: Use the ORIGINAL page numbers shown (not 1,2,3). "
                f"Keep ALL **bold**, *italic*, # heading formatting.\n"
                f"{pages_text}"
            )
        }]
    )

    raw_text = response.content[0].text
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    if "sonnet" in model:
        cost = (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
    else:
        cost = (input_tokens * 0.80 / 1_000_000) + (output_tokens * 4.0 / 1_000_000)

    return raw_text, input_tokens, output_tokens, cost


def parse_translation(raw_text, expected_page_nums=None):
    """Parse translated text into page-by-page sections."""
    pages = []
    pattern = r'===\s*পৃষ্ঠা\s*([০-৯]+)\s*==='
    parts = re.split(pattern, raw_text)

    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            page_num = parts[i]
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if content:
                content = re.sub(r'\n---\s*$', '', content).strip()
                pages.append({"page": page_num, "content": content})
    else:
        if expected_page_nums and len(expected_page_nums) == 1:
            pages.append({"page": int_to_bangla(expected_page_nums[0]), "content": raw_text.strip()})
        else:
            pages.append({"page": "?", "content": raw_text.strip()})

    return pages


def bangla_to_int(bangla_str):
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
    mapping = {'0': '০', '1': '১', '2': '২', '3': '৩', '4': '৪',
               '5': '৫', '6': '৬', '7': '৭', '8': '৮', '9': '৯'}
    result = ""
    for ch in str(num):
        result += mapping.get(ch, ch)
    return result


def add_formatted_text(paragraph, text, base_bold=False, base_italic=False, font_size=Pt(11), font_name='Noto Sans Bengali'):
    """
    Parse markdown-style formatting (**bold**, *italic*, ***both***) and add runs to paragraph.
    """
    # Pattern: ***bold italic***, **bold**, *italic*
    pattern = r'(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*)'
    last_end = 0

    for match in re.finditer(pattern, text):
        before = text[last_end:match.start()]
        if before:
            run = paragraph.add_run(before)
            run.font.size = font_size
            run.font.name = font_name
            run.bold = base_bold
            run.italic = base_italic

        if match.group(2):      # ***bold italic***
            run = paragraph.add_run(match.group(2))
            run.bold = True
            run.italic = True
        elif match.group(3):    # **bold**
            run = paragraph.add_run(match.group(3))
            run.bold = True
            run.italic = base_italic
        elif match.group(4):    # *italic*
            run = paragraph.add_run(match.group(4))
            run.bold = base_bold
            run.italic = True

        run.font.size = font_size
        run.font.name = font_name
        last_end = match.end()

    remaining = text[last_end:]
    if remaining:
        run = paragraph.add_run(remaining)
        run.font.size = font_size
        run.font.name = font_name
        run.bold = base_bold
        run.italic = base_italic


def build_docx(translated_pages, book_title, book_author, translator_name=""):
    """Build a professionally formatted DOCX with bold/italic/heading support."""
    doc = DocxDocument()

    style = doc.styles['Normal']
    font = style.font
    font.name = 'Noto Sans Bengali'
    font.size = Pt(11)
    style.paragraph_format.line_spacing = 1.15

    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # ── Title Page ──
    for _ in range(4):
        doc.add_paragraph()

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run(book_title)
    run.font.size = Pt(26)
    run.bold = True
    run.font.name = 'Noto Sans Bengali'

    doc.add_paragraph()

    author_para = doc.add_paragraph()
    author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = author_para.add_run(book_author)
    run.font.size = Pt(14)
    run.font.name = 'Noto Sans Bengali'

    doc.add_paragraph()

    press_para = doc.add_paragraph()
    press_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = press_para.add_run("অদম্য প্রেস")
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor(0x4C, 0xAF, 0x50)
    run.bold = True
    run.font.name = 'Noto Sans Bengali'

    if translator_name:
        doc.add_paragraph()
        trans_para = doc.add_paragraph()
        trans_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = trans_para.add_run(f"অনুবাদক: {translator_name}")
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
        run.font.name = 'Noto Sans Bengali'

        ts_para = doc.add_paragraph()
        ts_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = ts_para.add_run(f"তারিখ: {datetime.now().strftime('%d %B %Y, %I:%M %p')}")
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
        run.font.name = 'Noto Sans Bengali'

    doc.add_page_break()

    # ── Content Pages ──
    for idx, page_data in enumerate(translated_pages):
        page_num = page_data["page"]
        content = page_data["content"]

        # Page number header
        header_para = doc.add_paragraph()
        header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = header_para.add_run(f"পৃষ্ঠা {page_num}")
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
        run.font.name = 'Noto Sans Bengali'
        run.italic = True

        # Separator
        sep = doc.add_paragraph()
        sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = sep.add_run("─" * 50)
        run.font.size = Pt(6)
        run.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)

        # Process content
        lines = content.split('\n')
        for line in lines:
            stripped = line.strip()
            if not stripped:
                doc.add_paragraph()
                continue

            # Headings
            if stripped.startswith('### '):
                p = doc.add_paragraph()
                p.space_before = Pt(8)
                p.space_after = Pt(4)
                add_formatted_text(p, stripped[4:], base_bold=True, font_size=Pt(12))

            elif stripped.startswith('## '):
                p = doc.add_paragraph()
                p.space_before = Pt(10)
                p.space_after = Pt(5)
                add_formatted_text(p, stripped[3:], base_bold=True, font_size=Pt(14))

            elif stripped.startswith('# '):
                p = doc.add_paragraph()
                p.space_before = Pt(14)
                p.space_after = Pt(8)
                add_formatted_text(p, stripped[2:], base_bold=True, font_size=Pt(16))

            # Block Quotes
            elif stripped.startswith('> '):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.5)
                p.space_before = Pt(6)
                p.space_after = Pt(6)
                add_formatted_text(p, stripped[2:], base_italic=True, font_size=Pt(11))

            # Numbered lists (Bangla)
            elif re.match(r'^[০-৯]+[\.\)]\s', stripped):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.3)
                p.space_before = Pt(2)
                p.space_after = Pt(2)
                add_formatted_text(p, stripped, font_size=Pt(11))

            # Bullet lists
            elif stripped.startswith('• ') or stripped.startswith('- '):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.3)
                p.space_before = Pt(2)
                p.space_after = Pt(2)
                bullet_text = '• ' + stripped[2:]
                add_formatted_text(p, bullet_text, font_size=Pt(11))

            # Regular paragraph
            else:
                p = doc.add_paragraph()
                p.paragraph_format.line_spacing = 1.15
                add_formatted_text(p, stripped, font_size=Pt(11))

        if idx < len(translated_pages) - 1:
            doc.add_page_break()

    # Footer with translator info
    if translator_name:
        doc.add_paragraph()
        footer_sep = doc.add_paragraph()
        footer_sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer_sep.add_run("━" * 40)
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)

        footer = doc.add_paragraph()
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run(f"অনুবাদ: {translator_name} | অদম্য প্রেস | {datetime.now().strftime('%Y')}")
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        run.font.name = 'Noto Sans Bengali'

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def render_progress(current_batch, total_batches, pages_done, total_pages, cost, first_page, last_page):
    """Render enhanced visual progress bar."""
    if total_batches == 0:
        return

    pct = int((current_batch / total_batches) * 100)
    pct = min(pct, 100)
    pages_remaining = total_pages - pages_done

    if current_batch > 0:
        current_range = f"p{first_page}–{first_page + pages_done - 1}"
    else:
        current_range = "Not started"

    st.markdown(f"""
    <div class="progress-container">
        <div class="progress-header">
            <div class="left">📊 Translation Progress</div>
            <div class="right">{pct}% Complete</div>
        </div>
        <div class="progress-bar-outer">
            <div class="progress-bar-inner" style="width: {max(pct, 3)}%;">
                <span class="progress-bar-text">{pct}%</span>
            </div>
        </div>
        <div class="progress-stats">
            <div class="item">📦 Batches<br><span class="value">{current_batch}/{total_batches}</span></div>
            <div class="item">📄 Pages Done<br><span class="value">{pages_done}/{total_pages}</span></div>
            <div class="item">📍 Translated<br><span class="value">{current_range}</span></div>
            <div class="item">⏳ Remaining<br><span class="value">{pages_remaining} pages</span></div>
            <div class="item">💰 Cost<br><span class="value">${cost:.4f}</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════
defaults = {
    "all_translated": [],
    "current_batch": 0,
    "translation_status": "idle",
    "logs": [],
    "total_cost": 0.0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "pages_data": [],
    "batch_result": [],
    "num_batches": 0,
    "total_pdf_pages": 0,
    "extract_hash": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        if isinstance(v, list):
            st.session_state[k] = []
        else:
            st.session_state[k] = v


# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════
st.markdown('<h1 class="main-title">📚 অদম্য প্রেস — Book Translator</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">English → Bangla | Powered by Claude AI | Online Tech Academy</p>', unsafe_allow_html=True)
st.divider()

# ═══════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ Settings")

    default_key = os.environ.get("ANTHROPIC_API_KEY", "")
    api_key = st.text_input("🔑 Anthropic API Key", value=default_key, type="password",
                            help="Get from console.anthropic.com")

    st.divider()

    # ⭐ TRANSLATOR NAME — MANDATORY
    st.markdown("##### 👤 Translator (Required)")
    translator_name = st.text_input("👤 Your Name", value="", placeholder="আপনার নাম লিখুন...",
                                     help="Appears on DOCX cover page & admin logs")

    st.divider()

    model_choice = st.selectbox("🤖 Model", list(MODELS.keys()))
    model = MODELS[model_choice]

    st.divider()

    book_title = st.text_input("📖 Book Title (Bangla)", value="")
    book_author = st.text_input("✍️ Author Name", value="")

    st.divider()

    st.markdown("##### 📑 Page Range")
    col1, col2 = st.columns(2)
    with col1:
        start_page = st.number_input("Start Page", min_value=1, value=1)
    with col2:
        end_page = st.number_input("End Page", min_value=1, value=100)

    st.divider()

    batch_size = st.selectbox("📦 Review After Every", [5, 10, 15, 20], index=1,
                              help="Pauses after this many pages for review")

    st.divider()

    if st.button("🔄 Reset Everything", use_container_width=True, type="secondary"):
        for key in defaults.keys():
            if isinstance(defaults[key], list):
                st.session_state[key] = []
            else:
                st.session_state[key] = defaults[key]
        st.rerun()

    st.divider()
    st.markdown("**💰 Cost Guide:**\n\n| Model | Per 100 pages |\n|-------|:----------:|\n| Sonnet 4.5 | ~$2-5 |\n| Haiku 4.5 | ~$0.30-1.50 |")


# ═══════════════════════════════════════════════════════════════
# MAIN AREA
# ═══════════════════════════════════════════════════════════════

uploaded_file = st.file_uploader("📄 Upload English PDF Book", type=["pdf"])

if uploaded_file:

    # ── FIX #1: Re-extract when start/end page changes ──
    current_hash = hashlib.md5(f"{uploaded_file.name}_{start_page}_{end_page}".encode()).hexdigest()
    if st.session_state.extract_hash != current_hash:
        with st.spinner("📖 Extracting pages..."):
            pages_data, total_pdf_pages = extract_pages(uploaded_file, start_page, end_page)
            st.session_state.pages_data = pages_data
            st.session_state.total_pdf_pages = total_pdf_pages
            st.session_state.extract_hash = current_hash
            # Reset translation if range changed mid-translation
            if st.session_state.current_batch > 0:
                st.session_state.all_translated = []
                st.session_state.current_batch = 0
                st.session_state.translation_status = "idle"
                st.session_state.logs = []
                st.session_state.total_cost = 0.0
                st.session_state.total_input_tokens = 0
                st.session_state.total_output_tokens = 0
                st.session_state.batch_result = []

    pages_data = st.session_state.pages_data
    num_pages = len(pages_data)
    num_batches = (num_pages + batch_size - 1) // batch_size
    st.session_state.num_batches = num_batches

    if "sonnet" in model:
        est_cost = num_pages * 0.0114
    else:
        est_cost = num_pages * 0.0035

    # ── Translator Badge ──
    if translator_name:
        st.markdown(f"""
        <div class="translator-badge">
            👤 <span class="name">{translator_name}</span>
            <span style="color:#888">| 🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p')} | Pages {start_page}–{end_page}</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Stats with Page Range column ──
    first_actual = pages_data[0][0] if pages_data else start_page
    last_actual = pages_data[-1][0] if pages_data else end_page

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f'<div class="stat-box"><div class="stat-label">📄 Total Pages</div><div class="stat-number">{st.session_state.total_pdf_pages}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-box"><div class="stat-label">📑 Pages to Translate</div><div class="stat-number">{num_pages}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-box"><div class="stat-label">📍 Page Range</div><div class="stat-number" style="font-size:1.8rem;">{first_actual}–{last_actual}</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-box"><div class="stat-label">📦 Review Batches</div><div class="stat-number">{num_batches}</div></div>', unsafe_allow_html=True)
    with col5:
        st.markdown(f'<div class="stat-box"><div class="stat-label">💰 Est. Cost</div><div class="stat-number">${est_cost:.2f}</div></div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="cost-box">
        📊 <strong>Plan:</strong> {num_pages} pages (Page {first_actual}→{last_actual}) → {num_batches} batches of {batch_size}
        | Model: <strong>{model_choice}</strong> | ⏸️ Pauses every {batch_size} pages for review
    </div>
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════
    # TRANSLATION ENGINE
    # ═══════════════════════════════════════════════════════════

    status = st.session_state.translation_status
    current_batch = st.session_state.current_batch
    pages_done = len(st.session_state.all_translated)

    # ── FIX #3: Enhanced Progress Bar ──
    render_progress(current_batch, num_batches, pages_done, num_pages,
                    st.session_state.total_cost, first_actual, last_actual)

    # ── START / CONTINUE ──
    if status in ["idle", "reviewing"]:
        if current_batch >= num_batches:
            st.session_state.translation_status = "complete"
            st.rerun()
        else:
            # FIX #4: Block start without translator name
            if not translator_name:
                st.warning("⚠️ **Translator Name required.** Please enter your name in the sidebar.")

            # Show correct page range for next batch
            next_start_idx = current_batch * batch_size
            next_end_idx = min(next_start_idx + batch_size - 1, num_pages - 1)
            next_start_page = pages_data[next_start_idx][0]
            next_end_page = pages_data[next_end_idx][0]

            if status == "idle":
                btn_label = f"🚀 Start Translation — Batch 1/{num_batches} (Pages {next_start_page}–{next_end_page})"
            else:
                btn_label = f"▶️ Continue — Batch {current_batch + 1}/{num_batches} (Pages {next_start_page}–{next_end_page})"

            if st.button(btn_label, type="primary", use_container_width=True, disabled=(not translator_name)):
                if not api_key:
                    st.error("❌ Enter your Anthropic API Key in the sidebar.")
                else:
                    st.session_state.translation_status = "translating"
                    st.rerun()

    # ── TRANSLATING ──
    if status == "translating":
        batch_idx = st.session_state.current_batch
        b_start = batch_idx * batch_size
        b_end = min(b_start + batch_size, num_pages)
        batch_pages = pages_data[b_start:b_end]
        page_nums = [p[0] for p in batch_pages]

        st.info(f"🔄 **Translating Batch {batch_idx + 1}/{num_batches}** — Pages {page_nums[0]}–{page_nums[-1]} ({len(batch_pages)} pages)...")

        try:
            client = anthropic.Anthropic(api_key=api_key)
            raw, in_t, out_t, cost = translate_batch(client, model, batch_pages)
            parsed = parse_translation(raw, expected_page_nums=page_nums)

            st.session_state.all_translated.extend(parsed)
            st.session_state.batch_result = parsed
            st.session_state.total_cost += cost
            st.session_state.total_input_tokens += in_t
            st.session_state.total_output_tokens += out_t
            st.session_state.current_batch += 1

            log_entry = (
                f"✅ Batch {batch_idx + 1}: Pages {page_nums[0]}–{page_nums[-1]} "
                f"— {len(parsed)} pages — ${cost:.4f} "
                f"— by {translator_name} @ {datetime.now().strftime('%H:%M:%S')}"
            )
            st.session_state.logs.append(log_entry)
            st.session_state.translation_status = "reviewing"
            st.rerun()

        except anthropic.AuthenticationError:
            st.error("❌ Invalid API key.")
            st.session_state.translation_status = "reviewing"
        except anthropic.NotFoundError as e:
            st.error(f"❌ Model not found: `{model}`. Error: {str(e)}")
            st.session_state.translation_status = "reviewing"
        except Exception as e:
            st.session_state.logs.append(f"❌ Batch {batch_idx + 1}: {str(e)} — by {translator_name}")
            st.error(f"Batch failed: {e}")
            st.session_state.translation_status = "reviewing"

    # ── REVIEW MODE ──
    if status == "reviewing" and st.session_state.batch_result:
        batch_num = st.session_state.current_batch

        st.success(f"✅ **Batch {batch_num}/{num_batches} Complete** — Review below, then Continue or Download.")

        st.markdown("### 📝 Review Translation")
        with st.expander(f"📖 Batch {batch_num} — Click to Review", expanded=True):
            for page_data in st.session_state.batch_result:
                st.markdown(f"#### ━━━ পৃষ্ঠা {page_data['page']} ━━━")
                st.markdown(page_data["content"])
                st.markdown("---")

        st.markdown("### 📥 Download DOCX")
        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            if st.session_state.all_translated:
                docx_buf = build_docx(st.session_state.all_translated,
                                      book_title or "Translated Book",
                                      book_author or "Author", translator_name)
                total_done = len(st.session_state.all_translated)
                fp = st.session_state.all_translated[0]["page"]
                lp = st.session_state.all_translated[-1]["page"]
                st.download_button(
                    f"📥 Download All ({total_done} pages: p{fp}–{lp})",
                    data=docx_buf,
                    file_name=f"{book_title or 'translation'}_p{bangla_to_int(fp)}-{bangla_to_int(lp)}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        with col_dl2:
            if st.session_state.batch_result:
                batch_buf = build_docx(st.session_state.batch_result,
                                       book_title or "Translated Book",
                                       book_author or "Author", translator_name)
                bf = st.session_state.batch_result[0]["page"]
                bl = st.session_state.batch_result[-1]["page"]
                st.download_button(
                    f"📥 Batch {batch_num} Only (p{bf}–{bl})",
                    data=batch_buf,
                    file_name=f"batch_{batch_num}_p{bangla_to_int(bf)}-{bangla_to_int(bl)}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

    # ── COMPLETE ──
    if status == "complete":
        st.balloons()
        st.markdown(f"""
        <div class="success-box">
            <h3 style="color: #4CAF50; margin-top:0;">🎉 Translation Complete!</h3>
            <p>📄 Pages: <strong>{len(st.session_state.all_translated)}</strong> | 📦 Batches: <strong>{st.session_state.current_batch}</strong></p>
            <p>💰 Cost: <strong>${st.session_state.total_cost:.4f}</strong> | 🔤 Tokens: {st.session_state.total_input_tokens:,} in + {st.session_state.total_output_tokens:,} out</p>
            <p>👤 Translator: <strong>{translator_name}</strong> | 🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p')}</p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.all_translated:
            docx_buf = build_docx(st.session_state.all_translated,
                                  book_title or "Translated Book",
                                  book_author or "Author", translator_name)
            fp = st.session_state.all_translated[0]["page"]
            lp = st.session_state.all_translated[-1]["page"]
            st.download_button(
                f"📥 Download Complete Translation (p{fp}–{lp})",
                data=docx_buf,
                file_name=f"{book_title or 'translation'}_complete_p{bangla_to_int(fp)}-{bangla_to_int(lp)}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                type="primary",
            )

    # ── ADMIN LOG PANEL ──
    if st.session_state.logs:
        with st.expander("📋 Admin Panel — Translation Logs", expanded=False):
            st.markdown(f"""
            | Field | Value |
            |-------|-------|
            | 👤 Translator | **{translator_name or '—'}** |
            | 📖 Book | {book_title or '—'} by {book_author or '—'} |
            | 📍 Range | Pages {start_page}–{end_page} |
            | 🤖 Model | {model_choice} (`{model}`) |
            | 💰 Total Cost | ${st.session_state.total_cost:.4f} |
            | 📦 Batches | {st.session_state.current_batch}/{num_batches} |
            | 🔤 Tokens | {st.session_state.total_input_tokens:,} in / {st.session_state.total_output_tokens:,} out |
            """)
            st.divider()
            for log in st.session_state.logs:
                if log.startswith("✅"):
                    st.success(log)
                else:
                    st.error(log)

else:
    st.markdown("""
    ### 👋 How to Use

    1. **Enter API Key** & **Your Name** in the sidebar ← both required
    2. **Upload** your English PDF book
    3. **Set** title, author, page range, and review batch size
    4. **Click** "Start Translation" — pauses after each batch
    5. **Review** Bangla text on screen
    6. **Download** DOCX after each batch or after completion
    7. **Continue** to next batch

    ---

    ### ⭐ v2.1 Features

    | Feature | Details |
    |---------|---------|
    | ✅ Correct Pages | Start page 21 → translates pages 21–30, not 1–10 |
    | ✅ Bold/Italic/Heading | All formatting preserved in DOCX |
    | ✅ Progress Bar | Visual tracker with pages, cost, range |
    | ✅ Translator Name | Required — shown in DOCX cover & admin logs |
    | ✅ Batch Review | Pause after 5/10/15/20 pages to review |
    | ✅ Download Options | Download all-so-far or current batch |

    ---

    *Built for অদম্য প্রেস (Odommo Press) | Online Tech Academy*
    """)

st.divider()
st.markdown(
    "<p style='text-align:center; color:#666; font-size:0.8rem;'>"
    "অদম্য প্রেস Book Translator v2.1 | Powered by Claude AI | Online Tech Academy</p>",
    unsafe_allow_html=True
)
