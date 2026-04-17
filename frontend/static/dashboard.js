// Dashboard JavaScript
document.addEventListener('DOMContentLoaded', () => {
    // ─── Elements ────────────────────────────────────────────────────────────
    const statUptime = document.getElementById('stat-uptime');
    const statStatus = document.getElementById('stat-status');
    const statStatusTrend = document.getElementById('stat-status-trend');
    const statAlerts = document.getElementById('stat-alerts');
    const alertsList = document.getElementById('alerts-list');
    const alertsEmpty = document.getElementById('alerts-empty');
    const alertsCountBadge = document.getElementById('alerts-count-badge');
    const navAlertCount = document.getElementById('nav-alert-count');
    const testBtn = document.getElementById('test-alert-dash-btn');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');

    // ─── Uptime Counter ───────────────────────────────────────────────────────
    const startTime = Date.now();
    function updateUptime() {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const h = Math.floor(elapsed / 3600).toString().padStart(2, '0');
        const m = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
        const s = (elapsed % 60).toString().padStart(2, '0');
        if (statUptime) statUptime.textContent = `${h}:${m}:${s}`;
    }
    setInterval(updateUptime, 1000);
    updateUptime();

    // ─── Sidebar Toggle ───────────────────────────────────────────────────────
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }

    // ─── Fetch Status ─────────────────────────────────────────────────────────
    async function fetchStatus() {
        try {
            const res = await fetch('/status');
            if (!res.ok) return;
            const data = await res.json();
            if (!statStatus) return;

            if (data.status === 'FALL DETECTED') {
                statStatus.textContent = 'FALL';
                statStatus.style.color = '#f87171';
                if (statStatusTrend) {
                    statStatusTrend.textContent = '⚠ DETECTED';
                    statStatusTrend.className = 'stat-trend stat-trend-down';
                }
            } else {
                statStatus.textContent = 'Normal';
                statStatus.style.color = '#34d399';
                if (statStatusTrend) {
                    statStatusTrend.textContent = 'Monitoring';
                    statStatusTrend.className = 'stat-trend stat-trend-up';
                }
            }
        } catch (err) {
            console.error('Status fetch error:', err);
        }
    }

    // ─── Fetch Alerts ─────────────────────────────────────────────────────────
    async function fetchAlerts() {
        try {
            const res = await fetch('/alerts');
            if (!res.ok) return;
            const data = await res.json();

            if (statAlerts) statAlerts.textContent = data.length;
            if (alertsCountBadge) alertsCountBadge.textContent = data.length;
            if (navAlertCount) navAlertCount.textContent = data.length;

            if (!alertsList) return;

            // Clear existing items (keep the empty placeholder)
            const existingItems = alertsList.querySelectorAll('.alert-item');
            existingItems.forEach(el => el.remove());

            if (data.length === 0) {
                if (alertsEmpty) alertsEmpty.style.display = 'flex';
                return;
            }
            if (alertsEmpty) alertsEmpty.style.display = 'none';

            data.slice(0, 10).forEach((alert, idx) => {
                const isFall = alert.status && alert.status.includes('FALL');
                const item = document.createElement('div');
                item.className = 'alert-item';
                item.style.animationDelay = `${idx * 0.05}s`;

                item.innerHTML = `
                    <div class="alert-dot ${isFall ? 'alert-dot-fall' : 'alert-dot-normal'}"></div>
                    <div class="alert-info">
                        <div class="alert-time">${alert.timestamp || 'Unknown time'}</div>
                        <div class="alert-status-tag">${alert.status || 'Event'}</div>
                    </div>
                    <span class="alert-badge ${isFall ? 'alert-badge-fall' : 'alert-badge-normal'}">
                        ${isFall ? 'FALL' : 'OK'}
                    </span>
                `;
                alertsList.appendChild(item);
            });
        } catch (err) {
            console.error('Alerts fetch error:', err);
        }
    }

    // ─── Test Alert Button ────────────────────────────────────────────────────
    if (testBtn) {
        testBtn.addEventListener('click', async () => {
            const originalHTML = testBtn.innerHTML;
            testBtn.disabled = true;
            testBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" style="animation:spin 0.8s linear infinite">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                </svg>
                Sending…
            `;

            try {
                const res = await fetch('/test_alert', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    testBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16"><polyline points="20 6 9 17 4 12"/></svg> Sent!`;
                    setTimeout(() => {
                        testBtn.innerHTML = originalHTML;
                        testBtn.disabled = false;
                    }, 2500);
                } else {
                    testBtn.innerHTML = `⏳ On Cooldown`;
                    setTimeout(() => {
                        testBtn.innerHTML = originalHTML;
                        testBtn.disabled = false;
                    }, 2000);
                }
            } catch (err) {
                console.error('Test alert error:', err);
                testBtn.innerHTML = originalHTML;
                testBtn.disabled = false;
            }
        });
    }

    // ─── Add spin keyframes dynamically ──────────────────────────────────────
    const style = document.createElement('style');
    style.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
    document.head.appendChild(style);

    // ─── Initial Fetch + Polling ──────────────────────────────────────────────
    fetchStatus();
    fetchAlerts();
    setInterval(fetchStatus, 3000);
    setInterval(fetchAlerts, 3000);
});
