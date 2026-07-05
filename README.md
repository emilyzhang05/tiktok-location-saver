# TikTok-to-Google-Maps Location Saver

A secure travel concierge application that automatically extracts location recommendations from TikTok videos and comments, resolving coordinates via mapping APIs, and exporting them directly to your personal Google My Maps.

Built as a submission for the Google x Kaggle AI Course Capstone Project.

---

## 📌 Features

* **Multi-Agent Orchestration**: Powered by Google's Agent Development Kit (ADK) with five coordinated sub-agents (Orchestration, Text Extraction, Multimodal Media Fallbacks, Categorization, and MCP Maps Resolution).
* **Live Interactive Map**: Standalone web dashboard utilizing Leaflet.js to plot saved food, shopping, and sightseeing pins dynamically with custom color categories.
* **Google My Maps Sync**: Dynamically generates and downloads styled KML files with pre-colored folder layers (Food = Green, Shopping = Purple, Sightseeing = Blue) for instant import and sync with your mobile Google Maps app.
* **Security & Privacy Gateways**:
  * Programmatic PII Scrubbing: Automatically redacts email addresses, phone numbers, and API keys before they hit external LLM traces.
  * Decoupled AI Execution: The LLM acts solely as a parser returning JSON text; all file-writing and execution control remains in strict, locked-down server code to prevent prompt injection.
* **Human-in-the-Loop Checklist**: Lets users resolve multi-branch ambiguities (e.g. multiple "Joe's Pizza" locations in NYC) and correct categories within a 10-second countdown window.

---

## 📁 Project Structure

This repository is organized as a monorepo containing two sub-projects:

```text
tiktok-location-saver/
├── .gitignore              # Global git ignore rules (ignores .env, .venv, OS cache)
├── README.md               # ROOT README (this file)
│
├── agent/                  # Python Backend & AI Agent Project
│   ├── app/                # Core FastAPI app and tools logic
│   ├── tests/              # Offline unit test suites and eval configurations
│   ├── skills/             # Project-scoped ADK skills
│   ├── Dockerfile          # Container setup
│   ├── pyproject.toml      # Backend Python dependencies (FastAPI, google-genai)
│   └── README.md           # Technical guide for starting the Python server
│
└── extension/              # Chrome Extension Project
    ├── manifest.json       # MV3 permissions and background workers
    ├── content-script.js   # Content DOM scraping script
    ├── popup/              # Glassmorphic user interface popup
    └── README.md           # Instructions for loading the extension in Chrome
```

---

## 🚀 Quick Start Links

For detailed, step-by-step installation and run instructions, please refer to the sub-project guides:

1. **[Backend Server Setup Guide (agent/README.md)](file:///Users/zemil/Library/CloudStorage/OneDrive-NanyangTechnologicalUniversity/Google%20x%20Kaggle%20Course/Capstone%20Project/agent/README.md)** - Run the local FastAPI backend server and unit tests.
2. **[Chrome Extension Guide (extension/README.md)](file:///Users/zemil/Library/CloudStorage/OneDrive-NanyangTechnologicalUniversity/Google%20x%20Kaggle%20Course/Capstone%20Project/extension/README.md)** - Install the popup interface in Google Chrome.
