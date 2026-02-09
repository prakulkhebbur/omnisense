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
    
    document.querySelector('.stat-box.active .stat-number').innerText = activeCount;
    document.querySelector('.stat-box.pending .stat-number').innerText = queuedCount;

    // 2. Render Cards (The Priority Queue)
    const cardsContainer = document.querySelector('.cards-grid');
    cardsContainer.innerHTML = ''; // Clear existing cards

    if (!data.queue || data.queue.length === 0) {
        cardsContainer.innerHTML = '<h3 style="color:white; opacity:0.5; padding:20px;">No critical calls in queue.</h3>';
    }

    (data.queue || []).forEach((call, index) => {
        const rank = index + 1;
        const severityClass = getSeverityClass(call.severity_score);
        const iconClass = getIconClass(call.emergency_type);
        const deptName = getDeptName(call.emergency_type);
        const transcriptEntries = Array.isArray(call.transcript) ? call.transcript : [];
        const latestTranscript = transcriptEntries.length
            ? transcriptEntries[transcriptEntries.length - 1]?.text
            : null;
        const summaryText = latestTranscript || "No details available.";
        
        const html = `
          <div class="card" style="border-left: 5px solid ${severityClass}">
            <div class="badge">#${rank}</div>
            <div class="card-top">
              <div class="dept-name">${deptName} <span>Department</span></div>
              <i class="${iconClass}"></i>
            </div>
            <div class="card-inner">
              <div class="inner-text">
                <span class="sub">PROBLEM</span>
                <h2>${formatType(call.emergency_type)}</h2>
                <span class="sub">SEVERITY SCORE: ${call.severity_score}/100</span>
                <p>${summaryText}</p>
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

    // 3. Render Sidebar (Active/Dispatching)
    // We will list the top 4 active calls here
    const tableContainer = document.querySelector('.table-container');
    
    // Build columns HTML manually to match existing CSS structure
    let colPriority = '<h3>PRIORITY</h3>';
    let colDept = '<h3>DEPARTMENT</h3>';
    let colStatus = '<h3>STATUS</h3>';

    (data.active_calls || []).slice(0, 5).forEach(call => {
        colPriority += `<p>${call.severity_level.toUpperCase()}</p>`;
        colDept += `<p>${getDeptName(call.emergency_type).toUpperCase()}</p>`;
        colStatus += `<p>${call.status}</p>`;
    });

    tableContainer.innerHTML = `
        <div class="col">${colPriority}</div>
        <div class="col">${colDept}</div>
        <div class="col">${colStatus}</div>
    `;
}

// --- HELPER FUNCTIONS ---
function getSeverityClass(score) {
    if (score >= 80) return '#ff2b2b'; // Critical Red
    if (score >= 50) return '#ff9800'; // Orange
    return '#4caf50'; // Green
}

function getIconClass(type) {
    if (type.includes('fire')) return 'fas fa-fire icon-orange';
    if (type.includes('medical') || type.includes('cardiac')) return 'fas fa-plus-circle icon-blue';
    if (type.includes('police') || type.includes('theft')) return 'fas fa-shield-alt icon-black';
    return 'fas fa-exclamation-circle';
}

function getDeptName(type) {
    if (type.includes('fire')) return 'Fire';
    if (type.includes('medical') || type.includes('cardiac')) return 'Health';
    if (type.includes('police')) return 'Police';
    return 'General';
}

function formatType(type) {
    return type.replace(/_/g, ' ').toUpperCase();
}
