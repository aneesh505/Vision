// ==========================================================================
// AegisAI - DevSecOps Autonomous Agent Frontend Controller
// Handles: Theme switching, Real-time backend API integration (/api/scan),
// Polling run status, and Dynamic UI updates based on actual scan results.
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  initTheme();
});

// --- THEME SWITCHER (Light / Dark) ---
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon(savedTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
  updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
  const themeIcon = document.getElementById('themeIcon');
  if (!themeIcon) return;
  if (theme === 'light') {
    themeIcon.setAttribute('data-lucide', 'moon');
  } else {
    themeIcon.setAttribute('data-lucide', 'sun');
  }
  lucide.createIcons();
}

// --- QUICK REPO SELECTION ---
function setSampleRepo(url) {
  document.getElementById('repoUrlInput').value = url;
}

// --- LOGGING HELPERS ---
function addAgentLog(text, color = 'text-slate-300') {
  const logs = document.getElementById('agentLogs');
  const item = document.createElement('div');
  item.className = color;
  const timestamp = new Date().toLocaleTimeString();
  item.innerText = `[${timestamp}] ${text}`;
  logs.appendChild(item);
  logs.scrollTop = logs.scrollHeight;
}

function addTerminalLine(text, color = 'text-slate-300') {
  const term = document.getElementById('sandboxTerminal');
  const item = document.createElement('p');
  item.className = color;
  item.innerText = text;
  term.appendChild(item);
  term.scrollTop = term.scrollHeight;
}

// --- PIPELINE STEPPER ---
function setStep(stepNum, status = 'active') {
  const stepEl = document.getElementById(`step-${stepNum}`);
  if (!stepEl) return;

  stepEl.classList.remove('active', 'completed');
  if (status === 'active') {
    stepEl.classList.add('active');
  } else if (status === 'completed') {
    stepEl.classList.add('completed');
  }
  document.getElementById('stepProgressBadge').innerText = `STAGE ${stepNum} / 5`;
}

