"""
Career Tracker — Company Registry Utility

A Python utility for efficiently managing company entries in the YAML config
files under the `companies/` directory.  Eliminates the need to manually edit
YAML files every time you want to add, remove, or toggle companies.

Usage examples
--------------
    # Add a single company to a specific file
    from companies.company_registry import add_company
    add_company(
        yaml_file="data_jobs_freshers.yaml",
        company={
            "name": "My New Company",
            "careers_url": "https://example.com/careers",
            "ats_type": "greenhouse",
            "fetch_strategy": "static",
            "location_filter": "India",
            "target_levels": ["fresher", "entry"],
            "rate_limit_seconds": 2.0,
            "enabled": True,
            "tags": ["data-role", "global"],
        }
    )

    # Bulk-add many companies at once
    from companies.company_registry import add_companies_bulk
    add_companies_bulk("tamil_nadu.yaml", companies=[{...}, {...}])

    # List all companies across every YAML file
    from companies.company_registry import list_all_companies
    for yaml_file, names in list_all_companies().items():
        print(yaml_file, "->", names)

    # Enable / disable a company by name
    from companies.company_registry import toggle_company
    toggle_company("Snowflake", enabled=False)

    # Validate all YAML files against the CompanyConfig schema
    from companies.company_registry import validate_all_companies
    errors = validate_all_companies()
    for file, errs in errors.items():
        if errs:
            print(file, errs)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from schema.job import CompanyConfig

logger = logging.getLogger(__name__)

# Path to the companies/ directory (one level up from this file)
COMPANIES_DIR: Path = Path(__file__).resolve().parent


# ── Internal helpers ──────────────────────────────────────────────────────────


def _yaml_path(yaml_file: str) -> Path:
    """Resolve a YAML filename to its full path inside companies/."""
    p = COMPANIES_DIR / yaml_file
    if not p.suffix:
        p = p.with_suffix(".yaml")
    return p


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its content as a dict."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write data to a YAML file, preserving order."""
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)


def _all_yaml_files() -> list[Path]:
    """Return all .yaml files in the companies/ directory."""
    return sorted(COMPANIES_DIR.glob("*.yaml"))


# ── Public API ────────────────────────────────────────────────────────────────


def add_company(yaml_file: str, company: dict[str, Any]) -> bool:
    """
    Append a single company entry to a YAML file.

    If the company name already exists in the file, it will NOT be added
    again (idempotent).  Creates the YAML file if it does not exist.

    Args:
        yaml_file: Filename (e.g. "data_jobs_freshers.yaml") or full path.
        company:   Dictionary matching CompanyConfig fields. Required keys:
                   name, careers_url, ats_type, fetch_strategy.

    Returns:
        True if company was added, False if it already existed.

    Raises:
        ValueError: If the company dict is missing required fields.
    """
    name = company.get("name", "").strip()
    if not name:
        raise ValueError("Company dict must include a non-empty 'name'.")
    if not company.get("careers_url"):
        raise ValueError(f"Company '{name}' must include 'careers_url'.")

    path = _yaml_path(yaml_file)
    data = _load_yaml(path)

    # Support both 'companies' and 'aggregators' top-level keys
    top_key = "aggregators" if "aggregators" in data else "companies"
    entries: list[dict[str, Any]] = data.get(top_key, [])

    # Idempotency check
    existing_names = {e.get("name", "").strip().lower() for e in entries}
    if name.lower() in existing_names:
        logger.info("Company '%s' already exists in %s — skipping.", name, yaml_file)
        return False

    entries.append(company)
    data[top_key] = entries
    _save_yaml(path, data)
    logger.info("Added company '%s' to %s.", name, yaml_file)
    return True


def add_companies_bulk(yaml_file: str, companies: list[dict[str, Any]]) -> dict[str, bool]:
    """
    Add multiple companies to a YAML file in a single call.

    Args:
        yaml_file: Target YAML filename.
        companies: List of company dicts.

    Returns:
        Dict mapping company name -> True (added) / False (already existed).
    """
    results: dict[str, bool] = {}
    for company in companies:
        name = company.get("name", "unknown")
        try:
            results[name] = add_company(yaml_file, company)
        except ValueError as exc:
            logger.error("Skipping company '%s': %s", name, exc)
            results[name] = False
    logger.info(
        "Bulk add to %s: %d added, %d skipped.",
        yaml_file,
        sum(v for v in results.values()),
        sum(not v for v in results.values()),
    )
    return results


def list_all_companies() -> dict[str, list[str]]:
    """
    Return all company names grouped by their YAML file.

    Returns:
        Dict mapping yaml_filename -> list of company names (sorted).

    Example:
        {
            "data_jobs_freshers.yaml": ["Databricks India", "Razorpay", ...],
            "tamil_nadu.yaml": ["TCS", "Infosys", ...],
        }
    """
    result: dict[str, list[str]] = {}
    for yaml_path in _all_yaml_files():
        data = _load_yaml(yaml_path)
        top_key = "aggregators" if "aggregators" in data else "companies"
        entries = data.get(top_key, [])
        names = sorted(e.get("name", "?") for e in entries if isinstance(e, dict))
        result[yaml_path.name] = names
    return result


