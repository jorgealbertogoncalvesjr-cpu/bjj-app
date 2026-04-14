# =====================================================
# 1️⃣ IMPORTS
# =====================================================

import streamlit as st
import pandas as pd
import gspread
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import base64
import os
import io
import json
import re
import requests
from datetime import datetime
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from matplotlib.patches import Ellipse

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, HRFlowable
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT


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
# 3️⃣ HIERARQUIA DE FAIXAS
# =====================================================

# Ordem numérica das faixas (incluindo intermediárias)
FAIXAS_ORDEM = {
    "Branca":         0,
    "Branca/Azul":    1,
    "Azul":           2,
    "Azul/Roxa":      3,
    "Roxa":           4,
    "Roxa/Marrom":    5,
    "Marrom":         6,
    "Marrom/Preta":   7,
    "Preta":          8,
}

# Faixas base (sem intermediárias) — para cadastro e regras da federação
FAIXAS_BASE = ["Branca", "Azul", "Roxa", "Marrom", "Preta"]

# Faixas que aparecem como resultado de estimativa (inclui intermediárias)
FAIXAS_RESULTADO = [
    "Branca", "Branca/Azul", "Azul", "Azul/Roxa",
    "Roxa", "Roxa/Marrom", "Marrom", "Marrom/Preta", "Preta"
]

# Cores visuais para cada faixa
FAIXAS_CORES = {
    "Branca":         "#FFFFFF",
    "Branca/Azul":    "#ADD8E6",
    "Azul":           "#1565C0",
    "Azul/Roxa":      "#6A1B9A",
    "Roxa":           "#6A1B9A",
    "Roxa/Marrom":    "#5D4037",
    "Marrom":         "#4E342E",
    "Marrom/Preta":   "#212121",
    "Preta":          "#000000",
}

# Tempo mínimo (meses) por faixa — regras da federação (CBJJ)
TEMPO_MINIMO_FAIXA = {
    "Branca":         0,
    "Branca/Azul":    6,
    "Azul":           12,
    "Azul/Roxa":      30,
    "Roxa":           36,
    "Roxa/Marrom":    54,
    "Marrom":         60,   # Marrom requer ~5 anos de Jiu-Jitsu
    "Marrom/Preta":   66,
    "Preta":          72,   # Requer ao menos 6 anos na arte
}

# Score mínimo por faixa
SCORE_MINIMO_FAIXA = {
    "Branca":         0,
    "Branca/Azul":    25,
    "Azul":           40,
    "Azul/Roxa":      47,
    "Roxa":           55,
    "Roxa/Marrom":    62,
    "Marrom":         70,
    "Marrom/Preta":   78,
    "Preta":          85,
}


# =====================================================
# 4️⃣ CONEXÃO GOOGLE SHEETS
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
# 5️⃣ FUNÇÕES DE BANCO DE DADOS
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
        "forca_score", "tecnica_score", "guarda_score",
        "passagem_score", "condicionamento_score",
        "tempo_reacao_score", "estrategia_score"
    ]].mean(axis=1)
    return df


def athlete_has_evaluation(athlete_id, df_scores):
    """Verifica se atleta já realizou ao menos uma avaliação."""
    if df_scores.empty:
        return False
    return athlete_id in df_scores["athlete_id"].values


# =====================================================
# 6️⃣ FUNÇÕES ANALÍTICAS
# =====================================================

def calcular_scores(respostas):
    forca          = float(np.mean(respostas[0:3]))
    tecnica        = float(np.mean(respostas[3:6]))
    guarda         = float(np.mean(respostas[6:9]))
    passagem       = float(np.mean(respostas[9:12]))
    condicionamento = float(np.mean(respostas[12:15]))
    tempo_reacao   = float(np.mean(respostas[15:18]))
    estrategia     = float(np.mean(respostas[18:20]))
    score_global   = float(np.mean([
        forca, tecnica, guarda, passagem,
        condicionamento, tempo_reacao, estrategia
    ]))
    return (forca, tecnica, guarda, passagem,
            condicionamento, tempo_reacao, estrategia, score_global)


def calcular_bjj_score(forca, tecnica, guarda, passagem,
                       condicionamento, tempo_reacao, estrategia):
    score = (
        forca          * 0.15 +
        tecnica        * 0.20 +
        guarda         * 0.15 +
        passagem       * 0.20 +
        condicionamento * 0.10 +
        tempo_reacao   * 0.10 +
        estrategia     * 0.10
    )
    return round(score, 2)


def indice_faixa(faixa: str) -> int:
    return FAIXAS_ORDEM.get(faixa, 0)


def estimar_faixa(score: float, tempo: float, faixa_atual: str) -> str:
    """
    Estima a faixa do atleta considerando:
    1. Score + tempo mínimo (regra da federação)
    2. Faixas intermediárias (ex: Branca/Azul)
    3. Trava: resultado nunca pode ser menor que a faixa atual
    4. Peso para faixa atual (evita regressão absurda)
    """
    # --- Determinar faixa pelo score + tempo ---
    faixa_por_score = "Branca"
    for f in reversed(FAIXAS_RESULTADO):
        if score >= SCORE_MINIMO_FAIXA[f] and tempo >= TEMPO_MINIMO_FAIXA[f]:
            faixa_por_score = f
            break

    # --- Trava: resultado nunca pode ser ABAIXO da faixa atual ---
    idx_atual   = indice_faixa(faixa_atual)
    idx_score   = indice_faixa(faixa_por_score)

    # Peso para faixa atual: se o score sugere faixa abaixo da atual,
    # mantemos a atual; se sugere acima, mantemos o resultado calculado.
    if idx_score < idx_atual:
        faixa_estimada = faixa_atual
    else:
        faixa_estimada = faixa_por_score

    return faixa_estimada


def classificar_nivel(score):
    if score >= 85:
        return "Elite"
    elif 70 <= score < 85:
        return "Avançado"
    elif 55 <= score < 70:
        return "Intermediário"
    else:
        return "Iniciante"


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
# 7️⃣ DIAGNÓSTICO AUTOMÁTICO
# =====================================================

