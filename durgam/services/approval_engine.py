"""Approval engine helper — M10 Phase 3A OR-set support (STEP-A).

`resolve_stage_candidates` is the single entry point for OR-set stages.
It reads ApprovalStageOption rows for (process_id, stage_index) and
dispatches each row's resolver_name to the resolver registry.

ADDITIVE: this module does NOT import from or modify approval_request.py or
approval_routing.py.  The legacy single-role-code path in ApprovalRequestService
is unchanged.  Phase 3B will wire this helper into the service after validation.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlmodel import Session, select

from durgam.models.crosscutting import ApprovalProcess
from durgam.models.identity import User
from durgam.repositories.approval_stage_option import ApprovalStageOptionRepository
from durgam.services.approval_resolvers import ResolverContext, UnknownResolverError, resolve


class EngineError(Exception):
    """Raised when the engine encounters an unrecoverable configuration problem."""


def resolve_stage_candidates(
    session: Session,
    process_id: UUID,
    stage_index: int,
    ctx: ResolverContext,
) -> list[User]:
    """Return the union of users returned by all OR-set resolvers for this stage.

    If no ApprovalStageOption rows exist for (process_id, stage_index), returns
    an empty list — the caller should fall back to the legacy routing path.

    Raises EngineError if any resolver_name is not in the registry.
    """
    repo = ApprovalStageOptionRepository(session)
    options = repo.list_by_process_stage(process_id, stage_index)
    if not options:
        return []

    seen: set[UUID] = set()
    candidates: list[User] = []

    for opt in options:
        try:
            users = resolve(opt.resolver_name, ctx, session)
        except UnknownResolverError as exc:
            raise EngineError(str(exc)) from exc

        for user in users:
            if user.id not in seen:
                candidates.append(user)
                seen.add(user.id)

    return candidates


def get_stage_pick_mode(
    session: Session,
    process_id: UUID,
    stage_index: int,
) -> Literal["approver", "requestor"] | None:
    """Read pick_mode for a specific stage from ApprovalProcess.stage_pick_modes_json.

    JSON shape: {"1": "approver", "2": "requestor", ...} — keys are stage indices
    as strings (matches ApprovalRequest.current_stage 1-based convention).

    Returns:
    - 'approver' if the stage is configured for approver-pick mode
    - 'requestor' if the stage is configured for requestor-pick mode
    - None if stage_pick_modes_json is NULL, missing the stage key, or contains
      an invalid value (legacy stages fall through — caller uses legacy single-role routing)
    """
    process = session.exec(
        select(ApprovalProcess).where(
            ApprovalProcess.id == process_id,
            ApprovalProcess.is_deleted == False,  # noqa: E712
        )
    ).first()
    if process is None or process.stage_pick_modes_json is None:
        return None

    mode = process.stage_pick_modes_json.get(str(stage_index))
    if mode not in ("approver", "requestor"):
        return None
    return mode  # type: ignore[return-value]
