"""
Funções compartilhadas pelas páginas do dashboard (Financeiro e Obra).
Cuida da conexão ao vivo com o Google Sheets (gspread) e da limpeza dos dados.
"""

from pathlib import Path
import pandas as pd
import streamlit as st

PASTA = Path(__file__).parent
CAMINHO_CHAVE = PASTA / "credenciais.json"          # chave local (dev)
ESCOPOS = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Cores padrão
COR_RECEITA = "#2E7D32"   # verde
COR_DESPESA = "#C62828"   # vermelho
COR_NEUTRA = "#1565C0"    # azul


# ----------------------------------------------------------------------------
# Formatação / parsing (formato brasileiro)
# ----------------------------------------------------------------------------
def real_br(valor: float) -> str:
    """12345.6 -> 'R$ 12.345,60'."""
    if pd.isna(valor):
        return "R$ 0,00"
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def valor_para_numero(texto) -> float:
    """'R$ 12.000,00' -> 12000.0."""
    if pd.isna(texto):
        return 0.0
    s = (
        str(texto)
        .replace("R$", "").replace(" ", "").replace("\xa0", "")
        .replace(".", "").replace(",", ".").strip()
    )
    if s in ("", "-"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def norm(s) -> str:
    """Normaliza nome de coluna: minúsculo, sem acento, sem underscore."""
    s = str(s).strip().lower().replace("_", " ")
    for a, b in zip("êçáãéíóúâõà", "ecaaeiouaoa"):
        s = s.replace(a, b)
    return " ".join(s.split())


# ----------------------------------------------------------------------------
# Conexão ao vivo (gspread). Usa st.secrets na nuvem, ou credenciais.json local.
# ----------------------------------------------------------------------------
@st.cache_resource
def _cliente():
    from google.oauth2.service_account import Credentials
    import gspread

    if "gcp_service_account" in st.secrets:
        info = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(info, scopes=ESCOPOS)
    elif CAMINHO_CHAVE.exists():
        creds = Credentials.from_service_account_file(str(CAMINHO_CHAVE), scopes=ESCOPOS)
    else:
        return None
    return gspread.authorize(creds)


@st.cache_data(ttl=300, show_spinner=False)
def ler_valores(spreadsheet_id: str, aba: str):
    """Lê todos os valores de uma aba ao vivo. Tenta algumas vezes (a API do Google
    às vezes responde 502/503 temporário). Levanta erro se falhar — assim o cache
    NÃO guarda a falha (cache_data não cacheia exceções)."""
    import time
    cli = _cliente()
    if cli is None:
        raise RuntimeError("Credencial não configurada nos secrets.")
    ultimo = None
    for tentativa in range(3):
        try:
            return cli.open_by_key(spreadsheet_id).worksheet(aba).get_all_values()
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(2)
    raise RuntimeError(str(ultimo))


def proteger(chave: str, titulo: str):
    """Trava de senha por página. A senha fica em st.secrets['senhas'][chave].
    Se não houver senha configurada para a página, o acesso fica liberado."""
    try:
        senhas = st.secrets.get("senhas", {})
    except Exception:  # noqa: BLE001
        senhas = {}
    senha_certa = senhas.get(chave) if hasattr(senhas, "get") else None

    if not senha_certa:
        return  # sem senha configurada -> acesso liberado

    if st.session_state.get(f"auth_{chave}"):
        with st.sidebar:
            if st.button("🔒 Sair", key=f"sair_{chave}"):
                st.session_state[f"auth_{chave}"] = False
                st.rerun()
        return

    st.title(titulo)
    st.caption("🔒 Área protegida — digite a senha para acessar este painel.")
    senha = st.text_input("Senha", type="password", key=f"pw_{chave}")
    if st.button("Entrar", key=f"go_{chave}"):
        if senha == str(senha_certa):
            st.session_state[f"auth_{chave}"] = True
            st.rerun()
        else:
            st.error("Senha incorreta. Tente novamente.")
    st.stop()


def montar_df(valores, mapa: dict, marcadores: list) -> pd.DataFrame:
    """Acha a linha de cabeçalho (que contém os 'marcadores') e devolve um DataFrame
    só com as colunas internas definidas em 'mapa' (chave normalizada -> nome interno)."""
    raw = pd.DataFrame(valores).fillna("").astype(str)
    hi = 0
    for i in range(min(15, len(raw))):
        cels = [norm(x) for x in raw.iloc[i].tolist()]
        if all(m in cels for m in marcadores):
            hi = i
            break
    cols = [str(x).strip() for x in raw.iloc[hi].tolist()]
    df = raw.iloc[hi + 1:].copy()
    df.columns = cols
    ren = {c: mapa[norm(c)] for c in df.columns if norm(c) in mapa}
    df = df.rename(columns=ren)
    internos = list(dict.fromkeys(mapa.values()))
    for nome in internos:
        if nome not in df.columns:
            df[nome] = ""
    return df[internos].reset_index(drop=True)
