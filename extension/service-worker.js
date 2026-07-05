// Service worker to handle background operations and coordinate API calls

const BACKEND_URL = "http://127.0.0.1:8000";

// Handle installation and setup
chrome.runtime.onInstalled.addListener(() => {
  console.log("TikTok Maps Saver Extension Installed!");
});

// Listener for messages from popup.js
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "triggerPipeline") {
    // Process async to avoid blocking the sender
    handlePipelineTrigger(request.tabId).then(sendResponse);
    return true; // Keep connection open for async response
  }
});

async function handlePipelineTrigger(tabId) {
  try {
    // 1. Get TikTok page metadata from Content Script
    const scrapedData = await new Promise((resolve, reject) => {
      chrome.tabs.sendMessage(tabId, { action: "scrapeTikTok" }, (response) => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError.message);
        } else {
          resolve(response);
        }
      });
    });

    if (!scrapedData || !scrapedData.url) {
      return { success: false, error: "Not on a valid TikTok page or content script is not loaded." };
    }

    // 2. Call backend FastAPI service
    const response = await fetch(`${BACKEND_URL}/api/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: scrapedData.url,
        caption: scrapedData.caption || "",
        comments: scrapedData.comments || []
      })
    });

    if (!response.ok) {
      throw new Error(`Backend API returned error status: ${response.status}`);
    }

    const result = await response.json();
    return { success: true, task_id: result.task_id };

  } catch (err) {
    console.error("Error in background pipeline trigger:", err);
    return { success: false, error: String(err) };
  }
}
