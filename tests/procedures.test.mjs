// Unit tests for the Procedure Hub awareness layer (pure logic, no browser).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const relevance = require('../procedures/relevance.js');
const demo = require('../procedures/demoProcedures.js');
const { createDemoProcedureService, createLocalProcedureService } = require('../procedures/procedureService.js');
const { createReminderTracker } = require('../procedures/reminderTracker.js');

const memoryStorage = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) }; };
const titles = async (svc, text) => (await svc.findRelevantProcedures(text)).map((r) => r.procedure.title);

test('1. relevant phrases detect the correct procedure', async () => {
  const svc = createDemoProcedureService();
  assert.deepEqual(await titles(svc, 'Client said she cannot cash up because there are open tables.'), ['Open Tables Before Cash-Up']);
  assert.deepEqual(await titles(svc, "Client requested till roll slips and I advised them that we don't supply them outside Limpopo."), ['Till Roll Slip Supply']);
  assert.deepEqual(await titles(svc, 'The kitchen printer is offline and orders are not coming through.'), ['Kitchen Printer Offline']);
  assert.deepEqual(await titles(svc, 'Adumo PED offline at the client, card machine not connecting.'), ['Adumo PED Troubleshooting']);
  assert.deepEqual(await titles(svc, 'client said she cannot cash-up because of tables open'), ['Open Tables Before Cash-Up']);
});

test('2. a single weak keyword does not trigger an alert', async () => {
  const svc = createDemoProcedureService();
  for (const text of [
    'I was working on another case and saw a till roll in the store.',
    'cash-up', 'Adumo', 'the printer', 'open tables', 'Limpopo', 'kitchen printer', 'terminal offline',
    'I supply stock to Limpopo', 'receipt printer offline',
  ]) assert.deepEqual(await titles(svc, text), [], `should not trigger: "${text}"`);
});

test('3. multiple matching concepts increase relevance', () => {
  const p = demo.find((x) => x.id === 'demo-open-tables-cash-up');
  const one = relevance.scoreProcedure(p, 'cash-up');
  const two = relevance.scoreProcedure(p, 'cash-up with open tables');
  const three = relevance.scoreProcedure(p, 'cannot cash-up with open tables');
  assert.ok(one.score < two.score && two.score < three.score, `${one.score} < ${two.score} < ${three.score}`);
  assert.equal(one.matchedConcepts.length, 1);
  assert.equal(three.matchedConcepts.length, 3);
});

test('3b. a phrase is never double-counted ("till roll slips" is one concept)', () => {
  const p = demo.find((x) => x.id === 'demo-till-roll-supply');
  assert.equal(relevance.scoreProcedure(p, 'till roll slips').score, 3);
});

test('3c. required concepts gate eligibility', () => {
  const p = demo.find((x) => x.id === 'demo-till-roll-supply');
  const r = relevance.scoreProcedure(p, 'we do not supply to Limpopo');
  assert.equal(r.eligible, false);
});

test('3d. results are ranked by score', async () => {
  const svc = createDemoProcedureService();
  const res = await svc.findRelevantProcedures('adumo ped offline and cannot cash up with open tables');
  assert.equal(res.length, 2);
  assert.ok(res[0].score >= res[1].score);
});

test('4. the same procedure does not repeatedly alert during the same note', async () => {
  const svc = createDemoProcedureService();
  const tracker = createReminderTracker({ storage: memoryStorage() });
  const phrases = ['cash-up', 'cash-up because there were open tables', 'cash-up because there were open tables after closing the tables the cash-up worked'];
  let alerts = 0;
  for (const t of phrases) alerts += tracker.consider(await svc.findRelevantProcedures(t)).length;
  assert.equal(alerts, 1);
});

test('4b. a new note (reset) can surface the procedure again', async () => {
  const svc = createDemoProcedureService();
  const tracker = createReminderTracker({ storage: memoryStorage() });
  const text = 'cannot cash up because of open tables';
  assert.equal(tracker.consider(await svc.findRelevantProcedures(text)).length, 1);
  tracker.resetNote();
  assert.equal(tracker.consider(await svc.findRelevantProcedures(text)).length, 1);
});

test('5. dismissing suppresses the procedure for the session (and survives a reload of the tracker)', async () => {
  const svc = createDemoProcedureService();
  const storage = memoryStorage();
  const text = 'cannot cash up because of open tables';
  const t1 = createReminderTracker({ storage });
  const [first] = t1.consider(await svc.findRelevantProcedures(text));
  t1.dismiss(first.procedure.id);
  t1.resetNote();
  assert.equal(t1.consider(await svc.findRelevantProcedures(text)).length, 0);
  assert.equal(t1.detected().length, 1, 'still available for explicit reopen');
  const t2 = createReminderTracker({ storage }); // same browser session
  assert.equal(t2.consider(await svc.findRelevantProcedures(text)).length, 0);
  assert.equal(createReminderTracker({ storage: memoryStorage() }).consider(await svc.findRelevantProcedures(text)).length, 1, 'new session');
});

test('7. matching never mutates the transcript / suggestions are separate data', async () => {
  const svc = createDemoProcedureService();
  const text = 'client cannot cash up because there are open tables';
  const copy = String(text);
  const res = await svc.findRelevantProcedures(text);
  assert.equal(text, copy);
  assert.ok(res.length > 0);
});

test('8. procedure data is isolated behind the procedure service', async () => {
  const read = (f) => fs.readFileSync(path.join(root, f), 'utf8');
  const demoTitles = demo.map((p) => p.title);
  for (const f of ['index.html', 'app.js', 'procedures/procedureReminder.js', 'procedures/reminderTracker.js', 'procedures/relevance.js', 'procedures/procedureService.js']) {
    const src = read(f);
    for (const t of demoTitles) assert.ok(!src.includes(t), `${f} must not contain demo procedure "${t}"`);
    assert.ok(!src.includes('demoProcedures') || f === 'index.html' || f === 'procedures/procedureService.js', `${f} must not reference demo data directly`);
  }
  // UI layer only talks to the service contract.
  const ui = read('procedures/procedureReminder.js');
  assert.match(ui, /service\.findRelevantProcedures/);
  assert.match(ui, /service\.getProcedure/);
  // Public shape exposes no matcher internals and a different data source can be plugged in.
  const [r] = await createDemoProcedureService().findRelevantProcedures('cannot cash up because of open tables');
  for (const k of ['id', 'title', 'status', 'version', 'effectiveDate', 'instruction', 'source', 'lastUpdated']) assert.ok(k in r.procedure, k);
  assert.ok(!('concepts' in r.procedure));
  const custom = createLocalProcedureService({ procedures: [{ id: 'x', title: 'Custom', status: 'Active', version: 1, effectiveDate: '2026-01-01', lastUpdated: '2026-01-01T00:00:00Z', instruction: 'i', source: 's', concepts: [{ name: 'a', terms: ['alpha'], weight: 5 }] }] });
  assert.deepEqual(await titles(custom, 'alpha'), ['Custom']);
});

test('only Active procedures are surfaced', async () => {
  const svc = createLocalProcedureService({ procedures: demo.map((p) => ({ ...p, status: 'Retired' })) });
  assert.deepEqual(await titles(svc, 'cannot cash up because of open tables'), []);
});

test('demo data is clearly labelled and has the required fields', () => {
  assert.equal(demo.length, 4);
  for (const p of demo) {
    assert.equal(p.isDemo, true);
    assert.match(p.source, /demo/i);
    assert.equal(p.status, 'Active');
  }
  assert.deepEqual(demo.map((p) => p.version), [1, 1, 2, 3]);
});
