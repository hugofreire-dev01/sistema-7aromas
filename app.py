import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io
import plotly.express as px

# --- 1. CONFIGURAÇÃO DA PÁGINA (OBRIGATÓRIO SER A PRIMEIRA LINHA) ---
st.set_page_config(
    page_title="7 Aromas - SISTEMA V14",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS PARA IMPRESSÃO E VISUAL ---
st.markdown("""
<style>
    body {font-family: 'Segoe UI', sans-serif;}
    
    /* ESCONDER NA IMPRESSÃO */
    @media print {
        [data-testid="stSidebar"], .stAppHeader, .stFileUploader, .no-print, .stTabs {
            display: none !important;
        }
        .block-container {padding: 0 !important; margin: 0 !important;}
        .card-container {
            break-inside: avoid; page-break-inside: avoid;
            border: 1px solid #000 !important; box-shadow: none !important;
        }
    }

    .card-container {
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        background: white;
    }
    .card-header {
        color: white !important; padding: 12px; text-align: center; 
        font-weight: 800; font-size: 16px; text-transform: uppercase;
    }
    .card-body { padding: 0px; }
    
    .styled-table { width: 100%; border-collapse: collapse; font-size: 14px; }
    .styled-table td { padding: 8px 15px; border-bottom: 1px solid #eee; color: #333; }
    .styled-table tr:nth-of-type(even) { background-color: #f8f9fa; }
    
    .qtd-col { font-weight: 900; text-align: right; font-size: 16px; width: 80px; }

    /* CORES */
    .mini-vela {background-color: #674ea7;} 
    .vela-pote {background-color: #c27ba0;} 
    .spray {background-color: #134f5c;} 
    .escalda {background-color: #38761d;}
    .outros {background-color: #546e7a;}
    
    .versao-check {
        background-color: #d1e7dd; color: #0f5132; 
        padding: 10px; text-align: center; font-weight: bold; border-radius: 5px; margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FUNÇÕES DE PROCESSAMENTO ---

def limpar_float(valor):
    if pd.isna(valor): return 0.0
    s = str(valor).replace("R$", "").replace(" ", "")
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".") 
    elif "," in s: s = s.replace(",", ".")
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

def processar(df, dias_limite):
    producao = {}
    urgentes = []
    insumos = {"Cera (Kg)": 0, "Essência (L)": 0}
    finan = {"fat": 0.0, "pedidos": 0}
    hoje = datetime.now()
    
    # Busca Colunas
    col_sku = encontrar_coluna(df, ["SKU", "REFERÊNCIA"])
    col_qtd = encontrar_coluna(df, ["QUANTIDADE", "QTD"])
    col_nome = encontrar_coluna(df, ["NOME", "PRODUTO"])
    col_var = encontrar_coluna(df, ["VARIAÇÃO", "VARIATION"])
    col_data = encontrar_coluna(df, ["ENVIO", "DATA LIMITE"])
    col_status = encontrar_coluna(df, ["STATUS"])
    col_val = encontrar_coluna(df, ["VALOR", "PREÇO", "TOTAL"])
    col_id = encontrar_coluna(df, ["ID", "ORDER"])

    if not col_sku or not col_qtd:
        return None, None, None, None, f"ERRO: Colunas não encontradas. Colunas lidas: {list(df.columns)}"

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
        classe = "99. DIVERSOS"
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
            if "1L" in texto: classe = "4. SPRAY 1L"; vidro = "PET 1L"
            elif "500" in texto: classe = "4. SPRAY 500ML"; vidro = "PET 500ml"
            elif "250" in texto: classe = "4. SPRAY 250ML"; vidro = "PET 250ml"
            elif "100" in texto: classe = "4. SPRAY 100ML"; vidro = "PET 100ml"
            elif "60" in texto: classe = "4. SPRAY 60ML"; vidro = "PET 60ml"
            else: classe = "4. SPRAY - PADRÃO"; vidro = "Frascos Div"

        # Mult
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

        # Adição
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
    return producao, urgentes, insumos, finan, None

# --- 4. INTERFACE ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2823/2823652.png", width=50)
    st.title("7 Aromas ERP")
    st.write("---")
    prazo = st.radio("Filtro Prazo:", ("TUDO", "URGENTE", "3 DIAS"), index=0)
    dias = 1 if "URGENTE" in prazo else (3 if "3 DIAS" in prazo else 9999)
    st.warning("⚠️ Se o site não atualizar, clique nos 3 pontos lá em cima -> Clear Cache -> Rerun.")

# --- CORPO ---
st.markdown('<div class="versao-check">✅ VERSÃO 14.0 ATIVA - COM GRÁFICOS E GESTÃO</div>', unsafe_allow_html=True)
st.markdown('<div class="no-print">', unsafe_allow_html=True)
st.title("🏭 Central de Produção e Gestão")
f = st.file_uploader("Arraste o arquivo Shopee (.xlsx ou .csv)", type=['xlsx', 'csv'])
st.markdown('</div>', unsafe_allow_html=True)

if f:
    try:
        if f.name.endswith('.csv'):
            try: df = pd.read_csv(f, sep=';', encoding='utf-8')
            except: 
                f.seek(0)
                try: df = pd.read_csv(f, sep=',')
                except: df = pd.read_csv(f, sep=',', encoding='latin1')
        else:
            df = pd.read_excel(f)
            
        prod, urg, ins, fin, err = processar(df, dias)

        if err: st.error(err)
        else:
            # === ABAS DO SISTEMA ===
            t1, t2, t3 = st.tabs(["🏭 PRODUÇÃO", "💰 FINANCEIRO", "📦 INSUMOS"])

            with t1:
                st.markdown('<div class="no-print">', unsafe_allow_html=True)
                st.write("---")
                cats = sorted(prod.keys())
                vis = st.radio("Visualizar:", ["TODAS"] + cats, horizontal=True)
                if urg: st.error(f"🔥 {len(urg)} PEDIDOS URGENTES")
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
                c1, c2 = st.columns(2)
                c1.metric("Faturamento Total", f"R$ {fin['fat']:,.2f}")
                c2.metric("Total Pedidos", f"{fin['pedidos']}")
                
                # GRÁFICO
                st.write("---")
                data_chart = [{"Produto": k, "Qtd": v, "Categoria": c} for c, d in prod.items() for k, v in d['itens'].items()]
                if data_chart:
                    fig = px.bar(pd.DataFrame(data_chart).sort_values("Qtd", ascending=False).head(10), 
                                 x="Qtd", y="Produto", color="Categoria", orientation='h', title="Top 10 Mais Vendidos")
                    st.plotly_chart(fig, use_container_width=True)

            with t3:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("🏺 Embalagens Necessárias")
                    for k, v in ins.items(): 
                        if "Cera" not in k and "Essência" not in k: st.info(f"**{k}:** {int(v)}")
                with c2:
                    st.subheader("⚖️ Matéria Prima Estimada")
                    st.warning(f"Cera: {ins['Cera (Kg)']:.2f} Kg")
                    st.warning(f"Essência: {ins['Essência (L)']:.2f} L")

    except Exception as e: st.error(f"Erro: {e}")
