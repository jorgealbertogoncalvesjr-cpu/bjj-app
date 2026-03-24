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
from sklearn.preprocessing import StandardScaler
from matplotlib.patches import Ellipse
import io

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet



# =====================================================
# 2️⃣ CONFIGURAÇÃO STREAMLIT
# =====================================================

st.set_page_config(
    page_title="BJJ Performance Profile",
    page_icon="🥋",
    layout="centered"
)

st.title("🥋 BJJ Performance Analytics")


# =====================================================
# 3️⃣ CONEXÃO GOOGLE SHEETS
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
        st.error(e)

        st.stop()


# =====================================================
# 4️⃣ FUNÇÕES DE BANCO DE DADOS
# =====================================================

def get_athletes():

    try:

        ws = connect_google().worksheet("athletes")

        data = ws.get_all_records()

        if len(data) == 0:
            return pd.DataFrame()

        return pd.DataFrame(data)

    except Exception as e:

        st.error("Erro ao carregar atletas")
        st.error(e)

        return pd.DataFrame()


# -----------------------------------------------------
# ADICIONAR ATLETA
# -----------------------------------------------------

def add_athlete(nome, sobrenome, faixa, tempo):

    try:

        sheet = connect_google()
        ws = sheet.worksheet("athletes")

        records = ws.get_all_records()

        athlete_id = max([r["athlete_id"] for r in records], default=0) + 1

        ws.append_row([

            int(athlete_id),
            str(nome),
            str(sobrenome),
            str(faixa),
            int(tempo),
            datetime.now().strftime("%Y-%m-%d")

        ])

    except Exception as e:

        st.error("Erro ao salvar atleta")
        st.error(e)


# -----------------------------------------------------
# CARREGAR SCORES
# -----------------------------------------------------

def get_scores_df():

    try:

        ws = connect_google().worksheet("respostas_questionario")

        data = ws.get_all_records()

        if len(data) == 0:
            return pd.DataFrame()

        return pd.DataFrame(data)

    except Exception as e:

        st.error("Erro ao carregar respostas")
        st.error(e)

        return pd.DataFrame()


# -----------------------------------------------------
# SALVAR QUESTIONÁRIO
# -----------------------------------------------------

def save_questionnaire(data_row):

    try:

        ws = connect_google().worksheet("respostas_questionario")

        clean_row = []

        for v in data_row:

            if isinstance(v, (np.integer,)):
                clean_row.append(int(v))

            elif isinstance(v, (np.floating,)):
                clean_row.append(float(v))

            else:
                clean_row.append(v)

        ws.append_row(clean_row)

    except Exception as e:

        st.error("Erro ao salvar respostas")
        st.error(e)


# -----------------------------------------------------
# HISTÓRICO DO ATLETA
# -----------------------------------------------------

def get_athlete_history(athlete_id):

    df = get_scores_df()

    if df.empty:
        return pd.DataFrame()

    df = df[df["athlete_id"] == athlete_id]

    if df.empty:
        return pd.DataFrame()

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"])

    df["score_total"] = df[[

        "forca_score",
        "tecnica_score",
        "guarda_score",
        "passagem_score",
        "condicionamento_score",
        "tempo_reacao_score",
        "estrategia_score"

    ]].mean(axis=1)
    return df


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


# -----------------------------------------------------
# BJJ PERFORMANCE SCORE
# -----------------------------------------------------

def calcular_bjj_score(

    forca,
    tecnica,
    guarda,
    passagem,
    condicionamento,
    tempo_reacao,
    estrategia

):

    score = (

        forca * 0.15 +
        tecnica * 0.20 +
        guarda * 0.15 +
        passagem * 0.20 +
        condicionamento * 0.10 +
        tempo_reacao * 0.10 +
        estrategia * 0.10

    )

    return round(score,2)


# -----------------------------------------------------
# FAIXA ESTIMADA
# -----------------------------------------------------

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


# -----------------------------------------------------
# NÍVEL TÉCNICO
# -----------------------------------------------------

def classificar_nivel(score):

    if score >= 85:
        return "Elite"
    elif 70 <= score < 85:
        return "Avançado"
    elif 55 <= score < 70:
        return "Intermediário"
    else:
        return "Iniciante"


# -----------------------------------------------------
# PERFIL DE LUTA
# -----------------------------------------------------

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
# 6️⃣ DIAGNÓSTICO AUTOMÁTICO
# =====================================================

