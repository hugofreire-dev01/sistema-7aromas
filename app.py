import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io
import plotly.express as px # Biblioteca de Gráficos

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="7 Aromas - Sistema de Gestão",
    page_icon="🕯️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PRO (Estilo de Software) ---
st.markdown("""
<style>
    body {font-family: 'Segoe UI', sans-serif; background-color: #f8f9fa;}
    
    /* ESCONDER NA IMPRESSÃO */
    @media print {
        [data-testid="stSidebar"], .stAppHeader, .stFileUploader, .no-print, header, footer, .stTabs {
            display: none !important;
        }
        .block-container {padding: 0 !important; margin: 0 !important;}
        .card-container {
            break-inside: avoid; page-break-inside: avoid;
            border: 1px solid #000 !important; box-shadow: none !important;
        }
    }

    /* CARTÕES DE PRODUÇÃO */
    .card-container {
        margin-bottom: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        background: white;
    }
    .card-header {
        color: white !important; padding: 10px; text-align: center; 
        font-weight: 800; font-size: 16px; border-radius: 8px 8px 0 0;
        text-transform: uppercase; -webkit-print-color-adjust: exact;
    }
    .card-body { padding: 0px; }
    
    /* TABELA */
    .styled-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .styled-table td { padding: 8px 12px; border-bottom: 1px solid #eee; color: #333; }
    .styled-table tr:nth-of-type(even) { background-color: #fcfcfc; }
    .qtd-col { font-weight: 900; text-align: right; color: #000; font-size: 15px; width: 60px; }

    /* CORES CATEGORIAS */
    .mini-vela {background-color: #674ea7;} 
    .vela-pote {background-color: #c27ba0;} 
    .spray {background-color: #134f5c;} 
    .escalda {background-color: #38761d;}
    .outros {background-color: #546e7a;}

    /* KPIS (Caixinhas de números) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE SEGURANÇA E LÓGICA (CORE) ---

def limpar_float(valor):
    """Converte qualquer bagunça (R$ 1.200,50) para float (1200.50)"""
    if pd.isna(valor): return 0.0
    s = str(valor).replace("R$", "").replace(" ", "")
    if "," in s and "." in s: # Formato 1.000,00
        s = s.replace(".", "").replace(",", ".")
    elif "," in s: # Formato 1000,00
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

def encontrar_coluna(df, chaves):
    """Caça a coluna certa independente do nome exato"""
    cols = [c.upper().strip() for c in df.columns]
    for chave in chaves:
        for i, col in enumerate(cols):
            if chave in col:
                return df.columns[i]
    return None

def limpar_aroma(texto):
    if pd.isna(texto) or str(texto).strip() == "": return "Padrão / Sortido"
    texto = str(texto).replace(" e ", " & ").replace(" E ", " & ")
    # Remove medidas e lixo
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

def processar_dados_completos(df, dias_limite):
    producao = {}
    lista_critica = []
    insumos = {"Cera (Estimado Kg)": 0, "Essência (Estimado L)": 0}
    financeiro = {"faturamento": 0.0, "pedidos": 0, "ticket_medio": 0.0}
    hoje = datetime.now()
    
    # 1. Mapeamento Inteligente
    col_sku = encontrar_coluna(df, ["SKU", "REFERÊNCIA", "PARENT"])
    col_qtd = encontrar_coluna(df, ["QUANTIDADE", "QTD", "QUANTITY"])
    col_nome = encontrar_coluna(df, ["NOME DO PRODUTO", "PRODUCT NAME", "TITULO"])
    col_var = encontrar_coluna(df, ["VARIAÇÃO", "VARIATION", "OPÇÃO"])
    col_data = encontrar_coluna(df, ["ENVIO", "DATA LIMITE", "SHIP"])
    col_status = encontrar_coluna(df, ["STATUS", "SITUAÇÃO"])
    col_valor = encontrar_coluna(df, ["VALOR TOTAL", "PREÇO TOTAL", "TOTAL PRICE", "SUBTOTAL"])
    col_id = encontrar_coluna(df, ["ID DO PEDIDO", "ORDER ID"])

    if not col_sku or not col_qtd:
        return None, None, None, None, "❌ Erro Crítico: Colunas SKU ou Quantidade não encontradas no arquivo."

    # Conjunto para contar pedidos únicos
    ids_pedidos_unicos = set()

    # 2. Loop Principal
    for index, row in df.iterrows():
        # Ignora Cancelados
        if col_status and str(row[col_status]).upper() == "CANCELADO": continue
        
        # Filtro de Data
        data_envio = None
        if col_data and pd.notnull(row[col_data]):
            try:
                data_envio = pd.to_datetime(row[col_data], dayfirst=True, errors='coerce')
                if pd.notnull(data_envio) and (data_envio - hoje).days > dias_limite: continue
            except: pass
        
        # Extração de Dados
        sku = str(row[col_sku]).upper()
        nome = str(row[col_nome]).upper() if col_nome else ""
        var = str(row[col_var]) if col_var else ""
        qtd_pedido = limpar_float(row[col_qtd])
        valor_venda = limpar_float(row[col_valor]) if col_valor else 0.0
        
        if qtd_pedido <= 0: continue

        # --- Lógica Financeira ---
        if col_id:
            id_ped = str(row[col_id])
            if id_ped not in ids_pedidos_unicos:
                ids_pedidos_unicos.add(id_ped)
                # Soma valor apenas uma vez por pedido se o relatório for por linha de produto? 
                # Shopee geralmente repete o valor total em todas as linhas ou divide. 
                # Vamos assumir soma simples de linha por linha se for relatório de itens.
                # Ajuste: Melhor somar o valor da linha.
        financeiro["faturamento"] += valor_venda

        texto_total = f"{sku} {nome} {var}".upper()

        # --- Classificação & Estoque ---
        classe = "99. DIVERSOS"
        css = "outros"
        tipo_vidro = "Outros"
        peso_cera = 0 # gramas
        
        if "MV" in sku or "MINI VELA" in nome:
            classe = "1. MINI VELAS (30G)"
            css = "mini-vela"
            tipo_vidro = "Pote Mini (Un)"
            peso_cera = 30
        elif "V100" in sku or "100G" in nome or "POTE" in nome:
            classe = "2. VELAS POTE (100G)"
            css = "vela-pote"
            tipo_vidro = "Pote Vidro 100g (Un)"
            peso_cera = 100
        elif "ES-" in sku or "ESCALDA" in nome:
            classe = "3. ESCALDA PÉS"
            css = "escalda"
            tipo_vidro = "Pacote Zipper (Un)"
        elif "SPRAY" in texto_total or "CHEIRINHO" in texto_total:
            css = "spray"
            if "1L" in texto_total or "1 LITRO" in texto_total: 
                classe = "4. SPRAY - 1 LITRO"
                tipo_vidro = "Frasco PET 1L"
            elif "500" in texto_total: 
                classe = "4. SPRAY - 500ML"
                tipo_vidro = "Frasco PET 500ml"
            elif "250" in texto_total: 
                classe = "4. SPRAY - 250ML"
                tipo_vidro = "Frasco PET 250ml"
            elif "100" in texto_total: 
                classe = "4. SPRAY - 100ML"
                tipo_vidro = "Frasco PET 100ml"
            elif "60" in texto_total: 
                classe = "4. SPRAY - 60ML"
                tipo_vidro = "Frasco PET 60ml"
            elif "30" in texto_total: 
                classe = "4. SPRAY - 30ML"
                tipo_vidro = "Frasco PET 30ml"
            else: 
                classe = "4. SPRAY - PADRÃO"
                tipo_vidro = "Frascos Diversos"

        # Multiplicadores de Kit
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

        # Cálculos de Insumos Básicos
        insumos[tipo_vidro] = insumos.get(tipo_vidro, 0) + qtd_total
        insumos["Cera (Estimado Kg)"] += (qtd_total * peso_cera) / 1000
        # Estimativa grosseira de essência (10%)
        if peso_cera > 0:
            insumos["Essência (Estimado L)"] += (qtd_total * peso_cera * 0.1) / 1000

        # Regras de Produção (Aromas)
        itens_add = []
        if "V100-CFB" in sku or ("V100" in sku and "CERJ/FLOR/BRISA" in var.upper()):
            itens_add = [("Cereja & Avelã", qtd_pedido), ("Flor de Cerejeira", qtd_pedido), ("Brisa do Mar", qtd_pedido)]
        elif "ESCALDA" in classe and ("VARIADO" in var.upper() or "SORTIDO" in var.upper()):
            div = qtd_total / 3
            itens_add = [("Lavanda", div), ("Alecrim", div), ("Camomila", div)]
        else:
            aroma_limpo = limpar_aroma(var)
            itens_add = [(aroma_limpo, qtd_total)]

        for aroma, qtd in itens_add:
            if classe not in producao: producao[classe] = {'itens': {}, 'css': css}
            if aroma not in producao[classe]['itens']: producao[classe]['itens'][aroma] = 0
            producao[classe]['itens'][aroma] += qtd
            
            if data_envio and pd.notnull(data_envio):
                dias = (data_envio - hoje).days
                if dias <= 1:
                   lista_critica.append({"Data": data_envio.strftime("%d/%m"), "Item": f"{classe} - {aroma}", "Qtd": qtd})

    financeiro["pedidos"] = len(ids_pedidos_unicos)
    if financeiro["pedidos"] > 0:
        financeiro["ticket_medio"] = financeiro["faturamento"] / financeiro["pedidos"]

    return producao, lista_critica, insumos, financeiro, None

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2823/2823652.png", width=50)
    st.title("Gestão 7 Aromas")
    
    st.subheader("📅 Filtro Global")
    filtro_prazo = st.radio("Período:", ("TUDO", "URGENTE (24h)", "3 DIAS", "SEMANA"))
    
    dias_limite = 9999
    if "URGENTE" in filtro_prazo: dias_limite = 1
    elif "3 DIAS" in filtro_prazo: dias_limite = 3
    elif "SEMANA" in filtro_prazo: dias_limite = 7
    
    st.markdown("---")
    st.caption("Desenvolvido para Gestão de Alta Performance")

# --- CORPO PRINCIPAL ---
st.markdown('<div class="no-print">', unsafe_allow_html=True)
st.title("🏭 ERP 7 Aromas - Central de Comando")
st.info("Arraste seu relatório da Shopee (Excel ou CSV) para iniciar a análise completa.")
arquivo = st.file_uploader("", type=['xlsx', 'csv'])
st.markdown('</div>', unsafe_allow_html=True)

if arquivo:
    try:
        # Leitura Robusta
        if arquivo.name.endswith('.csv'):
            try: df = pd.read_csv(arquivo, sep=';', encoding='utf-8')
            except: 
                arquivo.seek(0)
                try: df = pd.read_csv(arquivo, sep=',')
                except: df = pd.read_csv(arquivo, sep=',', encoding='latin1')
        else:
            df = pd.read_excel(arquivo)
            
        # PROCESSAMENTO GERAL
        producao, urgentes, insumos, finan, erro = processar_dados_completos(df, dias_limite)

        if erro:
            st.error(erro)
        else:
            # === SISTEMA DE ABAS ===
            tab1, tab2, tab3 = st.tabs(["🏭 PRODUÇÃO", "💰 FINANCEIRO & DASHBOARD", "📦 INSUMOS & ESTOQUE"])

            # ---------------- AB 1: PRODUÇÃO ----------------
            with tab1:
                st.markdown('<div class="no-print">', unsafe_allow_html=True)
                st.write("### Selecione a Categoria para Imprimir")
                
                cats = sorted(producao.keys())
                sel_cat = st.radio("Visualizar:", ["TODAS"] + cats, horizontal=True)
                
                if urgentes:
                    st.error(f"🔥 {len(urgentes)} ITENS CRÍTICOS (Prazo Curto)")
                    with st.expander("Ver lista de urgência"):
                        st.dataframe(pd.DataFrame(urgentes))
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Renderiza Cartões
                cols = st.columns(2) if sel_cat == "TODAS" else st.columns(1)
                cats_show = cats if sel_cat == "TODAS" else [sel_cat]
                
                for i, cat in enumerate(cats_show):
                    dados = producao[cat]
                    rows = ""
                    for item, qtd in sorted(dados['itens'].items()):
                        v = int(qtd) if qtd % 1 == 0 else f"{qtd:.1f}"
                        if qtd > 0: rows += f"<tr><td>{item}</td><td class='qtd-col'>{v}</td></tr>"
                    
                    html = f"""
                    <div class="card-container">
                        <div class="card-header {dados['css']}">{cat}</div>
                        <div class="card-body"><table class="styled-table">{rows}</table></div>
                    </div>"""
                    with cols[i % len(cols)]: st.markdown(html, unsafe_allow_html=True)

            # ---------------- AB 2: FINANCEIRO ----------------
            with tab2:
                col1, col2, col3 = st.columns(3)
                col1.metric("Faturamento (Período)", f"R$ {finan['faturamento']:,.2f}")
                col2.metric("Total Pedidos", f"{finan['pedidos']}")
                col3.metric("Ticket Médio", f"R$ {finan['ticket_medio']:,.2f}")
                
                st.divider()
                
                # Prepara dados para Gráfico
                todos_itens = []
                for cat, dados in producao.items():
                    for item, qtd in dados['itens'].items():
                        todos_itens.append({"Produto": item, "Qtd": qtd, "Categoria": cat})
                
                if todos_itens:
                    df_chart = pd.DataFrame(todos_itens).sort_values("Qtd", ascending=False).head(10)
                    fig = px.bar(df_chart, x="Qtd", y="Produto", orientation='h', color="Categoria", 
                                 title="🏆 Top 10 Aromas Mais Vendidos", text="Qtd")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Sem dados para gráficos.")

            # ---------------- AB 3: INSUMOS ----------------
            with tab3:
                st.header("Lista de Compras & Separação")
                st.caption("Baseado na produção atual. Verifique seu estoque físico.")
                
                # Exibe Insumos em Cards
                col_ins1, col_ins2 = st.columns(2)
                
                with col_ins1:
                    st.subheader("🏺 Embalagens")
                    for k, v in insumos.items():
                        if "Cera" not in k and "Essência" not in k:
                            st.info(f"**{k}:** {int(v)}")
                            
                with col_ins2:
                    st.subheader("🧪 Matéria Prima Estimada")
                    st.warning(f"⚖️ **Cera Mix:** {insumos['Cera (Estimado Kg)']:.2f} Kg")
                    st.warning(f"💧 **Essência:** {insumos['Essência (Estimado L)']:.2f} Litros")
                    st.caption("*Cálculo estimado: 10% de essência sobre o peso da vela.")

    except Exception as e:
        st.error(f"Ocorreu um erro no processamento: {e}")