def gerar_diagnostico(forca, tecnica, guarda, passagem,
                      condicionamento, tempo_reacao, estrategia):
    pontos_fortes = []
    melhorias     = []
    recomendacoes = []

    # Pontos fortes
    if tecnica        >= 70: pontos_fortes.append("Boa eficiência técnica — minimiza esforço e maximiza resultado.")
    if passagem       >= 70: pontos_fortes.append("Passagem de guarda consistente e variada.")
    if guarda         >= 70: pontos_fortes.append("Jogo de guarda sólido e criativo.")
    if estrategia     >= 70: pontos_fortes.append("Boa leitura estratégica da luta e timing apurado.")
    if forca          >= 70: pontos_fortes.append("Boa base de força funcional aplicada ao Jiu-Jitsu.")
    if condicionamento >= 70: pontos_fortes.append("Condicionamento físico acima da média.")
    if tempo_reacao   >= 70: pontos_fortes.append("Tempo de reação rápido — responde bem sob pressão.")

    # Oportunidades de melhoria
    if guarda         < 50: melhorias.append("Jogo de guarda precisa de desenvolvimento (score: {:.0f}/100).".format(guarda))
    if condicionamento < 50: melhorias.append("Condicionamento físico abaixo do ideal (score: {:.0f}/100).".format(condicionamento))
    if tempo_reacao   < 50: melhorias.append("Tempo de reação pode ser aprimorado (score: {:.0f}/100).".format(tempo_reacao))
    if estrategia     < 50: melhorias.append("Tomada de decisão durante a luta requer atenção (score: {:.0f}/100).".format(estrategia))
    if tecnica        < 50: melhorias.append("Eficiência técnica abaixo do esperado (score: {:.0f}/100).".format(tecnica))
    if passagem       < 50: melhorias.append("Passagem de guarda precisa evoluir (score: {:.0f}/100).".format(passagem))

    # Recomendações de treino
    if guarda         < 60: recomendacoes.append("Treinar raspagens, retenção de guarda e guardas abertas (laço, aranha, De La Riva).")
    if passagem       < 60: recomendacoes.append("Aprimorar sequências de passagem: torreando, leg-drag e X-pass.")
    if condicionamento < 60: recomendacoes.append("Aumentar rounds de treino (>5 min), inserir drills de resistência e exercícios aeróbicos específicos.")
    if tecnica        < 60: recomendacoes.append("Reforçar fundamentos técnicos: entradas para quedas, finalizações da montada e costas.")
    if forca          < 50: recomendacoes.append("Trabalhar força funcional — kettlebell, suspensão e explosão de quadril.")
    if tempo_reacao   < 50: recomendacoes.append("Praticar drills de reação: sparring com adversários de faixa superior.")
    if estrategia     < 50: recomendacoes.append("Analisar lutas gravadas. Identificar padrões e desenvolver game-plan.")

    return pontos_fortes, melhorias, recomendacoes


# =====================================================
# 8️⃣ ANÁLISE IA (Anthropic API)
# =====================================================

def gerar_analise_ia(
    nome, faixa_atual, faixa_estimada, nivel,
    perfil, bjj_score, score_global,
    forca, tecnica, guarda, passagem,
    condicionamento, tempo_reacao, estrategia,
    pontos_fortes, melhorias, recomendacoes
):
    """Chama Claude para gerar análise narrativa personalizada do atleta."""
    try:
        api_key = st.secrets.get("anthropic_api_key", "")
        if not api_key:
            return None

        prompt = f"""Você é um professor de Jiu-Jitsu brasileiro especialista em análise de performance.

Gere uma análise técnica personalizada e motivadora para o atleta abaixo. 
Escreva em português, de forma direta e profissional. Máximo 4 parágrafos curtos.

DADOS DO ATLETA:
- Nome: {nome}
- Faixa atual: {faixa_atual}
- Faixa estimada pela avaliação: {faixa_estimada}
- Nível técnico: {nivel}
- Perfil de luta: {perfil}
- BJJ Score: {bjj_score}/100
- Score Global: {round(score_global, 1)}/100

SCORES POR DIMENSÃO (0-100):
- Força: {round(forca, 1)}
- Técnica: {round(tecnica, 1)}
- Guarda: {round(guarda, 1)}
- Passagem de guarda: {round(passagem, 1)}
- Condicionamento: {round(condicionamento, 1)}
- Tempo de reação: {round(tempo_reacao, 1)}
- Estratégia: {round(estrategia, 1)}

PONTOS FORTES IDENTIFICADOS: {', '.join(pontos_fortes) if pontos_fortes else 'Nenhum destacado ainda'}
ÁREAS DE MELHORIA: {', '.join(melhorias) if melhorias else 'Nenhuma crítica'}

Inclua:
1. Uma avaliação geral do atleta com base no perfil de luta e scores
2. O que mais se destaca positivamente
3. O principal foco de desenvolvimento para o próximo ciclo
4. Uma mensagem motivacional personalizada para o atleta
"""

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": "claude-opus-4-5",
            "max_tokens": 600,
            "messages": [{"role": "user", "content": prompt}]
        }

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=30
        )

        if resp.status_code == 200:
            data = resp.json()
            return data["content"][0]["text"]
        else:
            return None

    except Exception:
        return None


# =====================================================
# 9️⃣ CONFIDENCE ELLIPSE
# =====================================================