def gerar_diagnostico(
    forca,
    tecnica,
    guarda,
    passagem,
    condicionamento,
    tempo_reacao,
    estrategia
):

    pontos_fortes = []
    melhorias = []
    recomendacoes = []

    # Pontos fortes

    if tecnica >= 70:
        pontos_fortes.append("Boa eficiência técnica.")

    if passagem >= 70:
        pontos_fortes.append("Passagem de guarda consistente.")

    if guarda >= 70:
        pontos_fortes.append("Jogo de guarda sólido.")

    if estrategia >= 70:
        pontos_fortes.append("Boa leitura estratégica da luta.")


    # Oportunidades de melhoria

    if guarda < 50:
        melhorias.append("Desenvolver jogo de guarda.")

    if condicionamento < 50:
        melhorias.append("Melhorar condicionamento físico.")

    if tempo_reacao < 50:
        melhorias.append("Aprimorar tempo de reação.")

    if estrategia < 50:
        melhorias.append("Trabalhar tomada de decisão durante a luta.")


    # Recomendações de treino

    if guarda < 60:
        recomendacoes.append("Treinar raspagens e retenção de guarda.")

    if passagem < 60:
        recomendacoes.append("Aprimorar sequências de passagem de guarda.")

    if condicionamento < 60:
        recomendacoes.append("Aumentar rounds de treino e drills de resistência.")

    if tecnica < 60:
        recomendacoes.append("Reforçar fundamentos técnicos.")


    return pontos_fortes, melhorias, recomendacoes

# =====================================================
# CONFIDENCE ELLIPSE
# =====================================================


def draw_confidence_ellipse(x, y, ax, n_std=2.0):

    if len(x) < 2:
        return


    cov = np.cov(x, y)

    den = np.sqrt(cov[0,0] * cov[1,1])

    if den == 0:
        return

    pearson = cov[0,1] / den

    ell_radius_x = np.sqrt(1 + pearson)
    ell_radius_y = np.sqrt(1 - pearson)

    ellipse = Ellipse(
        (0,0),
        width=ell_radius_x * 2,
        height=ell_radius_y * 2,
        fill=False,
        linestyle="--",
        edgecolor="blue",
        linewidth=2,
        label="Zona da Academia"
    )

    scale_x = np.sqrt(cov[0,0]) * n_std
    scale_y = np.sqrt(cov[1,1]) * n_std

    mean_x = np.mean(x)
    mean_y = np.mean(y)

    transf = (
        plt.matplotlib.transforms.Affine2D()
        .rotate_deg(45)
        .scale(scale_x, scale_y)
        .translate(mean_x, mean_y)
    )

    ellipse.set_transform(transf + ax.transData)

    ax.add_patch(ellipse)
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

    if df.empty or len(df) < 2:
        st.warning("PCA requer mínimo 2 avaliações.")
        return 0, 0

    matriz = df[
        [
            "forca_score",
            "tecnica_score",
            "guarda_score",
            "passagem_score",
            "condicionamento_score",
            "tempo_reacao_score",
            "estrategia_score",
        ]
    ].astype(float)

    scaler = StandardScaler()
    matriz_scaled = scaler.fit_transform(matriz)

    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz_scaled)

    df["PC1"] = componentes[:, 0]
    df["PC2"] = componentes[:, 1]

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

    # 🎯 CRIA FIGURA
    fig, ax = plt.subplots(figsize=(8, 6))

    # BASE
    ax.scatter(
        df["PC1"],
        df["PC2"],
        color="lightgray",
        alpha=0.6,
        s=80,
        label="Base de atletas",
    )

    # ATLETA
    ax.scatter(
        pc1,
        pc2,
        color="darkorange",
        edgecolor="black",
        s=350,
        marker="*",
        label="Atleta Avaliado"
    )

    # GRID + EIXOS
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.axhline(0, linestyle="--", color="gray")
    ax.axvline(0, linestyle="--", color="gray")

    # LABELS
    ax.set_title("Mapa Técnico — PCA Scouting")
    ax.set_xlabel("Passagem ← → Guarda")
    ax.set_ylabel("Força ← → Técnica")
    ax.set_xlim(-5,5)
    ax.set_ylim(-5,5)

    ax.legend()

    st.pyplot(fig)

    return pc1, pc2  

