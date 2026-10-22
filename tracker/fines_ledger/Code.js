// 3514 fines ledger behind the public dashboard (bound to the "3514 Fines" sheet).
// Officers tab: one personal key per R4 (made by setup(), never stored in code or the repo).
// Payments tab: append-only log; the latest row per fine_id wins, "undo" clears it.
// Accounts tab: R4 proposals to mark an account farm/main; the admin (sheet owner) approves or rejects them from the 3514 menu,
// which starts the GitHub Action that recalculates and republishes the dashboard.
// Deployed as a Web app: execute as the owner, access "Anyone" (keys gate writes, reads are public).

const DASHBOARD = 'https://rizkyekoputra.github.io/rok-3514-dashboard/';
const RECALC = 'https://api.github.com/repos/rizkyekoputra/rok-3514/actions/workflows/recalc.yml/dispatches';
// Keep in sync with role=R4 in ../accounts.csv; rerun setup() after adding names (existing keys are kept).
const R4 = ['Totos メtreme', 'Dobelメtreme', 'RockyメGirang', 'Depati Amir', 'ＡＧＡＭ', 'MʀメSENOPATI', 'JDメ', 'ツ 3D',
            'Saxaa メtreme', 'Nyyaaa', '么 QUEEN', 'xxYxx', 'メ S L A Y E R メ'];
