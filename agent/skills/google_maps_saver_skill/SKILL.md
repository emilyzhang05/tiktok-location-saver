---
name: google_maps_saver_skill
description: "Resolve candidate locations with Google Places database, handle category determinations, and manage OAuth authenticated saves/updates to user lists."
---

# Google Maps Saver Skill

This skill handles interaction with Google Maps and Google Places API resources, specifically search validation and category routing.

## Process Guidelines

1. **Place Search & Verification**:
   - Query the Google Places API (or Google Maps MCP server tool) with the candidate name and inferred city.
   - Retrieve candidate matching places including Place ID, address, coordinates, and types (e.g. `['restaurant', 'food', 'point_of_interest']`).

2. **Categorization Rules**:
   - Classify each place into one of three major buckets:
     - **Food**: if types contains `restaurant`, `food`, `cafe`, `bar`, `bakery`, `meal_takeaway`, etc.
     - **Shopping**: if types contains `clothing_store`, `shopping_mall`, `store`, `shoe_store`, `supermarket`, etc.
     - **Sightseeing**: if types contains `tourist_attraction`, `museum`, `park`, `amusement_park`, `place_of_worship`, etc.
   - If ambiguous, map to the closest logical category based on the description, or default to a general category.

3. **Google Maps List Operations**:
   - Create category lists: "TikTok Food", "TikTok Shopping", "TikTok Sightseeing" if they do not exist.
   - Add verified Place ID to the designated list.
   - Support category update/move operations (used for the 10-second human correction window).
