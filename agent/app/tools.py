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

import logging
import os
import re
from typing import Any, Dict, List, Optional
import yt_dlp

logger = logging.getLogger(__name__)

# Mock database for offline testing & validation
MOCK_PLACES = {
    "l'industrie pizzeria": [
        {
            "place_id": "ch_l_industrie_nyc",
            "name": "L'Industrie Pizzeria",
            "address": "254 S 2nd St, Brooklyn, NY 11211",
            "city": "New York City",
            "types": ["restaurant", "food", "point_of_interest"],
            "rating": 4.8,
            "latitude": 40.7116,
            "longitude": -73.9578,
        }
    ],
    "soho bagels": [
        {
            "place_id": "ch_soho_bagels_nyc",
            "name": "Soho Bagels",
            "address": "120 Prince St, New York, NY 10012",
            "city": "New York City",
            "types": ["restaurant", "food", "bakery"],
            "rating": 4.5,
            "latitude": 40.7252,
            "longitude": -74.0012,
        }
    ],
    "moma": [
        {
            "place_id": "ch_moma_nyc",
            "name": "Museum of Modern Art (MoMA)",
            "address": "11 W 53rd St, New York, NY 10019",
            "city": "New York City",
            "types": ["museum", "tourist_attraction", "point_of_interest"],
            "rating": 4.7,
            "latitude": 40.7614,
            "longitude": -73.9776,
        }
    ],
    "museum of modern art": [
        {
            "place_id": "ch_moma_nyc",
            "name": "Museum of Modern Art (MoMA)",
            "address": "11 W 53rd St, New York, NY 10019",
            "city": "New York City",
            "types": ["museum", "tourist_attraction", "point_of_interest"],
            "rating": 4.7,
            "latitude": 40.7614,
            "longitude": -73.9776,
        }
    ],
    "kith": [
        {
            "place_id": "ch_kith_soho",
            "name": "Kith Soho",
            "address": "337 Lafayette St, New York, NY 10012",
            "city": "New York City",
            "types": ["clothing_store", "shopping_mall", "store"],
            "rating": 4.4,
            "latitude": 40.7262,
            "longitude": -73.9958,
        }
    ],
    "joe's pizza": [
        {
            "place_id": "ch_joes_pizza_greenwich",
            "name": "Joe's Pizza (Greenwich Village)",
            "address": "7 Carmine St, New York, NY 10014",
            "city": "New York City",
            "types": ["restaurant", "food", "point_of_interest"],
            "rating": 4.6,
            "latitude": 40.7306,
            "longitude": -74.0022,
        },
        {
            "place_id": "ch_joes_pizza_times_sq",
            "name": "Joe's Pizza (Times Square)",
            "address": "1435 Broadway, New York, NY 10018",
            "city": "New York City",
            "types": ["restaurant", "food", "point_of_interest"],
            "rating": 4.5,
            "latitude": 40.7571,
            "longitude": -73.9873,
        },
        {
            "place_id": "ch_joes_pizza_brooklyn",
            "name": "Joe's Pizza (Williamsburg)",
            "address": "216 Bedford Ave, Brooklyn, NY 11249",
            "city": "New York City",
            "types": ["restaurant", "food", "point_of_interest"],
            "rating": 4.4,
            "latitude": 40.7161,
            "longitude": -73.9598,
        }
    ]
}


def download_tiktok_media(url: str) -> Dict[str, Any]:
    """Downloads/extracts metadata for a TikTok video URL.

    Args:
        url: The TikTok video URL to download/analyze.

    Returns:
        A dictionary containing caption, comments, creator, and local file paths.
    """
    logger.info(f"Downloading TikTok metadata for: {url}")
    
    # Check if we should use mock data for testing
    if "tiktok.com" not in url:
        return {
            "title": "Mock Video Title",
            "description": "Checking out Soho Bagels in NYC! Best bagels ever.",
            "creator": "mock_creator",
            "comments": ["Where is Soho Bagels?", "It is at 120 Prince St!"],
            "audio_path": None,
            "video_path": None
        }

    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            comments = []
            if 'comments' in info and info['comments']:
                comments = [c.get('text', '') for c in info['comments'][:10]]
            
            return {
                "title": info.get("title", ""),
                "description": info.get("description", ""),
                "creator": info.get("uploader", ""),
                "comments": comments,
                "audio_path": None,
                "video_path": None
            }
    except Exception as e:
        logger.error(f"Failed to extract TikTok metadata via yt-dlp: {e}")
        # Return fallback mock based on URL keywords if extraction fails
        if "industrie" in url.lower():
            desc = "L'Industrie Pizzeria in Williamsburg has the best slices!"
        elif "joes" in url.lower():
            desc = "Getting a slice at Joe's Pizza today."
        else:
            desc = "Visiting Soho Bagels in NYC!"

        return {
            "title": "Fallback TikTok Title",
            "description": desc,
            "creator": "tiktok_traveler",
            "comments": ["Looks tasty!", "Is this in New York?"],
            "audio_path": None,
            "video_path": None
        }


