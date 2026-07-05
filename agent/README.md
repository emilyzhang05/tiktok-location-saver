# TikTok Location Saver - Backend Server

This is the Python backend server built using Google's Agent Development Kit (ADK) and FastAPI. It processes video extraction requests, runs the multi-agent pipeline, queries location APIs, and hosts the visual history dashboard.

---

## 🛠️ Requirements

Before starting, ensure you have installed:
* **Python 3.13**
* **uv**: Extremely fast Python package manager and environment runner - [Install Guide](https://docs.astral.sh/uv/getting-started/installation/)

---

## 🚀 Setup & Execution

### Step 1: Configure Credentials
1. Get a Gemini API Key from [Google AI Studio](https://aistudio.google.com/app/api-keys).
2. Open the `.env` file at `agent/app/.env` and paste your key:
   ```env
   GOOGLE_API_KEY=YOUR_API_KEY_HERE
   ```

### Step 2: Start the FastAPI Server
Run the following command in the `agent/` directory to automatically download dependencies, prepare the environment, and spin up the server:
```bash
uv run python -m app.fast_api_app
```
The backend server will run on `http://localhost:8000`. You can visit the interactive history dashboard in your browser at:
👉 `http://localhost:8000/dashboard`

---

## 🧪 Testing & Validation

### Running Offline Mock Tests
To verify the extraction logic, classification routing, and OpenStreetMap fallback handlers without consuming Gemini API tokens, run the mock test suite:
```bash
uv run pytest tests/unit/test_fast_api_mock.py
```

### Running Evaluation Datasets
We configure a custom evaluation suite under `tests/eval` to check for security containment (PII scrubbing, prompt injection defense) and categorization routing accuracy:
```bash
# Generate trace logs for the test cases
make generate-traces

# Grade trace logs using custom LLM-as-judge metrics
make grade
```
Traces will be stored in `artifacts/traces/generated_traces.json` for review.
