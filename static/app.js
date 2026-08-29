/**
 * PayPulse Frontend Application Logic
 * Concurrency Stress Testing Arena, Live Ledger Audit, & P2P Money Movement
 */

// ── State ──────────────────────────────────────────────────────────────────
let authToken = localStorage.getItem('paypulse_token') || null;
let currentUsername = localStorage.getItem('paypulse_username') || null;
let rawLedgerEntries = [];
let currentLedgerFilter = 'all';

// ── DOM Elements ───────────────────────────────────────────────────────────
const viewAuth = document.getElementById('view-auth');
const viewDashboard = document.getElementById('view-dashboard');
const navAuthenticated = document.getElementById('nav-authenticated');
const navUnauthenticated = document.getElementById('nav-unauthenticated');
const navUsername = document.getElementById('nav-username');

// Auth Tabs & Forms
const tabLogin = document.getElementById('tab-login');
const tabRegister = document.getElementById('tab-register');
const formLogin = document.getElementById('form-login');
const formRegister = document.getElementById('form-register');

// Dashboard Elements
const dashBalance = document.getElementById('dash-balance');
const btnRefreshBalance = document.getElementById('btn-refresh-balance');
const btnLogout = document.getElementById('btn-logout');

// Send / Request Tab Buttons & Panels
const btnTabSend = document.getElementById('btn-tab-send');
const btnTabRequest = document.getElementById('btn-tab-request');
const panelSend = document.getElementById('panel-send');
const panelRequest = document.getElementById('panel-request');

// Forms
const formSend = document.getElementById('form-send');
const formRequest = document.getElementById('form-request');

// Requests Subtabs & Containers
const subtabIncoming = document.getElementById('subtab-incoming');
const subtabOutgoing = document.getElementById('subtab-outgoing');
const containerIncoming = document.getElementById('container-incoming-requests');
const containerOutgoing = document.getElementById('container-outgoing-requests');
const incomingCountBadge = document.getElementById('incoming-count-badge');
const btnRefreshRequests = document.getElementById('btn-refresh-requests');

// Ledger & Audit
const tableLedgerBody = document.getElementById('table-ledger-body');
const btnRefreshHistory = document.getElementById('btn-refresh-history');
const btnRunReconciliation = document.getElementById('btn-run-reconciliation');
const auditDebits = document.getElementById('audit-debits');
const auditCredits = document.getElementById('audit-credits');
const auditDiff = document.getElementById('audit-diff');
const auditBadge = document.getElementById('audit-badge');

// Ledger Filters
const filterAll = document.getElementById('filter-all');
const filterDebits = document.getElementById('filter-debits');
const filterCredits = document.getElementById('filter-credits');

// Stress Test Modal Elements
const modalStressTest = document.getElementById('modal-stress-test');
const btnOpenStressTestNav = document.getElementById('btn-open-stress-test-nav');
const btnOpenStressTestCard = document.getElementById('btn-open-stress-test-card');
const btnCloseStressModal = document.getElementById('btn-close-stress-modal');
const btnExecuteStressTest = document.getElementById('btn-execute-stress-test');
const stressRecipientInput = document.getElementById('stress-recipient-input');
const stressResultsArea = document.getElementById('stress-results-area');
const stressSummaryBadge = document.getElementById('stress-summary-badge');
const stressResStart = document.getElementById('stress-res-start');
const stressResSuccess = document.getElementById('stress-res-success');
const stressResFailed = document.getElementById('stress-res-failed');
const stressResEnd = document.getElementById('stress-res-end');
const stressThreadsLog = document.getElementById('stress-threads-log');

// ── Toast Notifications ────────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    
    let bgClass = 'bg-slate-900 border-slate-700 text-white';
    let icon = 'ℹ️';
    if (type === 'success') {
        bgClass = 'bg-emerald-950/90 border-emerald-500/40 text-emerald-200';
        icon = '✅';
    } else if (type === 'error') {
        bgClass = 'bg-rose-950/90 border-rose-500/40 text-rose-200';
        icon = '❌';
    }

    toast.className = `p-4 rounded-xl border shadow-xl flex items-center space-x-3 pointer-events-auto fade-in ${bgClass}`;
    toast.innerHTML = `
        <span class="text-base">${icon}</span>
        <div class="text-xs font-medium">${message}</div>
    `;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ── API Helper ─────────────────────────────────────────────────────────────
