/* Speak Your Notes – vanilla JS, no dependencies. */
(() => {
  'use strict';

  // ---------------------------------------------------------------- elements
  const $ = (id) => document.getElementById(id);
  const notes = $('notes');
  const micBtn = $('mic');
  const micLabel = $('mic-label');
  const copyBtn = $('copy');
  const copyLabel = $('copy-label');
  const clearBtn = $('clear');
  const tidyBtn = $('tidy');
  const statusEl = $('status');
  const interimEl = $('interim');
  const counterEl = $('counter');
  const bannerEl = $('banner');
  const tagsEl = $('tags');
  const langSel = $('lang');
  const themeBtn = $('theme-toggle');
  const toastEl = $('toast');
  const toastText = $('toast-text');
  const toastAction = $('toast-action');

  // ---------------------------------------------------------------- storage
  const store = {
    get(k, d) { try { const v = localStorage.getItem('syn.' + k); return v === null ? d : v; } catch { return d; } },
    set(k, v) { try { localStorage.setItem('syn.' + k, v); } catch { /* private mode etc. */ } },
  };

  // ---------------------------------------------------------------- quick-insert shortcuts
  // `inline` tags insert a keyword at the caret; others insert a block template.
  // {|} marks where the caret lands afterwards so you can dictate straight into the first field.
  const fieldsTemplate = (title, firstField) =>
    `${title}:\n- ${firstField}: {|}\n- Issue: \n- Action taken: \n- Outcome: \n`;

  const TAGS = [
    { label: 'POS1', inline: true, text: 'POS1' },
    { label: 'GRV', text: fieldsTemplate('GRV', 'Supplier / Doc no.') },
    { label: 'Kitchen Printer', text: fieldsTemplate('Kitchen Printer', 'Printer name / IP') },
    { label: 'Adumo Base', text: fieldsTemplate('Adumo Base', 'Base / Site') },
    { label: 'Terminal', text: fieldsTemplate('Terminal', 'Terminal ID / Model') },
    { label: 'Stock Take', text: fieldsTemplate('Stock Take', 'Store / Section') },
    { label: 'Timestamp', inline: true, text: () => `[${stamp()}]` },
    { label: 'Follow-up', inline: true, text: 'Follow-up required: ' },
    { label: 'Resolved', inline: true, text: 'Resolved: ' },
  ];

  function stamp() {
    const d = new Date(), p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  // ---------------------------------------------------------------- text insertion
  const isCoarsePointer = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;

  /**
   * Insert text at the caret (or replace the selection).
   * opts.dictation  – smart spacing + sentence capitalisation
   * opts.block      – make sure the text starts on its own paragraph
   * opts.focus      – move focus into the textarea afterwards
   */
  function insertAtCaret(raw, opts = {}) {
    let text = raw;
    const start = notes.selectionStart ?? notes.value.length;
    const end = notes.selectionEnd ?? start;
    const before = notes.value.slice(0, start);
    const after = notes.value.slice(end);

    let caretOffset = null;
    const marker = text.indexOf('{|}');
    if (marker !== -1) { caretOffset = marker; text = text.replace('{|}', ''); }

    let prefix = '';
    if (opts.block) {
      if (before.length && !before.endsWith('\n\n')) prefix = before.endsWith('\n') ? '\n' : '\n\n';
    } else if (before.length && !/\s$/.test(before) && !/^[\s.,!?;:)]/.test(text)) {
      prefix = ' ';
    }

    if (opts.dictation) {
      const ctx = (before + prefix).replace(/[ \t]+$/, '');
      if (!ctx.length || /[.!?]$/.test(ctx) || /\n$/.test(ctx)) {
        text = text.replace(/^(\s*)([a-z])/, (_, ws, c) => ws + c.toUpperCase());
      }
      // Sentence starts inside the chunk (e.g. after a spoken "full stop" / "new line").
      text = text.replace(/([.!?]\s+|\n)([a-z])/g, (_, sep, c) => sep + c.toUpperCase());
    }

    const inserted = prefix + text;
    notes.value = before + inserted + after;
    const caret = before.length + prefix.length + (caretOffset ?? text.length);
    notes.setSelectionRange(caret, caret);

    if (opts.focus && !(isCoarsePointer && !opts.forceFocus)) notes.focus({ preventScroll: true });
    // Keep the caret visible when appending at the end.
    if (caret >= notes.value.length - 1) notes.scrollTop = notes.scrollHeight;
    onNotesChanged();
  }

  // ---------------------------------------------------------------- notes state
  let saveTimer = null;
  let procedureReminder = null; // set up in init; optional layer
  function onNotesChanged() {
    updateCounter();
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => store.set('notes', notes.value), 250);
    if (procedureReminder) procedureReminder.textChanged(notes.value);
  }
  function updateCounter() {
    const t = notes.value.trim();
    const words = t ? t.split(/\s+/).length : 0;
    counterEl.textContent = `${words} word${words === 1 ? '' : 's'} · ${notes.value.length} chars`;
  }
  notes.addEventListener('input', onNotesChanged);

  // ---------------------------------------------------------------- UI helpers
  function setStatus(text, tone) {
    statusEl.textContent = text;
    statusEl.className = 'truncate text-xs ' + (
      tone === 'rec' ? 'font-semibold text-red-500'
      : tone === 'err' ? 'font-semibold text-amber-600 dark:text-amber-400'
      : 'text-slate-500 dark:text-slate-400');
  }
  function showBanner(html) { bannerEl.innerHTML = html; bannerEl.hidden = false; }
  function hideBanner() { bannerEl.hidden = true; bannerEl.innerHTML = ''; }

  let toastTimer = null;
  function showToast(text, actionLabel, onAction, ms = 6000) {
    toastText.textContent = text;
    toastAction.textContent = actionLabel || '';
    toastAction.hidden = !actionLabel;
    toastAction.onclick = () => { hideToast(); onAction && onAction(); };
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, ms);
  }
  function hideToast() { toastEl.hidden = true; clearTimeout(toastTimer); }

  // ---------------------------------------------------------------- tags
  function renderTags() {
    TAGS.forEach((tag) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip';
      b.textContent = tag.label;
      b.dataset.tag = tag.label;
      // Keep the textarea caret/keyboard state intact when tapping a chip.
      b.addEventListener('pointerdown', (e) => e.preventDefault());
      b.addEventListener('click', () => {
        const text = typeof tag.text === 'function' ? tag.text() : tag.text;
        insertAtCaret(text, { block: !tag.inline, focus: true });
      });
      tagsEl.appendChild(b);
    });
  }

  // ---------------------------------------------------------------- copy / clear / tidy
  async function copyText() {
    const text = notes.value;
    if (!text.trim()) {
      copyBtn.classList.add('shake');
      setTimeout(() => copyBtn.classList.remove('shake'), 600);
      copyLabel.textContent = 'Nothing to copy';
      setTimeout(resetCopyLabel, 1500);
      return;
    }
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      // Fallback for insecure contexts / older browsers.
      const prevStart = notes.selectionStart, prevEnd = notes.selectionEnd;
      notes.focus(); notes.select();
      try { ok = document.execCommand('copy'); } catch { ok = false; }
      notes.setSelectionRange(prevStart, prevEnd);
    }
    if (ok) {
      copyLabel.textContent = 'Copied!';
      copyBtn.classList.add('!bg-emerald-600', '!text-white');
      clearTimeout(copyText.t);
      copyText.t = setTimeout(resetCopyLabel, 1800);
    } else {
      copyLabel.textContent = 'Copy failed';
      setTimeout(resetCopyLabel, 1800);
    }
  }
  function resetCopyLabel() {
    copyLabel.textContent = 'Copy';
    copyBtn.classList.remove('!bg-emerald-600', '!text-white');
  }

  function clearNotes() {
    const prev = notes.value;
    if (!prev) return;
    notes.value = '';
    onNotesChanged();
    stopInterim();
    showToast('Notes cleared', 'Undo', () => {
      notes.value = prev;
      notes.setSelectionRange(prev.length, prev.length);
      onNotesChanged();
    });
  }

  function tidy(text) {
    return text
      .trim()
      .replace(/[ \t]+/g, ' ')
      .replace(/ ?\n ?/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .replace(/ +([,.!?;:])/g, '$1')
      .replace(/([,;])(?=[A-Za-z])/g, '$1 ')
      .replace(/(^|[.!?]\s+|\n)((?:[-*•]\s+)?)([a-z])/g, (_, a, b, c) => a + b + c.toUpperCase())
      .replace(/\bi\b(?=[\s',.!?]|$)/g, 'I')
      .trim() + (text.trim() ? '\n' : '');
  }
  function tidyNotes() {
    const prev = notes.value;
    const next = tidy(prev);
    if (next === prev || !prev.trim()) { showToast('Already tidy', null, null, 1500); return; }
    notes.value = next;
    onNotesChanged();
    showToast('Notes tidied', 'Undo', () => { notes.value = prev; onNotesChanged(); });
  }

  // ---------------------------------------------------------------- theme
  function applyTheme(theme) {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    const meta = $('meta-theme');
    if (meta) meta.content = theme === 'dark' ? '#0f172a' : '#f1f5f9';
  }
  themeBtn.addEventListener('click', () => {
    const next = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
    store.set('theme', next);
    applyTheme(next);
  });

  // ---------------------------------------------------------------- dictation
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let wantRecording = false;   // user intent
  let state = 'idle';          // idle | starting | recording
  let quickEnds = 0;           // consecutive sessions that ended immediately
  let sessionStartedAt = 0;
  let lastFinal = { text: '', at: 0 };

  const MIC_CLASSES_IDLE = ['bg-teal-600', 'hover:bg-teal-500'];
  const MIC_CLASSES_REC = ['bg-red-600', 'hover:bg-red-500', 'mic-recording'];

  function setMicState(next) {
    state = next;
    const rec = next !== 'idle';
    micBtn.setAttribute('aria-pressed', String(rec));
    micBtn.classList.remove(...MIC_CLASSES_IDLE, ...MIC_CLASSES_REC);
    micBtn.classList.add(...(next === 'recording' ? MIC_CLASSES_REC : MIC_CLASSES_IDLE));
    micBtn.dataset.state = next;
    micLabel.textContent = next === 'idle' ? 'Start Dictation' : next === 'starting' ? 'Starting… (tap to cancel)' : 'Stop Dictation';
    if (next === 'recording') {
      statusEl.innerHTML = '<span class="rec-dot mr-1 inline-block h-2 w-2 rounded-full bg-red-500 align-middle"></span>Listening…';
      statusEl.className = 'truncate text-xs font-semibold text-red-500';
    } else if (next === 'starting') {
      setStatus('Waiting for microphone…');
    } else if (!bannerEl.hidden) {
      setStatus('Dictation unavailable', 'err');
    } else {
      setStatus('Ready');
    }
  }

  const VOICE_COMMANDS = [
    [/\s*\bnew paragraph\b[.,]?\s*/gi, '\n\n'],
    [/\s*\bnew line\b[.,]?\s*/gi, '\n'],
    [/\s*\bfull stop\b/gi, '.'],
    [/\s*\bquestion mark\b/gi, '?'],
    [/\s*\bexclamation mark\b/gi, '!'],
    [/\s*\bcomma\b/gi, ','],
  ];
  function applyVoiceCommands(t) {
    let out = t;
    for (const [re, rep] of VOICE_COMMANDS) out = out.replace(re, rep);
    return out;
  }

  function stopInterim() { interimEl.textContent = ''; }

  function permissionHelp() {
    return '<strong>Microphone access is blocked.</strong> Tap the lock / site-settings icon in the address bar, set <em>Microphone</em> to <em>Allow</em>, then try again.';
  }

  function startDictation() {
    hideBanner();
    if (!SR) {
      showBanner('<strong>Speech recognition isn\'t supported in this browser.</strong> Use Chrome, Edge or Safari (iOS 14.5+). You can still type and use the shortcut tags.');
      setStatus('Dictation unavailable', 'err');
      return;
    }
    if (!window.isSecureContext) {
      showBanner('<strong>Microphone needs a secure connection.</strong> Open the app over <code>https://</code> or <code>http://localhost</code>.');
      setStatus('Dictation unavailable', 'err');
      return;
    }
    wantRecording = true;
    quickEnds = 0;
    beginSession();
  }

  function stopDictation() {
    wantRecording = false;
    if (recognition) { try { recognition.stop(); } catch { /* already stopped */ } }
    setMicState('idle');
    stopInterim();
  }

  function fatal(html) {
    wantRecording = false;
    showBanner(html);
    setMicState('idle');
    stopInterim();
  }

  function beginSession() {
    const r = new SR();
    recognition = r;
    r.continuous = true;
    r.interimResults = true;
    r.maxAlternatives = 1;
    r.lang = langSel.value;
    setMicState('starting');

    r.onstart = () => {
      if (r !== recognition) return;
      sessionStartedAt = Date.now();
      setMicState('recording');
    };

    r.onresult = (e) => {
      if (r !== recognition) return;
      quickEnds = 0;
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        const t = res[0].transcript;
        if (res.isFinal) {
          const chunk = applyVoiceCommands(t.trim());
          const now = Date.now();
          // Some Android builds re-emit the same final phrase; drop immediate duplicates.
          if (!chunk || (chunk === lastFinal.text && now - lastFinal.at < 1200)) continue;
          lastFinal = { text: chunk, at: now };
          insertAtCaret(chunk, { dictation: true });
        } else {
          interim += t;
        }
      }
      interimEl.textContent = interim ? '… ' + interim.trim() : '';
    };

    r.onerror = (e) => {
      if (r !== recognition) return;
      switch (e.error) {
        case 'not-allowed':
        case 'service-not-allowed':
          fatal(permissionHelp());
          break;
        case 'audio-capture':
          fatal('<strong>No microphone found.</strong> Check that a microphone is connected and not in use by another app.');
          break;
        case 'network':
          fatal('<strong>Speech service unreachable.</strong> Dictation needs an internet connection in this browser.');
          break;
        case 'language-not-supported':
          fatal('<strong>That language isn\'t supported</strong> by this browser. Try EN-US or EN-GB.');
          break;
        case 'no-speech':
        case 'aborted':
        default:
          break; // onend will restart if the user still wants to record
      }
    };

    r.onend = () => {
      if (r !== recognition) return;
      stopInterim();
      if (!wantRecording) { setMicState('idle'); return; }
      // Browsers end continuous sessions after silence – transparently resume.
      if (Date.now() - sessionStartedAt < 1000) quickEnds++;
      if (quickEnds > 3) {
        fatal('<strong>Dictation keeps stopping.</strong> Check your microphone and connection, then tap Start Dictation again.');
        return;
      }
      setTimeout(() => { if (wantRecording && r === recognition) beginSession(); }, 150);
    };

    try {
      r.start();
    } catch (err) {
      fatal('<strong>Couldn\'t start dictation.</strong> ' + (err && err.message ? err.message : 'Please try again.'));
    }
  }

  micBtn.addEventListener('click', () => {
    if (state === 'idle') startDictation(); else stopDictation();
  });

  // Reflect the browser's microphone permission (where the Permissions API supports it).
  async function watchMicPermission() {
    if (!navigator.permissions || !navigator.permissions.query) return;
    try {
      const p = await navigator.permissions.query({ name: 'microphone' });
      const apply = () => {
        if (p.state === 'denied') {
          showBanner(permissionHelp());
          if (state === 'idle') setStatus('Microphone blocked', 'err');
        } else if (!wantRecording && !bannerEl.hidden && bannerEl.textContent.includes('blocked')) {
          hideBanner();
          if (state === 'idle') setStatus('Ready');
        }
      };
      p.onchange = apply;
      apply();
    } catch { /* 'microphone' not queryable (e.g. Safari) – fine */ }
  }

  // ---------------------------------------------------------------- shortcuts & lifecycle
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Shift + Space toggles dictation; Ctrl/Cmd + Shift + C copies.
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.code === 'Space') { e.preventDefault(); micBtn.click(); }
    else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.code === 'KeyC') { e.preventDefault(); copyText(); }
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden && wantRecording) stopDictation(); });

  langSel.addEventListener('change', () => {
    store.set('lang', langSel.value);
    if (wantRecording) { // restart with the new language
      const old = recognition; recognition = null;
      try { old && old.abort(); } catch { /* noop */ }
      beginSession();
    }
  });

  copyBtn.addEventListener('click', copyText);
  clearBtn.addEventListener('click', clearNotes);
  tidyBtn.addEventListener('click', tidyNotes);

  // ---------------------------------------------------------------- init
  // Procedure Hub awareness layer. The service is the only source of procedures: to move from demo data to
  // the real Procedure Hub, provide an object with findRelevantProcedures()/getProcedure() as
  // window.SYN_PROCEDURE_SERVICE (see procedures/procedureService.js for the contract).
  (function initProcedureLayer() {
    const PH = window.ProcedureHub;
    if (!PH || !PH.createReminderController) return;
    const service = window.SYN_PROCEDURE_SERVICE || PH.service.createDemoProcedureService();
    procedureReminder = PH.createReminderController({
      service,
      tracker: PH.tracker.createReminderTracker(),
      els: {
        cards: $('ph-cards'),
        tray: $('ph-tray'),
        modal: {
          root: $('ph-modal'),
          close: $('ph-m-close'),
          fields: {
            title: $('ph-m-title'), status: $('ph-m-status'), version: $('ph-m-version'),
            effective: $('ph-m-effective'), instruction: $('ph-m-instruction'),
            source: $('ph-m-source'), updated: $('ph-m-updated'), demo: $('ph-m-demo'),
          },
        },
      },
    });
  })();

  renderTags();
  notes.value = store.get('notes', '');
  notes.setSelectionRange(notes.value.length, notes.value.length);
  langSel.value = store.get('lang', 'en-ZA');
  if (langSel.value !== store.get('lang', 'en-ZA')) langSel.value = 'en-ZA';
  updateCounter();
  setMicState('idle');
  if (!SR) {
    showBanner('<strong>Speech recognition isn\'t supported in this browser.</strong> Use Chrome, Edge or Safari. You can still type and use the shortcut tags.');
    setStatus('Dictation unavailable', 'err');
  }
  watchMicPermission();

  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
    window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
  }
})();
