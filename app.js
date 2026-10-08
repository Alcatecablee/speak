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
  const tabNotes = $('tab-notes');
  const tabTranscript = $('tab-transcript');
  const tabReview = $('tab-review');
  const tabSalesforce = $('tab-salesforce');

  const panelNotes = $('panel-notes');
  const panelTranscript = $('panel-transcript');
  const panelReview = $('panel-review');
  const panelSalesforce = $('panel-salesforce');

  const transcriptContainer = $('transcript-container');
  const transcriptCount = $('transcript-count');
  const reviewContainer = $('review-container');
  const reviewConfidence = $('review-confidence');
  const salesforceContainer = $('salesforce-container');
  const copySfBtn = $('copy-sf-btn');
  const btnLoadSample = $('btn-load-sample');

  // Processing Stepper elements
  const processingCard = $('processing-card');
  const processingTitle = $('processing-title');
  const processingSubtitle = $('processing-subtitle');
  const processingTimer = $('processing-timer');
  const processingStepper = $('processing-stepper');
  const processingActions = $('processing-actions');
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
  let artifactsLoaded = false;

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

  const DEMO_SALESFORCE_PAYLOAD = {
    sobject: "Case",
    action: "DRAFT_UPDATE",
    human_review_status: "PENDING_CONSULTANT_APPROVAL",
    requires_consultant_confirmation: true,
    fields: {
      Subject: "Production Recipe Variance - 20288 2622 2622",
      Description: "[DRAFT CASE RECORD - GENERATED BY SPEAK V2 - REVIEW REQUIRED]\nREASON FOR CONTACT:\nClient requested assistance with production batch variance discrepancies (cheesecake slices vs whole unit) and butternut puree unit configuration.\n\nPRIMARY ISSUE:\nCheesecake batch variance deducting whole unit instead of slice portions.\n\nCONFIRMED ACTIONS & COMMITMENTS:\n- [COMPLETED_ACTION] Consultant connected remotely to client workstation (Owner: CONSULTANT)\n- [COMPLETED_ACTION] Client demonstrated variance calculation on screen with test values (Owner: CLIENT)\n- [COMPLETED_ACTION] Consultant diagnosed unit of measure configuration mismatch (Owner: CONSULTANT)\n- [PROPOSED_ACTION] Consultant proposed potential escalation to software support department (Owner: CONSULTANT)\n- [CONFIRMED_COMMITMENT] Consultant committed to investigate cheesecake recipe configuration and call client back (Owner: CONSULTANT)\n\nFOLLOW UP REQUIRED: YES\nFOLLOW UP DETAILS: Consultant to investigate cheesecake production configuration and call client back with update/fix. (Timeframe: Within 15 minutes)\n\nRESOLUTION STATUS: FOLLOW_UP_REQUIRED\nRESOLUTION BASIS: Consultant confirmed a follow-up callback commitment (Within 15 minutes) to finalize recipe configuration.",
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

  async function pollLocalEngine() {
    if (!window.__enableEngineInTest && (typeof window.__instances === 'function' || typeof window.__emit === 'function' || navigator.webdriver)) {
      return;
    }
    try {
      const res = await fetch(`${LOCAL_ENGINE_URL}/status`, { signal: AbortSignal.timeout(1500) });
      if (res.ok) {
        const data = await res.json();
        setEngineConnectionState(true, data);
      } else {
        setEngineConnectionState(false);
      }
    } catch {
      setEngineConnectionState(false);
    }
  }

  function setEngineConnectionState(connected, data = null) {
    engineConnected = connected;
    if (tagsNav) tagsNav.hidden = connected;
    if (connected) {
      engineDot.className = 'h-2 w-2 rounded-full bg-emerald-500 animate-pulse';
      engineText.textContent = 'Engine Connected';
      engineText.className = 'font-semibold text-emerald-600 dark:text-emerald-400';
      if (data) {
        handleEngineStatusUpdate(data);
      }
    } else {
      engineDot.className = 'h-2 w-2 rounded-full bg-amber-500';
      engineText.textContent = 'Engine Offline';
      engineText.className = 'text-slate-500 dark:text-slate-400';
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
    } else if (isError) {
      processingTitle.textContent = 'PROCESSING FAILED';
      processingTitle.className = 'text-xs font-bold uppercase tracking-wider text-red-600 dark:text-red-400';
      processingSubtitle.textContent = data.error || 'Pipeline encountered an unexpected error.';
      processingTimer.textContent = 'Failed';
      if (processingActions) processingActions.hidden = true;
    } else {
      processingTitle.textContent = 'PROCESSING CALL';
      processingTitle.className = 'text-xs font-bold uppercase tracking-wider text-teal-600 dark:text-teal-400';
      processingSubtitle.textContent = data.message || 'Dual-stream capture finalized · Running local pipeline on CPU';
      processingTimer.textContent = `Elapsed: ${formatDuration(data.elapsed_seconds || 0)}`;
      if (processingActions) processingActions.hidden = true;
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
        titleClass = 'text-emerald-900 dark:text-emerald-300 font-semibold';
        subtext = '<p class="text-[11px] text-emerald-700 dark:text-emerald-400 mt-0.5">Complete</p>';
      } else if (isActive) {
        itemClass = 'proc-item-active';
        badgeClass = 'proc-badge-active';
        icon = '●';
        titleClass = 'text-amber-900 dark:text-amber-300 font-bold';
        subtext = `<p class="text-[11px] text-amber-800 dark:text-amber-200 mt-0.5 font-medium">${escapeHtml(data.message || stage.desc)}</p>`;
      } else if (isFailed) {
        itemClass = 'proc-item-failed';
        badgeClass = 'proc-badge-failed';
        icon = '✕';
        titleClass = 'text-red-900 dark:text-red-300 font-bold';
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
      activeSessionId = data.session_id || activeSessionId;
      activeSessionType = data.session_type || 'live';
      fetchAndRenderEngineArtifacts(activeSessionId);
      showToast('Live call analysis ready! Review before Salesforce update.');
    } else if (data.status === 'ready') {
      setMicButtonState('idle', 'Start Call Capture');
    } else if (data.status === 'error') {
      if (prev === 'processing') {
        renderProcessingStepper(data);
      }
      setMicButtonState('idle', 'Start Call Capture');
      setStatus(`Engine error: ${data.error || 'Unknown error'}`, 'err');
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

  let activeSessionId = null;
  let activeSessionType = 'none'; // 'live', 'demo', 'none'

  async function startEngineCallCapture() {
    try {
      setStatus('Connecting to audio streams…');
      const res = await fetch(`${LOCAL_ENGINE_URL}/capture/start`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Could not start capture');
      }
      const resData = await res.json();
      activeSessionId = resData.session_id || null;
      activeSessionType = 'live';
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
      transcriptContainer.innerHTML = `<p class="italic text-slate-400">Recording live call (Session: ${escapeHtml(activeSessionId || '')})… transcript will generate upon stopping capture.</p>`;
      transcriptCount.textContent = 'Recording…';
      reviewContainer.innerHTML = `<p class="italic text-slate-400">Recording live call (Session: ${escapeHtml(activeSessionId || '')})… AI analysis will generate upon stopping capture.</p>`;
      reviewConfidence.textContent = '—';
      reviewConfidence.className = 'rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700';
      salesforceContainer.innerHTML = `<p class="italic text-slate-400">Recording live call (Session: ${escapeHtml(activeSessionId || '')})… Salesforce draft will generate upon stopping capture.</p>`;
    } catch (e) {
      showToast(`Failed to start capture: ${e.message}`);
      setStatus('Capture failed', 'err');
    }
  }

  async function stopEngineCallCapture() {
    clearInterval(engineSessionTimer);
    setMicButtonState('processing', 'Stopping capture & transcribing…');
    setStatus('Finalizing audio files…', 'info');
    try {
      const res = await fetch(`${LOCAL_ENGINE_URL}/capture/stop`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Could not stop capture');
      }
      engineState = 'processing';
      pollLocalEngine();
    } catch (e) {
      showToast(`Failed to stop capture: ${e.message}`);
      setMicButtonState('idle');
    }
  }

  async function fetchAndRenderEngineArtifacts(sessionId = null) {
    const targetSession = sessionId || activeSessionId;
    const sessionQuery = targetSession ? `?session_id=${encodeURIComponent(targetSession)}` : '';
    try {
      // 1. Fetch transcript
      const resTrans = await fetch(`${LOCAL_ENGINE_URL}/transcript${sessionQuery}`);
      if (!resTrans.ok) {
        const err = await resTrans.json();
        throw new Error(`Transcript fetch failed: ${err.detail || resTrans.statusText}`);
      }
      const transData = await resTrans.json();
      if (transData.session_id && targetSession && transData.session_id !== targetSession) {
        throw new Error(`Session mismatch: received ${transData.session_id}, expected ${targetSession}`);
      }
      renderTranscript(transData.data);

      // 2. Fetch analysis & review
      const resReview = await fetch(`${LOCAL_ENGINE_URL}/review${sessionQuery}`);
      if (!resReview.ok) {
        const err = await resReview.json();
        throw new Error(`Review fetch failed: ${err.detail || resReview.statusText}`);
      }
      const reviewData = await resReview.json();
      renderReview(reviewData);

      // 3. Fetch structured analysis JSON
      const resAnalysis = await fetch(`${LOCAL_ENGINE_URL}/analysis${sessionQuery}`);
      if (resAnalysis.ok) {
        const analysisData = await resAnalysis.json();
        if (analysisData.data && analysisData.data.confidence) {
          reviewConfidence.textContent = `Confidence: ${analysisData.data.confidence.level} (${Math.round(analysisData.data.confidence.score * 100)}%)`;
          reviewConfidence.className = 'rounded-full bg-teal-100 px-2.5 py-0.5 text-[11px] font-semibold text-teal-800 dark:bg-teal-950 dark:text-teal-300 border border-teal-200 dark:border-teal-800';
        }
      }
      artifactsLoaded = true;
    } catch (e) {
      console.error('Error fetching live session artifacts:', e);
      setStatus(`Artifact error: ${e.message}`, 'err');
      showToast(`Could not load session results: ${e.message}`, 'Retry', () => fetchAndRenderEngineArtifacts(targetSession));
    }
  }

  function renderTranscript(transJson) {
    if (!transJson || !transJson.merged_turns) return;
    artifactsLoaded = true;
    const turns = transJson.merged_turns;
    transcriptCount.textContent = `${turns.length} turns`;

    let html = '';
    turns.forEach((t) => {
      const isConsultant = t.speaker === 'CONSULTANT';
      const bg = isConsultant ? 'bg-teal-50 dark:bg-teal-950/40 border-teal-200 dark:border-teal-800' : 'bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700';
      const badge = isConsultant ? 'bg-teal-600 text-white' : 'bg-indigo-600 text-white';
      html += `
        <div class="rounded-xl border p-2.5 ${bg}">
          <div class="flex items-center justify-between gap-2 mb-1">
            <span class="rounded px-1.5 py-0.5 text-[10px] font-bold ${badge}">${t.speaker}</span>
            <span class="text-[10px] text-slate-400 font-mono">${t.timestamp_str || ''}</span>
          </div>
          <p class="text-xs text-slate-800 dark:text-slate-200 leading-relaxed">${escapeHtml(t.text)}</p>
        </div>
      `;
    });
    transcriptContainer.innerHTML = html || '<p class="italic text-slate-400">Empty transcript.</p>';

    // Trigger Procedure Hub evaluation on transcript text
    const fullTranscriptText = turns.map((t) => t.text).join(' ');
    triggerProcedureContext(fullTranscriptText);
  }

  function renderReview(reviewData) {
    if (!reviewData) return;
    artifactsLoaded = true;
    
    // Render Markdown summary nicely
    const md = reviewData.markdown || '';
    reviewContainer.innerHTML = formatSimpleMarkdown(md);

    // Trigger Procedure Hub evaluation on review summary
    triggerProcedureContext(md);

    // Render Salesforce Draft
    currentSalesforcePayload = reviewData.salesforce_draft;
    if (currentSalesforcePayload) {
      const f = currentSalesforcePayload.fields || currentSalesforcePayload;
      const subject = f.Subject || f.subject || '';
      const description = f.Description || f.description || '';
      const status = f.Status || f.status || 'Pending';
      const remoteId = f.Remote_Connection_ID__c || f.remote_connection_id || 'N/A';
      salesforceContainer.innerHTML = `
        <div class="space-y-3">
          <div class="rounded-xl border border-amber-300 bg-amber-50 p-3 dark:border-amber-700/60 dark:bg-amber-950/40 text-amber-900 dark:text-amber-200">
            <p class="font-bold text-xs">Human Review Boundary</p>
            <p class="text-[11px]">This case update was automatically generated. Review and click "Copy Case Record" to paste into Salesforce.</p>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="p-2 rounded-lg bg-slate-100 dark:bg-slate-800">
              <span class="text-slate-400 font-semibold block text-[10px]">CASE STATUS</span>
              <span class="font-bold text-slate-800 dark:text-slate-200">${escapeHtml(status)}</span>
            </div>
            <div class="p-2 rounded-lg bg-slate-100 dark:bg-slate-800">
              <span class="text-slate-400 font-semibold block text-[10px]">REMOTE CONNECTION ID</span>
              <span class="font-bold text-slate-800 dark:text-slate-200">${escapeHtml(remoteId)}</span>
            </div>
          </div>
          <div>
            <label class="font-bold text-xs block mb-1">Subject</label>
            <input type="text" readonly value="${escapeHtml(subject)}" class="w-full rounded-lg border border-slate-300 bg-slate-50 p-2 text-xs font-semibold dark:border-slate-700 dark:bg-slate-800" />
          </div>
          <div>
            <label class="font-bold text-xs block mb-1">Case Description (CRM Update)</label>
            <textarea readonly rows="8" class="w-full rounded-lg border border-slate-300 bg-slate-50 p-2 text-xs font-mono leading-relaxed dark:border-slate-700 dark:bg-slate-800">${escapeHtml(description)}</textarea>
          </div>
        </div>
      `;
    }
  }

  function escapeHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function formatSimpleMarkdown(text) {
    let out = escapeHtml(text);
    // Headers
    out = out.replace(/^# (.*?)$/gm, '<h1 class="text-base font-bold text-slate-900 dark:text-slate-100 mt-2 mb-1 border-b pb-1">$1</h1>');
    out = out.replace(/^## (.*?)$/gm, '<h2 class="text-sm font-bold text-slate-800 dark:text-slate-200 mt-3 mb-1 text-teal-700 dark:text-teal-400">$1</h2>');
    // Blockquotes & Alerts
    out = out.replace(/^> \[\!(.*?)\]\n> (.*?)$/gm, '<div class="my-2 p-2 rounded-lg bg-teal-50 dark:bg-teal-950/40 border-l-4 border-teal-500 text-xs"><strong>$1:</strong> $2</div>');
    out = out.replace(/^> (.*?)$/gm, '<blockquote class="my-2 p-2 rounded-lg bg-slate-100 dark:bg-slate-800/80 border-l-4 border-slate-400 text-xs italic">$1</blockquote>');
    // Bold / Code
    out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/`(.*?)`/g, '<code class="px-1 py-0.5 rounded bg-slate-200 dark:bg-slate-800 font-mono text-[11px]">$1</code>');
    // Bullet items
    out = out.replace(/^\- (.*?)$/gm, '<li class="ml-4 list-disc">$1</li>');
    out = out.replace(/^\* (.*?)$/gm, '<li class="ml-4 list-disc">$1</li>');
    // Tables
    out = out.replace(/\|(.+)\|/g, (match) => {
      const cells = match.split('|').filter((c) => c.trim() !== '');
      if (cells.some((c) => c.includes('---'))) return '';
      return `<div class="flex gap-2 text-[11px] py-1 border-b dark:border-slate-800">${cells.map((c) => `<span class="flex-1">${c.trim()}</span>`).join('')}</div>`;
    });
    return out.replace(/\n\n/g, '<br/>');
  }

  // ---------------------------------------------------------------- Tab Navigation
  function switchTab(tabId) {
    if (processingCard) processingCard.hidden = true;

    const tabs = [
      { id: 'notes', btn: tabNotes, panel: panelNotes },
      { id: 'transcript', btn: tabTranscript, panel: panelTranscript },
      { id: 'review', btn: tabReview, panel: panelReview },
      { id: 'salesforce', btn: tabSalesforce, panel: panelSalesforce },
    ];

    tabs.forEach((t) => {
      const active = t.id === tabId;
      t.panel.hidden = !active;
      t.btn.className = active ? 'tab-item-active' : 'tab-item';
    });

    if (tagsNav) tagsNav.hidden = tabId !== 'notes' || engineConnected;
  }

  tabNotes.addEventListener('click', () => switchTab('notes'));
  tabTranscript.addEventListener('click', () => switchTab('transcript'));
  tabReview.addEventListener('click', () => switchTab('review'));
  tabSalesforce.addEventListener('click', () => switchTab('salesforce'));

  if (btnViewTranscript) {
    btnViewTranscript.addEventListener('click', () => switchTab('transcript'));
  }
  if (btnViewReview) {
    btnViewReview.addEventListener('click', () => switchTab('review'));
  }
  if (btnViewSf) {
    btnViewSf.addEventListener('click', () => switchTab('salesforce'));
  }

  // ---------------------------------------------------------------- Demo & Copy Actions
  async function loadDemoCall() {
    showToast('Loading demo call sample…');
    if (engineConnected) {
      try {
        const res = await fetch(`${LOCAL_ENGINE_URL}/demo/load-sample`, { method: 'POST' });
        if (res.ok) {
          const resData = await res.json();
          activeSessionId = resData.session_id || 'sample_real_call_demo';
          activeSessionType = 'demo';
          await fetchAndRenderEngineArtifacts(activeSessionId);
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
      activeSessionId = 'demo_client_offline';
      activeSessionType = 'demo';
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

  btnLoadSample.addEventListener('click', () => {
    loadDemoCall();
  });

  copySfBtn.addEventListener('click', () => {
    if (!currentSalesforcePayload || !currentSalesforcePayload.fields) {
      showToast('No Salesforce payload to copy.');
      return;
    }
    const txt = currentSalesforcePayload.fields.Description || JSON.stringify(currentSalesforcePayload, null, 2);
    navigator.clipboard.writeText(txt).then(() => {
      showToast('Salesforce case record copied to clipboard!');
    }).catch(() => {
      showToast('Copy failed.');
    });
  });

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
    onNotesChanged();
    showToast('Notes cleared.', 'Undo', () => {
      notes.value = prev;
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
    if (next === prev || !prev.trim()) { showToast('Already tidy'); return; }
    notes.value = next;
    onNotesChanged();
    showToast('Notes tidied', 'Undo', () => { notes.value = prev; onNotesChanged(); });
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

  function stopInterim() { interimEl.textContent = ''; }

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
          const chunk = applyVoiceCommands(t.trim());
          const now = Date.now();
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