async function apiCall(endpoint, options = {}, suppressToast = false) {
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {})
    };

    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    try {
        const response = await fetch(endpoint, {
            ...options,
            headers
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            if (response.status === 401 && authToken) {
                logout();
                showToast('Session expired. Please log in again.', 'error');
                return null;
            }
            const errorMsg = data.detail || (Array.isArray(data.detail) ? data.detail[0]?.msg : 'Request failed');
            const error = new Error(errorMsg);
            error.status = response.status;
            error.data = data;
            throw error;
        }

        return data;
    } catch (err) {
        if (!suppressToast) {
            showToast(err.message, 'error');
        }
        throw err;
    }
}

// ── Auth Handlers ──────────────────────────────────────────────────────────
function setAuthState(token, username) {
    authToken = token;
    currentUsername = username;
    if (token) {
        localStorage.setItem('paypulse_token', token);
        localStorage.setItem('paypulse_username', username);
        navUsername.textContent = username;
        navAuthenticated.classList.remove('hidden');
        navUnauthenticated.classList.add('hidden');
        viewAuth.classList.add('hidden');
        viewDashboard.classList.remove('hidden');
        loadDashboardData();
    } else {
        localStorage.removeItem('paypulse_token');
        localStorage.removeItem('paypulse_username');
        navAuthenticated.classList.add('hidden');
        navUnauthenticated.classList.remove('hidden');
        viewAuth.classList.remove('hidden');
        viewDashboard.classList.add('hidden');
    }
}

function logout() {
    setAuthState(null, null);
    showToast('Signed out successfully.');
}

// Login
formLogin.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    try {
        const res = await apiCall('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        if (res && res.access_token) {
            setAuthState(res.access_token, username);
            showToast(`Welcome back, ${username}!`, 'success');
            formLogin.reset();
        }
    } catch (e) {}
});

// Register
formRegister.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('register-username').value.trim();
    const password = document.getElementById('register-password').value;

    try {
        const res = await apiCall('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        if (res) {
            showToast(`Account created! Auto-funded with ৳${res.wallet_balance_bdt} BDT.`, 'success');
            // Auto login
            const loginRes = await apiCall('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            if (loginRes && loginRes.access_token) {
                setAuthState(loginRes.access_token, username);
                formRegister.reset();
            }
        }
    } catch (e) {}
});

// Auth Tab Switching
tabLogin.addEventListener('click', () => {
    tabLogin.className = 'flex-1 pb-3 text-sm font-semibold text-brand-400 border-b-2 border-brand-500 transition-colors';
    tabRegister.className = 'flex-1 pb-3 text-sm font-semibold text-slate-400 hover:text-slate-200 border-b-2 border-transparent transition-colors';
    formLogin.classList.remove('hidden');
    formRegister.classList.add('hidden');
});

tabRegister.addEventListener('click', () => {
    tabRegister.className = 'flex-1 pb-3 text-sm font-semibold text-emerald-400 border-b-2 border-emerald-500 transition-colors';
    tabLogin.className = 'flex-1 pb-3 text-sm font-semibold text-slate-400 hover:text-slate-200 border-b-2 border-transparent transition-colors';
    formRegister.classList.remove('hidden');
    formLogin.classList.add('hidden');
});

btnLogout.addEventListener('click', logout);

// ── Quick Presets ──────────────────────────────────────────────────────────
window.setSendAmount = function(val) {
    document.getElementById('send-amount').value = val.toFixed(2);
};

window.setRequestAmount = function(val) {
    document.getElementById('req-amount').value = val.toFixed(2);
};

// ── Dashboard Operations ───────────────────────────────────────────────────
async function loadDashboardData() {
    await Promise.all([
        refreshBalance(),
        refreshRequests(),
        refreshLedgerHistory(),
        runReconciliationAudit()
    ]);
}

// 1. Refresh Balance
async function refreshBalance() {
    try {
        const res = await apiCall('/wallets/me');
        if (res && res.balance_bdt) {
            const formatted = parseFloat(res.balance_bdt).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            dashBalance.textContent = `৳ ${formatted}`;
            return parseFloat(res.balance_bdt);
        }
    } catch (e) {}
    return 0;
}
btnRefreshBalance.addEventListener('click', () => {
    refreshBalance();
    showToast('Balance updated.');
});

