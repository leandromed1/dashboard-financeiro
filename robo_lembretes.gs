/**
 * Robô de Lembretes de Provisionamentos — Léo
 * --------------------------------------------------------------
 * Roda todo dia e envia 1 email (por destinatário) com os lançamentos
 * que vencem em até 5 dias e que NÃO estão PAGO/RECEBIDO/CANCELADO.
 * Marca a coluna "avisado em" pra não repetir o mesmo vencimento.
 *
 * Entende a convenção da aba:
 *   - recorrência ÚNICA  -> vencimento é uma data fixa (DD/MM/AAAA)
 *   - recorrência MENSAL -> vencimento é "dia X" (calcula a próxima data)
 *
 * COMO INSTALAR:
 *   1) Na planilha: menu Extensões > Apps Script
 *   2) Apague o conteúdo e cole ESTE arquivo. Salve (ícone de disquete).
 *   3) Selecione a função "criarGatilhoDiario" e clique em Executar (▶).
 *      - Autorize quando pedir (é a sua conta enviando seus emails).
 *   4) (opcional) Rode "enviarLembretes" para testar agora.
 */

const ABA = "PROVISIONAMENTOS";
const DIAS_ANTES = 5;
const EMAIL_PADRAO = "leandromedeirosarq@gmail.com";

// colunas (0-based): A=0, B=1, ...
const COL = { desc:0, tipo:1, valor:2, venc:3, recor:4, cat:5, email:6, status:7, avisado:8, obs:9 };

function enviarLembretes() {
  reordenarPorDia(); // mantém a aba sempre em ordem de dia (receitas novas entram no lugar certo)
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ABA);
  const dados = sh.getDataRange().getValues();
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);

  const porEmail = {}; // email -> lista de itens

  for (let i = 1; i < dados.length; i++) {
    const row = dados[i];
    const desc = String(row[COL.desc] || "").trim();
    if (!desc) continue;

    const status = String(row[COL.status] || "").trim().toUpperCase();
    if (["PAGO", "RECEBIDO", "CANCELADO"].indexOf(status) >= 0) continue;

    const due = proximaData(row[COL.venc], hoje);
    if (!due) continue;

    const dias = Math.round((due - hoje) / 86400000);
    if (dias < 0 || dias > DIAS_ANTES) continue;

    const dueStr = formata(due);
    if (String(row[COL.avisado] || "").trim() === dueStr) continue; // já avisado

    const email = String(row[COL.email] || "").trim() || EMAIL_PADRAO;
    (porEmail[email] = porEmail[email] || []).push({
      linha: i + 1, desc: desc, tipo: String(row[COL.tipo] || ""),
      tipoLow: String(row[COL.tipo] || "").trim().toLowerCase(),
      valor: String(row[COL.valor] || ""), valorNum: paraNumero(row[COL.valor]),
      cat: String(row[COL.cat] || ""), dias: dias, dueStr: dueStr
    });
  }

  for (const email in porEmail) {
    const itens = porEmail[email];
    // Enviado como HTML (UTF-8) para os acentos saírem corretos.
    let html = "<p>Ol&aacute;, L&eacute;o!</p>" +
               "<p>Estes lan&ccedil;amentos vencem nos pr&oacute;ximos " + DIAS_ANTES + " dias:</p><ul>";
    let totDesp = 0, totRec = 0;
    itens.forEach(function (it) {
      const quando = it.dias === 0 ? "vence <b>HOJE</b>" : "em " + it.dias + " dia(s)";
      html += "<li><b>" + it.desc + "</b> (" + it.tipo + ") - " + it.valor +
              " - " + quando + " - vencimento " + it.dueStr +
              (it.cat ? " - " + it.cat : "") + "</li>";
      if (it.tipoLow.indexOf("receita") >= 0) totRec += it.valorNum; else totDesp += it.valorNum;
    });
    html += "</ul>";
    html += "<p style=\"font-size:15px\">" +
            "&#128176; <b>Total a pagar (precisa levantar): " + formataReais(totDesp) + "</b><br>" +
            "&#128229; Total a receber: " + formataReais(totRec) + "<br>" +
            "&#128202; Saldo previsto: " + formataReais(totRec - totDesp) + "</p>";
    html += "<p style=\"color:#888\">Rob&ocirc; de Provisionamentos &middot; planilha 2026 - FINANCEIRO LEO</p>";

    GmailApp.sendEmail(email, "Lembrete: lancamentos a vencer (" + itens.length + ")", "", {
      htmlBody: html,
      name: "Robo Provisionamentos"
    });
    itens.forEach(function (it) { sh.getRange(it.linha, COL.avisado + 1).setValue(it.dueStr); });
  }
}

