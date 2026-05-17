import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


TYPE_LABELS = {
    "A": "Ability & Aptitude",
    "B": "Biodata & Situational Judgement",
    "C": "Competencies",
    "D": "Development & 360",
    "E": "Assessment Exercises",
    "K": "Knowledge & Skills",
    "P": "Personality & Behavior",
    "S": "Simulations",
}

TYPE_CUES = {
    "A": {"ability", "aptitude", "cognitive", "numerical", "verbal", "reasoning", "calculation"},
    "B": {"biodata", "situational", "judgement", "judgment", "sjt"},
    "C": {"competency", "competencies", "leadership", "managerial", "communication"},
    "D": {"development", "360", "feedback"},
    "E": {"exercise", "assessment center", "case study"},
    "K": {"skill", "skills", "knowledge", "technical", "coding", "programming", "developer"},
    "P": {"personality", "behavior", "behaviour", "opq", "culture", "workstyle", "work style"},
    "S": {"simulation", "simulate", "hands on", "practical"},
}

QUERY_EXPANSIONS = {
    "java": {"java", "core java", "j2ee", "java ee"},
    "javascript": {"javascript", "node", "react", "angular"},
    "js": {"javascript", "node", "react", "angular"},
    "frontend": {"front end", "javascript", "react", "angular", "html", "css"},
    "backend": {"back end", "api", "sql", "database"},
    "fullstack": {"full stack", "javascript", "react", "angular", "sql"},
    "developer": {"programming", "software", "technical", "coding"},
    "engineer": {"engineering", "technical", "software"},
    "devops": {"aws", "azure", "cloud", "linux", "docker"},
    "data": {"analytics", "data science", "python", "excel"},
    "analyst": {"analysis", "excel", "sql", "numerical"},
    "sales": {"sales", "customer", "communication"},
    "manager": {"management", "leadership", "supervisor"},
    "stakeholder": {"communication", "personality", "competency"},
    "stakeholders": {"communication", "personality", "competency"},
    "opq": {"opq", "personality"},
    "gsa": {"global skills", "general ability", "g+"},
}

QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "in",
    "is",
    "it",
    "of",
    "or",
    "our",
    "the",
    "to",
    "we",
    "with",
    "need",
    "solution",
    "solutions",
    "candidate",
    "candidates",
    "hiring",
    "hire",
    "people",
    "pool",
    "positions",
    "experience",
    "years",
}

SKILL_ALIASES = {
    ".net": {".net"},
    "ai": {"ai", "artificial intelligence", "ai skills"},
    "aiml": {"ai", "ml", "machine learning", "data science"},
    "angular": {"angular"},
    "aws": {"aws", "amazon web services"},
    "azure": {"azure"},
    "c": {"c programming"},
    "c++": {"c++"},
    "communication": {"communication"},
    "data science": {"data science", "analytics"},
    "docker": {"docker"},
    "excel": {"excel", "ms excel", "microsoft excel"},
    "genai": {"genai", "generative ai", "ai skills"},
    "hipaa": {"hipaa"},
    "java": {"java", "core java", "java 8", "java ee", "java web services", "java frameworks"},
    "javascript": {"javascript"},
    "linux": {"linux"},
    "llmops": {"llmops", "ai skills"},
    "networking": {"networking"},
    "python": {"python"},
    "react": {"react"},
    "rest": {"rest", "restful", "web services"},
    "rust": {"rust", "linux", "networking", "live coding"},
    "safety": {"safety", "dependability"},
    "sales": {"sales"},
    "spring": {"spring"},
    "sql": {"sql"},
    "word": {"word", "microsoft word", "ms word"},
}

ALIAS_TO_NAME = {
    "opq": "Occupational Personality Questionnaire OPQ32r",
    "opq32": "Occupational Personality Questionnaire OPQ32r",
    "opq32r": "Occupational Personality Questionnaire OPQ32r",
    "gsa": "Global Skills Assessment",
    "verify g+": "SHL Verify Interactive G+",
    "verify interactive g+": "SHL Verify Interactive G+",
}

REFINEMENT_RE = re.compile(
    r"\b(actually|also|add|remove|drop|instead|include|exclude|change|make it|prefer|only|replace)\b",
    re.IGNORECASE,
)

