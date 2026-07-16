# ruff: noqa: RUF001 -- Turkish user-facing review copy is intentional.

from __future__ import annotations

from ynoy.models import (
    AnnotationPresentation,
    DataClass,
    PersonaAnnotationJudgment,
    PersonaModelProposal,
    PersonaProposalBundle,
)
from ynoy.persona_study.artifacts import ArtifactPayload
from ynoy.util import canonical_json_bytes

QUICK_REVIEW_PATH = "annotator/quick-review.template.json"
QUICK_REVIEW_MARKDOWN_PATH = "annotator/quick-review.md"
RETRY_QUICK_REVIEW_PATH = "annotator/quick-review.retry-01.template.json"
RETRY_QUICK_REVIEW_MARKDOWN_PATH = "annotator/quick-review.retry-01.md"
QUICK_REVIEW_INSTRUCTIONS = (
    "Her kart için yalnız confirm, correct veya not_mine seç.",
    "Model önerisi yoksa confirm kullanma.",
    "correct seçersen corrected_judgment alanını doldur.",
)


def review_payloads(
    bundle: PersonaProposalBundle,
    cards: tuple[AnnotationPresentation, ...],
    data_class: DataClass,
    sources: tuple[str, ...],
    attempt: str = "primary",
) -> tuple[ArtifactPayload, ArtifactPayload]:
    json_path, markdown_path = review_paths(attempt)
    return (
        ArtifactPayload(
            json_path,
            canonical_json_bytes(_review_template(bundle)),
            _raw_class(data_class),
            sources,
            "represented_user",
        ),
        ArtifactPayload(
            markdown_path,
            _review_markdown(bundle, cards).encode("utf-8"),
            _raw_class(data_class),
            sources,
        ),
    )


def review_paths(attempt: str) -> tuple[str, str]:
    if attempt == "primary":
        return QUICK_REVIEW_PATH, QUICK_REVIEW_MARKDOWN_PATH
    if attempt == "retry_01":
        return RETRY_QUICK_REVIEW_PATH, RETRY_QUICK_REVIEW_MARKDOWN_PATH
    raise ValueError(f"unsupported assisted review attempt: {attempt}")


def _review_template(bundle: PersonaProposalBundle) -> dict[str, object]:
    selected = tuple(item for item in bundle.proposals if item.selected_for_review)
    return {
        "schema_version": "persona-proposal-review/0.1",
        "study_id": bundle.receipt.study_id,
        "proposal_receipt_sha256": bundle.receipt.receipt_sha256,
        "completed_by": None,
        "instructions": QUICK_REVIEW_INSTRUCTIONS,
        "actions": [_review_action(item) for item in selected],
    }


def _review_action(item: PersonaModelProposal) -> dict[str, object]:
    proposal = item.chosen_judgment
    return {
        "presentation_id": item.presentation_id,
        "order": item.order,
        "proposed_judgment": proposal.model_dump(mode="json") if proposal else None,
        "allowed_actions": (
            ["confirm", "correct", "not_mine"] if proposal else ["correct", "not_mine"]
        ),
        "action": None,
        "corrected_judgment": None,
    }


def _review_markdown(
    bundle: PersonaProposalBundle, cards: tuple[AnnotationPresentation, ...]
) -> str:
    by_id = {item.presentation_id: item for item in cards}
    lines = [
        "# Hızlı Persona Önerisi Denetimi",
        "",
        "Model yalnız öneri üretti. Her kart için Doğru, Düzelt veya Bana ait değil seç.",
        "Bu denetim otomatik persona terfisi veya kişilik kalitesi kanıtı oluşturmaz.",
        "",
    ]
    for proposal in bundle.proposals:
        if proposal.selected_for_review:
            lines.extend(_review_card(proposal, by_id[proposal.presentation_id]))
    return "\n".join(lines).rstrip() + "\n"


def _review_card(proposal: PersonaModelProposal, card: AnnotationPresentation) -> list[str]:
    lines = [f"## Kart {card.order:02d}", "", card.focus.content, ""]
    lines.extend(_proposal_summary(proposal.chosen_judgment))
    lines.extend(("", "Karar: [ ] Doğru  [ ] Düzelt  [ ] Bana ait değil", ""))
    return lines


def _proposal_summary(judgment: PersonaAnnotationJudgment | None) -> list[str]:
    if judgment is None:
        return ["Model önerisi: geçersiz veya iki geçişte tutarsız; doğrulama gerekli."]
    kind = judgment.persona_kind.value if judgment.persona_kind else "yok"
    return [
        "Model önerisi: "
        f"katman={judgment.target_layer.value}, tür={kind}, "
        f"persona dışı={str(judgment.exclude_from_persona).lower()}, "
        f"güven={judgment.confidence.value}."
    ]


def _raw_class(derived: DataClass) -> DataClass:
    return (
        DataClass.PUBLIC_SYNTHETIC
        if derived == DataClass.PUBLIC_SYNTHETIC
        else DataClass.RAW_CORPUS
    )
