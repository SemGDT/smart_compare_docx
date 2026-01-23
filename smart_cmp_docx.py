import streamlit as st
from docx import Document
import difflib
import re

def get_text_file(file):
    """Read a text file and return list of paragraphs (non-empty lines)"""
    content = file.read().decode('utf-8')
    lines = content.split('\n')
    return [line.strip() for line in lines if line.strip() != ""]

def normalize_text(text):
    """
    Normalize text for storage (not just comparison).
    Replace hyphens with spaces, normalize whitespace.
    """
    if not text: return ""
    # Replace hyphens with spaces
    text = text.replace('-', ' ')
    # Normalize multiple spaces to single space
    text = ' '.join(text.split())
    return text

def flatten_poem_lines(paragraphs, window_size=4):
    """
    Detect and flatten poem sections (short lines that should be grouped).
    If we see multiple consecutive short paragraphs (< 50 chars), combine them.
    """
    result = []
    i = 0
    while i < len(paragraphs):
        para = paragraphs[i]
        
        # Check if this looks like a poem line (short paragraph)
        if len(para) < 50:
            # Look ahead to see if next few are also short (poem continues)
            poem_lines = [para]
            j = i + 1
            while j < len(paragraphs) and len(paragraphs[j]) < 50 and j < i + 20:
                poem_lines.append(paragraphs[j])
                j += 1
            
            # If we found multiple short lines, it's probably a poem - flatten it
            if len(poem_lines) >= window_size:
                flattened = ' '.join(poem_lines)
                result.append(flattened)
                i = j
            else:
                # Not enough short lines, treat as normal paragraph
                result.append(para)
                i += 1
        else:
            # Normal paragraph
            result.append(para)
            i += 1
    
    return result

def simplify(text):
    """
    Normalizes text for comparison logic only.
    Removes hyphens, spaces, punctuation, markers like (1), and ignores case.
    """
    if not text: return ""
    text = re.sub(r'\(\d+\)', '', text)  # Remove (1), (2)
    text = text.replace('-', ' ')
    text = re.sub(r'[.,;:!?\u3002\uff0c\u3001]', '', text) # Remove punctuation
    return text

def highlight_real_changes(text_a, text_b):
    """
    Compares word blocks. If the characters match (ignoring hyphens/case), 
    it displays as plain text. Otherwise, highlights the difference.
    """
    words_a = text_a.split()
    words_b = text_b.split()
    
    matcher = difflib.SequenceMatcher(None, 
                                     [simplify(w) for w in words_a], 
                                     [simplify(w) for w in words_b],
                                     autojunk=False)
    display_a, display_b = [], []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        block_a = " ".join(words_a[i1:i2])
        block_b = " ".join(words_b[j1:j2])
        
        if tag == 'equal' or simplify(block_a) == simplify(block_b):
            display_a.append(block_a)
            display_b.append(block_b)
        else:
            if block_a:
                display_a.append(f"<span style='background-color:#ffcccc;'>{block_a}</span>")
            if block_b:
                display_b.append(f"<span style='background-color:#ccffcc; color:black; font-weight:bold;'>{block_b}</span>")
            
    return " ".join(display_a), " ".join(display_b)

st.set_page_config(page_title="Deep-Sync Comparison", layout="wide")
st.title("Document Comparison (Typo & Offset Resilient)")

with st.sidebar:
    f_orig = st.file_uploader("Original Document", type=["txt", "docx"])
    f_rev = st.file_uploader("Revised Document", type=["txt", "docx"])
    anchor = st.text_input("Anchor Point", "Như vậy tôi nghe")
    context_lines = st.number_input("Context paragraphs", min_value=0, max_value=50, value=3)

