# -*- coding: utf-8 -*-
import sys, io, os, re, datetime, calendar
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import gspread
from google.oauth2.service_account import Credentials
KEY=r"H:\Meu Drive\templo do léo\meuinbox\06 claude\dashboard-financeiro\credenciais.json"
SID="1Upi8GAmLMM8mMD1VWVk7Z5s3ycYBNl4-qB_tke-chTw"
LINK="https://dashboard-financeiro-beuwd6bvhjcmjcec5pq7ro.streamlit.app"
gc=gspread.authorize(Credentials.from_service_account_file(KEY,scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]))
sh=gc.open_by_key(SID)
def num(t):
    s=str(t).replace("R$","").replace(" ","").replace("\xa0","").replace(".","").replace(",",".").strip()
    try:return float(s) if s not in("","-") else 0.0
    except:return 0.0
def br(n): return "R$ "+f"{n:,.2f}".replace(",","X").replace(".",",").replace("X",".")
def ent(cc):
    c=str(cc).strip().upper()
    if c=="INSTITUTO":return "Instituto"
    if c in ("LBTEC","CM_ARQ","PROJETOS","RTS") or c.startswith("OBRA"):return "Empresa"
    if c in ("LEANDRO PESSOAL","DIVIDAS"):return "Pessoal"
    if c in ("SOGARAPAHOME","NEGOCIOS A PARTE"):return "Outros Negócios"
    return "A definir"
hoje=datetime.date.today(); mk=(hoje.year,hoje.month)
MES3=["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]
nomeMes=f"{MES3[hoje.month-1]}/{hoje.year}"
# LANCAMENTOS mes vigente
v=sh.worksheet("LANÇAMENTOS").get_all_values(); hdr=[c.strip().lower() for c in v[0]]
ic=hdr.index("centro de custo"); it=hdr.index("tipo de cadastro"); iv=hdr.index("valor"); idd=hdr.index("data"); ica=hdr.index("categoria")
totR=totD=0.0; recE={}; despE={}; despC={}
for r in v[1:]:
    if len(r)<=max(ic,it,iv,idd,ica): continue
    d=re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})",str(r[idd]))
    if not d: continue
    y=int(d.group(3)); y=y+2000 if y<100 else y
    if (y,int(d.group(2)))!=mk: continue
    val=num(r[iv]); tp=str(r[it]).strip().upper(); e=ent(r[ic])
    if tp=="RECEITA": totR+=val; recE[e]=recE.get(e,0)+val
    elif tp=="DESPESA":
        totD+=val; despE[e]=despE.get(e,0)+val
        cat=re.sub(r'^[^A-Za-zÀ-ÿ]+','',str(r[ica])).strip() or "(sem categoria)"
        despC[cat]=despC.get(cat,0)+val
saldo=totR-totD
# PROVISIONAMENTOS a vencer 7d
pv=sh.worksheet("PROVISIONAMENTOS").get_all_values()
def prox(venc):
    s=str(venc).strip()
    m=re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})",s)
    if m:
        a=int(m.group(3)); a=a+2000 if a<100 else a
        try:return datetime.date(a,int(m.group(2)),int(m.group(1)))
        except:return None
    md=re.search(r"(\d{1,2})",s)
    if md:
        dd=int(md.group(1)); a,me=hoje.year,hoje.month
        if dd<hoje.day:
            me+=1
            if me>12:me=1;a+=1
        dd=min(dd,calendar.monthrange(a,me)[1]); return datetime.date(a,me,dd)
    return None
aPagar=aReceber=0.0; itens=[]
ph=[c.strip().lower() for c in pv[0]]
def gi(name,default): 
    return ph.index(name) if name in ph else default
