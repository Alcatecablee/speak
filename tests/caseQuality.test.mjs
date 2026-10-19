import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { polishCaseNote, evaluateQaReadiness, DEMO_CASE_NOTES } = require('../procedures/caseQuality.js');

test('Kingpos / MC2 demo scenario: rough input polishes into clean Salesforce-ready note', () => {
  const kingposDemo = DEMO_CASE_NOTES.find((c) => c.id === 'kingpos-mc2-demo');
  assert.ok(kingposDemo, 'kingpos-mc2-demo exists in DEMO_CASE_NOTES');

  const polished = polishCaseNote(kingposDemo.raw);
  assert.equal(polished, kingposDemo.preparedPolished);

  // Facts & voice preservation checks
  assert.match(polished, /^After restarting the machine, the client was unable to open Kingpos on MC2\./);
  assert.match(polished, /I dialed in to MC2 and restarted the SQL Agent service\./);
  assert.match(polished, /I tested it again and was able to open Kingpos\./);
  assert.match(polished, /Waiting for the cashier to confirm transaction processing\.$/);

  // No invented customer confirmation
  assert.doesNotMatch(polished, /customer confirmed/i);
  assert.doesNotMatch(polished, /issue is resolved/i);

  // No extraneous commentary or tutorial steps
  assert.doesNotMatch(polished, /Key Corrections Made/i);
  assert.doesNotMatch(polished, /Step \d/i);
  assert.doesNotMatch(polished, /Explanation/i);
});

test('Core benchmark: preserves facts and uncertainty without inventing confirmation', () => {
  const benchmarkInput = 'The client could not open the back office after I restarted the machine. I tested again and could open the back office.';
  const benchmarkExpected = 'After restarting the machine, the client was unable to open the Back Office. I tested it again and was able to open the Back Office.';
  assert.equal(polishCaseNote(benchmarkInput), benchmarkExpected);
});

test('Preserves suspected cause and pending test without premature resolution', () => {
  const input = 'suspect the network cable might be loose. tried a test transaction but still waiting for cashier to confirm if card machine is working';
  const out = polishCaseNote(input);
  assert.match(out, /^I suspect the network cable might be loose\./);
  assert.match(out, /I tried a test transaction, but I am still waiting for the cashier to confirm whether the card machine is working\.$/);
  assert.doesNotMatch(out, /resolved/i);
});

test('Backward compatibility: single-line spacing fixture is preserved exactly', () => {
  // Verifies the exact legacy fixture required by verify.mjs
  const input = 'the   printer  is down ,restart it.  then  test';
  assert.match(polishCaseNote(input), /The printer is down, restart it\. Then test/);
});

test('QA Readiness: evaluates all 9 scorecard criteria from Lynora session with individual weights', () => {
  const kingposDemo = DEMO_CASE_NOTES.find((c) => c.id === 'kingpos-mc2-demo');
  const polished = polishCaseNote(kingposDemo.raw);
  const report = evaluateQaReadiness({ noteText: polished });

  assert.equal(report.simulatedScore, null);
  assert.equal(report.overallStatus, 'Review Required');
  assert.equal(report.scoreDisplay, 'Review Required');
  assert.match(report.scoreLabel, /Customer confirmation pending/i);
  assert.match(report.disclaimer, /inspired by Lynora's case QA criteria/i);

  // Exactly 9 criteria as specified by Lynora
  assert.equal(report.checks.length, 9);

  const checksById = Object.fromEntries(report.checks.map((c) => [c.id, c]));

  // Verify weights total 100%
  const totalWeight = report.checks.reduce((sum, c) => sum + (c.weightValue || 0), 0);
  assert.equal(totalWeight, 100);

  // 1. Resolution notes (20%) - Unverified due to pending customer confirmation
  assert.ok(checksById.resolution_notes);
  assert.equal(checksById.resolution_notes.weight, '20%');
  assert.equal(checksById.resolution_notes.status, 'Unverified');
  assert.match(checksById.resolution_notes.evidenceSummary, /customer confirmation.+is pending/i);
  assert.match(checksById.resolution_notes.reviewGuidance, /Do NOT mark the case as resolved/i);

  // 2. Error description (10%) - Ready
  assert.ok(checksById.error_description);
  assert.equal(checksById.error_description.weight, '10%');
  assert.equal(checksById.error_description.status, 'Ready');

  // 3. Support origin (10%) - Not applicable (no 3rd-party outage involved, per Lynora guidance)
  assert.ok(checksById.support_origin);
  assert.equal(checksById.support_origin.weight, '10%');
  assert.equal(checksById.support_origin.status, 'Not applicable');

  // 4. Case comments (10%) - Ready
  assert.ok(checksById.case_comments);
  assert.equal(checksById.case_comments.weight, '10%');
  assert.equal(checksById.case_comments.status, 'Ready');

  // 5. Contact number (10%) - Unverified (inbound call logged, but no callback number recorded)
  assert.ok(checksById.contact_number);
  assert.equal(checksById.contact_number.weight, '10%');
  assert.equal(checksById.contact_number.status, 'Unverified');
  assert.match(checksById.contact_number.evidenceSummary, /no direct callback telephone number is recorded/i);

  // 6. System selection (10%) - Ready (Software / MC2)
  assert.ok(checksById.system_selection);
  assert.equal(checksById.system_selection.weight, '10%');
  assert.equal(checksById.system_selection.status, 'Ready');

  // 7. Error type (10%) - Ready
  assert.ok(checksById.error_type);
  assert.equal(checksById.error_type.weight, '10%');
  assert.equal(checksById.error_type.status, 'Ready');

  // 8. Product (10%) - Ready (Kingpos)
  assert.ok(checksById.product);
  assert.equal(checksById.product.weight, '10%');
  assert.equal(checksById.product.status, 'Ready');

  // 9. Priority (10%) - Ready (Medium/Standard)
  assert.ok(checksById.priority);
  assert.equal(checksById.priority.weight, '10%');
  assert.equal(checksById.priority.status, 'Ready');
});

test('Production Recipe Demo: rough note polishes cleanly and QA reflects committed callback pending', () => {
  const recipeDemo = DEMO_CASE_NOTES.find((c) => c.id === 'production-recipe-demo');
  assert.ok(recipeDemo, 'production-recipe-demo exists in DEMO_CASE_NOTES');

  const polished = polishCaseNote(recipeDemo.raw);
  assert.equal(polished, recipeDemo.preparedPolished);
  assert.match(polished, /cheesecake recipe/i);
  assert.match(polished, /MC1/);
  assert.match(recipeDemo.salesforceFields.Remote_Connection_ID__c, /20288 2622 2622/);
  assert.match(polished, /15 minutes/i);

  const report = evaluateQaReadiness({
    noteText: polished,
    salesforceFields: recipeDemo.salesforceFields,
  });

  assert.equal(report.overallStatus, 'Review Required');
  assert.equal(report.scoreDisplay, 'Review Required');
  assert.match(report.scoreLabel, /Callback & confirmation pending/i);
  assert.equal(report.checks.length, 9);

  const checksById = Object.fromEntries(report.checks.map((c) => [c.id, c]));
  assert.equal(checksById.resolution_notes.status, 'Unverified');
  assert.match(checksById.resolution_notes.evidenceSummary, /callback outcome and customer confirmation are pending/i);
  assert.equal(checksById.contact_number.status, 'Unverified');
  assert.match(checksById.contact_number.evidenceSummary, /no direct telephone callback number is recorded/i);
  assert.equal(checksById.product.status, 'Ready');
  assert.equal(checksById.error_type.status, 'Ready');
});
