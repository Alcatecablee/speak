/*
 * Procedure reminder UI – a small, non-blocking layer over the notepad.
 *
 *   note text ──debounce──► service.findRelevantProcedures ──► tracker (anti-spam) ──► cards / tray / panel
 *
 * Guarantees:
 *  - never touches the note text, the caret, focus or speech recognition
 *  - never shows the same procedure twice automatically (see reminderTracker.js)
 *  - knows nothing about where procedures come from – only the `service` contract
 */
(function (root, factory) {
  (root.ProcedureHub = root.ProcedureHub || {}).createReminderController = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function formatDate(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    if (!m) return iso || '—';
    return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  }
  function formatDateTime(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return iso || '—';
    return d.toLocaleString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  function el(tag, className, text) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text != null) e.textContent = text;
    return e;
  }

  /**
   * @param {{service: object, tracker: object, els: object, debounceMs?: number}} cfg
   */
  function createReminderController({ service, tracker, els, debounceMs = 400 }) {
    const { cards, tray, modal } = els;
    let timer = null;
    let seq = 0;                 // guards against out-of-order async results
    let lastFocus = null;
    const visible = new Map();   // procedure id -> card element
    let surfacedCount = 0;
    cards.dataset.surfacedCount = '0';

    // ------------------------------------------------------------ detection
    function textChanged(text) {
      clearTimeout(timer);
      if (!String(text).trim()) { resetNote(); return; }
      timer = setTimeout(() => evaluate(text), debounceMs);
    }

    async function evaluate(text) {
      const mine = ++seq;
      let results;
      try { results = await service.findRelevantProcedures(text); } catch { return; }
      if (mine !== seq || !Array.isArray(results)) return;
      tracker.consider(results).forEach((r) => addCard(r.procedure, true));
      renderTray();
    }

    function resetNote() {
      clearTimeout(timer);
      seq++;
      tracker.resetNote();
      visible.forEach((c) => c.remove());
      visible.clear();
      syncCardsVisibility();
      renderTray();
    }

    // ------------------------------------------------------------ cards
    function addCard(p, isNew) {
      if (visible.has(p.id)) return;
      const card = el('article', 'rounded-xl border border-slate-200/80 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-900');
      card.dataset.procedureId = p.id;
      card.setAttribute('aria-label', 'Procedure Hub reminder: ' + p.title);

      const top = el('div', 'flex items-start justify-between gap-2');
      const body = el('div', 'min-w-0');
      body.append(
        el('p', 'text-xs font-medium text-slate-500 dark:text-slate-400', 'Procedure Hub · possible relevant procedure'),
        el('p', 'mt-0.5 truncate font-semibold text-slate-900 dark:text-slate-100', p.title),
        el('p', 'mt-0.5 line-clamp-2 text-xs text-slate-600 dark:text-slate-300', p.instruction),
      );
      const close = el('button', 'grid h-8 w-8 shrink-0 place-items-center rounded-lg text-lg leading-none text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200', '×');
      close.type = 'button';
      close.dataset.action = 'dismiss';
      close.setAttribute('aria-label', 'Dismiss ' + p.title);
      close.addEventListener('click', () => dismiss(p.id));
      top.append(body, close);

      const row = el('div', 'mt-2 flex items-center gap-3');
      const view = el('button', 'rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400 transition', 'View Procedure');
      view.type = 'button';
      view.dataset.action = 'view';
      view.addEventListener('click', () => openProcedure(p.id));
      row.append(view);
      if (p.isDemo) row.append(el('span', 'text-[11px] text-slate-400 dark:text-slate-500', 'Demo data'));

      card.append(top, row);
      cards.append(card);
      visible.set(p.id, card);
      if (isNew) { surfacedCount++; cards.dataset.surfacedCount = String(surfacedCount); }
      syncCardsVisibility();
    }

    function dismiss(id) {
      tracker.dismiss(id);
      const card = visible.get(id);
      if (card) card.remove();
      visible.delete(id);
      syncCardsVisibility();
      renderTray();
    }

    function syncCardsVisibility() { cards.hidden = visible.size === 0; }

    // ------------------------------------------------------------ tray (explicit reopen)
    function hiddenDetected() { return tracker.detected().filter((p) => !visible.has(p.id)); }

    function renderTray() {
      const n = hiddenDetected().length;
      tray.hidden = n === 0;
      tray.textContent = 'Procedure Hub · ' + n;
      tray.setAttribute('aria-label', n + ' procedure' + (n === 1 ? '' : 's') + ' related to this note – show');
    }

    tray.addEventListener('click', () => { hiddenDetected().forEach((p) => addCard(p, false)); renderTray(); });

    // ------------------------------------------------------------ panel
    async function openProcedure(id) {
      let p = null;
      try { p = await service.getProcedure(id); } catch { /* fall back below */ }
      if (!p) p = tracker.detected().find((x) => x.id === id);
      if (!p) return;
      const set = (key, text) => { modal.fields[key].textContent = text; };
      set('title', p.title);
      set('status', p.status);
      set('version', 'Version ' + p.version);
      set('effective', formatDate(p.effectiveDate));
      set('instruction', p.instruction);
      set('source', p.source);
      set('updated', formatDateTime(p.lastUpdated));
      modal.fields.demo.hidden = !p.isDemo;
      lastFocus = document.activeElement;
      modal.root.hidden = false;
      modal.close.focus({ preventScroll: true });
    }

    function closePanel() {
      if (modal.root.hidden) return;
      modal.root.hidden = true;
      if (lastFocus && lastFocus.isConnected && lastFocus !== document.body) lastFocus.focus({ preventScroll: true });
      lastFocus = null;
    }

    modal.close.addEventListener('click', closePanel);
    modal.root.addEventListener('click', (e) => { if (e.target === modal.root) closePanel(); });
    document.addEventListener('keydown', (e) => {
      if (modal.root.hidden) return;
      if (e.key === 'Escape') { e.preventDefault(); closePanel(); }
      else if (e.key === 'Tab') { e.preventDefault(); modal.close.focus(); } // single focusable control
    });

    return { textChanged, resetNote, evaluate, dismiss, closePanel };
  }

  return createReminderController;
});