EXCLUDE_RE = re.compile(
    r"\b(?:remove|drop|exclude|without|no|not|skip)\s+(?:the\s+)?([a-z0-9+#. ]{2,40}?)(?:[,.;]|$|\s+and\b)",
    re.IGNORECASE,
)

NEGATED_TYPE_PATTERNS = {
    "P": re.compile(r"\b(no|not|without|exclude|remove)\s+(personality|behavior|behaviour|opq)\b"),
    "A": re.compile(r"\b(no|not|without|exclude|remove)\s+(aptitude|ability|cognitive|reasoning)\b"),
    "K": re.compile(r"\b(no|not|without|exclude|remove)\s+(technical|skills?|knowledge|coding)\b"),
}


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9+#.]+", text.lower())


def phrase_normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


@dataclass(frozen=True)
class QueryIntent:
    text: str
    latest: str
    role: str = ""
    seniority: str = ""
    skills: set[str] = field(default_factory=set)
    skill_order: tuple[str, ...] = ()
    requested_types: set[str] = field(default_factory=set)
    negated_types: set[str] = field(default_factory=set)
    include_personality: bool = False
    exclude_terms: set[str] = field(default_factory=set)
    is_refinement: bool = False


def extract_intent(context: str, latest: str | None = None) -> QueryIntent:
    latest = latest if latest is not None else context
    normalized = phrase_normalize(context)
    latest_norm = phrase_normalize(latest)
    skill_order = extract_skill_order(normalized)
    skills = set(skill_order)
    role = extract_role(context)
    seniority = extract_seniority(normalized)
    types = requested_types(context)
    if "technical assessment" in normalized or "technical test" in normalized:
        types.add("K")
    include_personality = bool({"P"} & types) or any(
        cue in normalized for cue in ("leadership", "manager", "mentor", "stakeholder", "culture", "behavior", "behaviour")
    )
    if include_personality:
        types.add("P")
    exclude_terms = extract_exclusions(latest_norm)
    return QueryIntent(
        text=context,
        latest=latest,
        role=role,
        seniority=seniority,
        skills=skills,
        skill_order=skill_order,
        requested_types=types,
        negated_types=negated_types(context),
        include_personality=include_personality,
        exclude_terms=exclude_terms,
        is_refinement=bool(REFINEMENT_RE.search(latest)),
    )


def extract_skills(normalized_text: str) -> set[str]:
    return set(extract_skill_order(normalized_text))


def extract_skill_order(normalized_text: str) -> tuple[str, ...]:
    positions: list[tuple[int, str]] = []
    for skill, aliases in SKILL_ALIASES.items():
        matches = [phrase_position(alias, normalized_text) for alias in aliases | {skill}]
        matches = [match for match in matches if match >= 0]
        if matches:
            positions.append((min(matches), skill))
    if "full stack" in normalized_text or "full-stack" in normalized_text:
        positions.append((min(value for value in [normalized_text.find("full stack"), normalized_text.find("full-stack")] if value >= 0), "fullstack"))
    if "ai ml" in normalized_text or "ai/ml" in normalized_text:
        positions.append((min(value for value in [normalized_text.find("ai ml"), normalized_text.find("ai/ml")] if value >= 0), "aiml"))

    ordered: list[str] = []
    for _, skill in sorted(positions):
        if skill not in ordered:
            ordered.append(skill)
    return tuple(ordered)


def phrase_in_text(phrase: str, text: str) -> bool:
    if any(char in phrase for char in "+#.") or " " in phrase:
        return phrase in text
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text))


def phrase_position(phrase: str, text: str) -> int:
    if any(char in phrase for char in "+#.") or " " in phrase:
        return text.find(phrase)
    match = re.search(rf"\b{re.escape(phrase)}\b", text)
    return match.start() if match else -1


def extract_role(text: str) -> str:
    match = re.search(r"\b(?:hiring|hire|for)\s+(?:a|an|the)?\s*([^.\n,;]{3,80})", text, re.IGNORECASE)
    return " ".join(match.group(1).split()) if match else ""


