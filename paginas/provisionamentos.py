"""Página: Provisionamentos (receitas/despesas futuras) — aba [PROVISIONAMENTOS]."""

import os
import sys
import re
import calendar
import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib_comum import (
    real_br, valor_para_numero, ler_valores, montar_df, proteger,
    COR_RECEITA, COR_DESPESA,
)

SPREADSHEET_ID = "1Upi8GAmLMM8mMD1VWVk7Z5s3ycYBNl4-qB_tke-chTw"
ABA = "PROVISIONAMENTOS"

MAPA = {
    "descricao": "descricao", "tipo": "tipo", "valor": "valor",
    "vencimento": "vencimento", "recorrencia": "recorrencia",
    "categoria": "categoria", "email": "email", "status": "status",
    "avisado em": "avisado_em", "observacao": "observacao",
}


def _proxima_data(venc, hoje):
    """Converte o vencimento em data:
    - data completa (DD/MM/AAAA), p/ itens ÚNICA → essa data
    - 'dia X', p/ itens MENSAL → próxima ocorrência (este mês se ainda não passou, senão o próximo)."""
    s = str(venc).strip()
    if not s:
        return pd.NaT
    m = re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", s)
    if m:
        return pd.to_datetime(m.group(0), dayfirst=True, errors="coerce")
    md = re.search(r"\d{1,2}", s)
    if md:
        dia = int(md.group(0))
        ano, mes = hoje.year, hoje.month
        if dia < hoje.day:
            mes += 1
            if mes > 12:
                mes, ano = 1, ano + 1
        ultimo = calendar.monthrange(ano, mes)[1]
        return pd.Timestamp(ano, mes, min(dia, ultimo))
    return pd.NaT


@st.cache_data(ttl=300)
def carregar() -> pd.DataFrame:
    valores = ler_valores(SPREADSHEET_ID, ABA)  # levanta erro se falhar
    df = montar_df(valores, MAPA, ["descricao", "tipo", "vencimento"]).fillna("")
    df = df[(df["descricao"].str.strip() != "") | (df["valor"].str.strip() != "")].copy()

    df["valor_num"] = df["valor"].apply(valor_para_numero)
    hoje = datetime.date.today()
    df["venc_dt"] = df["vencimento"].apply(lambda x: _proxima_data(x, hoje))
    df["tipo_n"] = df["tipo"].str.upper().str.strip()
    df["status_n"] = df["status"].str.upper().str.strip()
    df["aberto"] = ~df["status_n"].isin(["PAGO", "RECEBIDO", "CANCELADO"])
    meses_pt = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
                7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}
    df["ano_mes"] = df["venc_dt"].dt.strftime("%Y-%m").fillna("")
    df["mes_label"] = df["venc_dt"].apply(
        lambda d: f"{meses_pt[d.month]}/{d.year}" if pd.notna(d) else "sem data")
    return df


# usa a MESMA senha (e login) da página Financeiro Léo
proteger("financeiro", "📅 Provisionamentos")

st.title("📅 Provisionamentos")
st.caption("Fonte: aba [PROVISIONAMENTOS] · receitas e despesas previstas")

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

if df.empty:
    st.info("Ainda não há provisionamentos cadastrados na aba [PROVISIONAMENTOS].")
    st.stop()

hoje = datetime.date.today()
df["dias"] = df["venc_dt"].apply(lambda d: (d.date() - hoje).days if pd.notna(d) else None)

# ---- filtros ----
st.sidebar.header("🔎 Filtros")
status_disp = sorted(s for s in df["status"].unique() if s.strip())
status_sel = st.sidebar.multiselect("Status", status_disp, default=status_disp)
tipos_disp = sorted(t for t in df["tipo_n"].unique() if t)
tipos_sel = st.sidebar.multiselect("Tipo", tipos_disp, default=tipos_disp)
cats_disp = sorted(c for c in df["categoria"].unique() if c.strip())
cats_sel = st.sidebar.multiselect("Categoria", cats_disp, default=cats_disp)

f = df.copy()
if status_sel:
    f = f[f["status"].isin(status_sel)]
if tipos_sel:
    f = f[f["tipo_n"].isin(tipos_sel)]
if cats_sel:
    f = f[f["categoria"].isin(cats_sel)]

abertos = f[f["aberto"]]
rec_prev = abertos.loc[abertos["tipo_n"] == "RECEITA", "valor_num"].sum()
desp_prev = abertos.loc[abertos["tipo_n"] == "DESPESA", "valor_num"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Receitas previstas (em aberto)", real_br(rec_prev))
c2.metric("Despesas previstas (em aberto)", real_br(desp_prev))
c3.metric("Saldo previsto", real_br(rec_prev - desp_prev))
c4.metric("Itens em aberto", f"{len(abertos)}")

st.divider()

# ---- Vencidos e A vencer ----
vencidos = abertos[abertos["dias"].notna() & (abertos["dias"] < 0)].sort_values("venc_dt")
a_vencer = abertos[abertos["dias"].notna() & (abertos["dias"] >= 0) & (abertos["dias"] <= 30)].sort_values("venc_dt")

COLS = {"vencimento": "Vencimento", "descricao": "Descrição", "tipo": "Tipo",
        "valor_num": "Valor", "categoria": "Categoria", "status": "Status", "dias": "Dias"}


def mostra_tabela(dados):
    t = dados[list(COLS.keys())].rename(columns=COLS)
    st.dataframe(t, use_container_width=True, hide_index=True,
                 column_config={"Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f")})


col1, col2 = st.columns(2)
with col1:
    st.subheader(f"🔴 Vencidos ({len(vencidos)})")
    if vencidos.empty:
        st.success("Nada vencido em aberto. 🎉")
    else:
        mostra_tabela(vencidos)
with col2:
    st.subheader(f"🟡 A vencer (próx. 30 dias) ({len(a_vencer)})")
    if a_vencer.empty:
        st.info("Nada a vencer nos próximos 30 dias.")
    else:
        mostra_tabela(a_vencer)

st.divider()

# ---- Previsto por mês ----
st.subheader("📈 Previsto por mês")
evol = (f[f["ano_mes"] != ""].groupby(["ano_mes", "mes_label", "tipo_n"], as_index=False)["valor_num"].sum()
        .sort_values("ano_mes"))
if evol.empty:
    st.info("Sem datas de vencimento para montar o gráfico.")
else:
    fig = px.bar(evol, x="mes_label", y="valor_num", color="tipo_n", barmode="group",
                 text_auto=".2s",
                 color_discrete_map={"RECEITA": COR_RECEITA, "DESPESA": COR_DESPESA},
                 labels={"mes_label": "Mês", "valor_num": "Valor (R$)", "tipo_n": "Tipo"})
    fig.update_layout(legend_title_text="", yaxis_tickprefix="R$ ")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("📋 Todos os provisionamentos")
mostra_tabela(f.sort_values("venc_dt"))
