/**
 * PayPulse Application Logic
 * Pure Integer Whole Number Amounts (Zero Decimals / Floating Points)
 */

// ── State ──────────────────────────────────────────────────────────────────
let authToken = localStorage.getItem('paypulse_token') || null;
let currentUsername = localStorage.getItem('paypulse_username') || null;
let rawLedgerEntries = [];
let currentLedgerFilter = 'all';
let unreadTransactionCount = 0;
let lastSeenLedgerId = parseInt(localStorage.getItem('paypulse_last_seen_ledger') || '0', 10);
let pollInterval = null;

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

// Forms & Panels
const formSend = document.getElementById('form-send');
const formRequest = document.getElementById('form-request');
const tabReqForm = document.getElementById('tab-req-form');
const tabReqIncoming = document.getElementById('tab-req-incoming');
const tabReqOutgoing = document.getElementById('tab-req-outgoing');
const panelReqForm = document.getElementById('panel-req-form');
const panelReqIncoming = document.getElementById('panel-req-incoming');
const panelReqOutgoing = document.getElementById('panel-req-outgoing');
const containerIncoming = document.getElementById('container-incoming-requests');
const containerOutgoing = document.getElementById('container-outgoing-requests');
const incomingCountBadge = document.getElementById('incoming-count-badge');
const outgoingCountBadge = document.getElementById('outgoing-count-badge');
const btnRefreshRequests = document.getElementById('btn-refresh-requests');

// Inbox Drawer Elements
const drawerInbox = document.getElementById('drawer-inbox');
const btnToggleInbox = document.getElementById('btn-toggle-inbox');
const btnCloseInbox = document.getElementById('btn-close-inbox');
const btnMarkInboxRead = document.getElementById('btn-mark-inbox-read');
const inboxBadge = document.getElementById('inbox-badge');
const inboxItemsContainer = document.getElementById('inbox-items-container');
const inboxTotalCount = document.getElementById('inbox-total-count');

// Drawer Filters
const filterAll = document.getElementById('filter-all');
const filterDebits = document.getElementById('filter-debits');
const filterCredits = document.getElementById('filter-credits');

// ── Realistic Top-Right Toast Notifications ─────────────────────────────────
function showToast(message, type = 'info', title = null) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    
    let defaultTitle = 'Notification';
    let iconBg = 'bg-[#262b35] text-[#d4d4d8] border border-[#373e4d]';
    let iconSvg = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
    
    if (type === 'success') {
        defaultTitle = 'Success';
        iconBg = 'bg-accent-500/15 text-accent-400 border border-accent-500/25';
        iconSvg = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>`;
    } else if (type === 'error') {
        defaultTitle = 'Attention';
        iconBg = 'bg-rose-500/15 text-rose-400 border border-rose-500/25';
        iconSvg = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>`;
    }

    const toastTitle = title || defaultTitle;

    toast.className = 'toast-item p-3.5 rounded-2xl bg-[#16191f]/95 border border-[#2b303b] shadow-2xl shadow-black/80 flex items-start space-x-3 pointer-events-auto backdrop-blur-md animate-slide-in-right text-xs transition-all';
    toast.innerHTML = `
        <div class="w-7 h-7 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${iconBg}">
            ${iconSvg}
        </div>
        <div class="flex-1 min-w-0 pr-1">
            <div class="font-bold text-white tracking-tight text-xs">${toastTitle}</div>
            <div class="text-[11px] text-[#a1a1aa] leading-relaxed mt-0.5">${escapeHtml(message)}</div>
        </div>
        <button class="btn-dismiss-toast text-[#71717a] hover:text-[#d4d4d8] p-1 rounded-md transition shrink-0">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
    `;

    toast.querySelector('.btn-dismiss-toast').addEventListener('click', () => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        toast.style.transition = 'all 0.2s ease';
        setTimeout(() => toast.remove(), 200);
    });

    container.appendChild(toast);
    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            toast.style.transition = 'all 0.2s ease';
            setTimeout(() => toast.remove(), 200);
        }
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

// ── Strict Integer Validation Helper ───────────────────────────────────────
function parsePositiveInteger(valStr) {
    if (!valStr) return null;
    const clean = valStr.trim();
    // Rejects decimals, negative signs, letters, scientific notation
    if (!/^[1-9][0-9]*$/.test(clean)) {
        return null;
    }
    return clean;
}

