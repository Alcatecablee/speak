/*
 * Procedure relevance – deterministic, explainable matching (no AI, no network).
 *
 *   transcript ──normalise──► tokens ──match concepts──► score ──► eligible? / ranked
 *
 * A procedure carries `concepts`:  { name, terms: string[], weight: number, required?: boolean }
 *  - A concept is "matched" when any one of its terms appears as a whole-word phrase.
 *  - Each matched concept contributes its weight once.
 *  - A match that sits entirely inside a longer match (e.g. "kitchen" inside "kitchen printer") is ignored,
 *    so one phrase is never double-counted.
 *  - `required` concepts must all be present, otherwise the procedure is not eligible.
 *  - The procedure is relevant only when score >= threshold, so one weak keyword never triggers it.
 *
 * Works in the browser (window.ProcedureHub.relevance) and Node (require).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.ProcedureHub = root.ProcedureHub || {}).relevance = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DEFAULT_THRESHOLD = 5;

  /** Very small plural stemmer so "tables"/"table" and "slips"/"slip" compare equal. */
  function stem(word) {
    if (word.length > 3 && word.endsWith('s') && !word.endsWith('ss')) return word.slice(0, -1);
    return word;
  }

  /** "Can't cash-up!" -> ["cant", "cash", "up"] */
  function tokenise(text) {
    return String(text == null ? '' : text)
      .toLowerCase()
      .replace(/[\u2019']/g, '')        // don't -> dont
      .replace(/[^a-z0-9]+/g, ' ')      // punctuation / hyphens -> space
      .trim()
      .split(' ')
      .filter(Boolean)
      .map(stem);
  }

  function findStarts(tokens, termTokens) {
    const starts = [];
    for (let i = 0; i + termTokens.length <= tokens.length; i++) {
      let ok = true;
      for (let j = 0; j < termTokens.length; j++) {
        if (tokens[i + j] !== termTokens[j]) { ok = false; break; }
      }
      if (ok) starts.push(i);
    }
    return starts;
  }

  /**
   * Score one procedure against a transcript.
   * @returns {{score:number, eligible:boolean, matchedConcepts:Array<{name:string,term:string,weight:number}>}}
   */
  function scoreProcedure(procedure, text) {
    const tokens = Array.isArray(text) ? text : tokenise(text);
    const concepts = procedure.concepts || [];
    const candidates = [];

    for (const concept of concepts) {
      for (const term of concept.terms || []) {
        const termTokens = tokenise(term);
        if (!termTokens.length) continue;
        for (const start of findStarts(tokens, termTokens)) {
          candidates.push({ concept, term, start, end: start + termTokens.length });
        }
      }
    }

    const kept = candidates.filter((c) => !candidates.some((o) =>
      o !== c && o.start <= c.start && o.end >= c.end && (o.end - o.start) > (c.end - c.start)));

    const matched = new Map();
    for (const k of kept) {
      if (!matched.has(k.concept.name)) {
        matched.set(k.concept.name, { name: k.concept.name, term: k.term, weight: k.concept.weight == null ? 1 : k.concept.weight });
      }
    }

    const matchedConcepts = [...matched.values()];
    const score = matchedConcepts.reduce((sum, m) => sum + m.weight, 0);
    const eligible = concepts.filter((c) => c.required).every((c) => matched.has(c.name));
    return { score, eligible, matchedConcepts };
  }

  /**
   * Rank procedures that are relevant to the transcript (highest score first).
   * @param {Array} procedures
   * @param {string} text
   * @param {{threshold?:number, maxResults?:number}} [opts]
   */
  function rankProcedures(procedures, text, opts = {}) {
    const tokens = tokenise(text);
    const threshold = opts.threshold == null ? DEFAULT_THRESHOLD : opts.threshold;
    const out = [];
    for (const procedure of procedures) {
      const r = scoreProcedure(procedure, tokens);
      const needed = procedure.threshold == null ? threshold : procedure.threshold;
      if (r.eligible && r.score >= needed) out.push({ procedure, score: r.score, matchedConcepts: r.matchedConcepts });
    }
    out.sort((a, b) => b.score - a.score || a.procedure.title.localeCompare(b.procedure.title));
    return out.slice(0, opts.maxResults || 3);
  }

  return { DEFAULT_THRESHOLD, tokenise, scoreProcedure, rankProcedures };
});
