"""Página: Dashboard Financeiro Léo (aba [LANÇAMENTOS])."""

import os
import re
import sys
import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# garante que a pasta raiz do projeto esteja no caminho de busca (p/ achar lib_comum)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib_comum import (
    real_br, valor_para_numero, norm, ler_valores, montar_df, proteger,
    entidade_de, COR_RECEITA, COR_DESPESA, COR_NEUTRA,
)

SPREADSHEET_ID = "1Upi8GAmLMM8mMD1VWVk7Z5s3ycYBNl4-qB_tke-chTw"
ABA = "LANÇAMENTOS"
ARQUIVO_BACKUP = Path(__file__).parents[3] / "Financeiro" / "lancamentos_2026.csv"  # fonte real = Sheets ao vivo

MAPA = {
    "caixa": "caixa", "valor": "valor", "mes": "mes", "banco": "banco",
    "data": "data", "frequencia": "frequencia",
    "centro de custo": "centro_de_custo",
    "tipo de cadastro": "tipo_de_cadastro", "categoria": "categoria",
}

ORDEM_ENT = ["INSTITUTO", "EMPRESA", "PESSOAL", "OUTROS NEGÓCIOS", "A definir"]


@st.cache_data(ttl=300)
def carregar() -> pd.DataFrame:
    try:
        valores = ler_valores(SPREADSHEET_ID, ABA)
        df = montar_df(valores, MAPA, ["caixa", "valor"])
    except Exception:
        if ARQUIVO_BACKUP.exists():       # fallback local (offline)
            df = pd.read_csv(ARQUIVO_BACKUP, dtype=str).fillna("")
            for nome in MAPA.values():
                if nome not in df.columns:
                    df[nome] = ""
        else:
            raise

    df = df.fillna("")
    df = df[(df["caixa"].str.strip() != "") | (df["valor"].str.strip() != "")].copy()

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
    df["entidade"] = df["centro_de_custo"].apply(entidade_de)
    return df


proteger("financeiro", "📊 Financeiro Léo")

st.title("💰 Dashboard Financeiro — Léo")
st.caption("Fonte: aba [LANÇAMENTOS] · ano 2026")

try:
    df = carregar()
