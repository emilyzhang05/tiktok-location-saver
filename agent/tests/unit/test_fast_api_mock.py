import unittest
from unittest.mock import patch, MagicMock
import asyncio
import os
import json

from app.fast_api_app import process_tiktok_pipeline, TASKS, PERSISTENT_FILE
from app.tools import google_maps_search

class TestFastApiMock(unittest.TestCase):
    def setUp(self):
        # Ensure a clean slate for TASKS
        TASKS.clear()
        
        # Backup existing saved places file if any
        self.db_backup = None
        if os.path.exists(PERSISTENT_FILE):
            try:
                with open(PERSISTENT_FILE, "r") as f:
                    self.db_backup = f.read()
            except Exception:
                pass
            os.remove(PERSISTENT_FILE)

    def tearDown(self):
        # Restore backup database if any
        if os.path.exists(PERSISTENT_FILE):
            os.remove(PERSISTENT_FILE)
        if self.db_backup is not None:
            try:
                with open(PERSISTENT_FILE, "w") as f:
                    f.write(self.db_backup)
            except Exception:
                pass

    @patch("app.fast_api_app.run_agent")
    def test_pipeline_mock_places(self, mock_run_agent):
        """Test the extraction pipeline with a known mock place (L'industrie Pizzeria)."""
        # Configure mocked run_agent output for the text extractor
        mock_run_agent.return_value = {
            "extracted_location": {
                "place_name": "L’industrie Pizzeria",  # curly apostrophe
                "city": "Manhattan",
                "confidence": 1.0
            }
        }
        
        task_id = "test_task_1"
        TASKS[task_id] = {"status": "processing", "step": "", "result": None}
        
        # Run the pipeline synchronously for test purposes
        asyncio.run(
            process_tiktok_pipeline(
                task_id=task_id,
                url="https://tiktok.com/video/123",
                caption="Best pizza at L’industrie Pizzeria",
                comments=[]
            )
        )
        
        # Verify the pipeline output matches the expected mock database entry
        self.assertEqual(TASKS[task_id]["status"], "completed")
        self.assertEqual(TASKS[task_id]["step"], "Finished")
        
        result = TASKS[task_id]["result"]
        self.assertEqual(result["match_type"], "single")
        
        candidates = result["candidates"]
        self.assertEqual(len(candidates), 1)
        
        candidate = candidates[0]
        self.assertEqual(candidate["place_id"], "ch_l_industrie_nyc")
        self.assertEqual(candidate["name"], "L'Industrie Pizzeria")
        self.assertEqual(candidate["category"], "Food")

    @patch("urllib.request.urlopen")
    @patch("app.fast_api_app.run_agent")
    def test_pipeline_osm_fallback(self, mock_run_agent, mock_urlopen):
        """Test the pipeline fallbacks to OpenStreetMap search if a place is not in the mock DB."""
        # Configure mocked run_agent output for a place not in the mock DB
        mock_run_agent.return_value = {
            "extracted_location": {
                "place_name": "Katz's Deli",
                "city": "New York City",
                "confidence": 1.0
            }
        }
        
        # Mock OpenStreetMap HTTP response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([
            {
                "place_id": 99999,
                "display_name": "Katz's Delicatessen, 205, East Houston Street, Lower East Side, Manhattan, New York County, New York, 10002, United States",
                "type": "restaurant",
                "class": "amenity",
                "address": {
                    "amenity": "Katz's Delicatessen",
                    "road": "East Houston Street",
                    "city": "New York",
                    "postcode": "10002",
                    "country": "United States"
                }
            }
        ]).encode("utf-8")
        
        # Enter context manager mock
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        task_id = "test_task_2"
        TASKS[task_id] = {"status": "processing", "step": "", "result": None}
        
        # Run pipeline
        asyncio.run(
            process_tiktok_pipeline(
                task_id=task_id,
                url="https://tiktok.com/video/456",
                caption="Katz's Deli is great!",
                comments=[]
            )
        )
        
        # Verify the OSM fallback returned and categorized the location correctly
        self.assertEqual(TASKS[task_id]["status"], "completed")
        
        result = TASKS[task_id]["result"]
        self.assertEqual(result["match_type"], "single")
        
        candidates = result["candidates"]
        self.assertEqual(len(candidates), 1)
        
        candidate = candidates[0]
        self.assertEqual(candidate["place_id"], "osm_99999")
        self.assertEqual(candidate["name"], "Katz's Delicatessen")
        self.assertEqual(candidate["category"], "Food")