def extract_seniority(normalized_text: str) -> str:
    years = re.search(r"\b(\d{1,2})\+?\s*(?:years?|yrs?)\b", normalized_text)
    if years:
        return f"{years.group(1)} years"
    for cue in ("executive", "director", "senior", "mid-level", "mid professional", "entry-level", "graduate"):
        if cue in normalized_text:
            return cue
    return ""


def extract_exclusions(latest_norm: str) -> set[str]:
    terms: set[str] = set()
    for match in EXCLUDE_RE.finditer(latest_norm):
        value = match.group(1).strip()
        if value:
            terms.add(value)
    if "drop rest" in latest_norm:
        terms.add("rest")
    if "drop opq" in latest_norm or "remove opq" in latest_norm:
        terms.add("opq")
    return terms


def expand_query(text: str) -> Counter[str]:
    tokens = Counter(token for token in tokenize(text) if token not in QUERY_STOPWORDS)
    normalized = phrase_normalize(text)
    for key, values in QUERY_EXPANSIONS.items():
        if key in tokens or key in normalized:
            for value in values:
                for token in tokenize(value):
                    tokens[token] += 2
    return tokens


def requested_types(text: str) -> set[str]:
    normalized = phrase_normalize(text)
    found: set[str] = set()
    for type_code, cues in TYPE_CUES.items():
        if any(cue in normalized for cue in cues):
            found.add(type_code)
    return found


def negated_types(text: str) -> set[str]:
    normalized = phrase_normalize(text)
    return {type_code for type_code, pattern in NEGATED_TYPE_PATTERNS.items() if pattern.search(normalized)}


def record_text(record: dict[str, Any]) -> str:
    labels = " ".join(TYPE_LABELS.get(code, code) for code in record["test_types"])
    keywords = " ".join(record.get("keywords", []))
    job_levels = " ".join(record.get("job_levels", []))
    languages = " ".join(record.get("languages", []))
    duration = record.get("duration", "")
    keys = " ".join(record.get("keys", []))
    return f"{record['name']} {record.get('description', '')} {labels} {keys} {job_levels} {languages} {duration} {keywords}"


def score_record(record: dict[str, Any], query: str | QueryIntent) -> float:
    intent = query if isinstance(query, QueryIntent) else extract_intent(query)
    normalized_query = phrase_normalize(intent.text)
    query_terms = expand_query(intent.text)
    if not query_terms:
        return 0.0

    name = phrase_normalize(record["name"])
    description = phrase_normalize(record.get("description", ""))
    haystack = phrase_normalize(record_text(record))
    name_tokens = Counter(tokenize(record["name"]))
    description_tokens = Counter(tokenize(record.get("description", "")))
    record_tokens = Counter(tokenize(haystack))

    score = 0.0
    for term, weight in query_terms.items():
        if len(term) < 2:
            continue
        if term in name_tokens:
            score += 7.0 * weight
        elif term in description_tokens:
            score += 2.0 * weight
        elif term in record_tokens:
            score += 1.0 * weight

    for skill in intent.skills:
        score += score_skill_match(skill, name, description, haystack)
        if intent.role and phrase_in_text(skill, phrase_normalize(intent.role)) and score_skill_match(skill, name, "", haystack) >= 20:
            score += 45.0

    for phrase in QUERY_EXPANSIONS.values():
        for value in phrase:
            if len(value) > 3 and value in normalized_query and value in name:
                score += 10.0

    for type_code in intent.requested_types:
        if type_code in record["test_types"]:
            score += 16.0
    if "K" in intent.requested_types and not any(code in record["test_types"] for code in ("K", "S")):
        score -= 60.0

    for type_code in intent.negated_types:
        if type_code in record["test_types"]:
            score -= 30.0

    for term in intent.exclude_terms:
        if term and (term in name or term in haystack):
            score -= 75.0
        if term in {"opq", "personality"} and "P" in record["test_types"]:
            score -= 75.0

    if any(code in record["test_types"] for code in ("K", "S")) and any(
        cue in normalized_query
        for cue in ("developer", "engineer", "technical", "programming", "coding", "software")
    ):
        score += 5.0

    if intent.include_personality and "P" in record["test_types"]:
        score += 12.0

    if any(cue in normalized_query for cue in ("leadership", "executive", "cxo", "director", "benchmark")):
        if "opq" in name or "leadership" in name:
            score += 35.0
        if "P" in record["test_types"]:
            score += 12.0
        if "entry" in name:
            score -= 40.0

    score += seniority_bonus(intent.seniority, record)
    score -= unrelated_penalty(intent, name, haystack, record)

    if record.get("remote"):
        score += 0.25
    if record.get("adaptive"):
        score += 0.15

    return score