// ÚNICA -> data fixa; MENSAL ("dia X") -> próxima ocorrência
function proximaData(venc, hoje) {
  // Se a célula for uma DATA real (ÚNICA), o Sheets devolve um objeto Date.
  if (venc instanceof Date) {
    const d = new Date(venc.getFullYear(), venc.getMonth(), venc.getDate());
    d.setHours(0, 0, 0, 0);
    return d;
  }
  const s = String(venc || "").trim();
  if (!s) return null;

  let m = s.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
  if (m) {
    let ano = parseInt(m[3], 10); if (ano < 100) ano += 2000;
    const d = new Date(ano, parseInt(m[2], 10) - 1, parseInt(m[1], 10));
    d.setHours(0, 0, 0, 0);
    return d;
  }
  m = s.match(/(\d{1,2})/); // "dia X"
  if (m) {
    const dia = parseInt(m[1], 10);
    let ano = hoje.getFullYear(), mes = hoje.getMonth();
    let due = new Date(ano, mes, Math.min(dia, ultimoDia(ano, mes))); due.setHours(0, 0, 0, 0);
    if (due < hoje) { mes++; if (mes > 11) { mes = 0; ano++; }
      due = new Date(ano, mes, Math.min(dia, ultimoDia(ano, mes))); due.setHours(0, 0, 0, 0); }
    return due;
  }
  return null;
}

function ultimoDia(ano, mes) { return new Date(ano, mes + 1, 0).getDate(); }

// "R$ 1.234,56" -> 1234.56
function paraNumero(v) {
  var s = String(v || "").replace("R$", "").replace(/\s/g, "").replace(/\./g, "").replace(",", ".").trim();
  var n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}

// 1234.56 -> "R$ 1.234,56"
function formataReais(n) {
  var s = (Math.round(n * 100) / 100).toFixed(2).split(".");
  var inteiro = s[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return "R$ " + inteiro + "," + s[1];
}

function formata(d) {
  const p = function (n) { return (n < 10 ? "0" : "") + n; };
  return p(d.getDate()) + "/" + p(d.getMonth() + 1) + "/" + d.getFullYear();
}

// Reordena as linhas pela ordem do dia de vencimento (dia 1 -> 31).
// Roda junto com o envio diário; pode também ser executada manualmente.
function reordenarPorDia() {
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ABA);
  const dados = sh.getDataRange().getValues();
  if (dados.length <= 2) return;
  const header = dados[0];
  const origN = dados.length - 1;
  let linhas = dados.slice(1).filter(function (r) {
    return String(r[COL.desc] || "").trim() !== "" || String(r[COL.valor] || "").trim() !== "";
  });
  linhas.sort(function (a, b) { return diaDe(a[COL.venc]) - diaDe(b[COL.venc]); });
  if (linhas.length > 0) sh.getRange(2, 1, linhas.length, header.length).setValues(linhas);
  if (linhas.length < origN) {
    sh.getRange(2 + linhas.length, 1, origN - linhas.length, header.length).clearContent();
  }
}

function diaDe(venc) {
  if (venc instanceof Date) return venc.getDate();
  const s = String(venc || "").trim();
  let m = s.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
  if (m) return parseInt(m[1], 10);
  m = s.match(/(\d{1,2})/);
  if (m) return parseInt(m[1], 10);
  return 999;
}

// Rode UMA vez para agendar o envio diário (08h).
function criarGatilhoDiario() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === "enviarLembretes") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("enviarLembretes").timeBased().everyDays(1).atHour(8).create();
}


