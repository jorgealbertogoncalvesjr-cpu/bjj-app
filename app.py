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
    sheet = connect_google()
    return pd.DataFrame(sheet.worksheet("athletes").get_all_records())

def add_athlete(nome, sobrenome, faixa, tempo):

    try:

        sheet = connect_google()
        ws = sheet.worksheet("athletes")

        records = ws.get_all_records()
        athlete_id = len(records) + 1

        ws.append_row([
            int(athlete_id),
            str(nome),
            str(sobrenome),
            str(faixa),
            int(tempo),
            datetime.now().strftime("%Y-%m-%d")
        ])

    except Exception as e:

        st.error(f"Erro ao salvar atleta: {e}")
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
st.divider()

st.subheader("Ficha Técnica do Atleta")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Score Geral", round(score,1))

with col2:
    st.metric("Faixa Estimada", faixa_estimada)

with col3:
    st.metric("Perfil Técnico", perfil)


    
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

# =====================================================
# PCA MONEY STYLE
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

    if len(df) < 2:
        st.warning("PCA requer mínimo 2 avaliações.")
        return 0,0

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

    pc1 = novo[0][0]
    pc2 = novo[0][1]

    fig, ax = plt.subplots(figsize=(8,6))

    # grid
    ax.grid(True, linestyle="--", alpha=0.4)

    # linhas centrais
    ax.axhline(0, linestyle="--", color="gray")
    ax.axvline(0, linestyle="--", color="gray")

    # histórico atletas
    ax.scatter(
        df["PC1"],
        df["PC2"],
        color="lightgray",
        s=80
    )

    # atleta avaliado
    ax.scatter(
        pc1,
        pc2,
        color="darkorange",
        edgecolor="black",
        s=250,
        label="Atleta Avaliado"
    )

    # nomes quadrantes
    ax.text(2,2,"Ofensivo Técnico", fontsize=9)
ax.text(-3,2,"Defensivo Técnico", fontsize=9)
ax.text(2,-2,"Passador de Pressão", fontsize=9)
ax.text(-3,-2,"Guardeiro Estratégico", fontsize=9)
    ax.set_title("Mapa Técnico do Atleta")
    ax.set_xlabel("PC1 — Guarda vs Passagem")
    ax.set_ylabel("PC2 — Técnica vs Força")

    ax.legend()


    
    st.pyplot(fig)

    return pc1,pc2

    # -----------------------------
    # HISTÓRICO ATLETAS
    # -----------------------------

    ax.scatter(
        df["PC1"],
        df["PC2"],
        color="gray",
        alpha=0.6,
        s=60
    )

    # -----------------------------
    # ATLETA ATUAL
    # -----------------------------

    ax.scatter(
        pc1,
        pc2,
        color="red",
        s=250,
        marker="*",
        label="Atleta Avaliado"
    )

    # -----------------------------
    # NOMES DOS QUADRANTES
    # -----------------------------

    ax.text(2, 2, "Passador Técnico", fontsize=10)
    ax.text(-3, 2, "Guardeiro Técnico", fontsize=10)
    ax.text(-3, -2, "Guardeiro Físico", fontsize=10)
    ax.text(2, -2, "Passador Pressão", fontsize=10)

    # -----------------------------
    # ESTILO DASHBOARD
    # -----------------------------

    ax.set_title("Mapa Técnico do Atleta — PCA Scouting", fontsize=14)

    ax.set_xlabel("PC1 — Passagem vs Guarda")
    ax.set_ylabel("PC2 — Técnica vs Força")

    ax.legend()

    st.pyplot(fig)

    return pc1, pc2