// --- MAIN RUN CONTROLLER WITH REAL BACKEND CALLS ---
async function handleStartAnalysis(e) {
  e.preventDefault();
  const repoUrl = document.getElementById('repoUrlInput').value.trim();
  const branch = document.getElementById('branchInput').value.trim() || 'main';
  if (!repoUrl) return;

  const repoParts = repoUrl.replace('https://github.com/', '').split('/');
  const repoShort = repoParts.length >= 2 ? `${repoParts[0]}/${repoParts[1]}` : repoUrl;

  // Update Header Repo Target
  document.getElementById('activeRepoBadge').classList.remove('hidden');
  document.getElementById('activeRepoBadge').classList.add('flex');
  document.getElementById('headerRepoName').innerText = `target: ${repoShort} (${branch})`;

  // Disable Launch Button
  const btn = document.getElementById('startBtn');
  btn.disabled = true;
  btn.classList.add('opacity-50', 'cursor-not-allowed');

  // Reset Stats
  document.getElementById('statDetected').innerText = '0';
  document.getElementById('statProven').innerText = '0';
  document.getElementById('statRetries').innerText = '0';
  document.getElementById('statPRs').innerText = '0';

  // Live Pulse Status
  const livePulse = document.getElementById('liveStatusPulse');
  const liveText = document.getElementById('liveStatusText');
  livePulse.className = 'w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse-dot';
  liveText.innerText = 'Agent Active';
  liveText.className = 'text-xs font-mono text-cyan-400 uppercase';

  // Clear Terminal & Logs
  document.getElementById('agentLogs').innerHTML = '';
  document.getElementById('sandboxTerminal').innerHTML = '';
  document.getElementById('findingsList').innerHTML = `
    <div class="glass-card rounded-2xl p-6 text-center border border-cyan-500/25">
      <div class="inline-flex items-center justify-center p-3 rounded-xl bg-cyan-500/10 text-cyan-400 mb-2 animate-pulse">
        <i data-lucide="loader-2" class="w-6 h-6 animate-spin"></i>
      </div>
      <p class="text-sm font-semibold text-slate-200">Cloning & Analyzing Repository...</p>
      <p class="text-xs text-slate-400 mt-1">Executing Bandit, Semgrep, and LLM security audits.</p>
    </div>
  `;
  lucide.createIcons();
  document.getElementById('findingsCountLabel').innerText = 'Connecting to backend...';

  // Update Docker container tag
  const dockerTag = document.getElementById('dockerContainerTag');
  dockerTag.innerText = 'spawning...';
  dockerTag.className = 'text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded';

  // Reset all steps
  for (let i = 1; i <= 5; i++) {
    const el = document.getElementById(`step-${i}`);
    el.classList.remove('active', 'completed');
  }

  setStep(1, 'active');
  addAgentLog(`Initiating pipeline run for repository: ${repoUrl} (branch: ${branch})`, 'text-cyan-400');

  try {
    const enableBandit = document.getElementById('banditToggle')?.checked ?? true;
    const enableSemgrep = document.getElementById('semgrepToggle')?.checked ?? true;
    const enableDocker = document.getElementById('dockerToggle')?.checked ?? true;
    const enablePr = document.getElementById('prToggle')?.checked ?? true;

    // 1. Call Backend API
    const response = await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        repo_url: repoUrl,
        branch: branch,
        enable_bandit: enableBandit,
        enable_semgrep: enableSemgrep,
        enable_docker: enableDocker,
        enable_pr: enablePr
      })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Failed to start scan');

    const jobId = data.job_id;
    addAgentLog(`Scan job started (ID: ${jobId}). Polling execution status...`, 'text-slate-300');
    addTerminalLine(`$ python -m backend.pipeline --repo ${repoUrl} --branch ${branch}`, 'text-slate-500');

    // 2. Poll Backend for Status
    const pollInterval = setInterval(async () => {
      try {
        const statusRes = await fetch(`/api/runs/${jobId}`);
        if (!statusRes.ok) {
          throw new Error(statusRes.status === 404
            ? 'The scan was interrupted by a backend restart. Start a new scan.'
            : `Unable to read scan status (HTTP ${statusRes.status}).`);
        }
        const statusData = await statusRes.json();

        const status = statusData.status;

        if (status === 'completed' || status === 'clean' || status === 'failed' || status === 'patch_failed') {
          clearInterval(pollInterval);
          btn.disabled = false;
          btn.classList.remove('opacity-50', 'cursor-not-allowed');

          const result = statusData.result || {};
          const findings = result.findings || [];
          const fixes = result.fixes_applied || [];
          const findingsCount = findings.length;
          const verifiedFixes = fixes.filter(f => f.applied);
          const prCount = (result.pr_url && result.pr_url !== 'https://github.com/mock-pr-url') ? 1 : 0;
          const verify = result.verification || {};
          const verifyExitCode = (verify.exit_code !== undefined) ? verify.exit_code : null;
          const testsPassed = (verifyExitCode === 0);

          // Update real counters
          document.getElementById('statDetected').innerText = findingsCount;
          document.getElementById('statProven').innerText = testsPassed ? verifiedFixes.length : 0;
          document.getElementById('statRetries').innerText = status === 'patch_failed' ? fixes.length : '0';
          document.getElementById('statPRs').innerText = prCount;
          document.getElementById('findingsCountLabel').innerText = `${findingsCount} Vulnerabilities Discovered`;

          // Stream verification output into sandbox console
          if (verify.output) {
            addTerminalLine('--- Regression Test Output ---', 'text-slate-500');
            verify.output.split('\n').filter(Boolean).slice(-10).forEach(line => {
              addTerminalLine(line, testsPassed ? 'text-slate-300' : 'text-rose-300');
            });
          }

          if (status === 'clean') {
            setStep(1, 'completed');
            setStep(2, 'completed');
            setStep(3, 'completed');
            setStep(4, 'completed');
            setStep(5, 'completed');

            addAgentLog(`Clean scan: 0 vulnerabilities found in repository.`, 'text-emerald-400');
            addTerminalLine(`> [CLEAN] Security scan passed with 0 findings.`, 'text-emerald-400');
            dockerTag.innerText = 'idle';
            dockerTag.className = 'text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded';
            livePulse.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400';
            liveText.innerText = 'Repo Clean';
            liveText.className = 'text-xs font-mono text-emerald-400 uppercase';
            renderDynamicFindings(repoShort, [], []);
            return;
          }

          if (status === 'completed' && testsPassed) {
            setStep(1, 'completed');
            setStep(2, 'completed');
            setStep(3, 'completed');
            setStep(4, 'completed');
            setStep(5, prCount > 0 ? 'completed' : 'active');

            addAgentLog(`Remediation verified! ${verifiedFixes.length} patches applied, regression tests exit code 0.`, 'text-emerald-400');
            addTerminalLine(`> [SUCCESS] Regression test suite passed (exit code 0).`, 'text-emerald-400');
            dockerTag.innerText = 'verified (exit 0)';
            dockerTag.className = 'text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded';
            livePulse.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400';
            liveText.innerText = 'Remediated & Verified';
            liveText.className = 'text-xs font-mono text-emerald-400 uppercase';
          } else {
            // Failed verification or patch failure
            setStep(1, 'completed');
            setStep(2, 'completed');
            setStep(3, status === 'patch_failed' ? 'active' : 'completed');
            setStep(4, 'active');

            const reason = statusData.error || (status === 'patch_failed'
              ? 'LLM patch generation failed or returned invalid code.'
              : result.reason || `Regression test failed with exit code ${verifyExitCode}. Patch rejected.`);

            addAgentLog(`Pipeline halted: ${reason}`, 'text-rose-400');
            addTerminalLine(`> [FAILURE] ${reason}`, 'text-rose-400');
            dockerTag.innerText = verifyExitCode === null ? 'patch failed' : `failed (exit ${verifyExitCode})`;
            dockerTag.className = 'text-[10px] font-mono text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded';
            livePulse.className = 'w-2.5 h-2.5 rounded-full bg-rose-400';
            liveText.innerText = 'Verification Failed';
            liveText.className = 'text-xs font-mono text-rose-400 uppercase';
          }

          renderDynamicFindings(repoShort, findings, fixes, testsPassed, result.pr_url);
        } else {
          setStep(2, 'active');
          addAgentLog(`Pipeline processing in backend sandbox...`, 'text-purple-300');
        }
      } catch (pollErr) {
        clearInterval(pollInterval);
        console.error('Polling error:', pollErr);
        addAgentLog(pollErr.message, 'text-rose-400');
        addTerminalLine(`> [INTERRUPTED] ${pollErr.message}`, 'text-rose-400');
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
      }
    }, 2500);

  } catch (err) {
    addAgentLog(`Error connecting to backend: ${err.message}`, 'text-rose-400');
    btn.disabled = false;
    btn.classList.remove('opacity-50', 'cursor-not-allowed');
  }
}