/* ====================================================================
 *  RESUMO SEMANAL (domingo 20h) - panorama do mes por entidade + a vencer
 * ==================================================================== */
const ABA_LANC = "LANÇAMENTOS";                 // "LANÇAMENTOS" (escape p/ independer de encoding)
const LINK_DASH = "https://dashboard-financeiro-beuwd6bvhjcmjcec5pq7ro.streamlit.app/";
const MES3 = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
// colunas da LANCAMENTOS: caixa0 valor1 mes2 banco3 data4 freq5 centro6 tipo7 categoria8

function entidadeDe(centro) {
  var c = String(centro || "").trim().toUpperCase();
  if (c === "INSTITUTO") return "Instituto";
  if (["LBTEC", "CM_ARQ", "PROJETOS", "RTS"].indexOf(c) >= 0 || c.indexOf("OBRA") === 0) return "Empresa";
  if (["LEANDRO PESSOAL", "DIVIDAS"].indexOf(c) >= 0) return "Pessoal";
  if (["SOGARAPAHOME", "NEGOCIOS A PARTE"].indexOf(c) >= 0) return "Outros Negocios";
  return "A definir";
}

function mesChaveDe(dataVal) {
  if (dataVal instanceof Date) return dataVal.getFullYear() * 100 + (dataVal.getMonth() + 1);
  var s = String(dataVal || "").trim();
  var m = s.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
  if (m) { var y = parseInt(m[3], 10); if (y < 100) y += 2000; return y * 100 + parseInt(m[2], 10); }
  return 0;
}

function _kv(k, v, cor) {
  return "<tr><td style=\"padding:3px 18px 3px 0\">" + k + "</td><td style=\"padding:3px 0;color:" +
         (cor || "#222") + "\">" + v + "</td></tr>";
}

