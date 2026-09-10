"""
Career Tracker — LLM Match Judge (STUBBED)

Will be activated in Phase 7 to make judgment calls on borderline matches
(TF-IDF score between 55–80%). Until then, the TF-IDF score alone
determines match/reject.

The LLM is called ONLY for borderline cases — keeping API costs minimal.
"""

from __future__ import annotations

from typing import Any

from schema.job import Job

# ─── Prompt Template (for documentation / Phase 7 implementation) ───
#
# JUDGE_PROMPT = '''
# You are evaluating whether a job posting is a good match for a candidate.
#
# Job Title: {title}
# Company: {company}
# Description: {description}
#
# Candidate Profile:
# {profile_summary}
#
# Skills: {skills}
# Target Roles: {target_titles}
# Experience: {experience_years} years
#
# Evaluate:
# 1. Skill overlap (how many required skills does the candidate have?)
# 2. Seniority fit (is this the right level?)
# 3. Growth potential (could this role help the candidate grow?)
#
# Return JSON:
# {"match": true/false, "confidence": 0.0-1.0, "reasoning": "one sentence"}
# '''


class MatchDecision:
    """Result of an LLM judgment on a borderline match."""

    def __init__(self, match: bool, confidence: float, reasoning: str) -> None:
        self.match = match
        self.confidence = confidence
        self.reasoning = reasoning


_judge_cache: dict[str, MatchDecision] = {}


def judge_borderline(
    job: Job,
    profile: dict[str, Any],
) -> MatchDecision:
    """
    Use multi-provider LLM Engine to make a judgment call on a borderline match.

    Called when the score falls in the borderline range (55–80%).
    Results are cached in-memory by job.id to avoid redundant API token costs.
    """
    if job.id in _judge_cache:
        return _judge_cache[job.id]

    from advisor.llm_provider import llm_engine

    skills = profile.get("skills", [])
    target_titles = profile.get("target_titles", [])
    summary = profile.get("summary", "")

    prompt = f"""
You are evaluating whether a job posting is a good fit for an Indian IT MCA/BCA/B.Tech fresher.

Job Title: {job.title}
Company: {job.company}
Location: {job.location}
Description Snippet: {job.description[:600]}

Candidate Skills: {', '.join(skills)}
Target Roles: {', '.join(target_titles)}
Candidate Summary: {summary}

Evaluate:
1. Skill overlap (does candidate have key required skills like Python, React, SQL, Web Dev)?
2. Seniority fit (is this suitable for 0-2 years exp, fresher, associate, trainee)?
3. India tech market fit (Chennai, Bangalore, Remote, India)?

Return JSON:
{{
    "match": true,
    "confidence": 0.82,
    "reasoning": "One sentence explanation of fit"
}}
"""
    res, provider_name = llm_engine.generate_json(prompt, system_prompt="Evaluate tech job suitability for freshers in India.")
    if res and "match" in res:
        match_flag = bool(res.get("match", True))
        conf = float(res.get("confidence", 0.75))
        reason = f"[{provider_name}] {res.get('reasoning', 'Good skill alignment.')}"
        decision = MatchDecision(match=match_flag, confidence=conf, reasoning=reason)
        _judge_cache[job.id] = decision
        return decision

    # Local High-Precision Fallback Evaluator if no LLM provider responds
    text = f"{job.title} {job.description}".lower()
    matching_skills = [s for s in skills if s.lower() in text]
    match_ratio = len(matching_skills) / max(len(skills), 1)

    is_fresher_friendly = any(
        kw in text
        for kw in ["fresher", "trainee", "associate", "junior", "0-1", "0-2", "graduate", "walk-in", "entry"]
    )

    is_matched = (match_ratio >= 0.25) or is_fresher_friendly
    conf = min(0.60 + (match_ratio * 0.35), 0.95)
    reason = f"[Local AI Matcher] Matched {len(matching_skills)} skills: {', '.join(matching_skills[:3])}."

    decision = MatchDecision(match=is_matched, confidence=conf, reasoning=reason)
    _judge_cache[job.id] = decision
    return decision


