// 3514 fines ledger behind the public dashboard (bound to the "3514 Fines" sheet).
// Officers tab: one personal key per R4 (made by setup(), never stored in code or the repo).
// Payments tab: append-only log; the latest row per fine_id wins, "undo" clears it.
// Accounts tab: R4 proposals to mark an account farm/main; the admin (sheet owner) approves or rejects them from the 3514 menu,
// which starts the GitHub Action that recalculates and republishes the dashboard.
// Claims tab: players' "I've paid" submissions with proof files (screenshots/recordings, kept in a private Drive folder);
// R4s approve or reject them on the dashboard. Approving appends a Payments row, so it counts like a payment an R4 marked.
// Proof files are deleted CLAIM.keepDays after the decision (daily trigger made by setup()).
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
  Claims: ['time', 'claim_id', 'fine_id', 'player', 'week', 'fine', 'sent', 'gold_value', 'note', 'expect', 'files', 'bytes',
           'status', 'token', 'decided', 'decided_by', 'reason', 'cleaned'],
};
// Limits for player claims (keep maxFiles/maxBytes/types in sync with CLAIM_* in ../dashboard_template.html).
// status: uploading -> pending (all files in) -> approved | rejected; unfinished uploads become abandoned after a day.
const CLAIM = {maxFiles: 20, maxBytes: 30 * 1024 * 1024, perFine: 5, open: 100, burst: 20, keepDays: 30,
               types: /^(image\/(jpeg|png|webp|gif|heic|heif)|video\/(mp4|quicktime|webm|3gpp))$/};
const C = Object.fromEntries(HEADERS.Claims.map((h, i) => [h, i]));  // Claims column index by header

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
  if (!ScriptApp.getProjectTriggers().some(t => t.getHandlerFunction() === 'cleanupClaims'))
    ScriptApp.newTrigger('cleanupClaims').timeBased().everyDays(1).atHour(3).create();
  claimsFolder();
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

