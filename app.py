# =====================================================
# 1️⃣ IMPORTS
# =====================================================

import streamlit as st
import pandas as pd
import gspread
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import base64
import os
from datetime import datetime
from sklearn.decomposition import PCA

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet

# =====================================================
# 2️⃣ CONFIGURAÇÃO
# =====================================================

st.set_page_config(
    page_title="BJJ Performance Profile",
    page_icon="🥋",
    layout="centered"
)

# =====================================================
# 3️⃣ CONEXÃO GOOGLE
# =====================================================

@st.cache_resource
def connect_google():
    gc = gspread.service_account_from_dict(
        st.secrets["gcp_service_account"]
    )
    return gc.open("bjj_app_database")

# =====================================================
# 4️⃣ FUNÇÕES BANCO
# =====================================================

def get_athletes():
    sheet = connect_google()
    return pd.DataFrame(sheet.worksheet("athletes").get_all_records())

def add_athlete(nome, sobrenome, faixa, tempo):
    ws = connect_google().worksheet("athletes")
    athlete_id = len(ws.get_all_records()) + 1

    ws.append_row([
        athlete_id,
        nome,
        sobrenome,
        faixa,
        tempo,
        datetime.now().strftime("%Y-%m-%d")
    ])

def save_questionnaire(data_row):
    ws = connect_google().worksheet("respostas_questionario")
    ws.append_row(data_row)

def get_scores_df():
    return pd.DataFrame(
        connect_google().worksheet("respostas_questionario").get_all_records()
    )

# =====================================================
# 5️⃣ FUNÇÕES ANALÍTICAS
# =====================================================

def calcular_scores(respostas):
    forca = np.mean(respostas[0:5])
    tecnica = np.mean(respostas[5:10])
    guarda = np.mean(respostas[10:15])
    passagem = np.mean(respostas[15:20])
    score = np.mean([forca, tecnica, guarda, passagem])
    return forca, tecnica, guarda, passagem, score

def estimar_faixa(score, tempo):
    if score >= 85 and tempo >= 60:
        return "Preta"
    elif score >= 70 and tempo >= 48:
        return "Marrom"
    elif score >= 55 and tempo >= 36:
        return "Roxa"
    elif score >= 40 and tempo >= 12:
        return "Azul"
    return "Branca"

# =====================================================
# 6️⃣ FUNÇÕES GRÁFICAS
# =====================================================

def plot_pca(atual_scores):

    df = get_scores_df()
    if len(df) < 2:
        st.warning("PCA requer mínimo 2 avaliações.")
        return None

    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score"
    ]].astype(float)

    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz)

    df["PC1"] = componentes[:,0]
    df["PC2"] = componentes[:,1]

    novo = pca.transform([atual_scores])

    fig, ax = plt.subplots()
    sns.scatterplot(data=df, x="PC1", y="PC2", ax=ax)
    ax.scatter(novo[0][0], novo[0][1], s=200)
    ax.set_title("Mapa PCA")

    st.pyplot(fig)
    return fig

def plot_radar(forca, tecnica, guarda, passagem):

    categorias = ["Força","Técnica","Guarda","Passagem"]
    valores = [forca, tecnica, guarda, passagem]
    valores += valores[:1]

    angles = np.linspace(0, 2*np.pi, len(categorias), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(subplot_kw=dict(polar=True))
    ax.plot(angles, valores)
    ax.fill(angles, valores, alpha=0.25)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categorias)

    st.pyplot(fig)
    return fig

def plot_correlation():

    df = get_scores_df()
    if len(df) < 2:
        st.warning("Correlação requer histórico.")
        return None

    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score"
    ]].astype(float)

    corr = matriz.corr()

    fig, ax = plt.subplots()
    sns.heatmap(corr, annot=True, cmap="coolwarm", ax=ax)
    ax.set_title("Correlação")

    st.pyplot(fig)
    return fig

# =====================================================
# 7️⃣ PDF
# =====================================================

def gerar_pdf(nome, score, faixa):

    file_path = "relatorio_bjj.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("<b>Relatório Técnico BJJ</b>", styles["Title"]))
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(f"Atleta: {nome}", styles["Normal"]))
    elements.append(Paragraph(f"Score Global: {round(score,2)}", styles["Normal"]))
    elements.append(Paragraph(f"Faixa Estimada: {faixa}", styles["Normal"]))

    doc.build(elements)
    return file_path

# =====================================================
# 8️⃣ FUNDO
# =====================================================

def set_background(img):
    if os.path.exists(img):
        with open(img, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        st.markdown(
            f"<style>.stApp {{background-image:url(data:image/jpg;base64,{encoded});background-size:cover;}}</style>",
            unsafe_allow_html=True
        )

set_background("kimono.jpg")

# =====================================================
# 9️⃣ MENU
# =====================================================

if "menu" not in st.session_state:
    st.session_state.menu = "Cadastro"

menu = st.sidebar.selectbox(
    "Menu",
    ["Cadastro", "Avaliação"],
    index=["Cadastro","Avaliação"].index(st.session_state.menu)
)

# =====================================================
# 🔟 CADASTRO
# =====================================================

if menu == "Cadastro":

    st.title("Cadastro de Atleta")

    with st.form("cad"):
        nome = st.text_input("Nome")
        sobrenome = st.text_input("Sobrenome")
        faixa = st.selectbox("Faixa", ["Branca","Azul","Roxa","Marrom","Preta"])
        tempo = st.number_input("Tempo (meses)", min_value=0)

        if st.form_submit_button("Salvar"):
            if nome and sobrenome:
                add_athlete(nome, sobrenome, faixa, tempo)
                st.success("Atleta cadastrado!")
                st.session_state.menu = "Avaliação"
                st.rerun()

# =====================================================
# 1️⃣1️⃣ AVALIAÇÃO
# =====================================================

if menu == "Avaliação":

    st.title("Avaliação Técnica")

    df = get_athletes()
    if df.empty:
        st.warning("Nenhum atleta cadastrado.")
        st.stop()

    atleta_nome = st.selectbox(
        "Selecione o atleta",
        df["nome"] + " " + df["sobrenome"]
    )

    atleta = df[(df["nome"] + " " + df["sobrenome"]) == atleta_nome].iloc[0]
    tempo = int(atleta["tempo_treino_meses"])

    perguntas = ["Pergunta "+str(i) for i in range(1,21)]

    respostas = []
    with st.form("avaliacao"):
        for p in perguntas:
            respostas.append(st.slider(p,1,5,3))
        submitted = st.form_submit_button("Finalizar")

    if submitted:

        forca, tecnica, guarda, passagem, score = calcular_scores(respostas)
        faixa_estimada = estimar_faixa(score, tempo)

        st.success("Avaliação concluída!")
        st.write("Score:", round(score,2))
        st.write("Faixa Estimada:", faixa_estimada)

        save_questionnaire([
            len(get_scores_df())+1,
            atleta["athlete_id"],
            *respostas,
            round(forca,2),
            round(tecnica,2),
            round(guarda,2),
            round(passagem,2),
            round(score,2),
            faixa_estimada,
            datetime.now().strftime("%Y-%m-%d")
        ])

        # Gráficos
        plot_pca([forca, tecnica, guarda, passagem])
        plot_radar(forca, tecnica, guarda, passagem)
        plot_correlation()

        pdf = gerar_pdf(atleta_nome, score, faixa_estimada)
        with open(pdf,"rb") as f:
            st.download_button("Baixar PDF", f, "Relatorio_BJJ.pdf")
