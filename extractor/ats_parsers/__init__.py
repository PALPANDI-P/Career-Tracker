"""
Career Tracker — ATS Parser Registry

Maps ATS type strings to their parser functions.
Adding a new ATS parser is as simple as writing the parser module
and registering it here.
"""

from __future__ import annotations

from typing import Callable

from schema.job import ATSType, Job

from extractor.ats_parsers.greenhouse import parse_greenhouse_jobs
from extractor.ats_parsers.lever import parse_lever_jobs
from extractor.ats_parsers.smartrecruiters import parse_smartrecruiters_jobs

# Type alias for parser functions
ParserFunc = Callable[[str, str], list[Job]]

# Registry: ATS type → parser function
_PARSERS: dict[ATSType, ParserFunc] = {
    ATSType.GREENHOUSE: parse_greenhouse_jobs,
    ATSType.LEVER: parse_lever_jobs,
    ATSType.SMARTRECRUITERS: parse_smartrecruiters_jobs,
}


def get_parser(ats_type: ATSType) -> ParserFunc | None:
    """
    Get the parser function for a given ATS type.

    Returns None if no parser is registered for the type.
    """
    return _PARSERS.get(ats_type)


def has_parser(ats_type: ATSType) -> bool:
    """Check if a parser exists for the given ATS type."""
    return ats_type in _PARSERS


def supported_ats_types() -> list[ATSType]:
    """List all ATS types with registered parsers."""
    return list(_PARSERS.keys())
