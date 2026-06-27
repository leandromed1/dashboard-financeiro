"""Página: Dashboard da Obra Apto DN (aba [LANÇAMENTOS] da planilha consolidada)."""

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

# garante que a pasta raiz do projeto esteja no caminho de busca (p/ achar lib_comum)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib_comum import (
    real_br, valor_para_numero, norm, ler_valores, montar_df, proteger,
    COR_DESPESA, COR_NEUTRA,
)

SPREADSHEET_ID = "1ylYXcXeOk4BhmvkW1P2naYCGBhi7VAo658pefF7xEoU"
ABA = "LANÇAMENTOS"
ABA_CADASTRO = "CADASTRO"

MAPA = {
    "mes": "mes", "vencimento": "vencimento", "descricao": "descricao",
    "fornecedor": "fornecedor", "responsavel pelo custo": "responsavel",
    "categoria": "categoria", "etapa": "etapa",
    "faturamento": "faturamento", "total": "valor",
}
MAPA_CAD = {
    "codigo obra": "codigo", "data de inicio": "data_inicio",
    "prazo final": "prazo_final", "total previsto": "total_previsto",
}


@st.cache_data(ttl=300)
def carregar():
    valores = ler_valores(SPREADSHEET_ID, ABA)
    if not isinstance(valores, list):
        return None, (valores.get("erro") if isinstance(valores, dict) else "desconhecido")

    df = montar_df(valores, MAPA, ["descricao", "etapa", "total"]).fillna("")
    df = df[(df["descricao"].str.strip() != "") | (df["valor"].str.strip() != "")].copy()

    df["valor_num"] = df["valor"].apply(valor_para_numero)
    df["venc_dt"] = pd.to_datetime(df["vencimento"], format="%d/%m/%Y", errors="coerce")
    meses_pt = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
                7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}
    df["ano_mes"] = df["venc_dt"].dt.strftime("%Y-%m").fillna("")
    df["mes_label"] = df["venc_dt"].apply(
        lambda d: f"{meses_pt[d.month]}/{d.year}" if pd.notna(d) else "sem data")
    for c in ["categoria", "etapa", "fornecedor", "responsavel", "faturamento"]:
        df[c] = df[c].str.strip()
    df["fat_norm"] = df["faturamento"].apply(norm)
    return df, None


@st.cache_data(ttl=300)
def carregar_cadastro():
    valores = ler_valores(SPREADSHEET_ID, ABA_CADASTRO)
    if not isinstance(valores, list):
        return {}
    try:
        cad = montar_df(valores, MAPA_CAD, ["codigo obra", "total previsto"])
        linha = cad.iloc[0]
        return {
            "codigo": linha.get("codigo", ""),
            "data_inicio": linha.get("data_inicio", ""),
            "prazo_final": linha.get("prazo_final", ""),
            "total_previsto": valor_para_numero(linha.get("total_previsto", "")),
        }
    except Exception:  # noqa: BLE001
        return {}


proteger("obra", "🏗️ Obra Apto DN")

df, erro = carregar()

st.title("🏗️ Dashboard da Obra — Apto DN")
st.caption("Fonte: aba [LANÇAMENTOS] · planilha O.C CONSOLIDADO - APTO DN - 802")

if df is None:
    st.error("Não consegui ler a planilha da obra ao vivo.")
    st.caption(f"Detalhe: {erro}")
    st.info("Confirme que a planilha foi compartilhada (Leitor) com a conta de serviço "
            "`dashboard-leitor@dashboard-financeiro-500618.iam.gserviceaccount.com`.")
    st.stop()

cad = carregar_cadastro()
previsto = cad.get("total_previsto", 0.0)

# ---- filtros ----
st.sidebar.header("🔎 Filtros")
meses_disp = sorted(df.loc[df["ano_mes"] != "", "ano_mes"].unique())
mapa_label = dict(zip(df["ano_mes"], df["mes_label"]))
meses_sel = st.sidebar.multiselect("Mês", meses_disp, default=meses_disp,
                                   format_func=lambda x: mapa_label.get(x, x))
etapas_disp = sorted(e for e in df["etapa"].unique() if e)
etapas_sel = st.sidebar.multiselect("Etapa", etapas_disp, default=etapas_disp)
cats_disp = sorted(c for c in df["categoria"].unique() if c)
cats_sel = st.sidebar.multiselect("Categoria", cats_disp, default=cats_disp)
resp_disp = sorted(r for r in df["responsavel"].unique() if r)
resp_sel = st.sidebar.multiselect("Responsável", resp_disp, default=resp_disp)
fat_disp = sorted(s for s in df["faturamento"].unique() if s)
fat_sel = st.sidebar.multiselect("Faturamento", fat_disp, default=fat_disp)

f = df.copy()
if meses_sel:
    f = f[f["ano_mes"].isin(meses_sel)]
if etapas_sel:
    f = f[f["etapa"].isin(etapas_sel)]
if cats_sel:
    f = f[f["categoria"].isin(cats_sel)]
if resp_sel:
    f = f[f["responsavel"].isin(resp_sel)]
