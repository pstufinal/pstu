import re

def patch_app_js():
    with open("static/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    # 1. Remove strict integer helpers
    js = re.sub(r'function parsePositiveInteger\(.*?\n}\n\nfunction formatIntegerAmount\(.*?\n}\n', '', js, flags=re.DOTALL)
    
    # 2. Fix balance format
    js = js.replace('const formatted = formatIntegerAmount(res.balance_bdt);', 'const formatted = res.balance_bdt;')
    
    # 3. Fix Send Money and Request Money validations
    js = js.replace('const integerAmount = parsePositiveInteger(rawAmount);', 'const amount = rawAmount;')
    js = js.replace('if (!integerAmount) {', 'if (!amount) {')
    js = js.replace('amount_bdt: integerAmount', 'amount_bdt: amount')
    js = js.replace("showToast('Amount must be a whole positive integer (e.g. 2500, no decimals).', 'error');", "showToast('Amount must be valid (e.g. 2500 or 2500.00).', 'error');")
    js = js.replace("showToast('Amount must be a whole positive integer (e.g. 1200, no decimals).', 'error');", "showToast('Amount must be valid (e.g. 1200 or 1200.00).', 'error');")
    
    # 4. Remove all remaining formatIntegerAmount usages
    js = js.replace('formatIntegerAmount(res.wallet_balance_bdt)', 'res.wallet_balance_bdt')
    js = js.replace('formatIntegerAmount(res.amount_bdt)', 'res.amount_bdt')
    js = js.replace('formatIntegerAmount(r.amount_bdt)', 'r.amount_bdt')
    js = js.replace('formatIntegerAmount(entry.amount_bdt)', 'entry.amount_bdt')
    js = js.replace('formatIntegerAmount(entry.balance_after)', 'entry.balance_after')
    
    # 5. Append missing frontend logic (Escrow, Arena, Scaling)
    missing_logic = """
// ── Escrow Logic ───────────────────────────────────────────────────────────
window.handleEscrowRelease = async function(trxCode) {
    try {
        const res = await apiCall(`/escrow/payments/${trxCode}/release`, { method: 'POST' });
        if (res) { showToast('Escrow released successfully', 'success'); loadDashboardData(); }
    } catch (e) {}
};
window.handleEscrowCancel = async function(trxCode) {
    try {
        const res = await apiCall(`/escrow/payments/${trxCode}/cancel`, { method: 'POST' });
        if (res) { showToast('Escrow cancelled', 'info'); loadDashboardData(); }
    } catch (e) {}
};

document.getElementById('form-escrow-hold')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const recipient = document.getElementById('escrow-recipient').value.trim();
    const rawAmount = document.getElementById('escrow-amount').value;
    const note = document.getElementById('escrow-note').value.trim() || null;
    const idempotencyKey = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `idemp-${Date.now()}`;
    
    try {
        const res = await apiCall('/escrow/payments', {
            method: 'POST',
            headers: { 'Idempotency-Key': idempotencyKey },
            body: JSON.stringify({ seller_username: recipient, amount_bdt: rawAmount, item_description: note })
        });
        if (res) {
            showToast('Escrow created successfully', 'success');
            document.getElementById('form-escrow-hold').reset();
            loadDashboardData();
        }
    } catch (e) {}
});

async function refreshEscrow() {
    const container = document.getElementById('container-escrow-list');
    if (!container) return;
    try {
        const res = await apiCall('/escrow/payments', {}, true);
        if (!res) return;
        if (res.length === 0) {
            container.innerHTML = `<div class="text-center py-8 text-[#71717a] text-xs">No escrows found.</div>`;
            return;
        }
        container.innerHTML = res.map(e => `
            <div class="p-3 rounded-2xl bg-[#0c0e11] border border-[#242830] flex items-center justify-between space-x-3 fade-in">
                <div>
                    <div class="text-xs font-bold text-white">${escapeHtml(e.trx_code)} - ৳${e.amount_bdt}</div>
                    <div class="text-[10px] text-[#71717a]">Buyer: ${escapeHtml(e.buyer)}, Seller: ${escapeHtml(e.seller)}</div>
                    <div class="text-[10px] text-[#71717a]">Status: ${e.status}</div>
                </div>
                <div class="flex flex-col space-y-1">
                    ${e.status === 'HELD' && e.buyer === currentUsername ? `<button onclick="handleEscrowRelease('${e.trx_code}')" class="px-2 py-1 bg-accent-500 text-stone-950 rounded text-xs font-bold">Release</button>` : ''}
                    ${e.status === 'HELD' && e.buyer === currentUsername ? `<button onclick="handleEscrowCancel('${e.trx_code}')" class="px-2 py-1 bg-rose-500 text-white rounded text-xs font-bold">Cancel</button>` : ''}
                </div>
            </div>
        `).join('');
    } catch(e) {}
}

const origLoadDash = loadDashboardData;
loadDashboardData = async function() {
    await origLoadDash();
    refreshEscrow();
    refreshScaling();
};

const origStartPoll = startPolling;
startPolling = function() {
    origStartPoll();
    const oldInt = pollInterval;
    clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
        if (authToken) {
            await Promise.all([ refreshBalance(), refreshRequests(), refreshLedgerHistory(true), refreshEscrow(), refreshScaling() ]);
        }
    }, 3500);
}

// ── Scaling Metrics ────────────────────────────────────────────────────────
async function refreshScaling() {
    const el = document.getElementById('scaling-metrics-content');
    if (!el) return;
    try {
        const res = await apiCall('/scaling/metrics', {}, true);
        if (res) {
            el.innerHTML = `
                <div>Connections: ${res.database_connections.active}/${res.database_connections.max} (${res.database_connections.utilization_percent})</div>
                <div>Status: ${res.scaling_plan.next_scaling_step}</div>
            `;
        }
    } catch (e) {}
}

// ── Concurrency Arena ──────────────────────────────────────────────────────
document.getElementById('btn-arena-run')?.addEventListener('click', async () => {
    const resultsEl = document.getElementById('arena-results');
    resultsEl.innerHTML = "Firing requests...";
    const reqs = [];
    for (let i = 0; i < 10; i++) {
        const idempotencyKey = crypto.randomUUID();
        reqs.push(apiCall('/transfers/send', {
            method: 'POST',
            headers: { 'Idempotency-Key': idempotencyKey },
            body: JSON.stringify({ recipient_username: 'ESCROW_HOLD', amount_bdt: "1.00", note: "arena" })
        }, true).catch(e => null));
    }
    const results = await Promise.all(reqs);
    const success = results.filter(r => r !== null).length;
    resultsEl.innerHTML = `Sent 10 requests. Success: ${success}. Expected: -৳${success}. Check balance.`;
    loadDashboardData();
});

// Add copy button to trx_code
const origRenderInbox = renderInboxDrawer;
renderInboxDrawer = function() {
    origRenderInbox();
    const container = document.getElementById('inbox-items-container');
    container.querySelectorAll('.txn-code').forEach(el => {
        el.innerHTML = `${el.innerText} <button class="ml-2 text-accent-500 hover:text-white" onclick="navigator.clipboard.writeText('${el.innerText}')">[Copy]</button>`;
    });
}
"""
    js += missing_logic

    # Fix renderInboxDrawer trx_code class
    js = js.replace('TXN #${entry.transaction_id}', '<span class="txn-code">${entry.trx_code}</span>')
    
    with open("static/app.js", "w", encoding="utf-8") as f:
        f.write(js)

def patch_index_html():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Update hints
    html = html.replace('inputmode="numeric" pattern="[0-9]*"', '')
    html = html.replace('1200', '1200 (whole taka only)')
    html = html.replace('2500', '2500 (whole taka only)')

    # 2. Add Escrow, Arena, and Scaling blocks
    addition = """
            <!-- 3. Escrow, Scaling, Arena -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                <!-- Escrow -->
                <div class="bg-[#15181d] border border-[#262b33] rounded-3xl p-6 shadow-xl flex flex-col justify-between">
                    <h3 class="text-sm font-bold text-white mb-4 pb-3 border-b border-[#242830]">Escrow Services</h3>
                    <form id="form-escrow-hold" class="space-y-3.5 mb-4">
                        <input type="text" id="escrow-recipient" required placeholder="Seller username" class="w-full bg-[#0c0e11] border border-[#262b33] rounded-xl px-3.5 py-2 text-sm text-white placeholder-[#52525b] focus:outline-none focus:border-accent-500 transition">
                        <input type="text" id="escrow-amount" required placeholder="Amount (whole taka only)" class="w-full bg-[#0c0e11] border border-[#262b33] rounded-xl px-3.5 py-2 text-sm text-white placeholder-[#52525b] focus:outline-none focus:border-accent-500 transition">
                        <input type="text" id="escrow-note" placeholder="Item description" class="w-full bg-[#0c0e11] border border-[#262b33] rounded-xl px-3.5 py-2 text-sm text-white placeholder-[#52525b] focus:outline-none focus:border-accent-500 transition">
                        <button type="submit" class="w-full bg-accent-500 hover:bg-accent-400 text-stone-950 font-bold py-2.5 rounded-xl transition shadow-md flex items-center justify-center text-xs">Create Escrow</button>
                    </form>
                    <div id="container-escrow-list" class="space-y-2 max-h-48 overflow-y-auto pr-1"></div>
                </div>

                <!-- Arena & Scaling -->
                <div class="bg-[#15181d] border border-[#262b33] rounded-3xl p-6 shadow-xl flex flex-col justify-between space-y-4">
                    <div>
                        <h3 class="text-sm font-bold text-white mb-2 border-b border-[#242830] pb-2">Scaling Metrics</h3>
                        <div id="scaling-metrics-content" class="text-xs text-[#71717a] font-mono">Loading...</div>
                    </div>
                    <div>
                        <h3 class="text-sm font-bold text-white mb-2 border-b border-[#242830] pb-2">Concurrency Arena</h3>
                        <button id="btn-arena-run" class="w-full bg-[#20252d] hover:bg-[#2b313c] text-accent-300 border border-accent-500/30 font-bold py-2.5 rounded-xl transition text-xs mb-2">Fire 10 Concurrent Transfers</button>
                        <div id="arena-results" class="text-xs text-[#a1a1aa] font-mono"></div>
                    </div>
                </div>
            </div>
"""
    # Insert right before </section> of view-dashboard
    html = html.replace('        </section>\n\n    </main>', addition + '        </section>\n\n    </main>')
    
    with open("static/index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    patch_app_js()
    patch_index_html()
