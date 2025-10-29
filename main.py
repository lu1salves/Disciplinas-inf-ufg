import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import io

# Importa o conector GSheets nativo do Streamlit.
# Necessário: pip install streamlit-gsheets-connection
from streamlit_gsheets import GSheetsConnection 

# --- 1. Mapeamento de Colunas (Ajustado para o seu CSV) ---

# Mapeamento dos nomes longos das colunas do formulário para nomes curtos usados no código
# **IMPORTANTE:** Estes nomes devem corresponder EXATAMENTE aos cabeçalhos do seu arquivo CSV.
COLUNA_MAPPER = {
    'Carimbo de data/hora': 'Timestamp',
    'Endereço de e-mail': 'Email',
    'Nome completo': 'Nome',
    'Curso': 'Curso',
    'Número de Matrícula': 'Matricula',
    '1ª Prioridade: Qual disciplina você mais tem interesse em cursar nas férias?': 'Prioridade 1',
    '2ª Prioridade: Qual seria a SEGUNDA disciplina você mais tem interesse em cursar nas férias?': 'Prioridade 2',
    '3ª Prioridade: Qual seria a TERCEIRA disciplina você mais tem interesse em cursar nas férias?': 'Prioridade 3',
    'No geral, quais turnos você teria disponibilidade para cursar disciplinas de férias de verão?': 'Disponibilidade',
    # A motivação 1 é a única que precisamos expandir, mas o formulário tem 3 colunas, vamos usar apenas a primeira para a análise de detalhes, conforme o código original.
    '(1ª Disciplina) Algum dos casos baixo descreve seu interesse em cursar essa disciplina nas férias? Quais?': 'Motivacao',
    # Adicionando as colunas extras para evitar erro de key, mas não as usaremos na análise de detalhes
    '(2ª Disciplina) Algum dos casos baixo descreve seu interesse em cursar essa disciplina nas férias? Quais?': 'Motivacao 2',
    '(3ª Disciplina) Algum dos casos baixo descreve seu interesse em cursar essa disciplina nas férias? Quais?': 'Motivacao 3',
    'Qual o máximo de matérias que você gostaria de cursar durante o semestre de verão (2025.4)?': 'Maximo Materias',
    'Há outros fatores que motiva seu interesse em cursar essas disciplinas nas férias? ': 'Fatores Motivacao',
    'Seja sincero': 'Sinceridade',
    'Por favor, consulte sua matriz curricular para garantir que você cumpre os pré-requisitos para cursar a disciplina!': 'Check Pre-req',
    'Há mais alguma observação que gostaria de compartilhar?\nOpcional. Ex: "não posso ter aulas em fevereiro", "troquei de matriz e agora tá bem complicado pois..." , "tenho preferencia pelo professor(a) tal, mas dependendo também poderia com tal", "não tenho preferencia por horário e professor, estou desesperado(a)!".\n\nLembre-se: quanto menos restritivo e mais sincero, melhor.': 'Observacoes',
}

# Lista de colunas essenciais para o processamento
COLUNAS_ESSENCIAIS = [
    'Curso', 'Disponibilidade', 'Motivacao', 'Matricula', 
    'Prioridade 1', 'Prioridade 2', 'Prioridade 3'
]


