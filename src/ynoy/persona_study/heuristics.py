from __future__ import annotations


def challenge_tags(content: str) -> tuple[str, ...]:
    lowered = content.casefold()
    checks = {
        "question": "?" in content,
        "correction": any(
            word in lowered
            for word in ("yanlış", "düzelt", "demek istedi")  # noqa: RUF001
        ),
        "rejection": any(
            word in lowered
            for word in ("istemiyorum", "olmasın", "hayır", "siktir")  # noqa: RUF001
        ),
        "temporary": any(word in lowered for word in ("şimdilik", "sonra", "geçici", "for now")),
        "scope": any(
            word in lowered for word in ("persona", "kişilik", "proje", "sistem", "scope")
        ),
        "quote_risk": "```" in content or "files mentioned" in lowered or "](" in content,
    }
    return tuple(key for key, present in checks.items() if present)


def meaningful_repeat(content: str) -> bool:
    return len(content.strip()) >= 20 and len(content.split()) >= 3


def inert_control_like(content: str) -> bool:
    lowered = content.lstrip().casefold()
    markers = (
        "<codex_internal_context",
        "<environment_context>",
        "# agents.md instructions for",
        "<recommended_plugins>",
    )
    return any(marker in lowered for marker in markers)
