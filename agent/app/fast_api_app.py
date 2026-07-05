# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import contextlib
import json
import logging
import os
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import google.auth
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.apps import App as AdkApp

from app.agent import text_extractor_agent, media_extractor_agent, categorizer_agent, root_agent
from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.telemetry import setup_telemetry
from app.tools import download_tiktok_media, transcribe_audio, google_maps_search, google_maps_save_location, google_maps_update_list

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env variables from .env manually
def load_env_file():
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            os.environ[key] = val
                            # Make sure GEMINI_API_KEY is also set if GOOGLE_API_KEY is provided
                            if key == "GOOGLE_API_KEY":
                                os.environ["GEMINI_API_KEY"] = val
            except Exception as e:
                logger.error(f"Failed to load env file {path}: {e}")

load_env_file()
setup_telemetry()

# Path for persistent saved places JSON
PERSISTENT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    "saved_places.json"
)

# Global in-memory task store for async processing
TASKS: Dict[str, Dict[str, Any]] = {}
# Concurrency lock for saved_places.json file access
db_lock = asyncio.Lock()

# Pydantic models for request bodies
class ProcessRequest(BaseModel):
    url: str
    caption: str
    comments: List[str]

class SaveRequest(BaseModel):
    place_id: str
    name: str
    address: str
    category: str  # Food, Shopping, Sightseeing
    city: str

class UpdateCategoryRequest(BaseModel):
    place_id: str
    old_category: str
    new_category: str

