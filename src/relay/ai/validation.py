"""Policy validation for AI drafts.

Structural safety (no owner field, no extra fields) is enforced by the schema.
This layer enforces graph integrity and assumption discipline. Any violation
routes the caller to the deterministic fallback; nothing invalid reaches
canonical state.
"""

from __future__ import annotations

from relay.ai.schemas import ResponsibilityGraphDraft
from relay.core.enums import Provenance


def _has_cycle(step_keys: set[str], edges: list[tuple[str, str]]) -> bool:
    graph: dict[str, list[str]] = {k: [] for k in step_keys}
    for frm, to in edges:
        if frm in graph:
            graph[frm].append(to)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(step_keys, WHITE)

    def visit(node: str) -> bool:
        color[node] = GRAY
        for nxt in graph.get(node, []):
            if color.get(nxt) == GRAY:
                return True
            if color.get(nxt) == WHITE and visit(nxt):
                return True
        color[node] = BLACK
        return False

    return any(color[k] == WHITE and visit(k) for k in step_keys)


def validate_draft(draft: ResponsibilityGraphDraft) -> list[str]:
    violations: list[str] = []

    keys = [s.step_key for s in draft.steps]
    key_set = set(keys)
    if len(keys) != len(key_set):
        violations.append("duplicate step keys")

    edges: list[tuple[str, str]] = []
    for dep in draft.dependencies:
        if dep.from_step_key == dep.to_step_key:
            violations.append(f"self dependency on {dep.from_step_key}")
        if dep.from_step_key not in key_set or dep.to_step_key not in key_set:
            violations.append("dependency references unknown step")
        edges.append((dep.from_step_key, dep.to_step_key))
    if _has_cycle(key_set, edges):
        violations.append("dependency graph is cyclic")

    # High-impact assumption discipline: an AI-inferred concrete deadline must be
    # surfaced (as an assumption or a clarification), never presented as fact.
    if (
        draft.deadline_at is not None
        and draft.field_provenance.get("deadline_at") == Provenance.ai_inferred
        and not draft.assumptions
        and not draft.clarification_questions
    ):
        violations.append("inferred deadline not surfaced as an assumption or question")

    return violations
