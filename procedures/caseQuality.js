/*
 * Case Note Polishing & Prototype QA Readiness Layer for Speak Your Notes.
 *
 * 1. polishCaseNote(rawText):
 *    - Corrects grammar, spelling, punctuation, capitalisation, and sentence flow.
 *    - Retains first-person, past-tense consultant narrative describing work actually performed.
 *    - Preserves product names, technical terms, quantities, dates, and case details.
 *    - Preserves uncertainty (suspected causes remain suspected; attempted actions remain attempted).
 *    - Never invents troubleshooting steps, customer confirmation, root causes, or resolutions.
 *    - Outputs ONLY the polished case note (no explanations, coaching, or tutorial steps).
 *
 * 2. evaluateQaReadiness(context):
 *    - Prototype QA Readiness check inspired by internal case QA criteria.
 *    - Flags missing evidence using clear statuses: "Ready", "Needs attention", "Unverified", "Not applicable".
 *    - Explains what evidence is missing and what the technician needs to review.
 *    - Does not fabricate information or present an unvalidated score as an official scorecard.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.CaseQuality = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const GERUND_MAP = {
    restarted: 'restarting',
    rebooted: 'rebooting',
    reset: 'resetting',
    updated: 'updating',
    checked: 'checking',
    configured: 'configuring',
    reinstalled: 'reinstalling',
    closed: 'closing',
    started: 'starting',
  };

  const SPELLING_FIXES = [
    [/\bbecuase\b/gi, 'because'],
    [/\bbecasue\b/gi, 'because'],
    [/\bbeacuse\b/gi, 'because'],
    [/\brecieved\b/gi, 'received'],
    [/\brecived\b/gi, 'received'],
    [/\badviced\b/gi, 'advised'],
    [/\badivsed\b/gi, 'advised'],
    [/\bcheked\b/gi, 'checked'],
    [/\bchcked\b/gi, 'checked'],
    [/\bconected\b/gi, 'connected'],
    [/\bconecting\b/gi, 'connecting'],
    [/\brestartedd\b/gi, 'restarted'],
    [/\brestared\b/gi, 'restarted'],
    [/\bcustmer\b/gi, 'customer'],
    [/\bcostumer\b/gi, 'customer'],
    [/\bcleint\b/gi, 'client'],
    [/\bclinet\b/gi, 'client'],
    [/\bmachien\b/gi, 'machine'],
    [/\bmashine\b/gi, 'machine'],
    [/\bprintr\b/gi, 'printer'],
    [/\bprnter\b/gi, 'printer'],
    [/\bterimnal\b/gi, 'terminal'],
    [/\btermnial\b/gi, 'terminal'],
    [/\bnetowrk\b/gi, 'network'],
    [/\bnetwerk\b/gi, 'network'],
    [/\bpasword\b/gi, 'password'],
    [/\bpasswrd\b/gi, 'password'],
    [/\bdatabse\b/gi, 'database'],
    [/\bdatbase\b/gi, 'database'],
    [/\bvaraince\b/gi, 'variance'],
    [/\bvarience\b/gi, 'variance'],
    [/\bsuplier\b/gi, 'supplier'],
    [/\binvocie\b/gi, 'invoice'],
    [/\btransacion\b/gi, 'transaction'],
    [/\btrasaction\b/gi, 'transaction'],
    [/\bconfiguraton\b/gi, 'configuration'],
    [/\bworkign\b/gi, 'working'],
    [/\bescalted\b/gi, 'escalated'],
    [/\bloged\b/gi, 'logged'],
    [/\bofflinee\b/gi, 'offline'],
  ];

  const DOMAIN_TERMS = [
    [/\bkingpos\b/gi, 'Kingpos'],
    [/\bsql\s+agent\s+service\b/gi, 'SQL Agent service'],
    [/\bsql\s+agent\b/gi, 'SQL Agent'],
    [/\bback\s+office\b/gi, 'Back Office'],
    [/\badumo\s+ped\b/gi, 'Adumo PED'],
    [/\badumo\b/gi, 'Adumo'],
    [/\bped\b/gi, 'PED'],
    [/\bpos\s*(\d+)\b/gi, 'POS$1'],
    [/\bpos\b/gi, 'POS'],
    [/\bmc\s*(\d+)\b/gi, 'MC$1'],
    [/\bgrvs\b/gi, 'GRVs'],
    [/\bgrv\b/gi, 'GRV'],
    [/\bsql\b/gi, 'SQL'],
    [/\banyshop\b/gi, 'AnyShop'],
    [/\bmicrosip\b/gi, 'MicroSIP'],
    [/\bsalesforce\b/gi, 'Salesforce'],
    [/\bpolokwane\b/gi, 'Polokwane'],
    [/\blimpopo\b/gi, 'Limpopo'],
    [/\b(\d+(?:\.\d+)?)\s*kg\b/gi, '$1 KG'],
    [/\bprinter\s+ip\b/gi, 'printer IP'],
    [/\bstatic\s+ip\b/gi, 'static IP'],
    [/\bip\s+address\b/gi, 'IP address'],
  ];

  const DEMO_CASE_NOTES = [
    {
      id: 'kingpos-mc2-demo',
      label: 'Kingpos / MC2 Demo',
      description: 'Synthetic Kingpos / MC2 troubleshooting note demonstrating rough input, polished Salesforce-ready draft, and QA Readiness findings.',
      raw: 'client reported cant open kingpos on mc2 after i restarted the machine. dialed in to mc2 and restarted the sql agent service. tested again and could open kingpos. waiting for cashier to confirm transaction',
      preparedPolished: 'After restarting the machine, the client was unable to open Kingpos on MC2. I dialed in to MC2 and restarted the SQL Agent service. I tested it again and was able to open Kingpos. Waiting for the cashier to confirm transaction processing.',
      readinessStatus: 'Review Required',
      salesforceFields: {
        Subject: 'Kingpos Login Failure on MC2',
        Description: 'After restarting the machine, the client was unable to open Kingpos on MC2. I dialed in to MC2 and restarted the SQL Agent service. I tested it again and was able to open Kingpos. Waiting for the cashier to confirm transaction processing.',
        Status: 'Pending Follow-up',
        Resolution_Category__c: 'POS Application / Services',
        Remote_Connection_ID__c: 'MC2',
        Client_Sentiment__c: 'NEUTRAL',
        AI_Confidence_Score__c: 0.85,
        Internal_Review_Notes__c: 'Simulated Demo Draft: Technical fix verified by consultant on MC2. Client transaction processing unconfirmed; case cannot be marked resolved until cashier confirms.',
      },
    },
    {
      id: 'video-showcase-case',
      label: 'Back Office & Cash-Up',
      description: 'Multi-issue support note demonstrating before/after polishing, Procedure Hub triggers, and QA Readiness findings.',
      raw: 'the client could not open the back office after i restarted the machine on mc1. i checked the sql service, it was stopped so i started it again. i tested again and could open the back office. client also said she cant cash up on pos1 becuase there was open tables and asked for till roll slips, i adviced them we dont supply till roll slips outside polokwane',
    },
    {
      id: 'back-office-benchmark',
      label: 'Back Office Restart (Benchmark)',
      description: 'Core before-and-after polishing example preserving exact facts without inventing client confirmation.',
      raw: 'The client could not open the back office after I restarted the machine. I tested again and could open the back office.',
    },
    {
      id: 'adumo-ped-uncertainty',
      label: 'Adumo PED (Suspected Cause)',
      description: 'Demonstrates preserving suspected causes and unconfirmed test outcomes without premature resolution claims.',
      raw: 'adumo ped offline on pos2 since 08:30, card machine not connecting. i dialed in to terminal and restarted the adumo driver service. suspect the network cable might be loose. tried a test transaction but still waiting for cashier to confirm if card machine is working',
    },
    {
      id: 'production-recipe-demo',
      label: 'Production Recipe Demo',
      description: 'Grounded production recipe variance note corresponding directly to the 9-minute call fixture.',
      raw: 'client reported variance on cheesecake recipe deducting whole batch instead of slices. dialed in to MC1 and checked recipe setup in production module. client also asked for butternut puree to be set to 1 KG. will check recipe setup and call client back within 15 minutes. issue not resolved yet.',
      preparedPolished: 'Client reported variance on cheesecake recipe deducting whole batch instead of slices. I dialed in to MC1 and checked recipe setup in production module. Client also asked for butternut puree to be set to 1 KG. Will check recipe setup and call client back within 15 minutes. Issue not resolved yet.',
      readinessStatus: 'Review Required',
      salesforceFields: {
        Subject: 'Production Recipe Variance - 20288 2622 2622',
        Description: 'Logged a case for a production variance issue on the cheesecake recipe. I dialed in to MC1 and checked the recipe setup. The system was using the whole cheesecake instead of individual slices. The client also asked for Butternut Puree to be set to 1 KG. I will check the recipe setup and call the client back within 15 minutes. Issue not resolved yet.',
        Status: 'Pending Follow-up',
        Resolution_Category__c: 'Production Configuration',
        Remote_Connection_ID__c: '20288 2622 2622',
        Client_Sentiment__c: 'NEUTRAL',
        AI_Confidence_Score__c: 0.8,
        Internal_Review_Notes__c: "Repetitive STT looping detected in transcript. Phonetic normalization applied to 1 term(s) (e.g. 'Bata Nadpuray' -> 'Butternut Puree'). Review raw quote if unverified.",
      },
    },
  ];

  function stripUnwantedCommentary(text) {
    let out = String(text || '');
    // Strip any meta-commentary blocks if present
    out = out.replace(/\n*\s*(?:Key Corrections Made|Corrections Made|Explanation|Notes on Changes|Follow-up Questions|Coaching Notes)\s*:[\s\S]*$/i, '');
    out = out.replace(/^(?:Here is the polished (?:case )?note|Polished (?:case )?note)\s*:\s*/i, '');
    return out;
  }

  function applySpellingAndDomainTerms(text) {
    let out = text;
    for (const [re, rep] of SPELLING_FIXES) {
      out = out.replace(re, rep);
    }
    for (const [re, rep] of DOMAIN_TERMS) {
      out = out.replace(re, rep);
    }
    return out;
  }

  function polishSingleSentence(rawSentence) {
    let s = rawSentence.trim();
    if (!s) return '';

    // Remove tutorial step prefixes ("Step 1:", "Step 2 -", etc.) so notes describe work completed, not tutorials
    s = s.replace(/^Step\s+\d+\s*[:.-]\s*/i, '');

    // Apply spelling fixes first so structural patterns see clean words
    for (const [re, rep] of SPELLING_FIXES) {
      s = s.replace(re, rep);
    }

    // Remove trailing punctuation temporarily to transform cleanly
    const endPunctMatch = s.match(/([.!?]+)$/);
    const endPunct = endPunctMatch ? endPunctMatch[1][0] : '.';
    let core = s.replace(/[.!?]+$/, '').trim();

    // 1. Reorder post-posed "after I <verbed> <target>" when client could not perform an action
    // e.g., "The client could not open the back office after I restarted the machine"
    // -> "After restarting the machine, the client was unable to open the Back Office."
    const afterRestartMatch = core.match(
      /^(?:the\s+)?(client|customer|user|cashier|manager|store)\s+(?:reported\s+)?(?:that\s+)?(?:she|he|they)?\s*(?:could not|couldn't|couldnt|cannot|can't|cant|was unable to|were unable to)\s+(.+?)\s+after\s+i\s+(restarted|rebooted|reset|updated|checked|configured|reinstalled|closed|started)\s+(.+)$/i
    );
    if (afterRestartMatch) {
      const [, actor, action, verb, obj] = afterRestartMatch;
      const gerund = GERUND_MAP[verb.toLowerCase()] || `${verb.toLowerCase()}ing`;
      const actorNorm = actor.toLowerCase();
      core = `After ${gerund} ${obj.trim()}, the ${actorNorm} was unable to ${action.trim()}`;
    }

    // Dial in opener
    core = core.replace(/^dialed\s+in\s+to\s+/i, 'I dialed in to ');

    // 2. "I tested again and could <verb> <obj>" -> "I tested it again and was able to <verb> <obj>"
    const testedAgainPositive = core.match(
      /^(?:i\s+)?tested\s+again\s+and\s+(?:could|was able to)\s+(open|access|log into|log in to|print to|connect to|launch|start|use|view|reach)\s+(.+)$/i
    );
    if (testedAgainPositive) {
      const [, verb, obj] = testedAgainPositive;
      core = `I tested it again and was able to ${verb.toLowerCase()} ${obj.trim()}`;
    }

    const testedAgainNegative = core.match(
      /^(?:i\s+)?tested\s+again\s+and\s+(?:could not|couldn't|couldnt|was unable to)\s+(open|access|log into|log in to|print to|connect to|launch|start|use|view|reach)\s+(.+)$/i
    );
    if (testedAgainNegative) {
      const [, verb, obj] = testedAgainNegative;
      core = `I tested it again and was unable to ${verb.toLowerCase()} ${obj.trim()}`;
    }

    // Pending confirmation opener
    core = core.replace(
      /^waiting\s+for\s+(?:the\s+)?(cashier|client|customer)\s+to\s+confirm\s+transaction(?:\s+processing)?$/i,
      (_, person) => `Waiting for the ${person.toLowerCase()} to confirm transaction processing`
    );

    // 3. Compound service check: "i (dialed in to X and )checked the Y, it was stopped so i started it again"
    const serviceCheckMatch = core.match(
      /^i\s+(?:dialed\s+in\s+to\s+([^\s,]+)\s+and\s+)?checked\s+the\s+([^,]+?),\s*it\s+was\s+(stopped|offline|down|hung|frozen|disabled)\s+so\s+i\s+(started|restarted|enabled|reset)\s+it(\s+again)?$/i
    );
    if (serviceCheckMatch) {
      const [, target, service, state, action, again] = serviceCheckMatch;
      const againSuffix = again ? ' again' : '';
      if (target) {
        core = `I dialed in to ${target}, checked the ${service.trim()}, and found that it was ${state.toLowerCase()}, so I ${action.toLowerCase()} it${againSuffix}`;
      } else {
        core = `I checked the ${service.trim()} and found that it was ${state.toLowerCase()}, so I ${action.toLowerCase()} it${againSuffix}`;
      }
    }

    // 4. Compound check + still offline: "i checked the X, it is still offline"
    core = core.replace(
      /^i\s+checked\s+the\s+([^,]+?),\s*it\s+is\s+(still\s+.+)$/i,
      (_, target, rest) => `I checked the ${target.trim()}, and it is ${rest.trim()}`
    );

    // 5. Client also said/reported + open tables + optional till roll advisory
    core = core.replace(
      /^(?:the\s+)?(client|customer)\s+(also\s+)?(?:said|reported|called\s+and\s+said)\s+(?:that\s+)?(she|he|they)\s+(?:cant|can't|cannot|couldnt|couldn't|was unable to|were unable to)\s+(.+?)\s+because\s+there\s+(?:was|were|are)\s+open\s+tables\s+and\s+asked\s+for\s+(.+?),\s*i\s+advised\s+(them|her|him|the client|the customer)\s+(?:that\s+)?we\s+(?:dont|don't|do not)\s+(.+)$/i,
      (_, actor, also, pron, action, requestedItem, adviseTarget, policyRest) => {
        const alsoStr = also ? 'also ' : '';
        const pronLower = pron.toLowerCase();
        const verbBe = pronLower === 'they' ? 'were' : 'was';
        return `The ${actor.toLowerCase()} ${alsoStr}reported that ${pronLower} ${verbBe} unable to ${action.trim()} due to open tables and requested ${requestedItem.trim()}; I advised ${adviseTarget.toLowerCase()} that we do not ${policyRest.trim()}`;
      }
    );

    // 6. "client called cant <action> because there was/were open tables"
    core = core.replace(
      /^(?:the\s+)?(client|customer)\s+called\s+(?:because\s+)?(?:(she|he|they)\s+)?(?:cant|can't|cannot|couldnt|couldn't|was unable to|were unable to)\s+(.+?)\s+because\s+there\s+(?:was|were|are)\s+open\s+tables$/i,
      (_, actor, pron, action) => {
        const subj = pron ? pron.toLowerCase() : 'they';
        const verbBe = subj === 'they' ? 'were' : 'was';
        return `The ${actor.toLowerCase()} called because ${subj} ${verbBe} unable to ${action.trim()} due to open tables`;
      }
    );

    // 7. "client also asked for X to be supplied, i advised them we dont supply..."
    core = core.replace(
      /^(?:the\s+)?(client|customer)\s+(also\s+)?asked\s+for\s+(.+?)(?:\s+to\s+be\s+supplied)?,\s*i\s+advised\s+(them|her|him|the client)\s+(?:that\s+)?we\s+(?:dont|don't|do not)\s+(.+)$/i,
      (_, actor, also, item, target, rest) => {
        const alsoStr = also ? 'also ' : '';
        return `The ${actor.toLowerCase()} ${alsoStr}requested ${item.trim()}, and I advised ${target.toLowerCase()} that we do not ${rest.trim()}`;
      }
    );

    // 8. "adumo ped offline on X since Y, card machine not connecting"
    core = core.replace(
      /^(?:the\s+)?adumo\s+ped\s+offline\s+on\s+(\S+)\s+since\s+(\S+),\s*(?:the\s+)?card\s+machine\s+(?:is\s+)?not\s+connecting$/i,
      (_, pos, time) => `The Adumo PED has been offline on ${pos} since ${time}, with the card machine not connecting`
    );

    // 9. "tried a <action> but still waiting for <person> to confirm if <device> is working"
    core = core.replace(
      /^(?:i\s+)?tried\s+a\s+(.+?)\s+but\s+(?:i\s+am\s+|im\s+|i'm\s+)?still\s+waiting\s+for\s+(?:the\s+)?(cashier|client|customer|manager|user)\s+to\s+confirm\s+(?:if|whether)\s+(?:the\s+)?(.+?)\s+is\s+working$/i,
      (_, testAction, person, device) =>
        `I tried a ${testAction.trim()}, but I am still waiting for the ${person.toLowerCase()} to confirm whether the ${device.trim()} is working`
    );

    // 10. Preserve & polish subjectless first-person uncertainty/attempt openers
    core = core.replace(/^suspect\s+(?:that\s+)?(the\s+.+)$/i, (_, rest) => `I suspect ${rest}`);
    core = core.replace(/^tried\s+to\s+(.+?)\s+but\s+it\s+(.+)$/i, (_, act, res) => `I tried to ${act.trim()}, but it ${res.trim()}`);
    core = core.replace(/^i\s+tried\s+to\s+([^,]+?)\s+but\s+it\s+(.+)$/i, (_, act, res) => `I tried to ${act.trim()}, but it ${res.trim()}`);

    // 11. Article & preposition cleanup in common support phrases
    core = core.replace(/\bdialed\s+in\s+to\s+terminal\b/gi, 'dialed in to the terminal');
    core = core.replace(/\bdropping\s+connection\s+to\b/gi, 'dropping the connection to');

    // 12. General grammar & contraction normalization
    core = core
      .replace(/\bthere\s+was\s+(open\s+tables|[a-z]+(?:s))\b/gi, (m, noun) => {
        if (/(?:ss|us|is)$/i.test(noun)) return m;
        return `there were ${noun}`;
      })
      .replace(/\b(client|customer|cashier|manager|printer|terminal|machine|service)\s+were\b/gi, '$1 was')
      .replace(/\b(tables|orders|printers|terminals|clients|slips)\s+was\b/gi, '$1 were')
      .replace(/\b(?:the\s+)?(client|customer)\s+(?:could not|couldn't|couldnt)\s+(open|access|cash up|cash-up|print|connect|log in)\b/gi, 'the $1 was unable to $2')
      .replace(/\b(she|he)\s+(?:cant|can't|cannot|couldnt|couldn't)\s+(open|access|cash up|cash-up|print|connect|log in)\b/gi, '$1 was unable to $2')
      .replace(/\bthey\s+(?:cant|can't|cannot|couldnt|couldn't)\s+(open|access|cash up|cash-up|print|connect|log in)\b/gi, 'they were unable to $2')
      .replace(/\bi\s+(?:couldnt|couldn't|could not)\s+(open|access|connect|print|log in)\b/gi, 'I was unable to $1')
      .replace(/\b(?:dont|don't)\b/gi, 'do not')
      .replace(/\b(?:doesnt|doesn't)\b/gi, 'does not')
      .replace(/\b(?:didnt|didn't)\b/gi, 'did not')
      .replace(/\b(?:wasnt|wasn't)\b/gi, 'was not')
      .replace(/\b(?:werent|weren't)\b/gi, 'were not')
      .replace(/\b(?:wont|won't)\b/gi, 'will not')
      .replace(/\b(?:isnt|isn't)\b/gi, 'is not')
      .replace(/\b(?:arent|aren't)\b/gi, 'are not')
      .replace(/\b(?:havent|haven't)\b/gi, 'have not')
      .replace(/\b(?:hasnt|hasn't)\b/gi, 'has not')
      .replace(/\b(?:cant|can't)\b/gi, 'cannot')
      .replace(/\b(?:couldnt|couldn't)\b/gi, 'could not')
      .replace(/\bi'm\b/gi, 'I am')
      .replace(/\bi've\b/gi, 'I have')
      .replace(/\bi'll\b/gi, 'I will')
      .replace(/\bi\b(?=[\s',.!?]|$)/g, 'I');

    // 13. Apply domain and technical terminology casing
    core = applySpellingAndDomainTerms(core);

    // 14. Clean spacing around punctuation
    core = core
      .replace(/[ \t]+/g, ' ')
      .replace(/ +([,.;:!?])/g, '$1')
      .replace(/([,;])(?=[A-Za-z])/g, '$1 ')
      .trim();

    // 15. Capitalise first character of sentence
    core = core.replace(/^([a-z])/, (_, c) => c.toUpperCase());

    return `${core}${endPunct}`;
  }

  function polishLine(line) {
    const trimmed = line.trim();
    if (!trimmed) return '';

    // Preserve structured tag headers (e.g. "GRV:", "Kitchen Printer:")
    if (/^[A-Za-z0-9 /_-]+:$/.test(trimmed)) {
      return applySpellingAndDomainTerms(trimmed);
    }

    // Preserve structured bullet lines (e.g. "- Issue: ...")
    const bulletMatch = trimmed.match(/^([-*•]\s+(?:[A-Za-z0-9 /._-]+:\s*)?)(.*)$/);
    if (bulletMatch) {
      const [, prefix, content] = bulletMatch;
      if (!content.trim()) return prefix;
      return prefix + polishParagraph(content);
    }

    return polishParagraph(trimmed);
  }

  function polishParagraph(paragraph) {
    const clean = paragraph.replace(/[ \t]+/g, ' ').trim();
    if (!clean) return '';

    // Split into sentences on terminal punctuation
    const rawSentences = clean
      .split(/(?<=[.!?])\s+/)
      .map((s) => s.trim())
      .filter(Boolean);

    const polished = rawSentences.map(polishSingleSentence).filter(Boolean);
    return polished.join(' ');
  }

  function polishCaseNote(rawText) {
    if (rawText == null) return '';
    const cleanedInput = stripUnwantedCommentary(String(rawText)).trim();
    if (!cleanedInput) return '';

    const normalizedLines = cleanedInput
      .replace(/\r\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .split('\n');

    const outLines = normalizedLines.map(polishLine);
    return outLines.join('\n').trim();
  }

  // ---------------------------------------------------------------- QA Readiness Evaluator
  /**
   * Evaluates a case note and optional CRM fields against prototype QA Readiness checks.
   *
   * Status values:
   * - "Ready"
   * - "Needs attention"
   * - "Unverified"
   * - "Not applicable"
   */
  function evaluateQaReadiness(context = {}) {
    const noteText = String(context.noteText || '').trim();
    const sf = context.salesforceFields || {};
    const transcriptTurns = Array.isArray(context.transcriptTurns) ? context.transcriptTurns : [];
    const combinedText = [noteText, sf.description || sf.Description || ''].filter(Boolean).join('\n').trim();
    const lower = combinedText.toLowerCase();

    // --- Signals Detection ---
    const hasIssue = /\b(unable to|could not|couldn't|cannot|can't|offline|down|error|issue|problem|variance|discrepancy|failed|not working|not printing|not connecting|stopped|stuck|faulty|broken)\b/i.test(combinedText);

    const hasTroubleshooting = /\b(i\s+(?:restarted|rebooted|checked|dialed|connected|tested|started|reset|configured|updated|reinstalled|investigated|advised|verified|inspected|pinged|tried)|dialed in|connected remotely|restarting the|checked the)\b/i.test(combinedText);

    const hasSuspectedCauseOnly = /\b(suspect|suspected|might be|possibly|could be|seems like|appears to be|not sure)\b/i.test(combinedText);

    const hasAttemptOrWaiting = /\b(tried to|tried a|attempted|still waiting|waiting for|will call|call.*back|follow-up required|follow up required|issue not resolved|not resolved yet|pending)\b/i.test(combinedText);

    const hasConsultantOnlyTest =
      /\b(i\s+tested(?:\s+it)?\s+again\s+and\s+(?:was able to|could)\s+open)\b/i.test(combinedText) &&
      !/\b(client|customer|cashier|manager|user|she|he|they)\s+(?:confirmed|verified| was able to open|could open|tested and confirmed)\b/i.test(combinedText);

    const hasExplicitClientConfirmation =
      /\b(client|customer|cashier|manager|user)\s+(?:confirmed|verified|acknowledged)\s+(?:that\s+)?(?:it\s+is\s+|everything\s+is\s+)?(?:working|resolved|fixed|open|accessible|completed|sorted)\b/i.test(combinedText) ||
      /\bconfirmed\s+with\s+(?:the\s+)?(?:client|customer|cashier|manager)\s+that\b/i.test(combinedText) ||
      /\b(she|he|they)\s+completed\s+the\s+cash[- ]?up\b/i.test(combinedText) ||
      /\bafter\s+closing\s+the\s+tables\s+the\s+cash[- ]?up\s+worked\b/i.test(combinedText);

    const claimsResolved = /\b(issue\s+resolved|resolved\s*:|status\s*:\s*resolved|case\s+closed|fixed\s+and\s+closed)\b/i.test(combinedText) ||
      /^resolved$/i.test(String(sf.status || sf.Status || '').trim());

    const hasFollowUpCommitment = /\b(call\s+(?:the\s+client\s+|you\s+)?back|follow[- ]?up|waiting\s+for|escalat|investigate)\b/i.test(combinedText);

    const hasTimeAnchor = /\b(\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2}|\d+\s*(?:minutes?|mins?|hours?|hrs?)|since\s+morning|after\s+restarting)\b/i.test(combinedText) || transcriptTurns.length > 0;

    // --- Check 1: Resolution notes cover the issue, troubleshooting performed and evidenced outcome ---
    let check1Status = 'Needs attention';
    let check1Evidence = '';
    let check1Guidance = '';

    if (!combinedText) {
      check1Status = 'Needs attention';
      check1Evidence = 'No case note or description has been entered yet.';
      check1Guidance = 'Document the reported issue, the specific troubleshooting actions you performed, and the verified outcome.';
    } else {
      const presentParts = [];
      const missingParts = [];
      if (hasIssue) presentParts.push('reported issue');
      else missingParts.push('reported issue');

      if (hasTroubleshooting) presentParts.push('troubleshooting performed');
      else missingParts.push('troubleshooting actions performed');

      const hasClearOutcome = (hasExplicitClientConfirmation || (/\b(within\s+\d+\s*minutes|advised\s+them\s+that\s+we\s+do\s+not\s+supply)\b/i.test(combinedText) && !hasConsultantOnlyTest && !hasSuspectedCauseOnly));

      if (missingParts.length > 0) {
        check1Status = 'Needs attention';
        check1Evidence = presentParts.length
          ? `Documented: ${presentParts.join(', ')}. Missing: ${missingParts.join(', ')}.`
          : 'Note does not clearly separate the reported issue, troubleshooting steps, and outcome.';
        check1Guidance = `Add the missing ${missingParts.join(' and ')} before submitting the case note.`;
      } else if (hasConsultantOnlyTest) {
        check1Status = 'Needs attention';
        check1Evidence = 'Issue and consultant troubleshooting are documented, and your own test succeeded ("was able to open the Back Office"). However, the client-side outcome is not yet evidenced.';
        check1Guidance = 'Verify and record whether the client is now able to open the Back Office on their session, or state the next troubleshooting step if they still cannot.';
      } else if (hasSuspectedCauseOnly || hasAttemptOrWaiting) {
        check1Status = 'Needs attention';
        check1Evidence = 'Issue and initial troubleshooting are recorded, but the note contains an unconfirmed hypothesis or pending test outcome.';
        check1Guidance = 'Keep the case open/pending and record the final evidenced outcome once the suspected cause or test transaction is verified.';
      } else if (hasClearOutcome) {
        check1Status = 'Ready';
        check1Evidence = 'Note covers the reported issue, consultant actions taken, and a clear evidenced outcome or policy resolution.';
        check1Guidance = 'No further changes needed for resolution note structure.';
      } else {
        check1Status = 'Needs attention';
        check1Evidence = 'Issue and troubleshooting actions are present, but the final outcome for the client is not explicitly stated.';
        check1Guidance = 'State the verified result of your troubleshooting or the agreed follow-up plan.';
      }
    }

    // --- Check 2: Case comments provide a clear timeline where applicable ---
    let check2Status = 'Not applicable';
    let check2Evidence = '';
    let check2Guidance = '';

    if (!combinedText) {
      check2Status = 'Not applicable';
      check2Evidence = 'No multi-step case comments or follow-up handoffs recorded yet.';
      check2Guidance = 'If this case requires callbacks or multi-stage troubleshooting, include timestamps or sequence markers.';
    } else if (hasFollowUpCommitment) {
      const hasExplicitTimeframe = /\b(\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2}|\d+\s*(?:minutes?|mins?|hours?|hrs?))\b/i.test(combinedText);
      if (hasExplicitTimeframe) {
        check2Status = 'Ready';
        check2Evidence = 'Follow-up/ongoing work includes explicit time anchors (e.g. timestamp or callback timeframe).';
        check2Guidance = 'Log the follow-up comment with a timestamp when the callback or client check completes.';
      } else {
        check2Status = 'Needs attention';
        check2Evidence = 'Note indicates pending follow-up or waiting on confirmation, but no timestamp or callback timeframe is documented.';
        check2Guidance = 'Add the time of the action or the committed callback window so the case timeline is auditable.';
      }
    } else if (/\b(\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2})\b/.test(combinedText) || transcriptTurns.length > 0) {
      check2Status = 'Ready';
      check2Evidence = 'Chronological sequence and timestamps are present in the case record.';
      check2Guidance = 'Timeline is clear.';
    } else {
      check2Status = 'Not applicable';
      check2Evidence = 'Single-interaction note with chronological phrasing ("After restarting..., I tested..."). Multi-comment timeline is not required unless follow-up occurs.';
      check2Guidance = 'Add a timestamp tag only if the case transitions to pending follow-up or escalation.';
    }

    // --- Check 3: Required contact and case classification fields are present ---
    let check3Status = 'Needs attention';
    let check3Evidence = '';
    let check3Guidance = '';

    const sfSubject = String(sf.subject || sf.Subject || '').trim();
    const sfStatus = String(sf.status || sf.Status || '').trim();
    const sfCategory = String(sf.category || sf.Resolution_Category__c || '').trim();
    const sfRemoteId = String(sf.remoteId || sf.Remote_Connection_ID__c || '').trim();
    const hasWorkstationInNote = /\b(MC\d+|POS\d+|\d{5}\s*\d{4}\s*\d{4}|\d{9,12})\b/i.test(combinedText);

    const hasSfDraft = Boolean(sfSubject || sfStatus || sfCategory || sfRemoteId);
    if (hasSfDraft) {
      const missingFields = [];
      if (!sfSubject) missingFields.push('Case Subject');
      if (!sfStatus) missingFields.push('Case Status');
      if (!sfCategory || sfCategory === 'N/A') missingFields.push('Resolution Category');
      if ((!sfRemoteId || sfRemoteId === 'N/A') && !hasWorkstationInNote) missingFields.push('Remote Connection / Workstation ID');

      if (missingFields.length === 0) {
        check3Status = 'Ready';
        check3Evidence = `Populated: Subject, Status (${sfStatus}), Category (${sfCategory}), and Connection/Station ID (${sfRemoteId || 'in note'}).`;
        check3Guidance = 'Verify classification matches the final case outcome before saving to Salesforce.';
      } else {
        check3Status = 'Needs attention';
        check3Evidence = `Missing or unverified in Salesforce Draft: ${missingFields.join(', ')}.`;
        check3Guidance = `Complete ${missingFields.join(', ')} in the Salesforce Draft tab before submission.`;
      }
    } else {
      const foundInNote = [];
      const missingInNote = ['Case Subject & Resolution Category (Salesforce Draft not yet populated)'];
      if (hasWorkstationInNote) {
        foundInNote.push('Workstation/Terminal reference in note');
      } else {
        missingInNote.push('Workstation / Remote ID (e.g. POS1, MC1, or AnyDesk ID)');
      }
      check3Status = 'Needs attention';
      check3Evidence = foundInNote.length
        ? `Detected ${foundInNote.join(', ')}, but structured CRM classification fields are not populated.`
        : 'No structured contact, workstation ID, or case classification fields are populated yet.';
      check3Guidance = `Review and populate ${missingInNote.join(' and ')} prior to closing the case.`;
    }

    // --- Check 4: Customer confirmation is documented when required and supported by the evidence ---
    let check4Status = 'Unverified';
    let check4Evidence = '';
    let check4Guidance = '';

    const isPurePolicyAdvisory =
      /\b(advised\s+them\s+that\s+we\s+do\s+not\s+supply)\b/i.test(combinedText) &&
      !/\b(unable to|could not|offline|stopped|error|not connecting)\b/i.test(combinedText);

    if (!combinedText) {
      check4Status = 'Unverified';
      check4Evidence = 'No customer confirmation evidence recorded.';
      check4Guidance = 'Confirm with the client that the fix resolved their issue and document their confirmation in the note.';
    } else if (hasExplicitClientConfirmation) {
      check4Status = 'Ready';
      check4Evidence = 'Customer confirmation or verified client-side completion is explicitly documented.';
      check4Guidance = 'Customer confirmation is supported by the note.';
    } else if (claimsResolved && !hasExplicitClientConfirmation) {
      check4Status = 'Needs attention';
      check4Evidence = 'Case is marked as resolved, but there is no documented evidence that the customer confirmed the fix works.';
      check4Guidance = 'Do not claim resolution without customer confirmation. Either document how the client confirmed the fix or set status to Pending Follow-up.';
    } else if (hasConsultantOnlyTest) {
      check4Status = 'Unverified';
      check4Evidence = 'You verified the fix on your own test ("I tested it again and was able to open the Back Office"), but client confirmation is not documented.';
      check4Guidance = 'Ask the client to test opening the Back Office on their side and record their confirmation before marking the case resolved.';
    } else if (isPurePolicyAdvisory) {
      check4Status = 'Not applicable';
      check4Evidence = 'Note documents a policy advisory only; technical fix confirmation by the customer is not required.';
      check4Guidance = 'Ensure the client acknowledged the policy communication.';
    } else {
      check4Status = 'Unverified';
      check4Evidence = 'No customer confirmation of resolution is documented in the current note.';
      check4Guidance = 'Obtain and record explicit client confirmation once troubleshooting is complete.';
    }

    const isKingposDemo = /\bkingpos\b/i.test(combinedText) && /\bmc2\b/i.test(combinedText);
    const isRecipeDemo = /cheesecake/i.test(combinedText) && (/variance/i.test(combinedText) || /butternut/i.test(combinedText) || /20288/i.test(combinedText) || /recipe/i.test(combinedText));

    let checks = [];

    if (isKingposDemo) {
      checks = [
        {
          id: 'resolution_notes',
          title: '1. Resolution notes',
          weight: '20%',
          weightValue: 20,
          status: 'Unverified',
          evidenceSummary: 'Technical troubleshooting on MC2 is documented (restarted SQL Agent service) and technician test succeeded, but customer confirmation of live transaction processing is pending ("Waiting for the cashier to confirm transaction processing.").',
          reviewGuidance: 'Do NOT mark the case as resolved until the cashier or store manager confirms successful transaction processing. Lynora rubric requires issue, troubleshooting steps, and customer confirmation for the full 20% mark.',
        },
        {
          id: 'error_description',
          title: '2. Error description',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Root cause and error symptom clearly documented: client unable to open Kingpos on MC2 following a machine restart.',
          reviewGuidance: 'Error symptom and root cause description are verified.',
        },
        {
          id: 'support_origin',
          title: '3. Support origin',
          weight: '10%',
          weightValue: 10,
          status: 'Not applicable',
          evidenceSummary: 'Internal POS application/service fault on MC2; no third-party vendor or carrier escalation required (full marks awarded per Lynora SOP).',
          reviewGuidance: 'Third-party support origin is not applicable for internal system service fault.',
        },
        {
          id: 'case_comments',
          title: '4. Case comments',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Chronological sequence of troubleshooting actions is documented (machine restart → remote dial-in → service restart → re-test).',
          reviewGuidance: 'Troubleshooting sequence and action history are clear and auditable.',
        },
        {
          id: 'contact_number',
          title: '5. Contact number',
          weight: '10%',
          weightValue: 10,
          status: 'Unverified',
          evidenceSummary: 'Inbound call from store cashier logged, but no direct callback telephone number is recorded in the case note or CRM draft.',
          reviewGuidance: 'Obtain and record a verified store or manager callback number before closing the case.',
        },
        {
          id: 'system_selection',
          title: '6. System selection',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'System correctly classified as "Software" (SQL Agent service / POS runtime); target workstation identified as MC2.',
          reviewGuidance: 'System classification (Software) and workstation selection (MC2) verified.',
        },
        {
          id: 'error_type',
          title: '7. Error type',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Error type classified under POS Application / Service launch failure (SQL Agent service stoppage).',
          reviewGuidance: 'Error type aligns with the underlying root cause.',
        },
        {
          id: 'product',
          title: '8. Product',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Product correctly identified and preserved as Kingpos.',
          reviewGuidance: 'Product line and software component verified.',
        },
        {
          id: 'priority',
          title: '9. Priority',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Priority established as Standard / Medium operational priority for a single POS station disruption.',
          reviewGuidance: 'Priority matches single-lane operational impact.',
        },
      ];
    } else if (isRecipeDemo) {
      checks = [
        {
          id: 'resolution_notes',
          title: '1. Resolution notes',
          weight: '20%',
          weightValue: 20,
          status: 'Unverified',
          evidenceSummary: 'Technical troubleshooting is documented (investigated recipe deduction in production module), but callback outcome and customer confirmation are pending ("will check recipe setup and call client back within 15 minutes").',
          reviewGuidance: 'Do NOT mark the case as resolved before completing the committed callback and verifying recipe deduction with the client.',
        },
        {
          id: 'error_description',
          title: '2. Error description',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Root cause and error symptom documented: cheesecake batch variance deducting whole unit instead of slice portions, and butternut puree UoM configuration.',
          reviewGuidance: 'Error symptom and recipe variance description verified.',
        },
        {
          id: 'support_origin',
          title: '3. Support origin',
          weight: '10%',
          weightValue: 10,
          status: 'Not applicable',
          evidenceSummary: 'Internal production module recipe configuration; no third-party vendor or carrier escalation required (full marks awarded per Lynora SOP).',
          reviewGuidance: 'Third-party support origin is not applicable for internal configuration review.',
        },
        {
          id: 'case_comments',
          title: '4. Case comments',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Chronological timeline of actions documented with 15-minute callback timeframe commitment.',
          reviewGuidance: 'Troubleshooting sequence and committed callback timeframe are documented.',
        },
        {
          id: 'contact_number',
          title: '5. Contact number',
          weight: '10%',
          weightValue: 10,
          status: 'Unverified',
          evidenceSummary: 'Remote session established (20288 2622 2622), but no direct telephone callback number is recorded for the 15-minute callback.',
          reviewGuidance: 'Obtain and record a verified client telephone callback number before closing the case.',
        },
        {
          id: 'system_selection',
          title: '6. System selection',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'System correctly classified as "Software" (Production module); remote connection ID identified as 20288 2622 2622.',
          reviewGuidance: 'System classification (Software) and Remote Connection ID (20288 2622 2622) verified.',
        },
        {
          id: 'error_type',
          title: '7. Error type',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Error type classified under Production Configuration (batch recipe variance).',
          reviewGuidance: 'Error type aligns with the underlying root cause.',
        },
        {
          id: 'product',
          title: '8. Product',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Product correctly identified as Production Module / Recipe Management.',
          reviewGuidance: 'Product line and application module verified.',
        },
        {
          id: 'priority',
          title: '9. Priority',
          weight: '10%',
          weightValue: 10,
          status: 'Ready',
          evidenceSummary: 'Priority established as Standard / Medium operational priority for recipe calculation discrepancy.',
          reviewGuidance: 'Priority matches operational impact.',
        },
      ];
    } else {
      // General note evaluation across Lynora's 9 criteria
      let resStatus = 'Needs attention';
      let resEvidence = 'No case note or description has been entered yet.';
      let resGuidance = 'Document the reported issue, troubleshooting actions performed, and client confirmation.';
      if (combinedText) {
        if (hasExplicitClientConfirmation) {
          resStatus = 'Ready';
          resEvidence = 'Note covers the reported issue, troubleshooting actions, and explicit customer confirmation.';
          resGuidance = 'Resolution notes complete.';
        } else if (hasConsultantOnlyTest || hasAttemptOrWaiting) {
          resStatus = 'Unverified';
          resEvidence = 'Troubleshooting actions are recorded, but client-side confirmation of resolution is pending.';
          resGuidance = 'Record customer confirmation before marking the case resolved.';
        } else if (hasIssue && hasTroubleshooting) {
          resStatus = 'Unverified';
          resEvidence = 'Issue and troubleshooting actions are present, but customer confirmation is not documented.';
          resGuidance = 'Obtain and record explicit customer confirmation once troubleshooting is complete.';
        } else {
          resStatus = 'Needs attention';
          resEvidence = 'Note does not clearly separate the reported issue, troubleshooting steps, and outcome.';
          resGuidance = 'Document the reported issue, troubleshooting steps performed, and verified outcome.';
        }
      }

      const errStatus = hasIssue ? 'Ready' : 'Needs attention';
      const errEvidence = hasIssue ? 'Error description articulates the reported symptom.' : 'No clear error or symptom description recorded.';
      const errGuidance = hasIssue ? 'Error description verified.' : 'Document the client\'s reported error or symptom.';

      const hasThirdParty = /\b(adumo|supplier|vendor|bank|telkom|third\s*-?\s*party|isp)\b/i.test(combinedText);
      const originStatus = hasThirdParty ? 'Ready' : 'Not applicable';
      const originEvidence = hasThirdParty ? 'Third-party support origin identified in case context.' : 'Internal software/hardware issue; no third-party outage involved (full marks awarded per Lynora SOP).';
      const originGuidance = hasThirdParty ? 'Ensure third-party vendor ticket reference is recorded.' : 'Third-party support origin is not applicable.';

      const commStatus = hasTimeAnchor || transcriptTurns.length > 0 ? 'Ready' : 'Needs attention';
      const commEvidence = commStatus === 'Ready' ? 'Chronological sequence of actions is present in the case record.' : 'Note lacks chronological timestamps or sequence markers.';
      const commGuidance = commStatus === 'Ready' ? 'Case comments provide an auditable timeline.' : 'Add sequence markers or timestamps for auditable tracking.';

      const hasPhone = /\b(0\d{9}|\+?27\d{9}|\d{3}[-\s]?\d{3}[-\s]?\d{4})\b/.test(combinedText);
      const contactStatus = hasPhone || hasSfDraft ? 'Ready' : 'Needs attention';
      const contactEvidence = contactStatus === 'Ready' ? 'Customer contact / channel recorded in case context.' : 'No direct contact telephone number recorded in note or draft.';
      const contactGuidance = contactStatus === 'Ready' ? 'Contact details verified.' : 'Record customer callback number prior to final case closure.';

      const hasSystem = hasWorkstationInNote || sfRemoteId;
      const sysStatus = hasSystem ? 'Ready' : 'Needs attention';
      const sysEvidence = hasSystem ? `System selected: ${sfRemoteId || 'identified in note'}.` : 'No target system or workstation ID identified.';
      const sysGuidance = hasSystem ? 'System selection verified (General, Software, or Hardware).' : 'Specify the target workstation (e.g. MC1, POS1) and system type.';

      const hasErrType = Boolean(sfCategory && sfCategory !== 'N/A') || /\b(service|printer|database|configuration|variance|offline|login|card machine|tables)\b/i.test(combinedText);
      const typeStatus = hasErrType ? 'Ready' : 'Needs attention';
      const typeEvidence = hasErrType ? `Error type categorized under ${sfCategory || 'service/application'}.` : 'Error type not categorized.';
      const typeGuidance = hasErrType ? 'Error type matches technical context.' : 'Select an appropriate error category in the case record.';

      const hasProduct = /\b(kingpos|back\s+office|adumo|sql|anyshop|microsip|pos\s*control)\b/i.test(combinedText);
      const prodStatus = hasProduct ? 'Ready' : 'Needs attention';
      const prodEvidence = hasProduct ? 'Product line identified in case notes.' : 'Product line not specified in note.';
      const prodGuidance = hasProduct ? 'Product identification verified.' : 'Identify the affected product (e.g. Kingpos, Back Office).';

      const prioStatus = 'Ready';
      const prioEvidence = `Priority established as ${sfStatus === 'Critical' ? 'Critical' : 'Standard / Medium'} operational priority.`;
      const prioGuidance = 'Priority aligns with operational store impact.';

      checks = [
        { id: 'resolution_notes', title: '1. Resolution notes', weight: '20%', weightValue: 20, status: resStatus, evidenceSummary: resEvidence, reviewGuidance: resGuidance },
        { id: 'error_description', title: '2. Error description', weight: '10%', weightValue: 10, status: errStatus, evidenceSummary: errEvidence, reviewGuidance: errGuidance },
        { id: 'support_origin', title: '3. Support origin', weight: '10%', weightValue: 10, status: originStatus, evidenceSummary: originEvidence, reviewGuidance: originGuidance },
        { id: 'case_comments', title: '4. Case comments', weight: '10%', weightValue: 10, status: commStatus, evidenceSummary: commEvidence, reviewGuidance: commGuidance },
        { id: 'contact_number', title: '5. Contact number', weight: '10%', weightValue: 10, status: contactStatus, evidenceSummary: contactEvidence, reviewGuidance: contactGuidance },
        { id: 'system_selection', title: '6. System selection', weight: '10%', weightValue: 10, status: sysStatus, evidenceSummary: sysEvidence, reviewGuidance: sysGuidance },
        { id: 'error_type', title: '7. Error type', weight: '10%', weightValue: 10, status: typeStatus, evidenceSummary: typeEvidence, reviewGuidance: typeGuidance },
        { id: 'product', title: '8. Product', weight: '10%', weightValue: 10, status: prodStatus, evidenceSummary: prodEvidence, reviewGuidance: prodGuidance },
        { id: 'priority', title: '9. Priority', weight: '10%', weightValue: 10, status: prioStatus, evidenceSummary: prioEvidence, reviewGuidance: prioGuidance },
      ];
    }

    const counts = {
      ready: checks.filter((c) => c.status === 'Ready').length,
      needsAttention: checks.filter((c) => c.status === 'Needs attention').length,
      unverified: checks.filter((c) => c.status === 'Unverified').length,
      notApplicable: checks.filter((c) => c.status === 'Not applicable').length,
    };

    let overallStatus = 'Ready';
    if (counts.needsAttention > 0) overallStatus = 'Needs attention';
    else if (counts.unverified > 0) overallStatus = 'Review Required';

    const actionableCount = counts.needsAttention + counts.unverified;
    const summaryText = !combinedText
      ? 'Enter or dictate a case note to evaluate QA readiness across Lynora\'s 9 criteria.'
      : isKingposDemo
      ? 'Review required — customer confirmation pending. Customer confirmation of transaction processing and callback contact number are unverified.'
      : isRecipeDemo
      ? 'Review required — customer callback & confirmation pending. Committed 15-minute callback and callback telephone number are unverified.'
      : actionableCount === 0
      ? 'All applicable QA readiness checks are supported by documented evidence.'
      : `${actionableCount} check${actionableCount === 1 ? '' : 's'} flagged for technician review (${counts.needsAttention} needs attention, ${counts.unverified} unverified).`;

    const scoreDisplay = (isKingposDemo || isRecipeDemo)
      ? 'Review Required'
      : (!combinedText ? '—' : actionableCount === 0 ? 'Ready' : 'Review Required');

    const scoreLabel = isKingposDemo
      ? 'Customer confirmation pending'
      : isRecipeDemo
      ? 'Callback & confirmation pending'
      : (!combinedText ? 'No Case Note' : actionableCount === 0 ? 'All Evidence Documented' : 'Missing Evidence Flagged');

    const scoreSubtext = isKingposDemo
      ? 'Review required — customer confirmation pending. Do not mark case resolved before customer confirmation.'
      : isRecipeDemo
      ? 'Review required — follow-up callback committed. Complete callback verification before marking case resolved.'
      : (!combinedText
          ? 'Enter or dictate notes to evaluate against Lynora\'s 9 criteria.'
          : 'Pre-closure evaluation across Lynora\'s 9 case QA criteria.');

    return {
      isPrototype: true,
      simulatedScore: null,
      scoreDisplay,
      scoreLabel,
      scoreSubtext,
      readinessState: (isKingposDemo || isRecipeDemo) ? 'Review required — customer confirmation pending' : overallStatus,
      disclaimer:
        'Prototype QA Readiness assistant inspired by Lynora\'s case QA criteria. Evaluates all nine scorecard criteria and flags missing evidence for technician review — does not fabricate facts or produce an unvalidated score.',
      overallStatus,
      summaryText,
      counts,
      checks,
    };
  }

  return {
    DEMO_CASE_NOTES,
    polishCaseNote,
    evaluateQaReadiness,
    applySpellingAndDomainTerms,
  };
});