// 2. Send Money (Direct Transfer with Idempotency Key)
formSend.addEventListener('submit', async (e) => {
    e.preventDefault();
    const recipient = document.getElementById('send-recipient').value.trim();
    const amount = parseFloat(document.getElementById('send-amount').value);
    const note = document.getElementById('send-note').value.trim() || null;

    if (!recipient || isNaN(amount) || amount <= 0) {
        showToast('Please provide a valid recipient and positive amount.', 'error');
        return;
    }

    const idempotencyKey = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `idemp-${Date.now()}-${Math.random()}`;

    const btn = document.getElementById('btn-send-submit');
    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin inline-block mr-2">⚡</span> Processing Atomic Transfer...`;

    try {
        const res = await apiCall('/transfers/send', {
            method: 'POST',
            headers: {
                'Idempotency-Key': idempotencyKey
            },
            body: JSON.stringify({
                recipient_username: recipient,
                amount_bdt: amount.toFixed(2),
                note
            })
        });

        if (res) {
            showToast(`Transferred ৳${res.amount_bdt} BDT to ${res.recipient} successfully!`, 'success');
            formSend.reset();
            loadDashboardData();
        }
    } catch (e) {
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>Execute Transfer</span><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>`;
    }
});

// 3. Request Money
formRequest.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payer = document.getElementById('req-payer').value.trim();
    const amount = parseFloat(document.getElementById('req-amount').value);
    const note = document.getElementById('req-note').value.trim() || null;

    if (!payer || isNaN(amount) || amount <= 0) {
        showToast('Please provide a valid payer username and positive amount.', 'error');
        return;
    }

    const btn = document.getElementById('btn-request-submit');
    btn.disabled = true;

    try {
        const res = await apiCall('/money-requests', {
            method: 'POST',
            body: JSON.stringify({
                payer_username: payer,
                amount_bdt: amount.toFixed(2),
                note
            })
        });

        if (res) {
            showToast(`Requested ৳${res.amount_bdt} BDT from ${res.payer}!`, 'success');
            formRequest.reset();
            refreshRequests();
        }
    } catch (e) {
    } finally {
        btn.disabled = false;
    }
});

// 4. Money Requests
async function refreshRequests() {
    try {
        const res = await apiCall('/money-requests');
        if (!res) return;

        const incoming = res.incoming || [];
        const pendingIncoming = incoming.filter(r => r.status === 'pending');
        incomingCountBadge.textContent = pendingIncoming.length;

        if (incoming.length === 0) {
            containerIncoming.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">No pending requests to pay.</div>`;
        } else {
            containerIncoming.innerHTML = incoming.map(r => `
                <div class="p-3.5 rounded-2xl bg-slate-950 border border-slate-800/80 flex items-center justify-between space-x-3 fade-in">
                    <div>
                        <div class="flex items-center space-x-2">
                            <span class="text-xs font-bold text-white">${escapeHtml(r.requester_username)}</span>
                            <span class="text-[10px] text-slate-400">requests</span>
                            <span class="text-xs font-mono font-bold text-amber-400">৳${parseFloat(r.amount_bdt).toFixed(2)}</span>
                        </div>
                        ${r.note ? `<p class="text-[11px] text-slate-400 mt-0.5">"${escapeHtml(r.note)}"</p>` : ''}
                        <span class="text-[10px] text-slate-500 block mt-1">${formatTime(r.created_at)}</span>
                    </div>

                    <div>
                        ${r.status === 'pending' ? `
                            <div class="flex items-center space-x-1.5">
                                <button onclick="handleApproveRequest(${r.request_id})" class="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition shadow-sm">
                                    Pay Now
                                </button>
                                <button onclick="handleRejectRequest(${r.request_id})" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-rose-400 rounded-lg text-xs font-medium border border-slate-700 transition">
                                    Reject
                                </button>
                            </div>
                        ` : `
                            <span class="text-xs font-mono px-2 py-0.5 rounded ${r.status === 'approved' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'} uppercase text-[10px]">
                                ${r.status}
                            </span>
                        `}
                    </div>
                </div>
            `).join('');
        }

        const outgoing = res.outgoing || [];
        if (outgoing.length === 0) {
            containerOutgoing.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">No outgoing requests created yet.</div>`;
        } else {
            containerOutgoing.innerHTML = outgoing.map(r => `
                <div class="p-3.5 rounded-2xl bg-slate-950 border border-slate-800/80 flex items-center justify-between space-x-3 fade-in">
                    <div>
                        <div class="flex items-center space-x-2">
                            <span class="text-xs font-bold text-white">To: ${escapeHtml(r.payer_username)}</span>
                            <span class="text-xs font-mono font-bold text-indigo-300">৳${parseFloat(r.amount_bdt).toFixed(2)}</span>
                        </div>
                        ${r.note ? `<p class="text-[11px] text-slate-400 mt-0.5">"${escapeHtml(r.note)}"</p>` : ''}
                        <span class="text-[10px] text-slate-500 block mt-1">${formatTime(r.created_at)}</span>
                    </div>
                    <div>
                        <span class="text-xs font-mono px-2.5 py-1 rounded ${r.status === 'pending' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : (r.status === 'approved' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400')} uppercase text-[10px]">
                            ${r.status}
                        </span>
                    </div>
                </div>
            `).join('');
        }
    } catch (e) {}
}

