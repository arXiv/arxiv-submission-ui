"""Defines submission stages and workflows supported by this UI."""

from typing import Iterable, Optional, Callable, List, Iterator

from arxiv.submission.domain import Submission
from dataclasses import dataclass

from . import stages
from .stages import Stage


class WorkflowDefinition:
    order: List[Stage] = []

    # TODO do we have workflows that don't have confirmations?
    confirmation: Optional[Stage] = None

    def __iter__(self) -> Iterator[Stage]:
        """Iterate over stages in this workflow."""
        for stage in self.order:
            yield stage

    def iter_prior(self, stage: Stage) -> Iterable[Stage]:
        """Iterate over stages in this workflow up to a particular stage."""
        for prior_stage in self.order:
            if prior_stage == stage:
                return
            yield prior_stage

    def complete(self) -> bool:
        """Determine whether this workflow is complete."""
        return bool(self.submission.is_finalized)

    def next_stage(self, stage: Optional[Stage]) -> Optional[Stage]:
        """Get the next stage."""
        if stage is None:
            return None
        idx = self.order.index(stage)
        if idx + 1 >= len(self.order):
            return None
        return self.order[idx + 1]

    def previous_stage(self, stage: Optional[Stage]) -> Optional[Stage]:
        """Get the previous stage."""
        if stage is None:
            return None
        idx = self.order.index(stage)
        if idx == 0:
            return None
        return self.order[idx - 1]

    def stage_from_endpoint(self, endpoint: str) -> Stage:
        """Get the :class:`.Stage` for an endpoint."""
        for stage in self.order:
            if stage.endpoint == endpoint:
                return stage
            raise ValueError(f'No stage for endpoint: {endpoint}')


class SubmissionWorkflow(WorkflowDefinition):
    """Workflow for new submissions."""
    order = [
        stages.VerifyUser(),
        stages.Authorship(),
        stages.License(),
        stages.Policy(),
        stages.Classification(),
        stages.CrossList(required=False, must_see=True),
        stages.FileUpload(),
        stages.Process(),
        stages.Metadata(),
        stages.OptionalMetadata(required=False, must_see=True),
        stages.FinalPreview(),
        stages.Confirm()
    ]

    #Kind of odd that this is different instance than last in the list
    confirmation = stages.Confirm()


class ReplacementWorkflow(WorkflowDefinition):
    """Workflow for replacements."""

    order = [
        stages.VerifyUser(must_see=True),
        stages.Authorship(must_see=True),
        stages.License(must_see=True),
        stages.Policy(must_see=True),
        stages.FileUpload(must_see=True),
        stages.Process(must_see=True),
        stages.Metadata(must_see=True),
        stages.OptionalMetadata(required=False, must_see=True),
        stages.FinalPreview(must_see=True),
        stages.Confirm(must_see=True)
    ]
    confirmation = stages.Confirm()

