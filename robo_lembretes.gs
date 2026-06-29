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