def draw_confidence_ellipse(x, y, ax, n_std=2.0):
    if len(x) < 2:
        return
    cov = np.cov(x, y)
    den = np.sqrt(cov[0, 0] * cov[1, 1])
    if den == 0:
        return
    pearson = cov[0, 1] / den
    ell_radius_x = np.sqrt(1 + pearson)
    ell_radius_y = np.sqrt(1 - pearson)
    ellipse = Ellipse(
        (0, 0),
        width=ell_radius_x * 2,
        height=ell_radius_y * 2,
        fill=False,
        linestyle="--",
        edgecolor="blue",
        linewidth=2,
        label="Zona da Academia"
    )
    scale_x = np.sqrt(cov[0, 0]) * n_std
    scale_y = np.sqrt(cov[1, 1]) * n_std
    mean_x  = np.mean(x)
    mean_y  = np.mean(y)
    transf  = (
        plt.matplotlib.transforms.Affine2D()
        .rotate_deg(45)
        .scale(scale_x, scale_y)
        .translate(mean_x, mean_y)
    )
    ellipse.set_transform(transf + ax.transData)
    ax.add_patch(ellipse)


# =====================================================
# 🔟 GRÁFICOS
# =====================================================

def fig_to_buffer(fig):
    """Converte figura matplotlib para bytes (para PDF)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    return buf


def plot_pca(forca, tecnica, guarda, passagem,
             condicionamento, tempo_reacao, estrategia):
    df = get_scores_df()
    if df.empty or len(df) < 2:
        st.warning("PCA requer mínimo 2 avaliações.")
        return 0, 0

    matriz = df[[
        "forca_score", "tecnica_score", "guarda_score",
        "passagem_score", "condicionamento_score",
        "tempo_reacao_score", "estrategia_score",
    ]].astype(float)

    scaler = StandardScaler()
    matriz_scaled = scaler.fit_transform(matriz)

    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz_scaled)

    df["PC1"] = componentes[:, 0]
    df["PC2"] = componentes[:, 1]

    novo = scaler.transform([[
        forca, tecnica, guarda, passagem,
        condicionamento, tempo_reacao, estrategia
    ]])
    novo = pca.transform(novo)
    pc1 = novo[0][0]
    pc2 = novo[0][1]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(df["PC1"], df["PC2"], color="lightgray", alpha=0.6, s=80, label="Base de atletas")
    ax.scatter(pc1, pc2, color="darkorange", edgecolor="black", s=350, marker="*", label="Atleta Avaliado")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.axhline(0, linestyle="--", color="gray")
    ax.axvline(0, linestyle="--", color="gray")
    ax.set_title("Mapa Técnico — PCA Scouting")
    ax.set_xlabel("Passagem ← → Guarda")
    ax.set_ylabel("Força ← → Técnica")
    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)
    ax.legend()
    st.pyplot(fig)
    plt.close(fig)
    return pc1, pc2


def plot_pca_buf(forca, tecnica, guarda, passagem,
                 condicionamento, tempo_reacao, estrategia):
    """Versão que retorna buffer (para PDF)."""
    df = get_scores_df()
    if df.empty or len(df) < 2:
        return None, 0, 0

    matriz = df[[
        "forca_score", "tecnica_score", "guarda_score",
        "passagem_score", "condicionamento_score",
        "tempo_reacao_score", "estrategia_score",
    ]].astype(float)

    scaler = StandardScaler()
    matriz_scaled = scaler.fit_transform(matriz)
    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz_scaled)
    df["PC1"] = componentes[:, 0]
    df["PC2"] = componentes[:, 1]
    novo = scaler.transform([[forca, tecnica, guarda, passagem, condicionamento, tempo_reacao, estrategia]])
    novo = pca.transform(novo)
    pc1 = novo[0][0]
    pc2 = novo[0][1]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(df["PC1"], df["PC2"], color="lightgray", alpha=0.6, s=60, label="Base de atletas")
    ax.scatter(pc1, pc2, color="darkorange", edgecolor="black", s=250, marker="*", label="Atleta Avaliado")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.axhline(0, linestyle="--", color="gray")
    ax.axvline(0, linestyle="--", color="gray")
    ax.set_title("Mapa Técnico — PCA Scouting")
    ax.set_xlabel("Passagem ← → Guarda")
    ax.set_ylabel("Força ← → Técnica")
    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)
    ax.legend()
    buf = fig_to_buffer(fig)
    plt.close(fig)
    return buf, pc1, pc2


def plot_style_profile(pc1, pc2):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.axhline(0, color="gray", linestyle="--")
    ax.axvline(0, color="gray", linestyle="--")
    ax.scatter(pc1, pc2, s=300, color="darkorange", edgecolor="black")
    ax.text( 2,  2, "Passador Técnico",  fontsize=9, ha="center")
    ax.text(-2,  2, "Guardeiro Técnico", fontsize=9, ha="center")
    ax.text(-2, -2, "Guardeiro Físico",  fontsize=9, ha="center")
    ax.text( 2, -2, "Passador Pressão",  fontsize=9, ha="center")
    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)
    ax.set_title("BJJ Style Profile")
    ax.set_xlabel("Passagem  ← →  Guarda")
    ax.set_ylabel("Força  ← →  Técnica")
    st.pyplot(fig)
    buf = fig_to_buffer(fig)
    plt.close(fig)
    return buf


def plot_radar_comparativo(forca, tecnica, guarda, passagem,
                           condicionamento, tempo_reacao, estrategia):
    df = get_scores_df()
    if df.empty:
        return None

    df = df.apply(pd.to_numeric, errors="coerce")

    categorias = ["Força", "Técnica", "Guarda", "Passagem", "Cond.", "Reação", "Estratégia"]
    atleta = [forca, tecnica, guarda, passagem, condicionamento, tempo_reacao, estrategia]
    media  = [
        df["forca_score"].mean(),
        df["tecnica_score"].mean(),
        df["guarda_score"].mean(),
        df["passagem_score"].mean(),
        df["condicionamento_score"].mean(),
        df["tempo_reacao_score"].mean(),
        df["estrategia_score"].mean()
    ]

    atleta += atleta[:1]
    media  += media[:1]
    angles  = np.linspace(0, 2 * np.pi, len(categorias), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(subplot_kw=dict(polar=True), figsize=(6, 6))
    ax.plot(angles, atleta, linewidth=3, label="Atleta", color="darkorange")
    ax.fill(angles, atleta, alpha=0.25, color="darkorange")
    ax.plot(angles, media, linestyle="dashed", label="Média Academia", color="steelblue")
    ax.fill(angles, media, alpha=0.1, color="steelblue")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categorias, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_title("Radar Técnico Comparativo", pad=15)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    st.pyplot(fig)
    buf = fig_to_buffer(fig)
    plt.close(fig)
    return buf


def plot_heatmap():
    df = get_scores_df()
    atletas = get_athletes()
    if df.empty:
        return None

    matriz = df[[
        "forca_score", "tecnica_score", "guarda_score",
        "passagem_score", "condicionamento_score",
        "tempo_reacao_score", "estrategia_score"
    ]].copy()

    nomes = []
    for i in range(len(matriz)):
        if i < len(atletas):
            nomes.append(atletas.iloc[i]["nome"])
        else:
            nomes.append(f"A{i}")

    if len(nomes) == len(matriz):
        matriz.index = nomes

    matriz = matriz.apply(pd.to_numeric, errors="coerce").round(0)
    matriz.columns = ["Força", "Técnica", "Guarda", "Passagem", "Cond.", "Reação", "Estratégia"]
    matriz["média"] = matriz.mean(axis=1)
    matriz = matriz.sort_values("média", ascending=False).head(10)
    matriz = matriz.drop(columns="média")

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.heatmap(
        matriz, cmap="RdYlGn", annot=True, fmt=".0f",
        vmin=0, vmax=100,
        linewidths=0.5, linecolor="gray", ax=ax,
        cbar_kws={"label": "Score (0–100)"}
    )
    plt.xticks(rotation=30, ha="right")
    plt.yticks(rotation=0)

    for i, nome in enumerate(matriz.index):
        if nome == st.session_state.get("nome", ""):
            ax.get_yticklabels()[i].set_color("darkorange")
            ax.get_yticklabels()[i].set_weight("bold")

    ax.set_title("Heatmap de Competências (Top 10 Atletas)")
    st.pyplot(fig)
    buf = fig_to_buffer(fig)
    plt.close(fig)
    return buf


def plot_perceptual_map(atleta_nome=None):
    df      = get_scores_df()
    atletas = get_athletes()

    if df.empty or len(df) < 2:
        st.warning("Dados insuficientes para o Mapa Perceptual.")
        return None

    matriz = df[[
        "forca_score", "tecnica_score", "guarda_score",
        "passagem_score", "condicionamento_score",
        "tempo_reacao_score", "estrategia_score",
    ]].apply(pd.to_numeric, errors="coerce")

    scaler = StandardScaler()
    matriz_scaled = scaler.fit_transform(matriz)
    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz_scaled)

    fig, ax = plt.subplots(figsize=(9, 6))

    athlete_id_avaliado = None
    if atleta_nome is not None:
        row = atletas[atletas["nome"] == atleta_nome]
        if not row.empty:
            athlete_id_avaliado = row.iloc[0]["athlete_id"]

    for i in range(len(componentes)):
        if i < len(atletas):
            nome       = atletas.iloc[i]["nome"]
            athlete_id = atletas.iloc[i]["athlete_id"]
        else:
            nome       = f"A{i}"
            athlete_id = None

        x = componentes[i, 0]
        y = componentes[i, 1]

        if athlete_id == athlete_id_avaliado:
            ax.scatter(x, y, color="darkorange", s=350, marker="*",
                       edgecolor="black",
                       label="Atleta Avaliado" if i == 0 else "")
        else:
            ax.scatter(x, y, color="steelblue", s=90, alpha=0.7,
                       label="Base da Academia" if i == 0 else "")

        ax.text(x + 0.05, y + 0.05, nome, fontsize=8)

    ax.axhline(0, linestyle="--", color="gray")
    ax.axvline(0, linestyle="--", color="gray")
    ax.set_title("Mapa Perceptual — Perfil Técnico dos Atletas")
    ax.set_xlabel("Dimensão Técnica 1")
    ax.set_ylabel("Dimensão Técnica 2")

    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys())

    st.pyplot(fig)
    buf = fig_to_buffer(fig)
    plt.close(fig)
    return buf


def plot_evolucao_atleta(athlete_id):
    """Gráfico de evolução temporal do atleta."""
    hist = get_athlete_history(athlete_id)
    if hist.empty or len(hist) < 2:
        st.info("Histórico insuficiente para gráfico de evolução (mínimo 2 avaliações).")
        return None

    hist = hist.sort_values("data")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(hist["data"], hist["score_total"], marker="o",
            color="darkorange", linewidth=2.5, markersize=8)
    ax.fill_between(hist["data"], hist["score_total"], alpha=0.15, color="darkorange")
    ax.set_ylim(0, 100)
    ax.set_title("Evolução do Score ao Longo do Tempo")
    ax.set_xlabel("Data da Avaliação")
    ax.set_ylabel("Score Médio")
    ax.grid(True, linestyle="--", alpha=0.4)
    plt.xticks(rotation=30, ha="right")
    st.pyplot(fig)
    buf = fig_to_buffer(fig)
    plt.close(fig)
    return buf


def plot_barras_dimensoes(forca, tecnica, guarda, passagem,
                          condicionamento, tempo_reacao, estrategia):
    """Gráfico de barras horizontais com scores por dimensão."""
    dimensoes = ["Força", "Técnica", "Guarda", "Passagem",
                 "Condicionamento", "Tempo Reação", "Estratégia"]
    valores   = [forca, tecnica, guarda, passagem,
                 condicionamento, tempo_reacao, estrategia]

    cores = ["#2ecc71" if v >= 70 else "#e67e22" if v >= 50 else "#e74c3c" for v in valores]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.barh(dimensoes, valores, color=cores, height=0.6)

    for bar, val in zip(bars, valores):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}", va="center", fontsize=9)

    ax.set_xlim(0, 110)
    ax.set_xlabel("Score (0–100)")
    ax.set_title("Scores por Dimensão")
    ax.axvline(70, linestyle="--", color="green", alpha=0.5, label="Meta 70")
    ax.axvline(50, linestyle="--", color="orange", alpha=0.5, label="Alerta 50")
    ax.legend(fontsize=8)
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    plt.tight_layout()
    st.pyplot(fig)
    buf = fig_to_buffer(fig)
    plt.close(fig)
    return buf


def plot_faixa_gauge(bjj_score, faixa_estimada):
    """Gauge visual indicando o score e a faixa estimada."""
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Faixas coloridas de fundo
    intervalos = [
        (0,  25,  "#FFFFFF", "Branca"),
        (25, 40,  "#ADD8E6", "Branca/Azul"),
        (40, 47,  "#1565C0", "Azul"),
        (47, 55,  "#6A1B9A", "Azul/Roxa"),
        (55, 62,  "#7B1FA2", "Roxa"),
        (62, 70,  "#5D4037", "Roxa/Marrom"),
        (70, 78,  "#4E342E", "Marrom"),
        (78, 85,  "#212121", "Marrom/Preta"),
        (85, 100, "#000000", "Preta"),
    ]
    for (x0, x1, cor, label) in intervalos:
        ax.barh(0.5, x1 - x0, left=x0, height=0.5,
                color=cor, edgecolor="gray", linewidth=0.4, align="center")
        mid = (x0 + x1) / 2
        txt_cor = "white" if cor not in ("#FFFFFF", "#ADD8E6") else "black"
        ax.text(mid, 0.5, label, ha="center", va="center",
                fontsize=6.5, color=txt_cor, rotation=90 if (x1-x0) < 12 else 0)

    # Indicador do atleta
    ax.axvline(bjj_score, color="red", linewidth=3, ymin=0.1, ymax=0.9)
    ax.text(bjj_score, 0.92, f"{bjj_score:.0f}", ha="center",
            va="bottom", fontsize=11, fontweight="bold", color="red")

    ax.set_title(f"Posicionamento: {faixa_estimada}", fontsize=12, pad=10)
    plt.tight_layout()
    st.pyplot(fig)
    buf = fig_to_buffer(fig)
    plt.close(fig)
    return buf


# =====================================================
# 1️⃣1️⃣ GERAÇÃO DE RELATÓRIO PDF
# =====================================================

def gerar_pdf(
    nome_atleta, faixa_atual, tempo_treino,
    score_global, bjj_score, faixa_estimada,
    nivel, perfil,
    pontos_fortes, melhorias, recomendacoes,
    analise_ia,
    forca, tecnica, guarda, passagem,
    condicionamento, tempo_reacao, estrategia,
):
    file_path = f"relatorio_{nome_atleta}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles    = getSampleStyleSheet()
    cor_bjj   = colors.HexColor("#1565C0")
    cor_faixa = colors.HexColor(FAIXAS_CORES.get(faixa_estimada, "#000000"))

    style_title   = ParagraphStyle("titulo",   parent=styles["Title"],   fontSize=20, textColor=cor_bjj, spaceAfter=6)
    style_h2      = ParagraphStyle("h2",       parent=styles["Heading2"], fontSize=13, textColor=cor_bjj, spaceBefore=12, spaceAfter=4)
    style_normal  = ParagraphStyle("normal",   parent=styles["Normal"],  fontSize=10, spaceAfter=3)
    style_bullet  = ParagraphStyle("bullet",   parent=styles["Normal"],  fontSize=10, leftIndent=14, spaceAfter=2)
    style_ia      = ParagraphStyle("ia",       parent=styles["Normal"],  fontSize=10, spaceAfter=3, backColor=colors.HexColor("#F0F4FF"), borderPadding=6)
    style_center  = ParagraphStyle("center",   parent=styles["Normal"],  fontSize=10, alignment=TA_CENTER)

    elementos = []

    # ── Título ────────────────────────────────────────
    elementos.append(Paragraph("🥋 BJJ PERFORMANCE REPORT", style_title))
    elementos.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        style_center
    ))
    elementos.append(HRFlowable(width="100%", thickness=1.5, color=cor_bjj))
    elementos.append(Spacer(1, 12))

    # ── Perfil do Atleta (tabela) ─────────────────────
    elementos.append(Paragraph("Perfil do Atleta", style_h2))

    tabela_dados = [
        ["Nome",           nome_atleta,           "Faixa Atual",      faixa_atual],
        ["Tempo de treino", f"{int(tempo_treino)} meses", "Faixa Estimada",  faixa_estimada],
        ["Nível Técnico",  nivel,                 "Perfil de Luta",   perfil],
        ["BJJ Score",      f"{bjj_score}/100",    "Score Global",     f"{round(score_global,1)}/100"],
    ]

    t = Table(tabela_dados, colWidths=[3.8*cm, 5*cm, 3.8*cm, 5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3F2FD")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#E3F2FD")),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING",    (0, 0), (-1, -1), 4),
    ]))
    elementos.append(t)
    elementos.append(Spacer(1, 14))

    # ── Gauge de Faixa ────────────────────────────────
    try:
        buf_gauge = _gerar_gauge_pdf(bjj_score, faixa_estimada)
        img_gauge = RLImage(buf_gauge, width=16*cm, height=4.5*cm)
        elementos.append(img_gauge)
        elementos.append(Spacer(1, 8))
    except Exception:
        pass

    # ── Radar Técnico ─────────────────────────────────
    elementos.append(Paragraph("Radar Técnico Comparativo", style_h2))
    try:
        buf_radar = _gerar_radar_pdf(
            forca, tecnica, guarda, passagem,
            condicionamento, tempo_reacao, estrategia
        )
        if buf_radar:
            img_radar = RLImage(buf_radar, width=12*cm, height=10*cm)
            elementos.append(img_radar)
    except Exception:
        pass
    elementos.append(Spacer(1, 8))

    # ── Barras de Dimensões ───────────────────────────
    elementos.append(Paragraph("Scores por Dimensão", style_h2))
    try:
        buf_barras = _gerar_barras_pdf(
            forca, tecnica, guarda, passagem,
            condicionamento, tempo_reacao, estrategia
        )
        img_barras = RLImage(buf_barras, width=14*cm, height=7*cm)
        elementos.append(img_barras)
    except Exception:
        pass
    elementos.append(Spacer(1, 10))

    # ── Análise por IA ────────────────────────────────
    if analise_ia:
        elementos.append(Paragraph("Análise Técnica — IA", style_h2))
        elementos.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        elementos.append(Spacer(1, 4))
        for para in analise_ia.split("\n"):
            if para.strip():
                elementos.append(Paragraph(para.strip(), style_ia))
        elementos.append(Spacer(1, 12))

    # ── Pontos Fortes ─────────────────────────────────
    elementos.append(Paragraph("✅ Pontos Fortes", style_h2))
    if not pontos_fortes:
        elementos.append(Paragraph("Nenhum ponto forte identificado ainda.", style_normal))
    for p in pontos_fortes:
        elementos.append(Paragraph(f"• {p}", style_bullet))
    elementos.append(Spacer(1, 8))

    # ── Oportunidades de Melhoria ─────────────────────
    elementos.append(Paragraph("⚠️ Oportunidades de Melhoria", style_h2))
    if not melhorias:
        elementos.append(Paragraph("Nenhuma melhoria crítica identificada.", style_normal))
    for m in melhorias:
        elementos.append(Paragraph(f"• {m}", style_bullet))
    elementos.append(Spacer(1, 8))

    # ── Recomendações de Treino ───────────────────────
    elementos.append(Paragraph("🎯 Recomendação de Treino", style_h2))
    if not recomendacoes:
        elementos.append(Paragraph("Treinamento consistente recomendado.", style_normal))
    for r in recomendacoes:
        elementos.append(Paragraph(f"• {r}", style_bullet))
    elementos.append(Spacer(1, 20))

    # ── CTA ───────────────────────────────────────────
    elementos.append(HRFlowable(width="100%", thickness=1, color=cor_bjj))
    elementos.append(Spacer(1, 8))
    elementos.append(Paragraph("Treinamento Personalizado", style_h2))
    elementos.append(Paragraph(
        "Quer evoluir mais rápido no Jiu-Jitsu? Fale com nossos professores.",
        style_normal
    ))
    elementos.append(Paragraph("📱 WhatsApp: (11) 9 8987-3132", style_normal))

    doc.build(elementos)
    return file_path


# Funções auxiliares de geração de gráficos só para o PDF (sem st.pyplot)

def _gerar_radar_pdf(forca, tecnica, guarda, passagem,
                     condicionamento, tempo_reacao, estrategia):
    df = get_scores_df()
    if df.empty:
        return None
    df = df.apply(pd.to_numeric, errors="coerce")
    categorias = ["Força", "Técnica", "Guarda", "Passagem", "Cond.", "Reação", "Estratégia"]
    atleta = [forca, tecnica, guarda, passagem, condicionamento, tempo_reacao, estrategia]
    media  = [
        df["forca_score"].mean(), df["tecnica_score"].mean(),
        df["guarda_score"].mean(), df["passagem_score"].mean(),
        df["condicionamento_score"].mean(), df["tempo_reacao_score"].mean(),
        df["estrategia_score"].mean()
    ]
    atleta += atleta[:1]; media += media[:1]
    angles = np.linspace(0, 2 * np.pi, len(categorias), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(subplot_kw=dict(polar=True), figsize=(5, 5))
    ax.plot(angles, atleta, linewidth=2.5, color="darkorange", label="Atleta")
    ax.fill(angles, atleta, alpha=0.2, color="darkorange")
    ax.plot(angles, media, linestyle="dashed", color="steelblue", label="Média Academia")
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(categorias, fontsize=8)
    ax.set_ylim(0, 100); ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)
    buf = fig_to_buffer(fig); plt.close(fig)
    return buf


def _gerar_barras_pdf(forca, tecnica, guarda, passagem,
                      condicionamento, tempo_reacao, estrategia):
    dimensoes = ["Força", "Técnica", "Guarda", "Passagem", "Condic.", "Reação", "Estratégia"]
    valores   = [forca, tecnica, guarda, passagem, condicionamento, tempo_reacao, estrategia]
    cores     = ["#2ecc71" if v >= 70 else "#e67e22" if v >= 50 else "#e74c3c" for v in valores]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.barh(dimensoes, valores, color=cores, height=0.55)
    for bar, val in zip(bars, valores):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}", va="center", fontsize=8)
    ax.set_xlim(0, 110); ax.set_xlabel("Score (0–100)", fontsize=8)
    ax.axvline(70, linestyle="--", color="green", alpha=0.5)
    ax.axvline(50, linestyle="--", color="orange", alpha=0.5)
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    plt.tight_layout()
    buf = fig_to_buffer(fig); plt.close(fig)
    return buf


def _gerar_gauge_pdf(bjj_score, faixa_estimada):
    fig, ax = plt.subplots(figsize=(8, 2.5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 1); ax.axis("off")
    intervalos = [
        (0,  25,  "#FFFFFF", "Branca"),
        (25, 40,  "#ADD8E6", "Bca/Azul"),
        (40, 47,  "#1565C0", "Azul"),
        (47, 55,  "#7B1FA2", "Azl/Roxa"),
        (55, 62,  "#9C27B0", "Roxa"),
        (62, 70,  "#5D4037", "Rxa/Mrm"),
        (70, 78,  "#4E342E", "Marrom"),
        (78, 85,  "#212121", "Mrm/Pta"),
        (85, 100, "#000000", "Preta"),
    ]
    for (x0, x1, cor, label) in intervalos:
        ax.barh(0.5, x1 - x0, left=x0, height=0.6,
                color=cor, edgecolor="gray", linewidth=0.3, align="center")
        mid     = (x0 + x1) / 2
        txt_cor = "white" if cor not in ("#FFFFFF", "#ADD8E6") else "black"
        ax.text(mid, 0.5, label, ha="center", va="center",
                fontsize=6.5, color=txt_cor,
                rotation=90 if (x1-x0) < 10 else 0)
    ax.axvline(bjj_score, color="red", linewidth=2.5, ymin=0.05, ymax=0.95)
    ax.text(bjj_score, 0.93, f"{bjj_score:.0f}", ha="center",
            va="bottom", fontsize=10, fontweight="bold", color="red")
    ax.set_title(f"Posicionamento na Escala: {faixa_estimada}", fontsize=10, pad=6)
    plt.tight_layout()
    buf = fig_to_buffer(fig); plt.close(fig)
    return buf


# =====================================================
# 1️⃣2️⃣ MENU DO SISTEMA
# =====================================================

if "menu" not in st.session_state:
    st.session_state.menu = "Nova Avaliação"

menu = st.sidebar.selectbox(
    "Menu",
    ["Nova Avaliação", "Histórico de Atletas"]
)


# =====================================================
# CONTROLE DE ETAPAS
# =====================================================

if "etapa" not in st.session_state:
    st.session_state.etapa = 1


# =====================================================
# 📋 HISTÓRICO DE ATLETAS
# =====================================================

if menu == "Histórico de Atletas":

    st.header("📋 Histórico de Atletas")

    atletas    = get_athletes()
    df_scores  = get_scores_df()

    if atletas.empty:
        st.warning("Nenhum atleta cadastrado.")
        st.stop()

    # ── Filtros ───────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        filtro_faixa = st.multiselect(
            "Filtrar por faixa",
            options=FAIXAS_BASE,
            default=FAIXAS_BASE
        )

    with col2:
        apenas_avaliados = st.checkbox("Apenas atletas com avaliação", value=False)

    with col3:
        busca_nome = st.text_input("Buscar por nome")

    # Aplica filtros
    df_filtrado = atletas.copy()

    if filtro_faixa:
        df_filtrado = df_filtrado[df_filtrado["faixa"].isin(filtro_faixa)]

    if apenas_avaliados and not df_scores.empty:
        ids_avaliados = df_scores["athlete_id"].unique()
        df_filtrado = df_filtrado[df_filtrado["athlete_id"].isin(ids_avaliados)]

    if busca_nome:
        df_filtrado = df_filtrado[
            df_filtrado["nome"].str.contains(busca_nome, case=False, na=False) |
            df_filtrado["sobrenome"].str.contains(busca_nome, case=False, na=False)
        ]

    st.markdown(f"**{len(df_filtrado)} atleta(s) encontrado(s)**")

    if df_filtrado.empty:
        st.info("Nenhum atleta corresponde aos filtros selecionados.")
        st.stop()

    for _, row in df_filtrado.iterrows():
        athlete_id = row["athlete_id"]
        has_eval   = athlete_has_evaluation(athlete_id, df_scores)

        badge = "✅" if has_eval else "⏳"
        with st.expander(f"{badge} {row['nome']} {row['sobrenome']} — Faixa: {row['faixa']}"):
            st.write(f"**Faixa:** {row['faixa']} | **Tempo de treino:** {row['tempo']} meses")
            st.write(f"**Cadastrado em:** {row.get('data_cadastro', '—')}")

            if has_eval:
                hist = get_athlete_history(athlete_id)
                if not hist.empty:
                    ultima = hist.sort_values("data").iloc[-1]
                    st.metric("Último Score", f"{ultima['score_total']:.1f}/100")

                if len(hist) >= 2:
                    st.subheader("Evolução")
                    plot_evolucao_atleta(athlete_id)
            else:
                st.info("Este atleta ainda não realizou avaliação.")


# =====================================================
# 🆕 NOVA AVALIAÇÃO
# =====================================================

if menu == "Nova Avaliação":

    # ── ETAPA 1: Cadastro ─────────────────────────────
    if st.session_state.etapa == 1:

        st.header("Cadastro do Atleta")

        atletas   = get_athletes()
        df_scores = get_scores_df()

        # Opção: reavaliar atleta existente
        opcao = st.radio("Atleta", ["Novo atleta", "Atleta já cadastrado"], horizontal=True)

        if opcao == "Atleta já cadastrado" and not atletas.empty:
            nomes_lista = atletas.apply(lambda r: f"{r['nome']} {r['sobrenome']}", axis=1).tolist()
            selecionado = st.selectbox("Selecionar atleta", nomes_lista)
            idx = nomes_lista.index(selecionado)
            row = atletas.iloc[idx]

            st.info(f"Faixa atual: **{row['faixa']}** | Tempo: **{row['tempo']} meses**")
            has_eval = athlete_has_evaluation(row["athlete_id"], df_scores)
            if has_eval:
                st.success("✅ Este atleta já possui avaliação anterior.")

            if st.button("Iniciar Reavaliação"):
                st.session_state.nome        = row["nome"]
                st.session_state.sobrenome   = row["sobrenome"]
                st.session_state.faixa       = row["faixa"]
                st.session_state.tempo       = row["tempo"]
                st.session_state.athlete_id  = row["athlete_id"]
                st.session_state.novo_atleta = False
                st.session_state.etapa       = 2
                st.rerun()

        else:
            nome      = st.text_input("Nome")
            sobrenome = st.text_input("Sobrenome")

            faixa = st.selectbox("Faixa atual", FAIXAS_BASE)

            tempo = st.number_input("Tempo de treino (meses)", min_value=0)

            if st.button("Iniciar Avaliação"):
                if nome and sobrenome:
                    st.session_state.nome        = nome
                    st.session_state.sobrenome   = sobrenome
                    st.session_state.faixa       = faixa
                    st.session_state.tempo       = tempo
                    st.session_state.novo_atleta = True
                    st.session_state.etapa       = 2
                    st.rerun()
                else:
                    st.warning("Preencha nome e sobrenome.")

    # ── ETAPA 2: Questionário ─────────────────────────
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
            "Finalizo após passar guarda.",
        ]

        respostas = []

        with st.form("avaliacao"):
            for p in perguntas:
                respostas.append(st.slider(p, 0, 100, 50, step=5))

            submitted = st.form_submit_button("Finalizar Avaliação")

        if submitted:

            (forca, tecnica, guarda, passagem,
             condicionamento, tempo_reacao,
             estrategia, score) = calcular_scores(respostas)

            bjj_score = calcular_bjj_score(
                forca, tecnica, guarda, passagem,
                condicionamento, tempo_reacao, estrategia
            )

            faixa_estimada = estimar_faixa(
                bjj_score,
                st.session_state.tempo,
                st.session_state.faixa
            )

            nivel  = classificar_nivel(bjj_score)
            pc1, pc2 = 0, 0  # será calculado no gráfico

            # Salvar atleta (se novo)
            if st.session_state.get("novo_atleta", True):
                add_athlete(
                    st.session_state.nome,
                    st.session_state.sobrenome,
                    st.session_state.faixa,
                    st.session_state.tempo
                )
                df = get_athletes()
                atleta_id = int(df.iloc[-1]["athlete_id"])
                st.session_state.athlete_id = atleta_id
            else:
                atleta_id = st.session_state.athlete_id

            save_questionnaire([
                int(len(get_scores_df()) + 1),
                int(atleta_id),
                float(forca), float(tecnica), float(guarda),
                float(passagem), float(condicionamento),
                float(tempo_reacao), float(estrategia),
                datetime.now().strftime("%Y-%m-%d")
            ])

            pontos_fortes, melhorias, recomendacoes = gerar_diagnostico(
                forca, tecnica, guarda, passagem,
                condicionamento, tempo_reacao, estrategia
            )

            # ── KPIs ──────────────────────────────────
            st.success("✅ Avaliação concluída!")
            st.divider()

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("BJJ Score",      f"{bjj_score}/100")
            col2.metric("Score Global",   f"{round(score, 1)}/100")
            col3.metric("Faixa Estimada", faixa_estimada)
            col4.metric("Nível Técnico",  nivel)

            st.divider()

            # ── Gauge de faixa ────────────────────────
            st.subheader("📊 Posicionamento na Escala de Faixas")
            plot_faixa_gauge(bjj_score, faixa_estimada)

            # ── Tabs de gráficos ──────────────────────
            st.divider()
            st.subheader("📈 Análise Técnica")

            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "Barras",
                "Radar Técnico",
                "Scouting Map",
                "Style Profile",
                "Heatmap Academia",
                "Mapa Perceptual"
            ])

            with tab1:
                plot_barras_dimensoes(
                    forca, tecnica, guarda, passagem,
                    condicionamento, tempo_reacao, estrategia
                )

            with tab2:
                plot_radar_comparativo(
                    forca, tecnica, guarda, passagem,
                    condicionamento, tempo_reacao, estrategia
                )

            with tab3:
                pc1, pc2 = plot_pca(
                    forca, tecnica, guarda, passagem,
                    condicionamento, tempo_reacao, estrategia
                )

            with tab4:
                perfil = classificar_perfil(pc1, pc2)
                plot_style_profile(pc1, pc2)

            with tab5:
                plot_heatmap()

            with tab6:
                plot_perceptual_map(st.session_state.nome)

            perfil = classificar_perfil(pc1, pc2)

            # ── Diagnóstico ───────────────────────────
            st.divider()
            st.subheader("🩺 Diagnóstico")

            if pontos_fortes:
                st.markdown("**✅ Pontos Fortes**")
                for p in pontos_fortes:
                    st.markdown(f"- {p}")

            if melhorias:
                st.markdown("**⚠️ Oportunidades de Melhoria**")
                for m in melhorias:
                    st.markdown(f"- {m}")

            if recomendacoes:
                st.markdown("**🎯 Recomendações de Treino**")
                for r in recomendacoes:
                    st.markdown(f"- {r}")

            # ── Análise por IA ────────────────────────
            st.divider()
            st.subheader("🤖 Análise por Inteligência Artificial")

            with st.spinner("Gerando análise personalizada com IA..."):
                analise_ia = gerar_analise_ia(
                    nome           = st.session_state.nome,
                    faixa_atual    = st.session_state.faixa,
                    faixa_estimada = faixa_estimada,
                    nivel          = nivel,
                    perfil         = perfil,
                    bjj_score      = bjj_score,
                    score_global   = score,
                    forca          = forca,
                    tecnica        = tecnica,
                    guarda         = guarda,
                    passagem       = passagem,
                    condicionamento= condicionamento,
                    tempo_reacao   = tempo_reacao,
                    estrategia     = estrategia,
                    pontos_fortes  = pontos_fortes,
                    melhorias      = melhorias,
                    recomendacoes  = recomendacoes
                )

            if analise_ia:
                st.info(analise_ia)
            else:
                st.caption("ℹ️ Para ativar análise por IA, adicione `anthropic_api_key` nos secrets do Streamlit.")

            # ── PDF ───────────────────────────────────
            st.divider()
            pdf = gerar_pdf(
                nome_atleta    = st.session_state.nome,
                faixa_atual    = st.session_state.faixa,
                tempo_treino   = st.session_state.tempo,
                score_global   = score,
                bjj_score      = bjj_score,
                faixa_estimada = faixa_estimada,
                nivel          = nivel,
                perfil         = perfil,
                pontos_fortes  = pontos_fortes,
                melhorias      = melhorias,
                recomendacoes  = recomendacoes,
                analise_ia     = analise_ia,
                forca          = forca,
                tecnica        = tecnica,
                guarda         = guarda,
                passagem       = passagem,
                condicionamento= condicionamento,
                tempo_reacao   = tempo_reacao,
                estrategia     = estrategia
            )

            with open(pdf, "rb") as f:
                st.download_button(
                    "📄 Baixar Relatório PDF",
                    f,
                    file_name=f"BJJ_Report_{st.session_state.nome}.pdf",
                    mime="application/pdf"
                )
