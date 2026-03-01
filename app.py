import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
from sklearn.decomposition import PCA
import numpy as np
import base64
import os

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="BJJ Performance Profile",
    page_icon="🥋",
    layout="centered"
)

# =====================================================
# CONEXÃO GOOGLE
# =====================================================

@st.cache_resource
def connect_google_sheets():
    gc = gspread.service_account_from_dict(
        st.secrets["gcp_service_account"]
    )
    return gc.open("bjj_app_database")

# =====================================================
# BANCO
# =====================================================

def get_athletes():
    sheet = connect_google_sheets()
    return pd.DataFrame(sheet.worksheet("athletes").get_all_records())

def add_athlete(nome, sobrenome, faixa, tempo):
    sheet = connect_google_sheets()
    ws = sheet.worksheet("athletes")
    records = ws.get_all_records()
    athlete_id = len(records) + 1

    ws.append_row([
        athlete_id,
        nome,
        sobrenome,
        faixa,
        tempo,
        datetime.now().strftime("%Y-%m-%d")
    ])

def save_questionnaire(data_row):
    sheet = connect_google_sheets()
    ws = sheet.worksheet("respostas_questionario")
    ws.append_row(data_row)

# =====================================================
# ANALÍTICA
# =====================================================

def calcular_scores(respostas):
    forca = np.mean(respostas[0:5])
    tecnica = np.mean(respostas[5:10])
    guarda = np.mean(respostas[10:15])
    passagem = np.mean(respostas[15:20])
    score_global = np.mean([forca, tecnica, guarda, passagem])
    return forca, tecnica, guarda, passagem, score_global

def estimar_faixa(score, tempo):
    if score >= 85 and tempo >= 60:
        return "Preta"
    elif score >= 70 and tempo >= 48:
        return "Marrom"
    elif score >= 55 and tempo >= 36:
        return "Roxa"
    elif score >= 40 and tempo >= 12:
        return "Azul"
    else:
        return "Branca"

def calcular_pca_atual(forca, tecnica, guarda, passagem):
    sheet = connect_google_sheets()
    df = pd.DataFrame(
        sheet.worksheet("respostas_questionario").get_all_records()
    )

    if len(df) < 2:
        return None

    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score"
    ]].astype(float).values

    pca = PCA(n_components=2)
    pca.fit(matriz)

    novo = np.array([[forca, tecnica, guarda, passagem]])
    return pca.transform(novo)

# =====================================================
# FUNDO
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

set_background("kimono.jpg")

# =====================================================
# MENU COM SESSION STATE
# =====================================================

if "menu" not in st.session_state:
    st.session_state.menu = "Cadastro de Atleta"

menu = st.sidebar.selectbox(
    "Menu",
    ["Cadastro de Atleta", "Avaliação Técnica"],
    index=["Cadastro de Atleta", "Avaliação Técnica"].index(st.session_state.menu)
)

# =====================================================
# CADASTRO
# =====================================================

if menu == "Cadastro de Atleta":

    st.title("🥋 Cadastro de Atleta")

    with st.form("cadastro"):
        nome = st.text_input("Nome")
        sobrenome = st.text_input("Sobrenome")
        faixa = st.selectbox("Faixa", ["Branca", "Azul", "Roxa", "Marrom", "Preta"])
        tempo = st.number_input("Tempo (meses)", min_value=0)

        if st.form_submit_button("Cadastrar"):

            if nome and sobrenome:
                add_athlete(nome, sobrenome, faixa, tempo)
                st.success("Atleta cadastrado!")

                st.session_state.menu = "Avaliação Técnica"
                st.rerun()
            else:
                st.warning("Preencha nome e sobrenome.")

# =====================================================
# AVALIAÇÃO
# =====================================================

if menu == "Avaliação Técnica":

    st.title("📋 Avaliação Técnica")

    df = get_athletes()

    if df.empty:
        st.warning("Nenhum atleta cadastrado.")
        st.stop()

    atleta_nome = st.selectbox(
        "Selecione o atleta",
        df["nome"] + " " + df["sobrenome"]
    )

    atleta = df[
        (df["nome"] + " " + df["sobrenome"]) == atleta_nome
    ].iloc[0]

    tempo_meses = int(atleta["tempo_treino_meses"])

    perguntas = [
        "Consigo manter pressão constante.",
        "Meu jogo depende de força.",
        "Finalizo controlando posição.",
        "Estabilizo montada facilmente.",
        "Sou forte fisicamente.",
        "Uso pouca energia nos golpes.",
        "Tenho variações técnicas.",
        "Corrijo detalhes rápido.",
        "Finalizo por técnica.",
        "Tenho bom timing.",
        "Prefiro puxar guarda.",
        "Tenho múltiplas guardas.",
        "Raspo com frequência.",
        "Me sinto confortável por baixo.",
        "Finalizo da guarda.",
        "Prefiro passar guarda.",
        "Passo sem explodir.",
        "Uso pressão.",
        "Controlo joelho na barriga.",
        "Finalizo após passagem."
    ]

    respostas = []

    with st.form("avaliacao"):
        for p in perguntas:
            respostas.append(st.slider(p, 1, 5, 3))

        submitted = st.form_submit_button("Finalizar")

    if submitted:

        forca, tecnica, guarda, passagem, score = calcular_scores(respostas)
        faixa_estimada = estimar_faixa(score, tempo_meses)

        componentes = calcular_pca_atual(forca, tecnica, guarda, passagem)

        st.success("Avaliação concluída!")
        st.write("Score:", round(score, 2))
        st.write("Faixa Estimada:", faixa_estimada)

        if componentes is not None:
            st.write("PCA:", componentes)

        data_row = [
            len(connect_google_sheets().worksheet("respostas_questionario").get_all_records()) + 1,
            atleta["athlete_id"],
            *respostas,
            round(forca,2),
            round(tecnica,2),
            round(guarda,2),
            round(passagem,2),
            round(score,2),
            faixa_estimada,
            datetime.now().strftime("%Y-%m-%d")
        ]

        save_questionnaire(data_row)
