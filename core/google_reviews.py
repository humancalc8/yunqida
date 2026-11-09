
"""
Google Business Profile rating and reviews for Yunqida Energy Kenya.

Uses Google Places API (New), with an optional manual fallback.
Results are cached for 6 hours.
"""

import logging

import requests

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = "yunqida_google_reviews_v2"
CACHE_SECONDS = 6 * 60 * 60


def _links(place_id):
    if not place_id:
        return {}

    return {
        "google_reviews_url": (
            f"https://search.google.com/local/reviews?placeid={place_id}"
        ),
        "google_write_url": (
            f"https://search.google.com/local/writereview?placeid={place_id}"
        ),
    }


def _from_manual():
    """Load genuine manually supplied Google reviews."""

    data = getattr(settings, "GOOGLE_REVIEWS_MANUAL", None)

    if not isinstance(data, dict):
        return {}

    reviews = data.get("reviews", [])

    if not isinstance(reviews, list):
        reviews = []

    if not any([
        data.get("rating"),
        data.get("count"),
        reviews,
    ]):
        return {}

    return {
        "google_rating": data.get("rating"),
        "google_review_count": data.get("count"),
        "google_reviews": reviews,
    }


def _from_api(api_key, place_id):
    """Fetch rating and reviews from Google Places API (New)."""

    url = f"https://places.googleapis.com/v1/places/{place_id}"

    response = requests.get(
        url,
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "rating,userRatingCount,reviews"
            ),
        },
        timeout=10,
    )

    response.raise_for_status()

    place = response.json()

    reviews = []

    for review in place.get("reviews", []):
        review_text = (
            review.get("text")
            or review.get("originalText")
            or {}
        )

        if isinstance(review_text, dict):
            review_text = review_text.get("text", "")

        review_text = review_text.strip()

        if not review_text:
            continue

        author = review.get("authorAttribution", {})

        reviews.append({
            "name": author.get("displayName", "Google user"),
            "photo": author.get("photoUri", ""),
            "rating": review.get("rating", 5),
            "text": review_text,
            "time": review.get(
                "relativePublishTimeDescription", ""
            ),
        })

    return {
        "google_rating": place.get("rating"),
        "google_review_count": place.get("userRatingCount"),
        "google_reviews": reviews,
    }


def get_google_reviews():
    """
    Returns Google review data for the homepage.

    Falls back to manual reviews if the API is unavailable.
    Always returns the Google review links when a Place ID exists.
    """

    place_id = getattr(settings, "GOOGLE_PLACE_ID", "")
    api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "")

    cache_key = f"{CACHE_KEY}_{place_id or 'no_place'}"

    data = cache.get(cache_key)

    if data is None:
        data = {}

        # First attempt: Google Places API.
        if api_key and place_id:
            try:
                data = _from_api(api_key, place_id)

            except requests.RequestException as exc:
                logger.warning(
                    "Google Places API request failed: %s",
                    exc,
                )

            except (ValueError, TypeError, AttributeError) as exc:
                logger.warning(
                    "Google Places API returned invalid data: %s",
                    exc,
                )

        # Second attempt: manual fallback.
        if not any([
            data.get("google_rating"),
            data.get("google_review_count"),
            data.get("google_reviews"),
]):

        # Cache even empty results to avoid repeated failed requests.
            cache.set(cache_key, data, CACHE_SECONDS)

    return {
        **data,
        **_links(place_id),
    }