// --- RENDER DYNAMIC VULNERABILITY CARDS ---
function renderDynamicFindings(repoShort, findings, fixes, testsPassed = false, prUrl = null) {
  const container = document.getElementById('findingsList');
  if (!findings || findings.length === 0) {
    container.innerHTML = `
      <div class="glass-card rounded-2xl p-6 text-center border border-emerald-500/20">
        <div class="inline-flex items-center justify-center p-3 rounded-xl bg-emerald-500/10 text-emerald-400 mb-2">
          <i data-lucide="shield-check" class="w-6 h-6"></i>
        </div>
        <p class="text-sm font-semibold text-slate-200">No vulnerabilities detected!</p>
        <p class="text-xs text-slate-400 mt-1">The scanned repository passed security checks cleanly.</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  let html = '';
  findings.forEach((f, idx) => {
    const ruleId = f.test_id || f.check_id || 'SECURITY-ISSUE';
    const filename = f.filename || f.path || 'unknown';
    const lineNum = f.line_number || f.start?.line || 1;
    const issueText = f.issue_text || f.extra?.message || f.message || 'Potential security vulnerability';
    const severity = (f.issue_severity || f.extra?.severity || 'HIGH').toUpperCase();
    const severityClass = severity === 'HIGH' ? 'badge-high' : 'badge-info';

    // Find if a fix attempt matched this finding
    const fixObj = fixes.find(fx => {
      const fRule = fx.finding?.test_id;
      const fLine = fx.finding?.line_number;
      return fRule === ruleId && fLine === lineNum;
    }) || fixes[idx];

    const wasApplied = Boolean(fixObj && fixObj.applied);
    const hasError = Boolean(fixObj && fixObj.error);
    const isVerified = wasApplied && testsPassed;

    // Build badge HTML based on actual status
    let verificationBadge = '';
    if (isVerified) {
      verificationBadge = `
        <span class="badge badge-success flex items-center gap-1">
          <i data-lucide="check-circle" class="w-3.5 h-3.5"></i> Verified in Sandbox
        </span>
      `;
    } else if (hasError) {
      verificationBadge = `
        <span class="badge badge-high flex items-center gap-1">
          <i data-lucide="alert-circle" class="w-3.5 h-3.5"></i> Patch Generation Failed
        </span>
      `;
    } else if (wasApplied && !testsPassed) {
      verificationBadge = `
        <span class="badge badge-high flex items-center gap-1">
          <i data-lucide="x-circle" class="w-3.5 h-3.5"></i> Regression Failed (Reverted)
        </span>
      `;
    } else {
      verificationBadge = `
        <span class="badge badge-info flex items-center gap-1">
          <i data-lucide="clock" class="w-3.5 h-3.5"></i> Detected (Unpatched)
        </span>
      `;
    }

    // Build diff/remediation view
    let diffViewHtml = '';
    if (isVerified && fixObj && fixObj.fix) {
      diffViewHtml = `
        <div class="diff-container">
          <div class="diff-header code-font">
            <span>LLM Generated Secure Patch</span>
            <span class="text-emerald-400">+ Remediated code (Passed Tests)</span>
          </div>
          <pre class="diff-body code-font overflow-x-auto p-3 text-xs text-emerald-300 bg-slate-950/80 rounded-b-xl"><code>${escapeHtml(fixObj.fix)}</code></pre>
        </div>
      `;
    } else if (hasError) {
      diffViewHtml = `
        <div class="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300 space-y-1">
          <div class="flex items-center gap-2 font-semibold">
            <i data-lucide="alert-octagon" class="w-4 h-4 text-rose-400"></i> Remediation Failed
          </div>
          <p class="font-mono text-[11px] text-rose-400 break-words">${escapeHtml(fixObj.error)}</p>
        </div>
      `;
    } else if (wasApplied && !testsPassed) {
      diffViewHtml = `
        <div class="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
          <p class="font-semibold">Patch broke existing tests — reverted to preserve repository stability.</p>
        </div>
      `;
    } else {
      diffViewHtml = `
        <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-3 text-xs text-slate-400 italic">
          Vulnerability flagged for developer manual review.
        </div>
      `;
    }

    // Build footer status & PR link
    const testStatusText = isVerified
      ? `<strong class="text-emerald-400">PASSED (Neutralized)</strong>`
      : (hasError || !testsPassed
          ? `<strong class="text-rose-400">FAILED (Vulnerability Active)</strong>`
          : `<span class="text-slate-400">Not Verified</span>`);

    let prActionHtml = '';
    const validPrUrl = prUrl || fixObj?.pr_url;
    if (validPrUrl && validPrUrl !== 'https://github.com/mock-pr-url') {
      prActionHtml = `
        <a href="${validPrUrl}" target="_blank" class="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium">
          View PR <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
        </a>
      `;
    } else {
      prActionHtml = `
        <span class="text-slate-500 italic">No PR created (sandbox only)</span>
      `;
    }

    html += `
      <div class="glass-card rounded-2xl border-l-4 ${isVerified ? 'border-emerald-500' : 'border-rose-500'} p-5 space-y-3">
        <div class="flex items-start justify-between">
          <div class="space-y-1">
            <div class="flex items-center space-x-2">
              <span class="badge ${severityClass}">${severity}</span>
              <span class="badge badge-info">${ruleId}</span>
              <span class="text-xs text-slate-400 font-mono">${filename}:${lineNum}</span>
            </div>
            <h4 class="text-sm font-semibold text-slate-100">${escapeHtml(issueText)}</h4>
          </div>
          ${verificationBadge}
        </div>

        <p class="text-xs text-slate-300">
          ${isVerified
            ? 'Static analysis finding remediated and verified through regression tests.'
            : 'Static analysis finding active in repository.'}
        </p>

        <!-- Dynamic Diff or Error View -->
        ${diffViewHtml}

        <!-- Proof and Actions -->
        <div class="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
          <div class="flex items-center gap-2 text-slate-400">
            <i data-lucide="shield" class="w-4 h-4 ${isVerified ? 'text-emerald-400' : 'text-rose-400'}"></i>
            <span>Exploit / Regression Status: ${testStatusText}</span>
          </div>
          ${prActionHtml}
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  lucide.createIcons();
}

function escapeHtml(str) {
  if (typeof str !== 'string') return str;
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}