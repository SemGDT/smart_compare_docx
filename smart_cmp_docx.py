import streamlit as st
from docx import Document
import difflib
import re

# ─────────────────────────────────────────────
# FILE READING
# ─────────────────────────────────────────────

def get_text_file(file):
    content = file.read().decode('utf-8')
    lines = content.split('\n')
    return [line.strip() for line in lines if line.strip()]

# ─────────────────────────────────────────────
# TEXT NORMALIZATION
# ─────────────────────────────────────────────

def flatten_poem_lines(paragraphs, window_size=4):
    result = []
    i = 0
    while i < len(paragraphs):
        para = paragraphs[i]
        if len(para) < 50:
            poem_lines = [para]
            j = i + 1
            while j < len(paragraphs) and len(paragraphs[j]) < 50 and j < i + 20:
                poem_lines.append(paragraphs[j])
                j += 1
            if len(poem_lines) >= window_size:
                result.append(' '.join(poem_lines))
                i = j
            else:
                result.append(para)
                i += 1
        else:
            result.append(para)
            i += 1
    return result

def simplify(text):
    """Normalize for comparison only: remove punctuation, hyphens, markers, lowercase."""
    if not text: return ""
    text = re.sub(r'\(\d+\)', '', text)
    text = text.replace('-', ' ')
    text = re.sub(r'[.,;:!?\u3002\uff0c\u3001]', '', text)
    text = text.lower()
    return ' '.join(text.split())

# ─────────────────────────────────────────────
# SENTENCE SPLITTING
# The key insight: diff at SENTENCE level, not paragraph level.
# Paragraphs are just display containers — sentences are the real units of meaning.
# SequenceMatcher works reliably when each token is a sentence,
# because sentences are long enough to be uniquely identifiable,
# and short enough that boundary shifts don't hide matches.
# ─────────────────────────────────────────────

def split_into_sentences(paragraphs):
    """
    Split paragraphs into individual sentences.
    Returns list of (sentence_text, para_idx) so we can restore
    paragraph breaks in the display.
    """
    result = []
    for para_idx, para in enumerate(paragraphs):
        # Split at sentence-ending punctuation followed by whitespace
        parts = re.split(r'(?<=[.;!?])\s+', para.strip())
        for part in parts:
            part = part.strip()
            if part:
                result.append((part, para_idx))
    return result

# ─────────────────────────────────────────────
# DIFF AT SENTENCE LEVEL
# ─────────────────────────────────────────────

def build_diffs(sentences_a, sentences_b):
    """
    Diff two sentence lists. Each sentence is (text, para_idx).
    Returns list of diff blocks, each being a contiguous non-equal region:
      { 'sents_a': [(text, para_idx), ...],
        'sents_b': [(text, para_idx), ...],
        'context_a': [...],   # sentences after the block from side A
        'context_b': [...] }
    """
    keys_a = [simplify(s) for s, _ in sentences_a]
    keys_b = [simplify(s) for s, _ in sentences_b]

    matcher = difflib.SequenceMatcher(None, keys_a, keys_b, autojunk=False)
    diffs = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        block_a = sentences_a[i1:i2]
        block_b = sentences_b[j1:j2]
        # Skip if simplified content is identical (punctuation/case-only)
        if simplify(' '.join(s for s, _ in block_a)) == simplify(' '.join(s for s, _ in block_b)):
            continue
        diffs.append({
            'sents_a': block_a,
            'sents_b': block_b,
            'end_a': i2,
            'end_b': j2,
        })

    return diffs

# ─────────────────────────────────────────────
# WORD-LEVEL HIGHLIGHT within a sentence pair
# ─────────────────────────────────────────────

