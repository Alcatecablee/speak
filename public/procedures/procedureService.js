/*
 * Procedure service – the ONLY thing the UI knows about where procedures come from.
 *
 * Contract (kept async so a real HTTP client is a drop-in replacement):
 *
 *   Procedure = {
 *     id, title, status, version, effectiveDate (YYYY-MM-DD), instruction,
 *     source, lastUpdated (ISO 8601), isDemo?
 *   }
 *
 *   service.findRelevantProcedures(transcript: string)
 *       -> Promise<Array<{ procedure: Procedure, score: number }>>   (most relevant first, may be empty)
 *   service.getProcedure(id: string)
 *       -> Promise<Procedure | null>
 *
 * Phase 1 implementation: searches local demo data with the deterministic matcher.
 * Later: provide an object with the same two methods that calls the Procedure Hub API and set it as
 * `window.SYN_PROCEDURE_SERVICE` (or change the one line in app.js) – the UI does not change.
 */
(function (root, factory) {
  const dep = (name, path) => (typeof module === 'object' && module.exports
    ? require(path) : (root.ProcedureHub || {})[name]);
  const api = factory(dep('relevance', './relevance.js'), dep('demoProcedures', './demoProcedures.js'));
  if (typeof module === 'object' && module.exports) module.exports = api;
  else (root.ProcedureHub = root.ProcedureHub || {}).service = api;
})(typeof self !== 'undefined' ? self : this, function (relevance, demoProcedures) {
  'use strict';

  /** Strip matcher internals so consumers only ever see the public Procedure shape. */
  function toPublic(p) {
    const { concepts, threshold, ...pub } = p; // eslint-disable-line no-unused-vars
    return { ...pub };
  }

  /**
   * @param {{procedures: Array, threshold?: number, maxResults?: number}} opts
   */
  function createLocalProcedureService({ procedures, threshold, maxResults = 3 }) {
    return {
      kind: 'local',
      async findRelevantProcedures(transcript) {
        const active = procedures.filter((p) => p.status === 'Active');
        return relevance
          .rankProcedures(active, transcript, { threshold, maxResults })
          .map((r) => ({ procedure: toPublic(r.procedure), score: r.score }));
      },
      async getProcedure(id) {
        const p = procedures.find((x) => x.id === id);
        return p ? toPublic(p) : null;
      },
    };
  }

  function createDemoProcedureService() {
    return createLocalProcedureService({ procedures: demoProcedures });
  }

  return { createLocalProcedureService, createDemoProcedureService };
});