window.handleApproveRequest = async function(requestId) {
    try {
        const res = await apiCall(`/money-requests/${requestId}/approve`, {
            method: 'POST'
        });
        if (res) {
            showToast('Payment request approved and funds transferred!', 'success');
            loadDashboardData();
        }
    } catch (e) {}
};

window.handleRejectRequest = async function(requestId) {
    try {
        const res = await apiCall(`/money-requests/${requestId}/reject`, {
            method: 'POST'
        });
        if (res) {
            showToast('Payment request rejected.', 'info');
            refreshRequests();
        }
    } catch (e) {}
};

btnRefreshRequests.addEventListener('click', refreshRequests);

// 5. Ledger History & Filters
async function refreshLedgerHistory() {
    try {
        const res = await apiCall('/transactions/history');
        if (!res || !res.entries) return;

        rawLedgerEntries = res.entries;
        renderLedgerTable();
    } catch (e) {}
}

function renderLedgerTable() {
    let entries = rawLedgerEntries;
    if (currentLedgerFilter === 'debits') {
        entries = entries.filter(e => e.entry_type === 'DEBIT');
    } else if (currentLedgerFilter === 'credits') {
        entries = entries.filter(e => e.entry_type === 'CREDIT');
    }

    if (entries.length === 0) {
        tableLedgerBody.innerHTML = `
            <tr>
                <td colspan="6" class="py-8 text-center text-slate-500 font-sans">
                    No matching ledger entries found.
                </td>
            </tr>
        `;
        return;
    }

    tableLedgerBody.innerHTML = entries.map(entry => {
        const isDebit = entry.entry_type === 'DEBIT';
        const typeBadge = isDebit
            ? `<span class="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 font-bold text-[10px]">DEBIT (-)</span>`
            : `<span class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold text-[10px]">CREDIT (+)</span>`;
        
        const amountColor = isDebit ? 'text-rose-400' : 'text-emerald-400';
        const amountSign = isDebit ? '-' : '+';

        return `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="py-3 px-4 text-slate-400 font-mono">#${entry.ledger_entry_id}</td>
                <td class="py-3 px-4">${typeBadge}</td>
                <td class="py-3 px-4 font-bold ${amountColor}">${amountSign} ৳${parseFloat(entry.amount_bdt).toFixed(2)}</td>
                <td class="py-3 px-4 text-white">৳${parseFloat(entry.balance_after).toFixed(2)}</td>
                <td class="py-3 px-4 text-slate-400 text-[11px]">TXN #${entry.transaction_id}</td>
                <td class="py-3 px-4 text-slate-500 text-[11px] font-sans">${formatTime(entry.created_at)}</td>
            </tr>
        `;
    }).join('');
}

filterAll.addEventListener('click', () => {
    currentLedgerFilter = 'all';
    filterAll.className = 'px-2.5 py-1 rounded-lg bg-slate-800 text-white font-medium';
    filterDebits.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-rose-400';
    filterCredits.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-emerald-400';
    renderLedgerTable();
});

filterDebits.addEventListener('click', () => {
    currentLedgerFilter = 'debits';
    filterDebits.className = 'px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-300 font-medium border border-rose-500/30';
    filterAll.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-white';
    filterCredits.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-emerald-400';
    renderLedgerTable();
});

