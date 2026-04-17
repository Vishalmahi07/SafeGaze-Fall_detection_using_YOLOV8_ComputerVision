document.addEventListener('DOMContentLoaded', () => {
    const statusBadge = document.getElementById('status-badge');
    const alertsTbody = document.getElementById('alerts-tbody');
    const testBtn = document.getElementById('test-alert-btn');

    // Polling function for Status
    async function fetchStatus() {
        try {
            const res = await fetch('/status');
            const data = await res.json();
            
            if (data.status === 'FALL DETECTED') {
                statusBadge.textContent = 'FALL DETECTED';
                statusBadge.className = 'status-badge danger';
            } else {
                statusBadge.textContent = 'NORMAL';
                statusBadge.className = 'status-badge normal';
            }
        } catch (err) {
            console.error('Error fetching status:', err);
        }
    }

    // Polling function for Alerts
    async function fetchAlerts() {
        try {
            const res = await fetch('/alerts');
            const data = await res.json();
            
            alertsTbody.innerHTML = '';
            
            data.forEach(alert => {
                const tr = document.createElement('tr');
                
                const tdTime = document.createElement('td');
                tdTime.textContent = alert.timestamp;
                
                const tdStatus = document.createElement('td');
                const spanStatus = document.createElement('span');
                spanStatus.textContent = alert.status;
                spanStatus.className = alert.status.includes('FALL') ? 'status-tag fall' : 'status-tag';
                tdStatus.appendChild(spanStatus);
                
                tr.appendChild(tdTime);
                tr.appendChild(tdStatus);
                alertsTbody.appendChild(tr);
            });
        } catch (err) {
            console.error('Error fetching alerts:', err);
        }
    }

    // Trigger test alert
    testBtn.addEventListener('click', async () => {
        try {
            const res = await fetch('/test_alert', { method: 'POST' });
            const data = await res.json();
            if(data.success) {
                testBtn.textContent = 'Alert Triggered!';
                setTimeout(() => { testBtn.textContent = 'Test Alert'; }, 2000);
            }
        } catch(err) {
            console.error('Error triggering test:', err);
        }
    });

    // Start polling every 2 seconds
    setInterval(fetchStatus, 2000);
    setInterval(fetchAlerts, 2000);
    
    // Initial fetch
    fetchStatus();
    fetchAlerts();
});
