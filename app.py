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


def get_scores_df():
    return pd.DataFrame(
        connect_google().worksheet("respostas_questionario").get_all_records()
    )


def add_athlete(nome, sobrenome, faixa, tempo):
    ws = connect_google().worksheet("athletes")
    athlete_id = len(ws.get_all_records()) + 1

    ws.append_row([
        int(athlete_id),
        str(nome),
        str(sobrenome),
        str(faixa),
        int(tempo),
        datetime.now().strftime("%Y-%m-%d")
    ])


def save_questionnaire(data_row):
    ws = connect_google().worksheet("respostas_questionario")

    # 🔥 Conversão explícita para tipos nativos
    clean_row = []
    for v in data_row:
        if isinstance(v, (np.integer,)):
            clean_row.append(int(v))
        elif isinstance(v, (np.floating,)):
            clean_row.append(float(v))
        else:
            clean_row.append(v)

    ws.append_row(clean_row)


# =====================================================
# 5️⃣ FUNÇÕES ANALÍTICAS
# =====================================================

def calcular_scores(respostas):
    forca = float(np.mean(respostas[0:5]))
    tecnica = float(np.mean(respostas[5:10]))
    guarda = float(np.mean(respostas[10:15]))
    passagem = float(np.mean(respostas[15:20]))
    score_global = float(np.mean([forca, tecnica, guarda, passagem]))

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


# =====================================================
# 6️⃣ FUNÇÕES GRÁFICAS
# =====================================================

def plot_pca(forca, tecnica, guarda, passagem):

    df = get_scores_df()
    if len(df) < 2:
        st.warning("PCA requer mínimo 2 avaliações registradas.")
        return

    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score"
    ]].astype(float)

    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz)

    df["PC1"] = componentes[:, 0]
    df["PC2"] = componentes[:, 1]

    novo = pca.transform([[forca, tecnica, guarda, passagem]])

    fig, ax = plt.subplots()
    sns.scatterplot(data=df, x="PC1", y="PC2", ax=ax)
    ax.scatter(novo[0][0], novo[0][1], s=200)
    ax.set_title("Mapa PCA - Perfil Técnico")

    st.pyplot(fig)


def plot_radar(forca, tecnica, guarda, passagem):

    categorias = ["Força", "Técnica", "Guarda", "Passagem"]
    valores = [forca, tecnica, guarda, passagem]
    valores += valores[:1]

    angles = np.linspace(0, 2 * np.pi, len(categorias), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(subplot_kw=dict(polar=True))
    ax.plot(angles, valores)
    ax.fill(angles, valores, alpha=0.25)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categorias)
    ax.set_title("Perfil Técnico Radar")

    st.pyplot(fig)


def plot_correlation():

    df = get_scores_df()
    if len(df) < 2:
        st.warning("Correlação requer histórico mínimo.")
        return

    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score"
    ]].astype(float)

    corr = matriz.corr()

    fig, ax = plt.subplots()
    sns.heatmap(corr, annot=True, cmap="coolwarm", ax=ax)
    ax.set_title("Matriz de Correlação")

    st.pyplot(fig)


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
# 8️⃣ MENU
# =====================================================

if "menu" not in st.session_state:
    st.session_state.menu = "Cadastro"

menu = st.sidebar.selectbox(
    "Menu",
    ["Cadastro", "Avaliação"],
    index=["Cadastro", "Avaliação"].index(st.session_state.menu)
)


# =====================================================
# 9️⃣ CADASTRO
# =====================================================

if menu == "Cadastro":

    st.title("Cadastro de Atleta")

    with st.form("cadastro"):
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
# 🔟 AVALIAÇÃO
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

    perguntas = [
        # Força
        "Consigo manter pressão constante por 5 minutos.",
        "Meu jogo depende bastante de força física.",
        "Consigo finalizar apenas controlando posição.",
        "Tenho facilidade em estabilizar montada ou 100kg.",
        "Meu jogo melhora contra atletas menores.",
        # Técnica
        "Aplico golpes com mínimo gasto de energia.",
        "Tenho variações técnicas para uma posição.",
        "Corrijo detalhes técnicos com facilidade.",
        "Finalizo mais por técnica do que explosão.",
        "Meu timing é diferencial.",
        # Guarda
        "Prefiro puxar guarda.",
        "Tenho múltiplas guardas ativas.",
        "Raspo atletas da mesma faixa com frequência.",
        "Me sinto confortável por baixo.",
        "Finalizo da guarda com consistência.",
        # Passagem
        "Prefiro iniciar passando guarda.",
        "Passo guarda sem explodir.",
        "Uso pressão como estratégia.",
        "Tenho controle forte em joelho na barriga.",
        "Finalizo após passar guarda."
    ]

    respostas = []

    with st.form("avaliacao"):
        for p in perguntas:
            respostas.append(int(st.slider(p, 1, 5, 3)))
        submitted = st.form_submit_button("Finalizar Avaliação")

    if submitted:

        forca, tecnica, guarda, passagem, score = calcular_scores(respostas)
        faixa_estimada = estimar_faixa(score, tempo)

        st.success("Avaliação concluída!")
        st.write("Score:", round(score,2))
        st.write("Faixa Estimada:", faixa_estimada)

        save_questionnaire([
            int(len(get_scores_df()) + 1),
            int(atleta["athlete_id"]),
            *respostas,
            float(forca),
            float(tecnica),
            float(guarda),
            float(passagem),
            float(score),
            faixa_estimada,
            datetime.now().strftime("%Y-%m-%d")
        ])

        plot_pca(forca, tecnica, guarda, passagem)
        plot_radar(forca, tecnica, guarda, passagem)
        plot_correlation()

        pdf = gerar_pdf(atleta_nome, score, faixa_estimada)
        with open(pdf, "rb") as f:
            st.download_button("Baixar PDF", f, "Relatorio_BJJ.pdf")