// Officers who may also approve/reject farm/main changes on the dashboard (besides the admin in the sheet menu).
// Also settable per row: approver = yes in the Officers tab.
const APPROVERS = ['Totos メtreme', 'ＡＧＡＭ'];
const HEADERS = {
  Officers: ['name', 'key', 'status', 'link', 'approver'],
  Payments: ['time', 'fine_id', 'player', 'week', 'amount', 'by', 'action'],
  Accounts: ['time', 'account_id', 'player', 'type', 'by', 'status', 'decided', 'decided_by'],
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
    .addSeparator()
    .addItem('Approve selected account changes', 'approveSelected')
    .addItem('Reject selected account changes', 'rejectSelected')
    .addItem('Recalculate dashboard now', 'menuRecalc')
    .addItem('Set GitHub token', 'setToken')
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

const approveSelected = () => decideSelected('approved');
const rejectSelected = () => decideSelected('rejected');

// Approve/reject the proposed rows in the selection (Accounts tab), then recalculate if anything was approved.
function decideSelected(status) {
  const ui = SpreadsheetApp.getUi(), sh = book().getActiveSheet();
  if (sh.getName() !== 'Accounts') return ui.alert('Select the proposed rows in the Accounts tab first.');
  const done = [];
  sh.getActiveRangeList().getRanges().forEach(rg => {
    for (let r = Math.max(2, rg.getRow()); r <= rg.getLastRow(); r++) {
      const [, , player, type, , st] = sh.getRange(r, 1, 1, 7).getValues()[0];
      if (st !== 'proposed') continue;
      sh.getRange(r, 6, 1, 3).setValues([[status, new Date(), 'admin']]);
      done.push(`${player} → ${type}`);
    }
  });
  if (!done.length) return ui.alert('No proposed changes in the selection.');
  const recalc = status === 'approved' ? '\n\nRecalculation: ' + triggerRecalc() : '';
  ui.alert(`${status === 'approved' ? 'Approved' : 'Rejected'}:\n${done.join('\n')}${recalc}`);
}

function menuRecalc() { SpreadsheetApp.getUi().alert('Recalculation: ' + triggerRecalc()); }

// Starts the "Recalculate dashboard" GitHub Action (fine-grained token: rok-3514 only, Actions read/write).
function triggerRecalc() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) return 'not started, no GitHub token yet (3514 → Set GitHub token). The hourly run will pick it up.';
  const r = UrlFetchApp.fetch(RECALC, {method: 'post', contentType: 'application/json', muteHttpExceptions: true,
    headers: {Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json'}, payload: JSON.stringify({ref: 'main'})});
  return r.getResponseCode() === 204 ? 'started, the dashboard updates in about 2 minutes.'
    : `GitHub refused (${r.getResponseCode()}); the token may have expired (3514 → Set GitHub token).`;
}

// Token lives in Script Properties (owner-only), never in the sheet or the code.
function setToken() {
  const ui = SpreadsheetApp.getUi();
  const res = ui.prompt('GitHub token', 'Paste the fine-grained token (rok-3514 only, Actions: read and write).', ui.ButtonSet.OK_CANCEL);
  if (res.getSelectedButton() !== ui.Button.OK || !res.getResponseText().trim()) return;
  PropertiesService.getScriptProperties().setProperty('GITHUB_TOKEN', res.getResponseText().trim());
  ui.alert('Saved. Testing it: ' + triggerRecalc());
}

// Creates the tabs and a key + link for every R4 not listed yet; returns the names added.
function setup() {
  Object.keys(HEADERS).forEach(name => {
    const sh = tab(name) || book().insertSheet(name);
    if (sh.getLastRow() === 0) sh.appendRow(HEADERS[name]).setFrozenRows(1);
    else sh.getRange(1, 1, 1, HEADERS[name].length).setValues([HEADERS[name]]);  // adds columns introduced later
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

// {name, approver} for an active key, else null.
function officer(key) {
  if (!key) return null;
  const row = rows('Officers').find(r => r[1] === key && r[2] === 'active');
  return row ? {name: row[0], approver: row[4] === 'yes' || APPROVERS.includes(row[0])} : null;
}

// Approver on the dashboard: decide every open proposal for one account.
function decide(accountId, status, by) {
  const sh = tab('Accounts'), vals = sh.getDataRange().getValues();
  let n = 0;
  for (let r = 1; r < vals.length; r++) {
    if (vals[r][1] === accountId && vals[r][5] === 'proposed') {
      sh.getRange(r + 1, 6, 1, 3).setValues([[status, new Date(), by]]);
      n++;
    }
  }
  return n;
}

// account_id -> {type, by, decided} of the latest approved change, plus pending: the newest proposal after it.
function accountChanges() {
  const acc = {};
  rows('Accounts').forEach(([time, id, , type, by, status, decided]) => {
    const a = acc[id] || (acc[id] = {});
    if (status === 'approved') Object.assign(a, {type, by, decided: new Date(decided).toISOString()});
    if (status === 'proposed') a.pending = {type, by, time: new Date(time).toISOString()};
    else delete a.pending;
  });
  return acc;
}

// GET: {paid: {fine_id: {amount, by, time}}, accounts: accountChanges(), officer: name or null for ?key=}
function doGet(e) {
  const paid = {};
  rows('Payments').forEach(([time, fid, , , amount, by, action]) => {
    if (action === 'undo') delete paid[fid];
    else paid[fid] = {amount: Number(amount), by, time: new Date(time).toISOString()};
  });
  const o = officer(e.parameter.key);
  return out({paid, accounts: accountChanges(), officer: o && o.name, approver: !!(o && o.approver)});
}

// POST (text/plain JSON), either
//   {key, fine_id, player, week, amount, action: "paid" | "undo"}   fine payment
//   {key, account_id, player, action: "farm" | "main"}               account type proposal for the admin
//   {key, account_id, action: "approve" | "reject"}                  approvers only
function doPost(e) {
  let req;
  try { req = JSON.parse(e.postData.contents); } catch (err) { return out({ok: false, error: 'bad request'}); }
  const o = officer(req.key);
  if (!o) return out({ok: false, error: 'invalid key'});
  const by = o.name;
  if (req.action === 'approve' || req.action === 'reject') {
    if (!o.approver) return out({ok: false, error: 'not an approver'});
    if (!/^[0-9a-f]{10}$/.test(req.account_id)) return out({ok: false, error: 'bad request'});
    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    let n;
    try { n = decide(req.account_id, req.action === 'approve' ? 'approved' : 'rejected', by); } finally { lock.releaseLock(); }
    if (!n) return out({ok: false, error: 'nothing to decide'});
    let recalc = '';
    if (req.action === 'approve') { try { recalc = triggerRecalc(); } catch (err) { recalc = 'not started (' + err.message + ')'; } }
    return out({ok: true, by, recalc});
  }
  if (req.action === 'farm' || req.action === 'main') {
    if (!/^[0-9a-f]{10}$/.test(req.account_id)) return out({ok: false, error: 'bad request'});
    return locked(() => tab('Accounts').appendRow([new Date(), req.account_id, plain(req.player), req.action, by, 'proposed', '']), by);
  }
  const amount = Number(req.amount);
  if (!/^[0-9a-f]{10}$/.test(req.fine_id) || !/^\d{4}-\d{2}-\d{2}$/.test(req.week) ||
      !(amount >= 0 && amount <= 1e12)) return out({ok: false, error: 'bad request'});
  const action = req.action === 'undo' ? 'undo' : 'paid';
  return locked(() => tab('Payments').appendRow([new Date(), req.fine_id, plain(req.player), req.week,
                                                 action === 'undo' ? 0 : amount, by, action]), by);
}

function locked(write, by) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);  // two R4s tapping at once
  try { write(); } finally { lock.releaseLock(); }
  return out({ok: true, by});
}
