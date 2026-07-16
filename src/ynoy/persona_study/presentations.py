from __future__ import annotations

from typing import Literal

from ynoy.models import AnnotationPresentation, BlindMapEntry, EvidenceWindow, PresentationMessage
from ynoy.util import sha256_text

Split = Literal["annotation_development", "annotation_reserved"]


def build_presentations(
    windows: tuple[EvidenceWindow, ...], split: dict[str, Split], study_id: str
) -> tuple[tuple[AnnotationPresentation, ...], tuple[BlindMapEntry, ...]]:
    sampled = sorted(
        (item for item in windows if item.selection_arm == "sampled"),
        key=lambda item: item.window_id,
    )
    challenge = sorted(
        (item for item in windows if item.selection_arm == "challenge"),
        key=lambda item: item.window_id,
    )
    base = [item for pair in zip(sampled, challenge, strict=True) for item in pair]
    insertion_points = {8 + 2 * index: item for index, item in enumerate(base[:8])}
    sequence: list[tuple[EvidenceWindow, bool]] = []
    for index, window in enumerate(base, start=1):
        sequence.append((window, False))
        if repeated := insertion_points.get(index):
            sequence.append((repeated, True))
    return _materialize(sequence, split, study_id)


def _materialize(
    sequence: list[tuple[EvidenceWindow, bool]], split: dict[str, Split], study_id: str
) -> tuple[tuple[AnnotationPresentation, ...], tuple[BlindMapEntry, ...]]:
    presentations: list[AnnotationPresentation] = []
    blind: list[BlindMapEntry] = []
    for order, (window, repeated) in enumerate(sequence, start=1):
        presentation_id = sha256_text(
            f"{study_id}:presentation:{order}:{window.window_id}:{int(repeated)}"
        )
        presentations.append(
            AnnotationPresentation(
                presentation_id=presentation_id,
                order=order,
                context=tuple(
                    PresentationMessage(speaker=item.speaker, content=item.content)
                    for item in window.context
                ),
                focus=PresentationMessage(
                    speaker=window.focus.speaker, content=window.focus.content
                ),
            )
        )
        blind.append(
            BlindMapEntry(
                presentation_id=presentation_id,
                window_id=window.window_id,
                annotation_partition=split[window.window_id],
                repeated=repeated,
            )
        )
    return tuple(presentations), tuple(blind)