def score_skill_match(skill: str, name: str, description: str, haystack: str) -> float:
    aliases = SKILL_ALIASES.get(skill, {skill}) | {skill}
    score = 0.0
    for alias in aliases:
        if not alias or alias in {"ai", "ml"}:
            continue
        if phrase_in_text(alias, name):
            score += 55.0 if len(alias) >= 3 else 15.0
        elif alias in name:
            score += 30.0
        elif phrase_in_text(alias, description):
            score += 12.0
        elif phrase_in_text(alias, haystack):
            score += 6.0
    if skill == "fullstack" and any(value in name for value in ("javascript", "angular", "sql", "python")):
        score += 5.0
    return score


def seniority_bonus(seniority: str, record: dict[str, Any]) -> float:
    if not seniority:
        return 0.0
    name = phrase_normalize(record["name"])
    levels = phrase_normalize(" ".join(record.get("job_levels", [])))
    years = re.match(r"(\d{1,2}) years", seniority)
    is_senior = "senior" in seniority or bool(years and int(years.group(1)) >= 5)
    if is_senior:
        if "advanced" in name:
            return 18.0
        if any(level in levels for level in ("director", "executive", "manager")):
            return 8.0
        if "entry" in name:
            return -25.0
    if "entry" in seniority or "graduate" in seniority:
        if "entry" in name or "graduate" in levels or "graduate" in name:
            return 10.0
        if "advanced" in name:
            return -8.0
    if seniority in levels:
        return 3.0
    return 0.0


def unrelated_penalty(intent: QueryIntent, name: str, haystack: str, record: dict[str, Any]) -> float:
    if not intent.skills:
        return 0.0
    penalty = 0.0
    technical_skills = intent.skills & {
        ".net",
        "angular",
        "aws",
        "azure",
        "c",
        "c++",
        "data science",
        "docker",
        "excel",
        "java",
        "javascript",
        "linux",
        "networking",
        "python",
        "react",
        "rest",
        "spring",
        "sql",
        "word",
    }
    if technical_skills and "K" in intent.requested_types and "K" in record["test_types"]:
        matched = any(score_skill_match(skill, name, "", haystack) >= 20.0 for skill in technical_skills)
        if not matched:
            penalty += 35.0
    if "python" in intent.skills and any(bad in name for bad in ("c programming", "sql server", "technical support", "business analysis")):
        penalty += 45.0
    if "java" in intent.skills and any(bad in name for bad in ("javascript", "c programming", "python")):
        penalty += 20.0
    return penalty


def rank_records(records: list[dict[str, Any]], query: str | QueryIntent, limit: int = 10) -> list[dict[str, Any]]:
    intent = query if isinstance(query, QueryIntent) else extract_intent(query)
    scored = [(score_record(record, intent), record) for record in records]
    min_score = 25.0 if intent.skills and intent.requested_types == {"K"} else 18.0 if intent.skills else 2.5
    scored = [(score, record) for score, record in scored if score > min_score and math.isfinite(score)]
    if intent.requested_types == {"K"}:
        scored = [
            (score, record)
            for score, record in scored
            if any(code in record["test_types"] for code in ("K", "S"))
        ]
    scored.sort(key=lambda item: (-item[0], item[1]["name"].lower()))
    return diversify_by_skill(scored, intent, limit)


