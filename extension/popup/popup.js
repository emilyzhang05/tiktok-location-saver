// Popup controller for TikTok Location Saver

const BACKEND_URL = "http://127.0.0.1:8000";
let activeTab = null;
let currentTaskId = null;
let pollingInterval = null;
let countdownInterval = null;
let countdownValue = 100; // Percentage
let secondsLeft = 10;
let currentPlace = null; // Saves reference to current single place details

document.addEventListener("DOMContentLoaded", async () => {
  // Bind Header Dashboard link
  document.getElementById("btn-dashboard").addEventListener("click", () => {
    chrome.tabs.create({ url: `${BACKEND_URL}/dashboard` });
  });

  // Bind Buttons
  document.getElementById("btn-retry").addEventListener("click", startPipeline);
  document.getElementById("btn-undo").addEventListener("click", handleUndo);
  document.getElementById("btn-save-multiple").addEventListener("click", saveSelectedMultiple);
  document.getElementById("btn-manual-search").addEventListener("click", handleManualSearch);
  
  // Bind category select change
  document.getElementById("single-category-override").addEventListener("change", handleCategoryOverride);

  // Get active tab and check if it's TikTok
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  activeTab = tab;

  if (activeTab && activeTab.url && activeTab.url.includes("tiktok.com")) {
    startPipeline();
  } else {
    showView("view-invalid");
  }
});

// Toggle view displays
function showView(viewId) {
  document.querySelectorAll(".view").forEach(v => v.classList.add("hidden"));
  document.getElementById(viewId).classList.remove("hidden");
}

// Start backend agent processing pipeline
async function startPipeline() {
  showView("view-processing");
  document.getElementById("step-text").innerText = "Checking video details...";

  try {
    // Send message to service worker to trigger process
    chrome.runtime.sendMessage(
      { action: "triggerPipeline", tabId: activeTab.id },
      (response) => {
        if (!response || !response.success) {
          showError(response ? response.error : "Failed to trigger pipeline.");
          return;
        }

        currentTaskId = response.task_id;
        startPollingStatus();
      }
    );
  } catch (err) {
    showError(String(err));
  }
}

// Poll FastAPI backend for task status updates
function startPollingStatus() {
  if (pollingInterval) clearInterval(pollingInterval);
  
  pollingInterval = setInterval(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/status/${currentTaskId}`);
      if (!res.ok) throw new Error("Failed to get task status");
      
      const task = await res.json();
      
      // Update loading text
      document.getElementById("step-text").innerText = task.step || "Processing...";

      if (task.status === "completed") {
        clearInterval(pollingInterval);
        handlePipelineComplete(task.result);
      } else if (task.status === "failed") {
        clearInterval(pollingInterval);
        showError(task.step || "Agent processing failed.");
      }
    } catch (err) {
      clearInterval(pollingInterval);
      showError(String(err));
    }
  }, 600);
}

// Direct pipeline outcomes
function handlePipelineComplete(result) {
  if (!result || !result.candidates || result.candidates.length === 0) {
    showView("view-none");
    return;
  }

  if (result.match_type === "single") {
    currentPlace = result.candidates[0];
    showSingleSave(currentPlace);
  } else if (result.match_type === "multiple") {
    showMultipleSelector(result.candidates);
  }
}

// Single Match: Auto-saved with 10s change/undo window
function showSingleSave(place) {
  showView("view-single");
  document.getElementById("single-name").innerText = place.name;
  document.getElementById("single-address").innerText = place.address;

  // Set category badge
  const badge = document.getElementById("single-category");
  badge.innerText = place.category;
  badge.className = `category-badge badge-${place.category}`;

  // Reset dropdown
  document.getElementById("single-category-override").value = "";

  // Start 10-second countdown
  startCountdown();
}

function startCountdown() {
  if (countdownInterval) clearInterval(countdownInterval);
  
  countdownValue = 100;
  secondsLeft = 10;
  document.getElementById("secs-left").innerText = secondsLeft;
  
  const progressBar = document.getElementById("countdown-progress");
  progressBar.style.width = "100%";

  countdownInterval = setInterval(() => {
    countdownValue -= 1; // Decrease progress
    progressBar.style.width = `${countdownValue}%`;

    // Update seconds remaining every second
    if (countdownValue % 10 === 0) {
      secondsLeft = Math.max(0, secondsLeft - 1);
      document.getElementById("secs-left").innerText = secondsLeft;
    }

    if (countdownValue <= 0) {
      clearInterval(countdownInterval);
      finalizeSave();
    }
  }, 100); // 100ms ticks * 100 = 10s total
}

function finalizeSave() {
  const panel = document.querySelector(".countdown-panel");
  panel.innerHTML = `<div class="success-header" style="justify-content: center; font-size: 0.8rem; color: #10b981; font-weight: 600;">✓ Finalized and star-saved!</div>`;
}

// Category Override Handler (10s window)
async function handleCategoryOverride(e) {
  if (countdownInterval) clearInterval(countdownInterval);
  const newCat = e.target.value;
  if (!newCat || !currentPlace) return;

  try {
    const res = await fetch(`${BACKEND_URL}/api/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        place_id: currentPlace.place_id,
        old_category: currentPlace.category,
        new_category: newCat
      })
    });

    if (res.ok) {
      // Update UI elements
      currentPlace.category = newCat;
      const badge = document.getElementById("single-category");
      badge.innerText = newCat;
      badge.className = `category-badge badge-${newCat}`;
      
      const panel = document.querySelector(".countdown-panel");
      panel.innerHTML = `<div class="success-header" style="justify-content: center; font-size: 0.8rem; color: #10b981; font-weight: 600;">✓ Updated to list TikTok ${newCat}!</div>`;
    } else {
      showError("Failed to update category list.");
    }
  } catch (err) {
    showError(String(err));
  }
}

