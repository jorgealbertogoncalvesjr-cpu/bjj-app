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
import io
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from sklearn.preprocessing import StandardScaler

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
    try:
        gc = gspread.service_account_from_dict(
            st.secrets["gcp_service_account"]
        )
        return gc.open("bjj_app_database")
    except Exception as e:
        st.error("Erro ao conectar com Google Sheets")
        st.stop()


# =====================================================
# 4️⃣ FUNÇÕES BANCO
# =====================================================

def get_athletes():

    try:
        sheet = connect_google()
        ws = sheet.worksheet("athletes")
        data = ws.get_all_records()

        if len(data) == 0:
            return pd.DataFrame()

        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Erro ao acessar aba athletes: {e}")
        st.stop()


def get_scores_df():
    ws = connect_google().worksheet("respostas_questionario")
    data = ws.get_all_records()

    if len(data) == 0:
        return pd.DataFrame()

    return pd.DataFrame(data)


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
    if score >= 85 and tempo >= 66:
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

    if df.empty or len(df) < 2:
        st.warning("PCA requer no mínimo 2 avaliações registradas.")
        return

    # Seleção das variáveis
    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score"
    ]].astype(float)

    # Padronização (importante para PCA)
    scaler = StandardScaler()
    matriz_scaled = scaler.fit_transform(matriz)

    # PCA
    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz_scaled)

    df["PC1"] = componentes[:, 0]
    df["PC2"] = componentes[:, 1]

    # Projetar novo atleta no espaço PCA
    novo_scaled = scaler.transform([[forca, tecnica, guarda, passagem]])
    novo = pca.transform(novo_scaled)

    # Gráfico
    fig, ax = plt.subplots()

    sns.scatterplot(
        data=df,
        x="PC1",
        y="PC2",
        ax=ax
    )

    ax.scatter(
        novo[0][0],
        novo[0][1],
        s=200,
        color="red",
        label="Atleta atual"
    )

    ax.legend()
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

    if df.empty or len(df) < 2:
        st.warning("Correlação requer histórico mínimo de avaliações.")
        return

    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score"
    ]].astype(float)

    corr = matriz.corr()

    fig, ax = plt.subplots()

    sns.heatmap(
        corr,
        annot=True,
        cmap="coolwarm",
        ax=ax
    )

    ax.set_title("Matriz de Correlação Técnica")

    st.pyplot(fig)

# =====================================================
# 7️⃣ GERAÇÃO DE RELATÓRIO PDF
# =====================================================

def gerar_pdf(nome_atleta, score_global, faixa_estimada):

    file_path = "relatorio_bjj.pdf"

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4
    )

    styles = getSampleStyleSheet()

    elementos = []

    elementos.append(
        Paragraph("Relatório Técnico BJJ", styles["Title"])
    )

    elementos.append(Spacer(1, 0.5 * inch))

    elementos.append(
        Paragraph(f"Atleta: {nome_atleta}", styles["Normal"])
    )

    elementos.append(
        Paragraph(f"Score Global: {round(score_global,2)}", styles["Normal"])
    )

    elementos.append(
        Paragraph(f"Faixa Estimada: {faixa_estimada}", styles["Normal"])
    )

    elementos.append(Spacer(1, 0.5 * inch))

    elementos.append(
        Paragraph(
            "Este relatório foi gerado automaticamente com base nas respostas "
            "do questionário técnico e no histórico de avaliações armazenadas.",
            styles["Normal"]
        )
    )

    doc.build(elementos)

    return file_path
# =====================================================
# 8️⃣ MENU
# =====================================================

if "menu" not in st.session_state:
    st.session_state.menu = "Cadastro"

menu = st.sidebar.selectbox(
    "Menu",
    ["Nova Avaliação"]
)


# =====================================================
# 9️⃣ CADASTRO
# =====================================================