function formatIntegerAmount(val) {
    if (val === null || val === undefined) return '0';
    const num = parseInt(val, 10);
    return isNaN(num) ? String(val) : num.toLocaleString('en-US');
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
        startPolling();
    } else {
        localStorage.removeItem('paypulse_token');
        localStorage.removeItem('paypulse_username');
        navAuthenticated.classList.add('hidden');
        navUnauthenticated.classList.remove('hidden');
        viewAuth.classList.remove('hidden');
        viewDashboard.classList.add('hidden');
        stopPolling();
    }
}

function logout() {
    setAuthState(null, null);
    showToast('Signed out.');
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
            showToast(`Account created! Auto-funded with ৳${formatIntegerAmount(res.wallet_balance_bdt)} BDT.`, 'success');
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
    tabLogin.className = 'flex-1 pb-3 text-sm font-semibold text-accent-400 border-b-2 border-accent-400 transition-colors';
    tabRegister.className = 'flex-1 pb-3 text-sm font-semibold text-[#71717a] hover:text-[#d4d4d8] border-b-2 border-transparent transition-colors';
    formLogin.classList.remove('hidden');
    formRegister.classList.add('hidden');
});

tabRegister.addEventListener('click', () => {
    tabRegister.className = 'flex-1 pb-3 text-sm font-semibold text-accent-400 border-b-2 border-accent-400 transition-colors';
    tabLogin.className = 'flex-1 pb-3 text-sm font-semibold text-[#71717a] hover:text-[#d4d4d8] border-b-2 border-transparent transition-colors';
    formRegister.classList.remove('hidden');
    formLogin.classList.add('hidden');
});

btnLogout.addEventListener('click', logout);

// ── Dashboard Operations ───────────────────────────────────────────────────
async function loadDashboardData() {
    await Promise.all([
        refreshBalance(),
        refreshRequests(),
        refreshLedgerHistory()
    ]);
}

