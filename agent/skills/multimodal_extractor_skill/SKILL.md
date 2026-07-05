---
name: multimodal_extractor_skill
description: "Extract location names, business names, addresses, and geographic clues from rich video media using Speech-to-Text and OCR on video frames."
---

# Multimodal Extractor Skill

This skill provides guidelines and system prompts to extract candidate locations from social media videos when they are not explicitly written in the caption or text description.

## Process Guidelines

1. **Audio Transcription Analysis**:
   - Extract the audio track from the video (preferably in MP3/AAC format).
   - Use Gemini's multimodal audio ingestion to transcribe speech.
   - Look for auditory location indicators, street names, restaurant name drops, and landmarks (e.g., "we're checking out this place in Soho...", "the burger at Joe's was...").

2. **Video OCR / Visual Inspection**:
   - Extract video frames at key intervals (e.g., every 1–2 seconds).
   - Use Gemini Vision to detect:
     - On-screen text (e.g., subtitles, overlays, watermarks).
     - Storefront signs, menus, logos, napkins with branding, and street signs.
     - Visual landmarks (e.g., Eiffel Tower, Golden Gate Bridge) to narrow down the city.

3. **Extraction Prompting**:
   - Prompt the extraction model to return a structured JSON response matching the following schema:
     ```json
     {
       "candidate_locations": [
         {
           "name": "Joe's Pizza",
           "confidence": 0.95,
           "clues": ["spoken verbally in audio", "visual sign visible at 0:12"]
         }
       ],
       "inferred_city": "New York City"
     }
     ```
