// End-to-end verification: drives the real UI in a real browser (Edge/Chrome via playwright-core)
// with a scriptable fake SpeechRecognition, so mic/permission flows are deterministic.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from '../dev-server.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const shots = process.env.SCREENSHOTS_DIR || path.join(root, 'tests', '.output_screenshots');
fs.mkdirSync(shots, { recursive: true });

const server = createServer();
await new Promise((r) => server.listen(0, r));
const url = `http://localhost:${server.address().port}/`;

let passed = 0, failed = 0;
function check(name, cond, extra = '') {
  if (cond) { passed++; console.log('  ✔', name); } else { failed++; console.log('  ✘', name, extra); }
}

const FAKE_SR = () => {
  class FakeSR {
    constructor() { FakeSR.instances.push(this); this.started = false; }
    start() {
      if (window.__srStartThrows) throw new Error('InvalidStateError');
      this.started = true;
      setTimeout(() => this.onstart && this.onstart(), 10);
    }
    stop() { this.started = false; setTimeout(() => this.onend && this.onend(), 10); }
    abort() { this.started = false; }
  }
  FakeSR.instances = [];
  window.SpeechRecognition = FakeSR;
  window.webkitSpeechRecognition = FakeSR;
  const last = () => FakeSR.instances[FakeSR.instances.length - 1];
  window.__instances = () => FakeSR.instances.length;
  window.__emit = (list) => {
    const results = list.map((x) => { const a = [{ transcript: x.t }]; a.isFinal = !!x.final; return a; });
    last().onresult({ resultIndex: 0, results });
  };
  window.__err = (code) => { const i = last(); i.onerror && i.onerror({ error: code }); i.onend && i.onend(); };
  window.__silenceEnd = () => { const i = last(); i.onend && i.onend(); };
};

const launchOpts = { headless: true };
let browser;
for (const channel of ['msedge', 'chrome', undefined]) {
  try { browser = await chromium.launch({ ...launchOpts, channel }); console.log('Browser:', channel || 'bundled chromium'); break; } catch { /* try next */ }
}
if (!browser) { console.error('No Chromium-based browser found (install Edge/Chrome).'); process.exit(2); }

async function newPage(opts = {}, { fake = true, init } = {}) {
  const ctx = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'], ...opts });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  if (fake) await page.addInitScript(FAKE_SR);
  if (init) await page.addInitScript(init);
  await page.goto(url);
  return { ctx, page, errors };
}

