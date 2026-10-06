/*
 * Reminder tracker – pure state, no DOM. Decides which matches are worth surfacing (anti-spam).
 *
 *  - surfaced: procedures already shown for the CURRENT note  -> never auto-shown twice
 *  - dismissed: procedures the user closed                    -> suppressed for the browser session
 *  - detected: everything relevant to the current note (so the user can explicitly reopen it)
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.ProcedureHub = root.ProcedureHub || {}).tracker = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const KEY = 'syn.ph.dismissed';

  /** @param {{storage?: Storage}} [opts] storage defaults to sessionStorage when available */
  function createReminderTracker(opts = {}) {
    let storage = opts.storage;
    if (storage === undefined) {
      try { storage = typeof sessionStorage !== 'undefined' ? sessionStorage : null; } catch { storage = null; }
    }

    const surfaced = new Set();
    const detected = new Map();
    let dismissed = new Set();
    try { dismissed = new Set(JSON.parse((storage && storage.getItem(KEY)) || '[]')); } catch { /* ignore */ }

    function persist() {
      try { storage && storage.setItem(KEY, JSON.stringify([...dismissed])); } catch { /* ignore */ }
    }

    return {
      /** Record matches for the current note; return only those that should pop up now. */
      consider(results) {
        const fresh = [];
        for (const r of results) {
          const id = r.procedure.id;
          detected.set(id, r.procedure);
          if (surfaced.has(id) || dismissed.has(id)) continue;
          surfaced.add(id);
          fresh.push(r);
        }
        return fresh;
      },
      dismiss(id) { dismissed.add(id); surfaced.add(id); persist(); },
      isDismissed(id) { return dismissed.has(id); },
      isSurfaced(id) { return surfaced.has(id); },
      detected() { return [...detected.values()]; },
      /** New note (cleared / emptied): forget what was surfaced. Dismissals last for the session. */
      resetNote() { surfaced.clear(); detected.clear(); },
    };
  }

  return { createReminderTracker };
});