if fat_sel:
    f = f[f["faturamento"].isin(fat_sel)]

comprometido = f["valor_num"].sum()
pago = f.loc[f["fat_norm"] == "pago", "valor_num"].sum()
a_pagar = comprometido - pago
pct = (comprometido / previsto * 100) if previsto else 0
saldo_orc = previsto - comprometido

c1, c2, c3, c4 = st.columns(4)
c1.metric("Orçamento previsto", real_br(previsto))
c2.metric("Gasto (pago)", real_br(pago))
c3.metric("A pagar", real_br(a_pagar))
c4.metric("% do orçamento usado", f"{pct:.1f}%")

if previsto:
    st.progress(min(1.0, comprometido / previsto))
    cor = "🟢" if saldo_orc >= 0 else "🔴"
    st.caption(f"{cor} Saldo do orçamento: {real_br(saldo_orc)}  ·  "
               f"Comprometido (pago + a pagar): {real_br(comprometido)}  ·  "
               f"{len(f)} lançamentos")
if cad.get("data_inicio"):
    st.caption(f"📅 Início: {cad.get('data_inicio')}  ·  Prazo final: {cad.get('prazo_final')}  "
               f"·  Código: {cad.get('codigo')}")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("🧱 Custo por etapa")
    por_etapa = (f.groupby("etapa", as_index=False)["valor_num"].sum()
                 .sort_values("valor_num"))
    por_etapa = por_etapa[por_etapa["etapa"] != ""]
    if por_etapa.empty:
        st.info("Sem dados.")
    else:
        fig = px.bar(por_etapa, x="valor_num", y="etapa", orientation="h",
                     text_auto=".2s", labels={"valor_num": "Valor (R$)", "etapa": ""})
        fig.update_traces(marker_color=COR_NEUTRA)
        fig.update_layout(xaxis_tickprefix="R$ ")
        st.plotly_chart(fig, use_container_width=True)
with col2:
    st.subheader("🏷️ Custo por categoria")
    por_cat = (f.groupby("categoria", as_index=False)["valor_num"].sum()
               .sort_values("valor_num"))
    por_cat = por_cat[por_cat["categoria"] != ""]
    if por_cat.empty:
        st.info("Sem dados.")
    else:
        fig = px.bar(por_cat, x="valor_num", y="categoria", orientation="h",
                     text_auto=".2s", labels={"valor_num": "Valor (R$)", "categoria": ""})
        fig.update_traces(marker_color=COR_DESPESA)
        fig.update_layout(xaxis_tickprefix="R$ ")
        st.plotly_chart(fig, use_container_width=True)

st.subheader("📈 Evolução de gastos por mês")
evol = (f[f["ano_mes"] != ""].groupby(["ano_mes", "mes_label"], as_index=False)["valor_num"].sum()
        .sort_values("ano_mes"))
if evol.empty:
    st.info("Sem dados.")
else:
    fig = px.bar(evol, x="mes_label", y="valor_num", text_auto=".2s",
                 labels={"mes_label": "Mês", "valor_num": "Valor (R$)"})
    fig.update_traces(marker_color=COR_NEUTRA)
    fig.update_layout(yaxis_tickprefix="R$ ")
    st.plotly_chart(fig, use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    st.subheader("🏬 Top fornecedores")
    forn = (f[f["fornecedor"] != ""].groupby("fornecedor", as_index=False)["valor_num"].sum()
            .sort_values("valor_num", ascending=False).head(12).sort_values("valor_num"))
    if forn.empty:
        st.info("Sem fornecedor informado.")
    else:
        fig = px.bar(forn, x="valor_num", y="fornecedor", orientation="h",
                     text_auto=".2s", labels={"valor_num": "Valor (R$)", "fornecedor": ""})
        fig.update_traces(marker_color=COR_NEUTRA)
        fig.update_layout(xaxis_tickprefix="R$ ")
        st.plotly_chart(fig, use_container_width=True)
with col4:
    st.subheader("👷 Por responsável pelo custo")
    resp = (f[f["responsavel"] != ""].groupby("responsavel", as_index=False)["valor_num"].sum()
            .sort_values("valor_num", ascending=False))
    if resp.empty:
        st.info("Sem responsável informado.")
    else:
        fig = px.pie(resp, names="responsavel", values="valor_num", hole=0.45)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("📋 Lançamentos da obra (tabela)")
tabela = f[["vencimento", "descricao", "valor_num", "categoria", "etapa",
            "fornecedor", "responsavel", "faturamento"]].copy()
tabela = tabela.rename(columns={
    "vencimento": "Vencimento", "descricao": "Descrição", "valor_num": "Valor",
    "categoria": "Categoria", "etapa": "Etapa", "fornecedor": "Fornecedor",
    "responsavel": "Responsável", "faturamento": "Faturamento"})
st.dataframe(tabela.sort_values("Vencimento"), use_container_width=True, hide_index=True,
             column_config={"Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f")})
st.download_button("⬇️ Baixar tabela filtrada (CSV)",
                   data=tabela.to_csv(index=False).encode("utf-8-sig"),
                   file_name="obra_apto_dn_filtrado.csv", mime="text/csv")