function resumoSemanal() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hoje = new Date();
  var mk = hoje.getFullYear() * 100 + (hoje.getMonth() + 1);
  var nomeMes = MES3[hoje.getMonth()] + "/" + hoje.getFullYear();

  // ---- LANCAMENTOS: mes vigente ----
  var lanc = ss.getSheetByName(ABA_LANC).getDataRange().getValues();
  var totRec = 0, totDesp = 0, recEnt = {}, despEnt = {}, despCat = {};
  for (var i = 1; i < lanc.length; i++) {
    var r = lanc[i];
    if (!String(r[0] || "").trim() && !String(r[1] || "").trim()) continue;
    if (mesChaveDe(r[4]) !== mk) continue;
    var v = paraNumero(r[1]);
    var tipo = String(r[7] || "").trim().toUpperCase();
    var ent = entidadeDe(r[6]);
    if (tipo === "RECEITA") { totRec += v; recEnt[ent] = (recEnt[ent] || 0) + v; }
    else if (tipo === "DESPESA") {
      totDesp += v; despEnt[ent] = (despEnt[ent] || 0) + v;
      var cat = String(r[8] || "").replace(/^[^A-Za-zÀ-ÿ]+/, "").trim() || "(sem categoria)";
      despCat[cat] = (despCat[cat] || 0) + v;
    }
  }
  var saldoMes = totRec - totDesp;

  // ---- PROVISIONAMENTOS: a vencer nos proximos 7 dias ----
  var prov = ss.getSheetByName(ABA).getDataRange().getValues();
  var h0 = new Date(); h0.setHours(0, 0, 0, 0);
  var aPagar = 0, aReceber = 0, itens = [];
  for (var j = 1; j < prov.length; j++) {
    var p = prov[j];
    if (!String(p[COL.desc] || "").trim()) continue;
    var stt = String(p[COL.status] || "").trim().toUpperCase();
    if (["PAGO", "RECEBIDO", "CANCELADO"].indexOf(stt) >= 0) continue;
    var due = proximaData(p[COL.venc], h0);
    if (!due) continue;
    var dias = Math.round((due - h0) / 86400000);
    if (dias < 0 || dias > 7) continue;
    var val = paraNumero(p[COL.valor]);
    if (String(p[COL.tipo] || "").toLowerCase().indexOf("receita") >= 0) aReceber += val; else aPagar += val;
    itens.push({ desc: String(p[COL.desc]), tipo: String(p[COL.tipo]), valor: String(p[COL.valor]), dias: dias });
  }

  // ---- HTML ----
  var ordem = ["Instituto", "Empresa", "Pessoal", "Outros Negocios", "A definir"];
  var html = "<div style=\"font-family:Arial,sans-serif;max-width:640px;color:#222\">";
  html += "<h2>&#128202; Resumo Financeiro &mdash; " + nomeMes + "</h2>";
  html += "<p>Ol&aacute;, L&eacute;o! Panorama da semana:</p>";

  html += "<h3>&#128197; M&ecirc;s vigente</h3><table style=\"border-collapse:collapse\">";
  html += _kv("Receitas", formataReais(totRec), "#2E7D32");
  html += _kv("Despesas", formataReais(totDesp), "#C62828");
  html += _kv("<b>Saldo</b>", "<b>" + formataReais(saldoMes) + "</b>", saldoMes >= 0 ? "#2E7D32" : "#C62828");
  html += "</table>";

  html += "<h3>&#127970; Resultado por entidade (m&ecirc;s)</h3>";
  html += "<table style=\"border-collapse:collapse\" border=\"1\" cellpadding=\"6\">";
  html += "<tr style=\"background:#f2f2f2\"><th align=\"left\">Entidade</th><th align=\"right\">Receitas</th><th align=\"right\">Despesas</th><th align=\"right\">Resultado</th></tr>";
  ordem.forEach(function (e) {
    var rr = recEnt[e] || 0, dd = despEnt[e] || 0;
    if (rr === 0 && dd === 0) return;
    var res = rr - dd;
    html += "<tr><td>" + e.replace("Negocios", "Neg&oacute;cios") + "</td><td align=\"right\">" + formataReais(rr) +
            "</td><td align=\"right\">" + formataReais(dd) + "</td><td align=\"right\" style=\"color:" +
            (res >= 0 ? "#2E7D32" : "#C62828") + "\"><b>" + formataReais(res) + "</b></td></tr>";
  });
  html += "</table>";

  var cats = Object.keys(despCat).map(function (k) { return [k, despCat[k]]; }).sort(function (a, b) { return b[1] - a[1]; });
  if (cats.length) {
    html += "<h3>&#128184; Maiores gastos do m&ecirc;s</h3><ul>";
    cats.slice(0, 5).forEach(function (c) { html += "<li>" + c[0] + " &mdash; " + formataReais(c[1]) + "</li>"; });
    html += "</ul>";
  }

  html += "<h3>&#9203; A vencer nos pr&oacute;ximos 7 dias</h3>";
  html += "<p>&#128184; A pagar: <b>" + formataReais(aPagar) + "</b> &nbsp;|&nbsp; &#128229; A receber: <b>" + formataReais(aReceber) + "</b></p>";
  if (itens.length) {
    html += "<ul>";
    itens.sort(function (a, b) { return a.dias - b.dias; });
    itens.forEach(function (it) {
      var q = it.dias === 0 ? "hoje" : "em " + it.dias + "d";
      html += "<li>" + it.desc + " (" + it.tipo + ") &mdash; " + it.valor + " &mdash; " + q + "</li>";
    });
    html += "</ul>";
  }

  html += "<p style=\"margin-top:20px\"><a href=\"" + LINK_DASH +
          "\" style=\"background:#1565C0;color:#fff;padding:11px 18px;border-radius:6px;text-decoration:none;font-weight:bold\">&#128202; Abrir o dashboard completo</a></p>";
  html += "<p style=\"color:#888;font-size:12px\">Resumo autom&aacute;tico &middot; planilha 2026 - FINANCEIRO LEO</p></div>";

  GmailApp.sendEmail(EMAIL_PADRAO, "Resumo Financeiro semanal - " + nomeMes, "", { htmlBody: html, name: "Financeiro Leo" });
}

// Rode UMA vez para agendar o resumo semanal (domingo 20h).
function criarGatilhoSemanal() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === "resumoSemanal") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("resumoSemanal").timeBased().onWeekDay(ScriptApp.WeekDay.SUNDAY).atHour(20).create();
}
