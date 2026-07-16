from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile, ZipInfo

from ynoy.archive import ArchiveLimits, archive_sha256, iter_json_object_array, open_validated_zip
from ynoy.constants import PARSER_VERSION
from ynoy.corpus.synthetic import assert_synthetic_marker
from ynoy.corpus.types import (
    InventoryCounts,
    NormalizationStats,
    as_mapping,
    authority_for_speaker,
    branch_membership,
    claim_holder_for_speaker,
    conversation_files,
    event_time,
    source_event_metadata,
    speaker_from_message,
    text_content,
)
from ynoy.errors import DataValidationError
from ynoy.models import (
    DataClass,
    InventoryEntry,
    InventoryManifest,
    ScopeRef,
    SourceEvent,
    SourceReceipt,
    Speaker,
)
from ynoy.util import canonical_sha256, sha256_text


def _opaque(source_digest: str, namespace: str, raw_value: object) -> str:
    return sha256_text(f"{source_digest}:{namespace}:{raw_value}")


class ChatGPTZipAdapter:
    name = "chatgpt_zip"

    def __init__(self, limits: ArchiveLimits | None = None):
        self.limits = limits or ArchiveLimits()
        self.stats = NormalizationStats()

    def _iter_conversations(self, archive: ZipFile) -> Iterator[dict[str, object]]:
        selected = conversation_files(archive)
        if not selected:
            raise DataValidationError(
                "chatgpt_conversations_missing",
                "No conversations.json export member was found.",
            )
        for info in selected:
            with archive.open(info, mode="r") as stream:
                yield from iter_json_object_array(
                    stream,
                    max_item_bytes=self.limits.max_json_item_bytes,
                    max_nesting=self.limits.max_json_nesting,
                )

    def inventory(self, path: Path, *, synthetic: bool) -> InventoryManifest:
        source = path.expanduser().resolve(strict=True)
        if not source.is_file():
            raise DataValidationError("archive_not_file", "Selected export is not a file.")
        before = source.stat()
        source_digest = archive_sha256(source, self.limits)
        with open_validated_zip(str(source), self.limits) as archive:
            if synthetic:
                assert_synthetic_marker(archive)
            infos = archive.infolist()
            selected = {item.filename for item in conversation_files(archive)}
            if not selected:
                raise DataValidationError(
                    "chatgpt_conversations_missing",
                    "No conversations.json export member was found.",
                )
            entries = _inventory_entries(infos, selected)
            counts = _scan_inventory(self._iter_conversations(archive))
        _assert_source_unchanged(source, before.st_size, before.st_mtime_ns)
        return _build_manifest(
            source.name, source_digest, before.st_size, entries, counts, synthetic
        )

    def iter_events(
        self, path: Path, *, manifest: InventoryManifest, import_run_id: UUID
    ) -> Iterator[SourceEvent]:
        source = path.expanduser().resolve(strict=True)
        if archive_sha256(source, self.limits) != manifest.source_archive_sha256:
            raise DataValidationError(
                "archive_digest_mismatch", "Export no longer matches the approved inventory."
            )
        self.stats = NormalizationStats()
        with open_validated_zip(str(source), self.limits) as archive:
            for conversation in self._iter_conversations(archive):
                yield from _normalize_conversation(
                    conversation, manifest, import_run_id, self.stats
                )

    def build_receipt(
        self,
        *,
        manifest: InventoryManifest,
        import_run_id: UUID,
        normalized_count: int,
    ) -> SourceReceipt:
        if normalized_count != self.stats.normalized:
            raise DataValidationError(
                "normalization_count_mismatch", "Ingestion stream ended with inconsistent counts."
            )
        return SourceReceipt(
            import_run_id=import_run_id,
            source_id=manifest.source_archive_sha256,
            adapter=self.name,
            parser_version=PARSER_VERSION,
            source_archive_sha256=manifest.source_archive_sha256,
            normalized_event_count=normalized_count,
            excluded_event_count=self.stats.excluded,
            speaker_counts=dict(sorted(self.stats.speaker_counts.items())),
            status="complete",
            warnings=tuple(sorted(self.stats.warnings)),
        )


def _inventory_entries(
    infos: list[ZipInfo], selected_names: set[str]
) -> tuple[InventoryEntry, ...]:
    return tuple(
        InventoryEntry(
            name=info.filename,
            compressed_bytes=info.compress_size,
            uncompressed_bytes=info.file_size,
            compression_ratio=(info.file_size / max(info.compress_size, 1))
            if info.file_size
            else 0.0,
            selected_for_parser=info.filename in selected_names,
        )
        for info in infos
    )


