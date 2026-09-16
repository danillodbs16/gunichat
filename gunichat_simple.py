import streamlit as st
import subprocess
import time

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(
    page_title="GUNI",
    layout="wide"
)

# -------------------------
# SESSION STATE
# -------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "history" not in st.session_state:
    st.session_state.history = []

if "rerun_query" not in st.session_state:
    st.session_state.rerun_query = None

# -------------------------
# STYLES
# -------------------------
st.markdown("""
<style>

.subtitle {
    text-align: center;
    font-size: 1.2rem;
    color: #666;
    margin-top: 0;
    margin-bottom: 1.5rem;
}

[data-testid="stChatMessage"] {
    max-width: 100%;
}

section[data-testid="stSidebar"] button {
    width: 100%;
    text-align: left;
}

/* filter chip style */
.chip {
    display: inline-block;
    background: #ff7a00;
    color: white;
    padding: 5px 12px;
    border-radius: 20px;
    margin-right: 6px;
    margin-bottom: 6px;
    font-size: 0.85rem;
}

</style>
""", unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------
c1, c2, c3 = st.columns([4, 4, 4])

with c2:
    st.image("guni.png", use_container_width=True)

st.markdown(
    '<div class="subtitle">Tu guía familiar para encontrar planes cómodos en Euskadi hoy</div>',
    unsafe_allow_html=True
)

# -------------------------
# SIDEBAR HISTORY
# -------------------------
with st.sidebar:

    st.title("Historial")

    for i, q in enumerate(reversed(st.session_state.history)):
        if st.button(q, key=f"hist_{i}"):
            st.session_state.rerun_query = q
            st.rerun()

# -------------------------
# CHAT HISTORY
# -------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------
# QUERY FUNCTION
# -------------------------
def run_query(query, display_question):

    st.session_state.messages.append({
        "role": "user",
        "content": display_question
    })

    st.session_state.history.append(query)

    with st.chat_message("user"):
        st.markdown(display_question)

    result = subprocess.run(
        ["python3", "API_LLM_v3.py", query],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        st.error(result.stderr)
        return

    answer = result.stdout.strip()

    with st.chat_message("assistant"):
        placeholder = st.empty()
        current = ""

        for char in answer:
            current += char
            placeholder.markdown(current + "▌")
            time.sleep(0.001)

        placeholder.markdown(current)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

# -------------------------
# FILTERS
# -------------------------
st.markdown("### Filtros rápidos")

filters = {
    "Gratis": "gratis",
    "Bilbao": "Bilbao",
    "Donosti": "Donosti",
    "Sin lluvia": "sin lluvia",
    "Por la noche": "por la noche",
    "Por la tarde": "por la tarde",
}

cols = st.columns(len(filters))

selected_filters = []

for col, (label, value) in zip(cols, filters.items()):
    with col:
        if st.toggle(label, key=f"filter_{value}"):
            selected_filters.append(value)

# -------------------------
# SHOW APPLIED FILTERS (IMPROVED)
# -------------------------
if selected_filters:

    st.markdown("**Filtros aplicados:**")

    chip_html = ""
    for f in selected_filters:
        chip_html += f'<span class="chip">{f}</span>'

    st.markdown(chip_html, unsafe_allow_html=True)

# -------------------------
# APPLY FILTERS
# -------------------------
if st.button(
    "Aplicar filtros",
    type="primary",
    use_container_width=True
):

    query = " ".join(selected_filters)

    if not query:
        query = "sorprendeme"

    display_text = (
        " | ".join(selected_filters)
        if selected_filters
        else "Sorpréndeme"
    )

    run_query(query, display_text)

# -------------------------
# CHAT INPUT
# -------------------------
question = st.chat_input("¿Qué plan estás buscando?")

if question:

    query = question

    if selected_filters:
        query += " " + " ".join(selected_filters)

    run_query(query, question)

# -------------------------
# HISTORY RE-RUN
# -------------------------
if st.session_state.rerun_query:

    q = st.session_state.rerun_query

    st.session_state.rerun_query = None

    run_query(q, q)
