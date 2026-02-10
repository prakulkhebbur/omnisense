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
    const completedCount = data.stats?.completed || 0;
    const queuedCount = data.stats?.queued || 0;
    
    if (document.querySelector('.stat-box.active .stat-number')) {
        document.querySelector('.stat-box.active .stat-number').innerText = activeCount;
    }
    if (document.querySelector('.stat-box.completed .stat-number')) {
        document.querySelector('.stat-box.completed .stat-number').innerText = completedCount;
    }
    if (document.querySelector('.stat-box.pending .stat-number')) {
        document.querySelector('.stat-box.pending .stat-number').innerText = queuedCount;
    }

    // 2. Render Cards (ALL ACTIVE CALLS)
    const cardsContainer = document.querySelector('.cards-grid');
    if (cardsContainer) {
        cardsContainer.innerHTML = ''; // Clear existing cards

        // Render active calls first, then show completed calls greyed out
        const activeCalls = (data.active_calls || []).slice();
        const completedCalls = (data.completed_calls || []).slice();

        // Sort active by severity (highest first)
        activeCalls.sort((a, b) => b.severity_score - a.severity_score);
        // Place completed calls after active (also sort by severity if desired)
        let displayCalls = activeCalls.concat(completedCalls);

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

            // Completed flag and archived flag
            const isCompleted = call.status === 'COMPLETED';
            const isArchived = !!call.archived;

            // If the call was cut/completed but not archived yet, hide who is handling
            if (isCompleted && !isArchived) {
                assignedLabel = '';
                assignedClass = '';
            }

            // Prioritize AI Summary
            let summaryText = "Processing details...";
            if (call.summary && call.summary !== "Processing...") {
                summaryText = call.summary;
            } else if (call.transcript && call.transcript.length > 0) {
                summaryText = `"${call.transcript[call.transcript.length - 1].text}"`;
            }
            
            const html = `
            <div class="card ${isArchived ? 'completed' : ''}" style="border-left: 5px solid ${severityClass}">
                <div class="card-header-badges">
                    <div class="badge">#${rank}</div>
                    ${assignedLabel ? `<div class="badge ${assignedClass}">${assignedLabel}</div>` : ''}
                </div>
                
                <div class="card-top">
                    <div class="dept-name"><i class="${iconClass} dept-icon"></i> ${deptName} <span>Department</span></div>
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
                    ${isCompleted && !isArchived ? `<button class="btn-end" onclick="endCall('${call.id}')">End Case</button>` : `<button class="btn-call" ${isCompleted ? 'disabled' : ''}><i class="fas fa-phone-alt rotate"></i></button>`}
                </div>
            </div>
            `;
            cardsContainer.innerHTML += html;
        });
    }

    // 3. Render Sidebar lists
    // Render pattern alerts into the video placeholder
    const videoPlaceholder = document.querySelector('.video-placeholder');
    if (videoPlaceholder) {
        if (data.patterns && data.patterns.length) {
            let html = '<h4 class="patterns-title">Detected Patterns</h4><ul class="patterns-list">';
            html += data.patterns.map(p => `<li class="pattern-item">${p}</li>`).join('');
            html += '</ul>';
            videoPlaceholder.innerHTML = html;
        } else {
            videoPlaceholder.innerHTML = '<div class="no-patterns">No significant patterns</div>';
        }
    }
    const priorityList = document.getElementById('priority-list');
    const departmentList = document.getElementById('department-list');
    const statusList = document.getElementById('status-list');

    // Clear lists
    if (priorityList) priorityList.innerHTML = '';
    if (departmentList) departmentList.innerHTML = '';
    if (statusList) statusList.innerHTML = '';

    // Show top 5 active calls in sidebar (exclude archived completed)
    const sidebarCalls = (data.active_calls || []).filter(c => !c.archived).sort((a, b) => b.severity_score - a.severity_score).slice(0, 5);
    sidebarCalls.forEach(call => {
        if (priorityList) priorityList.innerHTML += `<div class="row-item ${call.severity_level}">${call.severity_level.toUpperCase()}</div>`;
        if (departmentList) departmentList.innerHTML += `<div class="row-item">${getDeptName(call.emergency_type).toUpperCase()}</div>`;
        if (statusList) statusList.innerHTML += `<div class="row-item">${call.status}</div>`;
    });
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
    if (t.includes('rescue') || t.includes('animal')) return 'fas fa-life-ring icon-blue';
    if (t.includes('police') || t.includes('theft') || t.includes('crime')) return 'fas fa-shield-alt icon-black';
    return 'fas fa-exclamation-circle';
}

function getDeptName(type) {
    if (!type) return 'General';
    const t = type.toLowerCase();
    if (t.includes('fire')) return 'Fire';
    if (t.includes('medical') || t.includes('cardiac') || t.includes('injury')) return 'Health';
    if (t.includes('rescue')) return 'Rescue';
    if (t.includes('police') || t.includes('crime')) return 'Police';
    return 'General';
}

function formatType(type) {
    if (!type) return 'UNKNOWN';
    return type.replace(/_/g, ' ').toUpperCase();
}

// End call handler invoked by the dashboard button
function endCall(callId) {
    fetch(`/api/calls/${callId}/end`, { method: 'POST' })
        .then(resp => resp.json())
        .then(j => console.log('ended', j))
        .catch(e => console.error('end call failed', e));
}