@st.cache_data
def process_data(df_raw):
    """Realiza o pré-processamento de melt e explode nos dados."""
    
    # 1. Renomeia as colunas longas para as chaves curtas
    # Usa errors='ignore' para ignorar colunas que não estão no mapeamento (ex: Observações)
    df_raw = df_raw.rename(columns=COLUNA_MAPPER, errors='ignore')
    
    # Verifica se todas as colunas essenciais estão presentes
    if not all(col in df_raw.columns for col in COLUNAS_ESSENCIAIS):
        missing = [col for col in COLUNAS_ESSENCIAIS if col not in df_raw.columns]
        st.error(f"Erro no mapeamento. As colunas essenciais estão faltando: {missing}. Verifique o COLUNA_MAPPER.")
        return pd.DataFrame(), pd.DataFrame()

    # --- REMOÇÃO DE FRASES DE PREENCHIMENTO PADRÃO ---
    frases_a_remover = [
        "NÃO TENHO UMA 1 DISCIPLINA DE INTERESSE",
        "NÃO TENHO UMA 2 DISCIPLINA DE INTERESSE",
        "NÃO TENHO UMA 3 DISCIPLINA DE INTERESSE",
    ]

    # Substitui as frases indesejadas por NaN
    for col in ['Prioridade 1', 'Prioridade 2', 'Prioridade 3']:
        if col in df_raw.columns:
            df_raw[col] = df_raw[col].replace(frases_a_remover, np.nan)


    # --- EXTRAÇÃO DO ANO DE MATRÍCULA ---
    try:
        # Extrai os primeiros 4 caracteres da matrícula (ex: 2022)
        df_raw['Ano Matrícula'] = df_raw['Matricula'].astype(str).str[:4]
        # Converte para numérico (inteiro)
        df_raw['Ano Matrícula'] = pd.to_numeric(df_raw['Ano Matrícula'], errors='coerce', downcast='integer')
        # Preenche NaNs com 0 para evitar problemas na filtragem (embora geralmente sejam filtrados)
        df_raw['Ano Matrícula'] = df_raw['Ano Matrícula'].fillna(0)
    except Exception as e:
        st.error(f"Erro ao extrair 'Ano Matrícula': {e}. Certifique-se de que a coluna 'Matricula' existe.")
        df_raw['Ano Matrícula'] = 0 # Default para não quebrar


    # 2. Função para empilhar as prioridades (P1, P2, P3) em uma única coluna 'Disciplina'
    df_consolidado = pd.melt(
        df_raw,
        # Adiciona 'Ano Matrícula' aos id_vars
        id_vars=['Curso', 'Disponibilidade', 'Motivacao', 'Matricula', 'Ano Matrícula'], 
        # Colunas a serem empilhadas
        value_vars=['Prioridade 1', 'Prioridade 2', 'Prioridade 3'], 
        var_name='Prioridade',
        value_name='Disciplina'
    )
    
    # 3. Remove linhas onde a disciplina é NaN/vazia (incluindo as frases removidas acima)
    df_consolidado = df_consolidado.dropna(subset=['Disciplina'])
    
    return df_raw, df_consolidado

# --- 2. LAYOUT E CARREGAMENTO DE DADOS COM GOOGLE SHEETS ---
st.set_page_config(layout="wide", page_title="BI de Demanda de Cursos de Férias")

# URL Placeholder para o logo (Você pode substituir por um link real)
INF_UFG_LOGO_URL = "https://placehold.co/100x100/1E3A8A/FFFFFF?text=INF+UFG" 

# Criação de colunas para o logo e o título
col_logo, col_title = st.columns([1, 6]) # 1 parte para o logo, 6 para o título

with col_logo:
    # Exibe a imagem do logo
    st.image(INF_UFG_LOGO_URL, width=100) 

with col_title:
    st.title("📊 Análise de Demanda de Disciplinas de Verão")
    st.markdown("Dashboard interativo baseado nas respostas do formulário de manifestação de interesse.")

st.sidebar.header("⚙️ Configuração")
st.sidebar.markdown("""
    Para que os dados sejam carregados:
    1. Instale: `pip install streamlit-gsheets-connection`
    2. Crie uma Service Account no Google Cloud.
    3. Compartilhe a planilha com o email da Service Account.
    4. Adicione as credenciais ao `secrets.toml` do Streamlit Cloud.
""")

# Variáveis globais para os DataFrames
df_raw = pd.DataFrame()
df_consolidado = pd.DataFrame()

