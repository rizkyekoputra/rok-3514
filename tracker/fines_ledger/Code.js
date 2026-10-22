// 3514 fines ledger behind the public dashboard (bound to the "3514 Fines" sheet).
// Officers tab: one personal key per R4 (made by setup(), never stored in code or the repo).
// Payments tab: append-only log; the latest row per fine_id wins, "undo" clears it.
// Deployed as a Web app: execute as the owner, access "Anyone" (keys gate writes, reads are public).

const DASHBOARD = 'https://rizkyekoputra.github.io/rok-3514-dashboard/';
// Keep in sync with role=R4 in ../accounts.csv; rerun setup() after adding names (existing keys are kept).
const R4 = ['Totos メtreme', 'Dobelメtreme', 'RockyメGirang', 'Depati Amir', 'ＡＧＡＭ', 'MʀメSENOPATI', 'JDメ', 'ツ 3D',
            'Saxaa メtreme', 'Nyyaaa', '么 QUEEN', 'xxYxx', 'メ S L A Y E R メ'];
const HEADERS = {
  Officers: ['name', 'key', 'status', 'link'],
  Payments: ['time', 'fine_id', 'player', 'week', 'amount', 'by', 'action'],
};

const book = () => SpreadsheetApp.getActiveSpreadsheet();
const tab = name => book().getSheetByName(name);
const out = obj => ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
// Tabs are created on first use, so the web app works even if setup() was never run by hand.
const rows = name => (tab(name) || (setup(), tab(name))).getDataRange().getValues().slice(1);
// Player names come from the game; stop "=..." etc. being read as a formula.
const plain = s => String(s == null ? '' : s).slice(0, 80).replace(/^([=+\-@])/, "'$1");

// Run once from the editor: creates the tabs and a key + link for every R4 not listed yet.
function setup() {
  Object.keys(HEADERS).forEach(name => {
    const sh = tab(name) || book().insertSheet(name);
    if (sh.getLastRow() === 0) sh.appendRow(HEADERS[name]).setFrozenRows(1);
  });
  const known = rows('Officers').map(r => r[0]);
  R4.filter(n => !known.includes(n)).forEach(n => {
    const key = Utilities.getUuid().replace(/-/g, '');
    tab('Officers').appendRow([n, key, 'active', DASHBOARD + '?key=' + key]);
  });
  const blank = book().getSheetByName('Sheet1');
  if (blank && book().getSheets().length > 2 && blank.getLastRow() === 0) book().deleteSheet(blank);
}

function officer(key) {
  if (!key) return null;
  const row = rows('Officers').find(r => r[1] === key && r[2] === 'active');
  return row ? row[0] : null;
}

// GET: {paid: {fine_id: {amount, by, time}}, officer: name or null for ?key=}
function doGet(e) {
  const paid = {};
  rows('Payments').forEach(([time, fid, , , amount, by, action]) => {
    if (action === 'undo') delete paid[fid];
    else paid[fid] = {amount: Number(amount), by, time: new Date(time).toISOString()};
  });
  return out({paid, officer: officer(e.parameter.key)});
}

// POST (text/plain JSON): {key, fine_id, player, week, amount, action: "paid" | "undo"}
function doPost(e) {
  let req;
  try { req = JSON.parse(e.postData.contents); } catch (err) { return out({ok: false, error: 'bad request'}); }
  const by = officer(req.key);
  if (!by) return out({ok: false, error: 'invalid key'});
  const amount = Number(req.amount);
  if (!/^[0-9a-f]{10}$/.test(req.fine_id) || !/^\d{4}-\d{2}-\d{2}$/.test(req.week) ||
      !(amount >= 0 && amount <= 1e12)) return out({ok: false, error: 'bad request'});
  const action = req.action === 'undo' ? 'undo' : 'paid';
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);  // two R4s tapping at once
  try {
    tab('Payments').appendRow([new Date(), req.fine_id, plain(req.player), req.week,
                               action === 'undo' ? 0 : amount, by, action]);
  } finally {
    lock.releaseLock();
  }
  return out({ok: true, by});
}