// Approver on the dashboard: decide every open proposal for the given account(s).
function decide(accountIds, status, by) {
  const ids = new Set([].concat(accountIds)), sh = tab('Accounts'), vals = sh.getDataRange().getValues();
  let n = 0;
  for (let r = 1; r < vals.length; r++) {
    if (ids.has(vals[r][1]) && vals[r][5] === 'proposed') {
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
  return out({paid, accounts: accountChanges(), officer: o && o.name, approver: !!(o && o.approver), officers: officerList(),
              claims: publicClaims(), claimList: o ? officerClaims() : undefined});
}

// SHA-256 of each active key (never the key): published with the dashboard so an R4 link works at once,
// without waiting for this web app. Writes are still checked against the real key here.
const sha256 = s => Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, s, Utilities.Charset.UTF_8)
  .map(b => ((b + 256) % 256).toString(16).padStart(2, '0')).join('');
function officerList() {
  return rows('Officers').filter(r => r[1] && r[2] === 'active')
    .map(r => ({h: sha256(String(r[1])), n: r[0], a: r[4] === 'yes' || APPROVERS.includes(r[0])}));
}

// POST (text/plain JSON), either
//   {key, fine_id, player, week, amount, action: "paid" | "undo"}   fine payment
//   {key, account_id, player, action: "farm" | "main"}               account type change (proposal, or
//   {key, accounts: [{account_id, player}], action: "farm" | "main"}  applied at once for approvers)
//   {key, account_id, action: "approve" | "reject"}                  approvers only
//   {action: "claim", fine_id, player, week, fine, sent, gold_value, note, files: [{type, size}]}   player, no key
//   {action: "claim_file", claim_id, token, name, type, data (base64)}  one proof file; then {action: "claim_done", ...}
//   {key, action: "claim_view", claim_id, file_id}                     R4: one proof file as base64
//   {key, action: "claim_approve", claim_id, amount} | {key, action: "claim_reject", claim_id, reason}
function doPost(e) {
  let req;
  try { req = JSON.parse(e.postData.contents); } catch (err) { return out({ok: false, error: 'bad request'}); }
  // players (no key): send a payment claim and its proof files
  if (req.action === 'claim') return out(newClaim(req));
  if (req.action === 'claim_file') return out(claimFile(req));
  if (req.action === 'claim_done') return out(claimDone(req));
  const o = officer(req.key);
  if (!o) return out({ok: false, error: 'invalid key'});
  const by = o.name;
  if (req.action === 'claim_view') return out(claimView(req));
  if (req.action === 'claim_approve' || req.action === 'claim_reject') return out(decideClaim(req, by));
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
    const list = Array.isArray(req.accounts) ? req.accounts : [{account_id: req.account_id, player: req.player}];
    if (!list.length || list.length > 500 || list.some(a => !a || !/^[0-9a-f]{10}$/.test(a.account_id)))
      return out({ok: false, error: 'bad request'});
    const now = new Date(), status = o.approver ? 'approved' : 'proposed';
    const add = list.map(a => [now, a.account_id, plain(a.player), req.action, by, status, o.approver ? now : '', o.approver ? by : '']);
    const lock = LockService.getScriptLock();
    lock.waitLock(20000);
    try {
      if (o.approver) decide(list.map(a => a.account_id), 'rejected', by);  // approvers' changes supersede open proposals
      const sh = tab('Accounts');
      sh.getRange(sh.getLastRow() + 1, 1, add.length, add[0].length).setValues(add);
    } finally { lock.releaseLock(); }
    if (!o.approver) return out({ok: true, by, count: add.length});
    let recalc = '';
    try { recalc = triggerRecalc(); } catch (err) { recalc = 'not started (' + err.message + ')'; }
    return out({ok: true, by, count: add.length, approved: true, recalc});
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

// ---------- payment claims ----------

// Proof files use the Drive API (advanced service, appsscript.json) with the drive.file scope: the script only reaches
// files it created itself. (DriveApp would need access to the whole Drive.)
function claimsFolder() {
  const props = PropertiesService.getScriptProperties(), id = props.getProperty('CLAIMS_FOLDER');
  if (id) { try { if (!Drive.Files.get(id, {fields: 'trashed'}).trashed) return id; } catch (err) { /* deleted: make a new one */ } }
  const made = Drive.Files.create({name: '3514 payment claims (proof files)', mimeType: 'application/vnd.google-apps.folder'}, null, {fields: 'id'}).id;
  props.setProperty('CLAIMS_FOLDER', made);
  return made;
}
const trashFile = id => Drive.Files.update({trashed: true}, id);
const fileBytes = id => UrlFetchApp.fetch(`https://www.googleapis.com/drive/v3/files/${encodeURIComponent(id)}?alt=media`,
  {headers: {Authorization: 'Bearer ' + ScriptApp.getOAuthToken()}}).getBlob().getBytes();

// [{r: sheet row (1-based), v: values}] of the Claims tab
function claimRows() { return rows('Claims').map((v, i) => ({r: i + 2, v})); }
const findClaim = id => claimRows().find(c => c.v[C.claim_id] === id);
const setCells = (c, cols) => Object.entries(cols).forEach(([h, val]) => tab('Claims').getRange(c.r, C[h] + 1).setValue(val));
const fileList = c => { try { return JSON.parse(c.v[C.files] || '[]'); } catch (err) { return []; } };
const iso = d => d ? new Date(d).toISOString() : '';

function newClaim(req) {
  const files = Array.isArray(req.files) ? req.files : [], bytes = files.reduce((a, f) => a + Number(f && f.size || 0), 0);
  const gold = Number(req.gold_value);
  if (!/^[0-9a-f]{10}$/.test(req.fine_id) || !/^\d{4}-\d{2}-\d{2}$/.test(req.week) || !(gold >= 0 && gold <= 1e13))
    return {ok: false, error: 'bad request'};
  if (!files.length || files.length > CLAIM.maxFiles) return {ok: false, error: `attach 1 to ${CLAIM.maxFiles} files`};
  if (files.some(f => !CLAIM.types.test(String(f.type)) || !(Number(f.size) > 0)))
    return {ok: false, error: 'only screenshots (JPG, PNG, WebP, HEIC) and recordings (MP4, MOV, WebM)'};
  if (bytes > CLAIM.maxBytes) return {ok: false, error: `files are over ${CLAIM.maxBytes / 1048576}MB in total`};
  const cache = CacheService.getScriptCache(), burst = Number(cache.get('claims') || 0);
  if (burst >= CLAIM.burst) return {ok: false, error: 'many claims just now, try again in a few minutes'};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const all = claimRows().map(c => c.v), mine = all.filter(v => v[C.fine_id] === req.fine_id && v[C.status] !== 'abandoned');
    if (mine.some(v => v[C.status] === 'pending')) return {ok: false, error: 'proof for this fine is already waiting for an R4'};
    if (mine.length >= CLAIM.perFine) return {ok: false, error: 'too many claims for this fine, please contact an R4'};
    if (all.filter(v => v[C.status] === 'pending' || v[C.status] === 'uploading').length >= CLAIM.open)
      return {ok: false, error: 'too many claims are waiting, try again later'};
    const id = newKey().slice(0, 12), token = newKey();
    const row = HEADERS.Claims.map(() => '');
    Object.assign(row, {[C.time]: new Date(), [C.claim_id]: id, [C.fine_id]: req.fine_id, [C.player]: plain(req.player),
      [C.week]: req.week, [C.fine]: plain(req.fine), [C.sent]: plain(req.sent), [C.gold_value]: gold,
      [C.note]: String(req.note || '').slice(0, 300).replace(/^([=+\-@])/, "'$1"),
      [C.expect]: JSON.stringify({n: files.length, bytes}), [C.files]: '[]', [C.bytes]: 0, [C.status]: 'uploading', [C.token]: token});
    tab('Claims').appendRow(row);
    cache.put('claims', String(burst + 1), 600);
    return {ok: true, claim_id: id, token};
  } finally { lock.releaseLock(); }
}

// one uploaded proof file (sent one by one so each request stays small)
function claimFile(req) {
  const c = findClaim(req.claim_id);
  if (!c || !req.token || c.v[C.token] !== req.token || c.v[C.status] !== 'uploading') return {ok: false, error: 'claim not open for upload'};
  if (!CLAIM.types.test(String(req.type))) return {ok: false, error: 'file type not allowed'};
  const expect = JSON.parse(c.v[C.expect]), list = fileList(c);
  let bytes;
  try { bytes = Utilities.base64Decode(String(req.data || '')); } catch (err) { return {ok: false, error: 'bad file'}; }
  const used = Number(c.v[C.bytes]) + bytes.length;
  if (!bytes.length || list.length >= expect.n || used > Math.min(expect.bytes, CLAIM.maxBytes)) return {ok: false, error: 'file over the limit'};
  const name = `${c.v[C.claim_id]}_${list.length + 1}_` + String(req.name || 'proof').replace(/[^\w.\-]+/g, '_').slice(-60);
  const fileId = Drive.Files.create({name, parents: [claimsFolder()], mimeType: req.type},
                                    Utilities.newBlob(bytes, req.type, name), {fields: 'id'}).id;
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const now = findClaim(req.claim_id), nowList = fileList(now);
    nowList.push({id: fileId, n: String(req.name || name).slice(0, 80), t: req.type, s: bytes.length});
    setCells(now, {files: JSON.stringify(nowList), bytes: Number(now.v[C.bytes]) + bytes.length});
    return {ok: true, count: nowList.length};
  } finally { lock.releaseLock(); }
}