# Tenta estabelecer a conexão e carregar os dados
try:
    # Conecta-se ao Google Sheets. O Streamlit Cloud usará os segredos do secrets.toml
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Lê os dados da planilha. Substitua 'Nome da sua Aba' e 'URL da sua planilha'
    # O Streamlit Cloud preferirá ler a URL/ID do secrets.toml, mas esta é a sintaxe de leitura
    # Certifique-se de que a aba (worksheet) está correta, geralmente 'Respostas ao formulário 1'
    # Você pode usar a URL ou o ID da planilha
    SHEET_URL = st.secrets["gsheets"]["spreadsheet_url"] # Assume que a URL está no secrets
    WORKSHEET_NAME = "Respostas ao formulário 1" # Ajuste o nome da aba se necessário

    # @st.cache_data garante que esta leitura seja feita apenas na primeira vez
    @st.cache_data(ttl=600) # Recarrega a cada 10 minutos
    def read_gsheets_data(conn, sheet_url, worksheet_name):
        return conn.read(spreadsheet=sheet_url, worksheet=worksheet_name)
    
    df_load = read_gsheets_data(conn, SHEET_URL, WORKSHEET_NAME)

    # Processa os dados
    df_raw, df_consolidado = process_data(df_load)
    
    st.sidebar.success("Conectado ao Google Sheets e dados carregados!")

except Exception as e:
    # Captura a exceção, mas permite que o app continue para mostrar instruções
    st.sidebar.error("Erro ao conectar ou carregar dados do Google Sheets.")
    st.info("O aplicativo está aguardando o carregamento dos dados da planilha. Verifique sua conexão e o arquivo `secrets.toml`.")
    st.stop() # Para a execução do restante do app se os dados não carregarem


st.sidebar.header("⚙️ Filtros de Análise")

# Verifica se os dados foram carregados e processados com sucesso
if df_consolidado is None or df_consolidado.empty:
    st.stop() 


# Opções de Cursos para filtro global
cursos_disponiveis = ['Todos os Cursos'] + sorted(df_raw['Curso'].unique().tolist())

# Opções de Anos de Matrícula para filtro global
# Converte para lista de strings para o selectbox e remove anos 0 (invalido)
anos_matricula_disponiveis = [str(int(a)) for a in df_raw['Ano Matrícula'].unique() if a != 0]
anos_matricula_disponiveis = ['Todos os Anos'] + sorted(anos_matricula_disponiveis, reverse=True)


# --- CRIAÇÃO DOS FILTROS NA SIDEBAR ---
curso_selecionado = st.sidebar.selectbox(
    "Filtrar por Curso (Aplica-se a todos os gráficos):", 
    cursos_disponiveis
)

ano_matricula_selecionado = st.sidebar.selectbox(
    "Filtrar por Ano de Matrícula (Aplica-se a todos os gráficos):",
    anos_matricula_disponiveis
)

# Opções de Disciplinas para o filtro de detalhes (P2 e P3)
disciplinas_com_interesse = sorted(df_consolidado['Disciplina'].unique().tolist())


# Adiciona a verificação para garantir que há disciplinas disponíveis para seleção
if disciplinas_com_interesse:
    disciplina_detalhe = st.sidebar.selectbox(
        "Selecione uma Disciplina para Detalhes (Motivação e Turno):",
        disciplinas_com_interesse
    )
else:
    st.warning("Nenhuma disciplina encontrada nos dados.")
    st.stop()
    
    
# --- APLICAÇÃO DO FILTRO GLOBAL DE CURSO E ANO NO DATAFRAME CONSOLIDADO ---

df_filtrado_global = df_consolidado.copy()

# Aplica filtro por Curso
if curso_selecionado != 'Todos os Cursos':
    df_filtrado_global = df_filtrado_global[df_filtrado_global['Curso'] == curso_selecionado].copy()