def plot_style_profile(pc1, pc2):

    fig, ax = plt.subplots(figsize=(6,6))

    ax.axhline(0, color="gray", linestyle="--")
    ax.axvline(0, color="gray", linestyle="--")

    ax.scatter(
        pc1,
        pc2,
        s=300,
        color="darkorange",
        edgecolor="black"
    )

    ax.text(2,2,"Passador Técnico")
    ax.text(-2,2,"Guardeiro Técnico")
    ax.text(-2,-2,"Guardeiro Físico")
    ax.text(2,-2,"Passador Pressão")

    # 🔑 LIMITAR ESCALA (evita imagem gigante)
    ax.set_xlim(-5,5)
    ax.set_ylim(-5,5)

    ax.set_title("BJJ Style Profile")

    ax.set_xlabel("Passagem  ← →  Guarda")
    ax.set_ylabel("Força  ← →  Técnica")

    st.pyplot(fig)


def plot_radar_comparativo(forca, tecnica, guarda, passagem):

    df = get_scores_df()

    if df.empty:
        return

    # converter para número
    df = df.apply(pd.to_numeric, errors="coerce")

    df["forca_score"] = pd.to_numeric(df["forca_score"], errors="coerce")
    df["tecnica_score"] = pd.to_numeric(df["tecnica_score"], errors="coerce")
    df["guarda_score"] = pd.to_numeric(df["guarda_score"], errors="coerce")
    df["passagem_score"] = pd.to_numeric(df["passagem_score"], errors="coerce")

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

    angles = np.linspace(0,2*np.pi,len(categorias),endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(subplot_kw=dict(polar=True))

    ax.plot(angles, atleta, linewidth=3, label="Atleta")
    ax.fill(angles, atleta, alpha=0.2)

    ax.plot(angles, media, linestyle="dashed", label="Média Academia")

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categorias)

    ax.set_ylim(0,100)

    ax.set_title("Radar Técnico Comparativo")

    ax.legend()

    st.pyplot(fig)

    return df

def plot_heatmap():

    df = get_scores_df()
    atletas = get_athletes()

    if df.empty:
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

    nomes = []

    for i in range(len(matriz)):

        if i < len(atletas):
            nomes.append(atletas.iloc[i]["nome"])

        else:
            nomes.append(f"A{i}")
    
    if len(nomes) == len(matriz):
        matriz.index = nomes

    fig, ax = plt.subplots(figsize=(10,5))

    fig, ax = plt.subplots(figsize=(14,8))

matriz = matriz.apply(pd.to_numeric, errors="coerce").round(0)

# 🔥 TOP 10 atletas
matriz["media"] = matriz.mean(axis=1)
matriz = matriz.sort_values("media", ascending=False).head(10)
matriz = matriz.drop(columns="media")

sns.heatmap(
    matriz,
    cmap="viridis",
    annot=False,
    vmin=0,
    vmax=100,
    linewidths=0.5,
    linecolor='gray',
    ax=ax
)

plt.xticks(rotation=45, ha="right")
plt.yticks(rotation=0)

# 🔥 destacar atleta
for i, nome in enumerate(matriz.index):
    if nome == st.session_state.nome:
        ax.get_yticklabels()[i].set_color("red")
        ax.get_yticklabels()[i].set_weight("bold")

ax.set_title("Heatmap de Competências (Top 10)")

st.pyplot(fig)



df = get_scores_df()
atletas = get_athletes()

faixa_filtro = st.selectbox(
    "Comparar com atletas da faixa:",
    ["Todas","Branca","Azul","Roxa","Marrom","Preta"]
)

    # FILTRO POR FAIXA
if faixa_filtro != "Todas":

    atletas_filtrados = atletas[atletas["faixa"] == faixa_filtro]

    ids = atletas_filtrados["athlete_id"].tolist()

    df = df[df["athlete_id"].isin(ids)]

    atletas = atletas_filtrados.reset_index(drop=True)
    df = df.reset_index(drop=True)

        if len(df) < 2:
            st.warning("Poucos atletas nesta faixa.")
            return

 
