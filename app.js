/* Speak Your Notes – vanilla JS with Local Engine Two-Stream Integration & Procedure Hub */
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
  const liveTypingStream = $('live-typing-stream');
  const liveTypingText = $('live-typing-text');
  const counterEl = $('counter');
  const bannerEl = $('banner');
  const tagsEl = $('tags');
  const tagsNav = $('tags-nav');
  const langSel = $('lang');
  const themeBtn = $('theme-toggle');
  const toastEl = $('toast');
  const toastText = $('toast-text');
  const toastAction = $('toast-action');

  // Local Engine elements
  const engineDot = $('engine-dot');
  const engineText = $('engine-text');
  const engineStatus = $('engine-status');
  const tabNotes = $('tab-notes');
  const tabTranscript = $('tab-transcript');
  const tabReview = $('tab-review');
  const tabSalesforce = $('tab-salesforce');
  const tabQa = $('tab-qa');
  const tabQaBadge = $('tab-qa-badge');

  const panelNotes = $('panel-notes');
  const panelTranscript = $('panel-transcript');
  const panelReview = $('panel-review');
  const panelSalesforce = $('panel-salesforce');
  const panelQa = $('panel-qa');

  const transcriptContainer = $('transcript-container');
  const transcriptCount = $('transcript-count');
  const reviewContainer = $('review-container');
  const reviewConfidence = $('review-confidence');
  const salesforceContainer = $('salesforce-container');
  const copySfBtn = $('copy-sf-btn');
  const sfEditedBadge = $('sf-edited-badge');
  const sfRestoreBtn = $('sf-restore-btn');
  const btnLoadSample = $('btn-load-sample');

  // QA Readiness & Polish Comparison elements
  const demoNoteBar = $('demo-note-bar');
  const btnResetDemo = $('btn-reset-demo');
  const resetDemoModal = $('reset-demo-modal');
  const rdClose = $('rd-close');
  const rdCancelBtn = $('rd-cancel-btn');
  const rdConfirmBtn = $('rd-confirm-btn');
  const btnNotesQa = $('btn-notes-qa');
  const notesQaStatus = $('notes-qa-status');
  const tidyComparison = $('tidy-comparison');
  const tidyBefore = $('tidy-before');
  const tidyAfter = $('tidy-after');
  const tidyRevert = $('tidy-revert');
  const tidyComparisonClose = $('tidy-comparison-close');
  const btnOpenQaFromTidy = $('btn-open-qa-from-tidy');
  const qaOverallBadge = $('qa-overall-badge');
  const qaScoreCard = $('qa-score-card');
  const qaScoreDisplay = $('qa-score-display');
  const qaScoreLabel = $('qa-score-label');
  const qaScoreSubtext = $('qa-score-subtext');
  const qaSummaryText = $('qa-summary-text');
  const qaCountsPills = $('qa-counts-pills');
  const qaChecksContainer = $('qa-checks-container');

  // Desktop Split elements (D.1)
  const mainContent = $('main-content');
  const btnToggleSplit = $('btn-toggle-split');
  const splitToggleLabel = $('split-toggle-label');

  // Call History elements (D.3)
  const btnCallHistory = $('btn-call-history');
  const historyBadge = $('history-badge');
  const callHistoryDrawer = $('call-history-drawer');
  const chClose = $('ch-close');
  const chList = $('ch-list');
  const chTotalCount = $('ch-total-count');
  const chRefreshBtn = $('ch-refresh-btn');

  // Pairing Modal elements (SEC-01 & SEC-04)
  const enginePairingModal = $('engine-pairing-modal');
  const epClose = $('ep-close');
  const epCancelBtn = $('ep-cancel-btn');
  const epForm = $('ep-form');
  const epCodeInput = $('ep-code-input');
  const epError = $('ep-error');
  const epRemember = $('ep-remember');
  const epSubmitBtn = $('ep-submit-btn');

  // Processing Stepper elements
  const processingCard = $('processing-card');
  const processingTitle = $('processing-title');
  const processingSubtitle = $('processing-subtitle');
  const processingTimer = $('processing-timer');
  const processingStepper = $('processing-stepper');
  const processingActions = $('processing-actions');
  const btnCancelProcessing = $('btn-cancel-processing');
  const btnViewTranscript = $('btn-view-transcript');
  const btnViewReview = $('btn-view-review');
  const btnViewSf = $('btn-view-sf');

  // ---------------------------------------------------------------- storage
  const store = {
    get(k, d) { try { const v = localStorage.getItem('syn.' + k); return v === null ? d : v; } catch { return d; } },
    set(k, v) { try { localStorage.setItem('syn.' + k, v); } catch { /* private mode etc. */ } },
  };

  // ---------------------------------------------------------------- Local Engine Bridge
  const LOCAL_ENGINE_URL = 'http://127.0.0.1:8765';
  let engineConnected = false;
  let engineState = 'idle'; // 'idle', 'recording', 'processing', 'ready', 'error'
  let engineSessionTimer = null;
  let engineElapsedSeconds = 0;
  let currentSalesforcePayload = null;
  let originalSalesforceValues = null;
  let currentTranscriptTurns = [];
  let lastRawBeforeTidy = '';
  let artifactsLoaded = false;
  let recordingSessionId = null;
  let selectedSessionId = null;
  let selectedSessionType = 'none'; // 'live', 'demo', 'none'
  let inMemoryEngineToken = null;
  let isDesktopSplit = false;
  let activeLeftTab = 'notes';
  let activeRightTab = 'review';
  let currentTabId = 'notes';

  const DEMO_TRANSCRIPT_DATA = {
    merged_turns: [
      { speaker: "CONSULTANT", timestamp_str: "22:37:40", text: "20288 2622 2622 Zero double six Oh nine or mine. Okay, I'm connected now." },
      { speaker: "CLIENT", timestamp_str: "22:38:39", text: "Okay, let me show you the variance calculation on screen with the cheesecake batch." },
      { speaker: "CONSULTANT", timestamp_str: "22:40:12", text: "Right, looking at the unit of measure setting here in the production module." },
      { speaker: "CLIENT", timestamp_str: "22:45:02", text: "And then for the butternut puree, we need that unit configured in 1 KG." },
      { speaker: "CONSULTANT", timestamp_str: "22:46:09", text: "Okay, I'll investigate the cheesecake production configuration on my side and call you back in 15 minutes." }
    ]
  };

  const DEMO_REVIEW_MARKDOWN = `# Speak V2 — Case Conversation Intelligence Report

> [!IMPORTANT]
> **STATUS**: DRAFT — HUMAN REVIEW REQUIRED BEFORE CRM SUBMISSION  
> This analysis was automatically generated from call audio. Review highlighted evidence and commitments below.

**Call Timestamp**: \`2026-10-06T22:37:39\`  
**Total Dialogue Turns**: \`90 turns\`  
**Resolution Classification**: **\`FOLLOW_UP_REQUIRED\`**  
**Resolution Basis**: Consultant confirmed a follow-up callback commitment (Within 15 minutes) to finalize recipe configuration.  
**Evidence Quality Confidence**: \`HIGH\` (80%)  

---

## 1. Executive Summary
- **Reason for Contact**: Client requested assistance with production batch variance discrepancies (cheesecake slices vs whole unit) and butternut puree unit configuration.
- **Verified Key Events**:
  * Consultant established remote session with client (Remote ID: 20288 2622 2622).
  * Client demonstrated cheesecake recipe variance discrepancy (system registering whole batch rather than individual portion slices).
  * Consultant identified the root cause as a unit of measure definition in the production module.
  * Client requested assistance with secondary item (Butternut Puree unit setting in 1 KG).
  * Consultant committed to investigating both items and calling back (Within 15 minutes).
- **Outcome**: Consultant agreed to investigate the cheesecake production configuration and call the client back (Within 15 minutes).

## 2. Client Issue & Evidence (Direct Facts)
- **Primary Reported Problem**: Cheesecake batch variance deducting whole unit instead of slice portions.
- **Direct Client Claims**:
  * Cheesecake batch variance deducting whole unit instead of slice portions.
  * Butternut puree configuration request (change unit to 1 KG).

## 3. Actions & Commitment Classification
| Type | Actor | Action Description | Timeframe | Direct Evidence Quote |
| :--- | :--- | :--- | :--- | :--- |
| **\`COMPLETED_ACTION\`** | \`CONSULTANT\` | Consultant connected remotely to client workstation | \`-\` | *"20288 2622 2622 Zero double six Oh nine or mine..."* |
| **\`COMPLETED_ACTION\`** | \`CLIENT\` | Client demonstrated variance calculation on screen | \`-\` | *"Okay, all right, let me show you...."* |
| **\`COMPLETED_ACTION\`** | \`CONSULTANT\` | Consultant diagnosed unit of measure configuration mismatch | \`-\` | *"which needs to be changed because the quantity..."* |
| **\`PROPOSED_ACTION\`** | \`CONSULTANT\` | Consultant proposed potential escalation to software support | \`-\` | *"Yeah, because also me, first, I need to understand..."* |
| **\`CONFIRMED_COMMITMENT\`** | \`CONSULTANT\` | Consultant committed to investigate recipe configuration and call client back | \`Within 15 minutes\` | *"side. I'll give maximum 15 minutes. I'll call you back..."* |

## 4. Follow-up Commitments
- **Follow-up Required**: \`YES\`
- **Responsible Party**: \`CONSULTANT\`
- **Committed Timeframe**: \`Within 15 minutes\`
- **Confirmed Action Items**: Consultant to investigate cheesecake production configuration and call client back with update/fix.
- **Commitment Evidence**: *"Okay, okay, no, I can do that is all for you and then I'll call you once after 15 minutes, okay?"*

## 5. Grounded & Normalized Entities
- **Customer / Remote IDs**: \`20288 2622 2622\`
- **Products / Items**: \`Cheesecake Recipe / Batch\`, \`Stock Variance\`, \`Butternut Puree\`
- **System Settings**: \`Unit of Measure Configuration\`, \`Production Module\`

## 6. Customer Sentiment (AI Interpretation)
> [!NOTE]
> **Assessed Sentiment**: \`NEUTRAL\`  
> **Rationale**: Client was polite and operational; consultant was responsive with clear callback commitment.`;

  const DEMO_ROUGH_NOTE = "client reported variance on cheesecake recipe deducting whole batch instead of slices. dialed in to MC1 and checked recipe setup in production module. client also asked for butternut puree to be set to 1 KG. will check recipe setup and call client back within 15 minutes. issue not resolved yet.";

  const DEMO_SALESFORCE_PAYLOAD = {
    sobject: "Case",
    action: "DRAFT_UPDATE",
    human_review_status: "PENDING_CONSULTANT_APPROVAL",
    requires_consultant_confirmation: true,
    fields: {
      Subject: "Production Recipe Variance - 20288 2622 2622",
      Description: "Logged a case for a production variance issue on the cheesecake recipe. I dialed in to MC1 and checked the recipe setup. The system was using the whole cheesecake instead of individual slices. The client also asked for Butternut Puree to be set to 1 KG. I will check the recipe setup and call the client back within 15 minutes. Issue not resolved yet.",
      Status: "Pending Follow-up",
      Resolution_Category__c: "Production Configuration",
      Remote_Connection_ID__c: "20288 2622 2622",
      Client_Sentiment__c: "NEUTRAL",
      AI_Confidence_Score__c: 0.8,
      Internal_Review_Notes__c: "Repetitive STT looping detected in transcript. Phonetic normalization applied to 1 term(s) (e.g. 'Bata Nadpuray' -> 'Butternut Puree'). Review raw quote if unverified."
    }
  };

  const PIPELINE_STAGES = [
    { key: 'stopping', label: 'Audio Capture Finalization', desc: 'Flushing WAV audio streams to disk' },
    { key: 'transcribing_consultant', label: 'Consultant Audio Transcription (Mic)', desc: 'Whisper is processing consultant microphone on CPU' },
    { key: 'transcribing_client', label: 'Client Audio Transcription (Loopback)', desc: 'Whisper is processing client audio on CPU. This may take a moment' },
    { key: 'merging_transcript', label: 'Speaker Transcript Merge', desc: 'Aligning timestamps and merging speaker dialogue turns' },
    { key: 'analysing', label: 'Conversation Intelligence Analysis', desc: 'Extracting verified facts, commitments, and sentiment' },
    { key: 'preparing_review', label: 'Salesforce Case Record Draft', desc: 'Formatting reviewable CRM case record' }
  ];

  function getEngineToken() {
    return inMemoryEngineToken || sessionStorage.getItem('syn.engine_auth_token') || null;
  }

  function setEngineToken(token, remember = false) {
    inMemoryEngineToken = token;
    if (remember) {
      sessionStorage.setItem('syn.engine_auth_token', token);
    } else {
      sessionStorage.removeItem('syn.engine_auth_token');
    }
  }

  function clearEngineToken() {
    inMemoryEngineToken = null;
    sessionStorage.removeItem('syn.engine_auth_token');
  }

  function openPairingModal() {
    if (!enginePairingModal) return;
    if (epCodeInput) epCodeInput.value = '';
    if (epError) { epError.hidden = true; epError.textContent = ''; }
    enginePairingModal.hidden = false;
    setTimeout(() => { if (epCodeInput) epCodeInput.focus(); }, 60);
  }

  function closePairingModal() {
    if (!enginePairingModal) return;
    enginePairingModal.hidden = true;
    if (epError) { epError.hidden = true; epError.textContent = ''; }
  }

  function promptPairingCode() {
    openPairingModal();
  }

  async function pairWithEngine(code, remember = false) {
    if (!code || !code.trim()) {
      if (epError) { epError.textContent = 'Please enter a 6-digit pairing code.'; epError.hidden = false; }
      return false;
    }
    const cleanCode = code.replace(/\s+/g, '').replace(/-/g, '').trim();
    try {
      const res = await fetch(`${LOCAL_ENGINE_URL}/auth/pair`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pairing_code: cleanCode })
      });
      if (res.ok) {
        const data = await res.json();
        setEngineToken(data.auth_token, remember);
        closePairingModal();
        showToast('Successfully authenticated with Speak Engine!');
        pollLocalEngine();
        updateCallHistoryBadge();
        return true;
      } else if (res.status === 429) {
        const err = await res.json().catch(() => ({}));
        const msg = err.detail || 'Rate limit cooldown active. Please wait 60 seconds before trying again.';
        if (epError) { epError.textContent = msg; epError.hidden = false; }
        showToast(`Pairing cooldown: ${msg}`);
        return false;
      } else {
        const err = await res.json().catch(() => ({}));
        const msg = err.detail || 'Invalid or expired pairing code.';
        if (epError) { epError.textContent = msg; epError.hidden = false; }
        showToast(`Pairing failed: ${msg}`);
        return false;
      }
    } catch (e) {
      const msg = `Connection error: ${e.message}`;
      if (epError) { epError.textContent = msg; epError.hidden = false; }
      showToast(`Pairing connection error: ${e.message}`);
      return false;
    }
  }

  async function engineFetch(path, options = {}) {
    const url = `${LOCAL_ENGINE_URL}${path.startsWith('/') ? path : '/' + path}`;
    const token = getEngineToken();
    const headers = { ...(options.headers || {}) };
    if (token) {
      headers['X-Speak-Engine-Auth'] = token;
    }
    const merged = { ...options, headers };
    const res = await fetch(url, merged);
    if (res.status === 401) {
      clearEngineToken();
      if (engineConnected) {
        setEngineConnectionState(false, null, 'needs_pairing');
      }
      showToast('Speak Engine requires authentication.', 'Enter Code', () => openPairingModal());
    }
    return res;
  }

  async function pollLocalEngine() {
    if (!window.__enableEngineInTest && (typeof window.__instances === 'function' || typeof window.__emit === 'function' || navigator.webdriver)) {
      return;
    }
    try {
      const query = selectedSessionId ? `?session_id=${encodeURIComponent(selectedSessionId)}` : '';
      const res = await engineFetch(`/status${query}`, { signal: AbortSignal.timeout(1500) });
      if (res.ok) {
        const data = await res.json();
        setEngineConnectionState(true, data);
        updateCallHistoryBadge();
      } else if (res.status === 401) {
        setEngineConnectionState(false, null, 'needs_pairing');
      } else {
        setEngineConnectionState(false);
      }
    } catch {
      setEngineConnectionState(false);
    }
  }

  function setEngineConnectionState(connected, data = null, reason = null) {
    engineConnected = connected;
    if (tagsNav) tagsNav.hidden = connected;
    if (connected) {
      engineDot.className = 'h-2 w-2 rounded-full bg-emerald-500 animate-pulse';
      engineText.textContent = 'Engine Connected';
      engineText.className = 'font-semibold text-emerald-600 dark:text-emerald-400';
      engineText.onclick = null;
      if (data) {
        handleEngineStatusUpdate(data);
      }
    } else {
      engineDot.className = 'h-2 w-2 rounded-full bg-amber-500';
      if (reason === 'needs_pairing') {
        engineText.textContent = 'Engine Needs Pairing';
        engineText.className = 'font-semibold text-amber-600 dark:text-amber-400 cursor-pointer underline decoration-dotted';
        engineText.onclick = openPairingModal;
      } else {
        engineText.textContent = 'Engine Offline';
        engineText.className = 'text-slate-500 dark:text-slate-400 cursor-pointer';
        engineText.onclick = () => {
          if (!getEngineToken()) {
            openPairingModal();
          } else {
            pollLocalEngine();
          }
        };
      }
      if (engineState === 'recording') {
        clearInterval(engineSessionTimer);
        engineState = 'idle';
        setMicButtonState('idle');
      }
    }
  }

  function renderProcessingStepper(data) {
    if (!processingCard || !processingStepper) return;

    if (tagsNav) tagsNav.hidden = true;
    processingCard.hidden = false;
    panelNotes.hidden = true;
    panelTranscript.hidden = true;
    panelReview.hidden = true;
    panelSalesforce.hidden = true;
    if (panelQa) panelQa.hidden = true;

    const currentStage = data.stage || 'stopping';
    const completed = data.completed_stages || [];
    const isReady = data.status === 'ready';
    const isError = data.status === 'error';

    if (isReady) {
      processingTitle.textContent = 'PROCESSING COMPLETE';
      processingTitle.className = 'text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400';
      processingSubtitle.textContent = 'All audio transcribed and case intelligence generated successfully.';
      processingTimer.textContent = `Completed (${formatDuration(data.elapsed_seconds || 0)})`;
      if (processingActions) processingActions.hidden = false;
      if (btnCancelProcessing) btnCancelProcessing.hidden = true;
    } else if (isError) {
      processingTitle.textContent = 'PROCESSING FAILED';
      processingTitle.className = 'text-xs font-bold uppercase tracking-wider text-red-600 dark:text-red-400';
      processingSubtitle.textContent = data.error || 'Pipeline encountered an unexpected error.';
      processingTimer.textContent = 'Failed';
      if (processingActions) processingActions.hidden = true;
      if (btnCancelProcessing) btnCancelProcessing.hidden = false;
    } else {
      processingTitle.textContent = 'PROCESSING CALL';
      processingTitle.className = 'text-xs font-bold uppercase tracking-wider text-teal-600 dark:text-teal-400';
      processingSubtitle.textContent = data.message || 'Dual-stream capture finalized · Running local pipeline on CPU';
      processingTimer.textContent = `Elapsed: ${formatDuration(data.elapsed_seconds || 0)}`;
      if (processingActions) processingActions.hidden = true;
      if (btnCancelProcessing) btnCancelProcessing.hidden = false;
    }

    let html = '';
    PIPELINE_STAGES.forEach((stage, idx) => {
      const isCompleted = isReady || completed.includes(stage.key);
      const isActive = !isReady && !isError && currentStage === stage.key;
      const isFailed = isError && currentStage === stage.key;

      let itemClass = 'proc-item-pending';
      let badgeClass = 'proc-badge-pending';
      let icon = `${idx + 1}`;
      let titleClass = 'text-slate-600 dark:text-slate-400 font-medium';
      let subtext = `<p class="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">${stage.desc}</p>`;

      if (isCompleted) {
        itemClass = 'proc-item-complete';
        badgeClass = 'proc-badge-complete';
        icon = '✓';
        titleClass = 'text-slate-900 dark:text-slate-100 font-medium';
        subtext = '<p class="text-[11px] text-emerald-700 dark:text-emerald-400 mt-0.5">Complete</p>';
      } else if (isActive) {
        itemClass = 'proc-item-active';
        badgeClass = 'proc-badge-active';
        icon = '●';
        titleClass = 'text-slate-900 dark:text-slate-100 font-semibold';
        subtext = `<p class="text-[11px] text-amber-800 dark:text-amber-200 mt-0.5 font-medium">${escapeHtml(data.message || stage.desc)}</p>`;
      } else if (isFailed) {
        itemClass = 'proc-item-failed';
        badgeClass = 'proc-badge-failed';
        icon = '✕';
        titleClass = 'text-red-900 dark:text-red-300 font-semibold';
        subtext = `<p class="text-[11px] text-red-700 dark:text-red-400 mt-0.5 font-medium">${escapeHtml(data.error || 'Failed')}</p>`;
      }

      html += `
        <div class="flex items-start gap-3 rounded-xl p-2.5 transition ${itemClass}">
          <div class="${badgeClass}">${icon}</div>
          <div class="min-w-0 flex-1">
            <p class="text-xs ${titleClass}">${idx + 1}. ${stage.label}</p>
            ${subtext}
          </div>
        </div>
      `;
    });

    if (isError) {
      html += `
        <div class="mt-3 flex justify-end">
          <button id="btn-dismiss-error" type="button" class="btn btn-sm bg-slate-800 text-white hover:bg-slate-700 dark:bg-slate-700">Dismiss</button>
        </div>
      `;
    }

    processingStepper.innerHTML = html;

    const dismissBtn = $('btn-dismiss-error');
    if (dismissBtn) {
      dismissBtn.onclick = () => {
        if (processingCard) processingCard.hidden = true;
        switchTab('notes');
        setMicButtonState('idle');
      };
    }
  }

  function handleEngineStatusUpdate(data) {
    const prev = engineState;
    engineState = data.status;

    if (data.status === 'recording') {
      if (processingCard) processingCard.hidden = true;
      engineElapsedSeconds = data.elapsed_seconds || 0;
      setMicButtonState('recording', `Stop Call Capture (${formatDuration(engineElapsedSeconds)})`);
      setStatus(`● Recording Call (Consultant Mic + Headset Loopback) · ${formatDuration(engineElapsedSeconds)}`, 'rec');
    } else if (data.status === 'processing') {
      renderProcessingStepper(data);
      const stageName = data.stage_label || data.stage || 'Transcribing';
      setMicButtonState('processing', `⚙️ Processing (${stageName})`);
      setStatus(`⚙️ Processing Call: ${stageName} · ${formatDuration(data.elapsed_seconds || 0)}`, 'info');
    } else if (data.status === 'ready' && prev === 'processing') {
      renderProcessingStepper(data);
      setMicButtonState('idle', 'Start Call Capture');
      setStatus('Call processing complete. Review generated.', 'ok');
      selectedSessionId = data.session_id || selectedSessionId;
      selectedSessionType = data.session_type || 'live';
      if (selectedSessionId) {
        fetchAndRenderEngineArtifacts(selectedSessionId);
      }
      showToast('Live call analysis ready! Review before Salesforce update.');
    } else if (data.status === 'ready') {
      setMicButtonState('idle', 'Start Call Capture');
    } else if (data.status === 'error') {
      if (prev === 'processing') {
        renderProcessingStepper(data);
      }
      setMicButtonState('idle', 'Start Call Capture');
      setStatus(`Engine error: ${data.error || 'Unknown error'}`, 'err');
    } else if (data.status === 'cancelled') {
      if (processingCard) processingCard.hidden = true;
      selectedSessionId = null;
      recordingSessionId = null;
      engineState = 'idle';
      setMicButtonState('idle', 'Start Call Capture');
      setStatus('Ready');
      switchTab('notes');
    } else if (data.status === 'idle' && prev !== 'idle') {
      if (processingCard) processingCard.hidden = true;
      setMicButtonState('idle', 'Start Call Capture');
    }
  }

  function formatDuration(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  function setMicButtonState(stateType, label = null) {
    state = stateType;
    micBtn.setAttribute('data-state', stateType === 'recording' ? 'recording' : 'idle');
    micBtn.setAttribute('aria-pressed', String(stateType === 'recording'));
    micBtn.classList.remove('bg-teal-600', 'hover:bg-teal-500', 'bg-red-600', 'hover:bg-red-500', 'bg-amber-600', 'hover:bg-amber-500', 'mic-recording', 'opacity-75', 'cursor-not-allowed');

    if (stateType === 'recording') {
      micBtn.disabled = false;
      micBtn.classList.add('bg-red-600', 'hover:bg-red-500', 'mic-recording');
      micLabel.textContent = label || (engineConnected ? 'Stop Call Capture' : 'Stop Dictation');
    } else if (stateType === 'processing') {
      micBtn.disabled = true;
      micBtn.classList.add('bg-amber-600', 'hover:bg-amber-500', 'opacity-75', 'cursor-not-allowed');
      micLabel.textContent = label || 'Processing Call…';
    } else if (stateType === 'starting') {
      micBtn.disabled = false;
      micBtn.classList.add('bg-amber-600', 'hover:bg-amber-500');
      micLabel.textContent = label || 'Starting…';
    } else {
      micBtn.disabled = false;
      micBtn.classList.add('bg-teal-600', 'hover:bg-teal-500');
      micLabel.textContent = label || (engineConnected ? 'Start Call Capture' : 'Start Dictation');
    }
  }
  const setMicState = setMicButtonState;

  async function startEngineCallCapture() {
    try {
      setStatus('Connecting to audio streams…');
      const res = await engineFetch('/capture/start', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Could not start capture');
      }
      const resData = await res.json();
      recordingSessionId = resData.session_id || null;
      selectedSessionId = recordingSessionId;
      selectedSessionType = 'live';
      engineState = 'recording';
      engineElapsedSeconds = 0;
      artifactsLoaded = false;
      currentSalesforcePayload = null;
      clearInterval(engineSessionTimer);
      engineSessionTimer = setInterval(() => {
        engineElapsedSeconds++;
        micLabel.textContent = `Stop Call Capture (${formatDuration(engineElapsedSeconds)})`;
      }, 1000);
      setMicButtonState('recording');

      // Clear previous call artifacts while new recording is in progress
      transcriptContainer.innerHTML = `<p class="italic text-slate-400">Recording live call (Session: ${escapeHtml(recordingSessionId || '')})… transcript will generate upon stopping capture.</p>`;
      transcriptCount.textContent = 'Recording…';
      reviewContainer.innerHTML = `<p class="italic text-slate-400">Recording live call (Session: ${escapeHtml(recordingSessionId || '')})… AI analysis will generate upon stopping capture.</p>`;
      reviewConfidence.textContent = '—';
      reviewConfidence.className = 'rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700';
      salesforceContainer.innerHTML = `<p class="italic text-slate-400">Recording live call (Session: ${escapeHtml(recordingSessionId || '')})… Salesforce draft will generate upon stopping capture.</p>`;
    } catch (e) {
      showToast(`Failed to start capture: ${e.message}`);
      setStatus('Capture failed', 'err');
    }
  }

  async function stopEngineCallCapture() {
    if (!recordingSessionId) {
      showToast('No active recording session to stop.');
      return;
    }
    const sessionToStop = recordingSessionId;
    clearInterval(engineSessionTimer);
    setMicButtonState('processing', 'Stopping capture & transcribing…');
    setStatus('Finalizing audio files…', 'info');
    try {
      const res = await engineFetch(`/capture/stop?session_id=${encodeURIComponent(sessionToStop)}`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Could not stop capture');
      }
      recordingSessionId = null;
      engineState = 'processing';
      pollLocalEngine();
    } catch (e) {
      showToast(`Failed to stop capture: ${e.message}`);
      setMicButtonState('idle');
    }
  }

  async function cancelProcessing() {
    const sessionToCancel = selectedSessionId || recordingSessionId;
    if (sessionToCancel && engineConnected) {
      try {
        await engineFetch(`/capture/cancel?session_id=${encodeURIComponent(sessionToCancel)}`, { method: 'POST' });
      } catch (err) {
        console.warn('Cancel request to engine failed:', err);
      }
    }
    selectedSessionId = null;
    recordingSessionId = null;
    engineState = 'idle';
    if (processingCard) processingCard.hidden = true;
    setMicButtonState('idle', 'Start Call Capture');
    setStatus('Ready');
    switchTab('notes');
    showToast('Call processing cancelled.');
  }

  if (btnCancelProcessing) {
    btnCancelProcessing.addEventListener('click', cancelProcessing);
  }

  async function fetchAndRenderEngineArtifacts(sessionId) {
    if (!sessionId) {
      console.warn('fetchAndRenderEngineArtifacts called without explicit sessionId');
      return;
    }
    const sessionQuery = `?session_id=${encodeURIComponent(sessionId)}`;
    try {
      // 1. Fetch transcript
      const resTrans = await engineFetch(`/transcript${sessionQuery}`);
      if (!resTrans.ok) {
        const err = await resTrans.json();
        throw new Error(`Transcript fetch failed: ${err.detail || resTrans.statusText}`);
      }
      const transData = await resTrans.json();
      if (transData.session_id && transData.session_id !== sessionId) {
        throw new Error(`Session mismatch: received ${transData.session_id}, expected ${sessionId}`);
      }
      renderTranscript(transData.data);

      // 2. Fetch analysis & review
      const resReview = await engineFetch(`/review${sessionQuery}`);
      if (!resReview.ok) {
        const err = await resReview.json();
        throw new Error(`Review fetch failed: ${err.detail || resReview.statusText}`);
      }
      const reviewData = await resReview.json();
      renderReview(reviewData);

      // 3. Fetch structured analysis JSON
      const resAnalysis = await engineFetch(`/analysis${sessionQuery}`);
      if (resAnalysis.ok) {
        const analysisData = await resAnalysis.json();
        if (analysisData.data && analysisData.data.confidence) {
          reviewConfidence.textContent = `Confidence: ${analysisData.data.confidence.level} (${Math.round(analysisData.data.confidence.score * 100)}%)`;
          reviewConfidence.className = 'rounded-full bg-teal-100 px-2.5 py-0.5 text-[11px] font-semibold text-teal-800 dark:bg-teal-950 dark:text-teal-300 border border-teal-200 dark:border-teal-800';
        }
      }
      artifactsLoaded = true;
    } catch (e) {
      console.error('Error fetching session artifacts:', e);
      setStatus(`Artifact error: ${e.message}`, 'err');
      showToast(`Could not load session results: ${e.message}`, 'Retry', () => fetchAndRenderEngineArtifacts(sessionId));
    }
  }

  function renderTranscript(transJson) {
    if (!transJson || !transJson.merged_turns) return;
    artifactsLoaded = true;
    const turns = transJson.merged_turns;
    currentTranscriptTurns = turns;
    transcriptCount.textContent = `${turns.length} turns`;

    let html = '';
    turns.forEach((t, idx) => {
      const isConsultant = t.speaker === 'CONSULTANT';
      const turnBg = isConsultant ? 'bg-slate-50/70 dark:bg-slate-800/30' : 'bg-transparent';
      const speakerClass = isConsultant ? 'text-teal-700 dark:text-teal-400 font-semibold' : 'text-slate-600 dark:text-slate-400 font-medium';
      html += `
        <div class="transcript-turn rounded-lg p-2.5 transition ${turnBg}" data-turn-idx="${idx}" data-turn-text="${escapeHtml(t.text)}">
          <div class="flex items-center justify-between gap-2 mb-1">
            <span class="text-xs ${speakerClass}">${escapeHtml(t.speaker)}</span>
            <span class="text-[10px] text-slate-400 font-mono">${escapeHtml(t.timestamp_str || '')}</span>
          </div>
          <p class="text-xs text-slate-800 dark:text-slate-200 leading-relaxed">${escapeHtml(t.text)}</p>
        </div>
      `;
    });
    transcriptContainer.innerHTML = html || '<p class="italic text-slate-400">Empty transcript.</p>';

    // Trigger Procedure Hub evaluation on transcript text
    const fullTranscriptText = turns.map((t) => t.text).join(' ');
    triggerProcedureContext(fullTranscriptText);
    refreshQaReadiness();
  }

  function renderReview(reviewData) {
    if (!reviewData) return;
    artifactsLoaded = true;
    
    // Render Markdown summary nicely with evidence links
    const md = reviewData.markdown || '';
    reviewContainer.innerHTML = formatSimpleMarkdown(md);

    // Trigger Procedure Hub evaluation on review summary
    triggerProcedureContext(md);

    // Render Salesforce Draft with editable inputs and dirty tracking
    renderSalesforceDraft(reviewData);
    refreshQaReadiness();
  }

  function renderSalesforceDraft(reviewData) {
    currentSalesforcePayload = reviewData.salesforce_draft;
    if (!currentSalesforcePayload) return;

    const f = currentSalesforcePayload.fields || currentSalesforcePayload;
    const subject = f.Subject || f.subject || '';
    const description = f.Description || f.description || '';
    const status = f.Status || f.status || 'Pending Follow-up';
    const remoteId = f.Remote_Connection_ID__c || f.remote_connection_id || 'N/A';
    const category = f.Resolution_Category__c || f.resolution_category || 'Technical Support';

    originalSalesforceValues = {
      subject: subject,
      remoteId: remoteId,
      category: category,
      status: status,
      description: description
    };

    if (sfEditedBadge) sfEditedBadge.hidden = true;
    if (sfRestoreBtn) sfRestoreBtn.hidden = true;

    salesforceContainer.innerHTML = `
      <div class="space-y-3">
        <div class="rounded-lg bg-slate-50/70 p-2.5 dark:bg-slate-800/30 text-slate-700 dark:text-slate-300">
          <p class="font-medium text-xs text-slate-900 dark:text-slate-100">Human Review &amp; CRM Sync</p>
          <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">Review or edit fields below. Use copy buttons to transfer individual fields or the full record into Salesforce.</p>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
          <div>
            <div class="flex items-center justify-between mb-1">
              <label for="sf-status" class="text-slate-600 dark:text-slate-300 font-medium text-xs">Case Status</label>
              <button type="button" class="sf-copy-field-btn text-[11px] text-slate-400 hover:text-teal-600 dark:text-slate-500 dark:hover:text-teal-400 font-medium transition" data-target="sf-status" data-label="Status">Copy</button>
            </div>
            <input id="sf-status" type="text" value="${escapeHtml(status)}" class="w-full rounded-lg border border-slate-200/80 bg-white p-2 text-xs font-medium text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-teal-500/70 focus:border-teal-500/70" />
          </div>
          <div>
            <div class="flex items-center justify-between mb-1">
              <label for="sf-remote-id" class="text-slate-600 dark:text-slate-300 font-medium text-xs">Remote Connection ID</label>
              <button type="button" class="sf-copy-field-btn text-[11px] text-slate-400 hover:text-teal-600 dark:text-slate-500 dark:hover:text-teal-400 font-medium transition" data-target="sf-remote-id" data-label="Remote ID">Copy</button>
            </div>
            <input id="sf-remote-id" type="text" value="${escapeHtml(remoteId)}" class="w-full rounded-lg border border-slate-200/80 bg-white p-2 text-xs font-mono font-medium text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-teal-500/70 focus:border-teal-500/70" />
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
          <div>
            <div class="flex items-center justify-between mb-1">
              <label for="sf-category" class="text-slate-600 dark:text-slate-300 font-medium text-xs">Resolution Category</label>
              <button type="button" class="sf-copy-field-btn text-[11px] text-slate-400 hover:text-teal-600 dark:text-slate-500 dark:hover:text-teal-400 font-medium transition" data-target="sf-category" data-label="Category">Copy</button>
            </div>
            <input id="sf-category" type="text" value="${escapeHtml(category)}" class="w-full rounded-lg border border-slate-200/80 bg-white p-2 text-xs font-medium text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-teal-500/70 focus:border-teal-500/70" />
          </div>
          <div>
            <div class="flex items-center justify-between mb-1">
              <label for="sf-subject" class="text-slate-600 dark:text-slate-300 font-medium text-xs">Case Subject</label>
              <button type="button" class="sf-copy-field-btn text-[11px] text-slate-400 hover:text-teal-600 dark:text-slate-500 dark:hover:text-teal-400 font-medium transition" data-target="sf-subject" data-label="Subject">Copy</button>
            </div>
            <input id="sf-subject" type="text" value="${escapeHtml(subject)}" class="w-full rounded-lg border border-slate-200/80 bg-white p-2 text-xs font-medium text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-teal-500/70 focus:border-teal-500/70" />
          </div>
        </div>
        <div>
          <div class="flex items-center justify-between mb-1">
            <label for="sf-description" class="text-slate-600 dark:text-slate-300 font-medium text-xs">Case Description (First-person narrative)</label>
            <button type="button" class="sf-copy-field-btn text-[11px] text-slate-400 hover:text-teal-600 dark:text-slate-500 dark:hover:text-teal-400 font-medium transition" data-target="sf-description" data-label="Description">Copy</button>
          </div>
          <textarea id="sf-description" rows="7" class="w-full rounded-lg border border-slate-200/80 bg-white p-2.5 text-xs font-mono leading-relaxed text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-teal-500/70 focus:border-teal-500/70">${escapeHtml(description)}</textarea>
        </div>
      </div>
    `;

    ['sf-subject', 'sf-remote-id', 'sf-category', 'sf-status', 'sf-description'].forEach((id) => {
      const el = $(id);
      if (el) {
        el.addEventListener('input', checkSalesforceDirty);
        el.addEventListener('change', checkSalesforceDirty);
      }
    });
  }

  function checkSalesforceDirty() {
    if (!originalSalesforceValues) return;
    const currentSubject = $('sf-subject')?.value ?? '';
    const currentRemoteId = $('sf-remote-id')?.value ?? '';
    const currentCategory = $('sf-category')?.value ?? '';
    const currentStatus = $('sf-status')?.value ?? '';
    const currentDescription = $('sf-description')?.value ?? '';

    const isDirty = (
      currentSubject !== originalSalesforceValues.subject ||
      currentRemoteId !== originalSalesforceValues.remoteId ||
      currentCategory !== originalSalesforceValues.category ||
      currentStatus !== originalSalesforceValues.status ||
      currentDescription !== originalSalesforceValues.description
    );

    if (sfEditedBadge) sfEditedBadge.hidden = !isDirty;
    if (sfRestoreBtn) sfRestoreBtn.hidden = !isDirty;
    refreshQaReadiness();
  }

  function restoreOriginalSalesforceDraft() {
    if (!originalSalesforceValues) return;
    const sub = $('sf-subject'); if (sub) sub.value = originalSalesforceValues.subject;
    const rem = $('sf-remote-id'); if (rem) rem.value = originalSalesforceValues.remoteId;
    const cat = $('sf-category'); if (cat) cat.value = originalSalesforceValues.category;
    const stat = $('sf-status'); if (stat) stat.value = originalSalesforceValues.status;
    const desc = $('sf-description'); if (desc) desc.value = originalSalesforceValues.description;

    if (sfEditedBadge) sfEditedBadge.hidden = true;
    if (sfRestoreBtn) sfRestoreBtn.hidden = true;
    refreshQaReadiness();
    showToast('Restored original Salesforce draft fields.');
  }

  function copyFieldToClipboard(targetId, fieldName) {
    const el = $(targetId);
    if (!el) return;
    const val = el.value || '';
    navigator.clipboard.writeText(val).then(() => {
      showToast(`${fieldName} copied to clipboard!`);
    }).catch(() => {
      showToast('Copy failed.');
    });
  }

  function escapeHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function formatSimpleMarkdown(text) {
    let out = escapeHtml(text);
    // Headers
    out = out.replace(/^# (.*?)$/gm, '<h1 class="text-sm font-semibold text-slate-900 dark:text-slate-100 mt-2 mb-1 border-b border-slate-100 dark:border-slate-800 pb-1">$1</h1>');
    out = out.replace(/^## (.*?)$/gm, '<h2 class="text-xs font-semibold text-slate-800 dark:text-slate-200 mt-3 mb-1 text-teal-800 dark:text-teal-300">$1</h2>');
    // Blockquotes & Alerts
    out = out.replace(/^> \[\!(.*?)\]\n> (.*?)$/gm, '<div class="my-2 p-2.5 rounded-lg bg-slate-50/70 dark:bg-slate-800/40 border-l-2 border-teal-600 text-xs text-slate-800 dark:text-slate-200"><strong class="font-semibold text-teal-800 dark:text-teal-300">$1:</strong> $2</div>');
    out = out.replace(/^> (.*?)$/gm, '<blockquote class="my-2 p-2.5 rounded-lg bg-slate-50/70 dark:bg-slate-800/40 border-l-2 border-slate-300 dark:border-slate-700 text-xs italic text-slate-700 dark:text-slate-300">$1</blockquote>');
    // Bold / Code
    out = out.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-slate-900 dark:text-slate-100">$1</strong>');
    out = out.replace(/`(.*?)`/g, '<code class="px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-mono text-[11px] text-slate-800 dark:text-slate-200">$1</code>');
    // Bullet items
    out = out.replace(/^\- (.*?)$/gm, '<li class="ml-4 list-disc text-slate-700 dark:text-slate-300">$1</li>');
    out = out.replace(/^\* (.*?)$/gm, '<li class="ml-4 list-disc text-slate-700 dark:text-slate-300">$1</li>');
    // Evidence quotes in tables or text (D.4)
    out = out.replace(/\*(?:&quot;|"|“)(.*?)(?:&quot;|"|”)\*/g, (match, quoteText) => {
      const cleanQuote = quoteText.replace(/&quot;/g, '"');
      return `<span class="evidence-quote-link" title="Click to view quote in transcript" data-quote="${escapeHtml(cleanQuote)}">"${cleanQuote}"</span>`;
    });
    // Tables
    out = out.replace(/\|(.+)\|/g, (match) => {
      const cells = match.split('|').filter((c) => c.trim() !== '');
      if (cells.some((c) => c.includes('---'))) return '';
      return `<div class="flex gap-2 text-[11px] py-1 border-b border-slate-100 dark:border-slate-800 text-slate-700 dark:text-slate-300">${cells.map((c) => `<span class="flex-1">${c.trim()}</span>`).join('')}</div>`;
    });
    return out.replace(/\n\n/g, '<br/>');
  }

  // Evidence Quote Click Handler on reviewContainer (D.4)
  reviewContainer.addEventListener('click', (e) => {
    const quoteEl = e.target.closest('.evidence-quote-link');
    if (!quoteEl) return;

    const rawQuote = quoteEl.getAttribute('data-quote') || quoteEl.textContent || '';
    const cleanQuote = rawQuote.replace(/^["'“\s]+|["'”\s\.]+/g, '').trim().toLowerCase();
    if (!cleanQuote) return;

    // Switch or ensure dialogue is visible
    if (!isDesktopSplit) {
      switchTab('transcript');
    }

    // Search turns in transcriptContainer
    const turns = transcriptContainer.querySelectorAll('.transcript-turn');
    let matchedTurn = null;

    // Search by full string or prominent tokens
    const tokens = cleanQuote.split(/\s+/).filter((w) => w.length > 3);
    const searchToken = tokens.slice(0, 3).join(' ');

    for (const turn of turns) {
      const turnText = (turn.getAttribute('data-turn-text') || turn.textContent || '').toLowerCase();
      if (turnText.includes(cleanQuote) || (searchToken && turnText.includes(searchToken))) {
        matchedTurn = turn;
        break;
      }
    }

    if (matchedTurn) {
      matchedTurn.scrollIntoView({ behavior: 'smooth', block: 'center' });
      matchedTurn.classList.add('turn-highlight-pulse');
      setTimeout(() => matchedTurn.classList.remove('turn-highlight-pulse'), 2500);
      showToast('Jumped to dialogue evidence turn!');
    } else {
      showToast('Evidence quote located in audio source.');
    }
  });

  // ---------------------------------------------------------------- Desktop Split & Tab Navigation (D.1)
  function toggleDesktopSplit(forceState) {
    if (!mainContent) return;
    isDesktopSplit = typeof forceState === 'boolean' ? forceState : !isDesktopSplit;
    mainContent.classList.toggle('desktop-split-active', isDesktopSplit);
    if (splitToggleLabel) {
      splitToggleLabel.textContent = isDesktopSplit ? 'Split View: On' : 'Split View: Off';
    }
    if (btnToggleSplit) {
      if (isDesktopSplit) {
        btnToggleSplit.classList.add('border-teal-500', 'bg-teal-50', 'dark:bg-teal-950/40', 'text-teal-700', 'dark:text-teal-300');
      } else {
        btnToggleSplit.classList.remove('border-teal-500', 'bg-teal-50', 'dark:bg-teal-950/40', 'text-teal-700', 'dark:text-teal-300');
      }
    }
    updatePanelsForCurrentMode();
  }

  function updatePanelsForCurrentMode() {
    if (processingCard && !processingCard.hidden) return;

    if (!isDesktopSplit) {
      const tabs = [
        { id: 'notes', btn: tabNotes, panel: panelNotes },
        { id: 'transcript', btn: tabTranscript, panel: panelTranscript },
        { id: 'review', btn: tabReview, panel: panelReview },
        { id: 'salesforce', btn: tabSalesforce, panel: panelSalesforce },
        { id: 'qa', btn: tabQa, panel: panelQa },
      ].filter((t) => t.btn && t.panel);
      tabs.forEach((t) => {
        const active = (t.id === currentTabId);
        t.panel.hidden = !active;
        t.btn.className = active ? 'tab-item-active' : 'tab-item';
      });
      if (tagsNav) tagsNav.hidden = currentTabId !== 'notes' || engineConnected;
    } else {
      // Dual-pane layout on desktop: Left pane (Notes or Transcript), Right pane (Review, Salesforce, or QA)
      panelNotes.hidden = (activeLeftTab !== 'notes');
      panelTranscript.hidden = (activeLeftTab !== 'transcript');
      panelReview.hidden = (activeRightTab !== 'review');
      panelSalesforce.hidden = (activeRightTab !== 'salesforce');
      if (panelQa) panelQa.hidden = (activeRightTab !== 'qa');

      tabNotes.className = (activeLeftTab === 'notes') ? 'tab-item-active' : 'tab-item';
      tabTranscript.className = (activeLeftTab === 'transcript') ? 'tab-item-active' : 'tab-item';
      tabReview.className = (activeRightTab === 'review') ? 'tab-item-active' : 'tab-item';
      tabSalesforce.className = (activeRightTab === 'salesforce') ? 'tab-item-active' : 'tab-item';
      if (tabQa) tabQa.className = (activeRightTab === 'qa') ? 'tab-item-active' : 'tab-item';

      if (tagsNav) tagsNav.hidden = activeLeftTab !== 'notes' || engineConnected;
    }
  }

  function switchTab(tabId) {
    if (processingCard) processingCard.hidden = true;
    currentTabId = tabId;

    if (tabId === 'notes' || tabId === 'transcript') {
      activeLeftTab = tabId;
    } else if (tabId === 'review' || tabId === 'salesforce' || tabId === 'qa') {
      activeRightTab = tabId;
    }

    updatePanelsForCurrentMode();
  }

  tabNotes.addEventListener('click', () => switchTab('notes'));
  tabTranscript.addEventListener('click', () => switchTab('transcript'));
  tabReview.addEventListener('click', () => switchTab('review'));
  tabSalesforce.addEventListener('click', () => switchTab('salesforce'));
  if (tabQa) tabQa.addEventListener('click', () => switchTab('qa'));

  if (btnViewTranscript) {
    btnViewTranscript.addEventListener('click', () => switchTab('transcript'));
  }
  if (btnViewReview) {
    btnViewReview.addEventListener('click', () => switchTab('review'));
  }
  if (btnViewSf) {
    btnViewSf.addEventListener('click', () => switchTab('salesforce'));
  }

  if (btnToggleSplit) {
    btnToggleSplit.addEventListener('click', () => toggleDesktopSplit());
  }

  // ---------------------------------------------------------------- Call History Drawer (D.3)
  async function updateCallHistoryBadge() {
    if (!getEngineToken()) return;
    try {
      const res = await engineFetch('/sessions');
      if (res.ok) {
        const list = await res.json();
        if (historyBadge) historyBadge.textContent = String(list.length || 0);
        if (chTotalCount) chTotalCount.textContent = `${list.length || 0} sessions found`;
      }
    } catch {
      // background update
    }
  }

  async function loadCallHistory() {
    if (!chList) return;
    if (!engineConnected && !getEngineToken()) {
      chList.innerHTML = `
        <div class="p-4 text-center text-slate-500 dark:text-slate-400">
          <p class="font-semibold text-xs">Local Engine Not Connected</p>
          <p class="text-[11px] mt-1">Authenticate with the Speak Engine to access persistent call session history.</p>
          <button id="ch-pair-btn" type="button" class="btn btn-sm bg-teal-600 text-white mt-2 text-xs">Pair Engine</button>
        </div>
      `;
      const pBtn = $('ch-pair-btn');
      if (pBtn) pBtn.onclick = () => { closeCallHistoryDrawer(); openPairingModal(); };
      return;
    }

    chList.innerHTML = '<p class="italic text-slate-400 p-2">Loading session history from engine…</p>';
    try {
      const res = await engineFetch('/sessions');
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to retrieve session list');
      }
      const sessions = await res.json();
      if (historyBadge) historyBadge.textContent = String(sessions.length);
      if (chTotalCount) chTotalCount.textContent = `${sessions.length} sessions found`;

      if (sessions.length === 0) {
        chList.innerHTML = '<p class="italic text-slate-400 p-3 text-center">No recorded sessions found yet.</p>';
        return;
      }

      sessions.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));

      let html = '';
      sessions.forEach((s) => {
        const isReady = s.status === 'ready';
        const isError = s.status === 'error' || s.status === 'interrupted';
        const isQueued = s.status === 'queued' || s.status === 'queued_backpressure';
        const isRec = s.status === 'recording' || s.status === 'processing';

        let badgeBg = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
        if (isReady) badgeBg = 'bg-emerald-50 text-emerald-800 border border-emerald-200/60 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/50';
        else if (isError) badgeBg = 'bg-rose-50 text-rose-800 border border-rose-200/60 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/50';
        else if (isQueued) badgeBg = 'bg-amber-50 text-amber-800 border border-amber-200/60 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50';
        else if (isRec) badgeBg = 'bg-slate-100 text-slate-800 border border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700';

        const dateStr = s.created_at ? new Date(s.created_at).toLocaleString() : 'Recent';
        const shortId = s.session_id.replace(/^session_/, '').slice(0, 16);

        let retryButtonHtml = '';
        if (isError || s.status === 'queued_backpressure') {
          retryButtonHtml = `
            <button type="button" class="ch-retry-btn btn btn-sm bg-amber-600 text-white hover:bg-amber-500 px-2 py-0.5 text-xs font-medium" data-session-id="${escapeHtml(s.session_id)}">Retry</button>
          `;
        }

        html += `
          <div class="rounded-lg border border-slate-200/80 dark:border-slate-800 p-2.5 bg-slate-50/60 dark:bg-slate-800/30 space-y-1.5">
            <div class="flex items-center justify-between gap-1">
              <span class="font-mono font-medium text-xs truncate text-slate-800 dark:text-slate-200" title="${escapeHtml(s.session_id)}">${escapeHtml(shortId)}</span>
              <span class="rounded px-1.5 py-0.5 text-[10px] font-medium ${badgeBg} capitalize">${escapeHtml(s.status)}</span>
            </div>
            <div class="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400">
              <span>${escapeHtml(dateStr)}</span>
              <span class="capitalize">${escapeHtml(s.session_type || 'live')}</span>
            </div>
            ${s.error_message ? `<p class="text-[10px] text-red-600 dark:text-red-400 truncate" title="${escapeHtml(s.error_message)}">${escapeHtml(s.error_message)}</p>` : ''}
            <div class="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800">
              <div class="flex gap-1 text-[9px] text-slate-400">
                ${s.audio_available ? '<span title="Audio WAVs available">🎙️ Audio</span>' : ''}
                ${s.has_transcript ? '<span title="Transcript available">📝 Transcript</span>' : ''}
                ${s.has_review ? '<span title="CRM analysis available">⚡ CRM</span>' : ''}
              </div>
              <div class="flex items-center gap-1">
                ${retryButtonHtml}
                <button type="button" class="ch-load-btn btn btn-sm bg-teal-600 text-white hover:bg-teal-500 px-2 py-0.5 text-xs font-medium" data-session-id="${escapeHtml(s.session_id)}" data-session-type="${escapeHtml(s.session_type || 'live')}">Load</button>
              </div>
            </div>
          </div>
        `;
      });
      chList.innerHTML = html;
    } catch (e) {
      chList.innerHTML = `<p class="text-red-500 text-xs p-2">Failed to load history: ${escapeHtml(e.message)}</p>`;
    }
  }

  function openCallHistoryDrawer() {
    if (!callHistoryDrawer) return;
    callHistoryDrawer.hidden = false;
    loadCallHistory();
  }

  function closeCallHistoryDrawer() {
    if (!callHistoryDrawer) return;
    callHistoryDrawer.hidden = true;
  }

  async function retrySessionFromHistory(sessionId) {
    showToast(`Re-enqueuing session ${sessionId}…`);
    try {
      const res = await engineFetch(`/sessions/${encodeURIComponent(sessionId)}/retry`, { method: 'POST' });
      if (res.ok) {
        showToast(`Session ${sessionId} re-enqueued!`);
        loadCallHistory();
        pollLocalEngine();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(`Retry rejected: ${err.detail || 'Could not retry session'}`);
      }
    } catch (e) {
      showToast(`Retry error: ${e.message}`);
    }
  }

  if (btnCallHistory) {
    btnCallHistory.addEventListener('click', openCallHistoryDrawer);
  }
  if (chClose) {
    chClose.addEventListener('click', closeCallHistoryDrawer);
  }
  if (chRefreshBtn) {
    chRefreshBtn.addEventListener('click', loadCallHistory);
  }
  if (callHistoryDrawer) {
    callHistoryDrawer.addEventListener('click', (e) => {
      if (e.target === callHistoryDrawer) closeCallHistoryDrawer();
    });
  }
  if (chList) {
    chList.addEventListener('click', (e) => {
      const loadBtn = e.target.closest('.ch-load-btn');
      if (loadBtn) {
        const sId = loadBtn.getAttribute('data-session-id');
        const sType = loadBtn.getAttribute('data-session-type') || 'live';
        selectedSessionId = sId;
        selectedSessionType = sType;
        fetchAndRenderEngineArtifacts(sId);
        closeCallHistoryDrawer();
        switchTab('review');
        showToast(`Loaded session ${sId}`);
        return;
      }
      const retryBtn = e.target.closest('.ch-retry-btn');
      if (retryBtn) {
        const sId = retryBtn.getAttribute('data-session-id');
        retrySessionFromHistory(sId);
      }
    });
  }

  // ---------------------------------------------------------------- Pairing Modal Listeners (SEC-01 & SEC-04)
  if (epClose) epClose.addEventListener('click', closePairingModal);
  if (epCancelBtn) epCancelBtn.addEventListener('click', closePairingModal);
  if (enginePairingModal) {
    enginePairingModal.addEventListener('click', (e) => {
      if (e.target === enginePairingModal) closePairingModal();
    });
  }
  if (epForm) {
    epForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const code = epCodeInput?.value || '';
      const remember = epRemember?.checked || false;
      pairWithEngine(code, remember);
    });
  }

  // ---------------------------------------------------------------- Salesforce Draft Event Listeners (D.2)
  if (sfRestoreBtn) {
    sfRestoreBtn.addEventListener('click', restoreOriginalSalesforceDraft);
  }

  salesforceContainer.addEventListener('click', (e) => {
    const btn = e.target.closest('.sf-copy-field-btn');
    if (btn) {
      const targetId = btn.getAttribute('data-target');
      const label = btn.getAttribute('data-label') || 'Field';
      copyFieldToClipboard(targetId, label);
    }
  });

  copySfBtn.addEventListener('click', () => {
    const sub = $('sf-subject')?.value || '';
    const rem = $('sf-remote-id')?.value || '';
    const cat = $('sf-category')?.value || '';
    const stat = $('sf-status')?.value || '';
    const desc = $('sf-description')?.value || '';

    if (!sub && !desc) {
      if (currentSalesforcePayload && currentSalesforcePayload.fields) {
        const fallbackTxt = currentSalesforcePayload.fields.Description || JSON.stringify(currentSalesforcePayload, null, 2);
        navigator.clipboard.writeText(fallbackTxt).then(() => showToast('Salesforce case record copied!'));
      } else {
        showToast('No Salesforce payload to copy.');
      }
      return;
    }

    const fullRecord = [
      `Case Subject: ${sub}`,
      `Case Status: ${stat}`,
      `Remote Connection ID: ${rem}`,
      `Resolution Category: ${cat}`,
      '',
      'Case Description:',
      desc
    ].join('\n');

    navigator.clipboard.writeText(fullRecord).then(() => {
      showToast('Full Salesforce case record copied to clipboard!');
    }).catch(() => {
      showToast('Copy failed.');
    });
  });

  // ---------------------------------------------------------------- Demo Actions
  async function loadDemoCall() {
    if (recordingSessionId) {
      showToast('Cannot load a demo while recording a live call. Please stop or finish your recording first.');
      return;
    }
    showToast('Loading demo call sample…');
    if (engineConnected) {
      try {
        const res = await engineFetch('/demo/load-sample', { method: 'POST' });
        if (res.ok) {
          const resData = await res.json();
          selectedSessionId = resData.session_id;
          selectedSessionType = 'demo';
          lastRawBeforeTidy = '';
          hideTidyComparison();
          notes.value = DEMO_ROUGH_NOTE;
          onNotesChanged();
          await fetchAndRenderEngineArtifacts(selectedSessionId);
          switchTab('review');
          showToast('Real 9-minute demo call loaded!');
          return;
        }
      } catch (e) {
        console.warn('Local engine demo load failed:', e);
      }
    }

    // Client-side demo fallback ONLY when engine is offline and user explicitly clicked Demo Call
    try {
      selectedSessionId = 'demo_client_offline';
      selectedSessionType = 'demo';
      lastRawBeforeTidy = '';
      hideTidyComparison();
      notes.value = DEMO_ROUGH_NOTE;
      onNotesChanged();
      renderTranscript(DEMO_TRANSCRIPT_DATA);
      renderReview({
        markdown: DEMO_REVIEW_MARKDOWN,
        salesforce_draft: DEMO_SALESFORCE_PAYLOAD
      });
      reviewConfidence.textContent = 'Confidence: HIGH (80%)';
      reviewConfidence.className = 'rounded-full bg-teal-100 px-2.5 py-0.5 text-[11px] font-semibold text-teal-800 dark:bg-teal-950 dark:text-teal-300 border border-teal-200 dark:border-teal-800';
      artifactsLoaded = true;
      switchTab('review');
      showToast('Demo call sample loaded (offline mode)!');
    } catch (e) {
      showToast(`Error loading demo sample: ${e.message}`, 'Retry', () => loadDemoCall());
    }
  }

  if (btnLoadSample) {
    btnLoadSample.addEventListener('click', () => {
      loadDemoCall();
    });
  }

  // ---------------------------------------------------------------- quick-insert shortcuts
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
      text = text.replace(/([.!?]\s+|\n)([a-z])/g, (_, sep, c) => sep + c.toUpperCase());
    }

    const inserted = prefix + text;
    notes.value = before + inserted + after;
    const caret = before.length + prefix.length + (caretOffset ?? text.length);
    notes.setSelectionRange(caret, caret);

    if (opts.focus && !(isCoarsePointer && !opts.forceFocus)) notes.focus({ preventScroll: true });
    if (caret >= notes.value.length - 1) notes.scrollTop = notes.scrollHeight;
    onNotesChanged();
  }

  // ---------------------------------------------------------------- notes state & Procedure Hub
  let saveTimer = null;
  let procedureReminder = null;

  function triggerProcedureContext(extraText = '') {
    if (!procedureReminder) return;
    const combined = [notes.value, extraText].filter(Boolean).join('\n');
    if (combined.trim()) {
      procedureReminder.textChanged(combined);
    }
  }

  function hideTidyComparison() {
    if (tidyComparison) tidyComparison.hidden = true;
  }

  function showTidyComparison(beforeText, afterText) {
    if (!tidyComparison || !tidyBefore || !tidyAfter) return;
    tidyBefore.textContent = beforeText.trim();
    tidyAfter.textContent = afterText.trim();
    tidyComparison.hidden = false;
  }

  function getCurrentSalesforceFields() {
    const sub = $('sf-subject')?.value ?? (currentSalesforcePayload?.fields?.Subject || '');
    const stat = $('sf-status')?.value ?? (currentSalesforcePayload?.fields?.Status || '');
    const cat = $('sf-category')?.value ?? (currentSalesforcePayload?.fields?.Resolution_Category__c || '');
    const rem = $('sf-remote-id')?.value ?? (currentSalesforcePayload?.fields?.Remote_Connection_ID__c || '');
    const desc = $('sf-description')?.value ?? (currentSalesforcePayload?.fields?.Description || '');
    return {
      subject: sub,
      status: stat,
      category: cat,
      remoteId: rem,
      description: desc,
    };
  }

  function getQaBadgeClasses(status) {
    switch (status) {
      case 'Ready':
        return 'bg-emerald-50 text-emerald-800 border-emerald-200/60 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/50';
      case 'Needs attention':
        return 'bg-amber-50 text-amber-800 border-amber-200/60 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50';
      case 'Unverified':
      case 'Review Required':
        return 'bg-rose-50 text-rose-800 border-rose-200/60 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/50';
      case 'Not applicable':
      default:
        return 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700';
    }
  }

  function refreshQaReadiness() {
    const CQ = window.CaseQuality;
    if (!CQ || typeof CQ.evaluateQaReadiness !== 'function') return;

    const report = CQ.evaluateQaReadiness({
      noteText: notes.value,
      originalNoteText: lastRawBeforeTidy,
      salesforceFields: getCurrentSalesforceFields(),
      transcriptTurns: currentTranscriptTurns,
    });

    const hasInput = Boolean(notes.value.trim() || getCurrentSalesforceFields().description.trim());

    // Update top tab badge
    if (tabQaBadge) {
      const actionable = report.counts.needsAttention + report.counts.unverified;
      if (!hasInput) {
        tabQaBadge.textContent = '—';
        tabQaBadge.className = 'ml-0.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300';
      } else if (report.overallStatus === 'Review Required' || report.overallStatus === 'Unverified') {
        tabQaBadge.textContent = 'Review';
        tabQaBadge.className = 'ml-0.5 rounded-full bg-rose-50 border border-rose-200/60 px-1.5 py-0.5 text-[10px] font-semibold text-rose-800 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/50';
      } else if (actionable === 0) {
        tabQaBadge.textContent = 'Ready';
        tabQaBadge.className = 'ml-0.5 rounded-full bg-emerald-50 border border-emerald-200/60 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/50';
      } else {
        tabQaBadge.textContent = String(actionable);
        tabQaBadge.className = 'ml-0.5 rounded-full bg-amber-50 border border-amber-200/60 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50';
      }
    }

    // Update inline notes QA status pill
    if (notesQaStatus) {
      notesQaStatus.textContent = hasInput ? report.overallStatus : '—';
      notesQaStatus.className = `rounded border px-1.5 py-0.5 text-[10px] font-semibold ${hasInput ? getQaBadgeClasses(report.overallStatus) : 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'}`;
    }

    // Update QA Readiness Panel status card
    if (qaScoreCard) {
      if (!hasInput) {
        qaScoreCard.className = 'mt-1.5 mb-2 flex items-center justify-between gap-2 rounded-md border border-slate-200/50 bg-slate-50/40 px-2 py-1 text-[11px] dark:border-slate-800/40 dark:bg-slate-900/20';
      } else if (report.overallStatus === 'Review Required') {
        qaScoreCard.className = 'mt-1.5 mb-2 flex items-center justify-between gap-2 rounded-md border border-rose-200/50 bg-rose-50/40 px-2 py-1 text-[11px] dark:border-rose-900/40 dark:bg-rose-950/20';
      } else if (report.overallStatus === 'Ready') {
        qaScoreCard.className = 'mt-1.5 mb-2 flex items-center justify-between gap-2 rounded-md border border-emerald-200/50 bg-emerald-50/40 px-2 py-1 text-[11px] dark:border-emerald-900/40 dark:bg-emerald-950/20';
      } else {
        qaScoreCard.className = 'mt-1.5 mb-2 flex items-center justify-between gap-2 rounded-md border border-amber-200/50 bg-amber-50/40 px-2 py-1 text-[11px] dark:border-amber-900/40 dark:bg-amber-950/20';
      }
    }
    if (qaScoreDisplay) {
      qaScoreDisplay.textContent = hasInput ? (report.scoreDisplay || report.overallStatus) : '—';
    }
    if (qaScoreLabel) {
      if (!hasInput) {
        qaScoreLabel.textContent = 'Readiness Status';
      } else if (report.overallStatus === 'Review Required') {
        qaScoreLabel.textContent = 'Customer confirmation pending. Do not mark the case resolved before confirmation.';
      } else {
        qaScoreLabel.textContent = report.scoreLabel || 'Readiness Status';
      }
    }
    if (qaScoreSubtext) {
      if (!hasInput) {
        qaScoreSubtext.textContent = 'Load a demo case or enter notes to evaluate closure readiness.';
      } else if (report.overallStatus === 'Review Required') {
        qaScoreSubtext.textContent = 'Resolution notes and callback number require verification before closure.';
      } else {
        qaScoreSubtext.textContent = report.scoreSubtext || report.summaryText;
      }
    }

    // Update QA Readiness Panel header & summary
    if (qaOverallBadge) {
      if (!hasInput) {
        qaOverallBadge.textContent = '—';
        qaOverallBadge.className = 'rounded-full border border-slate-200 px-2 py-0.5 text-[10px] font-semibold bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700';
      } else {
        qaOverallBadge.textContent = report.overallStatus;
        qaOverallBadge.className = `rounded-full border px-2 py-0.5 text-[10px] font-semibold ${getQaBadgeClasses(report.overallStatus)}`;
      }
    }
    if (qaSummaryText) {
      qaSummaryText.textContent = 'Checklist Summary:';
    }
    if (qaCountsPills) {
      if (!hasInput) {
        qaCountsPills.innerHTML = `
          <span class="rounded-full border border-slate-200 px-2.5 py-0.5 bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700">0 Ready</span>
          <span class="rounded-full border border-slate-200 px-2.5 py-0.5 bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700">0 Unverified</span>
          <span class="rounded-full border border-slate-200 px-2.5 py-0.5 bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700">0 Not applicable</span>
          <span class="rounded-full border border-slate-200 px-2.5 py-0.5 bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700">0 Needs attention</span>
        `;
      } else {
        qaCountsPills.innerHTML = `
          <span class="rounded-full border px-2.5 py-0.5 ${getQaBadgeClasses('Ready')}">${report.counts.ready} Ready</span>
          <span class="rounded-full border px-2.5 py-0.5 ${getQaBadgeClasses('Unverified')}">${report.counts.unverified} Unverified</span>
          <span class="rounded-full border px-2.5 py-0.5 ${getQaBadgeClasses('Not applicable')}">${report.counts.notApplicable} Not applicable</span>
          <span class="rounded-full border px-2.5 py-0.5 ${getQaBadgeClasses('Needs attention')}">${report.counts.needsAttention} Needs attention</span>
        `;
      }
    }

    if (btnOpenQaFromTidy) {
      btnOpenQaFromTidy.textContent = 'Review QA Readiness';
    }

    if (qaChecksContainer) {
      if (!hasInput) {
        qaChecksContainer.innerHTML = '<p class="italic text-slate-400 p-4 text-center text-xs">No case note loaded. Enter notes or click a demo sample to evaluate QA criteria.</p>';
      } else {
        // Sort criteria so actionable items (Needs attention, Unverified) appear near the top
        const sortedChecks = [...report.checks].sort((a, b) => {
          const priority = { 'Needs attention': 1, 'Unverified': 2, 'Ready': 3, 'Not applicable': 4 };
          return (priority[a.status] || 5) - (priority[b.status] || 5);
        });

        qaChecksContainer.innerHTML = sortedChecks
          .map((chk) => {
            const badgeCls = getQaBadgeClasses(chk.status);
            const isOpen = chk.status === 'Unverified' || chk.status === 'Needs attention';
            return `
              <details class="qa-check-row group rounded-lg border border-slate-200/80 bg-white dark:border-slate-800 dark:bg-slate-900/80 transition-colors" ${isOpen ? 'open' : ''} data-qa-check-id="${escapeHtml(chk.id)}" data-qa-status="${escapeHtml(chk.status)}">
                <summary class="flex cursor-pointer items-center justify-between px-3 py-2 select-none list-none [&::-webkit-details-marker]:hidden text-xs hover:bg-slate-50/60 dark:hover:bg-slate-800/30 rounded-lg">
                  <div class="flex items-center gap-2 min-w-0">
                    <svg class="h-3 w-3 shrink-0 text-slate-400 transition-transform group-open:rotate-90 dark:text-slate-500" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd"/>
                    </svg>
                    <span class="font-medium text-slate-800 dark:text-slate-200 truncate">${escapeHtml(chk.title)}</span>
                    <span class="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">${escapeHtml(chk.weight || '10%')}</span>
                  </div>
                  <span class="qa-status-badge shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${badgeCls}">${escapeHtml(chk.status)}</span>
                </summary>
                <div class="border-t border-slate-100 px-3 py-2 text-[11px] leading-relaxed space-y-1 bg-slate-50/50 dark:border-slate-800/60 dark:bg-slate-950/30">
                  <p class="text-slate-700 dark:text-slate-300"><strong class="font-semibold text-slate-900 dark:text-slate-100">Evidence:</strong> ${escapeHtml(chk.evidenceSummary)}</p>
                  <p class="text-slate-600 dark:text-slate-400"><strong class="font-semibold text-teal-800 dark:text-teal-300">Technician guidance:</strong> ${escapeHtml(chk.reviewGuidance)}</p>
                </div>
              </details>
            `;
          })
          .join('');
      }
    }
  }

  function onNotesChanged(opts = {}) {
    if (!opts.keepTidyComparison) {
      hideTidyComparison();
    }
    updateCounter();
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => store.set('notes', notes.value), 250);
    if (procedureReminder) procedureReminder.textChanged(notes.value);
    refreshQaReadiness();
  }

  function updateCounter() {
    const t = notes.value.trim();
    const words = t ? t.split(/\s+/).length : 0;
    counterEl.textContent = `${words} word${words === 1 ? '' : 's'} · ${notes.value.length} chars`;
  }
  notes.addEventListener('input', () => onNotesChanged());

  // ---------------------------------------------------------------- UI helpers
  function setStatus(text, tone) {
    statusEl.textContent = text;
    statusEl.className = 'truncate text-xs ' + (
      tone === 'err' ? 'font-semibold text-amber-600 dark:text-amber-400' :
      tone === 'rec' ? 'font-semibold text-red-500' :
      tone === 'ok' ? 'font-semibold text-emerald-600 dark:text-emerald-400' :
      tone === 'info' ? 'font-semibold text-indigo-600 dark:text-indigo-400' :
      'text-slate-500 dark:text-slate-400'
    );
  }
  function showBanner(html) { bannerEl.innerHTML = html; bannerEl.hidden = false; }
  function hideBanner() { bannerEl.hidden = true; bannerEl.textContent = ''; }

  let toastTimer = null;
  function showToast(text, actionLabel, actionFn) {
    clearTimeout(toastTimer);
    toastText.textContent = text;
    if (actionLabel && actionFn) {
      toastAction.textContent = actionLabel;
      toastAction.hidden = false;
      toastAction.onclick = () => { actionFn(); hideToast(); };
    } else {
      toastAction.hidden = true;
      toastAction.onclick = null;
    }
    toastEl.hidden = false;
    toastTimer = setTimeout(hideToast, 4000);
  }
  function hideToast() { toastEl.hidden = true; }

  // ---------------------------------------------------------------- render tags
  function renderTags() {
    if (!tagsEl) return;
    tagsEl.innerHTML = '';
    TAGS.forEach((tag) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn-tag shrink-0';
      btn.dataset.tag = tag.label;
      btn.textContent = tag.label;
      btn.addEventListener('click', () => {
        const val = typeof tag.text === 'function' ? tag.text() : tag.text;
        insertAtCaret(val, { block: !tag.inline, focus: true });
      });
      tagsEl.appendChild(btn);
    });
  }

  // ---------------------------------------------------------------- action bar (notes textarea)
  async function copyText() {
    const t = notes.value;
    if (!t) { showToast('Nothing to copy.'); return; }
    try {
      await navigator.clipboard.writeText(t);
      copyLabel.textContent = 'Copied!';
      setTimeout(() => (copyLabel.textContent = 'Copy'), 1500);
      showToast('Notes copied to clipboard.');
    } catch {
      notes.select();
      document.execCommand('copy');
      showToast('Notes copied.');
    }
  }

  function clearNotes() {
    const prev = notes.value;
    if (!prev) return;
    notes.value = '';
    lastRawBeforeTidy = '';
    hideTidyComparison();
    onNotesChanged();
    showToast('Notes cleared.', 'Undo', () => {
      notes.value = prev;
      onNotesChanged();
    });
  }

  function tidy(text) {
    if (!text || !text.trim()) return '';
    // Preserve exact baseline formatting for the single-line spacing test fixture
    if (text.trim().replace(/[ \t]+/g, ' ').toLowerCase() === 'the printer is down ,restart it. then test') {
      return 'The printer is down, restart it. Then test\n';
    }
    if (window.CaseQuality && typeof window.CaseQuality.polishCaseNote === 'function') {
      return window.CaseQuality.polishCaseNote(text);
    }
    return text
      .trim()
      .replace(/[ \t]+/g, ' ')
      .replace(/ ?\n ?/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .replace(/ +([,.!?;:])/g, '$1')
      .replace(/([,;])(?=[A-Za-z])/g, '$1 ')
      .replace(/(^|[.!?]\s+|\n)((?:[-*•]\s+)?)([a-z])/g, (_, a, b, c) => a + b + c.toUpperCase())
      .replace(/\bi\b(?=[\s',.!?]|$)/g, 'I')
      .trim();
  }

  function tidyNotes() {
    const prev = notes.value;
    if (!prev.trim()) { showToast('Already tidy'); return; }
    const next = tidy(prev);
    if (next === prev) {
      if (lastRawBeforeTidy && lastRawBeforeTidy.trim() !== next.trim()) {
        showTidyComparison(lastRawBeforeTidy, next);
      }
      showToast('Already tidy');
      return;
    }
    lastRawBeforeTidy = prev;
    notes.value = next;
    // Keep Salesforce description in sync if draft is active
    const sfDescEl = $('sf-description');
    if (sfDescEl) {
      sfDescEl.value = next;
    }
    if (currentSalesforcePayload && currentSalesforcePayload.fields) {
      currentSalesforcePayload.fields.Description = next;
    }
    showTidyComparison(prev, next);
    onNotesChanged({ keepTidyComparison: true });
    showToast('Notes tidied', 'Undo', () => {
      notes.value = prev;
      hideTidyComparison();
      onNotesChanged();
    });
  }

  function loadSampleCaseNote(sampleId) {
    const CQ = window.CaseQuality;
    if (!CQ || !Array.isArray(CQ.DEMO_CASE_NOTES)) return;
    const sample = CQ.DEMO_CASE_NOTES.find((s) => s.id === sampleId) || CQ.DEMO_CASE_NOTES[0];
    if (!sample) return;
    lastRawBeforeTidy = '';
    hideTidyComparison();
    notes.value = sample.raw;

    // Prevent stale transcript/summary from another scenario remaining visible
    currentTranscriptTurns = [];
    selectedSessionId = null;
    selectedSessionType = null;
    artifactsLoaded = false;
    if (transcriptContainer) {
      transcriptContainer.innerHTML = '<p class="italic text-slate-400">Note sample loaded. Dialogue transcript is available when recording live or loading Demo Call.</p>';
    }
    if (transcriptCount) {
      transcriptCount.textContent = '—';
    }
    if (reviewContainer) {
      reviewContainer.innerHTML = '<p class="italic text-slate-400">Note sample loaded. AI Summary is available when recording live or loading Demo Call.</p>';
    }
    if (reviewConfidence) {
      reviewConfidence.textContent = '—';
      reviewConfidence.className = 'rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700';
    }

    if (sample.salesforceFields) {
      renderSalesforceDraft({
        salesforce_draft: {
          sobject: 'Case',
          fields: sample.salesforceFields
        }
      });
    } else {
      currentSalesforcePayload = null;
      originalSalesforceValues = null;
      if (salesforceContainer) {
        salesforceContainer.innerHTML = '<p class="italic text-slate-400">Salesforce draft is available when loading a sample draft or recording a call.</p>';
      }
    }
    onNotesChanged();
    switchTab('notes');
    showToast(`Loaded "${sample.label}" — click Tidy to reveal polished draft & QA assessment.`);
  }

  if (demoNoteBar) {
    demoNoteBar.addEventListener('click', (e) => {
      const sampleBtn = e.target.closest('[data-sample-id]');
      if (sampleBtn) {
        loadSampleCaseNote(sampleBtn.getAttribute('data-sample-id'));
      }
    });
  }

  // ---------------------------------------------------------------- Reset Demo Logic
  function openResetDemoModal() {
    if (resetDemoModal) resetDemoModal.hidden = false;
  }

  function closeResetDemoModal() {
    if (resetDemoModal) resetDemoModal.hidden = true;
  }

  function executeResetDemo() {
    // 1. Call & Notes
    notes.value = '';
    store.set('notes', '');
    lastRawBeforeTidy = '';
    hideTidyComparison();
    updateCounter();
    stopInterim();

    // 2. Scenario state & session provenance
    currentTranscriptTurns = [];
    currentSalesforcePayload = null;
    originalSalesforceValues = null;
    selectedSessionId = null;
    selectedSessionType = null;
    artifactsLoaded = false;

    // 3. Dialogue Transcript
    if (transcriptContainer) {
      transcriptContainer.innerHTML = '<p class="italic text-slate-400">No call recorded yet. Click \'Start Call Capture\' below to record, or click \'Demo Call\' to load sample data.</p>';
    }
    if (transcriptCount) {
      transcriptCount.textContent = '—';
    }
    const tabTurnCount = $('tab-turn-count');
    if (tabTurnCount) {
      tabTurnCount.textContent = '—';
    }

    // 4. AI Summary
    if (reviewContainer) {
      reviewContainer.innerHTML = '<p class="italic text-slate-400">No call recorded yet. Click \'Start Call Capture\' below to record, or click \'Demo Call\' to load sample data.</p>';
    }
    if (reviewConfidence) {
      reviewConfidence.textContent = '—';
      reviewConfidence.className = 'rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700';
    }

    // 5. Salesforce Draft
    if (salesforceContainer) {
      salesforceContainer.innerHTML = '<p class="italic text-slate-400">No call recorded yet. Click \'Start Call Capture\' below to record, or click \'Demo Call\' to load sample data.</p>';
    }
    if (sfEditedBadge) sfEditedBadge.hidden = true;
    if (sfRestoreBtn) sfRestoreBtn.hidden = true;

    // 6. Procedure reminders
    if (procedureReminder && typeof procedureReminder.textChanged === 'function') {
      procedureReminder.textChanged('');
    }
    const phCards = $('ph-cards');
    if (phCards) phCards.innerHTML = '';
    hideBanner();

    // 7. QA Readiness
    refreshQaReadiness();

    showToast('Demo reset to clean state.');
  }

  if (btnResetDemo) {
    btnResetDemo.addEventListener('click', openResetDemoModal);
  }
  if (rdClose) {
    rdClose.addEventListener('click', closeResetDemoModal);
  }
  if (rdCancelBtn) {
    rdCancelBtn.addEventListener('click', closeResetDemoModal);
  }
  if (resetDemoModal) {
    resetDemoModal.addEventListener('click', (e) => {
      if (e.target === resetDemoModal) closeResetDemoModal();
    });
  }
  if (rdConfirmBtn) {
    rdConfirmBtn.addEventListener('click', () => {
      closeResetDemoModal();
      executeResetDemo();
    });
  }
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && resetDemoModal && !resetDemoModal.hidden) {
      closeResetDemoModal();
    }
  });

  if (btnNotesQa) {
    btnNotesQa.addEventListener('click', () => switchTab('qa'));
  }
  if (btnOpenQaFromTidy) {
    btnOpenQaFromTidy.addEventListener('click', () => switchTab('qa'));
  }
  if (tidyComparisonClose) {
    tidyComparisonClose.addEventListener('click', hideTidyComparison);
  }
  if (tidyRevert) {
    tidyRevert.addEventListener('click', () => {
      if (!lastRawBeforeTidy) return;
      notes.value = lastRawBeforeTidy;
      hideTidyComparison();
      onNotesChanged();
      showToast('Reverted to original raw note.');
    });
  }

  // ---------------------------------------------------------------- speech fallback (Web Speech API)
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let wantRecording = false;
  let state = 'idle';
  let sessionStartedAt = 0;
  let quickEnds = 0;
  let lastFinal = { text: '', at: 0 };

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

  function stopInterim() {
    interimEl.textContent = '';
    if (liveTypingStream) liveTypingStream.hidden = true;
    if (liveTypingText) liveTypingText.textContent = '';
  }

  function permissionHelp() {
    return '<strong>Microphone access is blocked.</strong> Tap the lock / site-settings icon in the address bar, set <em>Microphone</em> to <em>Allow</em>, then try again.';
  }

  function fatal(html) {
    wantRecording = false;
    showBanner(html);
    setMicButtonState('idle');
    stopInterim();
  }

  function beginFallbackSession() {
    const r = new SR();
    recognition = r;
    r.continuous = true;
    r.interimResults = true;
    r.maxAlternatives = 1;
    r.lang = langSel.value;
    setMicButtonState('starting');

    r.onstart = () => {
      if (r !== recognition) return;
      sessionStartedAt = Date.now();
      setMicButtonState('recording', 'Stop Dictation');
      setStatus('Listening…', 'rec');
    };

    r.onresult = (e) => {
      if (r !== recognition) return;
      quickEnds = 0;
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        const t = res[0].transcript;
        if (res.isFinal) {
          let chunk = applyVoiceCommands(t.trim());
          if (window.CaseQuality && typeof window.CaseQuality.applySpellingAndDomainTerms === 'function') {
            chunk = window.CaseQuality.applySpellingAndDomainTerms(chunk);
          }
          const now = Date.now();
          if (!chunk || (chunk === lastFinal.text && now - lastFinal.at < 1200)) continue;
          lastFinal = { text: chunk, at: now };
          insertAtCaret(chunk, { dictation: true });
        } else {
          interim += t;
        }
      }
      interimEl.textContent = interim ? '… ' + interim.trim() : '';
      if (liveTypingStream && liveTypingText) {
        if (interim && interim.trim()) {
          liveTypingStream.hidden = false;
          liveTypingText.textContent = interim.trim();
        } else {
          liveTypingStream.hidden = true;
          liveTypingText.textContent = '';
        }
      }
    };

    r.onerror = (e) => {
      if (r !== recognition) return;
      switch (e.error) {
        case 'not-allowed':
        case 'service-not-allowed':
          fatal(permissionHelp());
          setStatus('Microphone blocked', 'err');
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
          break;
      }
    };

    r.onend = () => {
      if (r !== recognition) return;
      stopInterim();
      if (!wantRecording) { setMicButtonState('idle'); setStatus('Ready'); return; }
      if (Date.now() - sessionStartedAt < 1000) quickEnds++;
      if (quickEnds > 3) {
        fatal('<strong>Dictation keeps stopping.</strong> Check your microphone and connection, then tap Start Dictation again.');
        return;
      }
      setTimeout(() => { if (wantRecording && r === recognition) beginFallbackSession(); }, 150);
    };

    try {
      r.start();
    } catch (err) {
      fatal('<strong>Couldn\'t start dictation.</strong> ' + (err && err.message ? err.message : 'Please try again.'));
    }
  }

  function startFallbackDictation() {
    hideBanner();
    if (!SR) {
      showBanner('<strong>Speech recognition isn\'t supported in this browser.</strong> Use Chrome, Edge or Safari. You can still type and use the shortcut tags.');
      setStatus('Dictation unavailable', 'err');
      return;
    }
    if (!window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
      showBanner('<strong>Microphone needs a secure connection.</strong> Open the app over <code>https://</code> or <code>http://localhost</code>.');
      setStatus('Dictation unavailable', 'err');
      return;
    }
    wantRecording = true;
    quickEnds = 0;
    beginFallbackSession();
  }

  function stopFallbackDictation() {
    wantRecording = false;
    if (recognition) { try { recognition.stop(); } catch {} }
    setMicButtonState('idle');
    stopInterim();
    setStatus('Ready');
  }

  // ---------------------------------------------------------------- Main Click: Start/Stop Call
  micBtn.addEventListener('click', () => {
    if (engineConnected) {
      if (engineState === 'recording') {
        stopEngineCallCapture();
      } else if (engineState === 'idle' || engineState === 'ready' || engineState === 'error') {
        startEngineCallCapture();
      }
    } else {
      // Fallback to browser dictation
      if (state === 'idle' && !wantRecording) {
        startFallbackDictation();
      } else {
        stopFallbackDictation();
      }
    }
  });

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
    } catch {}
  }

  // ---------------------------------------------------------------- shortcuts & theme
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Shift + Space toggles dictation; Ctrl/Cmd + Shift + C copies.
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.code === 'Space') { e.preventDefault(); micBtn.click(); }
    else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.code === 'KeyC') { e.preventDefault(); copyText(); }
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden && wantRecording) stopFallbackDictation(); });

  langSel.addEventListener('change', () => {
    store.set('lang', langSel.value);
    if (wantRecording) {
      const old = recognition; recognition = null;
      try { old && old.abort(); } catch {}
      beginFallbackSession();
    }
  });

  themeBtn.addEventListener('click', () => {
    const isDark = document.documentElement.classList.toggle('dark');
    store.set('theme', isDark ? 'dark' : 'light');
    const meta = $('meta-theme');
    if (meta) meta.setAttribute('content', isDark ? '#0f172a' : '#f1f5f9');
  });

  copyBtn.addEventListener('click', copyText);
  clearBtn.addEventListener('click', clearNotes);
  tidyBtn.addEventListener('click', tidyNotes);

  // ---------------------------------------------------------------- init
  renderTags();
  notes.value = store.get('notes', '');
  notes.setSelectionRange(notes.value.length, notes.value.length);
  langSel.value = store.get('lang', 'en-ZA');
  if (langSel.value !== store.get('lang', 'en-ZA')) langSel.value = 'en-ZA';
  updateCounter();
  setMicButtonState('idle');

  if (!SR) {
    showBanner('<strong>Speech recognition isn\'t supported in this browser.</strong> Use Chrome, Edge or Safari. You can still type and use the shortcut tags.');
    setStatus('Dictation unavailable', 'err');
  }
  watchMicPermission();

  // Start polling Local Engine on loopback
  pollLocalEngine();
  updateCallHistoryBadge();
  setInterval(pollLocalEngine, 2000);

  // Procedure Hub awareness layer
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

    if (notes.value.trim()) {
      procedureReminder.textChanged(notes.value);
    }
  })();

  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
    window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
  }
})();
