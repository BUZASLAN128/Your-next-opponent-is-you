from __future__ import annotations

from enum import StrEnum


class SpeechAct(StrEnum):
    REQUIREMENT = "requirement"
    PREFERENCE = "preference"
    CORRECTION = "correction"
    PROPOSAL = "proposal"
    QUESTION = "question"
    ASPIRATION = "aspiration"
    REJECTION = "rejection"
    DECISION = "decision"
    OBSERVATION = "observation"


class ClaimModality(StrEnum):
    MUST = "must"
    MUST_NOT = "must_not"
    SHOULD = "should"
    PREFER = "prefer"
    CONDITIONAL = "conditional"
    POSSIBLE = "possible"
    EXPLORATORY = "exploratory"
    UNKNOWN = "unknown"


class AtomicClaimType(StrEnum):
    VALUE = "value"
    GOAL = "goal"
    PREFERENCE = "preference"
    REQUIREMENT = "requirement"
    POLICY = "policy"
    GUARDRAIL = "guardrail"
    HYPOTHESIS = "hypothesis"
    ASPIRATION = "aspiration"
    METACOGNITIVE_RULE = "metacognitive_rule"
    DESIGN_PRINCIPLE = "design_principle"


class TargetLayer(StrEnum):
    PROJECT_CONSTITUTION = "project_constitution"
    PROTECTED_CONTROL = "protected_control"
    ARCHITECTURE_CANDIDATE = "architecture_candidate"
    SCOPED_POLICY = "scoped_policy"
    MISSION_STATE = "mission_state"
    EPISODIC_MEMORY = "episodic_memory"
    EXPERIMENT_BACKLOG = "experiment_backlog"
    RESEARCH_VISION = "research_vision"
    PERSONA_CANDIDATE = "persona_candidate"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class NullReason(StrEnum):
    NOT_STATED = "not_stated"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"
    INTENTIONALLY_UNSPECIFIED = "intentionally_unspecified"
    AWAITING_USER_CONFIRMATION = "awaiting_user_confirmation"
    REDACTED_FOR_PRIVACY = "redacted_for_privacy"
    SOURCE_UNAVAILABLE = "source_unavailable"


class ReviewAction(StrEnum):
    CONFIRM = "confirm"
    SPLIT = "split"
    NARROW_SCOPE = "narrow_scope"
    MARK_TEMPORARY = "mark_temporary"
    PROPOSE_FOR_CORE = "propose_for_core"
    MAKE_PROJECT_RULE = "make_project_rule"
    REJECT_INFERENCE = "reject_inference"
    REJECT = "reject"


class ReviewOutcome(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    REVISED = "revised"
    SPLIT = "split"
    CORE_REVIEW_REQUESTED = "core_review_requested"