def transcribe_audio(file_path: Optional[str]) -> str:
    """Simulates audio transcription if a file path is provided.

    Args:
        file_path: Path to the extracted audio file.

    Returns:
        Transcribed text from the audio.
    """
    if not file_path:
        return "No audio file provided to transcribe."
    logger.info(f"Transcribing audio file: {file_path}")
    return "This place is called Soho Bagels, located right on Prince Street in NYC."


def google_maps_search(query: str, city: str = "") -> List[Dict[str, Any]]:
    """Searches the Google Places database for matching locations.

    Args:
        query: The name of the place to search for.
        city: Optional city to constrain the search.

    Returns:
        A list of dicts with Place IDs, names, addresses, and types.
    """
    clean_query = query.lower().strip()
    # Normalize curly apostrophes and backticks to standard straight apostrophes
    clean_query = clean_query.replace("’", "'").replace("‘", "'").replace("`", "'")
    logger.info(f"Searching Google Maps for: '{clean_query}' in city '{city}'")

    # Match against mock database first
    matched_key = None
    for key in MOCK_PLACES.keys():
        if key in clean_query or clean_query in key:
            matched_key = key
            break
            
    if matched_key:
        return MOCK_PLACES[matched_key]
        
    # Live OpenStreetMap Nominatim Search fallback
    import urllib.request
    import urllib.parse
    import json
    
    try:
        search_query = query
        if city:
            search_query += f", {city}"
            
        logger.info(f"Querying OpenStreetMap Nominatim for: '{search_query}'")
        
        # Nominatim usage policy requires a descriptive User-Agent
        headers = {
            "User-Agent": "TikTokMapsSaver/1.0 (contact: support@tiktokmapssaver.local)"
        }
        params = {
            "q": search_query,
            "format": "json",
            "addressdetails": "1",
            "limit": "3"
        }
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            candidates = []
            for item in data:
                addr = item.get("address", {})
                
                # Reconstruct a clean address
                city_name = addr.get("city") or addr.get("town") or addr.get("suburb") or addr.get("village") or city or ""
                road = addr.get("road") or ""
                house_number = addr.get("house_number") or ""
                postcode = addr.get("postcode") or ""
                state = addr.get("state") or ""
                country = addr.get("country") or ""
                
                parts = [p for p in [house_number, road, city_name, state, postcode, country] if p]
                full_address = ", ".join(parts) if parts else item.get("display_name", "")
                
                name = addr.get("amenity") or addr.get("shop") or addr.get("tourism") or item.get("display_name", "").split(",")[0]
                
                types = [item.get("type", ""), item.get("class", ""), "point_of_interest"]
                # Map specific OSM types to standard ones for our categorizer
                if any(x in types for x in ("restaurant", "cafe", "fast_food", "pub", "bar", "bakery")):
                    types.append("restaurant")
                    types.append("food")
                elif any(x in types for x in ("clothes", "mall", "supermarket", "boutique", "shop", "convenience")):
                    types.append("store")
                elif any(x in types for x in ("museum", "park", "monument", "attraction", "castle")):
                    types.append("tourist_attraction")
                    
                candidates.append({
                    "place_id": f"osm_{item.get('place_id')}",
                    "name": name,
                    "address": full_address,
                    "city": city_name,
                    "types": types,
                    "rating": 4.5,
                    "latitude": float(item.get("lat")) if item.get("lat") else 0.0,
                    "longitude": float(item.get("lon")) if item.get("lon") else 0.0,
                })
            
            if candidates:
                logger.info(f"OSM Search returned {len(candidates)} candidates.")
                return candidates
    except Exception as e:
        logger.error(f"Live OSM Search failed fallback: {e}")
        
    # Return empty list if no mock match is found and live search fails
    return []


def google_maps_save_location(place_id: str, category: str) -> bool:
    """Saves a Google Maps Place ID to the specified category list.

    Args:
        place_id: The Google Maps Place ID.
        category: The category (Food, Shopping, Sightseeing).

    Returns:
        True if successfully saved, False otherwise.
    """
    logger.info(f"Saving Place ID {place_id} to category list 'TikTok {category}'")
    # Simulate writing to Google Maps list
    return True


def google_maps_update_list(place_id: str, old_category: str, new_category: str) -> bool:
    """Moves a saved Place ID from an old list to a new list (Human-in-the-loop override).

    Args:
        place_id: The Google Maps Place ID.
        old_category: The previous category.
        new_category: The new category.

    Returns:
        True if successfully moved, False otherwise.
    """
    logger.info(f"Moving Place ID {place_id} from 'TikTok {old_category}' to 'TikTok {new_category}'")
    return True
