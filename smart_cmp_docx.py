import streamlit as st
from docx import Document
import difflib

def get_docx_text(file):
    doc = Document(file)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip() != ""]

def clean_strictly(text):
    """Normalize text by removing hyphens and extra spaces, and lowering case."""
    if not text: return ""
    return text.replace('-', '').replace(' ', '').lower()

def highlight_only_real_changes(text_a, text_b):
    words_a = text_a.split()
    words_b = text_b.split()
    
    # Compare based on character-only 'skeletons'
    matcher = difflib.SequenceMatcher(None, 
                                     [clean_strictly(w) for w in words_a], 
                                     [clean_strictly(w) for w in words_b])
    display_a = []
    display_b = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        word_block_a = " ".join(words_a[i1:i2])
        word_block_b = " ".join(words_b[j1:j2])
        
        # If the blocks are 'equal' OR if they match after cleaning, NO COLOR
        if tag == 'equal' or clean_strictly(word_block_a) == clean_strictly(word_block_b):
            display_a.append(word_block_a)
            display_b.append(word_block_b)
        else:
            # ONLY color if the actual letters changed (e.g., 'c hâu' vs 'châu')
            display_a.append(f"<span style='color:#777; background-color:#ffcccc;'>{word_block_a}</span>")
            display_b.append(f"<span style='color:black; background-color:#ccffcc; font-weight:bold;'>{word_block_b}</span>")
            
    return " ".join(display_a), " ".join(display_b)

st.set_page_config(page_title="Text Aligner", layout="wide")
st.title("Document Comparison (True Content Only)")

with st.sidebar:
    file_orig = st.file_uploader("Original Document", type="docx")
    file_rev = st.file_uploader("Revised Document", type="docx")
    anchor = st.text_input("Anchor String", "Như vậy tôi nghe")

if file_orig and file_rev:
    raw_a = get_docx_text(file_orig)
    raw_b = get_docx_text(file_rev)

    # Find Anchor index (Case/Hyphen insensitive)
    idx_a = next((i for i, x in enumerate(raw_a) if clean_strictly(anchor) in clean_strictly(x)), 0)
    idx_b = next((i for i, x in enumerate(raw_b) if clean_strictly(anchor) in clean_strictly(x)), 0)
    
    text_a, text_b = raw_a[idx_a:], raw_b[idx_b:]

    # Filter for paragraphs that have REAL character differences
    diff_indices = []
    matcher = difflib.SequenceMatcher(None, 
                                     [clean_strictly(t) for t in text_a], 
                                     [clean_strictly(t) for t in text_b])
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != 'equal':
            # Check if the text is different even after cleaning
            if clean_strictly("".join(text_a[i1:i2])) != clean_strictly("".join(text_b[j1:j2])):
                diff_indices.append((i1, i2, j1, j2))

    if not diff_indices:
        st.success("No meaningful character differences found!")
    else:
        if "nav" not in st.session_state: st.session_state.nav = 0
        st.session_state.nav = min(st.session_state.nav, len(diff_indices) - 1)

        # Navigation
        col_prev, col_cnt, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("⬅️ Previous"): st.session_state.nav = max(0, st.session_state.nav - 1)
        with col_cnt:
            st.markdown(f"<h3 style='text-align:center'>Real Difference {st.session_state.nav + 1} of {len(diff_indices)}</h3>", unsafe_allow_html=True)
        with col_next:
            if st.button("Next ➡️"): st.session_state.nav = min(len(diff_indices)-1, st.session_state.nav + 1)

        # Display
        i1, i2, j1, j2 = diff_indices[st.session_state.nav]
        high_a, high_b = highlight_only_real_changes("\n".join(text_a[i1:i2]), "\n".join(text_b[j1:j2]))

        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown(f"<div style='border:1px solid #ddd; padding:20px; font-size:18px;'>{high_a}</div>", unsafe_allow_html=True)
        with c_right:
            st.markdown(f"<div style='border:1px solid #ddd; padding:20px; font-size:18px;'>{high_b}</div>", unsafe_allow_html=True)