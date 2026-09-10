/**
 * Kode Web App untuk menyambungkan Jurnal Transaksi (di app Sinyal Saham) ke
 * Google Sheets, dengan data terpisah per USERNAME (sistem login sederhana --
 * cuma nama, BUKAN password beneran, cukup buat memisahkan data biar tidak
 * tercampur antar orang yang pakai app yang sama).
 *
 * Tiap kali ada posisi ditutup, "Rapor Performa" ikut otomatis ter-generate
 * ulang, TERPISAH per username (tab "Rapor - <username>"), lengkap dengan
 * grafik & saran per transaksi (saran berbasis aturan sederhana, BUKAN
 * prediksi AI/ML).
 *
 * SETUP HEADER SHEET (baris 1, kolom A-I), urutan bebas asal nama-nama ini
 * semua ada:
 *   Username | ID | Ticker | TanggalBeli | HargaBeli | JumlahLot | TanggalJual | HargaJual | Catatan
 *
 * Kalau upgrade dari versi sebelumnya (belum ada kolom Username): klik kanan
 * huruf kolom A -> "Insert 1 column left" -> ketik "Username" di sel A1.
 *
 * Cara pakai lengkap ada di README.md bagian "Sinkron Jurnal ke Spreadsheet".
 */

var JOURNAL_SHEET_NAME = "Jurnal";
var REPORT_SHEET_PREFIX = "Rapor - ";

function getJournalSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(JOURNAL_SHEET_NAME) || ss.getSheets()[0];
}

function getHeaderMap(sheet) {
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var map = {};
  headers.forEach(function (h, i) { map[h] = i; });
  return map;
}

function normalizeUsername(raw) {
  var u = (raw || "").toString().trim().toLowerCase();
  return u || "(tanpa nama)";
}

function doPost(e) {
  var sheet = getJournalSheet();
  var col = getHeaderMap(sheet);
  var data = JSON.parse(e.postData.contents);
  var username = normalizeUsername(data.username);

  var values = sheet.getDataRange().getValues();
  var rowIndex = -1;
  for (var i = 1; i < values.length; i++) {
    var rowUsername = normalizeUsername(values[i][col["Username"]]);
    if (String(values[i][col["ID"]]) === String(data.id) && rowUsername === username) {
      rowIndex = i + 1;
      break;
    }
  }

  var rowData = [];
  rowData[col["Username"]] = username;
  rowData[col["ID"]] = data.id;
  rowData[col["Ticker"]] = data.ticker;
  rowData[col["TanggalBeli"]] = data.buy_date;
  rowData[col["HargaBeli"]] = data.buy_price;
  rowData[col["JumlahLot"]] = data.lots;
  rowData[col["TanggalJual"]] = data.sell_date || "";
  rowData[col["HargaJual"]] = data.sell_price || "";
  rowData[col["Catatan"]] = data.note || "";

  if (rowIndex > 0) {
    sheet.getRange(rowIndex, 1, 1, rowData.length).setValues([rowData]);
  } else {
    sheet.appendRow(rowData);
  }

  try {
    generateAllReports();
  } catch (err) {
    // Jangan sampai jurnal gagal tersimpan gara-gara rapor error
  }

  return ContentService
    .createTextOutput(JSON.stringify({ status: "ok" }))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  if (e.parameter && e.parameter.type === "chat") {
    return handleChatRequest(e.parameter.q || "");
  }

  var sheet = getJournalSheet();
  var values = sheet.getDataRange().getValues();
  var headers = values[0];
  var filterUsername = (e.parameter && e.parameter.username) ? normalizeUsername(e.parameter.username) : null;

  var entries = values.slice(1)
    .filter(function (row) { return row.join("") !== ""; })
    .map(function (row) {
      var obj = {};
      headers.forEach(function (h, i) { obj[h] = row[i]; });
      return obj;
    })
    .filter(function (obj) {
      if (!filterUsername) return true;
      return normalizeUsername(obj["Username"]) === filterUsername;
    });

  return ContentService
    .createTextOutput(JSON.stringify(entries))
    .setMimeType(ContentService.MimeType.JSON);
}

