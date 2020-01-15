"""Defines submission stages and workflows supported by this UI."""

from typing import Iterable, Optional, Callable, List, Iterator, Union

from arxiv.submission.domain import Submission
from dataclasses import dataclass, field

from . import stages
from .stages import Stage


@dataclass
class WorkflowDefinition:
    order: List[Stage] = field(default_factory=list)

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

    def __getitem__(self, query):
        return self.get_stage(query)

    def get_stage(self, query: Union[type, Stage, str, int]) -> Optional[Stage]:
        """Get the stage object from this workflow for Class, class name,
        stage label, endpoint or index in order """
        if query is None:
            return None
        if isinstance(query, type):
            if issubclass(query, Stage):
                stages = [st for st in self.order if issubclass(
                    st.__class__, query)]
                if len(stages) > 0:
                    return stages[0]
                else:
                    return None
            else:
                raise ValueError("Cannot call get_stage with non-Stage class")
        if isinstance(query, int):
            if query >= len(self.order) or query < 0:
                return None
            else:
                return self.order[query]
        if query in self.order:
            return self[self.order.index(query)]
        if isinstance(query, str):
            # it could be classname, stage label or stage endpoint
            for stage in self.order:
                if(stage.label == query
                        or stage.__class__.__name__ == query
                        or stage.endpoint == query):
                    return stage
            return None
        raise ValueError("query should be Stage class or class name or "
                         f"endpoint or lable str or int. Not {type(query)}")


SubmissionWorkflow = WorkflowDefinition(
    [
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
    ],
    # Kind of odd that this is different instance than last in the list
    stages.Confirm()
)
"""Workflow for new submissions."""

ReplacementWorkflow=WorkflowDefinition(
    [
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
    ],
    stages.Confirm()
    )
"""Workflow for replacements."""