def diversify_by_skill(scored: list[tuple[float, dict[str, Any]]], intent: QueryIntent, limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for skill in intent.skill_order:
        candidate = best_for_skill(scored, skill, seen)
        if candidate:
            selected.append(candidate)
            seen.add(candidate["url"])
        if len(selected) >= limit:
            return selected

    for type_code in sorted(intent.requested_types):
        candidate = best_for_type(scored, type_code, seen)
        if candidate:
            selected.append(candidate)
            seen.add(candidate["url"])
        if len(selected) >= limit:
            return selected

    for _, record in scored:
        if record["url"] in seen:
            continue
        selected.append(record)
        seen.add(record["url"])
        if len(selected) >= limit:
            break
    return selected


def best_for_skill(
    scored: list[tuple[float, dict[str, Any]]], skill: str, seen: set[str]
) -> dict[str, Any] | None:
    best: tuple[float, dict[str, Any]] | None = None
    for total_score, record in scored:
        if record["url"] in seen:
            continue
        name = phrase_normalize(record["name"])
        description = phrase_normalize(record.get("description", ""))
        haystack = phrase_normalize(record_text(record))
        skill_score = score_skill_match(skill, name, description, haystack)
        if skill_score < 20.0:
            continue
        weighted = total_score + skill_score + canonical_skill_bonus(skill, name)
        if best is None or weighted > best[0]:
            best = (weighted, record)
    return best[1] if best else None


def best_for_type(
    scored: list[tuple[float, dict[str, Any]]], type_code: str, seen: set[str]
) -> dict[str, Any] | None:
    best: tuple[float, dict[str, Any]] | None = None
    for total_score, record in scored:
        if record["url"] in seen or type_code not in record["test_types"]:
            continue
        name = phrase_normalize(record["name"])
        weighted = total_score
        if type_code == "P" and ("opq32r" in name or name == "occupational personality questionnaire opq32r"):
            weighted += 120.0
        if type_code == "A" and name == "shl verify interactive g+":
            weighted += 120.0
        if best is None or weighted > best[0]:
            best = (weighted, record)
    return best[1] if best else None


def canonical_skill_bonus(skill: str, name: str) -> float:
    preferred = {
        "aws": ("amazon web services", "aws"),
        "docker": ("docker (new)", "docker"),
        "excel": ("microsoft excel", "ms excel"),
        "java": ("core java", "java 8"),
        "python": ("python (new)", "python"),
        "spring": ("spring (new)", "spring"),
        "sql": ("sql (new)",),
        "word": ("microsoft word", "ms word"),
    }
    for phrase in preferred.get(skill, ()):
        if name.startswith(phrase) or name == phrase:
            return 80.0
    return 0.0


def find_named_records(records: list[dict[str, Any]], text: str, limit: int = 4) -> list[dict[str, Any]]:
    normalized = phrase_normalize(text)
    alias_hits: list[dict[str, Any]] = []
    for alias, target in ALIAS_TO_NAME.items():
        if phrase_in_text(alias, normalized):
            match = find_by_name(records, target)
            if match and match not in alias_hits:
                alias_hits.append(match)

    matches: list[tuple[float, dict[str, Any]]] = []
    for record in records:
        name = phrase_normalize(record["name"])
        compact_name = re.sub(r"[^a-z0-9]", "", name)
        score = 0.0
        if name and name in normalized:
            score += 100.0
        for token in tokenize(record["name"]):
            if len(token) >= 3 and re.search(rf"\b{re.escape(token)}\b", normalized):
                score += 12.0
        for query_alias, expansions in QUERY_EXPANSIONS.items():
            if query_alias in normalized and any(expansion in name for expansion in expansions):
                score += 25.0
        if "opq" in normalized and "opq" in compact_name:
            score += 80.0
        if "gsa" in normalized and ("global skills" in name or "g+" in name):
            score += 60.0
        if score > 0:
            matches.append((score, record))
    matches.sort(key=lambda item: (-item[0], item[1]["name"].lower()))

    unique: list[dict[str, Any]] = list(alias_hits)
    seen: set[str] = set()
    for record in unique:
        seen.add(record["url"])
    for _, record in matches:
        if record["url"] in seen:
            continue
        seen.add(record["url"])
        unique.append(record)
        if len(unique) >= limit:
            break
    return unique


def find_by_name(records: list[dict[str, Any]], target_name: str) -> dict[str, Any] | None:
    target = phrase_normalize(target_name)
    for record in records:
        if phrase_normalize(record["name"]) == target:
            return record
    for record in records:
        if target in phrase_normalize(record["name"]):
            return record
    return None