def plot_perceptual_map(atleta_nome=None):

    df = get_scores_df()
    atletas = get_athletes()

    if len(df) < 2:
        st.warning("Dados insuficientes.")
        return

    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score",
        "condicionamento_score",
        "tempo_reacao_score",
        "estrategia_score"
    ]]

    matriz = matriz.apply(pd.to_numeric, errors="coerce")

    scaler = StandardScaler()
    matriz_scaled = scaler.fit_transform(matriz)

    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz_scaled)

    fig, ax = plt.subplots(figsize=(9,6))

    for i in range(len(componentes)):

        if i < len(atletas):
            nome = atletas.iloc[i]["nome"]
        else:
            nome = f"A{i}"

        x = componentes[i,0]
        y = componentes[i,1]

        # atleta avaliado
        if nome == atleta_nome:

            ax.scatter(
                x,y,
                color="darkorange",
                s=250,
                edgecolor="black",
                label="Atleta Avaliado" if i==0 else ""
            )

        else:

            ax.scatter(
                x,y,
                color="steelblue",
                s=90,
                label="Base de atletas" if i==1 else ""
            )

        ax.text(x,y,nome,fontsize=9)

    ax.axhline(0, linestyle="--", color="gray")
    ax.axvline(0, linestyle="--", color="gray")

    ax.set_title("Mapa Perceptual — Perfil Técnico dos Atletas")

    ax.set_xlabel("Dimensão Técnica 1")
    ax.set_ylabel("Dimensão Técnica 2")

    ax.legend()

    st.pyplot(fig)

def plot_radar_comparativo(forca, tecnica, guarda, passagem):

    df = get_scores_df()

    categorias = ["Força","Técnica","Guarda","Passagem"]

    atleta = [forca, tecnica, guarda, passagem]

    media = [
        df["forca_score"].mean(),
        df["tecnica_score"].mean(),
        df["guarda_score"].mean(),
        df["passagem_score"].mean()
    ]

    atleta += atleta[:1]
    media += media[:1]

    angles = np.linspace(0, 2*np.pi, len(categorias), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(5,5), subplot_kw=dict(polar=True))

    ax.plot(angles, atleta, linewidth=3, label="Atleta")
    ax.fill(angles, atleta, alpha=0.2)

    ax.plot(angles, media, linewidth=2, linestyle="dashed", label="Média Academia")

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categorias)

    ax.set_title("Radar Técnico Comparativo")

    ax.legend()

    st.pyplot(fig)

def plot_heatmap():

    df = get_scores_df()
    atletas = get_athletes()

    if len(df) == 0:
        return

    matriz = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score",
        "condicionamento_score",
        "tempo_reacao_score",
        "estrategia_score"
    ]].copy()

    matriz = matriz.apply(pd.to_numeric, errors="coerce")

    # adicionar nomes
    nomes = []

    for i in range(len(matriz)):
        if i < len(atletas):
            nomes.append(atletas.iloc[i]["nome"])
        else:
            nomes.append(f"A{i}")

    matriz.index = nomes

    fig, ax = plt.subplots(figsize=(10,5))

    sns.heatmap(
        matriz,
        cmap="RdYlGn",
        annot=True,
        fmt=".0f",
        linewidths=0.5,
        vmin=0,
        vmax=100,
        cbar_kws={"label":"Score Técnico"},
        ax=ax
    )

    ax.set_title("Heatmap de Competências Técnicas")

    ax.set_ylabel("Atletas")
    ax.set_xlabel("Dimensões Técnicas")

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

def ranking_academia():

    df = get_scores_df()
    atletas = get_athletes()

    if len(df)==0:
        return

    df["score_total"] = df[[
        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score",
        "condicionamento_score",
        "tempo_reacao_score",
        "estrategia_score"
    ]].mean(axis=1)

    ranking = df.sort_values("score_total", ascending=False)

    ranking["nome"] = atletas["nome"]

    st.subheader("Ranking Técnico da Academia")

    st.dataframe(
        ranking[["nome","score_total"]],
        use_container_width=True
    )


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


            # =====================================================
            # FUNÇÕES BANCO
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
                    return pd.DataFrame()


            # salvar atleta novamente para garantir ID atualizado
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

st.divider()

st.subheader("Análise Técnica do Atleta")

tab1, tab2, tab3, tab4 = st.tabs([
    "Radar Técnico",
    "Scouting Map (PCA)",
    "Heatmap Academia",
    "Mapa Perceptual"
])

with tab1:

    st.caption("Distribuição das competências do atleta")

    plot_radar(
        forca,
        tecnica,
        guarda,
        passagem
    )

with tab2:

    st.caption("Posicionamento técnico do atleta comparado à base")

    plot_pca(
        forca,
        tecnica,
        guarda,
        passagem,
        condicionamento,
        tempo_reacao,
        estrategia
    )

with tab3:

    st.caption("Mapa de intensidade das competências")

    plot_heatmap()

with tab4:

    st.caption("Associação perceptual entre atletas")

    plot_perceptual_map(st.session_state.nome)

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
