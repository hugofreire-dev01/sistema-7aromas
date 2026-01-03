import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="7AURAS - Sistema de Produção",
    page_icon="🕯️",
    layout="wide"
)

# Estilo CSS para impressão e visual (Cards)
st.markdown("""
<style>
    .block-container {padding-top: 1rem;}
    .stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;}
    .card-header {
        color: white; 
        padding: 10px; 
        text-align: center; 
        font-weight: bold; 
        font-size: 18px;
        border-radius: 5px 5px 0 0;
        margin-top: 20px;
    }
    .card-body {
        border: 2px solid;
        border-top: none;
        padding: 0px;
        border-radius: 0 0 5px 5px;
    }
    /* Cores das Categorias */
    .mini-vela {background-color: #674ea7; border-color: #674ea7;}
    .vela-pote {background-color: #c27ba0; border-color: #c27ba0;}
    .spray {background-color: #134f5c; border-color: #134f5c;}
    .escalda {background-color: #38761d; border-color: #38761d;}
    .outros {background-color: #607d8b; border-color: #607d8b;}
    
    @media print {
        .stSidebar, header, footer {display: none;}
        .block-container {padding: 0;}
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE LÓGICA (CORE) ---

def limpar_aroma(texto):
    if not isinstance(texto, str): return "Padrão / Sortido"
    
    # 1. Padronizações
    texto = texto.replace(" e ", " & ")
    
    # 2. Remoção de sujeira (Regex poderoso)
    # Remove: (1 unidade), 100ml, 1L, 10 un, etc.
    padroes = [
        r"\(1 unidade\)", r"\(1 un\)", r"\(1\)",
        r"\b\d+\s?(ml|L|Litro|un|unidades|kits|kit)\b",
        r"[0-9]", r",", r"\.", r"\+"
    ]
    
    for p in padroes:
        texto = re.sub(p, "", texto, flags=re.IGNORECASE)
        
    texto = texto.strip()
    if texto.endswith(")"): texto = texto[:-1]
    
    return texto.strip() or "Padrão / Sortido"

def processar_pedidos(df, dias_limite):
    producao = {} # Dicionario para agrupar
    lista_critica = []
    hoje = datetime.now()
    
    # Mapear colunas (Flexibilidade para achar nomes parecidos)
    cols = {c: c for c in df.columns}
    col_sku = next((c for c in cols if 'SKU' in c), None)
    col_var = next((c for c in cols if 'variação' in c.lower()), None)
    col_nome = next((c for c in cols if 'Nome do Produto' in c), None)
    col_qtd = next((c for c in cols if 'Quantidade' in c), None)
    col_data = next((c for c in cols if 'envio' in c.lower()), None)
    col_status = next((c for c in cols if 'Status' in c), None)

    if not all([col_sku, col_qtd]):
        return None, None, "Erro: Colunas SKU ou Quantidade não encontradas."

    for index, row in df.iterrows():
        # Filtros básicos
        if col_status and row[col_status] == "Cancelado": continue
        
        # Filtro de Data
        data_envio = None
        if col_data and pd.notnull(row[col_data]):
            try:
                # Tenta converter data
                data_envio = pd.to_datetime(row[col_data], dayfirst=True)
                diff = (data_envio - hoje).days
                if diff > dias_limite: continue # Pula se estiver longe do prazo
            except:
                pass # Se der erro na data, processa mesmo assim
        
        # Extração de dados
        sku = str(row[col_sku]).upper()
        nome = str(row[col_nome]).upper() if col_nome else ""
        var = str(row[col_var]) if col_var else ""
        qtd_pedido = float(row[col_qtd])
        
        texto_total = f"{sku} {nome} {var}".upper()

        # --- 1. CLASSIFICAÇÃO ---
        classe = "99. OUTROS"
        css_class = "outros"
        
        if "MV" in sku or "MINI VELA" in nome:
            classe = "1. MINI VELAS (30G)"
            css_class = "mini-vela"
        elif "V100" in sku or "100G" in nome or "POTE" in nome:
            classe = "2. VELAS POTE (100G)"
            css_class = "vela-pote"
        elif "ES-" in sku or "ESCALDA" in nome:
            classe = "3. ESCALDA PÉS"
            css_class = "escalda"
        elif "SPRAY" in texto_total or "CHEIRINHO" in texto_total:
            if "1L" in texto_total or "1 LITRO" in texto_total: classe = "4. HOME SPRAY - 1 LITRO"
            elif "500" in texto_total: classe = "4. HOME SPRAY - 500ML"
            elif "250" in texto_total: classe = "4. HOME SPRAY - 250ML"
            elif "100" in texto_total: classe = "4. HOME SPRAY - 100ML"
            elif "60" in texto_total: classe = "4. HOME SPRAY - 60ML"
            elif "30" in texto_total: classe = "4. HOME SPRAY - 30ML"
            else: classe = "4. HOME SPRAY - PADRÃO"
            css_class = "spray"

        # --- 2. MULTIPLICADORES ---
        mult = 1
        if re.search(r"20\s?UN", texto_total): mult = 20
        elif re.search(r"10\s?UN", texto_total): mult = 10
        elif re.search(r"5\s?UN", texto_total): mult = 5
        elif "MVK" in sku or "KIT 4" in texto_total:
            mult = 4
            if "2 KIT" in texto_total: mult = 8
        elif "KIT 3" in sku: mult = 3
        elif "SPRAY" in classe and "2UN" in texto_total: mult = 2
        
        qtd_total = qtd_pedido * mult

        # --- 3. REGRAS E ADIÇÃO ---
        itens_para_adicionar = []

        # Regra Kit Misto 3 Velas
        if "V100-CFB" in sku or ("V100" in sku and "CERJ/FLOR/BRISA" in var.upper()):
            itens_para_adicionar = [("Cereja & Avelã", qtd_pedido), ("Flor de Cerejeira", qtd_pedido), ("Brisa do Mar", qtd_pedido)]
        # Regra Escalda Pés Variados
        elif "ESCALDA" in classe and ("VARIADO" in var.upper() or "SORTIDO" in var.upper()):
            div = qtd_total / 3
            itens_para_adicionar = [("Lavanda", div), ("Alecrim", div), ("Camomila", div)]
        # Item Normal
        else:
            aroma_limpo = limpar_aroma(var)
            itens_para_adicionar = [(aroma_limpo, qtd_total)]

        # Adiciona ao dicionario mestre
        for aroma, qtd in itens_para_adicionar:
            if classe not in producao: producao[classe] = {'itens': {}, 'css': css_class}
            if aroma not in producao[classe]['itens']: producao[classe]['itens'][aroma] = 0
            producao[classe]['itens'][aroma] += qtd

            # Urgencia
            if data_envio:
                dias_para_envio = (data_envio - hoje).days
                if dias_para_envio <= 1: # 24h a 48h
                   lista_critica.append({
                       "Data": data_envio.strftime("%d/%m"),
                       "Item": f"{classe} - {aroma}",
                       "Qtd": qtd
                   })

    return producao, lista_critica, None

# --- INTERFACE DO USUÁRIO (FRONTEND) ---

st.sidebar.header("🎛️ Filtros de Produção")
filtro_prazo = st.sidebar.radio(
    "O que produzir?",
    ("TUDO (Sem limites)", "🚨 URGENTE (24h)", "⚠️ Próximos 3 Dias", "📅 Esta Semana"),
    index=0
)

# Define dias limite baseado na escolha
dias_limite = 9999
if "URGENTE" in filtro_prazo: dias_limite = 1
elif "3 Dias" in filtro_prazo: dias_limite = 3
elif "Semana" in filtro_prazo: dias_limite = 7

st.title("🏭 7AURAS - Central de Produção")
st.markdown("Arraste sua planilha da Shopee abaixo para gerar a ordem de produção.")

arquivo = st.file_uploader("Upload Planilha Shopee (.xlsx ou .csv)", type=['xlsx', 'csv'])

if arquivo:
    try:
        if arquivo.name.endswith('.csv'):
            df = pd.read_csv(arquivo, sep=';') # Tenta ponto e virgula
            if len(df.columns) < 5: df = pd.read_csv(arquivo, sep=',') # Tenta virgula
        else:
            df = pd.read_excel(arquivo)
        
        # Processa
        producao, urgentes, erro = processar_pedidos(df, dias_limite)

        if erro:
            st.error(erro)
        else:
            # Métricas de Topo
            total_pecas = sum([sum(cat['itens'].values()) for cat in producao.values()])
            c1, c2 = st.columns(2)
            c1.metric("Total de Peças (Filtro Atual)", f"{int(total_pecas)}")
            c2.metric("Itens Críticos", f"{len(urgentes)}")

            # --- VISUALIZAÇÃO DOS URGENTES ---
            if urgentes:
                st.error(f"🔥 HÁ {len(urgentes)} ITENS PARA ENVIO IMEDIATO (HOJE/AMANHÃ)")
                df_urgentes = pd.DataFrame(urgentes)
                st.dataframe(df_urgentes, use_container_width=True)

            st.markdown("---")

            # --- VISUALIZAÇÃO DOS CARDS (GRID) ---
            categorias_ordenadas = sorted(producao.keys())
            
            # Divide a tela em 2 colunas para economizar papel
            col_esq, col_dir = st.columns(2)
            cols = [col_esq, col_dir]
            
            for i, cat_nome in enumerate(categorias_ordenadas):
                dados = producao[cat_nome]
                itens = dados['itens']
                style = dados['css']
                
                # Prepara tabela bonita
                df_cat = pd.DataFrame(list(itens.items()), columns=['Aroma / Variação', 'Qtd'])
                df_cat = df_cat.sort_values('Aroma / Variação')
                df_cat['Qtd'] = df_cat['Qtd'].apply(lambda x: round(x, 1) if x % 1 != 0 else int(x)) # Arredonda
                
                # Coloca na coluna certa (alternado)
                with cols[i % 2]:
                    # HTML Customizado para o Card
                    st.markdown(f"""
                        <div class='card-header {style}'>{cat_nome}</div>
                    """, unsafe_allow_html=True)
                    
                    # Tabela
                    st.table(df_cat)

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