# Helper to scrub PII from strings
def scrub_pii(text: str) -> str:
    # Emails
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED_EMAIL]", text)
    # Phone numbers (common formats)
    text = re.sub(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[REDACTED_PHONE]", text)
    # Generic API Keys / Auth patterns (e.g. AIzaSy...)
    text = re.sub(r"\bAIzaSy[A-Za-z0-9_-]{33}\b", "[REDACTED_KEY]", text)
    return text

# Helper to run an ADK agent in-memory with a custom prompt
async def run_agent(agent_obj, prompt: str) -> Dict[str, Any]:
    from google.genai import types
    temp_app = AdkApp(name="temp_app", root_agent=agent_obj)
    temp_runner = Runner(
        app=temp_app,
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
        auto_create_session=True,
    )
    new_message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for _ in temp_runner.run_async(
        user_id="temp_user",
        session_id="temp_session",
        new_message=new_message
    ):
        pass
    session = await temp_runner.session_service.get_session(app_name=temp_runner.app_name, user_id="temp_user", session_id="temp_session")
    
    # Extract text response from the session
    model_text = ""
    for event in reversed(session.events):
        if event.author == agent_obj.name and event.content:
            for part in event.content.parts:
                if part.text:
                    model_text += part.text
            if model_text:
                break
                
    # Parse the JSON
    parsed_dict = {}
    if model_text:
        try:
            # Strip markdown code blocks if any
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", model_text, re.DOTALL)
            if match:
                model_text = match.group(1)
            parsed_dict = json.loads(model_text.strip())
        except Exception:
            # Fallback regex parsing if JSON format is slightly off
            name_match = re.search(r'"place_name"\s*:\s*"(.*?)"', model_text)
            city_match = re.search(r'"city"\s*:\s*"(.*?)"', model_text)
            conf_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', model_text)
            cat_match = re.search(r'"category"\s*:\s*"(.*?)"', model_text)
            if name_match:
                parsed_dict["place_name"] = name_match.group(1)
            if city_match:
                parsed_dict["city"] = city_match.group(1)
            if conf_match:
                parsed_dict["confidence"] = float(conf_match.group(1))
            if cat_match:
                parsed_dict["category"] = cat_match.group(1)
                
    # Map to the key structure expected by the backend logic
    if agent_obj.name in ("text_extractor_agent", "media_extractor_agent"):
        return {"extracted_location": parsed_dict}
    elif agent_obj.name == "categorizer_agent":
        return {"place_category": parsed_dict}
    return parsed_dict

# Background task processing pipeline
async def process_tiktok_pipeline(task_id: str, url: str, caption: str, comments: List[str]):
    try:
        TASKS[task_id]["step"] = "Scrubbing PII and personal info..."
        await asyncio.sleep(0.5)
        
        clean_caption = scrub_pii(caption)
        clean_comments = [scrub_pii(c) for c in comments]

        # Combine text context
        text_context = f"Caption: {clean_caption}\nComments:\n" + "\n".join(clean_comments)

        TASKS[task_id]["step"] = "Extracting location references..."
        state = await run_agent(text_extractor_agent, text_context)
        extracted = state.get("extracted_location", {})

        place_name = extracted.get("place_name")
        city = extracted.get("city")
        confidence = extracted.get("confidence", 0.0)

        # Fallback to multimodal visual/audio if text confidence is low
        if (not place_name or confidence < 0.5):
            TASKS[task_id]["step"] = "Downloading TikTok media (audio/frames)..."
            media_info = download_tiktok_media(url)
            
            TASKS[task_id]["step"] = "Transcribing audio and scanning text overlays..."
            transcription = transcribe_audio(media_info.get("audio_path"))
            media_context = f"Subtitles/Audio: {transcription}\nDescription: {media_info.get('description', '')}"
            
            media_state = await run_agent(media_extractor_agent, media_context)
            extracted_media = media_state.get("extracted_location", {})
            if extracted_media.get("place_name"):
                place_name = extracted_media.get("place_name")
                city = extracted_media.get("city") or city
                confidence = extracted_media.get("confidence", 0.0)

        if not place_name:
            TASKS[task_id]["status"] = "completed"
            TASKS[task_id]["step"] = "Finished"
            TASKS[task_id]["result"] = {"match_type": "none", "candidates": []}
            return

        TASKS[task_id]["step"] = f"Searching Google Maps for '{place_name}'..."
        candidates = google_maps_search(place_name, city)

        if not candidates:
            # Try a broader search
            candidates = google_maps_search(place_name)

        if not candidates:
            TASKS[task_id]["status"] = "completed"
            TASKS[task_id]["step"] = "Finished"
            TASKS[task_id]["result"] = {"match_type": "none", "candidates": []}
            return

        # Determine category for candidates
        TASKS[task_id]["step"] = "Categorizing location type..."
        for cand in candidates:
            # Check simple types first deterministically
            types_list = cand.get("types", [])
            category = "Food"  # default
            
            food_types = {'restaurant', 'food', 'cafe', 'bar', 'bakery', 'meal_takeaway'}
            shopping_types = {'clothing_store', 'shopping_mall', 'store', 'shoe_store', 'supermarket'}
            sightseeing_types = {'tourist_attraction', 'museum', 'park', 'amusement_park', 'place_of_worship'}
            
            matched = False
            for t in types_list:
                if t in food_types:
                    category = "Food"
                    matched = True
                    break
                elif t in shopping_types:
                    category = "Shopping"
                    matched = True
                    break
                elif t in sightseeing_types:
                    category = "Sightseeing"
                    matched = True
                    break
            
            if not matched:
                # LLM fallback
                cat_prompt = f"Place Name: {cand['name']}\nTypes: {', '.join(types_list)}\nAddress: {cand['address']}"
                cat_state = await run_agent(categorizer_agent, cat_prompt)
                category = cat_state.get("place_category", {}).get("category", "Food")
            
            cand["category"] = category

        TASKS[task_id]["status"] = "completed"
        TASKS[task_id]["step"] = "Finished"
        
        if len(candidates) == 1:
            # Auto-save single matches
            single_place = candidates[0]
            google_maps_save_location(single_place["place_id"], single_place["category"])
            # Record locally
            await save_place_locally(single_place)
            TASKS[task_id]["result"] = {
                "match_type": "single",
                "candidates": candidates
            }
        else:
            # Multiple matches: let the user select
            TASKS[task_id]["result"] = {
                "match_type": "multiple",
                "candidates": candidates
            }
            
    except Exception as e:
        logger.error(f"Error in pipeline: {e}")
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["step"] = f"Error: {str(e)}"

# Helper to save a place locally to saved_places.json
async def save_place_locally(place: Dict[str, Any]):
    async with db_lock:
        places = []
        if os.path.exists(PERSISTENT_FILE):
            try:
                with open(PERSISTENT_FILE, "r") as f:
                    places = json.load(f)
            except Exception:
                places = []

        # Avoid duplicate place IDs
        places = [p for p in places if p.get("place_id") != place.get("place_id")]
        places.append(place)

        try:
            with open(PERSISTENT_FILE, "w") as f:
                json.dump(places, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write to local persistent file: {e}")

# Lifespan manager for the App
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Bootstrap ADK runner
    main_app = AdkApp(name="main_app", root_agent=root_agent)
    runner = Runner(
        app=main_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = "app"
    yield

# Main FastAPI App wrapping
allow_origins = ["*"]
AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)

app.title = "TikTok Maps Agent Backend"
app.description = "FastAPI Service supporting Chrome Extension and Saved Places Dashboard"

# Add CORS Middleware to support chrome extension requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API ENDPOINTS

@app.post("/api/process")
async def start_process(request: ProcessRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
        "status": "processing",
        "step": "Starting pipeline...",
        "result": None
    }
    background_tasks.add_task(
        process_tiktok_pipeline, 
        task_id, 
        request.url, 
        request.caption, 
        request.comments
    )
    return {"task_id": task_id}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

@app.post("/api/save")
async def save_location(request: SaveRequest):
    success = google_maps_save_location(request.place_id, request.category)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save to Google Maps")
    
    # Save locally for dashboard view
    await save_place_locally({
        "place_id": request.place_id,
        "name": request.name,
        "address": request.address,
        "category": request.category,
        "city": request.city,
        "rating": 4.5
    })
    return {"status": "success"}

@app.post("/api/update")
async def update_location_category(request: UpdateCategoryRequest):
    success = google_maps_update_list(request.place_id, request.old_category, request.new_category)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update category list")

    # Update in local DB
    async with db_lock:
        if os.path.exists(PERSISTENT_FILE):
            try:
                with open(PERSISTENT_FILE, "r") as f:
                    places = json.load(f)
                for p in places:
                    if p.get("place_id") == request.place_id:
                        p["category"] = request.new_category
                with open(PERSISTENT_FILE, "w") as f:
                    json.dump(places, f, indent=2)
            except Exception as e:
                logger.error(f"Error updating local file: {e}")

    return {"status": "success"}

@app.get("/api/export/kml")
async def export_kml():
    from fastapi.responses import Response
    if not os.path.exists(PERSISTENT_FILE):
        return Response(content="<kml></kml>", media_type="application/vnd.google-earth.kml+xml")
    
    async with db_lock:
        try:
            with open(PERSISTENT_FILE, "r") as f:
                places = json.load(f)
        except Exception:
            places = []

    # Group places by category
    places_by_cat = {"Food": [], "Shopping": [], "Sightseeing": [], "Other": []}
    for p in places:
        cat = p.get("category", "Other")
        if cat not in places_by_cat:
            cat = "Other"
        places_by_cat[cat].append(p)

    kml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '  <Document>',
        '    <name>TikTok Saved Locations</name>',
        '    <description>Locations saved via TikTok Map Saver Agent</description>'
    ]

    # Custom styles for categories (KML color is aabbggrr format in hex)
    # Food (Green: #10b981 -> aabbggrr: ff81b910)
    kml_parts.append('    <Style id="style-Food">')
    kml_parts.append('      <IconStyle>')
    kml_parts.append('        <color>ff81b910</color>')
    kml_parts.append('        <scale>1.1</scale>')
    kml_parts.append('        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/grn-circle.png</href></Icon>')
    kml_parts.append('      </IconStyle>')
    kml_parts.append('    </Style>')

    # Shopping (Purple: #a855f7 -> aabbggrr: fff755a8)
    kml_parts.append('    <Style id="style-Shopping">')
    kml_parts.append('      <IconStyle>')
    kml_parts.append('        <color>fff755a8</color>')
    kml_parts.append('        <scale>1.1</scale>')
    kml_parts.append('        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/purple-circle.png</href></Icon>')
    kml_parts.append('      </IconStyle>')
    kml_parts.append('    </Style>')

    # Sightseeing (Blue: #0ea5e9 -> aabbggrr: ffe9a50e)
    kml_parts.append('    <Style id="style-Sightseeing">')
    kml_parts.append('      <IconStyle>')
    kml_parts.append('        <color>ffe9a50e</color>')
    kml_parts.append('        <scale>1.1</scale>')
    kml_parts.append('        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/blu-circle.png</href></Icon>')
    kml_parts.append('      </IconStyle>')
    kml_parts.append('    </Style>')

    # Other (Grey: aabbggrr: ff888888)
    kml_parts.append('    <Style id="style-Other">')
    kml_parts.append('      <IconStyle>')
    kml_parts.append('        <color>ff888888</color>')
    kml_parts.append('        <scale>1.1</scale>')
    kml_parts.append('        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/wht-circle.png</href></Icon>')
    kml_parts.append('      </IconStyle>')
    kml_parts.append('    </Style>')

    for cat, cat_places in places_by_cat.items():
        if not cat_places:
            continue
        kml_parts.append('    <Folder>')
        kml_parts.append(f'      <name>{cat}</name>')
        for p in cat_places:
            lat = p.get("latitude")
            lon = p.get("longitude")
            if lat and lon:
                desc = f"Category: {cat}\nAddress: {p.get('address')}"
                desc_escaped = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                name_escaped = p.get("name", "Unknown Place").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                address_escaped = p.get("address", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                
                kml_parts.append('      <Placemark>')
                kml_parts.append(f'        <name>{name_escaped}</name>')
                kml_parts.append(f'        <description>{desc_escaped}</description>')
                kml_parts.append(f'        <styleUrl>#style-{cat}</styleUrl>')
                kml_parts.append('        <ExtendedData>')
                kml_parts.append('          <Data name="Category">')
                kml_parts.append(f'            <value>{cat}</value>')
                kml_parts.append('          </Data>')
                kml_parts.append('          <Data name="Address">')
                kml_parts.append(f'            <value>{address_escaped}</value>')
                kml_parts.append('          </Data>')
                kml_parts.append('        </ExtendedData>')
                kml_parts.append('        <Point>')
                kml_parts.append(f'          <coordinates>{lon},{lat},0</coordinates>')
                kml_parts.append('        </Point>')
                kml_parts.append('      </Placemark>')
        kml_parts.append('    </Folder>')

    kml_parts.append('  </Document>')
    kml_parts.append('</kml>')

    kml_content = "\n".join(kml_parts)
    headers = {
        "Content-Disposition": "attachment; filename=tiktok_saved_locations.kml"
    }
    return Response(content=kml_content, media_type="application/vnd.google-earth.kml+xml", headers=headers)

@app.get("/api/history")
async def get_saved_history():
    if not os.path.exists(PERSISTENT_FILE):
        return []
    async with db_lock:
        try:
            with open(PERSISTENT_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

# Serve the HTML Dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def view_dashboard():
    dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r") as f:
            return f.read()
    return "<h1>Dashboard file not found. Please create dashboard.html in app/ folder.</h1>"

# Main execution
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