try {
  // ------------------------------------------------------------------ desktop, fake recogniser
  console.log('\nDictation + UI (desktop)');
  {
    const { ctx, page, errors } = await newPage({ viewport: { width: 1280, height: 800 } });
    const mic = page.locator('#mic'), notes = page.locator('#notes');

    check('page title', (await page.title()) === 'Speak Your Notes');
    check('mic idle label', (await page.locator('#mic-label').innerText()) === 'Start Dictation');

    await mic.click();
    await page.waitForSelector('#mic[data-state="recording"]');
    check('recording: label = Stop Dictation', (await page.locator('#mic-label').innerText()) === 'Stop Dictation');
    check('recording: pulsing animation class + red', await mic.evaluate((b) => b.classList.contains('mic-recording') && b.classList.contains('bg-red-600')));
    check('recording: aria-pressed true', (await mic.getAttribute('aria-pressed')) === 'true');
    check('recording: status says Listening', (await page.locator('#status').innerText()).includes('Listening'));
    await page.screenshot({ path: path.join(shots, 'desktop-recording.png') });

    await page.evaluate(() => window.__emit([{ t: 'printer is offline', final: false }]));
    check('interim text previewed', (await page.locator('#interim').innerText()).includes('printer is offline'));
    check('interim not yet committed', (await notes.inputValue()) === '');

    await page.evaluate(() => window.__emit([{ t: ' customer reports the printer is offline', final: true }]));
    check('final text inserted + capitalised', (await notes.inputValue()) === 'Customer reports the printer is offline');
    await page.evaluate(() => window.__emit([{ t: 'full stop new line restarted the base', final: true }]));
    check('voice commands (full stop / new line)', (await notes.inputValue()) === 'Customer reports the printer is offline.\nRestarted the base', JSON.stringify(await notes.inputValue()));

    // browser ends the session after silence -> must silently resume
    const before = await page.evaluate(() => window.__instances());
    await page.evaluate(() => window.__silenceEnd());
    await page.waitForFunction((n) => window.__instances() > n, before);
    await page.waitForSelector('#mic[data-state="recording"]');
    check('auto-resumes after silence timeout', true);

    // android-style duplicate final result is dropped
    await page.evaluate(() => { window.__emit([{ t: 'dup phrase', final: true }]); window.__emit([{ t: 'dup phrase', final: true }]); });
    check('duplicate final phrase de-duplicated', ((await notes.inputValue()).match(/dup phrase/g) || []).length === 1);

    await mic.click();
    await page.waitForSelector('#mic[data-state="idle"]');
    check('stop: back to idle', (await page.locator('#mic-label').innerText()) === 'Start Dictation');
    check('stop: pulse removed', await mic.evaluate((b) => !b.classList.contains('mic-recording')));
    const inst = await page.evaluate(() => window.__instances());
    await page.waitForTimeout(400);
    check('stop: does not restart', (await page.evaluate(() => window.__instances())) === inst);

    // ---- copy
    await notes.fill('Hello support note');
    await page.click('#copy');
    await page.waitForFunction(() => document.getElementById('copy-label').textContent === 'Copied!', null, { timeout: 2000 }).catch(() => {});
    check('copy button shows Copied!', (await page.locator('#copy-label').innerText()) === 'Copied!');
    check('clipboard has the note text', (await page.evaluate(() => navigator.clipboard.readText())) === 'Hello support note');
    await page.waitForFunction(() => document.getElementById('copy-label').textContent === 'Copy', null, { timeout: 4000 });
    check('copy label resets', true);

    // ---- clear + undo
    await page.click('#clear');
    check('clear empties notes', (await notes.inputValue()) === '');
    check('counter reset', (await page.locator('#counter').innerText()).startsWith('0 words'));
    await page.click('#toast-action');
    check('undo restores notes', (await notes.inputValue()) === 'Hello support note');

    // ---- tidy
    await notes.fill('  the   printer  is down ,restart it.  then  test ');
    await page.click('#tidy');
    check('tidy fixes spacing/capitalisation', (await notes.inputValue()) === 'The printer is down, restart it. Then test\n', JSON.stringify(await notes.inputValue()));

    // ---- persistence + theme
    await notes.fill('persist me');
    await page.waitForTimeout(400);
    await page.reload();
    check('notes persist across reload', (await page.locator('#notes').inputValue()) === 'persist me');
    const wasDark = await page.evaluate(() => document.documentElement.classList.contains('dark'));
    await page.click('#theme-toggle');
    check('theme toggles', (await page.evaluate(() => document.documentElement.classList.contains('dark'))) !== wasDark);
    await page.waitForTimeout(400);
    check('toast hidden when idle', await page.locator('#toast').isHidden());
    await page.screenshot({ path: path.join(shots, 'desktop-theme-toggled.png') });
    await page.reload();
    check('theme persists', (await page.evaluate(() => document.documentElement.classList.contains('dark'))) !== wasDark);

    check('no uncaught JS errors', errors.length === 0, errors.join('; '));
    await ctx.close();
  }

  // ------------------------------------------------------------------ mic permission / error handling
  console.log('\nMicrophone permission & error handling');
  for (const [code, text] of [
    ['not-allowed', 'blocked'], ['service-not-allowed', 'blocked'],
    ['audio-capture', 'No microphone'], ['network', 'unreachable'],
  ]) {
    const { ctx, page } = await newPage();
    await page.click('#mic');
    await page.waitForSelector('#mic[data-state="recording"]');
    await page.evaluate((c) => window.__err(c), code);
    await page.waitForSelector('#mic[data-state="idle"]');
    const banner = page.locator('#banner');
    check(`'${code}' → banner shown & mic reset`, (await banner.isVisible()) && (await banner.innerText()).includes(text), await banner.innerText());
    const n = await page.evaluate(() => window.__instances());
    await page.waitForTimeout(500);
    check(`'${code}' → no restart loop`, (await page.evaluate(() => window.__instances())) === n);
    if (code === 'not-allowed') await page.screenshot({ path: path.join(shots, 'mic-blocked-banner.png') });
    // user can retry and the banner clears
    await page.click('#mic');
    await page.waitForSelector('#mic[data-state="recording"]');
    check(`'${code}' → retry clears banner`, await banner.isHidden());
    await ctx.close();
  }
  {
    const { ctx, page } = await newPage();
    await page.click('#mic'); await page.waitForSelector('#mic[data-state="recording"]');
    await page.evaluate(() => window.__err('no-speech'));
    await page.waitForSelector('#mic[data-state="recording"]');
    check("'no-speech' → keeps listening", await page.locator('#banner').isHidden());
    await ctx.close();
  }
  {
    const { ctx, page } = await newPage({}, { init: () => { window.__srStartThrows = true; } });
    await page.click('#mic');
    check('start() throwing → friendly banner, mic idle', (await page.locator('#banner').isVisible()) && (await page.locator('#mic').getAttribute('data-state')) === 'idle');
    await ctx.close();
  }
  {
    const { ctx, page } = await newPage({}, {
      init: () => {
        const orig = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = (d) => d.name === 'microphone'
          ? Promise.resolve({ state: 'denied', onchange: null }) : orig(d);
      },
    });
    await page.waitForSelector('#banner:not([hidden])');
    check('Permissions API "denied" → banner on load', (await page.locator('#banner').innerText()).includes('blocked'));
    check('status shows Microphone blocked', (await page.locator('#status').innerText()).includes('Microphone blocked'));
    await ctx.close();
  }
  {
    const { ctx, page } = await newPage({}, { fake: false, init: () => { delete window.SpeechRecognition; delete window.webkitSpeechRecognition; } });
    check('unsupported browser → banner, typing still works', await page.locator('#banner').isVisible());
    await page.fill('#notes', 'typed notes support');
    check('typing works without speech support', (await page.inputValue('#notes')) === 'typed notes support');
    await ctx.close();
  }

  // ------------------------------------------------------------------ keyboard shortcuts
  console.log('\nKeyboard shortcuts');
  {
    const { ctx, page } = await newPage({ viewport: { width: 1280, height: 800 } });
    await page.keyboard.press('Control+Shift+Space');
    await page.waitForSelector('#mic[data-state="recording"]');
    check('Ctrl+Shift+Space starts dictation', true);
    await page.keyboard.press('Control+Shift+Space');
    await page.waitForSelector('#mic[data-state="idle"]');
    check('Ctrl+Shift+Space stops dictation', true);
    await page.fill('#notes', 'shortcut copy test');
    await page.keyboard.press('Control+Shift+C');
    await page.waitForFunction(() => document.getElementById('copy-label').textContent === 'Copied!', null, { timeout: 2000 }).catch(() => {});
    check('Ctrl+Shift+C copies', (await page.locator('#copy-label').innerText()) === 'Copied!' && (await page.evaluate(() => navigator.clipboard.readText())) === 'shortcut copy test');
    await ctx.close();
  }

  // ------------------------------------------------------------------ Procedure Hub awareness layer
  console.log('\nProcedure Hub reminder layer');
  {
    const { ctx, page, errors } = await newPage({ viewport: { width: 1280, height: 800 } });
    const notes = page.locator('#notes');
    const cards = page.locator('#ph-cards [data-procedure-id]');
    const say = (t) => page.evaluate((x) => window.__emit([{ t: x, final: true }]), t);
    const chunks = [];
    const speak = async (t) => { chunks.push(t); await say(t); };

    check('tagline shown', (await page.locator('header').innerText()).includes('Speak it. Structure it. Copy it.'));
    await page.click('#mic'); await page.waitForSelector('#mic[data-state="recording"]');
    const instances = await page.evaluate(() => window.__instances());

    await speak('I saw a till roll in the store.');
    await page.waitForTimeout(800);
    check('single weak keyword → no reminder', (await cards.count()) === 0 && (await page.locator('#ph-cards').isHidden()));

    await speak('Client said she cannot cash up because there are open tables.');
    await page.waitForSelector('#ph-cards [data-procedure-id="demo-open-tables-cash-up"]');
    const cardText = await cards.first().innerText();
    check('reminder appears for relevant phrase', cardText.toLowerCase().includes('procedure hub') && cardText.toLowerCase().includes('open tables before cash-up') && cardText.toLowerCase().includes('view procedure'), cardText);
    check('only the matching procedure is shown', (await cards.count()) === 1);
    check('dictation not interrupted by reminder', (await page.locator('#mic').getAttribute('data-state')) === 'recording' && (await page.evaluate(() => window.__instances())) === instances);
    check('reminder does not steal focus / no modal', (await page.evaluate(() => !document.getElementById('ph-cards').contains(document.activeElement))) && (await page.locator('#ph-modal').isHidden()));
    await page.screenshot({ path: path.join(shots, 'procedure-reminder-desktop.png') });

    // keep talking about the same thing → no repeat alerts
    await speak('Checked the tables and found three open tables.');
    await speak('After closing the tables the cash up worked.');
    await page.waitForTimeout(900);
    check('same procedure does not alert again in the same note', (await cards.count()) === 1 && (await page.locator('#ph-cards').getAttribute('data-surfaced-count')) === '1');

    // View procedure – panel content, dictation continues
    await cards.first().locator('[data-action="view"]').click();
    await page.waitForSelector('#ph-modal:not([hidden])');
    const field = (id) => page.locator(id).innerText();
    check('panel: title', (await field('#ph-m-title')) === 'Open Tables Before Cash-Up');
    check('panel: status + version', (await field('#ph-m-status')) === 'Active' && (await field('#ph-m-version')) === 'Version 1');
    check('panel: effective date', (await field('#ph-m-effective')) === '3 October 2026', await field('#ph-m-effective'));
    check('panel: instruction', (await field('#ph-m-instruction')) === 'Ensure all open tables are closed before completing the cash-up.');
    check('panel: source + last updated', (await field('#ph-m-source')).includes('demo') && (await field('#ph-m-updated')).includes('3 October 2026'));
    check('panel: labelled as demo data', await page.locator('#ph-m-demo').isVisible());
    await page.screenshot({ path: path.join(shots, 'procedure-panel-desktop.png') });
    check('viewing a procedure does not stop dictation', (await page.locator('#mic').getAttribute('data-state')) === 'recording');
    await speak('Closed them and she completed the cash up.');
    check('speech still inserted while panel is open', (await notes.inputValue()).includes('Closed them and she completed'));
    await page.keyboard.press('Escape');
    await page.waitForSelector('#ph-modal', { state: 'hidden' });
    check('Escape closes panel; dictation continues on same session', (await page.locator('#mic').getAttribute('data-state')) === 'recording' && (await page.evaluate(() => window.__instances())) === instances);

    check('suggestions never modify the resolution text', (await notes.inputValue()) === chunks.join(' '), JSON.stringify(await notes.inputValue()));

    // Dismiss → suppressed for the session, can be reopened explicitly
    await cards.first().locator('[data-action="dismiss"]').click();
    check('dismiss removes the card', (await cards.count()) === 0);
    check('dismissed procedure available from tray', (await page.locator('#ph-tray').isVisible()) && (await page.locator('#ph-tray').innerText()).includes('1'));
    await speak('Open tables again, cannot cash up.');
    await page.waitForTimeout(900);
    check('dismissed procedure is suppressed', (await cards.count()) === 0);
    check('dismiss did not change the note', (await notes.inputValue()) === chunks.join(' '));
    await page.click('#ph-tray');
    check('explicit reopen shows it again', (await cards.count()) === 1);

    // Clear starts a new note; dismissal still holds for the session
    await page.click('#clear');
    check('clear removes reminders', (await cards.count()) === 0 && (await page.locator('#ph-tray').isHidden()));
    await say('Cannot cash up because of open tables.');
    await page.waitForTimeout(900);
    check('dismissal persists for the session after clear', (await cards.count()) === 0);
    check('copy still returns exactly the note', await (async () => {
      await page.click('#copy');
      await page.waitForTimeout(200);
      return (await page.evaluate(() => navigator.clipboard.readText())) === (await notes.inputValue());
    })());
    check('no uncaught JS errors', errors.length === 0, errors.join('; '));
    await ctx.close();
  }
  {
    // Typed text is covered too; a different procedure; the multi-procedure + new-session path.
    const { ctx, page } = await newPage({ viewport: { width: 1280, height: 800 } });
    await page.fill('#notes', 'Kitchen printer offline since morning, orders not printing');
    await page.waitForSelector('#ph-cards [data-procedure-id="demo-kitchen-printer-offline"]');
    check('typed text also surfaces a procedure (Kitchen Printer Offline)', true);
    const before = await page.inputValue('#notes');
    await page.locator('#ph-cards [data-action="view"]').click();
    check('panel shows version 2', (await page.locator('#ph-m-version').innerText()) === 'Version 2');
    await page.click('#ph-m-close');
    check('note untouched after viewing', (await page.inputValue('#notes')) === before);
    await ctx.close();
  }
  {
    // Typed "till roll supply" triggers IMPORTANT: TILL ROLL SUPPLY RESTRICTION & verifies panel content
    const { ctx, page } = await newPage({ viewport: { width: 1280, height: 800 } });
    await page.fill('#notes', 'till roll supply');
    await page.waitForSelector('#ph-cards [data-procedure-id="demo-till-roll-supply"]');
    const card = page.locator('#ph-cards [data-procedure-id="demo-till-roll-supply"]');
    check('typed "till roll supply" surfaces procedure card', await card.isVisible());
    const cardText = await card.innerText();
    check('reminder card displays exact title', cardText.includes('IMPORTANT: TILL ROLL SUPPLY RESTRICTION'));
    check('reminder card displays PROCEDURE HUB label', cardText.toLowerCase().includes('procedure hub · possible relevant procedure'));
    await card.locator('[data-action="view"]').click();
    await page.waitForSelector('#ph-modal:not([hidden])');
    check('panel displays exact title', (await page.locator('#ph-m-title').innerText()) === 'IMPORTANT: TILL ROLL SUPPLY RESTRICTION');
    check('panel displays exact procedure instruction', (await page.locator('#ph-m-instruction').innerText()) === 'Effective immediately, till roll slips may only be supplied to clients in Polokwane. Do not supply outside Polokwane.');
    await page.click('#ph-m-close');
    await page.waitForSelector('#ph-modal', { state: 'hidden' });
    check('panel closes cleanly after view procedure', await page.locator('#ph-modal').isHidden());
    await ctx.close();
  }
  {
    // Isolation: swap the service and the UI follows it – no demo data is baked into the UI.
    const { ctx, page } = await newPage({}, {
      init: () => {
        window.SYN_PROCEDURE_SERVICE = {
          async findRelevantProcedures(t) {
            return /banana/i.test(t) ? [{ score: 9, procedure: { id: 'fake-1', title: 'Peel Bananas First', status: 'Active', version: 7, effectiveDate: '2026-01-02', instruction: 'Peel before eating.', source: 'Test service', lastUpdated: '2026-01-02T10:00:00Z' } }] : [];
          },
          async getProcedure() { return null; },
        };
      },
    });
    await page.fill('#notes', 'client asked about cannot cash up because open tables');
    await page.waitForTimeout(800);
    check('swapped service: demo procedures are gone', (await page.locator('#ph-cards [data-procedure-id]').count()) === 0);
    await page.fill('#notes', 'a banana was involved');
    await page.waitForSelector('#ph-cards [data-procedure-id="fake-1"]');
    check('swapped service: UI renders whatever the service returns', (await page.locator('#ph-cards').innerText()).includes('Peel Bananas First'));
    await page.locator('#ph-cards [data-action="view"]').click();
    check('swapped service: panel renders its data', (await page.locator('#ph-m-version').innerText()) === 'Version 7' && (await page.locator('#ph-m-demo').isHidden()));
    await ctx.close();
  }
  {
    // Mobile: reminder + panel fit on a phone screen and don't cover the mic button.
    const { ctx, page } = await newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
    await page.tap('#mic'); await page.waitForSelector('#mic[data-state="recording"]');
    await page.evaluate(() => window.__emit([{ t: 'Client said she cannot cash up because there are open tables.', final: true }]));
    await page.waitForSelector('#ph-cards [data-procedure-id]');
    await page.screenshot({ path: path.join(shots, 'procedure-reminder-mobile.png') });
    const m = await page.evaluate(() => ({
      overflowX: document.documentElement.scrollWidth > window.innerWidth,
      card: document.querySelector('#ph-cards [data-procedure-id]').getBoundingClientRect().toJSON(),
      mic: document.getElementById('mic').getBoundingClientRect().toJSON(),
      notesH: document.getElementById('notes').getBoundingClientRect().height,
    }));
    check('mobile: no horizontal overflow with reminder', !m.overflowX);
    check('mobile: reminder does not overlap the mic button', m.card.bottom <= m.mic.top);
    check('mobile: notes box still usable (>200px)', m.notesH > 200, String(m.notesH));
    await page.tap('#ph-cards [data-action="view"]');
    await page.waitForSelector('#ph-modal:not([hidden])');
    await page.screenshot({ path: path.join(shots, 'procedure-panel-mobile.png') });
    check('mobile: dictation still recording with panel open', (await page.locator('#mic').getAttribute('data-state')) === 'recording');
    await ctx.close();
  }

  // ------------------------------------------------------------------ mobile
  console.log('\nMobile layout (iPhone-sized, touch)');
  {
    const { ctx, page } = await newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
    await page.tap('#mic'); await page.waitForSelector('#mic[data-state="recording"]');
    await page.evaluate(() => window.__emit([{ t: 'supplier delivered short', final: true }]));
    await page.screenshot({ path: path.join(shots, 'mobile-recording.png') });
    const m = await page.evaluate(() => ({
      overflowX: document.documentElement.scrollWidth > window.innerWidth,
      micBox: document.getElementById('mic').getBoundingClientRect().toJSON(),
      vh: window.innerHeight,
      notesH: document.getElementById('notes').getBoundingClientRect().height,
      btnMin: Math.min(...['mic', 'copy', 'tidy', 'clear'].map((i) => document.getElementById(i).getBoundingClientRect().height)),
    }));
    check('no horizontal overflow', !m.overflowX);
    check('mic button fully on-screen', m.micBox.bottom <= m.vh && m.micBox.top >= 0);
    check('touch targets ≥ 44px', m.btnMin >= 44, String(m.btnMin));
    check('text area is large (>250px)', m.notesH > 250, String(m.notesH));
    await ctx.close();
  }

  // ------------------------------------------------------------------ PWA bits
  console.log('\nPWA');
  {
    const { ctx, page } = await newPage({ viewport: { width: 390, height: 844 } });
    const manifest = await (await page.request.get(url + 'manifest.webmanifest')).json();
    check('manifest valid (standalone, icons)', manifest.display === 'standalone' && manifest.icons.length >= 3);
    for (const i of manifest.icons) {
      const r = await page.request.get(url + i.src);
      check(`icon reachable: ${i.src}`, r.ok());
    }
    await page.evaluate(() => navigator.serviceWorker.ready);
    check('service worker active', await page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration())?.active));
    check('offline cache (v2) includes procedure layer scripts', await page.evaluate(async () =>
      (await caches.keys()).includes('speak-your-notes-v2') &&
      !!(await caches.match('./procedures/procedureReminder.js')) && !!(await caches.match('./procedures/demoProcedures.js'))));
    await ctx.close();
  }

  // ------------------------------------------------------------------ Session Provenance & Tab Switch Persistence (LIVE SESSION TEST 8472)
  console.log('\nSession Provenance & Tab Switch Persistence (LIVE SESSION TEST 8472)');
  {
    const marker = 'LIVE SESSION TEST 8472';
    const { ctx, page, errors } = await newPage({
      viewport: { width: 1280, height: 800 }
    }, {
      init: () => {
        window.__enableEngineInTest = true;
        let mockState = 'idle';
        // Intercept window.fetch to simulate local engine responding with live session data
        const origFetch = window.fetch;
        window.fetch = async (input, init) => {
          const urlStr = typeof input === 'string' ? input : (input && input.url ? input.url : '');
          if (urlStr.includes('/health')) {
            return new Response(JSON.stringify({ status: 'ok', loopback_only: true }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' }
            });
          }
          if (urlStr.includes('/capture/start')) {
            mockState = 'recording';
            return new Response(JSON.stringify({
              status: 'recording',
              session_id: 'live_session_8472',
              stage_label: 'Recording call'
            }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' }
            });
          }
          if (urlStr.includes('/capture/stop')) {
            mockState = 'processing';
            return new Response(JSON.stringify({
              status: 'processing',
              session_id: 'live_session_8472',
              stage_label: 'Finalizing audio capture'
            }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' }
            });
          }
          if (urlStr.includes('/status')) {
            if (mockState === 'processing') {
              mockState = 'ready';
              return new Response(JSON.stringify({
                status: 'ready',
                stage: 'ready',
                stage_label: 'Ready',
                session_id: 'live_session_8472',
                session_type: 'live',
                has_transcript: true
              }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
              });
            }
            return new Response(JSON.stringify({
              status: mockState,
              stage: mockState,
              stage_label: mockState === 'recording' ? 'Recording call' : 'Idle',
              session_id: 'live_session_8472',
              session_type: 'live',
              has_transcript: mockState === 'ready'
            }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' }
            });
          }
          if (urlStr.includes('/transcript')) {
            return new Response(JSON.stringify({
              status: 'success',
              session_id: 'live_session_8472',
              session_type: 'live',
              data: {
                session_id: 'live_session_8472',
                session_type: 'live',
                total_turns: 2,
                merged_turns: [
                  { speaker: 'CONSULTANT', text: 'Hello, ' + 'LIVE SESSION TEST 8472' + ' started.' },
                  { speaker: 'CLIENT', text: 'Confirmed, received marker ' + 'LIVE SESSION TEST 8472' + '.' }
                ]
              },
              formatted_text: '[CONSULTANT]: Hello, LIVE SESSION TEST 8472 started.\n[CLIENT]: Confirmed, received marker LIVE SESSION TEST 8472.'
            }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' }
            });
          }
          if (urlStr.includes('/analysis')) {
            return new Response(JSON.stringify({
              status: 'success',
              session_id: 'live_session_8472',
              session_type: 'live',
              data: {
                session_id: 'live_session_8472',
                session_type: 'live',
                executive_summary: 'Live analysis for LIVE SESSION TEST 8472',
                issue_category: 'Hardware / Printer',
                root_cause: 'Network offline during LIVE SESSION TEST 8472',
                action_items_consultant: ['Follow up LIVE SESSION TEST 8472'],
                action_items_client: ['Check power on LIVE SESSION TEST 8472'],
                resolution_status: 'RESOLVED',
                confidence: { level: 'HIGH', score: 0.95 }
              }
            }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' }
            });
          }
          if (urlStr.includes('/review')) {
            return new Response(JSON.stringify({
              status: 'success',
              session_id: 'live_session_8472',
              session_type: 'live',
              markdown: '# Case Review for LIVE SESSION TEST 8472\n\nLive verified call analysis.',
              salesforce_draft: {
                action: 'CREATE_CASE',
                fields: {
                  Subject: 'Live Call - LIVE SESSION TEST 8472',
                  Description: 'Salesforce draft payload for LIVE SESSION TEST 8472',
                  Status: 'Pending Review',
                  Remote_Connection_ID__c: '8472-TEST'
                }
              }
            }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' }
            });
          }
          return origFetch(input, init);
        };
      }
    });

    // Wait for engine poll to see 'Engine Connected'
    await page.waitForFunction(() => document.getElementById('engine-text')?.textContent === 'Engine Connected');
    check('engine status connected', (await page.locator('#engine-text').innerText()) === 'Engine Connected');

    // Trigger capture start + stop
    await page.click('#mic'); // start capture
    await page.waitForSelector('#mic[data-state="recording"]');
    check('recording started with active live session', true);

    await page.click('#mic'); // stop capture
    await page.waitForSelector('#btn-view-transcript:not([hidden])', { timeout: 5000 });
    check('processing completed to ready state', true);

    // 1. Dialogue Tab Verification
    await page.click('#tab-transcript');
    await page.waitForTimeout(200);
    const transcriptText = await page.locator('#transcript-container').innerText();
    check('dialogue tab contains LIVE SESSION TEST 8472 marker', transcriptText.includes(marker), transcriptText);
    check('dialogue tab does not contain demo data', !transcriptText.includes('cheesecake') && !transcriptText.includes('butternut'));

    // 2. AI Summary Tab Verification
    await page.click('#tab-review');
    await page.waitForTimeout(200);
    const reviewText = await page.locator('#review-container').innerText();
    check('AI summary tab contains LIVE SESSION TEST 8472 marker', reviewText.includes(marker), reviewText);
    check('AI summary tab does not contain demo data', !reviewText.includes('cheesecake') && !reviewText.includes('butternut'));

    // 3. Salesforce Draft Tab Verification
    await page.click('#tab-salesforce');
    await page.waitForTimeout(200);
    const getSfContent = () => page.locator('#salesforce-container').evaluate((el) => {
      const inputs = Array.from(el.querySelectorAll('input, textarea')).map((i) => i.value).join(' ');
      return el.innerText + ' ' + inputs;
    });
    const sfText = await getSfContent();
    check('salesforce draft tab contains LIVE SESSION TEST 8472 marker', sfText.includes(marker), sfText);
    check('salesforce draft tab does not contain demo data', !sfText.includes('cheesecake') && !sfText.includes('butternut'));

    // 4. Repeated Tab Switching Isolation Check
    for (let i = 0; i < 3; i++) {
      await page.click('#tab-transcript');
      await page.click('#tab-review');
      await page.click('#tab-salesforce');
    }
    const sfTextAfterSwitching = await getSfContent();
    check('salesforce draft retains live marker after multiple tab switches', sfTextAfterSwitching.includes(marker));
    await page.click('#tab-transcript');
    const transcriptAfterSwitching = await page.locator('#transcript-container').innerText();
    check('dialogue retains live marker after multiple tab switches', transcriptAfterSwitching.includes(marker));

    // 5. Verify Demo Button explicitly loads demo
    await page.click('#btn-load-sample');
    await page.waitForTimeout(400);
    await page.click('#tab-transcript');
    const demoTranscript = await page.locator('#transcript-container').innerText();
    check('demo button explicitly loads demo data', demoTranscript.includes('cheesecake') || demoTranscript.includes('butternut') || demoTranscript.includes('20288'));

    check('no uncaught JS errors in session provenance test', errors.length === 0, errors.join('; '));
    await ctx.close();
  }

  // ------------------------------------------------------------------ UI Sprint: Desktop Split, Salesforce Draft, History, Evidence
  console.log('\nUI Sprint Features (Desktop Split, Editable Draft, Call History Drawer, Evidence Links)');
  {
    const { ctx, page, errors } = await newPage({ viewport: { width: 1280, height: 800 } });

    // 1. Desktop Split Toggle (D.1)
    const splitBtn = page.locator('#btn-toggle-split');
    const mainContent = page.locator('#main-content');
    check('split toggle button visible on desktop', await splitBtn.isVisible());
    await splitBtn.click();
    check('desktop split active class added', await mainContent.evaluate((el) => el.classList.contains('desktop-split-active')));
    check('split toggle label updated', (await page.locator('#split-toggle-label').innerText()).includes('On'));
    
    // In split mode, verify two panels are visible simultaneously
    check('dual pane active: notes visible', await page.locator('#panel-notes').isVisible());
    check('dual pane active: review visible', await page.locator('#panel-review').isVisible());

    await splitBtn.click();
    check('desktop split toggled off', !(await mainContent.evaluate((el) => el.classList.contains('desktop-split-active'))));
    check('split toggle label reverted', (await page.locator('#split-toggle-label').innerText()).includes('Off'));

    // 2. Call History Drawer (D.3)
    const historyBtn = page.locator('#btn-call-history');
    const historyDrawer = page.locator('#call-history-drawer');
    const historyClose = page.locator('#ch-close');
    check('call history button exists in header', await historyBtn.isVisible());
    await historyBtn.click();
    check('call history drawer opens on click', await historyDrawer.isVisible());
    await historyClose.click();
    check('call history drawer closes on close button click', await historyDrawer.isHidden());

    // 3. Editable Salesforce Draft & Dirty Tracking (D.2)
    await page.click('#btn-load-sample');
    await page.waitForTimeout(400);
    await page.click('#tab-salesforce');

    const sfSubject = page.locator('#sf-subject');
    const sfEditedBadge = page.locator('#sf-edited-badge');
    const sfRestoreBtn = page.locator('#sf-restore-btn');
    const origSubject = await sfSubject.inputValue();

    check('salesforce subject input exists and is editable', await sfSubject.isEditable());
    check('salesforce edited badge initially hidden', await sfEditedBadge.isHidden());
    check('salesforce restore button initially hidden', await sfRestoreBtn.isHidden());

    // Edit subject field
    await sfSubject.fill('Edited Recipe Subject');
    await sfSubject.dispatchEvent('input');
    check('salesforce edited badge appears on change', await sfEditedBadge.isVisible());
    check('salesforce restore button appears on change', await sfRestoreBtn.isVisible());

    // Test field-level copy copies the live modified value
    await page.click('.sf-copy-field-btn[data-target="sf-subject"]');
    const copiedSubject = await page.evaluate(() => navigator.clipboard.readText());
    check('field-level copy copies the live edited value', copiedSubject === 'Edited Recipe Subject', copiedSubject);

    // Test restore button
    await sfRestoreBtn.click();
    check('salesforce subject restored to original value', (await sfSubject.inputValue()) === origSubject);
    check('salesforce edited badge hidden after restore', await sfEditedBadge.isHidden());
    check('salesforce restore button hidden after restore', await sfRestoreBtn.isHidden());

    // Test Full Record Copy button copies current values
    await page.click('#copy-sf-btn');
    const copiedFullRecord = await page.evaluate(() => navigator.clipboard.readText());
    check('copy full record copies formatted CRM payload', copiedFullRecord.includes('Case Subject:') && copiedFullRecord.includes(origSubject));

    // 4. Transcript Evidence Quote Linking & Highlighting (D.4)
    await page.click('#tab-review');
    const evidenceLinks = page.locator('.evidence-quote-link');
    const evidenceCount = await evidenceLinks.count();
    check('evidence quote links generated in review markdown', evidenceCount > 0);

    // Click an evidence link to trigger dialogue jump
    await evidenceLinks.first().click();
    check('clicking evidence link switches to transcript panel', await page.locator('#panel-transcript').isVisible());

    // 5. Reset Demo Action Across All Tabs
    console.log('\nReset Demo Action');
    const btnResetDemo = page.locator('#btn-reset-demo');
    const resetModal = page.locator('#reset-demo-modal');
    const rdCancel = page.locator('#rd-cancel-btn');
    const rdConfirm = page.locator('#rd-confirm-btn');

    check('reset demo button exists in UI', await btnResetDemo.isVisible());
    check('reset demo modal initially hidden', await resetModal.isHidden());

    // Load Demo Call first
    await page.click('#btn-load-sample');
    await page.waitForTimeout(400);
    check('demo note loaded in notes editor', (await page.locator('#notes').inputValue()).includes('cheesecake recipe'));
    check('QA tab shows Review Required badge', (await page.locator('#tab-qa-badge').innerText()) === 'Review');

    // Click Reset Demo -> confirmation modal appears
    await btnResetDemo.click();
    check('reset confirmation modal appears on click', await resetModal.isVisible());

    // Click Cancel -> modal closes, data remains intact
    await rdCancel.click();
    check('cancelling reset closes modal', await resetModal.isHidden());
    check('notes intact after cancel', (await page.locator('#notes').inputValue()).includes('cheesecake recipe'));
    check('QA badge intact after cancel', (await page.locator('#tab-qa-badge').innerText()) === 'Review');

    // Open modal again and confirm reset
    await btnResetDemo.click();
    await rdConfirm.click();
    check('confirming reset closes modal', await resetModal.isHidden());

    // Check Call & Notes tab state
    check('notes textarea empty after reset', (await page.locator('#notes').inputValue()) === '');
    check('counter shows 0 words after reset', (await page.locator('#counter').innerText()).includes('0 words'));
    check('tidy comparison hidden after reset', await page.locator('#tidy-comparison').isHidden());

    // Check Dialogue tab
    await page.click('#tab-transcript');
    const transcriptAfter = await page.locator('#transcript-container').innerText();
    check('dialogue container reset to empty state', transcriptAfter.includes('No call recorded yet'));
    check('dialogue turn count badge reset', (await page.locator('#transcript-count').innerText()) === '—');

    // Check AI Summary tab
    await page.click('#tab-review');
    const reviewAfter = await page.locator('#review-container').innerText();
    check('AI summary container reset to empty state', reviewAfter.includes('No call recorded yet'));
    check('confidence badge reset to —', (await page.locator('#review-confidence').innerText()) === '—');

    // Check Salesforce Draft tab
    await page.click('#tab-salesforce');
    const sfAfter = await page.locator('#salesforce-container').innerText();
    check('salesforce container reset to empty state', sfAfter.includes('No call recorded yet'));
    check('salesforce edited badge hidden after reset', await page.locator('#sf-edited-badge').isHidden());

    // Check QA Readiness tab
    await page.click('#tab-qa');
    check('QA tab badge reset to —', (await page.locator('#tab-qa-badge').innerText()) === '—');
    check('QA overall badge reset to —', (await page.locator('#qa-overall-badge').innerText()) === '—');
    check('QA score display reset to —', (await page.locator('#qa-score-display').innerText()) === '—');
    const qaChecksAfter = await page.locator('#qa-checks-container').innerText();
    check('QA checks container shows neutral message', qaChecksAfter.includes('No case note loaded'));

    // Switch across tabs to ensure no stale data reappears
    await page.click('#tab-notes');
    check('switching back to notes remains empty', (await page.locator('#notes').inputValue()) === '');
    await page.click('#tab-review');
    check('switching back to summary remains empty', (await page.locator('#review-container').innerText()).includes('No call recorded yet'));

    // Verify user preferences preserved: lang
    const currentLang = await page.locator('#lang').inputValue();
    check('user language preference preserved', currentLang.length > 0);

    // Verify existing Clear button still works with its Undo toast
    await page.click('#tab-notes');
    await page.locator('#notes').fill('Manual test note for clear button');
    await page.locator('#notes').dispatchEvent('input');
    await page.click('#clear');
    check('clear button clears notes only', (await page.locator('#notes').inputValue()) === '');
    const toastAction = page.locator('#toast-action');
    check('undo button visible in toast', await toastAction.isVisible() && (await toastAction.innerText()) === 'Undo');
    await toastAction.click();
    check('undo restores manual note', (await page.locator('#notes').inputValue()) === 'Manual test note for clear button');

    check('no uncaught JS errors in UI sprint tests', errors.length === 0, errors.join('; '));
    await ctx.close();
  }
} finally {
  await browser.close();
  server.close();
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