function claimDone(req) {
  const c = findClaim(req.claim_id);
  if (!c || !req.token || c.v[C.token] !== req.token || c.v[C.status] !== 'uploading') return {ok: false, error: 'claim not open'};
  if (!fileList(c).length) return {ok: false, error: 'no files arrived'};
  setCells(c, {status: 'pending', token: ''});
  return {ok: true};
}

// public: fine_id -> {s: status, t: time, why: reason if rejected} of the latest claim per fine
function publicClaims() {
  const res = {};
  claimRows().forEach(({v}) => {
    if (v[C.status] === 'uploading' || v[C.status] === 'abandoned') return;
    res[v[C.fine_id]] = {s: v[C.status], t: iso(v[C.time]), why: v[C.status] === 'rejected' ? v[C.reason] : undefined};
  });
  return res;
}

// R4s: claims waiting for a decision, plus the ones decided in the last CLAIM.keepDays days
function officerClaims() {
  const since = Date.now() - CLAIM.keepDays * 864e5;
  return claimRows().map(c => c.v).filter(v => v[C.status] === 'pending' ||
      ((v[C.status] === 'approved' || v[C.status] === 'rejected') && new Date(v[C.decided]).getTime() > since))
    .map(v => ({id: v[C.claim_id], fine_id: v[C.fine_id], player: v[C.player], week: v[C.week], fine: v[C.fine],
      sent: v[C.sent], gold: Number(v[C.gold_value]), note: v[C.note], files: (() => { try { return JSON.parse(v[C.files]); } catch (e) { return []; } })(),
      status: v[C.status], time: iso(v[C.time]), decided: iso(v[C.decided]), by: v[C.decided_by], reason: v[C.reason],
      cleaned: !!v[C.cleaned]}));
}

