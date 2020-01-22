"""Defines submission stages and workflows supported by this UI."""

from typing import Optional, Dict

from arxiv.submission.domain import Submission
from dataclasses import field, dataclass
from . import WorkflowDefinition, Stage


@dataclass
class WorkflowProcessor:
    """Class to handle a submission moving through a WorkflowDefinition.

    The seen methods is_seen and mark_seen are handled with a Dict. This class
    doesn't handle loading or saving that data.
    """
    workflow: WorkflowDefinition
    submission: Submission
    seen: Dict[str, bool] = field(default_factory=dict)

    def is_complete(self) -> bool:
        """Determine whether this workflow is complete."""
        return bool(self.submission.is_finalized)

    def next_stage(self, stage: Optional[Stage]) -> Optional[Stage]:
        """Get the stage after the one in the parameter."""
        return self.workflow.next_stage(stage)
    
    def can_proceed_to(self, stage: Optional[Stage]) -> bool:
        """Determine whether the user can proceed to a stage."""
        if stage is None:
            return True
        return all(map(self.is_done, self.workflow.iter_prior(stage)))

    def current_stage(self) -> Optional[Stage]:
        """Get the first stage in the workflow that is not done."""
        for stage in self.workflow.order:
            if not self.is_done(stage):
                return stage
        return None

    def _seen_key(self, stage: Stage) -> str:
        return f"{self.workflow.name}---" +\
            f"{stage.__class__.__name__}---{stage.label}---"

    def mark_seen(self, stage: Optional[Stage]) -> None:
        """Mark a stage as seen by the user."""
        if stage is not None:
            self.seen[self._seen_key(stage)] = True

    def is_seen(self, stage: Optional[Stage]) -> bool:
        """Determine whether or not the user has seen this stage."""
        if stage is None:
            return True
        return self.seen.get(self._seen_key(stage), False)

    def is_done(self, stage: Optional[Stage]) -> bool:
        """
        Evaluate whether a stage is sufficiently addressed for this workflow.
        This considers whether the stage is complete (if required), and whether
        the stage has been seen (if it must be seen).
        """
        if stage is None:
            return True
        # TODO older logic:
        # return ((self.is_complete(stage) or not stage.required)
        #         and (self.is_seen(stage) or not stage.must_see))
        # More efficent:        
        return ((not stage.required or stage.is_complete(self.submission))
                and
                (not stage.must_see or self.is_seen(stage)))