def highlight_words(text_a, text_b):
    """Word-level diff highlight between two text blocks."""
    words_a = text_a.split()
    words_b = text_b.split()
    matcher = difflib.SequenceMatcher(None,
                                      [simplify(w) for w in words_a],
                                      [simplify(w) for w in words_b],
                                      autojunk=False)
    out_a, out_b = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        wa = ' '.join(words_a[i1:i2])
        wb = ' '.join(words_b[j1:j2])
        if tag == 'equal' or simplify(wa) == simplify(wb):
            out_a.append(wa)
            out_b.append(wb)
        else:
            if wa:
                out_a.append(f"<span style='background-color:#ffcccc;'>{wa}</span>")
            if wb:
                out_b.append(f"<span style='background-color:#ccffcc; color:black; font-weight:bold;'>{wb}</span>")
    return ' '.join(out_a), ' '.join(out_b)

# ─────────────────────────────────────────────
# RENDERING
# ─────────────────────────────────────────────

def render_sentence_list(sentences, highlight_map=None):
    """
    Render a list of (text, para_idx) sentences as HTML,
    inserting paragraph breaks on para_idx changes.
    highlight_map: dict of sentence_idx -> highlighted_html (overrides plain text).
    """
    html = []
    last_para = None
    for idx, (text, para_idx) in enumerate(sentences):
        if last_para is not None and para_idx != last_para:
            html.append('<br><br>')
        last_para = para_idx
        if highlight_map and idx in highlight_map:
            html.append(highlight_map[idx] + ' ')
        else:
            html.append(text + ' ')
    return ''.join(html)

def render_diff(diff, sentences_a, sentences_b, context_lines):
    """
    Render one diff block with word-level highlights.
    Sentences within the block are matched pairwise where possible,
    with inserts/deletes shown on one side only.
    """
    sents_a = diff['sents_a']
    sents_b = diff['sents_b']

    # Match sentences pairwise using another SequenceMatcher pass
    keys_a = [simplify(s) for s, _ in sents_a]
    keys_b = [simplify(s) for s, _ in sents_b]
    inner = difflib.SequenceMatcher(None, keys_a, keys_b, autojunk=False)

    html_a_parts, html_b_parts = [], []
    last_para_a, last_para_b = None, None

    def add_break_a(para_idx):
        nonlocal last_para_a
        if last_para_a is not None and para_idx != last_para_a:
            html_a_parts.append('<br><br>')
        last_para_a = para_idx

    def add_break_b(para_idx):
        nonlocal last_para_b
        if last_para_b is not None and para_idx != last_para_b:
            html_b_parts.append('<br><br>')
        last_para_b = para_idx

    for tag, i1, i2, j1, j2 in inner.get_opcodes():
        if tag == 'equal':
            for text, pi in sents_a[i1:i2]:
                add_break_a(pi)
                html_a_parts.append(text + ' ')
            for text, pi in sents_b[j1:j2]:
                add_break_b(pi)
                html_b_parts.append(text + ' ')

        elif tag == 'replace':
            # Pair up sentences and do word-level diff on each pair
            block_a = sents_a[i1:i2]
            block_b = sents_b[j1:j2]
            # Join each side and do one word-level diff across the whole replace block
            joined_a = ' '.join(s for s, _ in block_a)
            joined_b = ' '.join(s for s, _ in block_b)
            hl_a, hl_b = highlight_words(joined_a, joined_b)
            # Emit on side A using first sentence's para_idx for break logic
            if block_a:
                add_break_a(block_a[0][1])
            html_a_parts.append(hl_a + ' ')
            if block_b:
                add_break_b(block_b[0][1])
            html_b_parts.append(hl_b + ' ')

        elif tag == 'delete':
            for text, pi in sents_a[i1:i2]:
                add_break_a(pi)
                html_a_parts.append(
                    f"<span style='background-color:#ffcccc;'>{text}</span> "
                )

        elif tag == 'insert':
            for text, pi in sents_b[j1:j2]:
                add_break_b(pi)
                html_b_parts.append(
                    f"<span style='background-color:#ccffcc; color:black; font-weight:bold;'>{text}</span> "
                )

    high_a = ''.join(html_a_parts)
    high_b = ''.join(html_b_parts)

    # Context sentences after this diff block
    end_a, end_b = diff['end_a'], diff['end_b']
    ctx_a = sentences_a[end_a:end_a + context_lines]
    ctx_b = sentences_b[end_b:end_b + context_lines]

    if ctx_a or ctx_b:
        sep = "<br><br><div style='border-top:1px dashed #ccc; margin:15px 0; padding-top:15px; color:#999;'>"
        high_a += sep + render_sentence_list(ctx_a) + "</div>"
        high_b += sep + render_sentence_list(ctx_b) + "</div>"

    return high_a, high_b

# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────

st.set_page_config(page_title="Deep-Sync Comparison", layout="wide")
st.title("Document Comparison (Typo & Offset Resilient)")

with st.sidebar:
    f_orig = st.file_uploader("Original Document", type=["txt", "docx"])
    f_rev  = st.file_uploader("Revised Document",  type=["txt", "docx"])
    anchor = st.text_input("Anchor Point", "Như vậy tôi nghe")
    context_lines = st.number_input("Context sentences", min_value=0, max_value=50, value=5)

if f_orig and f_rev:
    # ── Read ──
    if f_orig.name.endswith('.txt'):
        raw_a = get_text_file(f_orig)
    else:
        raw_a = [p.text.strip() for p in Document(f_orig).paragraphs if p.text.strip()]

    if f_rev.name.endswith('.txt'):
        raw_b = get_text_file(f_rev)
    else:
        raw_b = [p.text.strip() for p in Document(f_rev).paragraphs if p.text.strip()]

    # ── Normalize hyphens in display text ──
    raw_a = [p.replace('-', ' ') for p in raw_a]
    raw_b = [p.replace('-', ' ') for p in raw_b]

    # ── Flatten poem lines ──
    raw_a = flatten_poem_lines(raw_a)
    raw_b = flatten_poem_lines(raw_b)

    # ── Anchor alignment ──
    idx_a = next((i for i, x in enumerate(raw_a) if simplify(anchor) in simplify(x)), 0)
    idx_b = next((i for i, x in enumerate(raw_b) if simplify(anchor) in simplify(x)), 0)
    text_a = raw_a[idx_a:]
    text_b = raw_b[idx_b:]

    # ── Split into sentences ──
    sentences_a = split_into_sentences(text_a)
    sentences_b = split_into_sentences(text_b)

    # ── Session state ──
    if "last_anchor" not in st.session_state:
        st.session_state.last_anchor = anchor
    if st.session_state.last_anchor != anchor:
        st.session_state.nav = 0
        st.session_state.last_anchor = anchor
    if "nav" not in st.session_state:
        st.session_state.nav = 0

    # ── Build diffs ──
    diffs = build_diffs(sentences_a, sentences_b)

    if not diffs:
        st.success("Documents are fully synchronized. No content differences found!")
    else:
        st.session_state.nav = min(st.session_state.nav, len(diffs) - 1)

        # Navigation
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("Previous"):
                st.session_state.nav = max(0, st.session_state.nav - 1)
        with c2:
            st.markdown(
                f"<p style='text-align:center'>Difference "
                f"<b>{st.session_state.nav + 1}</b> of <b>{len(diffs)}</b></p>",
                unsafe_allow_html=True
            )
        with c3:
            if st.button("Next"):
                st.session_state.nav = min(len(diffs) - 1, st.session_state.nav + 1)

        high_a, high_b = render_diff(
            diffs[st.session_state.nav], sentences_a, sentences_b, context_lines
        )

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Original")
            st.markdown(
                f"<div style='border:1px solid #ddd; padding:20px; "
                f"font-size:18px; min-height:300px; line-height:1.9;'>{high_a}</div>",
                unsafe_allow_html=True
            )
        with col2:
            st.subheader("Revised")
            st.markdown(
                f"<div style='border:1px solid #ddd; padding:20px; "
                f"font-size:18px; min-height:300px; line-height:1.9;'>{high_b}</div>",
                unsafe_allow_html=True
            )