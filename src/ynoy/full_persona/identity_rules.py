# ruff: noqa: RUF001 -- Turkish identity vocabulary is intentional.

from __future__ import annotations

import re
from typing import Literal

type LifeTopic = Literal["birth", "childhood", "education", "exams", "current_life"]

LIFE_TOPIC_ORDER: tuple[LifeTopic, ...] = (
    "birth",
    "childhood",
    "education",
    "exams",
    "current_life",
)

_IMPORTED_PREFIXES = (
    "# context from my ide setup:",
    "# files mentioned by the user:",
    "please implement this plan:",
)
_BIRTH = re.compile(
    r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+(?:tarihinde\s+)?doğdum|"
    r"\d{4}\s+doğumluyum|doğum\s+günüm\s+\d{1,4}[./-]\d{1,2}[./-]\d{1,4}|"
    r"doğum\s+(?:yerim|tarihim)\b)",
    re.I,
)
_CHILDHOOD = re.compile(
    r"\b(?:(?:çocukken|küçükken).{0,100}(?:büyüdüm|yaşadım)|"
    r"çocukluğum\w*(?:\s+[^.!?\n]{1,100})?|büyürken\b)",
    re.I,
)
_EDUCATION = re.compile(
    r"\b(?:okul|lise|üniversite|fakülte|bölüm)\w*.{0,100}"
    r"(?:okudum|bitirdim|mezun\w*|öğrenciyim|öğrenciydim)|"
    r"(?:okudum|bitirdim|mezun\w*)\w*.{0,100}"
    r"(?:okul|lise|üniversite|fakülte|bölüm)\w*\b",
    re.I,
)
_EXAMS = re.compile(
    r"\b(?:sınav\w*|yks|öss|kpss|ales|toefl|ielts|gre|sat)\b.{0,100}"
    r"\b(?:girdim(?:\s+ve\s+(?:puan\w*|sonucum)\s+[^.!?\n]{1,80})?|"
    r"kazandım|geçtim|kaldım|puan\w*(?:\s+[^.!?\n]{1,80})?|"
    r"sonucum(?:\s+[^.!?\n]{1,80})?)\b|"
    r"\b(?:girdim|kazandım|geçtim|kaldım|puan\w*|sonucum)\b.{0,100}"
    r"\b(?:sınav\w*|yks|öss|kpss|ales|toefl|ielts|gre|sat)\b",
    re.I,
)
_CURRENT_LIFE = re.compile(
    r"\b(?:\d{1,3}\s+yaşındayım|kendi\s+şirketim\s+var|gezerek\s+çalışıyorum|"
    r"mesleğim\s+[^.!?\n]{2,80}|[^.!?\n]{2,50}(?:'?[dt][ae])\s+yaşıyorum)\b",
    re.I,
)
_RELATIONSHIP = re.compile(
    r"\b(?:annem(?:le)?|babam(?:la)?|kardeşim(?:le)?|eşim(?:le)?|sevgilim(?:le)?|"
    r"ailem(?:le)?|arkadaşımla|bir\s+arkadaşım(?:la|\s+ile)|benim\s+(?:oğlum|kızım)|"
    r"(?:oğlum|kızım)\s+var)\b",
    re.I,
)
_SKILL = re.compile(
    r"\b(?:uzmanım|hakimim|yetkinim|yıllardır(?:\s+[^.!?\n]{1,80})?\s+kullanıyorum|"
    r"profesyonel\s+olarak\s+[^.!?\n]{1,80}\s+yapıyorum)\b",
    re.I,
)
_VALUE = re.compile(
    r"\b(?:önemsiyorum|değer\s+veriyorum|inanıyorum|benim\s+için\s+önemli|"
    r"vazgeçilmez|asla\s+kabul\s+etmem)\b",
    re.I,
)


def is_imported_identity_text(value: str) -> bool:
    lowered = value.lstrip().casefold()
    return any(lowered.startswith(prefix) for prefix in _IMPORTED_PREFIXES)


def life_topics(value: str) -> tuple[LifeTopic, ...]:
    return tuple(dict.fromkeys(topic for topic, _fact in life_facts(value)))


def life_facts(value: str) -> tuple[tuple[LifeTopic, str], ...]:
    patterns: tuple[tuple[LifeTopic, re.Pattern[str]], ...] = (
        ("birth", _BIRTH),
        ("childhood", _CHILDHOOD),
        ("education", _EDUCATION),
        ("exams", _EXAMS),
        ("current_life", _CURRENT_LIFE),
    )
    result: list[tuple[LifeTopic, str]] = []
    seen: set[tuple[LifeTopic, str]] = set()
    for topic, pattern in patterns:
        for match in pattern.finditer(value):
            fact = " ".join(match.group(0).strip().split())
            key = (topic, fact.casefold())
            if fact and key not in seen:
                result.append((topic, fact))
                seen.add(key)
    return tuple(result)


def has_biography_claim(value: str) -> bool:
    return bool(life_topics(value))


def is_biography_query(value: str) -> bool:
    terms = (
        "biyografi",
        "çocuklu",
        "doğum",
        "eğitim",
        "hakkımda",
        "hayatım",
        "okul",
        "sınav",
        "yaşamım",
    )
    normalized = value.casefold()
    return any(term in normalized for term in terms)


def has_relationship_claim(value: str) -> bool:
    return _RELATIONSHIP.search(value) is not None


def has_skill_claim(value: str) -> bool:
    return _SKILL.search(value) is not None


def has_value_claim(value: str) -> bool:
    return _VALUE.search(value) is not None
