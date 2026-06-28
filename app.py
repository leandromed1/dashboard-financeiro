"""
Dashboard do Léo — app com múltiplas páginas (mesmo link).
  • Financeiro Léo  (aba [LANÇAMENTOS] da planilha 2026 - FINANCEIRO LEO)
  • Obra Apto DN    (aba [LANÇAMENTOS] da planilha O.C CONSOLIDADO - APTO DN - 802)

Para rodar:
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Dashboards do Léo",
    page_icon="📊",
    layout="wide",
)

financeiro = st.Page(
    "paginas/financeiro.py", title="Financeiro Léo", icon="📊", default=True
)
obra = st.Page(
    "paginas/obra.py", title="Obra Apto DN", icon="🏗️"
)
provisionamentos = st.Page(
    "paginas/provisionamentos.py", title="Provisionamentos", icon="📅"
)

pg = st.navigation([financeiro, obra, provisionamentos])
pg.run()
