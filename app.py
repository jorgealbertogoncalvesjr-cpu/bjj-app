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


        import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
from sklearn.decomposition import PCA
import numpy as np

# =====================================================
# CONEXÃO GOOGLE SHEETS
# =====================================================

@st.cache_resource
def connect_google_sheets():
    gc = gspread.service_account_from_dict(
        st.secrets["gcp_service_account"]
    )
    return gc.open("bjj_app_database")

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def get_athletes():
    sheet = connect_google_sheets()
    df = pd.DataFrame(sheet.worksheet("athletes").get_all_records())
    return df

def save_questionnaire(data_row):
    sheet = connect_google_sheets()
    worksheet = sheet.worksheet("respostas_questionario")
    worksheet.append_row(data_row)

def calcular_scores(respostas):
    forca = np.mean(respostas[0:5])
    tecnica = np.mean(respostas[5:10])
    guarda = np.mean(respostas[10:15])
    passagem = np.mean(respostas[15:20])
    
    score_global = np.mean([forca, tecnica, guarda, passagem])
    
    return forca, tecnica, guarda, passagem, score_global

def estimar_faixa(score_global, tempo_meses):
    if score_global >= 85 and tempo_meses >= 60:
        return "Preta"
    elif score_global >= 70 and tempo_meses >= 48:
        return "Marrom"
    elif score_global >= 55 and tempo_meses >= 36:
        return "Roxa"
    elif score_global >= 40 and tempo_meses >= 12:
        return "Azul"
    else:
        return "Branca"

# =====================================================
# INTERFACE
# =====================================================

st.title("📋 Avaliação Técnica BJJ")

athletes_df = get_athletes()

if athletes_df.empty:
    st.warning("Nenhum atleta cadastrado.")
    st.stop()

athlete_nome = st.selectbox(
    "Selecione o atleta",
    athletes_df["nome"] + " " + athletes_df["sobrenome"]
)

athlete_data = athletes_df[
    (athletes_df["nome"] + " " + athletes_df["sobrenome"]) == athlete_nome
].iloc[0]

tempo_meses = athlete_data["tempo_treino_meses"]

st.subheader("Responda de 1 (Muito baixo) a 5 (Muito alto)")

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

with st.form("questionario"):
    for p in perguntas:
        respostas.append(st.slider(p, 1, 5, 3))
    
    submitted = st.form_submit_button("Finalizar Avaliação")

if submitted:

    forca, tecnica, guarda, passagem, score_global = calcular_scores(respostas)
    
    faixa_estimada = estimar_faixa(score_global, tempo_meses)

    # PCA
    matriz = np.array([[forca, tecnica, guarda, passagem]])
    pca = PCA(n_components=2)
    componentes = pca.fit_transform(matriz)

    st.success("Avaliação concluída!")

    st.markdown(f"""
    **Score Global:** {round(score_global,2)}  
    **Faixa Estimada:** {faixa_estimada}
    """)

    # Salvar no Sheets
    data_row = [
        len(connect_google_sheets().worksheet("respostas_questionario").get_all_records()) + 1,
        athlete_data["athlete_id"],
        *respostas,
        round(forca,2),
        round(tecnica,2),
        round(guarda,2),
        round(passagem,2),
        round(score_global,2),
        faixa_estimada,
        datetime.now().strftime("%Y-%m-%d")
    ]

    save_questionnaire(data_row)

        if nome and sobrenome:
            add_athlete(nome, sobrenome, faixa, tempo)
            st.success("✅ Atleta cadastrado com sucesso!")
        else:
            st.warning("Preencha nome e sobrenome.")
