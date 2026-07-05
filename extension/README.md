# TikTok Location Saver - Chrome Extension

A Manifest V3 Chrome Extension providing a glassmorphic dark-mode popup to save travel and food recommendations from TikTok videos instantly.

---

## 🛠️ Installation

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Turn on **Developer mode** using the toggle switch in the top-right corner.
3. Click the **Load unpacked** button in the top-left corner.
4. Select the `extension/` folder in your file system:
   ```text
   tiktok-location-saver/extension/
   ```

The extension icon will now appear in your browser's toolbar!

---

## 🚀 How to Use

1. Ensure the backend FastAPI server is running on `http://localhost:8000`.
2. Open any TikTok video on your browser (e.g. searching for *"NYC food vlogs"*).
3. Click the **TikTok Location Saver** extension icon in your browser toolbar.
4. Click **Save Location**.
5. **Resolve Branches**: If multiple matching places are found, check the ones you wish to save.
6. **Countdown Timer**: A 10-second progress bar will start. If the category classification was wrong (e.g., Shopping instead of Food), you can override it using the dropdown before the timer runs out!
7. **View Map**: Click **Go to Dashboard** in the popup header to see your saved pins plotted on the interactive dark map!
