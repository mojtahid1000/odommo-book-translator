"""
═══════════════════════════════════════════════════════════════
 অদম্য প্রেস — Book Translation Web App
 Cloud-hosted: Your team uploads PDF → gets Bangla DOCX back
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
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="অদম্য প্রেস — Book Translator",
    page_icon="📚",
    layout="wide",
)

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════
CONFIG = {
    "font_bangla": "Noto Sans Bengali",
    "font_english": "Calibri",
    "font_size_body": 11,
    "font_size_heading": 16,
    "font_size_quote": 11,
    "page_margin_inches": 1.0,
}

SYSTEM_PROMPT = """You are a professional English-to-Bangla book translator for অদম্য প্রেস (Odommo Press), specializing in reader-friendly translations for Bangladeshi readers.

## TRANSLATION RULES

### Language Priority: Reader-Friendly First
The goal is MAXIMUM READABILITY for Bangladeshi readers. Use whichever language makes each word/phrase easiest to understand:

- **Use English** when the English word is more commonly understood or avoids unnecessarily complex Bangla. Examples: Focus, Energy, Goal, Priority, Distraction, Pattern, Reflect, Productivity, Environment, Routine, Mindset, Personality, Confidence, Resilience, Accountability, Motivation, Discipline, Process, Comfort Zone, Trigger, Emotion, Stress, Balance, Relationship, Communication, Trust, Support, Challenge, Growth, etc.
- **Use Bangla** for sentence structure, connectors, verbs (করুন, বুঝুন, তৈরি করুন, etc.), common everyday words, and emotional/descriptive language.
- **Use English** for all technical/business terms widely used in Bangladesh.
- **Use English** for proper nouns.
- **AVOID** forcing hard/complex Bangla. Use "Distraction" not "বিক্ষিপ্ততা", "Resilience" not "স্থিতিস্থাপকতা", "Productivity" not "উৎপাদনশীলতা".
- Translate for MEANING, not word-by-word.
- Sentences must sound natural when read aloud.

### Output Format
Return ONLY the translation in this exact structured format. Do NOT add any commentary.

For each page, output:

---PAGE_START [page_number]---
HEADING: [Translated chapter heading]
HEADING_EN: [Original English heading]
QUOTE: [Translated quote if present, or leave empty]
BODY: [Translated body paragraph - opening]
ITEMS:
[bangla_number]. **[Bold part]** [Rest of item]
...
CLOSING: [Translated closing paragraph]
---PAGE_END---

### Bangla Numerals
Always use: ১ ২ ৩ ৪ ৫ ৬ ৭ ৮ ৯ ০
"""


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def extract_pages_from_bytes(pdf_bytes, start_page=1, end_page=None):
    """Extract text from PDF bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    if end_page is None or end_page > total:
        end_page = total
    pages = []
    for i in range(start_page - 1, end_page):
        text = doc[i].get_text().strip()
        if text:
            pages.append((i + 1, text))
    doc.close()
    return pages, total


def translate_batch(client, model, pages):
    """Send pages to Claude API for translation."""
    user_content = "Translate the following pages from English to Reader-Friendly Bangla:\n\n"
    for page_num, text in pages:
        user_content += f"=== PAGE {page_num} ===\n{text}\n\n"

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}]
    )

    result = ""
    for block in response.content:
        if block.type == "text":
            result += block.text

    input_t = response.usage.input_tokens
    output_t = response.usage.output_tokens

    # Cost calculation based on model
    if "haiku" in model:
        cost = (input_t * 0.0008 + output_t * 0.004) / 1000
    else:
        cost = (input_t * 0.003 + output_t * 0.015) / 1000

    return result, input_t, output_t, cost