// ==== Fitur "Tanya AI" -- proxy aman ke Gemini API ====
// API key TIDAK ditaruh di kode ini (biar aman kalau kode dibagikan), tapi
// disimpan di "Script Properties": Project Settings (ikon gerigi) > Script
// Properties > Add script property > Name: GEMINI_API_KEY, Value: (key kamu).
// Opsional: tambah juga "GEMINI_MODEL" kalau mau pakai model lain dari default.
function handleChatRequest(question) {
  if (!question) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: "Pertanyaan kosong." }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty("GEMINI_API_KEY");
  var model = props.getProperty("GEMINI_MODEL") || "gemini-3.6-flash";

  if (!apiKey) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: "GEMINI_API_KEY belum diset di Script Properties (lihat komentar di atas fungsi ini)." }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var systemPrompt = "Kamu adalah asisten tanya-jawab seputar saham Indonesia (IDX) yang ramah, " +
    "ringkas, dan informatif, jawab dalam Bahasa Indonesia. Boleh bantu jelaskan istilah trading, " +
    "analisis umum, atau pandangan atas suatu saham/sektor, TAPI selalu ingatkan ini bukan nasihat " +
    "investasi resmi dan keputusan akhir + risikonya ada di tangan investor sendiri.";

  var url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + apiKey;
  var payload = {
    contents: [{ parts: [{ text: question }] }],
    systemInstruction: { parts: [{ text: systemPrompt }] },
  };

  try {
    var response = UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });
    var result = JSON.parse(response.getContentText());

    if (result.error) {
      return ContentService
        .createTextOutput(JSON.stringify({ error: "Gemini API error: " + result.error.message }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    var answer = (result.candidates && result.candidates[0] && result.candidates[0].content)
      ? result.candidates[0].content.parts.map(function (p) { return p.text; }).join("")
      : "Maaf, tidak ada jawaban dari AI.";

    return ContentService
      .createTextOutput(JSON.stringify({ answer: answer }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: "Gagal menghubungi Gemini: " + err }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Menu manual di Google Sheets kalau mau refresh rapor semua orang sekaligus
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('📊 Sinyal Saham')
    .addItem('Generate / Refresh Semua Rapor Performa', 'generateAllReports')
    .addToUi();
}

// Saran sederhana berbasis aturan (bukan AI/ML) -- transparan & bisa dicek logikanya
function adviceFor(pctReturn, holdingDays) {
  if (pctReturn < -5) {
    return holdingDays <= 3
      ? "Rugi cukup besar dalam waktu singkat. Evaluasi apakah entry terlalu terburu-buru tanpa konfirmasi tren."
      : "Rugi besar & ditahan " + holdingDays + " hari. Disiplin stop loss bisa membatasi kerugian lebih awal.";
  }
  if (pctReturn < 0) {
    return "Rugi tipis, ini wajar terjadi. Evaluasi apakah level stop loss sudah sesuai volatilitas saham ini.";
  }
  if (pctReturn < 3) {
    return holdingDays > 14
      ? "Profit tipis meski ditahan " + holdingDays + " hari. Pertimbangkan apakah modal ini lebih produktif di peluang lain."
      : "Profit tipis, sudah cukup baik. Evaluasi apakah target price sebelumnya realistis.";
  }
  if (pctReturn < 10) {
    return "Profit sehat. Pertahankan disiplin exit seperti ini.";
  }
  return holdingDays <= 3
    ? "Profit besar dalam waktu cepat, bagus! Pertimbangkan take profit bertahap ke depannya untuk kunci sebagian gain lebih awal."
    : "Profit besar. Pertimbangkan trailing stop supaya tidak melepas posisi terlalu cepat saat tren masih kuat.";
}

function generateAllReports() {
  var sheet = getJournalSheet();
  var col = getHeaderMap(sheet);
  var values = sheet.getDataRange().getValues();

  var usernames = {};
  for (var i = 1; i < values.length; i++) {
    var row = values[i];
    if (!row[col["Ticker"]]) continue;
    usernames[normalizeUsername(row[col["Username"]])] = true;
  }

  Object.keys(usernames).forEach(function (uname) {
    generateReportFor(uname);
  });
}

function generateReportFor(username) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var journalSheet = getJournalSheet();
  var col = getHeaderMap(journalSheet);
  var values = journalSheet.getDataRange().getValues();

  var closedTrades = [];
  for (var i = 1; i < values.length; i++) {
    var row = values[i];
    if (!row[col["Ticker"]]) continue;
    if (String(row[col["Ticker"]]).toUpperCase() === "TEST") continue; // lewati data uji coba
    if (normalizeUsername(row[col["Username"]]) !== username) continue;
    var sellPrice = row[col["HargaJual"]];
    if (!sellPrice) continue; // posisi masih terbuka, dilewati dari rapor

    var buyPrice = Number(row[col["HargaBeli"]]);
    var lots = Number(row[col["JumlahLot"]]);
    var pnlRp = (Number(sellPrice) - buyPrice) * lots * 100;
    var pnlPct = ((Number(sellPrice) - buyPrice) / buyPrice) * 100;
    var buyDate = new Date(row[col["TanggalBeli"]]);
    var sellDate = new Date(row[col["TanggalJual"]]);
    var holdingDays = Math.max(0, Math.round((sellDate - buyDate) / (1000 * 60 * 60 * 24)));

    closedTrades.push({
      ticker: row[col["Ticker"]], sellDate: sellDate,
      pnlRp: pnlRp, pnlPct: pnlPct, holdingDays: holdingDays,
    });
  }

  closedTrades.sort(function (a, b) { return a.sellDate - b.sellDate; });

  var reportSheetName = REPORT_SHEET_PREFIX + username;
  var reportSheet = ss.getSheetByName(reportSheetName);
  if (!reportSheet) reportSheet = ss.insertSheet(reportSheetName);
  reportSheet.clear();
  var oldCharts = reportSheet.getCharts();
  for (var c = 0; c < oldCharts.length; c++) reportSheet.removeChart(oldCharts[c]);

  reportSheet.getRange("A1").setValue("RAPOR PERFORMA -- " + username.toUpperCase()).setFontWeight("bold").setFontSize(14);
  reportSheet.getRange("A2").setValue("Update terakhir: " + new Date().toLocaleString("id-ID"));
  reportSheet.getRange("A2").setFontColor("#888888").setFontStyle("italic");

  if (closedTrades.length === 0) {
    reportSheet.getRange("A4").setValue("Belum ada transaksi yang ditutup untuk user ini.");
    return;
  }

  var wins = closedTrades.filter(function (t) { return t.pnlRp > 0; });
  var losses = closedTrades.filter(function (t) { return t.pnlRp <= 0; });
  var totalPnl = closedTrades.reduce(function (s, t) { return s + t.pnlRp; }, 0);
  var avgPct = closedTrades.reduce(function (s, t) { return s + t.pnlPct; }, 0) / closedTrades.length;
  var best = closedTrades.reduce(function (a, b) { return b.pnlPct > a.pnlPct ? b : a; });
  var worst = closedTrades.reduce(function (a, b) { return b.pnlPct < a.pnlPct ? b : a; });
  var winRate = (wins.length / closedTrades.length) * 100;

  var summary = [
    ["Total Transaksi Ditutup", closedTrades.length],
    ["Win Rate", winRate.toFixed(1) + "%"],
    ["Total P&L (Rp)", totalPnl],
    ["Rata-rata P&L per Transaksi", avgPct.toFixed(1) + "%"],
    ["Trade Terbaik", best.ticker + " (" + best.pnlPct.toFixed(1) + "%)"],
    ["Trade Terburuk", worst.ticker + " (" + worst.pnlPct.toFixed(1) + "%)"],
  ];
  reportSheet.getRange(4, 1, summary.length, 2).setValues(summary);
  reportSheet.getRange(4, 1, summary.length, 1).setFontWeight("bold");
  reportSheet.getRange(6, 2, 1, 1).setNumberFormat('"Rp"#,##0');

  reportSheet.getRange("D4").setValue("Status");
  reportSheet.getRange("E4").setValue("Jumlah");
  reportSheet.getRange("D5").setValue("Menang");
  reportSheet.getRange("E5").setValue(wins.length);
  reportSheet.getRange("D6").setValue("Kalah");
  reportSheet.getRange("E6").setValue(losses.length);

  var startRow = 13;
  var tableHeaders = ["Ticker", "Tanggal Jual", "P&L (Rp)", "P&L (%)", "Lama Pegang (hari)", "P&L Kumulatif (Rp)", "Saran"];
  reportSheet.getRange(startRow, 1, 1, tableHeaders.length).setValues([tableHeaders]).setFontWeight("bold");

  var cumulative = 0;
  var tableRows = closedTrades.map(function (t) {
    cumulative += t.pnlRp;
    return [
      t.ticker, t.sellDate, t.pnlRp, t.pnlPct.toFixed(1) + "%", t.holdingDays, cumulative,
      adviceFor(t.pnlPct, t.holdingDays),
    ];
  });
  reportSheet.getRange(startRow + 1, 1, tableRows.length, tableHeaders.length).setValues(tableRows);
  reportSheet.getRange(startRow + 1, 2, tableRows.length, 1).setNumberFormat("dd-mmm-yyyy");
  reportSheet.getRange(startRow + 1, 3, tableRows.length, 1).setNumberFormat('"Rp"#,##0');
  reportSheet.getRange(startRow + 1, 6, tableRows.length, 1).setNumberFormat('"Rp"#,##0');
  reportSheet.autoResizeColumns(1, 6);
  reportSheet.setColumnWidth(7, 380);

  var n = tableRows.length;

  var pieChart = reportSheet.newChart()
    .asPieChart()
    .addRange(reportSheet.getRange("D4:E6"))
    .setPosition(4, 9, 0, 0)
    .setOption("title", "Menang vs Kalah")
    .setOption("width", 350).setOption("height", 250)
    .build();
  reportSheet.insertChart(pieChart);

  var barChart = reportSheet.newChart()
    .asColumnChart()
    .addRange(reportSheet.getRange(startRow, 1, n + 1, 1))
    .addRange(reportSheet.getRange(startRow, 3, n + 1, 1))
    .setPosition(20, 9, 0, 0)
    .setOption("title", "Untung/Rugi per Transaksi (Rp)")
    .setOption("width", 480).setOption("height", 280)
    .build();
  reportSheet.insertChart(barChart);

  var lineChart = reportSheet.newChart()
    .asLineChart()
    .addRange(reportSheet.getRange(startRow, 2, n + 1, 1))
    .addRange(reportSheet.getRange(startRow, 6, n + 1, 1))
    .setPosition(38, 9, 0, 0)
    .setOption("title", "P&L Kumulatif dari Waktu ke Waktu")
    .setOption("width", 480).setOption("height", 280)
    .build();
  reportSheet.insertChart(lineChart);
}
