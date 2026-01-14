import streamlit as st
from docx import Document
import difflib
import re

def get_docx_text(file):
    doc = Document(file)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip() != ""]

def simplify(text):
    """
    Normalizes text for comparison logic only.
    Removes hyphens, spaces, punctuation, markers like (1), and ignores case.
    """
    if not text: return ""
    text = re.sub(r'\(\d+\)', '', text)  # Remove (1), (2)
    text = text.replace('-', '').replace(' ', '')
    text = re.sub(r'[.,;:!?\u3002\uff0c\u3001]', '', text) # Remove punctuation
    return text.lower()

def highlight_real_changes(text_a, text_b):
    """
    Compares word blocks. If the characters match (ignoring hyphens/case), 
    it displays as plain text. Otherwise, highlights the difference.
    """
    words_a = text_a.split()
    words_b = text_b.split()
    
    # SequenceMatcher handles the 'extra' or 'missing' word shifts within the paragraph
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
            # Highlight missing (red) or extra/changed (green) words
            if block_a:
                display_a.append(f"<span style='color:#999; text-decoration:line-through; background-color:#ffcccc;'>{block_a}</span>")
            if block_b:
                display_b.append(f"<span style='background-color:#ccffcc; color:black; font-weight:bold;'>{block_b}</span>")
            
    return " ".join(display_a), " ".join(display_b)

st.set_page_config(page_title="Deep-Sync Comparison", layout="wide")
st.title("Document Comparison (Typo & Offset Resilient)")

with st.sidebar:
    f_orig = st.file_uploader("Original Document", type="docx")
    f_rev = st.file_uploader("Revised Document", type="docx")
    anchor = st.text_input("Anchor Point", "Như vậy tôi nghe")

if f_orig and f_rev:
    raw_a, raw_b = get_docx_text(f_orig), get_docx_text(f_rev)

    # Initial Anchor Alignment
    idx_a = next((i for i, x in enumerate(raw_a) if simplify(anchor) in simplify(x)), 0)
    idx_b = next((i for i, x in enumerate(raw_b) if simplify(anchor) in simplify(x)), 0)
    
    text_a, text_b = raw_a[idx_a:], raw_b[idx_b:]

    # GLOBAL SYNC LOGIC: 
    # This aligns the documents paragraph-by-paragraph globally.
    # It identifies where blocks match and where 'inserts' or 'deletes' occurred.
    real_diffs = []
    global_matcher = difflib.SequenceMatcher(None, 
                                            [simplify(t) for t in text_a], 
                                            [simplify(t) for t in text_b], 
                                            autojunk=False)
    
    for tag, i1, i2, j1, j2 in global_matcher.get_opcodes():
        if tag != 'equal':
            # Check if it's a real content difference
            if simplify("".join(text_a[i1:i2])) != simplify("".join(text_b[j1:j2])):
                real_diffs.append((i1, i2, j1, j2))

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
        
        # Display the specific range of paragraphs identified as a 'difference unit'
        para_a = "\n\n".join(text_a[i1:i2]) if i1 != i2 else "[Empty / Missing Paragraph]"
        para_b = "\n\n".join(text_b[j1:j2]) if j1 != j2 else "[Empty / Missing Paragraph]"
        
        high_a, high_b = highlight_real_changes(para_a, para_b)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Original")
            st.markdown(f"<div style='border:1px solid #ddd; padding:20px; font-size:18px; min-height:300px;'>{high_a}</div>", unsafe_allow_html=True)
        with col2:
            st.subheader("Revised")
            st.markdown(f"<div style='border:1px solid #ddd; padding:20px; font-size:18px; min-height:300px;'>{high_b}</div>", unsafe_allow_html=True)