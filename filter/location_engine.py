"""
Career Tracker — Location Engine

Implements Section 11 of MASTER DEVELOPMENT PROMPT.

Normalizes city/state/country strings into canonical representations
and calculates configurable preference weights for matching.

Examples:
  "Bangalore"       -> city=Bengaluru, state=Karnataka, country=India
  "Bengaluru, KA"   -> city=Bengaluru, state=Karnataka, country=India
  "Remote"          -> remote_type=REMOTE_INDIA
  "Chennai, TN"     -> city=Chennai, state=Tamil Nadu, country=India
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Canonical City Aliases ────────────────────────────────────────────
# Maps all known spelling variants -> canonical name
CITY_ALIASES: dict[str, str] = {
    # Bangalore / Bengaluru
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "bengaluru, karnataka": "Bengaluru",
    "blr": "Bengaluru",
    "blore": "Bengaluru",
    # Chennai
    "chennai": "Chennai",
    "madras": "Chennai",
    # Coimbatore
    "coimbatore": "Coimbatore",
    "coimbatore, tamil nadu": "Coimbatore",
    "cbee": "Coimbatore",
    # Madurai
    "madurai": "Madurai",
    # Hyderabad
    "hyderabad": "Hyderabad",
    "hyd": "Hyderabad",
    "secunderabad": "Hyderabad",
    # Mumbai
    "mumbai": "Mumbai",
    "bombay": "Mumbai",
    "navi mumbai": "Mumbai",
    # Pune
    "pune": "Pune",
    # Delhi / NCR
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "ncr": "Delhi",
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "noida": "Noida",
    # Kochi / Trivandrum / Kerala
    "kochi": "Kochi",
    "cochin": "Kochi",
    "ernakulam": "Kochi",
    "trivandrum": "Thiruvananthapuram",
    "thiruvananthapuram": "Thiruvananthapuram",
    "calicut": "Kozhikode",
    "kozhikode": "Kozhikode",
    # Mysore
    "mysore": "Mysuru",
    "mysuru": "Mysuru",
    # Other Tamil Nadu cities
    "trichy": "Tiruchirappalli",
    "tiruchirappalli": "Tiruchirappalli",
    "salem": "Salem",
    "vellore": "Vellore",
    "sivaganga": "Sivaganga",
    # Other south Indian cities
    "mangalore": "Mangaluru",
    "mangaluru": "Mangaluru",
    "hubli": "Hubballi",
    "hubballi": "Hubballi",
}

# ─── City -> State Mapping ─────────────────────────────────────────────
CITY_STATE_MAP: dict[str, str] = {
    "Bengaluru": "Karnataka",
    "Mysuru": "Karnataka",
    "Mangaluru": "Karnataka",
    "Hubballi": "Karnataka",
    "Chennai": "Tamil Nadu",
    "Coimbatore": "Tamil Nadu",
    "Madurai": "Tamil Nadu",
    "Tiruchirappalli": "Tamil Nadu",
    "Salem": "Tamil Nadu",
    "Vellore": "Tamil Nadu",
    "Sivaganga": "Tamil Nadu",
    "Kochi": "Kerala",
    "Thiruvananthapuram": "Kerala",
    "Kozhikode": "Kerala",
    "Hyderabad": "Telangana",
    "Mumbai": "Maharashtra",
    "Pune": "Maharashtra",
    "Delhi": "Delhi",
    "Gurugram": "Haryana",
    "Noida": "Uttar Pradesh",
}

# ─── State Aliases ─────────────────────────────────────────────────────
STATE_ALIASES: dict[str, str] = {
    "karnataka": "Karnataka",
    "tn": "Tamil Nadu",
    "tamil nadu": "Tamil Nadu",
    "tamilnadu": "Tamil Nadu",
    "kerala": "Kerala",
    "telangana": "Telangana",
    "andhra pradesh": "Andhra Pradesh",
    "ap": "Andhra Pradesh",
    "maharashtra": "Maharashtra",
    "mh": "Maharashtra",
    "ka": "Karnataka",
    "kl": "Kerala",
}

# ─── Remote keywords ───────────────────────────────────────────────────
REMOTE_PATTERNS = {
    "remote": "remote",
    "work from home": "remote",
    "wfh": "remote",
    "fully remote": "remote",
    "remote india": "remote_india",
    "remote - india": "remote_india",
    "remote (india)": "remote_india",
    "hybrid": "hybrid",
    "hybrid remote": "hybrid",
    "remote / hybrid": "hybrid",
}


@dataclass
class CanonicalLocation:
    """Result of location normalization."""

    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    remote_type: Optional[str] = None  # "remote", "remote_india", "hybrid", "onsite"
    canonical_string: str = ""
    is_preferred: bool = False
    preference_weight: float = 0.5


def normalize_location(raw_location: Optional[str]) -> CanonicalLocation:
    """
    Normalize a raw location string to canonical city/state/country.

    Args:
        raw_location: Raw location string from ATS (e.g. "Bangalore, KA, India")

    Returns:
        CanonicalLocation with normalized fields.
    """
    if not raw_location:
        return CanonicalLocation(canonical_string="", remote_type="unknown")

    loc = raw_location.strip()
    loc_lower = loc.lower()

    # Check remote/hybrid patterns first
    for pattern, remote_type in REMOTE_PATTERNS.items():
        if pattern in loc_lower:
            return CanonicalLocation(
                remote_type=remote_type,
                canonical_string=loc,
            )

    # Try to find a canonical city
    canonical_city = None
    for alias, canonical in CITY_ALIASES.items():
        if alias in loc_lower:
            canonical_city = canonical
            break

    # Determine state
    canonical_state = None
    if canonical_city:
        canonical_state = CITY_STATE_MAP.get(canonical_city)
    else:
        for alias, state in STATE_ALIASES.items():
            if alias in loc_lower:
                canonical_state = state
                break

    canonical_str = ", ".join(filter(None, [canonical_city, canonical_state, "India"]))

    return CanonicalLocation(
        city=canonical_city,
        state=canonical_state,
        country="India",
        remote_type="onsite" if canonical_city else None,
        canonical_string=canonical_str,
    )


def calculate_location_weight(
    location: CanonicalLocation,
    priority_cities: Optional[list[str]] = None,
    preferred_states: Optional[list[str]] = None,
    location_weights: Optional[dict[str, float]] = None,
) -> float:
    """
    Calculate a preference weight for a canonical location.

    Uses weights from Section 11 of MASTER DEVELOPMENT PROMPT:
      preferred_city: 1.0
      preferred_state: 0.9
      remote: 0.9
      india_other: 0.5
      outside_india: 0.0

    Args:
        location: Canonical location to evaluate.
        priority_cities: List of candidate's priority cities.
        preferred_states: List of candidate's preferred states.
        location_weights: Custom weight overrides.

    Returns:
        Float weight from 0.0 (no preference) to 1.0 (perfect match).
    """
    if priority_cities is None:
        priority_cities = ["Chennai", "Coimbatore", "Madurai", "Bengaluru", "Mysuru", "Kochi", "Thiruvananthapuram"]
    if preferred_states is None:
        preferred_states = ["Tamil Nadu", "Karnataka", "Kerala"]

    weights = {
        "preferred_city": 1.0,
        "preferred_state": 0.9,
        "remote": 0.9,
        "india_other": 0.5,
        "outside_india": 0.0,
    }
    if location_weights:
        weights.update(location_weights)

    # Remote / hybrid
    if location.remote_type in ("remote", "remote_india"):
        return weights["remote"]
    if location.remote_type == "hybrid":
        return weights["remote"] * 0.95  # Slightly lower than fully remote

    # Priority city match
    if location.city:
        # Normalize for comparison
        city_normalized = location.city.lower().replace(" ", "")
        for pc in priority_cities:
            if pc.lower().replace(" ", "") == city_normalized:
                return weights["preferred_city"]

    # Preferred state match
    if location.state:
        state_normalized = location.state.lower()
        for ps in preferred_states:
            if ps.lower() == state_normalized:
                return weights["preferred_state"]

    # India-wide role (city/state not preferred but still in India)
    if location.country == "India" or location.city:
        return weights["india_other"]

    return weights["outside_india"]