pdesc=0; ptipo=ph.index("tipo") if "tipo" in ph else 1; pval=ph.index("valor") if "valor" in ph else 2
pvenc=ph.index("vencimento") if "vencimento" in ph else 3; pstat=ph.index("status") if "status" in ph else 7
for r in pv[1:]:
    if len(r)<=max(ptipo,pval,pvenc,pstat): continue
    if not str(r[pdesc]).strip(): continue
    if str(r[pstat]).strip().upper() in ("PAGO","RECEBIDO","CANCELADO"): continue
    due=prox(r[pvenc])
    if not due: continue
    dias=(due-hoje).days
    if dias<0 or dias>7: continue
    val=num(r[pval])
    if "receita" in str(r[ptipo]).lower(): aReceber+=val
    else: aPagar+=val
    itens.append((dias,str(r[pdesc]),str(r[ptipo]),str(r[pval])))
itens.sort()
# HTML
ordem=["Instituto","Empresa","Pessoal","Outros Negócios","A definir"]
h=['<div style="font-family:Arial,sans-serif;max-width:640px;color:#222">']
h.append(f'<h2>📊 Resumo Financeiro — {nomeMes}</h2>')
h.append('<p>Olá, Léo! Panorama da semana:</p>')
h.append('<h3>📅 Mês vigente</h3><table style="border-collapse:collapse">')
h.append(f'<tr><td style="padding:3px 18px 3px 0">Receitas</td><td style="color:#2E7D32">{br(totR)}</td></tr>')
h.append(f'<tr><td style="padding:3px 18px 3px 0">Despesas</td><td style="color:#C62828">{br(totD)}</td></tr>')
h.append(f'<tr><td style="padding:3px 18px 3px 0"><b>Saldo</b></td><td style="color:{"#2E7D32" if saldo>=0 else "#C62828"}"><b>{br(saldo)}</b></td></tr></table>')
h.append('<h3>🏢 Resultado por entidade (mês)</h3><table border="1" cellpadding="6" style="border-collapse:collapse">')
h.append('<tr style="background:#f2f2f2"><th align="left">Entidade</th><th align="right">Receitas</th><th align="right">Despesas</th><th align="right">Resultado</th></tr>')
for e in ordem:
    rr=recE.get(e,0); dd=despE.get(e,0)
    if rr==0 and dd==0: continue
    res=rr-dd
    h.append(f'<tr><td>{e}</td><td align="right">{br(rr)}</td><td align="right">{br(dd)}</td><td align="right" style="color:{"#2E7D32" if res>=0 else "#C62828"}"><b>{br(res)}</b></td></tr>')
h.append('</table>')
cats=sorted(despC.items(),key=lambda x:-x[1])[:5]
if cats:
    h.append('<h3>💸 Maiores gastos do mês</h3><ul>')
    for c,val in cats: h.append(f'<li>{c} — {br(val)}</li>')
    h.append('</ul>')
h.append('<h3>⏳ A vencer nos próximos 7 dias</h3>')
h.append(f'<p>💸 A pagar: <b>{br(aPagar)}</b> &nbsp;|&nbsp; 📥 A receber: <b>{br(aReceber)}</b></p>')
if itens:
    h.append('<ul>')
    for dias,desc,tp,val in itens:
        q="hoje" if dias==0 else f"em {dias}d"
        h.append(f'<li>{desc} ({tp}) — {val} — {q}</li>')
    h.append('</ul>')
h.append(f'<p style="margin-top:20px"><a href="{LINK}" style="background:#1565C0;color:#fff;padding:11px 18px;border-radius:6px;text-decoration:none;font-weight:bold">📊 Abrir o dashboard completo</a></p>')
h.append('<p style="color:#888;font-size:12px">Resumo enviado manualmente (teste) · planilha 2026 - FINANCEIRO LEO</p></div>')
html="".join(h)
out=os.path.join(os.environ.get("TEMP", os.path.dirname(__file__)), "resumo_semanal.html")
open(out,"w",encoding="utf-8").write(html)
print("ASSUNTO: Resumo Financeiro semanal - "+nomeMes)
print("HTML_FILE:",out)
print("mes:",nomeMes,"| Rec",br(totR),"| Desp",br(totD),"| Saldo",br(saldo))
print("a pagar 7d:",br(aPagar),"| a receber 7d:",br(aReceber),"| itens:",len(itens))
print("chars:",len(html))