// Background auto-refresh polling
function startPolling() {
    stopPolling();
    pollInterval = setInterval(async () => {
        if (authToken) {
            await Promise.all([
                refreshBalance(),
                refreshRequests(),
                refreshLedgerHistory(true)
            ]);
        }
    }, 3500);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// 1. Refresh Balance (Formatted as integer)
async function refreshBalance() {
    try {
        const res = await apiCall('/wallets/me', {}, true);
        if (res && res.balance_bdt) {
            const formatted = formatIntegerAmount(res.balance_bdt);
            dashBalance.textContent = `৳ ${formatted}`;
            return res.balance_bdt;
        }
    } catch (e) {}
    return "0";
}
btnRefreshBalance.addEventListener('click', () => {
    refreshBalance();
    showToast('Balance updated.');
});

// 2. Send Money (Pure Integer Amounts)
formSend.addEventListener('submit', async (e) => {
    e.preventDefault();
    const recipient = document.getElementById('send-recipient').value.trim();
    const rawAmount = document.getElementById('send-amount').value;
    const integerAmount = parsePositiveInteger(rawAmount);
    const note = document.getElementById('send-note').value.trim() || null;

    if (!recipient) {
        showToast('Please enter a recipient username.', 'error');
        return;
    }

    if (!integerAmount) {
        showToast('Amount must be a whole positive integer (e.g. 2500, no decimals).', 'error');
        return;
    }

    const idempotencyKey = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `idemp-${Date.now()}-${Math.random()}`;
    const btn = document.getElementById('btn-send-submit');
    btn.disabled = true;
    btn.innerHTML = `<span>Sending...</span>`;

    try {
        const res = await apiCall('/transfers/send', {
            method: 'POST',
            headers: {
                'Idempotency-Key': idempotencyKey
            },
            body: JSON.stringify({
                recipient_username: recipient,
                amount_bdt: integerAmount,
                note
            })
        });

        if (res) {
            showToast(`Sent ৳${formatIntegerAmount(res.amount_bdt)} BDT to ${res.recipient}!`, 'success');
            formSend.reset();
            triggerNewInboxNotification();
            await loadDashboardData();
        }
    } catch (e) {
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>Send Money</span><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>`;
    }
});

// 3. Request Money (Pure Integer Amounts)
formRequest.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payer = document.getElementById('req-payer').value.trim();
    const rawAmount = document.getElementById('req-amount').value;
    const integerAmount = parsePositiveInteger(rawAmount);
    const note = document.getElementById('req-note').value.trim() || null;

    if (!payer) {
        showToast('Please enter a payer username.', 'error');
        return;
    }

    if (!integerAmount) {
        showToast('Amount must be a whole positive integer (e.g. 1200, no decimals).', 'error');
        return;
    }

    const btn = document.getElementById('btn-request-submit');
    btn.disabled = true;

    try {
        const res = await apiCall('/money-requests', {
            method: 'POST',
            body: JSON.stringify({
                payer_username: payer,
                amount_bdt: integerAmount,
                note
            })
        });

        if (res) {
            showToast(`Requested ৳${formatIntegerAmount(res.amount_bdt)} BDT from ${res.payer}!`, 'success');
            formRequest.reset();
            await refreshRequests();
            // Automatically switch to Sent Requests tab so the user sees it
            switchToTab('outgoing');
        }
    } catch (e) {
    } finally {
        btn.disabled = false;
    }
});

// 4. Money Requests
async function refreshRequests() {
    try {
        const res = await apiCall('/money-requests', {}, true);
        if (!res) return;

        // 1. Incoming Requests (To Pay)
        const incoming = res.incoming || [];
        const pendingIncoming = incoming.filter(r => r.status === 'pending');
        incomingCountBadge.textContent = pendingIncoming.length;

        if (pendingIncoming.length === 0) {
            containerIncoming.innerHTML = `<div class="text-center py-8 text-[#71717a] text-xs">No pending requests to pay.</div>`;
        } else {
            containerIncoming.innerHTML = pendingIncoming.map(r => `
                <div class="p-3 rounded-2xl bg-[#0c0e11] border border-[#242830] flex items-center justify-between space-x-3 fade-in">
                    <div>
                        <div class="flex items-center space-x-1.5">
                            <span class="text-xs font-bold text-white">${escapeHtml(r.requester_username)}</span>
                            <span class="text-[10px] text-[#71717a]">asks for</span>
                            <span class="text-xs font-mono font-bold text-accent-400">৳${formatIntegerAmount(r.amount_bdt)}</span>
                        </div>
                        ${r.note ? `<p class="text-[10px] text-[#a1a1aa] mt-0.5">"${escapeHtml(r.note)}"</p>` : ''}
                        <span class="text-[10px] text-[#71717a] block mt-1">${formatTime(r.created_at)}</span>
                    </div>

                    <div class="flex items-center space-x-1.5 shrink-0">
                        <button onclick="handleApproveRequest(${r.request_id})" class="px-2.5 py-1 bg-accent-500 hover:bg-accent-400 text-stone-950 rounded-lg text-xs font-bold transition shadow-sm">
                            Pay
                        </button>
                        <button onclick="handleRejectRequest(${r.request_id})" class="px-2 py-1 bg-[#1a1e24] hover:bg-[#252b34] text-rose-300 rounded-lg text-xs font-medium border border-[#2b303b] transition">
                            ✕
                        </button>
                    </div>
                </div>
            `).join('');
        }

        // 2. Outgoing Requests (Sent by me)
        const outgoing = res.outgoing || [];
        outgoingCountBadge.textContent = outgoing.length;

        if (outgoing.length === 0) {
            containerOutgoing.innerHTML = `<div class="text-center py-8 text-[#71717a] text-xs">No sent requests created yet.</div>`;
        } else {
            containerOutgoing.innerHTML = outgoing.map(r => {
                let statusBadge = `<span class="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 font-bold text-[10px] border border-amber-500/20">PENDING</span>`;
                if (r.status === 'approved') {
                    statusBadge = `<span class="px-2 py-0.5 rounded bg-accent-500/10 text-accent-400 font-bold text-[10px] border border-accent-500/20">PAID</span>`;
                } else if (r.status === 'rejected') {
                    statusBadge = `<span class="px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 font-bold text-[10px] border border-rose-500/20">REJECTED</span>`;
                }

                return `
                    <div class="p-3 rounded-2xl bg-[#0c0e11] border border-[#242830] flex items-center justify-between space-x-3 fade-in">
                        <div>
                            <div class="flex items-center space-x-1.5">
                                <span class="text-xs font-bold text-white">To: ${escapeHtml(r.payer_username)}</span>
                                <span class="text-xs font-mono font-bold text-[#d4d4d8]">৳${formatIntegerAmount(r.amount_bdt)}</span>
                            </div>
                            ${r.note ? `<p class="text-[10px] text-[#a1a1aa] mt-0.5">"${escapeHtml(r.note)}"</p>` : ''}
                            <span class="text-[10px] text-[#71717a] block mt-1">${formatTime(r.created_at)}</span>
                        </div>

                        <div class="shrink-0">
                            ${statusBadge}
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (e) {}
}

window.handleApproveRequest = async function(requestId) {
    try {
        const res = await apiCall(`/money-requests/${requestId}/approve`, {
            method: 'POST'
        });
        if (res) {
            showToast('Request approved & funds transferred!', 'success');
            triggerNewInboxNotification();
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
            showToast('Request rejected.', 'info');
            refreshRequests();
        }
    } catch (e) {}
};

btnRefreshRequests.addEventListener('click', () => {
    refreshRequests();
    showToast('Requests refreshed.');
});

// 3-Way Tab Switching Helper
function switchToTab(tabName) {
    tabReqForm.className = 'text-[#71717a] hover:text-white pb-1 transition-colors';
    tabReqIncoming.className = 'text-[#71717a] hover:text-white pb-1 transition-colors';
    tabReqOutgoing.className = 'text-[#71717a] hover:text-white pb-1 transition-colors';

    panelReqForm.classList.add('hidden');
    panelReqIncoming.classList.add('hidden');
    panelReqOutgoing.classList.add('hidden');

    if (tabName === 'form') {
        tabReqForm.className = 'text-white border-b-2 border-accent-400 pb-1';
        panelReqForm.classList.remove('hidden');
    } else if (tabName === 'incoming') {
        tabReqIncoming.className = 'text-white border-b-2 border-accent-400 pb-1';
        panelReqIncoming.classList.remove('hidden');
    } else if (tabName === 'outgoing') {
        tabReqOutgoing.className = 'text-white border-b-2 border-accent-400 pb-1';
        panelReqOutgoing.classList.remove('hidden');
    }
}

tabReqForm.addEventListener('click', () => switchToTab('form'));
tabReqIncoming.addEventListener('click', () => switchToTab('incoming'));
tabReqOutgoing.addEventListener('click', () => switchToTab('outgoing'));

// ── Transaction Inbox System ───────────────────────────────────────────────
function triggerNewInboxNotification() {
    unreadTransactionCount += 1;
    updateInboxBadgeUI();
}

function updateInboxBadgeUI() {
    if (unreadTransactionCount > 0) {
        inboxBadge.textContent = `${unreadTransactionCount}`;
        inboxBadge.classList.remove('hidden');
        btnMarkInboxRead.textContent = `Clear (${unreadTransactionCount})`;
    } else {
        inboxBadge.classList.add('hidden');
        btnMarkInboxRead.textContent = `Clear (0)`;
    }
}

async function refreshLedgerHistory(isBackground = false) {
    try {
        const res = await apiCall('/transactions/history', {}, true);
        if (!res || !res.entries) return;

        rawLedgerEntries = res.entries;
        
        if (rawLedgerEntries.length > 0) {
            const newestId = rawLedgerEntries[0].ledger_entry_id;
            if (lastSeenLedgerId > 0 && newestId > lastSeenLedgerId) {
                const countNew = rawLedgerEntries.filter(e => e.ledger_entry_id > lastSeenLedgerId).length;
                unreadTransactionCount = countNew;
                updateInboxBadgeUI();
            }
        }

        renderInboxDrawer();
    } catch (e) {}
}

function openInboxDrawer() {
    drawerInbox.classList.remove('hidden');
    if (rawLedgerEntries.length > 0) {
        lastSeenLedgerId = rawLedgerEntries[0].ledger_entry_id;
        localStorage.setItem('paypulse_last_seen_ledger', String(lastSeenLedgerId));
    }
    unreadTransactionCount = 0;
    updateInboxBadgeUI();
    renderInboxDrawer();
}

function closeInboxDrawer() {
    drawerInbox.classList.add('hidden');
}

btnToggleInbox.addEventListener('click', openInboxDrawer);
btnCloseInbox.addEventListener('click', closeInboxDrawer);
btnMarkInboxRead.addEventListener('click', () => {
    unreadTransactionCount = 0;
    if (rawLedgerEntries.length > 0) {
        lastSeenLedgerId = rawLedgerEntries[0].ledger_entry_id;
        localStorage.setItem('paypulse_last_seen_ledger', String(lastSeenLedgerId));
    }
    updateInboxBadgeUI();
    showToast('Inbox marked as read.');
});

drawerInbox.addEventListener('click', (e) => {
    if (e.target === drawerInbox) closeInboxDrawer();
});

function renderInboxDrawer() {
    let entries = rawLedgerEntries;
    inboxTotalCount.textContent = `${entries.length} items`;

    if (currentLedgerFilter === 'debits') {
        entries = entries.filter(e => e.entry_type === 'DEBIT');
    } else if (currentLedgerFilter === 'credits') {
        entries = entries.filter(e => e.entry_type === 'CREDIT');
    }

    if (entries.length === 0) {
        inboxItemsContainer.innerHTML = `
            <div class="text-center py-12 text-[#71717a] text-xs font-sans">
                No transactions found.
            </div>
        `;
        return;
    }

    inboxItemsContainer.innerHTML = entries.map(entry => {
        const isDebit = entry.entry_type === 'DEBIT';
        const typeBadge = isDebit
            ? `<span class="px-1.5 py-0.2 rounded bg-rose-500/10 text-rose-300 font-bold text-[10px]">SENT</span>`
            : `<span class="px-1.5 py-0.2 rounded bg-accent-500/10 text-accent-400 font-bold text-[10px]">RECEIVED</span>`;
        
        const amountColor = isDebit ? 'text-rose-300' : 'text-accent-400';
        const amountSign = isDebit ? '-' : '+';

        return `
            <div class="p-3 rounded-2xl bg-[#0c0e11] border border-[#242830] space-y-1.5 fade-in">
                <div class="flex items-center justify-between">
                    <div class="flex items-center space-x-2">
                        ${typeBadge}
                        <span class="text-[10px] text-[#71717a]">TXN #${entry.transaction_id}</span>
                    </div>
                    <span class="text-xs font-bold font-mono ${amountColor}">
                        ${amountSign} ৳${formatIntegerAmount(entry.amount_bdt)}
                    </span>
                </div>

                <div class="flex items-center justify-between text-[10px] text-[#71717a] pt-1 border-t border-[#1a1e24]">
                    <div>
                        <span>Balance:</span>
                        <span class="text-[#d4d4d8] font-mono font-medium">৳${formatIntegerAmount(entry.balance_after)}</span>
                    </div>
                    <span class="font-sans">${formatTime(entry.created_at)}</span>
                </div>
            </div>
        `;
    }).join('');
}

filterAll.addEventListener('click', () => {
    currentLedgerFilter = 'all';
    filterAll.className = 'px-2 py-0.5 rounded-lg bg-[#1f2329] text-white font-medium';
    filterDebits.className = 'px-2 py-0.5 rounded-lg text-[#71717a] hover:text-rose-400';
    filterCredits.className = 'px-2 py-0.5 rounded-lg text-[#71717a] hover:text-accent-400';
    renderInboxDrawer();
});

filterDebits.addEventListener('click', () => {
    currentLedgerFilter = 'debits';
    filterDebits.className = 'px-2 py-0.5 rounded-lg bg-rose-500/20 text-rose-300 font-medium';
    filterAll.className = 'px-2 py-0.5 rounded-lg text-[#71717a] hover:text-white';
    filterCredits.className = 'px-2 py-0.5 rounded-lg text-[#71717a] hover:text-accent-400';
    renderInboxDrawer();
});

filterCredits.addEventListener('click', () => {
    currentLedgerFilter = 'credits';
    filterCredits.className = 'px-2 py-0.5 rounded-lg bg-accent-500/20 text-accent-300 font-medium';
    filterAll.className = 'px-2 py-0.5 rounded-lg text-[#71717a] hover:text-white';
    filterDebits.className = 'px-2 py-0.5 rounded-lg text-[#71717a] hover:text-rose-400';
    renderInboxDrawer();
});

// ── Helpers ────────────────────────────────────────────────────────────────
function formatTime(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
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