# Aplica filtro por Ano de Matrícula
if ano_matricula_selecionado != 'Todos os Anos':
    # Converte o ano selecionado de volta para o tipo numérico (inteiro) para correspondência
    target_year = pd.to_numeric(ano_matricula_selecionado)
    df_filtrado_global = df_filtrado_global[df_filtrado_global['Ano Matrícula'] == target_year].copy()


# --- 3. IMPLEMENTAÇÃO DA ANÁLISE 1: TOP MATÉRIAS ---
st.header("1. Top Matérias - Demanda Consolidada")

# Mensagem de informação sobre os filtros ativos
filtro_info = f"Mostrando a demanda consolidada (P1, P2 e P3) para o curso de **{curso_selecionado}**"
if ano_matricula_selecionado != 'Todos os Anos':
    filtro_info += f" e ano de matrícula **{ano_matricula_selecionado}**."
else:
    filtro_info += "."
st.info(filtro_info)


# Verifica se o DataFrame filtrado não está vazio
if df_filtrado_global.empty:
    st.warning(f"Não há dados para os filtros selecionados: Curso '{curso_selecionado}' e Ano '{ano_matricula_selecionado}'.")
    st.stop()
else:
    # 1. Contagem total de manifestações por disciplina (P1, P2, P3 somadas)
    demanda_total_disciplina = df_filtrado_global.groupby('Disciplina').size().reset_index(name='Contagem Total')
    
    # 2. Ordena as disciplinas pela contagem total (decrescente)
    demanda_total_disciplina = demanda_total_disciplina.sort_values(by='Contagem Total', ascending=True)
    
    # 3. Cria a lista ordenada de disciplinas
    disciplinas_ordenadas = demanda_total_disciplina['Disciplina'].tolist()

    # 4. Cria o DataFrame final, mesclando a contagem total com a distribuição por prioridade
    demanda_disciplina = df_filtrado_global.groupby(['Disciplina', 'Prioridade']).size().reset_index(name='Contagem')
    
    # Adiciona a coluna de Contagem Total para ser usada na ordenação do Plotly
    demanda_disciplina = demanda_disciplina.merge(demanda_total_disciplina, on='Disciplina', how='left')

    # 5. Criação do gráfico de barras empilhadas com Plotly
    fig_top_materias = px.bar(
        demanda_disciplina,
        x='Contagem',
        y='Disciplina',
        color='Prioridade',
        orientation='h',
        title='Demanda por Disciplina (Prioridade 1, 2 e 3)',
        category_orders={'Prioridade': ['Prioridade 1', 'Prioridade 2', 'Prioridade 3']},
        color_discrete_sequence=px.colors.qualitative.Bold
    )

    # Garante que o eixo Y seja ordenado pela Contagem Total (que é a soma das prioridades)
    fig_top_materias.update_layout(
        xaxis_title="Número de Manifestações",
        yaxis_title="Disciplina",
        legend_title="Prioridade",
        height=600,
        # Ordena o eixo y (Disciplina) com base na lista disciplinas_ordenadas
        yaxis={'categoryorder': 'array', 'categoryarray': disciplinas_ordenadas}
    )
    
    st.plotly_chart(fig_top_materias, use_container_width=True)

# --- 4. IMPLEMENTAÇÃO DAS ANÁLISES 2, 3 E 4 (DETALHES POR MATÉRIA) ---
st.markdown("---")
st.header(f"Detalhes da Disciplina: {disciplina_detalhe}")
st.caption(f"Os dados abaixo refletem a seleção da disciplina **{disciplina_detalhe}** feita pelos alunos do curso **{curso_selecionado}** e ano **{ano_matricula_selecionado}**.")


# Filtra o DataFrame já filtrado globalmente (df_filtrado_global) pela disciplina selecionada
df_detalhe = df_filtrado_global[df_filtrado_global['Disciplina'] == disciplina_detalhe]

if df_detalhe.empty:
    st.warning(f"Não há manifestações da disciplina {disciplina_detalhe} para os filtros ativos.")
    st.stop()