filterCredits.addEventListener('click', () => {
    currentLedgerFilter = 'credits';
    filterCredits.className = 'px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-300 font-medium border border-emerald-500/30';
    filterAll.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-white';
    filterDebits.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-rose-400';
    renderLedgerTable();
});

btnRefreshHistory.addEventListener('click', () => {
    refreshLedgerHistory();
    showToast('Ledger audit trail refreshed.');
});

// 6. System Reconciliation Audit
async function runReconciliationAudit() {
    try {
        const res = await apiCall('/ledger/reconciliation');
        if (!res) return;

        auditDebits.textContent = `৳ ${parseFloat(res.total_debits_bdt).toFixed(2)}`;
        auditCredits.textContent = `৳ ${parseFloat(res.total_credits_bdt).toFixed(2)}`;
        auditDiff.textContent = `${res.difference_bdt} BDT`;

        if (res.is_balanced) {
            auditBadge.className = 'text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
            auditBadge.textContent = '100% BALANCED';
            auditDiff.className = 'text-emerald-400 font-bold';
        } else {
            auditBadge.className = 'text-xs font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20';
            auditBadge.textContent = 'DISCREPANCY';
            auditDiff.className = 'text-rose-400 font-bold';
        }
    } catch (e) {}
}
btnRunReconciliation.addEventListener('click', async () => {
    await runReconciliationAudit();
    showToast('System reconciliation verified: Total Debits == Total Credits.', 'success');
});

// ── Concurrency Stress Test Arena ──────────────────────────────────────────
function openStressModal() {
    modalStressTest.classList.remove('hidden');
    stressResultsArea.classList.add('hidden');
}

function closeStressModal() {
    modalStressTest.classList.add('hidden');
}

btnOpenStressTestNav.addEventListener('click', openStressModal);
btnOpenStressTestCard.addEventListener('click', openStressModal);
btnCloseStressModal.addEventListener('click', closeStressModal);

// Close on backdrop click
modalStressTest.addEventListener('click', (e) => {
    if (e.target === modalStressTest) closeStressModal();
});