def plot_perceptual_map(atleta_nome=None):

    df = get_scores_df()
    atletas = get_athletes()

    if df.empty or len(df) < 2:
        st.warning("Dados insuficientes.")
        return

    # -------------------------------------------------
    # MATRIZ PCA
    # -------------------------------------------------

    matriz = df[
        [
            "forca_score",
            "tecnica_score",
            "guarda_score",
            "passagem_score",
            "condicionamento_score",
            "tempo_reacao_score",
            "estrategia_score",
        ]
    ]

    matriz = matriz.apply(pd.to_numeric, errors="coerce")

    scaler = StandardScaler()
    matriz_scaled = scaler.fit_transform(matriz)

    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz_scaled)

    fig, ax = plt.subplots(figsize=(9, 6))

    # -------------------------------------------------
    # IDENTIFICAR ATLETA
    # -------------------------------------------------

    athlete_id_avaliado = None

    if atleta_nome is not None:
        atleta_row = atletas[atletas["nome"] == atleta_nome]

        if not atleta_row.empty:
            athlete_id_avaliado = atleta_row.iloc[0]["athlete_id"]

    # -------------------------------------------------
    # PLOT DOS ATLETAS
    # -------------------------------------------------

    for i in range(len(componentes)):

        if i < len(atletas):
            nome = atletas.iloc[i]["nome"]
            athlete_id = atletas.iloc[i]["athlete_id"]
        else:
            nome = f"A{i}"
            athlete_id = None

        x = componentes[i, 0]
        y = componentes[i, 1]

        if athlete_id == athlete_id_avaliado:

            ax.scatter(
                x,
                y,
                color="darkorange",
                s=350,
                marker="*",
                edgecolor="black",
                label="Atleta Avaliado" if i == 0 else ""
            )

        else:

            ax.scatter(
                x,
                y,
                color="steelblue",
                s=90,
                alpha=0.7,
                label="Base da Academia" if i == 0 else ""
            )

        ax.text(x, y, nome, fontsize=8)

    # -------------------------------------------------
    # EIXOS (FORA DO LOOP!)
    # -------------------------------------------------

    ax.axhline(0, linestyle="--", color="gray")
    ax.axvline(0, linestyle="--", color="gray")

    ax.set_title("Mapa Perceptual — Perfil Técnico dos Atletas")
    ax.set_xlabel("Dimensão Técnica 1")
    ax.set_ylabel("Dimensão Técnica 2")

    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys())

    st.pyplot(fig)



# =====================================================
# 8️⃣ GERAÇÃO DE RELATÓRIO PDF
# =====================================================

def gerar_pdf(
    nome_atleta,
    score_global,
    bjj_score,
    faixa_estimada,
    perfil,
    pontos_fortes,
    melhorias,
    recomendacoes
):

    file_path = f"relatorio_{nome_atleta}_{datetime.now().timestamp()}.pdf"
    if not pontos_fortes:
        
    
        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4
        )
    
        styles = getSampleStyleSheet()
    
        elementos = []

    # -------------------------------------------------
    # TÍTULO
    # -------------------------------------------------

    elementos.append(
        Paragraph("BJJ PERFORMANCE REPORT", styles["Title"])
    )

    elementos.append(Spacer(1,20))


    # -------------------------------------------------
    # PERFIL DO ATLETA
    # -------------------------------------------------

    elementos.append(
        Paragraph("Perfil do Atleta", styles["Heading2"])
    )

    elementos.append(
        Paragraph(f"Nome: {nome_atleta}", styles["Normal"])
    )

    elementos.append(
        Paragraph(f"BJJ Performance Score: {bjj_score}/100", styles["Normal"])
    )

    elementos.append(
        Paragraph(f"Score Global: {round(score_global,2)}", styles["Normal"])
    )

    elementos.append(
        Paragraph(f"Perfil Técnico: {perfil}", styles["Normal"])
    )

    elementos.append(
        Paragraph(f"Faixa Estimada: {faixa_estimada}", styles["Normal"])
    )

    elementos.append(Spacer(1,20))


    # -------------------------------------------------
    # PONTOS FORTES
    # -------------------------------------------------

    elementos.append(
        Paragraph("Pontos Fortes", styles["Heading2"])
    )

    if len(pontos_fortes) == 0:
        elementos.append(
            Paragraph("Nenhum ponto forte identificado.", styles["Normal"])
        )

    for p in pontos_fortes:
        elementos.append(
            Paragraph(f"• {p}", styles["Normal"])
        )

    elementos.append(Spacer(1,20))


    # -------------------------------------------------
    # OPORTUNIDADES DE MELHORIA
    # -------------------------------------------------

    elementos.append(
        Paragraph("Oportunidades de Melhoria", styles["Heading2"])
    )

    if len(melhorias) == 0:
        elementos.append(
            Paragraph("Nenhuma melhoria crítica identificada.", styles["Normal"])
        )

    for m in melhorias:
        elementos.append(
            Paragraph(f"• {m}", styles["Normal"])
        )

    elementos.append(Spacer(1,20))


    # -------------------------------------------------
    # RECOMENDAÇÕES DE TREINO
    # -------------------------------------------------

    elementos.append(
        Paragraph("Recomendação de Treino", styles["Heading2"])
    )

    if len(recomendacoes) == 0:
        elementos.append(
            Paragraph("Treinamento consistente recomendado.", styles["Normal"])
        )

    for r in recomendacoes:
        elementos.append(
            Paragraph(f"• {r}", styles["Normal"])
        )

    elementos.append(Spacer(1,30))


    # -------------------------------------------------
    # CTA COMERCIAL
    # -------------------------------------------------

    elementos.append(
        Paragraph("Treinamento Personalizado", styles["Heading2"])
    )

    elementos.append(
        Paragraph(
            "Deseja evoluir mais rápido no Jiu-Jitsu?",
            styles["Normal"]
        )
    )

    elementos.append(
        Paragraph(
            "Entre em contato para aulas particulares com nossos professores.",
            styles["Normal"]
        )
    )

    elementos.append(
        Paragraph(
            "WhatsApp: (11) 9 8987-3132",
            styles["Normal"]
        )
    )


    doc.build(elementos)

    return file_path