# --- NOVA ANÁLISE 2: RESUMO NUMÉRICO DA DISCIPLINA ---

st.subheader("2. Resumo Numérico da Disciplina")

# 1. Número absoluto de alunos interessados na matéria (contagem de matrículas únicas no df_detalhe)
total_alunos = df_detalhe['Matricula'].nunique()

# 2. Número absoluto de alunos interessados por curso
demanda_por_curso = df_detalhe.groupby('Curso')['Matricula'].nunique().reset_index(name='Alunos')

# 3. Número de alunos por ano
demanda_por_ano = df_detalhe.groupby('Ano Matrícula')['Matricula'].nunique().reset_index(name='Alunos')
# Remove o ano 0 (inválido/NaN)
demanda_por_ano = demanda_por_ano[demanda_por_ano['Ano Matrícula'] != 0].sort_values(by='Ano Matrícula', ascending=False)
demanda_por_ano['Ano Matrícula'] = demanda_por_ano['Ano Matrícula'].astype(int) # Formata como inteiro

col_metric_1, col_metric_2, col_metric_3 = st.columns(3)

# KPI 1: Total de Alunos
col_metric_1.metric(
    label=f"Total de Alunos (únicos) em '{disciplina_detalhe}'",
    value=total_alunos
)

# KPI 2: Demanda por Curso (Exibindo o principal)
principal_curso = demanda_por_curso.sort_values(by='Alunos', ascending=False).iloc[0] if not demanda_por_curso.empty else None

if principal_curso is not None:
    col_metric_2.metric(
        label=f"Curso Principal ({principal_curso['Curso']})",
        value=principal_curso['Alunos'],
        help="Número de alunos de cada curso interessados na disciplina."
    )
else:
    col_metric_2.metric(label="Curso Principal", value="N/A")


# KPI 3: Demanda por Ano (Exibindo a maior concentração)
maior_demanda_ano = demanda_por_ano.sort_values(by='Alunos', ascending=False).iloc[0] if not demanda_por_ano.empty else None

if maior_demanda_ano is not None:
    col_metric_3.metric(
        label=f"Maior Concentração (Ano {maior_demanda_ano['Ano Matrícula']})",
        value=maior_demanda_ano['Alunos'],
        help="Maior número de alunos por ano de matrícula interessados."
    )
else:
    col_metric_3.metric(label="Maior Concentração", value="N/A")

st.markdown("#### Distribuição Detalhada de Matrículas")

# Exibe a tabela de alunos por curso
st.dataframe(demanda_por_curso.set_index('Curso').T, use_container_width=True)

# Exibe a tabela de alunos por ano
st.dataframe(demanda_por_ano.set_index('Ano Matrícula').T, use_container_width=True)


st.markdown("---") # Separador visual

# --- ANÁLISE 3: DISPONIBILIDADE POR MATÉRIA ---

st.subheader("3. Disponibilidade de Turnos")

# 1. Expandir (explode) a coluna de Disponibilidade (que é CSV)
df_disponibilidade = df_detalhe.dropna(subset=['Disponibilidade']).assign(Disponibilidade=df_detalhe['Disponibilidade'].str.split(',\s*')).explode('Disponibilidade')
df_disponibilidade['Disponibilidade'] = df_disponibilidade['Disponibilidade'].str.strip()

# 2. Contar e calcular porcentagem e contagem absoluta
contagem_disponibilidade_abs = df_disponibilidade['Disponibilidade'].value_counts().rename('Contagem')
contagem_disponibilidade_perc = df_disponibilidade['Disponibilidade'].value_counts(normalize=True).mul(100).rename('Porcentagem')

contagem_disponibilidade = pd.concat([contagem_disponibilidade_abs, contagem_disponibilidade_perc], axis=1).reset_index()
contagem_disponibilidade = contagem_disponibilidade.rename(columns={'index': 'Disponibilidade'})


