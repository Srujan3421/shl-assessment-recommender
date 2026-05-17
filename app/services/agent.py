import re
from typing import Any

from app.schemas import ChatMessage, ChatResponse
from app.services.catalog import to_recommendation
from app.services.retrieval import TYPE_LABELS, extract_intent, find_named_records, rank_records


PROMPT_INJECTION_RE = re.compile(
    r"\b(ignore|forget|override|reveal|dump|bypass)\b.*\b(instruction|prompt|system|developer|policy|guardrail)s?\b",
    re.IGNORECASE,
)
OFF_TOPIC_RE = re.compile(
    r"\b(weather|stock|crypto|recipe|medical diagnosis|doctor|diagnosis|lawsuit|legal|lawyer|visa|salary|compensation|pay range|offer|firing|fire\b|termination|hr policy|employment law)\b",
    re.IGNORECASE,
)
GENERAL_HIRING_ADVICE_RE = re.compile(
    r"\b(how should i hire|write interview questions|generate interview questions|interview question|employment law|termination|fire an employee|compensation|salary advice|offer advice)\b",
    re.IGNORECASE,
)
NON_SHL_RE = re.compile(r"\b(non-shl|outside shl|not shl|hackerrank|codility|leetcode|indeed assessments)\b", re.IGNORECASE)
ASSESSMENT_SCOPE_RE = re.compile(
    r"\b(assessment|test|shl|candidate|hiring|hire|role|job|selection|benchmark|leadership|executive|director|developer|engineer|manager|analyst|sales|java|python|spring|aws|docker|sql|excel|personality|opq|gsa|aptitude|cognitive|numerical|verbal|simulation|skills?)\b",
    re.IGNORECASE,
)
VAGUE_RE = re.compile(
    r"^\s*(hi|hello|hey|i need an assessment|need assessment|recommend assessments?|recommend tests?|we are hiring|help me choose|assessment needed)\s*[.!?]*\s*$",
    re.IGNORECASE,
)
COMPARE_RE = re.compile(r"\b(compare|difference|different|versus|vs\.?|between)\b", re.IGNORECASE)
REFUSAL = "I can only help with SHL assessment recommendations, refinements, and comparisons based on the SHL catalog."


class ChatAgent:
    def __init__(self, catalog: list[dict[str, Any]]):
        self.catalog = catalog

    def reply(self, messages: list[ChatMessage]) -> ChatResponse:
        user_messages = [message.content for message in messages if message.role == "user"]
        latest = user_messages[-1] if user_messages else ""
        context = "\n".join(user_messages)
        intent = extract_intent(context, latest)

        if self._is_prompt_injection(latest):
            return self._refuse(REFUSAL)

        if self._is_off_topic(latest):
            return self._refuse(REFUSAL)

        if self._is_compare(latest):
            return self._compare(latest)

        if self._needs_clarification(context):
            return ChatResponse(
                reply=(
                    "Sure. What role are you hiring for, and do you want to assess technical skills, "
                    "cognitive ability, personality, communication, or a mix?"
                ),
                recommendations=[],
                end_of_conversation=False,
            )

        ranked = rank_records(self.catalog, intent, limit=10)
        if not ranked:
            return ChatResponse(
                reply=(
                    "I have enough to stay in scope, but not enough to map this to specific SHL catalog tests. "
                    "Please share the role title, core skills, seniority, and any desired assessment type."
                ),
                recommendations=[],
                end_of_conversation=False,
            )

        type_phrase = self._type_phrase(intent.requested_types)
        recommendations = [to_recommendation(record) for record in ranked]
        reply = (
            f"Got it. I extracted the current context as role '{intent.role or 'not specified'}', "
            f"seniority '{intent.seniority or 'not specified'}', and skills "
            f"{', '.join(sorted(intent.skills)) or 'not specified'}. "
            f"Here are {len(recommendations)} SHL catalog assessments that best match{type_phrase}."
        )
        return ChatResponse(reply=reply, recommendations=recommendations, end_of_conversation=False)

    def _is_prompt_injection(self, latest: str) -> bool:
        return bool(PROMPT_INJECTION_RE.search(latest))

    def _is_off_topic(self, latest: str) -> bool:
        if NON_SHL_RE.search(latest):
            return True
        if OFF_TOPIC_RE.search(latest):
            return True
        if GENERAL_HIRING_ADVICE_RE.search(latest):
            return True
        if len(latest.split()) > 3 and not ASSESSMENT_SCOPE_RE.search(latest):
            return True
        return False

    def _is_compare(self, latest: str) -> bool:
        return bool(COMPARE_RE.search(latest))

    def _needs_clarification(self, context: str) -> bool:
        normalized = context.strip()
        if VAGUE_RE.match(normalized):
            return True
        scope_terms = ASSESSMENT_SCOPE_RE.findall(normalized)
        content_words = re.findall(r"[a-zA-Z0-9+#.]{3,}", normalized)
        if len(content_words) < 4:
            return True
        return len(scope_terms) == 0

    def _compare(self, latest: str) -> ChatResponse:
        matches = find_named_records(self.catalog, latest, limit=4)
        if len(matches) < 2:
            return ChatResponse(
                reply=(
                    "I can compare SHL catalog assessments, but I need two recognizable catalog names. "
                    "Please provide the assessment names exactly as they appear in the SHL catalog."
                ),
                recommendations=[],
                end_of_conversation=False,
            )

        first, second = matches[0], matches[1]
        reply = "\n".join(
            [
                f"{first['name']} and {second['name']} differ in the catalog fields I can verify:",
                self._comparison_line(first),
                self._comparison_line(second),
                "In simple terms, choose the first when its catalog description and type match the capability you want to measure; choose the second when its catalog description and type match better. I am not adding recommendations because this was a comparison request.",
            ]
        )
        return ChatResponse(reply=reply, recommendations=[], end_of_conversation=False)

    def _comparison_line(self, record: dict[str, Any]) -> str:
        type_labels = ", ".join(TYPE_LABELS.get(code, code) for code in record["test_types"])
        remote = "remote testing available" if record.get("remote") else "remote testing not marked"
        adaptive = "adaptive marked" if record.get("adaptive") else "adaptive not marked"
        duration = record.get("duration") or "duration not listed"
        description = record.get("description") or "No description is available in the catalog record."
        return f"- {record['name']}: {type_labels}; duration {duration}; {remote}; {adaptive}. {description} URL: {record['url']}"

    def _refuse(self, reply: str) -> ChatResponse:
        return ChatResponse(reply=reply, recommendations=[], end_of_conversation=False)

    def _type_phrase(self, requested: set[str]) -> str:
        if not requested:
            return ""
        labels = [TYPE_LABELS.get(code, code) for code in sorted(requested)]
        return " with emphasis on " + ", ".join(labels)
