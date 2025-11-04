import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import io

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


    # 2. Função para empilhar as prioridades (P1, P2, P3) em uma única coluna 'Disciplina'
    df_consolidado = pd.melt(
        df_raw,
        # Mantém as colunas de contexto
        id_vars=['Curso', 'Disponibilidade', 'Motivacao', 'Matricula'], 
        # Colunas a serem empilhadas
        value_vars=['Prioridade 1', 'Prioridade 2', 'Prioridade 3'], 
        var_name='Prioridade',
        value_name='Disciplina'
    )
    
    # 3. Remove linhas onde a disciplina é NaN/vazia (se o aluno não preencheu as 3 prioridades)
    df_consolidado = df_consolidado.dropna(subset=['Disciplina'])
    
    return df_raw, df_consolidado

# --- 2. LAYOUT E CARREGAMENTO DE DADOS COM UPLOADER ---
st.set_page_config(layout="wide", page_title="BI de Demanda de Cursos de Férias")

st.title("📊 Análise de Demanda de Disciplinas de Verão")
st.markdown("Dashboard interativo baseado nas respostas do formulário de manifestação de interesse.")

# Layout da Sidebar
with st.sidebar:
    st.header("⚙️ Carregar Dados")
    uploaded_file = st.file_uploader("Carregue seu arquivo CSV ou Excel aqui:", type=['csv', 'xlsx'])
    
    # Inicializa DataFrames para evitar ReferenceBeforeAssignment
    df_raw = pd.DataFrame()
    df_consolidado = pd.DataFrame()
    
    if uploaded_file is not None:
        try:
            # Lê o arquivo carregado
            if uploaded_file.name.endswith('.csv'):
                # Tenta detectar o separador (vírgula ou ponto e vírgula)
                uploaded_file.seek(0)
                file_content_bytes = uploaded_file.read()
                
                # Tenta decodificar com utf-8, se falhar, tenta latin-1
                try:
                    file_content = file_content_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    uploaded_file.seek(0)
                    file_content = file_content_bytes.decode('latin-1')

                separator = ',' if file_content.count(',') > file_content.count(';') else ';'
                
                # Retorna ao início do buffer para o pandas ler
                uploaded_file.seek(0)
                
                # Tenta ler com o encoding que funcionou
                try:
                    df_load = pd.read_csv(uploaded_file, sep=separator, encoding='utf-8')
                except UnicodeDecodeError:
                    uploaded_file.seek(0)
                    df_load = pd.read_csv(uploaded_file, sep=separator, encoding='latin-1')
                    
            else: # Assumindo xlsx
                df_load = pd.read_excel(uploaded_file)
                
            df_raw, df_consolidado = process_data(df_load)
            st.success("Dados carregados e processados com sucesso!")
            
        except Exception as e:
            st.error(f"Erro ao ler ou processar o arquivo. Verifique o formato e o mapeamento das colunas. Erro: {e}")
    else:
        st.warning("Carregue um arquivo para iniciar a análise.")


st.sidebar.header("⚙️ Filtros de Análise")

# Verifica se os dados foram carregados e processados com sucesso
if df_consolidado is None or df_consolidado.empty:
    st.info("Aguardando o carregamento do arquivo CSV ou Excel...")
    st.stop() 


# Opções de Cursos para filtro global
cursos_disponiveis = ['Todos os Cursos'] + sorted(df_raw['Curso'].unique().tolist())
# Opções de Disciplinas para o filtro de detalhes (P2 e P3)
disciplinas_com_interesse = sorted(df_consolidado['Disciplina'].unique().tolist())

# Filtros após o carregamento
curso_selecionado = st.sidebar.selectbox(
    "Filtrar por Curso (Análise Top Matérias):",
    cursos_disponiveis
)

# Adiciona a verificação para garantir que há disciplinas disponíveis para seleção
if disciplinas_com_interesse:
    disciplina_detalhe = st.sidebar.selectbox(
        "Selecione uma Disciplina para Detalhes (Motivação e Turno):",
        disciplinas_com_interesse
    )
else:
    st.warning("Nenhuma disciplina encontrada nos dados.")
    st.stop()


# --- 3. IMPLEMENTAÇÃO DA ANÁLISE 1: TOP MATÉRIAS ---
st.header("1. Top Matérias - Demanda Consolidada")

# Filtragem Dinâmica por Curso
if curso_selecionado != 'Todos os Cursos':
    df_filtrado = df_consolidado[df_consolidado['Curso'] == curso_selecionado]
    st.info(f"Mostrando a demanda consolidada (P1, P2 e P3) para o curso de **{curso_selecionado}**.")
else:
    df_filtrado = df_consolidado
    st.info("Mostrando a demanda consolidada (P1, P2 e P3) para **Todos os Cursos**.")

# Verifica se o DataFrame filtrado não está vazio
if df_filtrado.empty:
    st.warning(f"Não há dados para o curso selecionado: {curso_selecionado}")
    # Usa st.markdown em vez de st.stop() para manter o layout (se houver dados não-filtrados)
    pass 
