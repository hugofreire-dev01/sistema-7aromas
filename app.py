import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="7 Aromas ERP v13",
    page_icon="🕯️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PRO ---
st.markdown("""
<style>
    body {font-family: 'Segoe UI', sans-serif; background-color: #f4f6f9;}
    
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

    /* CARTÕES */
    .card-container {
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-radius: 10px;
        background: white;
        overflow: hidden;
        border: 1px solid #e1e4e8;
    }
    .card-header {
        color: white !important; padding: 12px; text-align: center; 
        font-weight: 700; font-size: 16px; text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .card-body { padding: 0; }
    
    /* TABELA */
    .styled-table { width: 100%; border-collapse: collapse; font-size: 14px; }
    .styled-table td { padding: 10px 15px; border-bottom: 1px solid #f0f0f0; color: #444; }
    .styled-table tr:nth-of-type(even) { background-color: #f8f9fa; }
    .qtd-col { font-weight: 800; text-align: right; color: #2c3e50; font-size: 16px; width: 80px; }

    /* CORES CATEGORIAS */
    .mini-vela {background: linear-gradient(135deg, #674ea7, #513b87);} 
    .vela-pote {background: linear-gradient(135deg, #c27ba0, #a05a80);} 
    .spray {background: linear-gradient(135deg, #134f5c, #0e3a43);} 
    .escalda {background: linear-gradient(135deg, #38761d, #254e13);}
    .outros {background: linear-gradient(135deg, #546e7a, #37474f);}

    /* ALERTAS E METRICAS */
    div[data-testid="metric-container"] {
        background-color: white; border-radius: 8px; 
        padding: 15px; border: 1px solid #eee; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES CORE ---

def limpar_float(valor):
    if pd.isna(valor): return 0.0
    s = str(valor).replace("R$", "").replace(" ", "")
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".") # 1.000,00
    elif "," in s: s = s.replace(",", ".") # 1000,00
    try: return float(s)
    except: return 0.0

def encontrar_coluna(df, chaves):
    cols = [str(c).upper().strip() for c in df.columns]
    for chave in chaves:
        for i, col in enumerate(cols):
            if chave in col: return df.columns[i]
    return None

def limpar_aroma(texto):
    if pd.isna(texto) or str(texto).strip() == "": return "Padrão / Sortido"
    texto = str(texto).replace(" e ", " & ").replace(" E ", " & ")
    padroes = [r"\(1 unidade\)", r"\(1 un\)", r"\(1\)", r"\b\d+\s?(ml|L|Litro|un|unidades|kits|kit)\b", r"[0-9]", r",", r"\.", r"\+"]
    for p in padroes: texto = re.sub(p, "", texto, flags=re.IGNORECASE)
    return texto.strip().replace("  ", " ") or "Padrão / Sortido"

def processar_tudo(df, dias_limite):
    producao = {}
    urgentes = []
    insumos = {"Cera (Kg)": 0, "Essência (L)": 0}
    finan = {"fat": 0.0, "pedidos": 0, "ticket": 0.0}
    hoje = datetime.now()
    
    # Mapeamento
    col_sku = encontrar_coluna(df, ["SKU", "REFERÊNCIA"])
    col_qtd = encontrar_coluna(df, ["QUANTIDADE", "QTD"])
    col_nome = encontrar_coluna(df, ["NOME", "PRODUTO", "TITULO"])
    col_var = encontrar_coluna(df, ["VARIAÇÃO", "VARIATION"])
    col_data = encontrar_coluna(df, ["ENVIO", "DATA LIMITE"])
    col_status = encontrar_coluna(df, ["STATUS"])
    col_val = encontrar_coluna(df, ["VALOR", "PREÇO", "TOTAL"])
    col_id = encontrar_coluna(df, ["ID", "ORDER"])

    if not col_sku or not col_qtd:
        return None, None, None, None, "❌ Erro: Colunas SKU/QTD não encontradas."

    pedidos_unicos = set()

    for idx, row in df.iterrows():
        if col_status and str(row[col_status]).upper() == "CANCELADO": continue
        
        # Filtro Data
        data_envio = None
        if col_data and pd.notnull(row[col_data]):
            try:
                data_envio = pd.to_datetime(row[col_data], dayfirst=True, errors='coerce')
                if pd.notnull(data_envio) and (data_envio - hoje).days > dias_limite: continue
            except: pass
        
        sku = str(row[col_sku]).upper()
        nome = str(row[col_nome]).upper() if col_nome else ""
        var = str(row[col_var]) if col_var else ""
        qtd = limpar_float(row[col_qtd])
        val = limpar_float(row[col_val]) if col_val else 0.0
        
        if qtd <= 0: continue

        # Financeiro
        if col_id: pedidos_unicos.add(str(row[col_id]))
        finan["fat"] += val

        texto = f"{sku} {nome} {var}".upper()

        # Classificação
        classe = "99. OUTROS"
        css = "outros"
        vidro = "Outros"
        peso = 0
        
        if "MV" in sku or "MINI VELA" in nome:
            classe = "1. MINI VELAS (30G)"
            css = "mini-vela"
            vidro = "Pote Mini"
            peso = 30
        elif "V100" in sku or "100G" in nome or "POTE" in nome:
            classe = "2. VELAS POTE (100G)"
            css = "vela-pote"
            vidro = "Pote Vidro 100g"
            peso = 100
        elif "ES-" in sku or "ESCALDA" in nome:
            classe = "3. ESCALDA PÉS"
            css = "escalda"
            vidro = "Pacote Zipper"
        elif "SPRAY" in texto or "CHEIRINHO" in texto:
            css = "spray"
            if "1L" in texto: 
                classe = "4. SPRAY 1L"
                vidro = "PET 1L"
            elif "500" in texto: 
                classe = "4. SPRAY 500ML"
                vidro = "PET 500ml"
            elif "250" in texto: 
                classe = "4. SPRAY 250ML"
                vidro = "PET 250ml"
            elif "100" in texto: 
                classe = "4. SPRAY 100ML"
                vidro = "PET 100ml"
            elif "60" in texto: 
                classe = "4. SPRAY 60ML"
                vidro = "PET 60ml"
            else: 
                classe = "4. SPRAY - PADRÃO"
                vidro = "Frascos Div"

        # Multiplicadores
        mult = 1
        if re.search(r"20\s?UN", texto): mult = 20
        elif re.search(r"10\s?UN", texto): mult = 10
        elif re.search(r"5\s?UN", texto): mult = 5
        elif "MVK" in sku or "KIT 4" in texto:
            mult = 4
            if "2 KIT" in texto: mult = 8
        elif "KIT 3" in sku: mult = 3
        elif "SPRAY" in classe and "2UN" in texto: mult = 2
        
        qtd_tot = qtd * mult

        # Insumos
        insumos[vidro] = insumos.get(vidro, 0) + qtd_tot
        insumos["Cera (Kg)"] += (qtd_tot * peso) / 1000
        if peso > 0: insumos["Essência (L)"] += (qtd_tot * peso * 0.1) / 1000

        # Adição Itens
        itens = []
        if "V100-CFB" in sku or ("V100" in sku and "CERJ/FLOR/BRISA" in var.upper()):
            itens = [("Cereja & Avelã", qtd), ("Flor de Cerejeira", qtd), ("Brisa do Mar", qtd)]
        elif "ESCALDA" in classe and ("VARIADO" in var.upper() or "SORTIDO" in var.upper()):
            div = qtd_tot / 3
            itens = [("Lavanda", div), ("Alecrim", div), ("Camomila", div)]
        else:
            itens = [(limpar_aroma(var), qtd_tot)]

        for item, q in itens:
            if classe not in producao: producao[classe] = {'itens': {}, 'css': css}
            if item not in producao[classe]['itens']: producao[classe]['itens'][item] = 0
            producao[classe]['itens'][item] += q
            
            if data_envio and pd.notnull(data_envio):
                if (data_envio - hoje).days <= 1:
                   urgentes.append({"Data": data_envio.strftime("%d/%m"), "Item": f"{classe} - {item}", "Qtd": q})

    finan["pedidos"] = len(pedidos_unicos)
    if finan["pedidos"] > 0: finan["ticket"] = finan["fat"] / finan["pedidos"]
    
    return producao, urgentes, insumos, finan, None

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2823/2823652.png", width=50)
    st.title("7 Aromas v13.0")
    st.write("---")
    prazo = st.radio("Filtro de Prazo:", ("TUDO", "URGENTE (24h)", "3 DIAS"), index=0)
    dias = 1 if "URGENTE" in prazo else (3 if "3 DIAS" in prazo else 9999)
    st.info("💡 Para forçar atualização: Clique nos '...' no canto superior direito > 'Clear Cache' > 'Rerun'.")

# --- APP ---
st.markdown('<div class="no-print">', unsafe_allow_html=True)
st.title("🏭 ERP 7 Aromas - v13.0")
st.write("Arraste o arquivo `.xlsx` ou `.csv` da Shopee.")
f = st.file_uploader("", type=['xlsx', 'csv'])
st.markdown('</div>', unsafe_allow_html=True)

if f:
    try:
        if f.name.endswith('.csv'):
            try: df = pd.read_csv(f, sep=';')
            except: 
                f.seek(0)
                df = pd.read_csv(f, sep=',')
        else:
            df = pd.read_excel(f)
            
        prod, urg, ins, fin, err = processar_tudo(df, dias)

        if err: st.error(err)
        else:
            # ABAS
            t1, t2, t3 = st.tabs(["🏭 PRODUÇÃO", "💰 FINANCEIRO", "📦 INSUMOS"])

            with t1:
                st.markdown('<div class="no-print">', unsafe_allow_html=True)
                st.write("---")
                cats = sorted(prod.keys())
                vis = st.radio("Categoria:", ["TODAS"] + cats, horizontal=True)
                if urg: st.error(f"🔥 {len(urg)} ITENS URGENTES")
                st.markdown('</div>', unsafe_allow_html=True)
                
                cols = st.columns(2) if vis == "TODAS" else st.columns(1)
                show = cats if vis == "TODAS" else [vis]
                
                for i, c in enumerate(show):
                    d = prod[c]
                    rows = ""
                    for it, q in sorted(d['itens'].items()):
                        val = int(q) if q % 1 == 0 else f"{q:.1f}"
                        if q > 0: rows += f"<tr><td>{it}</td><td class='qtd-col'>{val}</td></tr>"
                    
                    html = f"""<div class="card-container"><div class="card-header {d['css']}">{c}</div>
                    <div class="card-body"><table class="styled-table">{rows}</table></div></div>"""
                    with cols[i%len(cols)]: st.markdown(html, unsafe_allow_html=True)

            with t2:
                c1, c2, c3 = st.columns(3)
                c1.metric("Faturamento", f"R$ {fin['fat']:,.2f}")
                c2.metric("Pedidos", f"{fin['pedidos']}")
                c3.metric("Ticket Médio", f"R$ {fin['ticket']:,.2f}")
                
                # Gráfico
                data_chart = [{"Produto": k, "Qtd": v, "Cat": c} for c, d in prod.items() for k, v in d['itens'].items()]
                if data_chart:
                    fig = px.bar(pd.DataFrame(data_chart).sort_values("Qtd", ascending=False).head(10), 
                                 x="Qtd", y="Produto", color="Cat", orientation='h', title="Top 10 Produtos")
                    st.plotly_chart(fig, use_container_width=True)

            with t3:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("🏺 Embalagens")
                    for k, v in ins.items(): 
                        if "Cera" not in k and "Essência" not in k: st.info(f"**{k}:** {int(v)}")
                with c2:
                    st.subheader("⚖️ Matéria Prima")
                    st.warning(f"Cera: {ins['Cera (Kg)']:.2f} Kg")
                    st.warning(f"Essência: {ins['Essência (L)']:.2f} L")

    except Exception as e: st.error(f"Erro: {e}")