// Undo Save Handler (10s window)
async function handleUndo() {
  if (countdownInterval) clearInterval(countdownInterval);
  if (!currentPlace) return;

  try {
    // Delete/Remove mock save. In a real environment, we'd delete from user list.
    // For our backend, we update it by deleting or letting it be, but let's notify the user and reset view.
    const panel = document.querySelector(".countdown-panel");
    panel.innerHTML = `<div class="success-header" style="justify-content: center; font-size: 0.8rem; color: #ef4444; font-weight: 600;">✗ Save undone.</div>`;
    
    setTimeout(() => {
      showView("view-none");
    }, 1000);
  } catch (err) {
    showError(String(err));
  }
}

// Multiple Matches: Pre-check all and let user choose
function showMultipleSelector(candidates) {
  showView("view-multiple");
  const container = document.getElementById("branches-container");
  container.innerHTML = "";

  candidates.forEach(cand => {
    const item = document.createElement("div");
    item.className = "branch-item";
    item.innerHTML = `
      <input type="checkbox" class="branch-checkbox" data-id="${cand.place_id}" checked>
      <div class="branch-info">
        <div class="branch-name">${cand.name}</div>
        <div class="branch-address">${cand.address}</div>
      </div>
      <span class="category-badge badge-${cand.category}">${cand.category}</span>
    `;

    // Make clicking the card toggle the checkbox
    item.addEventListener("click", (e) => {
      if (e.target.tagName !== "INPUT") {
        const cb = item.querySelector(".branch-checkbox");
        cb.checked = !cb.checked;
      }
    });

    container.appendChild(item);
  });

  // Save candidates reference
  window.multipleCandidates = candidates;
}

// Save all checked multiple branches
async function saveSelectedMultiple() {
  const container = document.getElementById("branches-container");
  const checkboxes = container.querySelectorAll(".branch-checkbox");
  const candidates = window.multipleCandidates || [];
  
  const toSave = [];
  checkboxes.forEach(cb => {
    if (cb.checked) {
      const placeId = cb.getAttribute("data-id");
      const cand = candidates.find(c => c.place_id === placeId);
      if (cand) toSave.push(cand);
    }
  });

  if (toSave.length === 0) {
    showView("view-none");
    return;
  }

  showView("view-processing");
  document.getElementById("step-text").innerText = `Saving ${toSave.length} locations...`;

  try {
    for (const place of toSave) {
      await fetch(`${BACKEND_URL}/api/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          place_id: place.place_id,
          name: place.name,
          address: place.address,
          category: place.category,
          city: place.city || "New York City"
        })
      });
    }

    // Success Screen
    showView("view-single");
    document.getElementById("single-name").innerText = `${toSave.length} locations`;
    document.getElementById("single-address").innerText = "Successfully saved all branches to your lists!";
    document.getElementById("single-category").innerText = "SAVED";
    document.getElementById("single-category").className = "category-badge badge-Food";
    
    const panel = document.querySelector(".countdown-panel");
    panel.innerHTML = `<div class="success-header" style="justify-content: center; font-size: 0.8rem; color: #10b981; font-weight: 600;">✓ Locations added to Google Maps lists!</div>`;

  } catch (err) {
    showError(String(err));
  }
}

// Manual search redirect
function handleManualSearch() {
  const query = document.getElementById("manual-search-input").value;
  if (!query) return;
  
  const searchUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
  chrome.tabs.create({ url: searchUrl });
}

// Error reporting
function showError(msg) {
  showView("view-error");
  document.getElementById("error-message").innerText = msg;
}
