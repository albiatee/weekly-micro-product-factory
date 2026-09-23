"""Constants from the adopted Schema Contract."""

from __future__ import annotations

# ID prefixes
PREFIX_SIGNAL = "sig_"
PREFIX_OPPORTUNITY = "opp_"
PREFIX_EXPERIMENT = "exp_"
PREFIX_DECISION = "dec_"
PREFIX_LEARNING = "lr_"

# Signal.source — reference list (extensible; `other` always allowed)
SIGNAL_SOURCES = frozenset(
    {
        "github_issue",
        "x",
        "reddit",
        "trends",
        "review",
        "competitor",
        "manual",
        "other",
    }
)

# Opportunity.status
OPP_STATUSES = frozenset(
    {
        "draft",
        "hypothesized",
        "experimenting",
        "decided",
        "building",
        "shipped",
        "iterating",
        "killed",
    }
)

# Allowed transitions: from -> frozenset(to)
OPP_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"hypothesized", "killed"}),
    "hypothesized": frozenset({"experimenting", "killed"}),
    "experimenting": frozenset({"decided"}),  # only
    "decided": frozenset({"building", "iterating", "killed"}),
    "building": frozenset({"shipped", "killed"}),
    "shipped": frozenset({"iterating"}),
    "iterating": frozenset({"hypothesized", "experimenting"}),
    "killed": frozenset(),
}

# Statuses that require non-empty signal_ids
OPP_REQUIRES_SIGNALS = frozenset(
    {
        "hypothesized",
        "experimenting",
        "decided",
        "building",
        "shipped",
        "iterating",
        # killed may have been hypothesized before; require if not draft-origin only —
        # contract: from hypothesized onward. killed after hypothesized must keep signals.
        "killed",
    }
)

SOLUTION_TYPES = frozenset(
    {
        "digital_micro",
        "content_pack",
        "concierge",
        "saas",
        "physical_hybrid",
        "marketplace",
        "unknown",
    }
)

EXPERIMENT_STATUSES = frozenset({"planned", "running", "completed", "aborted"})
EXPERIMENT_TYPES = frozenset(
    {
        "smoke_page",
        "waitlist",
        "concierge",
        "preorder",
        "community_vote",
        "manual_pilot",
    }
)

DECISION_VERDICTS = frozenset({"execute", "iterate", "kill"})
DECIDED_BY = frozenset({"human", "human_with_agent_suggestion"})

# Decision.evidence_refs — only these prefixes in contract v1
EVIDENCE_PREFIXES = (PREFIX_EXPERIMENT, PREFIX_SIGNAL)