def _scan_inventory(conversations: Iterator[dict[str, object]]) -> InventoryCounts:
    conversation_count = message_count = branch_count = malformed = excluded_parts = 0
    speakers: Counter[str] = Counter()
    for conversation in conversations:
        conversation_count += 1
        mapping = conversation.get("mapping")
        if not isinstance(mapping, Mapping):
            malformed += 1
            continue
        memberships = branch_membership(mapping)
        leaves = {leaf for branch_leaves in memberships.values() for leaf in branch_leaves}
        branch_count += max(len(leaves), 1)
        for raw_node in mapping.values():
            message = as_mapping(raw_node).get("message")
            if not isinstance(message, Mapping):
                continue
            message_count += 1
            speakers[speaker_from_message(message).value] += 1
            excluded_parts += text_content(message)[1]
    return InventoryCounts(
        conversation_count,
        message_count,
        branch_count,
        malformed,
        excluded_parts,
        speakers,
    )


def _build_manifest(
    source_name: str,
    source_digest: str,
    source_bytes: int,
    entries: tuple[InventoryEntry, ...],
    counts: InventoryCounts,
    synthetic: bool,
) -> InventoryManifest:
    draft = InventoryManifest(
        parser_version=PARSER_VERSION,
        source_name=source_name,
        source_archive_sha256=source_digest,
        source_bytes=source_bytes,
        entries=entries,
        entry_count=len(entries),
        total_uncompressed_bytes=sum(item.uncompressed_bytes for item in entries),
        conversation_count=counts.conversations,
        message_count=counts.messages,
        branch_count=counts.branches,
        speaker_counts=dict(sorted(counts.speakers.items())),
        malformed_record_count=counts.malformed,
        excluded_content_part_count=counts.excluded_parts,
        warnings=("metadata_only_no_claims_derived",),
        source_data_class=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS),
        synthetic=synthetic,
    )
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"manifest_sha256"}))
    return draft.model_copy(update={"manifest_sha256": digest})


def _assert_source_unchanged(source: Path, size: int, modified_ns: int) -> None:
    after = source.stat()
    if (size, modified_ns) != (after.st_size, after.st_mtime_ns):
        raise DataValidationError(
            "archive_changed_during_inventory",
            "Export changed while inventory was running; retry with a stable file.",
        )


def _conversation_raw_id(conversation: Mapping[str, object], stats: NormalizationStats) -> object:
    raw_id = conversation.get("id") or conversation.get("conversation_id")
    if raw_id is not None:
        return raw_id
    mapping_keys = sorted(str(key) for key in as_mapping(conversation.get("mapping")))
    stats.warnings.add("conversation_id_missing")
    return canonical_sha256({"mapping_keys": mapping_keys})


def _normalize_conversation(
    conversation: Mapping[str, object],
    manifest: InventoryManifest,
    import_run_id: UUID,
    stats: NormalizationStats,
) -> Iterator[SourceEvent]:
    raw_conversation_id = _conversation_raw_id(conversation, stats)
    mapping = as_mapping(conversation.get("mapping"))
    if not mapping:
        stats.excluded += 1
        return
    memberships = branch_membership(mapping)
    conversation_id = _opaque(manifest.source_archive_sha256, "conversation", raw_conversation_id)
    origin_id = _opaque(manifest.source_archive_sha256, "origin_cluster", raw_conversation_id)
    for raw_node_id, raw_node in mapping.items():
        event = _normalize_node(
            raw_node_id,
            as_mapping(raw_node),
            memberships,
            conversation_id,
            origin_id,
            manifest,
            import_run_id,
            stats,
        )
        if event is not None:
            stats.normalized += 1
            yield event


def _normalize_node(
    raw_node_id: object,
    node: Mapping[str, object],
    memberships: Mapping[str, tuple[str, ...]],
    conversation_id: str,
    origin_id: str,
    manifest: InventoryManifest,
    import_run_id: UUID,
    stats: NormalizationStats,
) -> SourceEvent | None:
    message = node.get("message")
    if not isinstance(message, Mapping):
        return None
    content, excluded = text_content(message)
    stats.excluded += excluded
    if not content:
        stats.excluded += 1
        return None
    speaker = speaker_from_message(message)
    stats.speaker_counts[speaker.value] += 1
    if speaker == Speaker.USER:
        stats.warnings.add("user_turn_claims_require_span_attribution")
    digest = manifest.source_archive_sha256
    event_id = _opaque(digest, "event", raw_node_id)
    parent = node.get("parent")
    leaves = memberships.get(str(raw_node_id), (str(raw_node_id),))
    return SourceEvent(
        import_run_id=import_run_id,
        source_id=digest,
        source_locator=f"chatgpt://{conversation_id}/{event_id}",
        conversation_id=conversation_id,
        branch_id=_opaque(digest, "branch_set", "|".join(leaves)),
        event_id=event_id,
        parent_event_id=_opaque(digest, "event", parent) if parent is not None else None,
        speaker=speaker,
        claim_holder=claim_holder_for_speaker(speaker),
        source_authority=authority_for_speaker(speaker),
        data_class=DataClass.PUBLIC_SYNTHETIC if manifest.synthetic else DataClass.RAW_CORPUS,
        event_time=event_time(message),
        content=content,
        content_sha256=sha256_text(content),
        origin_cluster_id=origin_id,
        scope=ScopeRef(person_id="self"),
        metadata=source_event_metadata(message, len(leaves), speaker),
    )
