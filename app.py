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

    forca = float(np.mean(respostas[0:3]))
    tecnica = float(np.mean(respostas[3:6]))
    guarda = float(np.mean(respostas[6:9]))
    passagem = float(np.mean(respostas[9:12]))
    condicionamento = float(np.mean(respostas[12:15]))
    tempo_reacao = float(np.mean(respostas[15:18]))
    estrategia = float(np.mean(respostas[18:20]))

    score_global = float(np.mean([
        forca,
        tecnica,
        guarda,
        passagem,
        condicionamento,
        tempo_reacao,
        estrategia
    ]))

    return (
        forca,
        tecnica,
        guarda,
        passagem,
        condicionamento,
        tempo_reacao,
        estrategia,
        score_global
    )


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
# CLASSIFICAÇÃO DE PERFIL TÉCNICO
# =====================================================

def classificar_perfil(pc1, pc2):

    if pc1 < 0 and pc2 > 0:
        return "Guardeiro Técnico"

    elif pc1 < 0 and pc2 <= 0:
        return "Guardeiro Físico"

    elif pc1 >= 0 and pc2 > 0:
        return "Passador Técnico"

    else:
        return "Passador Pressão"

# =====================================================
# 6️⃣ FUNÇÕES GRÁFICAS
# =====================================================

from sklearn.preprocessing import StandardScaler

def plot_pca(
    forca,
    tecnica,
    guarda,
    passagem,
    condicionamento,
    tempo_reacao,
    estrategia
):

    df = get_scores_df()

    if len(df) < 3:
        st.warning("PCA requer pelo menos 3 avaliações.")
        return 0, 0

    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score",
        "condicionamento_score",
        "tempo_reacao_score",
        "estrategia_score"
    ]].astype(float)

    scaler = StandardScaler()
    matriz_scaled = scaler.fit_transform(matriz)

    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz_scaled)

    df["PC1"] = componentes[:,0]
    df["PC2"] = componentes[:,1]

    novo = scaler.transform([[
        forca,
        tecnica,
        guarda,
        passagem,
        condicionamento,
        tempo_reacao,
        estrategia
    ]])

    novo = pca.transform(novo)

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
        s=250,
        marker="X"
    )

    ax.set_title("Mapa PCA - Perfil Técnico BJJ")

    st.pyplot(fig)

    return novo[0][0], novo[0][1]


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


if "etapa" not in st.session_state:
    st.session_state.etapa = 1


if menu == "Nova Avaliação":

    if st.session_state.etapa == 1:

        st.title("Nova Avaliação Técnica")

        nome = st.text_input("Nome")
        sobrenome = st.text_input("Sobrenome")

        faixa = st.selectbox(
            "Faixa atual",
            ["Branca","Azul","Roxa","Marrom","Preta"]
        )

        tempo = st.number_input(
            "Tempo de treino (meses)",
            min_value=0
        )

        if st.button("Iniciar Avaliação"):

            if nome and sobrenome:

                st.session_state.nome = nome
                st.session_state.sobrenome = sobrenome
                st.session_state.faixa = faixa
                st.session_state.tempo = tempo

                st.session_state.etapa = 2
                st.rerun()


# =====================================================
# 9️⃣ CADASTRO
# =====================================================
# =====================================================
# NOVA AVALIAÇÃO (FLUXO DINÂMICO)
# =====================================================

if "etapa" not in st.session_state:
    st.session_state.etapa = 1


if menu == "Nova Avaliação":

    # -----------------------------
    # ETAPA 1 — CADASTRO
    # -----------------------------

    if st.session_state.etapa == 1:

        st.title("Nova Avaliação Técnica")

        nome = st.text_input("Nome")
        sobrenome = st.text_input("Sobrenome")

        faixa = st.selectbox(
            "Faixa atual",
            ["Branca", "Azul", "Roxa", "Marrom", "Preta"]
        )

        tempo = st.number_input(
            "Tempo de treino (meses)",
            min_value=0
        )

        if st.button("Iniciar Avaliação"):

            if nome and sobrenome:

                st.session_state.nome = nome
                st.session_state.sobrenome = sobrenome
                st.session_state.faixa = faixa
                st.session_state.tempo = tempo

                st.session_state.etapa = 2
                st.rerun()

            else:
                st.warning("Preencha nome e sobrenome.")

# -----------------------------
# ETAPA 2 — QUESTIONÁRIO
# -----------------------------

if st.session_state.etapa == 2:

    st.title("Questionário Técnico")

    perguntas = [
        "Consigo manter pressão constante por 5 minutos.",
        "Meu jogo depende bastante de força física.",
        "Consigo finalizar apenas controlando posição.",
        "Tenho facilidade em estabilizar montada ou 100kg.",
        "Meu jogo melhora contra atletas menores.",

        "Aplico golpes com mínimo gasto de energia.",
        "Tenho variações técnicas para uma posição.",
        "Corrijo detalhes técnicos com facilidade.",
        "Finalizo mais por técnica do que explosão.",
        "Meu timing é diferencial.",

        "Prefiro puxar guarda.",
        "Tenho múltiplas guardas ativas.",
        "Raspo atletas da mesma faixa com frequência.",
        "Me sinto confortável por baixo.",
        "Finalizo da guarda com consistência.",

        "Prefiro iniciar passando guarda.",
        "Passo guarda sem explodir.",
        "Uso pressão como estratégia.",
        "Tenho controle forte em joelho na barriga.",
        "Finalizo após passar guarda."
    ]

    respostas = []

    with st.form("avaliacao"):

        for p in perguntas:
            respostas.append(st.slider(p, 0, 100, 50, step=5))

        submitted = st.form_submit_button("Finalizar Avaliação")


    if submitted:

        forca, tecnica, guarda, passagem, condicionamento, tempo_reacao, estrategia, score = calcular_scores(respostas)

        faixa_estimada = estimar_faixa(
            score,
            st.session_state.tempo
        )

        # salvar atleta
        add_athlete(
            st.session_state.nome,
            st.session_state.sobrenome,
            st.session_state.faixa,
            st.session_state.tempo
        )

        df = get_athletes()
        atleta_id = df.iloc[-1]["athlete_id"]

        # salvar scores
        save_questionnaire([
            int(len(get_scores_df()) + 1),
            int(atleta_id),
            float(forca),
            float(tecnica),
            float(guarda),
            float(passagem),
            float(condicionamento),
            float(tempo_reacao),
            float(estrategia),
            datetime.now().strftime("%Y-%m-%d")
        ])

        st.success("Avaliação concluída!")

        st.write("Score:", round(score, 2))
        st.write("Faixa estimada:", faixa_estimada)

        pc1, pc2 = plot_pca(
            forca,
            tecnica,
            guarda,
            passagem,
            condicionamento,
            tempo_reacao,
            estrategia
        )

        perfil = classificar_perfil(pc1, pc2)

        st.subheader("Perfil Técnico Identificado")
        st.success(perfil)

        st.markdown(f"""
        ### Perfil Técnico

        **{perfil}**

        Este perfil representa a tendência dominante do jogo do atleta
        considerando força, técnica, guarda e passagem.
        """)

        plot_radar(forca, tecnica, guarda, passagem)
        plot_correlation()

        pdf = gerar_pdf(
            st.session_state.nome,
            score,
            faixa_estimada
        )

        with open(pdf, "rb") as f:
            st.download_button(
                "Baixar PDF",
                f,
                "Relatorio_BJJ.pdf"
            )
   
