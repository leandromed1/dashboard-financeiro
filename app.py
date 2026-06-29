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
    "paginas/financeiro.py", title="Visão geral", icon="📊", default=True
)
provisionamentos = st.Page(
    "paginas/provisionamentos.py", title="Provisionamentos", icon="📅"
)
obra = st.Page(
    "paginas/obra.py", title="Visão geral", icon="🏗️"
)

# menu agrupado: Provisionamentos vira sub-aba do Financeiro Léo
pg = st.navigation({
    "Financeiro Léo": [financeiro, provisionamentos],
    "Obra Apto DN": [obra],
})
pg.run()