def toggle_company(name: str, enabled: bool, yaml_file: str | None = None) -> bool:
    """
    Enable or disable a company across all YAML files (or a specific one).

    Args:
        name:      Exact company name (case-insensitive match).
        enabled:   True to enable, False to disable.
        yaml_file: Optional — restrict search to a single YAML file.

    Returns:
        True if the company was found and updated, False otherwise.
    """
    files = [_yaml_path(yaml_file)] if yaml_file else _all_yaml_files()
    name_lower = name.strip().lower()
    updated = False

    for path in files:
        data = _load_yaml(path)
        top_key = "aggregators" if "aggregators" in data else "companies"
        entries: list[dict[str, Any]] = data.get(top_key, [])
        changed = False

        for entry in entries:
            if entry.get("name", "").strip().lower() == name_lower:
                entry["enabled"] = enabled
                changed = True
                updated = True
                logger.info(
                    "Company '%s' in %s set to enabled=%s.",
                    name,
                    path.name,
                    enabled,
                )

        if changed:
            data[top_key] = entries
            _save_yaml(path, data)

    if not updated:
        logger.warning("Company '%s' not found in any YAML file.", name)
    return updated


def remove_company(name: str, yaml_file: str | None = None) -> bool:
    """
    Remove a company from all YAML files (or a specific one).

    Args:
        name:      Exact company name (case-insensitive).
        yaml_file: Optional — restrict removal to one YAML file.

    Returns:
        True if the company was found and removed, False if not found.
    """
    files = [_yaml_path(yaml_file)] if yaml_file else _all_yaml_files()
    name_lower = name.strip().lower()
    removed = False

    for path in files:
        data = _load_yaml(path)
        top_key = "aggregators" if "aggregators" in data else "companies"
        entries: list[dict[str, Any]] = data.get(top_key, [])
        before = len(entries)
        entries = [e for e in entries if e.get("name", "").strip().lower() != name_lower]

        if len(entries) < before:
            data[top_key] = entries
            _save_yaml(path, data)
            logger.info("Removed company '%s' from %s.", name, path.name)
            removed = True

    if not removed:
        logger.warning("Company '%s' not found in any YAML file.", name)
    return removed


def validate_all_companies() -> dict[str, list[str]]:
    """
    Validate every company entry in all YAML files against CompanyConfig.

    Returns:
        Dict mapping yaml_filename -> list of validation error strings.
        Files with no errors map to an empty list.

    Example:
        {
            "data_jobs_freshers.yaml": [],
            "tier1.yaml": ["Airbnb: field 'careers_url' invalid ..."],
        }
    """
    errors: dict[str, list[str]] = {}

    for yaml_path in _all_yaml_files():
        file_errors: list[str] = []
        data = _load_yaml(yaml_path)

        # Aggregator files (naukri_aggregator.yaml) use a different schema
        # (base_url + search_urls).  Skip CompanyConfig validation for them.
        if "aggregators" in data:
            errors[yaml_path.name] = []  # aggregators have their own schema
            continue

        entries = data.get("companies", [])

        for entry in entries:
            if not isinstance(entry, dict):
                file_errors.append(f"Non-dict entry found: {entry!r}")
                continue
            try:
                # Patch missing optional fields for validation
                entry.setdefault("ats_type", "unknown")
                entry.setdefault("fetch_strategy", "static")
                CompanyConfig(**entry)
            except ValidationError as exc:
                name = entry.get("name", "?")
                for error in exc.errors():
                    field = ".".join(str(loc) for loc in error["loc"])
                    msg = error["msg"]
                    file_errors.append(f"{name}: [{field}] {msg}")

        errors[yaml_path.name] = file_errors

    total_errors = sum(len(v) for v in errors.values())
    if total_errors == 0:
        logger.info("validate_all_companies: All YAML files are valid.")
    else:
        logger.warning("validate_all_companies: %d validation error(s) found.", total_errors)

    return errors


def search_company(query: str) -> dict[str, list[str]]:
    """
    Search for companies by name (case-insensitive substring match).

    Args:
        query: Substring to search for in company names.

    Returns:
        Dict mapping yaml_filename -> list of matching company names.
    """
    query_lower = query.strip().lower()
    results: dict[str, list[str]] = {}

    for yaml_path in _all_yaml_files():
        data = _load_yaml(yaml_path)
        top_key = "aggregators" if "aggregators" in data else "companies"
        entries = data.get(top_key, [])
        matches = [
            e.get("name", "?")
            for e in entries
            if isinstance(e, dict) and query_lower in e.get("name", "").lower()
        ]
        if matches:
            results[yaml_path.name] = sorted(matches)

    return results


def get_companies_by_tag(tag: str) -> dict[str, list[str]]:
    """
    Return all companies that carry a specific tag.

    Args:
        tag: Tag to filter by (e.g. 'data-role', 'fresher-focused', 'mnc').

    Returns:
        Dict mapping yaml_filename -> list of company names with that tag.
    """
    tag_lower = tag.strip().lower()
    results: dict[str, list[str]] = {}

    for yaml_path in _all_yaml_files():
        data = _load_yaml(yaml_path)
        top_key = "aggregators" if "aggregators" in data else "companies"
        entries = data.get(top_key, [])
        matches = [
            e.get("name", "?")
            for e in entries
            if isinstance(e, dict) and tag_lower in [t.lower() for t in e.get("tags", [])]
        ]
        if matches:
            results[yaml_path.name] = sorted(matches)

    return results


def count_companies() -> dict[str, int]:
    """
    Return the count of company entries per YAML file.

    Returns:
        Dict mapping yaml_filename -> company count.
    """
    counts: dict[str, int] = {}
    for yaml_path in _all_yaml_files():
        data = _load_yaml(yaml_path)
        top_key = "aggregators" if "aggregators" in data else "companies"
        counts[yaml_path.name] = len(data.get(top_key, []))
    return counts
