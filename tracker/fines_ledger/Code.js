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

const newKey = () => Utilities.getUuid().replace(/-/g, '');

// Sheet menu, so keys can be managed without opening the script editor.
function onOpen() {
  SpreadsheetApp.getUi().createMenu('3514')
    .addItem('Create keys for missing R4s', 'menuSetup')
    .addItem('New key for selected R4', 'rotateSelected')
    .addToUi();
}

function menuSetup() {
  const added = setup();
  SpreadsheetApp.getUi().alert(added.length ? `Created keys for: ${added.join(', ')}` : 'Every R4 already has a key.');
}

// Replace the key (and link) on the selected Officers row; the old link stops working at once.
function rotateSelected() {
  const ui = SpreadsheetApp.getUi(), sh = book().getActiveSheet(), r = sh.getActiveRange().getRow();
  if (sh.getName() !== 'Officers' || r < 2 || !sh.getRange(r, 1).getValue())
    return ui.alert('Select an R4 row in the Officers tab first.');
  const name = sh.getRange(r, 1).getValue();
  if (ui.alert(`Give ${name} a new key? Their current link stops working.`, ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  const key = newKey();
  sh.getRange(r, 2, 1, 3).setValues([[key, 'active', DASHBOARD + '?key=' + key]]);
  ui.alert(`New link for ${name} is in column D. Send it to them privately.`);
}

// Creates the tabs and a key + link for every R4 not listed yet; returns the names added.
function setup() {
  Object.keys(HEADERS).forEach(name => {
    const sh = tab(name) || book().insertSheet(name);
    if (sh.getLastRow() === 0) sh.appendRow(HEADERS[name]).setFrozenRows(1);
  });
  const known = rows('Officers').map(r => r[0]);
  const added = R4.filter(n => !known.includes(n));
  added.forEach(n => {
    const key = newKey();
    tab('Officers').appendRow([n, key, 'active', DASHBOARD + '?key=' + key]);
  });
  console.log(`Officers listed: ${known.length}; keys created for ${added.length}: ${added.join(', ')}`);
  const blank = book().getSheetByName('Sheet1');
  if (blank && book().getSheets().length > 2 && blank.getLastRow() === 0) book().deleteSheet(blank);
  return added;
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