function claimView(req) {
  const c = findClaim(req.claim_id), f = c && fileList(c).find(x => x.id === req.file_id);
  if (!f || c.v[C.cleaned]) return {ok: false, error: 'file not found (deleted after 30 days?)'};
  return {ok: true, type: f.t, name: f.n, data: Utilities.base64Encode(fileBytes(f.id))};
}

function decideClaim(req, by) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const c = findClaim(req.claim_id);
    if (!c || c.v[C.status] !== 'pending') return {ok: false, error: 'claim is not waiting for a decision'};
    if (req.action === 'claim_reject') {
      const reason = String(req.reason || '').trim().slice(0, 200).replace(/^([=+\-@])/, "'$1");
      if (!reason) return {ok: false, error: 'give a reason'};
      setCells(c, {status: 'rejected', decided: new Date(), decided_by: by, reason});
      return {ok: true, by};
    }
    const amount = Number(req.amount);
    if (!(amount > 0 && amount <= 1e12)) return {ok: false, error: 'bad amount'};
    // the latest Payments row per fine is its total paid, so the dashboard sends previous payments + this claim
    tab('Payments').appendRow([new Date(), c.v[C.fine_id], c.v[C.player], c.v[C.week], amount, by, 'paid']);
    setCells(c, {status: 'approved', decided: new Date(), decided_by: by});
    return {ok: true, by};
  } finally { lock.releaseLock(); }
}

// Daily: delete proof files CLAIM.keepDays after the decision, and files of uploads never finished (after a day).
function cleanupClaims() {
  const now = Date.now();
  claimRows().forEach(c => {
    const v = c.v, st = v[C.status];
    const done = (st === 'approved' || st === 'rejected') && !v[C.cleaned] && now - new Date(v[C.decided]).getTime() > CLAIM.keepDays * 864e5;
    const stale = st === 'uploading' && now - new Date(v[C.time]).getTime() > 864e5;
    if (!done && !stale) return;
    fileList(c).forEach(f => { try { trashFile(f.id); } catch (err) { /* already gone */ } });
    setCells(c, stale ? {status: 'abandoned', token: '', cleaned: new Date()} : {cleaned: new Date()});
  });
}
