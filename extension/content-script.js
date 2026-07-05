// Content script to scrape TikTok video elements

function scrapeData() {
  const url = window.location.href;
  
  // Try selectors for TikTok descriptions/captions
  let caption = "";
  const descEl = document.querySelector('h1[data-e2e="browse-video-desc"]') || 
                 document.querySelector('div[data-e2e="video-desc"]') ||
                 document.querySelector('[class*="-DivDesc"]');
  if (descEl) {
    caption = descEl.innerText || "";
  }

  // Try selectors for comments
  const commentEls = document.querySelectorAll('p[data-e2e="comment-text"]') || 
                     document.querySelectorAll('[class*="-PCommentText"]');
  const comments = [];
  commentEls.forEach((el, index) => {
    if (index < 10) { // Limit to top 10 comments to keep payload light
      comments.push(el.innerText || "");
    }
  });

  // Try to find subtitles / closed captions on-screen
  let subtitles = "";
  const subtitleEl = document.querySelector('[class*="-DivCaptionWrapper"]') ||
                     document.querySelector('.tiktok-captions-text') ||
                     document.querySelector('[class*="-Subtitle"]');
  if (subtitleEl) {
    subtitles = subtitleEl.innerText || "";
  }

  return {
    url: url,
    caption: caption,
    comments: comments,
    subtitles: subtitles
  };
}

// Set up event message listener from service worker
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "scrapeTikTok") {
    const payload = scrapeData();
    sendResponse(payload);
  }
  return true; // Keep message channel open
});