def parse_translation(raw_text):
    """Parse structured translation output."""
    pages = []
    page_blocks = re.split(r'---PAGE_START\s*\[?(\d+)\]?---', raw_text)
    i = 1
    while i < len(page_blocks) - 1:
        page_num = int(page_blocks[i])
        content = re.sub(r'---PAGE_END---', '', page_blocks[i + 1]).strip()

        page_data = {
            "page_num": page_num,
            "heading": "", "heading_en": "", "quote": "",
            "body": "", "items": [], "closing": "", "raw": content,
        }

        for field, pattern in [
            ("heading", r'HEADING:\s*(.+?)(?=\n(?:HEADING_EN|QUOTE|BODY|ITEMS|CLOSING|$))'),
            ("heading_en", r'HEADING_EN:\s*(.+?)(?=\n(?:QUOTE|BODY|ITEMS|CLOSING|$))'),
            ("quote", r'QUOTE:\s*(.+?)(?=\n(?:BODY|ITEMS|CLOSING|$))'),
            ("body", r'BODY:\s*(.+?)(?=\n(?:ITEMS|CLOSING|$))'),
            ("closing", r'CLOSING:\s*(.+?)$'),
        ]:
            m = re.search(pattern, content, re.DOTALL)
            if m:
                page_data[field] = m.group(1).strip()

        items_m = re.search(r'ITEMS:\s*(.+?)(?=\n(?:CLOSING|$))', content, re.DOTALL)
        if items_m:
            page_data["items"] = re.findall(r'[১২৩৪৫৬৭৮৯০]+\.\s*(.+)', items_m.group(1))

        pages.append(page_data)
        i += 2

    if not pages and raw_text.strip():
        pages.append({
            "page_num": 0, "heading": "", "heading_en": "",
            "quote": "", "body": raw_text.strip(),
            "items": [], "closing": "", "raw": raw_text.strip(),
        })
    return pages


