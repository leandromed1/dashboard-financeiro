"""Página: Dashboard Financeiro Léo (aba [LANÇAMENTOS])."""

import os
import re
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# garante que a pasta raiz do projeto esteja no caminho de busca (p/ achar lib_comum)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib_comum import (
    real_br, valor_para_numero, norm, ler_valores, montar_df, proteger,
    COR_RECEITA, COR_DESPESA,
)

SPREADSHEET_ID = "1Upi8GAmLMM8mMD1VWVk7Z5s3ycYBNl4-qB_tke-chTw"
ABA = "LANÇAMENTOS"
ARQUIVO_BACKUP = Path(__file__).parent.parent / "dados" / "lancamentos_2026.csv"

MAPA = {
    "caixa": "caixa", "valor": "valor", "mes": "mes", "banco": "banco",
    "data": "data", "frequencia": "frequencia",
    "centro de custo": "centro_de_custo",
    "tipo de cadastro": "tipo_de_cadastro", "categoria": "categoria",
}


@st.cache_data(ttl=300)
def carregar() -> pd.DataFrame:
    valores = ler_valores(SPREADSHEET_ID, ABA)

    if isinstance(valores, list):
        df = montar_df(valores, MAPA, ["caixa", "valor"])
    elif ARQUIVO_BACKUP.exists():
        raw = pd.read_csv(ARQUIVO_BACKUP, dtype=str).fillna("")
        df = raw  # backup já vem com as colunas certas
        for nome in MAPA.values():
            if nome not in df.columns:
                df[nome] = ""
    else:
        st.error("Não consegui ler a planilha ao vivo. Verifique a credencial e o compartilhamento.")
        if isinstance(valores, dict):
            st.caption(f"Detalhe: {valores.get('erro')}")
        st.stop()

    df = df.fillna("")
    # remove linhas vazias
    df = df[(df["caixa"].str.strip() != "") | (df["valor"].str.strip() != "")].copy()

    # limpa emoji da categoria
    def limpa_cat(s):
        s = str(s)
        m = re.search(r"[A-Za-zÀ-ÿ]", s)
        return s[m.start():].strip() if m else s.strip()
    df["categoria"] = df["categoria"].apply(limpa_cat)

    df["valor_num"] = df["valor"].apply(valor_para_numero)
    df["data_dt"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    meses_pt = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
                7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}
    df["ano_mes"] = df["data_dt"].dt.strftime("%Y-%m").fillna("")
    df["mes_label"] = df["data_dt"].apply(
        lambda d: f"{meses_pt[d.month]}/{d.year}" if pd.notna(d) else "sem data")
    df["tipo_de_cadastro"] = df["tipo_de_cadastro"].str.upper().str.strip()
    return df


proteger("financeiro", "📊 Financeiro Léo")

df = carregar()

st.title("💰 Dashboard Financeiro — Léo")
st.caption("Fonte: aba [LANÇAMENTOS] · ano 2026")

# ---- filtros ----
st.sidebar.header("🔎 Filtros")
meses_disp = sorted(df.loc[df["ano_mes"] != "", "ano_mes"].unique())
mapa_label = dict(zip(df["ano_mes"], df["mes_label"]))
meses_sel = st.sidebar.multiselect("Mês", meses_disp, default=meses_disp,
                                   format_func=lambda x: mapa_label.get(x, x))
tipos_disp = sorted(t for t in df["tipo_de_cadastro"].unique() if t)
tipos_sel = st.sidebar.multiselect("Tipo", tipos_disp, default=tipos_disp)
centros_disp = sorted(c for c in df["centro_de_custo"].unique() if c)
centros_sel = st.sidebar.multiselect("Centro de custo", centros_disp, default=centros_disp)
categorias_disp = sorted(c for c in df["categoria"].unique() if c)
categorias_sel = st.sidebar.multiselect("Categoria", categorias_disp, default=categorias_disp)

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

c1, c2, c3, c4 = st.columns(4)
c1.metric("Receitas", real_br(receitas))
c2.metric("Despesas", real_br(despesas))
c3.metric("Saldo (Rec - Desp)", real_br(saldo))
c4.metric("Lançamentos", f"{len(f)}")
if ajustes:
    st.caption(f"ℹ️ Ajustes de caixa no período: {real_br(ajustes)} (não somados em receitas/despesas)")

st.divider()

st.subheader("📈 Evolução por mês")
evol = (f[f["tipo_de_cadastro"].isin(["RECEITA", "DESPESA"])]
        .groupby(["ano_mes", "mes_label", "tipo_de_cadastro"], as_index=False)["valor_num"].sum()
        .sort_values("ano_mes"))
if evol.empty:
    st.info("Sem dados para os filtros selecionados.")
else:
    fig = px.bar(evol, x="mes_label", y="valor_num", color="tipo_de_cadastro",
                 barmode="group", text_auto=".2s",
                 color_discrete_map={"RECEITA": COR_RECEITA, "DESPESA": COR_DESPESA},
                 labels={"mes_label": "Mês", "valor_num": "Valor (R$)", "tipo_de_cadastro": "Tipo"})
    fig.update_layout(legend_title_text="", yaxis_tickprefix="R$ ")
    st.plotly_chart(fig, use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("💸 Despesas por categoria")
    desp_cat = (f[f["tipo_de_cadastro"] == "DESPESA"]
                .groupby("categoria", as_index=False)["valor_num"].sum()
                .sort_values("valor_num"))
    if desp_cat.empty:
        st.info("Sem despesas no período.")
    else:
        fig = px.bar(desp_cat, x="valor_num", y="categoria", orientation="h",
                     text_auto=".2s", labels={"valor_num": "Valor (R$)", "categoria": ""})
        fig.update_traces(marker_color=COR_DESPESA)
        fig.update_layout(xaxis_tickprefix="R$ ")
        st.plotly_chart(fig, use_container_width=True)
with col_b:
    st.subheader("🏦 Receitas por centro de custo")
    rec_cc = (f[f["tipo_de_cadastro"] == "RECEITA"]
              .groupby("centro_de_custo", as_index=False)["valor_num"].sum()
              .sort_values("valor_num", ascending=False))
    if rec_cc.empty:
        st.info("Sem receitas no período.")
    else:
        fig = px.pie(rec_cc, names="centro_de_custo", values="valor_num", hole=0.45)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("📋 Lançamentos (tabela)")
tabela = f[["data", "caixa", "valor_num", "tipo_de_cadastro", "categoria",
            "centro_de_custo", "frequencia", "mes"]].copy()
tabela = tabela.rename(columns={
    "data": "Data", "caixa": "Descrição", "valor_num": "Valor",
    "tipo_de_cadastro": "Tipo", "categoria": "Categoria",
    "centro_de_custo": "Centro de custo", "frequencia": "Frequência", "mes": "Mês"})
st.dataframe(tabela.sort_values("Data"), use_container_width=True, hide_index=True,
             column_config={"Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f")})
st.download_button("⬇️ Baixar tabela filtrada (CSV)",
                   data=tabela.to_csv(index=False).encode("utf-8-sig"),
                   file_name="financeiro_filtrado.csv", mime="text/csv")