if f_orig and f_rev:
    # Detect file type and read accordingly
    if f_orig.name.endswith('.txt'):
        raw_a = get_text_file(f_orig)
    else:
        doc = Document(f_orig)
        raw_a = [p.text.strip() for p in doc.paragraphs if p.text.strip() != ""]
    
    if f_rev.name.endswith('.txt'):
        raw_b = get_text_file(f_rev)
    else:
        doc = Document(f_rev)
        raw_b = [p.text.strip() for p in doc.paragraphs if p.text.strip() != ""]
    
    # ONLY replace hyphens with spaces - preserve everything else
    raw_a = [p.replace('-', ' ') for p in raw_a]
    raw_b = [p.replace('-', ' ') for p in raw_b]
    
    # Flatten poem sections (combine short consecutive lines)
    raw_a = flatten_poem_lines(raw_a)
    raw_b = flatten_poem_lines(raw_b)

    # Initial Anchor Alignment
    idx_a = next((i for i, x in enumerate(raw_a) if simplify(anchor) in simplify(x)), 0)
    idx_b = next((i for i, x in enumerate(raw_b) if simplify(anchor) in simplify(x)), 0)
    
    text_a, text_b = raw_a[idx_a:], raw_b[idx_b:]

    # GLOBAL SYNC LOGIC
    real_diffs = []
    global_matcher = difflib.SequenceMatcher(None, 
                                            [simplify(t) for t in text_a], 
                                            [simplify(t) for t in text_b], 
                                            autojunk=False)
    
    for tag, i1, i2, j1, j2 in global_matcher.get_opcodes():
        if tag != 'equal':
            if simplify(" ".join(text_a[i1:i2])) != simplify(" ".join(text_b[j1:j2])):
                real_diffs.append((i1, i2, j1, j2))

    if "last_anchor" not in st.session_state:
        st.session_state.last_anchor = anchor
    if st.session_state.last_anchor != anchor:
        st.session_state.nav = 0
        st.session_state.last_anchor = anchor

    if not real_diffs:
        st.success("Documents are fully synchronized. No content differences found!")
    else:
        if "nav" not in st.session_state: st.session_state.nav = 0
        st.session_state.nav = min(st.session_state.nav, len(real_diffs) - 1)

        # Navigation
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️ Previous"): st.session_state.nav = max(0, st.session_state.nav - 1)
        with c2:
            st.markdown(f"<p style='text-align:center'>Real Difference <b>{st.session_state.nav + 1}</b> of {len(real_diffs)}</p>", unsafe_allow_html=True)
        with c3:
            if st.button("Next ➡️"): st.session_state.nav = min(len(real_diffs)-1, st.session_state.nav + 1)

        # Show Results
        i1, i2, j1, j2 = real_diffs[st.session_state.nav]
        
        para_a = "\n\n".join(text_a[i1:i2]) if i1 != i2 else "[Empty]"
        para_b = "\n\n".join(text_b[j1:j2]) if j1 != j2 else "[Empty]"
        
        high_a, high_b = highlight_real_changes(para_a, para_b)

        # Add context
        context_a = text_a[i2:min(i2 + context_lines, len(text_a))]
        context_b = text_b[j2:min(j2 + context_lines, len(text_b))]
        
        if context_a or context_b:
            high_a += "<br><br><div style='border-top:1px dashed #ccc; margin:15px 0; padding-top:15px;'>"
            high_b += "<br><br><div style='border-top:1px dashed #ccc; margin:15px 0; padding-top:15px;'>"
            
            if context_a:
                high_a += "<br><br>".join(context_a)
            if context_b:
                high_b += "<br><br>".join(context_b)
            
            high_a += "</div>"
            high_b += "</div>"

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Original")
            st.markdown(f"<div style='border:1px solid #ddd; padding:20px; font-size:18px; min-height:300px;'>{high_a}</div>", unsafe_allow_html=True)
        with col2:
            st.subheader("Revised")
            st.markdown(f"<div style='border:1px solid #ddd; padding:20px; font-size:18px; min-height:300px;'>{high_b}</div>", unsafe_allow_html=True)
