import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import base64
import os

# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================

st.set_page_config(
    page_title="BJJ Performance Profile",
    page_icon="🥋",
    layout="centered"
)

# =====================================================
# CONEXÃO GOOGLE SHEETS (Cloud Ready)
# =====================================================

@st.cache_resource
def connect_google_sheets():
    try:
        gc = gspread.service_account_from_dict(
            st.secrets["gcp_service_account"]
        )
        return gc.open("bjj_app_database")
    except Exception as e:
        st.error("Erro ao conectar com Google Sheets.")
        st.stop()

# =====================================================
# FUNÇÃO ADICIONAR ATLETA
# =====================================================

def add_athlete(nome, sobrenome, faixa, tempo):
    sheet = connect_google_sheets()
    worksheet = sheet.worksheet("athletes")

    # Gerar ID incremental
    records = worksheet.get_all_records()
    athlete_id = len(records) + 1

    worksheet.append_row([
        athlete_id,
        nome,
        sobrenome,
        faixa,
        tempo,
        datetime.now().strftime("%Y-%m-%d")
    ])

# =====================================================
# FUNDO PERSONALIZADO (OPCIONAL)
# =====================================================

def set_background(image_file):
    if os.path.exists(image_file):
        with open(image_file, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()

        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url("data:image/jpg;base64,{encoded}");
                background-size: cover;
                background-position: center;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

# =====================================================
# INTERFACE
# =====================================================

set_background("kimono.jpg")  # opcional

st.title("🥋 BJJ Performance Profile")
st.subheader("Cadastro Inicial do Atleta")

with st.form("cadastro_form"):

    nome = st.text_input("Nome")
    sobrenome = st.text_input("Sobrenome")

    faixa = st.selectbox(
        "Faixa",
        ["Branca", "Azul", "Roxa", "Marrom", "Preta"]
    )

    tempo = st.number_input(
        "Tempo de treino (meses)",
        min_value=0,
        step=1
    )

    submitted = st.form_submit_button("Cadastrar")

    if submitted:

        if nome and sobrenome:
            add_athlete(nome, sobrenome, faixa, tempo)
            st.success("✅ Atleta cadastrado com sucesso!")
        else:
            st.warning("Preencha nome e sobrenome.")
