// --- CLOCK FUNCTION ---
function updateClock() {
    const clockElement = document.getElementById('live-clock');
    if (!clockElement) return;
    const now = new Date();
    clockElement.innerText = now.toLocaleString('en-GB', { 
        day: '2-digit', month: '2-digit', year: 'numeric', 
        hour: '2-digit', minute: '2-digit', second: '2-digit' 
    });
}
setInterval(updateClock, 1000);
updateClock();

// --- WEBSOCKET CONNECTION ---
const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${wsProtocol}://${window.location.host}/ws/dashboard`);

ws.onopen = () => {
    console.log("✅ Connected to OmniSense Backend");
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    renderDashboard(data);
};

// --- RENDER LOGIC ---
function renderDashboard(data) {
    // 1. Update Header Stats
    const activeCount = data.stats?.total_active || 0;
    const queuedCount = data.stats?.queued || 0;
    
    if (document.querySelector('.stat-box.active .stat-number')) {
        document.querySelector('.stat-box.active .stat-number').innerText = activeCount;
    }
    if (document.querySelector('.stat-box.pending .stat-number')) {
        document.querySelector('.stat-box.pending .stat-number').innerText = queuedCount;
    }

    // 2. Render Cards (ALL ACTIVE CALLS)
    const cardsContainer = document.querySelector('.cards-grid');
    if (cardsContainer) {
        cardsContainer.innerHTML = ''; // Clear existing cards

        // --- FIX: Use active_calls instead of queue, so Human calls show up ---
        let displayCalls = data.active_calls || [];
        
        // Filter out completed calls
        displayCalls = displayCalls.filter(c => c.status !== 'COMPLETED');
        
        // Sort by Severity (Highest First)
        displayCalls.sort((a, b) => b.severity_score - a.severity_score);

        if (displayCalls.length === 0) {
            cardsContainer.innerHTML = '<p style="color:#888; margin-left:10px;">No active calls.</p>';
        }

        displayCalls.forEach((call, index) => {
            const rank = index + 1;
            const severityClass = getSeverityClass(call.severity_score);
            const iconClass = getIconClass(call.emergency_type);
            const deptName = getDeptName(call.emergency_type);
            
            // Determine Assignment Label
            let assignedLabel = "AI Agent";
            let assignedClass = "badge-ai";
            if (call.assigned_to && call.assigned_to !== "AI_AGENT") {
                assignedLabel = `Officer ${call.assigned_to}`;
                assignedClass = "badge-human";
            }

            // Prioritize AI Summary
            let summaryText = "Processing details...";
            if (call.summary && call.summary !== "Processing...") {
                summaryText = call.summary;
            } else if (call.transcript && call.transcript.length > 0) {
                summaryText = `"${call.transcript[call.transcript.length - 1].text}"`;
            }
            
            const html = `
            <div class="card" style="border-left: 5px solid ${severityClass}">
                <div class="card-header-badges">
                    <div class="badge">#${rank}</div>
                    <div class="badge ${assignedClass}">${assignedLabel}</div>
                </div>
                
                <div class="card-top">
                    <div class="dept-name">${deptName} <span>Department</span></div>
                    <i class="${iconClass}"></i>
                </div>
                <div class="card-inner">
                    <div class="inner-text">
                        <span class="sub">PROBLEM</span>
                        <h2>${formatType(call.emergency_type)}</h2>
                        <span class="sub">SEVERITY SCORE: ${call.severity_score}/100</span>
                        <p class="summary-text">${summaryText}</p>
                    </div>
                </div>
                <div class="card-bottom">
                    <div class="user">
                        <p><i class="fas fa-phone"></i> ${call.caller.phone_number}</p>
                        <p class="addr">
                            <i class="fas fa-map-marker-alt"></i> ${call.location?.address || "Location Unknown"}
                        </p>
                    </div>
                    <button class="btn-call"><i class="fas fa-phone-alt rotate"></i></button>
                </div>
            </div>
            `;
            cardsContainer.innerHTML += html;
        });
    }

    // 3. Render Sidebar (Compact List)
    const tableContainer = document.querySelector('.table-container');
    if (tableContainer) {
        let colPriority = '<div class="col"><h3>PRIORITY</h3>';
        let colDept = '<div class="col"><h3>DEPARTMENT</h3>';
        let colStatus = '<div class="col"><h3>STATUS</h3>';

        // Show top 5 active calls in sidebar
        (data.active_calls || [])
            .filter(c => c.status !== 'COMPLETED')
            .sort((a, b) => b.severity_score - a.severity_score)
            .slice(0, 5)
            .forEach(call => {
                colPriority += `<div class="row-item ${call.severity_level}">${call.severity_level.toUpperCase()}</div>`;
                colDept += `<div class="row-item">${getDeptName(call.emergency_type).toUpperCase()}</div>`;
                colStatus += `<div class="row-item">${call.status}</div>`;
            });
        
        colPriority += '</div>';
        colDept += '</div>';
        colStatus += '</div>';

        tableContainer.innerHTML = `
            ${colPriority}
            ${colDept}
            ${colStatus}
        `;
    }
}

// --- HELPER FUNCTIONS ---
function getSeverityClass(score) {
    if (score >= 80) return '#ff2b2b'; // Critical Red
    if (score >= 50) return '#ff9800'; // Orange
    return '#4caf50'; // Green
}

function getIconClass(type) {
    if (!type) return 'fas fa-exclamation-circle';
    const t = type.toLowerCase();
    if (t.includes('fire')) return 'fas fa-fire icon-orange';
    if (t.includes('medical') || t.includes('cardiac') || t.includes('injury')) return 'fas fa-plus-circle icon-blue';
    if (t.includes('police') || t.includes('theft') || t.includes('crime')) return 'fas fa-shield-alt icon-black';
    return 'fas fa-exclamation-circle';
}

function getDeptName(type) {
    if (!type) return 'General';
    const t = type.toLowerCase();
    if (t.includes('fire')) return 'Fire';
    if (t.includes('medical') || t.includes('cardiac') || t.includes('injury')) return 'Health';
    if (t.includes('police') || t.includes('crime')) return 'Police';
    return 'General';
}

function formatType(type) {
    if (!type) return 'UNKNOWN';
    return type.replace(/_/g, ' ').toUpperCase();
}