def build_docx(translated_pages, title="", author=""):
    """Build a formatted DOCX from translated pages."""
    doc = DocxDocument()

    # Page setup
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    margin = Inches(CONFIG["page_margin_inches"])
    section.top_margin = margin
    section.bottom_margin = margin
    section.left_margin = margin
    section.right_margin = margin

    # Header
    hp = section.header.paragraphs[0] if section.header.paragraphs else section.header.add_paragraph()
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = hp.add_run(title or "বাংলা অনুবাদ")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(153, 153, 153)
    run.font.name = CONFIG["font_bangla"]

    # Footer
    fp = section.footer.paragraphs[0] if section.footer.paragraphs else section.footer.add_paragraph()
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run(f"{author} — বাংলা অনুবাদ | অদম্য প্রেস")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(153, 153, 153)
    run.font.name = CONFIG["font_bangla"]

    # Style
    style = doc.styles['Normal']
    style.font.name = CONFIG["font_bangla"]
    style.font.size = Pt(CONFIG["font_size_body"])
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = 1.15

    bangla_nums = ['১','২','৩','৪','৫','৬','৭','৮','৯','১০',
                   '১১','১২','১৩','১৪','১৫','১৬','১৭','১৮','১৯','২০']

    for idx, pd in enumerate(translated_pages):
        if idx > 0:
            doc.add_page_break()

        if pd.get("heading"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.space_before = Pt(12)
            p.space_after = Pt(6)
            r = p.add_run(pd["heading"])
            r.font.name = CONFIG["font_bangla"]
            r.font.size = Pt(CONFIG["font_size_heading"])
            r.bold = True

        if pd.get("heading_en"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.space_after = Pt(12)
            r = p.add_run(f"({pd['heading_en']})")
            r.font.size = Pt(10)
            r.font.color.rgb = RGBColor(102, 102, 102)
            r.font.name = CONFIG["font_english"]

        if pd.get("quote"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.space_before = Pt(8)
            p.space_after = Pt(12)
            qt = pd["quote"].strip('""\u201C\u201D')
            r = p.add_run(f"\u201C{qt}\u201D")
            r.font.name = CONFIG["font_bangla"]
            r.font.size = Pt(CONFIG["font_size_quote"])
            r.italic = True

        if pd.get("body"):
            p = doc.add_paragraph()
            p.space_after = Pt(8)
            r = p.add_run(pd["body"])
            r.font.name = CONFIG["font_bangla"]

        for j, item_text in enumerate(pd.get("items", [])):
            p = doc.add_paragraph()
            p.space_after = Pt(4)
            num = bangla_nums[j] if j < len(bangla_nums) else str(j+1)
            bold_m = re.match(r'\*\*(.+?)\*\*\s*(.*)', item_text, re.DOTALL)
            if bold_m:
                r = p.add_run(f"{num}. {bold_m.group(1)}")
                r.font.name = CONFIG["font_bangla"]
                r.bold = True
                r2 = p.add_run(f" {bold_m.group(2)}")
                r2.font.name = CONFIG["font_bangla"]
            else:
                r = p.add_run(f"{num}. {item_text}")
                r.font.name = CONFIG["font_bangla"]

        if pd.get("closing"):
            p = doc.add_paragraph()
            p.space_before = Pt(8)
            r = p.add_run(pd["closing"])
            r.font.name = CONFIG["font_bangla"]

        if not any([pd.get("heading"), pd.get("body"), pd.get("items"), pd.get("closing")]):
            if pd.get("raw"):
                for pt in pd["raw"].split("\n\n"):
                    pt = pt.strip()
                    if pt:
                        p = doc.add_paragraph()
                        r = p.add_run(pt)
                        r.font.name = CONFIG["font_bangla"]

    # End page
    doc.add_page_break()
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("— সমাপ্ত —")
    r.font.name = CONFIG["font_bangla"]
    r.font.size = Pt(18)
    r.bold = True

    if title:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"মূল বই: {title}")
        r.font.name = CONFIG["font_bangla"]
        r.font.size = Pt(12)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("বাংলা অনুবাদ সম্পন্ন | অদম্য প্রেস")
    r.font.name = CONFIG["font_bangla"]
    r.font.size = Pt(11)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════════════════════════

# Custom CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        border-bottom: 2px solid #e0e0e0;
        margin-bottom: 2rem;
    }
    .main-header h1 {
        color: #1a1a2e;
        font-size: 2rem;
    }
    .main-header p {
        color: #666;
        font-size: 1rem;
    }
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .cost-box {
        background-color: #f0f9f0;
        border: 1px solid #4CAF50;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #fff9e6;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>📚 অদম্য প্রেস — Book Translator</h1>
    <p>English → Reader-Friendly Bangla | Powered by Claude AI</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")

    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        help="Get your key at console.anthropic.com",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
    )

    model = st.selectbox(
        "AI Model",
        options=["claude-sonnet-4-5-20250514", "claude-haiku-4-5-20251001"],
        format_func=lambda x: "Sonnet 4.5 (Best Quality ~$2-5/book)" if "sonnet" in x else "Haiku 4.5 (Budget ~$0.30-1.50/book)",
    )

    batch_size = st.slider("Pages per API call", 3, 10, 5,
                           help="Lower = better quality, more API calls. 5 is recommended.")

    st.divider()
    st.header("📖 Book Details")
    book_title = st.text_input("Book Title", placeholder="e.g. Attitude Is Everything")
    book_author = st.text_input("Author", placeholder="e.g. Harvard-Fiction KH")

    st.divider()
    st.header("📄 Page Range")
    col1, col2 = st.columns(2)
    start_page = col1.number_input("Start Page", min_value=1, value=1)
    end_page_input = col2.number_input("End Page (0 = all)", min_value=0, value=0)

    st.divider()
    st.markdown("**💡 Tips:**")
    st.markdown("- Sonnet gives best quality for publishing")
    st.markdown("- Haiku is good for drafts & previews")
    st.markdown("- Batch size 3-5 gives best results")
    st.markdown("- You can translate specific page ranges")

# Main area
uploaded_file = st.file_uploader(
    "📂 Upload English PDF Book",
    type=["pdf"],
    help="Upload the English book in PDF format"
)

if uploaded_file:
    pdf_bytes = uploaded_file.read()

    # Extract and show info
    pages, total_pages = extract_pages_from_bytes(pdf_bytes, 1, None)
    end_page = end_page_input if end_page_input > 0 else total_pages

    # Filter pages by range
    pages_in_range = [(pn, txt) for pn, txt in pages if start_page <= pn <= end_page]
    num_pages = len(pages_in_range)
    num_batches = (num_pages + batch_size - 1) // batch_size

    # Cost estimate
    if "haiku" in model:
        est_cost = (num_pages * 800 * 0.0008 + num_pages * 600 * 0.004) / 1000
    else:
        est_cost = (num_pages * 800 * 0.003 + num_pages * 600 * 0.015) / 1000

    # Info display
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Total Pages", total_pages)
    col2.metric("📑 Pages to Translate", num_pages)
    col3.metric("📦 API Batches", num_batches)
    col4.metric("💰 Est. Cost", f"${est_cost:.2f}")

    st.markdown(f"""
    <div class="cost-box">
        <strong>📊 Translation Summary:</strong> {num_pages} pages (Page {start_page}→{end_page}) in {num_batches} batches
        using <strong>{'Sonnet 4.5' if 'sonnet' in model else 'Haiku 4.5'}</strong> ≈ <strong>${est_cost:.2f} USD</strong>
    </div>
    """, unsafe_allow_html=True)

    # Translate button
    if st.button("🚀 Start Translation", type="primary", use_container_width=True):
        if not api_key:
            st.error("❌ Please enter your Anthropic API Key in the sidebar.")
        else:
            try:
                client = anthropic.Anthropic(api_key=api_key)

                progress_bar = st.progress(0)
                status_text = st.empty()
                log_area = st.empty()

                all_translated = []
                total_cost = 0.0
                total_input_tokens = 0
                total_output_tokens = 0
                logs = []

                for batch_idx in range(num_batches):
                    b_start = batch_idx * batch_size
                    b_end = min(b_start + batch_size, num_pages)
                    batch_pages = pages_in_range[b_start:b_end]
                    page_nums = [p[0] for p in batch_pages]

                    progress = (batch_idx + 1) / num_batches
                    progress_bar.progress(progress)
                    status_text.markdown(f"**🔄 Translating Batch {batch_idx+1}/{num_batches}** — Pages {page_nums[0]}-{page_nums[-1]}...")

                    try:
                        raw, in_t, out_t, cost = translate_batch(client, model, batch_pages)
                        parsed = parse_translation(raw)
                        all_translated.extend(parsed)

                        total_cost += cost
                        total_input_tokens += in_t
                        total_output_tokens += out_t

                        logs.append(f"✅ Batch {batch_idx+1}: Pages {page_nums[0]}-{page_nums[-1]} — {len(parsed)} pages — ${cost:.4f}")
                        log_area.code("\n".join(logs))

                    except Exception as e:
                        logs.append(f"❌ Batch {batch_idx+1}: Error — {str(e)}")
                        log_area.code("\n".join(logs))
                        st.warning(f"Batch {batch_idx+1} failed: {e}. Continuing...")

                    # Rate limit delay
                    if batch_idx < num_batches - 1:
                        time.sleep(1)

                progress_bar.progress(1.0)
                status_text.markdown("**✅ Translation Complete!**")

                # Build DOCX
                if all_translated:
                    status_text.markdown("**📄 Building DOCX document...**")
                    docx_buffer = build_docx(all_translated, book_title, book_author)

                    # Success summary
                    st.success(f"""
                    🎉 **Translation Complete!**
                    - Pages translated: {len(all_translated)}
                    - Total cost: ${total_cost:.4f} USD
                    - Tokens: {total_input_tokens:,} input / {total_output_tokens:,} output
                    """)

                    # Download button
                    filename = f"{book_title or uploaded_file.name.replace('.pdf','')}_Bangla.docx"
                    st.download_button(
                        label="📥 Download Bangla DOCX",
                        data=docx_buffer,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary",
                        use_container_width=True,
                    )
                else:
                    st.error("No pages were translated successfully.")

            except anthropic.AuthenticationError:
                st.error("❌ Invalid API key. Please check your Anthropic API key.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

else:
    # Welcome state
    st.markdown("""
    ### 👋 How to Use

    1. **Enter your API Key** in the sidebar (get one at [console.anthropic.com](https://console.anthropic.com))
    2. **Upload** your English PDF book above
    3. **Set** book title, author, and page range in the sidebar
    4. **Click** "Start Translation" and wait
    5. **Download** the translated Bangla DOCX

    ---

    ### 💰 Cost Guide

    | Model | Quality | Cost per 100 pages |
    |-------|---------|-------------------|
    | Sonnet 4.5 | ★★★★★ Best | ~$2-5 |
    | Haiku 4.5 | ★★★★ Good | ~$0.30-1.50 |

    ---

    *Built for অদম্য প্রেস (Odommo Press) | Online Tech Academy*
    """)

# Footer
st.divider()
st.markdown(
    "<p style='text-align:center; color:#999; font-size:0.8rem;'>"
    "অদম্য প্রেস Book Translator v1.0 | Powered by Claude AI | Online Tech Academy</p>",
    unsafe_allow_html=True
)
