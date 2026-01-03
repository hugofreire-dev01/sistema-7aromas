import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="7 Aromas - Central de Produção",
    page_icon="🕯️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS PRO (Visual e Impressão) ---
st.markdown("""
<style>
    body {font-family: 'Segoe UI', sans-serif;}
    
    /* ESCONDER NA IMPRESSÃO */
    @media print {
        [data-testid="stSidebar"], .stAppHeader, .stFileUploader, .no-print, header, footer {
            display: none !important;
        }
        .block-container {
            padding: 0 !important; margin: 0 !important;
        }
        .card-container {
            break-inside: avoid;
            page-break-inside: avoid;
            box-shadow: none !important;
            border: 1px solid #000 !important;
        }
    }

    /* ESTILO DOS CARTÕES */
    .card-container {
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        background: white;
    }
    .card-header {
        color: white !important; 
        padding: 15px; 
        text-align: center; 
        font-weight: 800; 
        font-size: 20px;
        border-radius: 8px 8px 0 0;
        text-transform: uppercase;
        letter-spacing: 1px;
        -webkit-print-color-adjust: exact; /* Força cor na impressão */
        print-color-adjust: exact;
    }
    .card-body {
        padding: 0px;
        border-radius: 0 0 8px 8px;
    }
    
    /* TABELA */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }
    .styled-table th, .styled-table td {
        padding: 10px 15px;
        text-align: left;
        border-bottom: 1px solid #f0f0f0;
        color: #000;
    }
    .styled-table tr:nth-of-type(even) { background-color: #f9f9f9; }
    
    .qtd-col {
        font-weight: 900;
        text-align: right;
        color: #000;
        font-size: 18px;
        width: 80px;
    }

    /* CORES */
    .mini-vela {background-color: #674ea7;} 
    .vela-pote {background-color: #c27ba0;} 
    .spray {background-color: #134f5c;} 
    .escalda {background-color: #38761d;}
    .outros {background-color: #555555;}
    
    /* ALERTAS */
    .alert-box {
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 20px;
        font-weight: bold;
    }
    .alert-red { background-color: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
    .alert-blue { background-color: #e3f2fd; color: #1565c0; border: 1px solid #90caf9; }

</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES (LÓGICA) ---

def limpar_aroma(texto):
    if pd.isna(texto) or texto == "": return "Padrão / Sortido"
    texto = str(texto).replace(" e ", " & ").replace(" E ", " & ")
    
    padroes = [
        r"\(1 unidade\)", r"\(1 un\)", r"\(1\)",
        r"\b\d+\s?(ml|L|Litro|un|unidades|kits|kit)\b",
        r"[0-9]", r",", r"\.", r"\+"
    ]
    for p in padroes:
        texto = re.sub(p, "", texto, flags=re.IGNORECASE)
    
    texto = texto.replace("  ", " ").strip()
    if texto.endswith(")"): texto = texto[:-1]
    return texto.strip() or "Padrão / Sortido"

def encontrar_coluna(df, palavras_chave):
    """ Tenta encontrar uma coluna que contenha alguma das palavras chave """
    cols_upper = [str(c).upper().strip() for c in df.columns]
    for chave in palavras_chave:
        for i, col in enumerate(cols_upper):
            if chave in col:
                return df.columns[i] # Retorna o nome original da coluna
    return None

def processar_pedidos(df, dias_limite):
    producao = {}
    lista_critica = []
    resumo_estoque = {}
    hoje = datetime.now()
    
    # --- 1. DETECÇÃO INTELIGENTE DE COLUNAS ---
    col_sku = encontrar_coluna(df, ["SKU", "REFERÊNCIA", "REFERENCE"])
    col_qtd = encontrar_coluna(df, ["QUANTIDADE", "QUANTITY", "QTD"])
    col_nome = encontrar_coluna(df, ["NOME DO PRODUTO", "PRODUCT NAME", "PRODUTO"])
    col_var = encontrar_coluna(df, ["VARIAÇÃO", "VARIATION", "OPÇÃO"])
    col_data = encontrar_coluna(df, ["ENVIO", "SHIP", "DATA LIMITE"])
    col_status = encontrar_coluna(df, ["STATUS", "SITUAÇÃO"])

    # Se não achar SKU ou QTD, para tudo.
    if not col_sku or not col_qtd:
        cols_encontradas = f"Colunas no arquivo: {list(df.columns)}"
        return None, None, None, f"ERRO: Não encontrei as colunas SKU ou QUANTIDADE. \n{cols_encontradas}"

    # --- 2. LOOP DE PROCESSAMENTO ---
    for index, row in df.iterrows():
        # Ignorar Cancelados
        if col_status and str(row[col_status]).upper() == "CANCELADO": continue
        
        # Filtro Data
        data_envio = None
        if col_data and pd.notnull(row[col_data]):
            try:
                data_envio = pd.to_datetime(row[col_data], dayfirst=True, errors='coerce')
                if pd.notnull(data_envio) and (data_envio - hoje).days > dias_limite: continue
            except: pass
        
        # Extrair dados com segurança
        sku = str(row[col_sku]).upper() if pd.notnull(row[col_sku]) else ""
        nome = str(row[col_nome]).upper() if col_nome and pd.notnull(row[col_nome]) else ""
        var = str(row[col_var]) if col_var and pd.notnull(row[col_var]) else ""
        
        try: 
            qtd_txt = str(row[col_qtd]).replace(",", ".")
            qtd_pedido = float(qtd_txt)
        except: 
            qtd_pedido = 0.0

        if qtd_pedido <= 0: continue # Pula se qtd for zero

        texto_total = f"{sku} {nome} {var}".upper()

        # CLASSIFICAÇÃO
        classe = "99. NÃO IDENTIFICADO" # Padrão para não perder nada
        css_class = "outros"
        tipo_estoque = "Outros Itens"
        
        if "MV" in sku or "MINI VELA" in nome:
            classe = "1. MINI VELAS (30G)"
            css_class = "mini-vela"
            tipo_estoque = "Mini Velas (Un)"
        elif "V100" in sku or "100G" in nome or "POTE" in nome:
            classe = "2. VELAS POTE (100G)"
            css_class = "vela-pote"
            tipo_estoque = "Potes Vidro (Un)"
        elif "ES-" in sku or "ESCALDA" in nome:
            classe = "3. ESCALDA PÉS"
            css_class = "escalda"
            tipo_estoque = "Escalda Pés (Pct)"
        elif "SPRAY" in texto_total or "CHEIRINHO" in texto_total:
            css_class = "spray"
            if "1L" in texto_total or "1 LITRO" in texto_total: 
                classe = "4. SPRAY - 1 LITRO"
                tipo_estoque = "Frasco 1L"
            elif "500" in texto_total: 
                classe = "4. SPRAY - 500ML"
                tipo_estoque = "Frasco 500ml"
            elif "250" in texto_total: 
                classe = "4. SPRAY - 250ML"
                tipo_estoque = "Frasco 250ml"
            elif "100" in texto_total: 
                classe = "4. SPRAY - 100ML"
                tipo_estoque = "Frasco 100ml"
            elif "60" in texto_total: 
                classe = "4. SPRAY - 60ML"
                tipo_estoque = "Frasco 60ml"
            elif "30" in texto_total: 
                classe = "4. SPRAY - 30ML"
                tipo_estoque = "Frasco 30ml"
            else: 
                classe = "4. SPRAY - PADRÃO"
                tipo_estoque = "Frascos Div"

        # MULTIPLICADORES
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

        # REGRAS DE ADIÇÃO
        itens_add = []
        if "V100-CFB" in sku or ("V100" in sku and "CERJ/FLOR/BRISA" in var.upper()):
            itens_add = [("Cereja & Avelã", qtd_pedido), ("Flor de Cerejeira", qtd_pedido), ("Brisa do Mar", qtd_pedido)]
            qtd_estoque = qtd_pedido * 3
        elif "ESCALDA" in classe and ("VARIADO" in var.upper() or "SORTIDO" in var.upper()):
            div = qtd_total / 3
            itens_add = [("Lavanda", div), ("Alecrim", div), ("Camomila", div)]
            qtd_estoque = qtd_total
        else:
            aroma_limpo = limpar_aroma(var)
            itens_add = [(aroma_limpo, qtd_total)]
            qtd_estoque = qtd_total

        if tipo_estoque not in resumo_estoque: resumo_estoque[tipo_estoque] = 0
        resumo_estoque[tipo_estoque] += qtd_estoque

        for aroma, qtd in itens_add:
            if classe not in producao: producao[classe] = {'itens': {}, 'css': css_class}
            if aroma not in producao[classe]['itens']: producao[classe]['itens'][aroma] = 0
            producao[classe]['itens'][aroma] += qtd
            
            # Checa urgência (se tiver data)
            if data_envio and pd.notnull(data_envio):
                dias = (data_envio - hoje).days
                if dias <= 1:
                   lista_critica.append({"Data": data_envio.strftime("%d/%m"), "Item": f"{classe} - {aroma}", "Qtd": qtd})

    return producao, lista_critica, resumo_estoque, None

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2823/2823652.png", width=50)
    st.title("7 Aromas")
    st.write("---")
    
    st.subheader("📅 Filtro de Data")
    filtro_prazo = st.radio("Mostrar:", ("TUDO", "URGENTE (24h)", "3 DIAS", "SEMANA"))
    st.write("---")
    st.info("Para imprimir: Selecione a categoria acima da lista e tecle Ctrl+P.")

# Lógica do filtro
dias_limite = 9999
if "URGENTE" in filtro_prazo: dias_limite = 1
elif "3 DIAS" in filtro_prazo: dias_limite = 3
elif "SEMANA" in filtro_prazo: dias_limite = 7

# --- CORPO PRINCIPAL ---
st.markdown('<div class="no-print">', unsafe_allow_html=True)
st.title("🏭 Central de Produção")
st.write("Arraste o arquivo `.xlsx` ou `.csv` da Shopee.")
arquivo = st.file_uploader("", type=['xlsx', 'csv'])
st.markdown('</div>', unsafe_allow_html=True)

if arquivo:
    try:
        # Tenta ler Excel ou CSV com varias codificações
        if arquivo.name.endswith('.csv'):
            try: df = pd.read_csv(arquivo, sep=';', encoding='utf-8')
            except: 
                arquivo.seek(0)
                try: df = pd.read_csv(arquivo, sep=',')
                except: df = pd.read_csv(arquivo, sep=',', encoding='latin1')
        else:
            df = pd.read_excel(arquivo)
        
        # Processa
        producao, urgentes, estoque, erro = processar_pedidos(df, dias_limite)

        if erro:
            st.error(erro)
            st.write("Dica: Verifique se o arquivo não está vazio ou corrompido.")
            with st.expander("Ver dados brutos (Debug)"):
                st.dataframe(df.head())
        
        elif not producao:
            st.warning("O arquivo foi lido, mas nenhum pedido se encaixou nos filtros.")
            
        else:
            # === BOTÕES DE CATEGORIA ===
            st.markdown('<div class="no-print">', unsafe_allow_html=True)
            st.write("---")
            cats_disp = sorted(producao.keys())
            opcoes = ["VISÃO GERAL"] + cats_disp
            
            # Estilo de abas
            escolha = st.radio("Modo de Visualização:", opcoes, horizontal=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # === VISÃO GERAL ===
            if escolha == "VISÃO GERAL":
                c1, c2 = st.columns(2)
                total = sum([sum(c['itens'].values()) for c in producao.values()])
                c1.metric("Total Peças", f"{int(total)}")
                c2.metric("Pedidos Urgentes", f"{len(urgentes)}")

                if urgentes:
                    st.markdown(f'<div class="alert-box alert-red">🔥 {len(urgentes)} ITENS PARA ENVIO IMEDIATO!</div>', unsafe_allow_html=True)
                    with st.expander("Ver Lista de Urgência"):
                        st.dataframe(pd.DataFrame(urgentes))
                
                st.markdown("### 📦 Picking List (Estoque)")
                st.markdown('<div class="alert-box alert-blue">', unsafe_allow_html=True)
                cols_pk = st.columns(3)
                for i, (k, v) in enumerate(estoque.items()):
                    cols_pk[i%3].write(f"**{k}:** {int(v)}")
                st.markdown('</div>', unsafe_allow_html=True)

                cats_show = cats_disp
            else:
                cats_show = [escolha]
                st.success(f"Filtrando: {escolha}. Pressione Ctrl+P para imprimir.")

            # === CARTÕES ===
            st.write("---")
            cols = st.columns(2) if len(cats_show) > 1 else st.columns(1)
            
            for i, cat in enumerate(cats_show):
                dados = producao[cat]
                # HTML Tabela
                rows = ""
                for item, qtd in sorted(dados['itens'].items()):
                    v = int(qtd) if qtd % 1 == 0 else f"{qtd:.1f}"
                    if qtd > 0:
                        rows += f"<tr><td>{item}</td><td class='qtd-col'>{v}</td></tr>"
                
                html = f"""
                <div class="card-container">
                    <div class="card-header {dados['css']}">{cat}</div>
                    <div class="card-body">
                        <table class="styled-table">{rows}</table>
                    </div>
                </div>
                """
                with cols[i % len(cols)]:
                    st.markdown(html, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Erro Crítico: {e}")
