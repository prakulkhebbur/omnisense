function updateClock() {
    const now = new Date();

    // Time (HH:MM:SS)
    const hours = String(now.getHours()).padStart(2, "0");
    const minutes = String(now.getMinutes()).padStart(2, "0");
    const seconds = String(now.getSeconds()).padStart(2, "0");

    // Date (DD-MM-YYYY)
    const day = String(now.getDate()).padStart(2, "0");
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const year = now.getFullYear();

    const timeString = `${hours}:${minutes}:${seconds}`;
    const dateString = `${day}-${month}-${year}`;

    document.querySelector(".time-display").textContent = timeString;
    document.querySelector(".date-display").textContent = dateString;
}

// Run once immediately
updateClock();

// Update every second
setInterval(updateClock, 1000);


function initLiveMap() {
  // Center location (change to your city if needed)
  const map = L.map("live-map").setView([29.2195, 79.5124], 13);

  // Map tiles (OpenStreetMap - free)
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map);

  // Sample live call markers
  const calls = [
    { lat: 29.2205, lng: 79.5102, label: "Cardiac Arrest" },
    { lat: 29.2152, lng: 79.5208, label: "House on Fire" },
    { lat: 29.2251, lng: 79.5001, label: "Road Accident" },
  ];

  calls.forEach((call) => {
    L.marker([call.lat, call.lng])
      .addTo(map)
      .bindPopup(call.label);
  });
}

window.addEventListener("load", initLiveMap);

// Hover toggle for phone buttons
document.querySelectorAll(".call-action-btn.phone").forEach((btn) => {
  btn.addEventListener("mouseenter", () => {
    btn.classList.add("active");
  });

  btn.addEventListener("mouseleave", () => {
    btn.classList.remove("active");
  });
});

// Hover toggle for Active Calls & Pending Calls cards
document.querySelectorAll(".stat-card.active-calls, .stat-card.pending-calls").forEach((card) => {
  card.addEventListener("mouseenter", () => {
    card.classList.add("active");
  });

  card.addEventListener("mouseleave", () => {
    card.classList.remove("active");
  });
});

// Hover toggle for all call cards
document.querySelectorAll(".call-card").forEach((card) => {
  card.addEventListener("mouseenter", () => {
    card.classList.add("active");
  });

  card.addEventListener("mouseleave", () => {
    card.classList.remove("active");
  });
});

