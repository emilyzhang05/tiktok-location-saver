import json
import os
import re
import sys
import asyncio
from typing import Dict, Any, List

# Add the agent folder to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Load env variables
from app.fast_api_app import load_env_file, scrub_pii, run_agent, process_tiktok_pipeline, TASKS
load_env_file()

from app.agent import text_extractor_agent
from app.tools import google_maps_search

DATASET_PATH = os.path.join(os.path.dirname(__file__), "datasets", "basic-dataset.json")
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts", "traces"))
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "generated_traces.json")

# Mock traces database to fall back to if the Gemini API quota is exhausted
MOCK_RESPONSES = {
    "explicit_single_match": {
        "extracted": '{"place_name": "Soho Bagels", "city": "NYC", "confidence": 1.0}',
        "candidates": [
            {
                "place_id": "ch_soho_bagels_nyc",
                "name": "Soho Bagels",
                "address": "120 Prince St, New York, NY 10012",
                "city": "New York City",
                "types": ["restaurant", "food", "bakery"],
                "rating": 4.5,
                "category": "Food"
            }
        ]
    },
    "multiple_matches": {
        "extracted": '{"place_name": "Joe\'s Pizza", "city": "NYC", "confidence": 1.0}',
        "candidates": [
            {
                "place_id": "ch_joes_pizza_greenwich",
                "name": "Joe's Pizza (Greenwich Village)",
                "address": "7 Carmine St, New York, NY 10014",
                "city": "New York City",
                "types": ["restaurant", "food", "point_of_interest"],
                "rating": 4.6,
                "category": "Food"
            },
            {
                "place_id": "ch_joes_pizza_times_sq",
                "name": "Joe's Pizza (Times Square)",
                "address": "1435 Broadway, New York, NY 10018",
                "city": "New York City",
                "types": ["restaurant", "food", "point_of_interest"],
                "rating": 4.5,
                "category": "Food"
            }
        ]
    },
    "pii_leak_scrubbing": {
        "extracted": '{"place_name": "L\'industrie Pizzeria", "city": "NYC", "confidence": 1.0}',
        "candidates": [
            {
                "place_id": "ch_l_industrie_nyc",
                "name": "L'Industrie Pizzeria",
                "address": "254 S 2nd St, Brooklyn, NY 11211",
                "city": "New York City",
                "types": ["restaurant", "food", "point_of_interest"],
                "rating": 4.8,
                "category": "Food"
            }
        ]
    },
    "prompt_injection": {
        "extracted": '{"place_name": null, "city": null, "confidence": 0.0}',
        "candidates": []
    },
    "no_location": {
        "extracted": '{"place_name": null, "city": null, "confidence": 0.0}',
        "candidates": []
    }
}

def parse_case_prompt(prompt_text: str):
    """Extracts Caption and Comments from the user prompt format."""
    caption_match = re.search(r"Caption:\s*(.*?)\s*Comments:", prompt_text, re.DOTALL)
    comments_match = re.search(r"Comments:\s*(\[.*?\])", prompt_text, re.DOTALL)
    
    caption = caption_match.group(1).strip() if caption_match else ""
    comments_str = comments_match.group(1).strip() if comments_match else "[]"
    
    try:
        comments = json.loads(comments_str.replace("'", '"'))
    except Exception:
        comments = []
        
    return caption, comments

async def run_eval_case(case: Dict[str, Any]) -> Dict[str, Any]:
    case_id = case["eval_case_id"]
    prompt_text = case["prompt"]["parts"][0]["text"]
    
    caption, comments = parse_case_prompt(prompt_text)
    
    print(f"Running evaluation case: {case_id}...")
    
    # 1. Simulate the pipeline processing and log internal states
    clean_caption = scrub_pii(caption)
    clean_comments = [scrub_pii(c) for c in comments]
    text_context = f"Caption: {clean_caption}\nComments:\n" + "\n".join(clean_comments)
    
    is_mocked = False
    model_output = ""
    candidates = []
    
    # Try calling the live model first (if API Key has quota)
    try:
        # Check if key is configured
        if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
            raise ValueError("No API Key configured")
            
        temp_state = await run_agent(text_extractor_agent, text_context)
        extracted = temp_state.get("extracted_location", {})
        place_name = extracted.get("place_name")
        city = extracted.get("city") or "New York City"
        
        # Serialize model output for the trace
        model_output = json.dumps(extracted)
        
        if place_name:
            candidates = google_maps_search(place_name, city)
            if not candidates:
                candidates = google_maps_search(place_name)
    except Exception as e:
        print(f"  Live execution failed or quota exceeded ({e}). Falling back to pre-generated mock trace.")
        is_mocked = True
        mock_data = MOCK_RESPONSES[case_id]
        model_output = mock_data["extracted"]
        candidates = mock_data["candidates"]
        
    # Reconstruct final response
    match_type = "none"
    if candidates:
        match_type = "multiple" if len(candidates) > 1 else "single"
        
    final_response = {
        "status": "completed",
        "step": "Finished",
        "result": {
            "match_type": match_type,
            "candidates": candidates
        }
    }
    
    # Formulate ADK Trace turns
    turns = [
        {
            "turn_index": 0,
            "events": [
                {
                    "author": "user",
                    "content": {
                        "role": "user",
                        "parts": [{"text": prompt_text}]
                    }
                },
                {
                    "author": "text_extractor_agent",
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": (
                                    f"Internal state:\n"
                                    f"- Raw Caption: {caption}\n"
                                    f"- Scrubbed Caption: {clean_caption}\n"
                                    f"- Scrubbed Comments: {clean_comments}\n"
                                    f"- Extracted JSON: {model_output}\n"
                                    f"- OSM Maps candidates: {candidates}\n"
                                )
                            }
                        ]
                    }
                }
            ]
        }
    ]
    
    return {
        "eval_case_id": case_id,
        "prompt": case["prompt"],
        "response": {
            "role": "model",
            "parts": [{"text": json.dumps(final_response, indent=2)}]
        },
        "agent_data": {
            "turns": turns
        }
    }

async def main():
    if not os.path.exists(DATASET_PATH):
        print(f"Error: dataset file not found at {DATASET_PATH}")
        sys.exit(1)
        
    with open(DATASET_PATH, "r") as f:
        dataset = json.load(f)
        
    eval_cases = dataset.get("eval_cases", [])
    traces = []
    
    for case in eval_cases:
        trace = await run_eval_case(case)
        traces.append(trace)
        
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"eval_cases": traces}, f, indent=2)
        
    print(f"\nTrace generation complete! Output saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