# 3. Criar o gráfico
if not contagem_disponibilidade.empty:
    fig_disponibilidade = px.bar(
        contagem_disponibilidade.sort_values(by='Porcentagem', ascending=True),
        x='Porcentagem',
        y='Disponibilidade',
        orientation='h',
        color='Disponibilidade',
        text='Contagem', # Mostrar contagem absoluta na barra
        title=f"Disponibilidade para {disciplina_detalhe}",
        color_discrete_sequence=px.colors.qualitative.Vivid
    )
    fig_disponibilidade.update_layout(
        xaxis_title="Porcentagem de Manifestações (%)",
        yaxis_title="Turno",
        showlegend=False
    )
    fig_disponibilidade.update_traces(textposition='outside', texttemplate='%{text} alunos')
    st.plotly_chart(fig_disponibilidade, use_container_width=True)
else:
    st.warning(f"Nenhuma disponibilidade registrada para {disciplina_detalhe} com os filtros ativos.")

st.markdown("---") # Separador visual entre as análises de detalhes

# --- ANÁLISE 4: MOTIVAÇÕES POR MATÉRIA (GRÁFICO DE BARRAS) ---

st.subheader("4. Motivações (Excluindo Outros/Não Interesse)")

# 1. Expandir (explode) a coluna de Motivação (que é CSV)
df_motivacao = df_detalhe.dropna(subset=['Motivacao']).assign(Motivacao=df_detalhe['Motivacao'].str.split(',\s*')).explode('Motivacao')
df_motivacao['Motivacao'] = df_motivacao['Motivacao'].str.strip()

# 2. Filtrar os motivos não desejados (ajustado para termos em português)
motivos_excluir = [
    'outros', 'outro', 'não tenho interesse', 
    'há outros fatores que motiva seu interesse em cursar essas disciplinas nas férias? há mais alguma observação que gostaria de compartilhar?',
    'opcional. ex: "não posso ter aulas em fevereiro", "troquei de matriz e agora tá bem complicado pois..." , "tenho preferencia pelo professor(a) tal, mas dependendo também poderia com tal", "não tenho preferencia por horário e professor, estou desesperado(a)!".',
    'seja sincero'
] 

df_motivacao_filtrada = df_motivacao[~df_motivacao['Motivacao'].str.lower().isin(motivos_excluir)]

# 3. Contar e calcular porcentagem e contagem absoluta
contagem_motivacao_abs = df_motivacao_filtrada['Motivacao'].value_counts().rename('Contagem')
contagem_motivacao_perc = df_motivacao_filtrada['Motivacao'].value_counts(normalize=True).mul(100).rename('Porcentagem')

contagem_motivacao = pd.concat([contagem_motivacao_abs, contagem_motivacao_perc], axis=1).reset_index()
contagem_motivacao = contagem_motivacao.rename(columns={'index': 'Motivacao'})


# 4. Criar o gráfico DE BARRAS
if not contagem_motivacao.empty:
    # Ordena pela porcentagem
    contagem_motivacao = contagem_motivacao.sort_values(by='Porcentagem', ascending=True)
    
    fig_motivacao = px.bar(
        contagem_motivacao,
        x='Porcentagem',
        y='Motivacao',
        orientation='h',
        text='Contagem', # Mostrar contagem absoluta na barra
        title=f"Distribuição de Motivações para {disciplina_detalhe}",
        color='Motivacao', # Colore cada barra
        color_discrete_sequence=px.colors.qualitative.T10
    )
    
    fig_motivacao.update_layout(
        xaxis_title="Porcentagem de Manifestações (%)",
        yaxis_title="Motivo",
        showlegend=False
    )
    fig_motivacao.update_traces(textposition='outside', texttemplate='%{text} alunos')
    st.plotly_chart(fig_motivacao, use_container_width=True)
else:
    st.warning("Não há motivos válidos (excluindo genéricos) para esta disciplina com os filtros ativos.")
