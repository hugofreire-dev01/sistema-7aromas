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
    initial_sidebar_state="collapsed" # Barra lateral começa fechada para dar foco
)

# --- CSS AVANÇADO (VISUAL E IMPRESSÃO) ---
st.markdown("""
<style>
    /* Fonte Geral */
    body {font-family: 'Segoe UI', sans-serif;}
    
    /* Esconder elementos na impressão */
    @media print {
        [data-testid="stSidebar"] {display: none !important;}
        .stAppHeader {display: none !important;}
        .stFileUploader {display: none !important;}
        .no-print {display: none !important;} /* Classe mágica para esconder botões */
        .block-container {padding: 0 !important; margin: 0 !important;}
        #root {margin-top: 0 !important;}
        .css-1544g2n {padding-top: 0 !important;}
    }

    /* Cartões de Produção */
    .card-container {
        page-break-inside: avoid;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    .card-header {
        color: white; 
        padding: 15px; 
        text-align: center; 
        font-weight: 800; 
        font-size: 20px;
        border-radius: 8px 8px 0 0;
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    .card-body {
        padding: 0px;
        background-color: white;
        border-radius: 0 0 8px 8px;
    }
    
    /* Tabela */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 15px;
    }
    .styled-table th, .styled-table td {
        padding: 12px 15px;
        text-align: left;
        border-bottom: 1px solid #f0f0f0;
    }
    .styled-table tr:nth-of-type(even) { background-color: #fcfcfc; }
    .styled-table tr:last-of-type td { border-bottom: none; }
    
    /* Coluna de Quantidade Destaque */
    .qtd-col {
        font-weight: 900;
        text-align: right;
        color: #333;
        font-size: 18px;
        width: 80px;
    }

    /* Cores das Categorias */
    .mini-vela {background-color: #674ea7; border-bottom: 3px solid #4a357d;}
    .vela-pote {background-color: #c27ba0; border-bottom: 3px solid #a05a80;}
    .spray {background-color: #134f5c; border-bottom: 3px solid #0d3842;}
    .escalda {background-color: #38761d; border-bottom: 3px solid #265213;}
    .outros {background-color: #607d8b; border-bottom: 3px solid #455a64;}

</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE LÓGICA (BACKEND) ---

def limpar_aroma(texto):
    if not isinstance(texto, str): return "Padrão / Sortido"
    texto = texto.replace(" e ", " & ").replace(" E ", " & ")
    # Regex para limpar medidas e lixo visual
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

def processar_pedidos(df, dias_limite):
    producao = {}
    lista_critica = []
    resumo_estoque = {}
    hoje = datetime.now()
    
    # Normalizar cabeçalhos
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # Busca inteligente de colunas
    col_sku = next((c for c in df.columns if 'SKU' in c), None)
    col_var = next((c for c in df.columns if 'VARIAÇÃO' in c or 'VARIATION' in c), None)
    col_nome = next((c for c in df.columns if 'NOME DO PRODUTO' in c or 'PRODUCT NAME' in c), None)
    col_qtd = next((c for c in df.columns if 'QUANTIDADE' in c or 'QUANTITY' in c), None)
    col_data = next((c for c in df.columns if 'ENVIO' in c or 'SHIP' in c), None)
    col_status = next((c for c in df.columns if 'STATUS' in c), None)

    if not col_sku or not col_qtd:
        return None, None, None, "Erro: Colunas SKU ou Quantidade não encontradas."

    for index, row in df.iterrows():
        if col_status and str(row[col_status]).upper() == "CANCELADO": continue
        
        # Filtro Data
        data_envio = None
        if col_data and pd.notnull(row[col_data]):
            try:
                data_envio = pd.to_datetime(row[col_data], dayfirst=True)
                if (data_envio - hoje).days > dias_limite: continue
            except: pass
        
        sku = str(row[col_sku]).upper()
        nome = str(row[col_nome]).upper() if col_nome else ""
        var = str(row[col_var]) if col_var else ""
        try: qtd_pedido = float(str(row[col_qtd]).replace(",", "."))
        except: qtd_pedido = 0.0
        
        texto_total = f"{sku} {nome} {var}".upper()

        # CLASSIFICAÇÃO
        classe = "99. DIVERSOS"
        css_class = "outros"
        tipo_estoque = "Outros"
        
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

        # REGRAS E ADIÇÃO
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
            
            if data_envio and (data_envio - hoje).days <= 1:
               lista_critica.append({"Data": data_envio.strftime("%d/%m"), "Item": f"{classe} - {aroma}", "Qtd": qtd})

    return producao, lista_critica, resumo_estoque, None

# --- SIDEBAR FIXA (MENU) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2823/2823652.png", width=50)
    st.title("7 Aromas")
    st.write("---")
    
    # Filtro de Prazo
    st.subheader("⏳ Prazo de Envio")
    filtro_prazo = st.radio(
        "Filtrar data:",
        ("TUDO", "URGENTE (24h)", "3 DIAS", "SEMANA"),
        index=0,
        label_visibility="collapsed"
    )
    
    st.write("---")
    st.info("Para imprimir separado: Selecione a categoria nos botões acima da lista e tecle Ctrl+P.")

# --- LÓGICA FILTRO PRAZO ---
dias_limite = 9999
if "URGENTE" in filtro_prazo: dias_limite = 1
elif "3 DIAS" in filtro_prazo: dias_limite = 3
elif "SEMANA" in filtro_prazo: dias_limite = 7

# --- CORPO PRINCIPAL ---

# Título e Upload (Classe no-print para sumir na impressão)
st.markdown('<div class="no-print">', unsafe_allow_html=True)
st.title("🏭 Central de Produção")
arquivo = st.file_uploader("📂 Arraste o arquivo Shopee aqui", type=['xlsx', 'csv'])
st.markdown('</div>', unsafe_allow_html=True)

if arquivo:
    try:
        # Leitura
        if arquivo.name.endswith('.csv'):
            try: df = pd.read_csv(arquivo, sep=';', encoding='utf-8')
            except: 
                arquivo.seek(0)
                df = pd.read_csv(arquivo, sep=',')
        else:
            df = pd.read_excel(arquivo)
        
        producao, urgentes, estoque, erro = processar_pedidos(df, dias_limite)

        if erro:
            st.error(erro)
        else:
            # === ÁREA DE BOTÕES DE FILTRO (VISÍVEL SÓ NA TELA) ===
            st.markdown('<div class="no-print">', unsafe_allow_html=True)
            st.write("---")
            st.subheader("🔍 O que você quer visualizar/imprimir?")
            
            # Criar lista de categorias disponíveis
            cats_disponiveis = sorted(producao.keys())
            opcoes_filtro = ["VISÃO GERAL (TODOS)"] + cats_disponiveis
            
            # Botões de Rádio Horizontais (Funcionam como abas)
            filtro_categoria = st.radio(
                "Selecione uma categoria para isolar:",
                opcoes_filtro,
                horizontal=True,
                label_visibility="collapsed"
            )
            st.markdown('</div>', unsafe_allow_html=True) # Fim do no-print

            # === LÓGICA DE EXIBIÇÃO ===
            if filtro_categoria == "VISÃO GERAL (TODOS)":
                categorias_para_mostrar = cats_disponiveis
                
                # Resumo de Estoque e Urgencia só aparece na visão geral
                c1, c2 = st.columns(2)
                c1.metric("Total de Peças", f"{int(sum([sum(c['itens'].values()) for c in producao.values()]))}")
                c2.metric("Pedidos Urgentes", f"{len(urgentes)}")
                
                if urgentes:
                    st.error(f"🔥 {len(urgentes)} ITENS URGENTES!")
                    with st.expander("Ver lista"): st.dataframe(pd.DataFrame(urgentes))
                
                # Picking List
                st.markdown("### 📦 Separação de Material")
                st.info(" ".join([f"**{k}:** {int(v)}  | " for k, v in estoque.items()]))
                
            else:
                # Se selecionou uma categoria específica
                categorias_para_mostrar = [filtro_categoria]
                st.success(f"👁️ Visualizando apenas: **{filtro_categoria}**. Pressione Ctrl+P para imprimir.")

            st.write("---")

            # === GERAÇÃO DOS CARTÕES ===
            # Se for visão geral, usa 2 colunas. Se for individual, usa 1 coluna centralizada.
            if len(categorias_para_mostrar) > 1:
                cols = st.columns(2)
            else:
                cols = st.columns(1)

            for i, cat_nome in enumerate(categorias_para_mostrar):
                dados = producao[cat_nome]
                itens = dados['itens']
                style = dados['css']
                
                # Tabela HTML
                rows = ""
                for item, qtd in sorted(itens.items()):
                    val = int(qtd) if qtd % 1 == 0 else f"{qtd:.1f}"
                    if qtd > 0:
                        rows += f"<tr><td>{item}</td><td class='qtd-col'>{val}</td></tr>"
                
                html_card = f"""
                <div class="card-container">
                    <div class="card-header {style}">{cat_nome}</div>
                    <div class="card-body">
                        <table class="styled-table">{rows}</table>
                    </div>
                </div>
                """
                
                # Renderiza na coluna correta
                with cols[i % len(cols)]:
                    st.markdown(html_card, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Erro: {e}")

# Rodapé
st.markdown('<div class="no-print" style="text-align:center; margin-top:50px; color:#aaa;">Sistema 7 Aromas v10</div>', unsafe_allow_html=True)