except Exception as e:  # noqa: BLE001
    st.error("Instabilidade ao ler a planilha ao vivo (servidor do Google). "
             "Geralmente passa em alguns segundos.")
    st.caption(f"Detalhe: {e}")
    if st.button("🔄 Tentar de novo"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# ----------------------------------------------------------------------------
# Filtros
# ----------------------------------------------------------------------------
st.sidebar.header("🔎 Filtros")

ents_disp = [e for e in ORDEM_ENT if e in set(df["entidade"])]
ents_sel = st.sidebar.multiselect("🏢 Entidade", ents_disp, default=ents_disp)

meses_disp = sorted(df.loc[df["ano_mes"] != "", "ano_mes"].unique())
mapa_label = dict(zip(df["ano_mes"], df["mes_label"]))
mes_atual = datetime.date.today().strftime("%Y-%m")
default_meses = [mes_atual] if mes_atual in meses_disp else meses_disp
meses_sel = st.sidebar.multiselect("Mês", meses_disp, default=default_meses,
                                   format_func=lambda x: mapa_label.get(x, x))
tipos_disp = sorted(t for t in df["tipo_de_cadastro"].unique() if t)
tipos_sel = st.sidebar.multiselect("Tipo", tipos_disp, default=tipos_disp)
centros_disp = sorted(c for c in df["centro_de_custo"].unique() if c)
centros_sel = st.sidebar.multiselect("Centro de custo", centros_disp, default=centros_disp)
categorias_disp = sorted(c for c in df["categoria"].unique() if c)
categorias_sel = st.sidebar.multiselect("Categoria", categorias_disp, default=categorias_disp)

# base = todos os filtros MENOS o mês (p/ os gráficos de tendência do ano)
base = df.copy()
if ents_sel:
    base = base[base["entidade"].isin(ents_sel)]
if tipos_sel:
    base = base[base["tipo_de_cadastro"].isin(tipos_sel)]
if centros_sel:
    base = base[base["centro_de_custo"].isin(centros_sel)]
if categorias_sel:
    base = base[base["categoria"].isin(categorias_sel)]

fa = base                                                   # ano todo (tendências)
f = base[base["ano_mes"].isin(meses_sel)] if meses_sel else base   # mês selecionado


def soma(d, tipo):
    return d.loc[d["tipo_de_cadastro"] == tipo, "valor_num"].sum()


# ----------------------------------------------------------------------------
# Cartões (mês selecionado)
# ----------------------------------------------------------------------------
rot_mes = ", ".join(mapa_label.get(m, m) for m in meses_sel) if meses_sel else "tudo"
st.caption(f"💳 Cartões, categorias e tabela = **{rot_mes}**  ·  📈 gráficos de tendência = **ano todo** (seguem os demais filtros)")

receitas = soma(f, "RECEITA")
despesas = soma(f, "DESPESA")
ajustes = soma(f, "AJUSTE DE CAIXA")
saldo = receitas - despesas

c1, c2, c3, c4 = st.columns(4)
c1.metric("Receitas", real_br(receitas))
c2.metric("Despesas", real_br(despesas))
c3.metric("Saldo (Rec - Desp)", real_br(saldo))
c4.metric("Lançamentos", f"{len(f)}")
if ajustes:
    st.caption(f"ℹ️ Ajustes de caixa no período: {real_br(ajustes)} (não somados em receitas/despesas)")

st.divider()

# ----------------------------------------------------------------------------
# Resultado por entidade (ano todo)
# ----------------------------------------------------------------------------
st.subheader("🏢 Resultado por entidade (ano)")
ent = (fa[fa["tipo_de_cadastro"].isin(["RECEITA", "DESPESA"])]
       .groupby(["entidade", "tipo_de_cadastro"])["valor_num"].sum().unstack(fill_value=0))
if ent.empty:
    st.info("Sem dados para os filtros selecionados.")
else:
    ent["Receitas"] = ent.get("RECEITA", 0.0)
    ent["Despesas"] = ent.get("DESPESA", 0.0)
    ent["Resultado"] = ent["Receitas"] - ent["Despesas"]
    tab_ent = (ent[["Receitas", "Despesas", "Resultado"]]
               .reindex([e for e in ORDEM_ENT if e in ent.index])
               .reset_index().rename(columns={"entidade": "Entidade"}))
    st.dataframe(
        tab_ent, use_container_width=True, hide_index=True,
        column_config={
            "Receitas": st.column_config.NumberColumn(format="R$ %.2f"),
            "Despesas": st.column_config.NumberColumn(format="R$ %.2f"),
            "Resultado": st.column_config.NumberColumn(format="R$ %.2f"),
        })

st.divider()

# ----------------------------------------------------------------------------
# Evolução por mês (barras) + Curva acumulada (linha) + Saldo de fechamento
# ----------------------------------------------------------------------------
rd = fa[fa["tipo_de_cadastro"].isin(["RECEITA", "DESPESA"])].copy()
mensal = (rd.groupby(["ano_mes", "mes_label", "tipo_de_cadastro"], as_index=False)["valor_num"]
          .sum().sort_values("ano_mes"))
CORES_TIPO = {"RECEITA": COR_RECEITA, "DESPESA": COR_DESPESA}

st.subheader("📊 Receitas × Despesas por mês")
if mensal.empty:
    st.info("Sem dados.")
else:
    fig = px.bar(mensal, x="mes_label", y="valor_num", color="tipo_de_cadastro",
                 barmode="group", text_auto=".2s", color_discrete_map=CORES_TIPO,
                 labels={"mes_label": "Mês", "valor_num": "Valor (R$)", "tipo_de_cadastro": "Tipo"})
    fig.update_layout(legend_title_text="", yaxis_tickprefix="R$ ")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📈 Curva acumulada (receita × despesa)")
    cur = mensal.copy()
    cur["acumulado"] = cur.groupby("tipo_de_cadastro")["valor_num"].cumsum()
    figc = px.line(cur, x="mes_label", y="acumulado", color="tipo_de_cadastro",
                   markers=True, color_discrete_map=CORES_TIPO,
                   labels={"mes_label": "Mês", "acumulado": "Acumulado (R$)", "tipo_de_cadastro": "Tipo"})
    figc.update_layout(legend_title_text="", yaxis_tickprefix="R$ ")
    st.plotly_chart(figc, use_container_width=True)

    st.subheader("💵 Saldo de fechamento por mês (Receitas − Despesas)")
    rd["sgn"] = rd["valor_num"] * rd["tipo_de_cadastro"].map({"RECEITA": 1, "DESPESA": -1})
    sal = rd.groupby(["ano_mes", "mes_label"], as_index=False)["sgn"].sum().sort_values("ano_mes")
    sal["resultado"] = sal["sgn"]
    sal["cor"] = sal["resultado"].apply(lambda v: "positivo" if v >= 0 else "negativo")
    figs = px.bar(sal, x="mes_label", y="resultado", color="cor", text_auto=".2s",
                  color_discrete_map={"positivo": COR_RECEITA, "negativo": COR_DESPESA},
                  labels={"mes_label": "Mês", "resultado": "Saldo (R$)"})
    figs.update_layout(showlegend=False, yaxis_tickprefix="R$ ")
    st.plotly_chart(figs, use_container_width=True)
    st.caption(f"Saldo acumulado do período (ano): **{real_br(sal['resultado'].sum())}**")

st.divider()

# ----------------------------------------------------------------------------
# Categorias / centro de custo (mês selecionado)
# ----------------------------------------------------------------------------
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
    st.subheader("🏦 Receitas por entidade")
    rec_ent = (f[f["tipo_de_cadastro"] == "RECEITA"]
               .groupby("entidade", as_index=False)["valor_num"].sum()
               .sort_values("valor_num", ascending=False))
    if rec_ent.empty:
        st.info("Sem receitas no período.")
    else:
        fig = px.pie(rec_ent, names="entidade", values="valor_num", hole=0.45)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------------
# Tabela (mês selecionado)
# ----------------------------------------------------------------------------
st.subheader("📋 Lançamentos (tabela)")
tabela = f[["data", "caixa", "valor_num", "tipo_de_cadastro", "entidade", "categoria",
            "centro_de_custo", "frequencia", "mes"]].copy()
tabela = tabela.rename(columns={
    "data": "Data", "caixa": "Descrição", "valor_num": "Valor",
    "tipo_de_cadastro": "Tipo", "entidade": "Entidade", "categoria": "Categoria",
    "centro_de_custo": "Centro de custo", "frequencia": "Frequência", "mes": "Mês"})
st.dataframe(tabela.sort_values("Data"), use_container_width=True, hide_index=True,
             column_config={"Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f")})
st.download_button("⬇️ Baixar tabela filtrada (CSV)",
                   data=tabela.to_csv(index=False).encode("utf-8-sig"),
                   file_name="financeiro_filtrado.csv", mime="text/csv")
