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

from typing import List, Optional
from pydantic import BaseModel, Field

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

# Structured Output Schema for Location Extraction
class ExtractedLocation(BaseModel):
    place_name: Optional[str] = Field(
        default=None, 
        description="The name of the physical business, restaurant, shop, cafe, museum, landmark, or point of interest mentioned."
    )
    city: Optional[str] = Field(
        default=None, 
        description="The city, neighborhood, or country where this place is located (e.g. New York, Soho, Brooklyn, London)."
    )
    confidence: float = Field(
        default=0.0,
        description="Your confidence score from 0.0 (no location found) to 1.0 (certain)."
    )

# Structured Output Schema for Categorization
class PlaceCategory(BaseModel):
    category: str = Field(
        description="Must be exactly one of: 'Food', 'Shopping', or 'Sightseeing'."
    )
    reason: str = Field(
        description="A short explanation of why this category was selected."
    )

# Model configuration
model_config = Gemini(
    model="gemini-2.5-flash",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# Text Extractor Agent
text_extractor_agent = Agent(
    name="text_extractor_agent",
    model=model_config,
    instruction=(
        "You are an expert location extractor. Analyze the provided TikTok caption, description, "
        "and comments. Extract the name of the place being reviewed or visited, and the city/neighborhood "
        "where it is located. Ignore generic words. If no specific business or place name is mentioned, "
        "set place_name to null and confidence to 0.0.\n\n"
        "Output your response STRICTLY as a raw JSON object with the following fields:\n"
        "{\n"
        "  \"place_name\": string or null,\n"
        "  \"city\": string or null,\n"
        "  \"confidence\": float (0.0 to 1.0)\n"
        "}\n"
        "Do not wrap the JSON in markdown code blocks. Do not add any explanation or other text."
    ),
)

# Multimodal / Media Extractor Agent
media_extractor_agent = Agent(
    name="media_extractor_agent",
    model=model_config,
    instruction=(
        "You are an expert multimodal location extractor. Analyze the audio transcript and video descriptions. "
        "Identify the name of the physical place (restaurant, shop, museum, etc.) and city. "
        "If no specific place name is mentioned, set place_name to null and confidence to 0.0.\n\n"
        "Output your response STRICTLY as a raw JSON object with the following fields:\n"
        "{\n"
        "  \"place_name\": string or null,\n"
        "  \"city\": string or null,\n"
        "  \"confidence\": float (0.0 to 1.0)\n"
        "}\n"
        "Do not wrap the JSON in markdown code blocks. Do not add any explanation or other text."
    ),
)

# LLM-based Categorization Agent (Fallback)
categorizer_agent = Agent(
    name="categorizer_agent",
    model=model_config,
    instruction=(
        "You are a category routing expert. Classify the place into exactly one of these three categories:\n"
        "1. 'Food' (for restaurants, bakeries, cafes, bars, food trucks, ice cream shops, etc.)\n"
        "2. 'Shopping' (for clothing boutiques, malls, department stores, markets, retail shops, etc.)\n"
        "3. 'Sightseeing' (for museums, parks, historical landmarks, views, bridges, tourist attractions, etc.)\n\n"
        "Use the place name, address, and Google Places types to make your decision.\n\n"
        "Output your response STRICTLY as a raw JSON object with the following fields:\n"
        "{\n"
        "  \"category\": \"Food\" or \"Shopping\" or \"Sightseeing\",\n"
        "  \"reason\": string\n"
        "}\n"
        "Do not wrap the JSON in markdown code blocks. Do not add any explanation or other text."
    ),
)

# Model Context Protocol (MCP) Google Maps Server Integration
try:
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    from mcp import StdioServerParameters
    import os

    google_maps_mcp = McpToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-google-maps"],
            env={"GOOGLE_MAPS_API_KEY": os.environ.get("GOOGLE_API_KEY", "")}
        )
    )
    mcp_tools = [google_maps_mcp]
except Exception:
    mcp_tools = []

# Google Maps Resolver Agent using MCP Server
maps_agent = Agent(
    name="maps_agent",
    model=model_config,
    instruction=(
        "You are a mapping concierge. Use the registered Google Maps MCP tools "
        "to search for places, verify details, and resolve coordinates."
    ),
    tools=mcp_tools,
)

# Root agent that represents the app's agent registry entrypoint
root_agent = Agent(
    name="root_agent",
    model=model_config,
    instruction="Orchestrator for the TikTok Location Saver application.",
    sub_agents=[text_extractor_agent, media_extractor_agent, categorizer_agent, maps_agent],
)

app = App(
    root_agent=root_agent,
    name="app",
)