else:
    # Contagem e visualização
    demanda_disciplina = df_filtrado.groupby(['Disciplina', 'Prioridade']).size().reset_index(name='Contagem')
    demanda_total_disciplina = demanda_disciplina.groupby('Disciplina')['Contagem'].sum().sort_values(ascending=False).index.tolist()

    # Garante que as Top Matérias sejam as primeiras
    demanda_disciplina['Disciplina'] = pd.Categorical(demanda_disciplina['Disciplina'], categories=demanda_total_disciplina, ordered=True)
    demanda_disciplina = demanda_disciplina.sort_values('Disciplina')

    # Criação do gráfico de barras empilhadas com Plotly
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

    fig_top_materias.update_layout(
        xaxis_title="Número de Manifestações",
        yaxis_title="Disciplina",
        legend_title="Prioridade",
        height=600,
        yaxis={'categoryorder':'total ascending'} # Ordena o eixo Y pelo total
    )
    st.plotly_chart(fig_top_materias, use_container_width=True)

# --- 4. IMPLEMENTAÇÃO DAS ANÁLISES 2 E 3 (DETALHES POR MATÉRIA) ---
st.markdown("---")
st.header(f"Detalhes da Disciplina: {disciplina_detalhe}")

col1, col2 = st.columns(2)

# Filtrar o DataFrame apenas para a disciplina selecionada
df_detalhe = df_consolidado[df_consolidado['Disciplina'] == disciplina_detalhe]

if df_detalhe.empty:
    st.warning(f"Não há detalhes para a disciplina: {disciplina_detalhe}")
    st.stop()

# --- ANÁLISE 2: DISPONIBILIDADE POR MATÉRIA ---
with col1:
    st.subheader("2. Disponibilidade de Turnos")
    
    # 1. Expandir (explode) a coluna de Disponibilidade (que é CSV)
    # A coluna de disponibilidade pode vir como NaN ou strings vazias, então filtramos
    df_disponibilidade = df_detalhe.dropna(subset=['Disponibilidade']).assign(Disponibilidade=df_detalhe['Disponibilidade'].str.split(',\s*')).explode('Disponibilidade')
    df_disponibilidade['Disponibilidade'] = df_disponibilidade['Disponibilidade'].str.strip()
    
    # 2. Contar e calcular porcentagem
    contagem_disponibilidade = df_disponibilidade['Disponibilidade'].value_counts(normalize=True).mul(100).rename('Porcentagem').reset_index()
    
    # 3. Criar o gráfico
    if not contagem_disponibilidade.empty:
        fig_disponibilidade = px.bar(
            contagem_disponibilidade,
            x='Porcentagem',
            y='Disponibilidade',
            orientation='h',
            color='Disponibilidade',
            title=f"Disponibilidade para {disciplina_detalhe}",
            color_discrete_sequence=px.colors.qualitative.Vivid
        )
        fig_disponibilidade.update_layout(
            xaxis_title="Porcentagem de Manifestações (%)",
            yaxis_title="Turno",
            showlegend=False
        )
        st.plotly_chart(fig_disponibilidade, use_container_width=True)
    else:
        st.warning(f"Nenhuma disponibilidade registrada para {disciplina_detalhe}.")

# --- ANÁLISE 3: MOTIVAÇÕES POR MATÉRIA ---
with col2:
    st.subheader("3. Motivações (Excluindo Outros/Não Interesse)")

    # 1. Expandir (explode) a coluna de Motivação (que é CSV)
    df_motivacao = df_detalhe.dropna(subset=['Motivacao']).assign(Motivacao=df_detalhe['Motivacao'].str.split(',\s*')).explode('Motivacao')
    df_motivacao['Motivacao'] = df_motivacao['Motivacao'].str.strip()
    
    # 2. Filtrar os motivos não desejados (ajustado para termos em português)
    motivos_excluir = [
        'outros', 'outro', 'não tenho interesse', 
        'há outros fatores que motiva seu interesse em cursar essas disciplinas nas férias? há mais alguma observação que gostaria de compartilhar?',
        'opcional. ex: "não posso ter aulas em fevereiro", "troquei de matriz e agora tá bem complicado pois..." , "tenho preferencia pelo professor(a) tal, mas dependendo também poderia com tal", "não tenho preferencia por horário e professor, estou desesperado(a)!".'
    ] 
    
    df_motivacao_filtrada = df_motivacao[~df_motivacao['Motivacao'].str.lower().isin(motivos_excluir)]
    
    # 3. Contar e calcular porcentagem
    contagem_motivacao = df_motivacao_filtrada['Motivacao'].value_counts(normalize=True).mul(100).rename('Porcentagem').reset_index()
    
    # 4. Criar o gráfico
    if not contagem_motivacao.empty:
        fig_motivacao = px.pie(
            contagem_motivacao,
            values='Porcentagem',
            names='Motivacao',
            title=f"Motivações Principais para {disciplina_detalhe}",
            color_discrete_sequence=px.colors.qualitative.T10
        )
        fig_motivacao.update_traces(textposition='inside', textinfo='percent+label')
        fig_motivacao.update_layout(showlegend=False)
        st.plotly_chart(fig_motivacao, use_container_width=True)
    else:
        st.warning("Não há motivos válidos (excluindo genéricos) para esta disciplina.")