# =====================================================
# 9️⃣ MENU DO SISTEMA
# =====================================================

if "menu" not in st.session_state:
    st.session_state.menu = "Nova Avaliação"

menu = st.sidebar.selectbox(

    "Menu",

    [
        "Nova Avaliação"
    ]

)


# =====================================================
# CONTROLE DE ETAPAS
# =====================================================

if "etapa" not in st.session_state:
    st.session_state.etapa = 1

# =====================================================
# 🔟 CADASTRO DO ATLETA
# =====================================================

if menu == "Nova Avaliação":

    if st.session_state.etapa == 1:

        st.header("Cadastro do Atleta")

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

            else:

                st.warning("Preencha nome e sobrenome.")


# =====================================================
# 1️⃣1️⃣ QUESTIONÁRIO
# =====================================================

    if st.session_state.etapa == 2:

        st.header("Questionário Técnico")

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

                respostas.append(
                    st.slider(p,0,100,50,step=5)
                )

            submitted = st.form_submit_button("Finalizar Avaliação")

        if submitted:

            forca, tecnica, guarda, passagem, condicionamento, tempo_reacao, estrategia, score = calcular_scores(respostas)

bjj_score = calcular_bjj_score(
    forca,
    tecnica,
    guarda,
    passagem,
    condicionamento,
    tempo_reacao,
    estrategia
)

faixa_estimada = estimar_faixa(score, st.session_state.tempo)

add_athlete(
        st.session_state.nome,
        st.session_state.sobrenome,
        st.session_state.faixa,
        st.session_state.tempo
    )

df = get_athletes()
atleta_id = df.iloc[-1]["athlete_id"]

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

    # -----------------------------
    # RESULTADOS
    # -----------------------------

st.write("Score:", round(score, 2))
st.write("Faixa estimada:", faixa_estimada)

st.divider()

    # KPI PRINCIPAL
st.metric("BJJ Performance Score", f"{bjj_score}/100")

    # -----------------------------
    # PCA + PERFIL
    # -----------------------------

pc1, pc2 = plot_pca(
        forca, tecnica, guarda, passagem,
        condicionamento, tempo_reacao, estrategia
    )

perfil = classificar_perfil(pc1, pc2)

pontos_fortes, melhorias, recomendacoes = gerar_diagnostico(
        forca, tecnica, guarda, passagem,
        condicionamento, tempo_reacao, estrategia
    )

    # -----------------------------
    # FICHA TÉCNICA
    # -----------------------------

st.divider()
st.subheader("Ficha Técnica do Atleta")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("BJJ Score", f"{bjj_score}/100")

with col2:
    st.metric("Score Global", round(score,2))

with col3:
    st.metric("Faixa Estimada", faixa_estimada)

    # -----------------------------
    # TABS
    # -----------------------------

st.divider()
st.subheader("Análise Técnica")

tab1,tab2,tab3,tab4,tab5 = st.tabs([
    "Radar Técnico",
    "Scouting Map",
    "Style Profile",
    "Heatmap Academia",
    "Mapa Perceptual"
])

with tab1:
    plot_radar_comparativo(forca, tecnica, guarda, passagem)

with tab2:
    plot_pca(
    forca, tecnica, guarda, passagem,
    condicionamento, tempo_reacao, estrategia
    )

with tab3:
    plot_style_profile(pc1, pc2)

with tab4:
    plot_heatmap()

with tab5:
    plot_perceptual_map(st.session_state.nome)

    # -----------------------------
    # PDF
    # -----------------------------

    pdf = gerar_pdf(
        st.session_state.nome,
        score,
        bjj_score,
        faixa_estimada,
        perfil,
        pontos_fortes,
        melhorias,
        recomendacoes
    )

    with open(pdf,"rb") as f:
        st.download_button("Baixar Relatório PDF", f, "BJJ_Report.pdf")
