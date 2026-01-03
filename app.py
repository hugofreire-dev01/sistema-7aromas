import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io

# --- CONFIGURAÇÃO DA PÁGINA (Precisa ser a primeira linha) ---
st.set_page_config(
    page_title="7 Aromas - Sistema de Produção",
    page_icon="🕯️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PARA IMPRESSÃO E VISUAL (ESTILO PRO) ---
st.markdown("""
<style>
    /* Fonte e Corpo */
    body {font-family: 'Segoe UI', sans-serif;}
    
    /* Cartões de Produção */
    .card-container {
        page-break-inside: avoid; /* Evita quebrar o cartão no meio da folha */
        margin-bottom: 20px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
        border-radius: 8px;
    }
    .card-header {
        color: white; 
        padding: 12px; 
        text-align: center; 
        font-weight: 800; 
        font-size: 18px;
        border-radius: 8px 8px 0 0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .card-body {
        border: 1px solid #ddd;
        border-top: none;
        padding: 0px;
        border-radius: 0 0 8px 8px;
        background-color: white;
    }
    
    /* Tabela dentro do cartão */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }
    .styled-table th, .styled-table td {
        padding: 10px;
        text-align: left;
        border-bottom: 1px solid #eee;
    }
    .styled-table tr:nth-of-type(even) {
        background-color: #f9f9f9;
    }
    .styled-table tr:last-of-type td {
        border-bottom: none;
    }
    .qtd-col {
        font-weight: bold;
        text-align: right;
        color: #333;
        font-size: 16px;
    }

    /* Cores das Categorias */
    .mini-vela {background-color: #674ea7; border: 1px solid #674ea7;} /* Roxo */
    .vela-pote {background-color: #c27ba0; border: 1px solid #c27ba0;} /* Rosa */
    .spray {background-color: #134f5c; border: 1px solid #134f5c;} /* Azul Petróleo */
    .escalda {background-color: #38761d; border: 1px solid #38761d;} /* Verde */
    .outros {background-color: #607d8b; border: 1px solid #607d8b;} /* Cinza */
    
    /* MODO DE IMPRESSÃO (O Segredo) */
    @media print {
        [data-testid="stSidebar"] {display: none;} /* Esconde Barra Lateral */
        .stAppHeader {display: none;} /* Esconde Cabeçalho Streamlit */
        .stFileUploader {display: none;} /* Esconde Upload */
        .no-print {display: none;} /* Esconde botões extras */
        .block-container {padding: 0 !important;}
        body { -webkit-print-color-adjust: exact; } /* Força imprimir cores */
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE LÓGICA ---

def limpar_aroma(texto):
    if not isinstance(texto, str): return "Padrão / Sortido"
    
    # Padronizações
    texto = texto.replace(" e ", " & ").replace(" E ", " & ")
    
    # Regex agressivo para limpar medidas e sujeira
    padroes = [
        r"\(1 unidade\)", r"\(1 un\)", r"\(1\)",
        r"\b\d+\s?(ml|L|Litro|un|unidades|kits|kit)\b",
        r"[0-9]", r",", r"\.", r"\+"
    ]
    for p in padroes:
        texto = re.sub(p, "", texto, flags=re.IGNORECASE)
        
    texto = texto.strip()
    if texto.endswith(")"): texto = texto[:-1]
    
    # Tratamento final
    texto = texto.replace("  ", " ").strip()
    return texto or "Padrão / Sortido"

def processar_pedidos(df, dias_limite):
    producao = {} 
    lista_critica = []
    resumo_estoque = {} # Novo: Para Picking
    hoje = datetime.now()
    
    # Normalizar colunas (Upper case para facilitar busca)
    df.columns = [c.strip() for c in df.columns]
    cols = {c.upper(): c for c in df.columns}
    
    # Tenta encontrar as colunas chaves
    col_sku = next((cols[c] for c in cols if 'SKU' in c), None)
    col_var = next((cols[c] for c in cols if 'VARIAÇÃO' in c or 'VARIATION' in c), None)
    col_nome = next((cols[c] for c in cols if 'NOME DO PRODUTO' in c or 'PRODUCT NAME' in c), None)
    col_qtd = next((cols[c] for c in cols if 'QUANTIDADE' in c or 'QUANTITY' in c), None)
    col_data = next((cols[c] for c in cols if 'ENVIO' in c or 'SHIP' in c), None)
    col_status = next((cols[c] for c in cols if 'STATUS' in c), None)

    if not all([col_sku, col_qtd]):
        return None, None, None, "Erro: Não encontrei colunas de SKU ou Quantidade. Verifique se é o arquivo correto da Shopee."

    for index, row in df.iterrows():
        # Filtros
        if col_status and str(row[col_status]).upper() == "CANCELADO": continue
        
        # Filtro de Data
        data_envio = None
        if col_data and pd.notnull(row[col_data]):
            try:
                data_envio = pd.to_datetime(row[col_data], dayfirst=True)
                diff = (data_envio - hoje).days
                if diff > dias_limite: continue 
            except:
                pass 
        
        # Extração Segura
        sku = str(row[col_sku]).upper()
        nome = str(row[col_nome]).upper() if col_nome else ""
        var = str(row[col_var]) if col_var else ""
        try:
            qtd_pedido = float(str(row[col_qtd]).replace(",", "."))
        except:
            qtd_pedido = 0.0
        
        texto_total = f"{sku} {nome} {var}".upper()

        # 1. CLASSIFICAÇÃO
        classe = "99. OUTROS"
        css_class = "outros"
        tipo_estoque = "Outros"
        
        if "MV" in sku or "MINI VELA" in nome:
            classe = "1. MINI VELAS (30G)"
            css_class = "mini-vela"
            tipo_estoque = "Mini Velas (Unidades)"
        elif "V100" in sku or "100G" in nome or "POTE" in nome:
            classe = "2. VELAS POTE (100G)"
            css_class = "vela-pote"
            tipo_estoque = "Potes de Vidro (Unidades)"
        elif "ES-" in sku or "ESCALDA" in nome:
            classe = "3. ESCALDA PÉS"
            css_class = "escalda"
            tipo_estoque = "Escalda Pés (Pacotes)"
        elif "SPRAY" in texto_total or "CHEIRINHO" in texto_total:
            css_class = "spray"
            if "1L" in texto_total or "1 LITRO" in texto_total: 
                classe = "4. HOME SPRAY - 1 LITRO"
                tipo_estoque = "Frasco 1 Litro"
            elif "500" in texto_total: 
                classe = "4. HOME SPRAY - 500ML"
                tipo_estoque = "Frasco 500ml"
            elif "250" in texto_total: 
                classe = "4. HOME SPRAY - 250ML"
                tipo_estoque = "Frasco 250ml"
            elif "100" in texto_total: 
                classe = "4. HOME SPRAY - 100ML"
                tipo_estoque = "Frasco 100ml"
            elif "60" in texto_total: 
                classe = "4. HOME SPRAY - 60ML"
                tipo_estoque = "Frasco 60ml"
            elif "30" in texto_total: 
                classe = "4. HOME SPRAY - 30ML"
                tipo_estoque = "Frasco 30ml"
            else: 
                classe = "4. HOME SPRAY - PADRÃO"
                tipo_estoque = "Frascos Diversos"

        # 2. MULTIPLICADORES
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

        # 3. REGRAS E ADIÇÃO
        itens_para_adicionar = []

        # Kit Misto
        if "V100-CFB" in sku or ("V100" in sku and "CERJ/FLOR/BRISA" in var.upper()):
            itens_para_adicionar = [("Cereja & Avelã", qtd_pedido), ("Flor de Cerejeira", qtd_pedido), ("Brisa do Mar", qtd_pedido)]
            # Ajuste estoque (são 3 potes)
            qtd_total_estoque = qtd_pedido * 3
        # Escalda Misto
        elif "ESCALDA" in classe and ("VARIADO" in var.upper() or "SORTIDO" in var.upper()):
            div = qtd_total / 3
            itens_para_adicionar = [("Lavanda", div), ("Alecrim", div), ("Camomila", div)]
            qtd_total_estoque = qtd_total
        # Normal
        else:
            aroma_limpo = limpar_aroma(var)
            itens_para_adicionar = [(aroma_limpo, qtd_total)]
            qtd_total_estoque = qtd_total

        # Soma Estoque Geral
        if tipo_estoque not in resumo_estoque: resumo_estoque[tipo_estoque] = 0
        resumo_estoque[tipo_estoque] += qtd_total_estoque

        # Soma Produção Detalhada
        for aroma, qtd in itens_para_adicionar:
            if classe not in producao: producao[classe] = {'itens': {}, 'css': css_class}
            if aroma not in producao[classe]['itens']: producao[classe]['itens'][aroma] = 0
            producao[classe]['itens'][aroma] += qtd

            # Urgencia
            if data_envio:
                dias_para_envio = (data_envio - hoje).days
                if dias_para_envio <= 1: 
                   lista_critica.append({
                       "Data": data_envio.strftime("%d/%m"),
                       "Produto": f"{classe} - {aroma}",
                       "Qtd": qtd
                   })

    return producao, lista_critica, resumo_estoque, None

# --- SIDEBAR (Barra Lateral) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2823/2823652.png", width=60) # Ícone vela
    st.title("7 Aromas")
    st.markdown("---")
    
    st.header("🎛️ Filtro de Prazo")
    filtro_prazo = st.radio(
        "Mostrar pedidos para:",
        ("TUDO (Sem limites)", "🚨 URGENTE (24h)", "⚠️ Próximos 3 Dias", "📅 Esta Semana"),
        index=0
    )
    
    st.markdown("---")
    st.info("💡 Dica: Pressione **Ctrl + P** para imprimir os cartões sem essa barra lateral.")

# Logica do Filtro
dias_limite = 9999
if "URGENTE" in filtro_prazo: dias_limite = 1
elif "3 Dias" in filtro_prazo: dias_limite = 3
elif "Semana" in filtro_prazo: dias_limite = 7

# --- CORPO PRINCIPAL ---
st.title("🏭 7 Aromas - Central de Produção")
st.markdown("Faça o upload da planilha da Shopee (`Order.toship...`) para gerar a ordem de fabricação.")

arquivo = st.file_uploader("Arraste o arquivo aqui", type=['xlsx', 'csv'])

if arquivo:
    try:
        # Leitura do Arquivo
        if arquivo.name.endswith('.csv'):
            # Tenta separadores diferentes automaticamente
            try:
                df = pd.read_csv(arquivo, sep=';', encoding='utf-8')
                if len(df.columns) < 5: raise Exception
            except:
                arquivo.seek(0)
                df = pd.read_csv(arquivo, sep=',')
        else:
            df = pd.read_excel(arquivo)
        
        # Processamento
        producao, urgentes, estoque, erro = processar_pedidos(df, dias_limite)

        if erro:
            st.error(erro)
        else:
            # === MÉTRICAS DE TOPO ===
            total_pecas = sum([sum(cat['itens'].values()) for cat in producao.values()])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Peças a Produzir", f"{int(total_pecas)}")
            c2.metric("Itens Críticos (Urgentes)", f"{len(urgentes)}")
            
            # Botão de Excel (Função para baixar)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # Cria um DF para exportar
                export_data = []
                for cat, data in producao.items():
                    for item, qtd in data['itens'].items():
                        export_data.append({"Categoria": cat, "Aroma": item, "Qtd": qtd})
                pd.DataFrame(export_data).to_excel(writer, sheet_name='Producao', index=False)
            
            c3.download_button(
                label="📥 Baixar Relatório em Excel",
                data=buffer.getvalue(),
                file_name="producao_7aromas.xlsx",
                mime="application/vnd.ms-excel",
                help="Baixe os dados processados para seu computador"
            )

            # === ALERTA DE URGÊNCIA ===
            if urgentes:
                st.error(f"🔥 ATENÇÃO: {len(urgentes)} ITENS PRECISAM SER ENVIADOS HOJE OU AMANHÃ!")
                with st.expander("Ver lista detalhada de urgências"):
                    st.dataframe(pd.DataFrame(urgentes), use_container_width=True)

            st.markdown("---")

            # === RESUMO DE ESTOQUE (PICKING) ===
            # Isso ajuda a separar os materiais antes de produzir
            st.subheader("📦 Separação de Estoque (Picking)")
            cols_pick = st.columns(len(estoque)) if len(estoque) <= 4 else st.columns(4)
            for i, (tipo, qtd) in enumerate(estoque.items()):
                with cols_pick[i % 4]:
                    st.info(f"**{tipo}**\n\n# {int(qtd)}")
            
            st.markdown("---")

            # === CARTÕES DE PRODUÇÃO (LAYOUT DE FÁBRICA) ===
            st.subheader("📋 Ordens de Produção (Imprimir)")
            
            categorias_ordenadas = sorted(producao.keys())
            
            # Layout em Colunas para visualização (Na impressão o CSS ajusta)
            col_esq, col_dir = st.columns(2)
            cols = [col_esq, col_dir]
            
            for i, cat_nome in enumerate(categorias_ordenadas):
                dados = producao[cat_nome]
                itens = dados['itens']
                style = dados['css']
                
                # Monta HTML da tabela
                rows_html = ""
                # Ordena itens alfabeticamente
                for item, qtd in sorted(itens.items()):
                    qtd_fmt = int(qtd) if qtd % 1 == 0 else f"{qtd:.1f}"
                    if qtd > 0:
                        rows_html += f"<tr><td>{item}</td><td class='qtd-col'>{qtd_fmt}</td></tr>"
                
                html_card = f"""
                <div class="card-container">
                    <div class="card-header {style}">
                        {cat_nome}
                    </div>
                    <div class="card-body">
                        <table class="styled-table">
                            {rows_html}
                        </table>
                    </div>
                </div>
                """
                
                with cols[i % 2]:
                    st.markdown(html_card, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar: {e}")
        st.info("Verifique se o arquivo enviado é o relatório de pedidos padrão da Shopee.")

# Rodapé para impressão
st.markdown("<div style='text-align: center; margin-top: 50px; color: #888; font-size: 12px;'>Gerado pelo Sistema 7 Aromas</div>", unsafe_allow_html=True)
