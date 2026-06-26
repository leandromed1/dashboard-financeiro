"""
Dashboard Financeiro - LEO
Lê a aba [LANÇAMENTOS] (exportada para CSV) e monta um painel interativo.

Fase 1 (atual): lê o arquivo dados/lancamentos_2026.csv
Fase 2 (depois): trocar a função carregar_dados() para ler a planilha ao vivo.

Para rodar:
    streamlit run app.py
"""

from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

# ----------------------------------------------------------------------------
# Configuração da página
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard Financeiro - Léo",
    page_icon="💰",
    layout="wide",
)

PASTA = Path(__file__).parent
ARQUIVO_DADOS = PASTA / "dados" / "lancamentos_2026.csv"   # fallback offline

# ---- Conexão ao vivo com o Google Sheets (gspread) --------------------------
SPREADSHEET_ID = "1Upi8GAmLMM8mMD1VWVk7Z5s3ycYBNl4-qB_tke-chTw"  # 2026 - FINANCEIRO LEO
ABA = "LANÇAMENTOS"
CAMINHO_CHAVE = PASTA / "credenciais.json"   # chave da conta de serviço (local)
ESCOPOS = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Cores padrão
COR_RECEITA = "#2E7D32"   # verde
COR_DESPESA = "#C62828"   # vermelho
COR_SALDO = "#1565C0"     # azul


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def real_br(valor: float) -> str:
    """Formata número como moeda brasileira: 12345.6 -> 'R$ 12.345,60'."""
    if pd.isna(valor):
        return "R$ 0,00"
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def valor_para_numero(texto) -> float:
    """Converte 'R$ 12.000,00' -> 12000.0 (formato brasileiro)."""
    if pd.isna(texto):
        return 0.0
    s = (
        str(texto)
        .replace("R$", "")
        .replace(" ", "")
        .replace("\xa0", "")
        .replace(".", "")       # remove separador de milhar
        .replace(",", ".")      # vírgula decimal -> ponto
        .strip()
    )
    if s in ("", "-"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


# ----------------------------------------------------------------------------
# Carregamento dos dados (é AQUI que, na Fase 2, ligamos no Google Sheets ao vivo)
# ----------------------------------------------------------------------------
def _norm(s) -> str:
    """Normaliza nome de coluna: minúsculo e sem acentos."""
    s = str(s).strip().lower().replace("_", " ")
    for a, b in zip("êçáãéíóú", "ecaaeiou"):
        s = s.replace(a, b)
    return " ".join(s.split())


# nomes esperados (normalizados) -> nome interno
_MAPA_COLS = {
    "caixa": "caixa", "valor": "valor", "mes": "mes", "banco": "banco",
    "data": "data", "frequencia": "frequencia",
    "centro de custo": "centro_de_custo",
    "tipo de cadastro": "tipo_de_cadastro", "categoria": "categoria",
}


def _valores_ao_vivo():
    """Lê a aba [LANÇAMENTOS] ao vivo via gspread. Retorna lista de linhas ou None."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # 1) tenta os secrets (quando hospedado no Streamlit Cloud)
        info = None
        try:
            if "gcp_service_account" in st.secrets:
                info = dict(st.secrets["gcp_service_account"])
        except Exception:
            info = None

        if info:
            creds = Credentials.from_service_account_info(info, scopes=ESCOPOS)
        elif CAMINHO_CHAVE.exists():
            creds = Credentials.from_service_account_file(str(CAMINHO_CHAVE), scopes=ESCOPOS)
        else:
            return None

        gc = gspread.authorize(creds)
        ws = gc.open_by_key(SPREADSHEET_ID).worksheet(ABA)
        return ws.get_all_values()  # lista de listas (texto), incluindo cabeçalho
    except Exception as e:
        st.warning(f"Não consegui ler ao vivo do Google Sheets ({e}). Usando dados locais.")
        return None


def _ler_bruto() -> pd.DataFrame:
    """Lê ao vivo do Google Sheets; se não der, cai no CSV local. Acha o cabeçalho."""
    valores = _valores_ao_vivo()
    if valores:
        raw = pd.DataFrame(valores).fillna("").astype(str)
    elif ARQUIVO_DADOS.exists():
        raw = pd.read_csv(ARQUIVO_DADOS, header=None, dtype=str).fillna("")
    else:
        st.error(
            "Não consegui ler a planilha ao vivo e não há backup local. "
            "Verifique a credencial (secrets) e o compartilhamento da planilha."
        )
        st.stop()

    # acha a linha de cabeçalho (a que contém 'caixa' e 'valor')
    linha_cab = 0
    for i in range(min(10, len(raw))):
        vals = [_norm(x) for x in raw.iloc[i].tolist()]
        if "caixa" in vals and "valor" in vals:
            linha_cab = i
            break

    cols = [str(x).strip() for x in raw.iloc[linha_cab].tolist()]
    df = raw.iloc[linha_cab + 1:].copy()
    df.columns = cols

    ren = {c: _MAPA_COLS[_norm(c)] for c in df.columns if _norm(c) in _MAPA_COLS}
    df = df.rename(columns=ren)
    # garante todas as colunas internas
    for nome in _MAPA_COLS.values():
        if nome not in df.columns:
            df[nome] = ""
    return df[list(_MAPA_COLS.values())].reset_index(drop=True)


@st.cache_data(ttl=300)
def carregar_dados() -> pd.DataFrame:
    import re
    df = _ler_bruto().fillna("")

    # remove linhas sem descrição E sem valor (vazias/totais soltos)
    df = df[(df["caixa"].str.strip() != "") | (df["valor"].str.strip() != "")].copy()

    # limpa prefixo de emoji/mojibake da categoria (tudo antes da 1a letra)
    def _limpa_cat(s):
        s = str(s)
        m = re.search(r"[A-Za-zÀ-ÿ]", s)
        return s[m.start():].strip() if m else s.strip()
    df["categoria"] = df["categoria"].apply(_limpa_cat)

    # valor numérico
    df["valor_num"] = df["valor"].apply(valor_para_numero)

    # data -> datetime (formato brasileiro dd/mm/aaaa)
    df["data_dt"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")

    # rótulo de mês ordenável (ex.: 2026-01) e nome amigável (ex.: jan/2026)
    meses_pt = {
        1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
        7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez",
    }
    df["ano_mes"] = df["data_dt"].dt.strftime("%Y-%m")
    df["mes_label"] = df["data_dt"].apply(
        lambda d: f"{meses_pt[d.month]}/{d.year}" if pd.notna(d) else "sem data"
    )

    # normaliza o tipo
    df["tipo_de_cadastro"] = df["tipo_de_cadastro"].str.upper().str.strip()

    return df


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------
df = carregar_dados()

st.title("💰 Dashboard Financeiro — Léo")
st.caption("Fonte: aba [LANÇAMENTOS] · ano 2026")

# ---- Sidebar: filtros --------------------------------------------------------
if st.sidebar.button("🔄 Atualizar agora (puxar da planilha)", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.header("🔎 Filtros")

meses_disp = sorted(
    df.loc[df["ano_mes"] != "", "ano_mes"].unique()
)
mapa_label = dict(zip(df["ano_mes"], df["mes_label"]))
meses_sel = st.sidebar.multiselect(
    "Mês",
    options=meses_disp,
    default=meses_disp,
    format_func=lambda x: mapa_label.get(x, x),
)

tipos_disp = sorted(t for t in df["tipo_de_cadastro"].unique() if t)
tipos_sel = st.sidebar.multiselect("Tipo", options=tipos_disp, default=tipos_disp)

centros_disp = sorted(c for c in df["centro_de_custo"].unique() if c)
centros_sel = st.sidebar.multiselect(
    "Centro de custo", options=centros_disp, default=centros_disp
)

categorias_disp = sorted(c for c in df["categoria"].unique() if c)
categorias_sel = st.sidebar.multiselect(
    "Categoria", options=categorias_disp, default=categorias_disp
)

# ---- Aplica filtros ----------------------------------------------------------
f = df.copy()
if meses_sel:
    f = f[f["ano_mes"].isin(meses_sel)]
if tipos_sel:
    f = f[f["tipo_de_cadastro"].isin(tipos_sel)]
if centros_sel:
    f = f[f["centro_de_custo"].isin(centros_sel)]
if categorias_sel:
    f = f[f["categoria"].isin(categorias_sel)]

receitas = f.loc[f["tipo_de_cadastro"] == "RECEITA", "valor_num"].sum()
despesas = f.loc[f["tipo_de_cadastro"] == "DESPESA", "valor_num"].sum()
ajustes = f.loc[f["tipo_de_cadastro"] == "AJUSTE DE CAIXA", "valor_num"].sum()
saldo = receitas - despesas

# ---- Cartões (KPIs) ----------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Receitas", real_br(receitas))
c2.metric("Despesas", real_br(despesas))
c3.metric("Saldo (Rec - Desp)", real_br(saldo))
c4.metric("Lançamentos", f"{len(f)}")

if ajustes:
    st.caption(f"ℹ️ Ajustes de caixa no período: {real_br(ajustes)} (não somados em receitas/despesas)")

st.divider()

# ---- Gráfico 1: Evolução por mês --------------------------------------------
st.subheader("📈 Evolução por mês")

evol = (
    f[f["tipo_de_cadastro"].isin(["RECEITA", "DESPESA"])]
    .groupby(["ano_mes", "mes_label", "tipo_de_cadastro"], as_index=False)["valor_num"]
    .sum()
    .sort_values("ano_mes")
)
if evol.empty:
    st.info("Sem dados para os filtros selecionados.")
else:
    fig_evol = px.bar(
        evol,
        x="mes_label",
        y="valor_num",
        color="tipo_de_cadastro",
        barmode="group",
        text_auto=".2s",
        color_discrete_map={"RECEITA": COR_RECEITA, "DESPESA": COR_DESPESA},
        labels={"mes_label": "Mês", "valor_num": "Valor (R$)", "tipo_de_cadastro": "Tipo"},
    )
    fig_evol.update_layout(legend_title_text="", yaxis_tickprefix="R$ ")
    st.plotly_chart(fig_evol, use_container_width=True)

# ---- Gráficos 2 e 3: por categoria ------------------------------------------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("💸 Despesas por categoria")
    desp_cat = (
        f[f["tipo_de_cadastro"] == "DESPESA"]
        .groupby("categoria", as_index=False)["valor_num"]
        .sum()
        .sort_values("valor_num", ascending=True)
    )
    if desp_cat.empty:
        st.info("Sem despesas no período.")
    else:
        fig_desp = px.bar(
            desp_cat,
            x="valor_num",
            y="categoria",
            orientation="h",
            text_auto=".2s",
            labels={"valor_num": "Valor (R$)", "categoria": ""},
        )
        fig_desp.update_traces(marker_color=COR_DESPESA)
        fig_desp.update_layout(xaxis_tickprefix="R$ ")
        st.plotly_chart(fig_desp, use_container_width=True)

with col_b:
    st.subheader("🏦 Receitas por centro de custo")
    rec_cc = (
        f[f["tipo_de_cadastro"] == "RECEITA"]
        .groupby("centro_de_custo", as_index=False)["valor_num"]
        .sum()
        .sort_values("valor_num", ascending=False)
    )
    if rec_cc.empty:
        st.info("Sem receitas no período.")
    else:
        fig_rec = px.pie(
            rec_cc,
            names="centro_de_custo",
            values="valor_num",
            hole=0.45,
        )
        fig_rec.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_rec, use_container_width=True)

st.divider()

# ---- Tabela filtrável --------------------------------------------------------
st.subheader("📋 Lançamentos (tabela)")

tabela = f[[
    "data", "caixa", "valor_num", "tipo_de_cadastro",
    "categoria", "centro_de_custo", "frequencia", "mes",
]].copy()
tabela = tabela.rename(columns={
    "data": "Data",
    "caixa": "Descrição",
    "valor_num": "Valor",
    "tipo_de_cadastro": "Tipo",
    "categoria": "Categoria",
    "centro_de_custo": "Centro de custo",
    "frequencia": "Frequência",
    "mes": "Mês",
})
tabela = tabela.sort_values("Data")

st.dataframe(
    tabela,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
    },
)

# Botão de download do que está filtrado
csv_out = tabela.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "⬇️ Baixar tabela filtrada (CSV)",
    data=csv_out,
    file_name="lancamentos_filtrados.csv",
    mime="text/csv",
)