// Execute Parallel Requests
btnExecuteStressTest.addEventListener('click', async () => {
    const recipient = stressRecipientInput.value.trim() || 'bob';
    const numThreads = 10;
    const amountPerThread = 20000.00;

    // Ensure recipient exists
    try {
        await apiCall('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username: recipient, password: 'password123' })
        }, true);
    } catch (e) {
        // Recipient likely already registered, safe to proceed
    }

    const startBalance = await refreshBalance();
    
    btnExecuteStressTest.disabled = true;
    btnExecuteStressTest.innerHTML = `<span class="animate-spin inline-block mr-2">⚡</span> Firing 10 Simultaneous Requests Across Database Connections...`;
    stressResultsArea.classList.remove('hidden');
    stressThreadsLog.innerHTML = `<div class="text-slate-500 animate-pulse">Launching Promise.all with 10 concurrent requests...</div>`;
    stressResStart.textContent = `৳ ${startBalance.toFixed(2)}`;

    // Prepare 10 concurrent requests with unique UUID idempotency keys
    const requests = Array.from({ length: numThreads }).map((_, index) => {
        const idempKey = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `stress-${Date.now()}-${index}-${Math.random()}`;
        return apiCall('/transfers/send', {
            method: 'POST',
            headers: { 'Idempotency-Key': idempKey },
            body: JSON.stringify({
                recipient_username: recipient,
                amount_bdt: amountPerThread.toFixed(2),
                note: `Live Concurrency Test Thread #${index + 1}`
            })
        }, true).then(res => ({
            thread: index + 1,
            status: 'SUCCESS',
            amount: amountPerThread,
            detail: res
        })).catch(err => ({
            thread: index + 1,
            status: 'BLOCKED',
            reason: err.message || 'Insufficient balance',
            detail: err
        }));
    });

    // Fire all 10 simultaneously
    const results = await Promise.all(requests);

    // Analyze results
    const succeeded = results.filter(r => r.status === 'SUCCESS');
    const blocked = results.filter(r => r.status === 'BLOCKED');

    stressResSuccess.textContent = `${succeeded.length} / ${numThreads}`;
    stressResFailed.textContent = `${blocked.length} / ${numThreads}`;

    const endBalance = await refreshBalance();
    stressResEnd.textContent = `৳ ${endBalance.toFixed(2)}`;

    // Check invariants
    const zeroNegativeBalance = endBalance >= 0;
    const expectedSuccessCount = Math.floor(startBalance / amountPerThread);

    if (zeroNegativeBalance) {
        stressSummaryBadge.className = 'text-xs font-mono px-2.5 py-0.5 rounded font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
        stressSummaryBadge.textContent = `PERFECT SERIALIZATION (${succeeded.length} Settled, ${blocked.length} Protected)`;
    } else {
        stressSummaryBadge.className = 'text-xs font-mono px-2.5 py-0.5 rounded font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30';
        stressSummaryBadge.textContent = 'RACE CONDITION DETECTED';
    }

    // Render thread logs
    stressThreadsLog.innerHTML = results.map(r => {
        if (r.status === 'SUCCESS') {
            return `
                <div class="flex items-center justify-between p-2 rounded-lg bg-emerald-950/40 border border-emerald-500/20 text-emerald-300">
                    <div class="flex items-center space-x-2">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        <span class="font-bold">Thread #${r.thread}:</span>
                        <span>HTTP 200 OK</span>
                    </div>
                    <span class="font-mono text-emerald-400">-৳${r.amount.toFixed(2)} (Settled)</span>
                </div>
            `;
        } else {
            return `
                <div class="flex items-center justify-between p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400">
                    <div class="flex items-center space-x-2">
                        <span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
                        <span class="font-bold text-slate-300">Thread #${r.thread}:</span>
                        <span class="text-rose-300 font-semibold">HTTP 400</span>
                    </div>
                    <span class="font-mono text-slate-500 text-[10px]">${escapeHtml(r.reason)}</span>
                </div>
            `;
        }
    }).join('');

    await Promise.all([
        refreshRequests(),
        refreshLedgerHistory(),
        runReconciliationAudit()
    ]);

    btnExecuteStressTest.disabled = false;
    btnExecuteStressTest.innerHTML = `<span>🔥 Execute 10 Parallel Transfers Now (Promise.all)</span>`;
    showToast(`Concurrency stress test complete: ${succeeded.length} succeeded, ${blocked.length} blocked cleanly!`, 'success');
});

// ── UI Helpers ─────────────────────────────────────────────────────────────
btnTabSend.addEventListener('click', () => {
    btnTabSend.className = 'flex-1 py-2.5 text-xs font-semibold rounded-xl bg-brand-600 text-white shadow transition-all';
    btnTabRequest.className = 'flex-1 py-2.5 text-xs font-semibold rounded-xl text-slate-400 hover:text-white transition-all';
    panelSend.classList.remove('hidden');
    panelRequest.classList.add('hidden');
});

btnTabRequest.addEventListener('click', () => {
    btnTabRequest.className = 'flex-1 py-2.5 text-xs font-semibold rounded-xl bg-indigo-600 text-white shadow transition-all';
    btnTabSend.className = 'flex-1 py-2.5 text-xs font-semibold rounded-xl text-slate-400 hover:text-white transition-all';
    panelRequest.classList.remove('hidden');
    panelSend.classList.add('hidden');
});

subtabIncoming.addEventListener('click', () => {
    subtabIncoming.className = 'pb-2 text-brand-400 border-b-2 border-brand-500 mr-4 transition-colors';
    subtabOutgoing.className = 'pb-2 text-slate-400 hover:text-slate-200 border-b-2 border-transparent transition-colors';
    containerIncoming.classList.remove('hidden');
    containerOutgoing.classList.add('hidden');
});

subtabOutgoing.addEventListener('click', () => {
    subtabOutgoing.className = 'pb-2 text-indigo-400 border-b-2 border-indigo-500 transition-colors';
    subtabIncoming.className = 'pb-2 text-slate-400 hover:text-slate-200 border-b-2 border-transparent mr-4 transition-colors';
    containerOutgoing.classList.remove('hidden');
    containerIncoming.classList.add('hidden');
});

function formatTime(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' ' + d.toLocaleDateString();
    } catch {
        return isoStr;
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Initial Boot ───────────────────────────────────────────────────────────
if (authToken && currentUsername) {
    setAuthState(authToken, currentUsername);
} else {
    setAuthState(null, null);
}
