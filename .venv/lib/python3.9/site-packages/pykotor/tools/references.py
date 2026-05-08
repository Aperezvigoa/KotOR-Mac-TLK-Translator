"""High-level reference extraction and referrer search using reference_config.

Provides extract_references (from a single resource) and find_referrers (across
an installation) for scripts, conversations, tags, and template resrefs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykotor.resource.formats.gff.gff_data import GFFFieldType, GFFList, GFFStruct
from pykotor.tools.reference_config import (
    DLG_SCRIPT_PATHS,
    get_conversation_fields_for_type,
    get_script_fields_for_type,
    get_tag_fields_for_type,
    get_template_resref_fields_for_type,
)
from pykotor.tools.reference_finder import (
    ReferenceSearchResult,
    find_conversation_references,
    find_resref_references,
    find_script_references,
    find_tag_references,
)

if TYPE_CHECKING:
    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.gff import GFF


@dataclass(frozen=True)
class ExtractedReference:
    """A single reference extracted from a GFF (script, conversation, tag, template_resref)."""

    ref_kind: str
    value: str
    field_path: str


def _value_to_str(value: Any) -> str:
    """Normalize GFF field value to string for ResRef/String."""
    if value is None or value == "":
        return ""
    if hasattr(value, "get") and callable(getattr(value, "get", None)):
        return str(value.get()) if value.get() else ""
    return str(value).strip()


def _collect_from_struct(
    struct: GFFStruct,
    path_prefix: str,
    file_type: str,
    script_fields: set[str],
    tag_fields: set[str],
    template_fields: set[str],
    conversation_fields: set[str],
    out: list[ExtractedReference],
) -> None:
    """Walk a GFF struct and append ExtractedReference for configured fields."""
    for label, field_type, value in struct:
        if value is None:
            continue
        field_path = f"{path_prefix}.{label}" if path_prefix else label

        if field_type == GFFFieldType.ResRef:
            s = _value_to_str(value)
            if s:
                if label in script_fields:
                    out.append(ExtractedReference("script", s, field_path))
                if label in template_fields:
                    out.append(ExtractedReference("template_resref", s, field_path))
                if label in conversation_fields:
                    out.append(ExtractedReference("conversation", s, field_path))
        elif field_type == GFFFieldType.String:
            s = _value_to_str(value)
            if s and label in tag_fields:
                out.append(ExtractedReference("tag", s, field_path))
        elif field_type == GFFFieldType.Struct and isinstance(value, GFFStruct):
            _collect_from_struct(
                value,
                field_path,
                file_type,
                script_fields,
                tag_fields,
                template_fields,
                conversation_fields,
                out,
            )
        elif field_type == GFFFieldType.List and isinstance(value, GFFList):
            for idx, item in enumerate(value):
                if isinstance(item, GFFStruct):
                    list_path = f"{field_path}[{idx}]"
                    _collect_from_struct(
                        item,
                        list_path,
                        file_type,
                        script_fields,
                        tag_fields,
                        template_fields,
                        conversation_fields,
                        out,
                    )


def extract_references(
    gff: GFF,
    file_type: str,
) -> list[ExtractedReference]:
    """Extract all script, conversation, tag, and template_resref references from a GFF.

    Uses pykotor.tools.reference_config for field maps. DLG nested lists (StartingList,
    EntryList, ReplyList) are walked so script/condition refs inside entries/replies
    are included.

    Args:
    ----
        gff: Loaded GFF (e.g. from read_gff(resource.data()))
        file_type: Uppercase extension (e.g. "UTC", "DLG", "ARE")

    Returns:
    -------
        List of ExtractedReference (ref_kind, value, field_path)
    """
    script_fields = get_script_fields_for_type(file_type)
    tag_fields = get_tag_fields_for_type(file_type)
    template_fields = get_template_resref_fields_for_type(file_type)
    conversation_fields = get_conversation_fields_for_type(file_type)

    out: list[ExtractedReference] = []
    _collect_from_struct(
        gff.root,
        "",
        file_type,
        script_fields,
        tag_fields,
        template_fields,
        conversation_fields,
        out,
    )

    # DLG: also walk nested paths from DLG_SCRIPT_PATHS (e.g. EntryList[].RepliesList[].Active)
    if file_type == "DLG":
        for list_field, script_field in DLG_SCRIPT_PATHS:
            if list_field not in gff.root:
                continue
            list_val = gff.root[list_field]
            if not isinstance(list_val, GFFList):
                continue
            for idx, item in enumerate(list_val):
                if isinstance(item, GFFStruct) and script_field in item:
                    val = item[script_field]
                    s = _value_to_str(val)
                    if s:
                        out.append(
                            ExtractedReference(
                                "script",
                                s,
                                f"{list_field}[{idx}].{script_field}",
                            ),
                        )

    return out


def find_referrers(
    installation: Installation,
    value: str,
    *,
    reference_kind: str = "resref",
    module_root: str | None = None,
    partial_match: bool = False,
    case_sensitive: bool = False,
    file_pattern: str | None = None,
    file_types: set[str] | None = None,
) -> list[ReferenceSearchResult]:
    """Find resources that reference the given value (script, tag, conversation, or resref).

    Uses reference_finder and optionally filters by module_root (e.g. "danm13" to limit
    to that module's RIMs). locations filter is not yet supported (installation iterator
    does not expose source location).

    Args:
    ----
        installation: Installation to search
        value: Script resref, tag, conversation resref, or generic resref
        reference_kind: "script" | "tag" | "conversation" | "resref"
        module_root: If set, only include results whose resource path contains this (e.g. module name)
        partial_match: Allow partial matches
        case_sensitive: Case-sensitive match
        file_pattern: Optional glob pattern for resource filenames
        file_types: Optional set of file type abbreviations

    Returns:
    -------
        List of ReferenceSearchResult; may be filtered by module_root
    """
    if reference_kind == "script":
        results = find_script_references(
            installation,
            value,
            partial_match=partial_match,
            case_sensitive=case_sensitive,
            file_pattern=file_pattern,
            file_types=file_types,
        )
    elif reference_kind == "tag":
        results = find_tag_references(
            installation,
            value,
            partial_match=partial_match,
            case_sensitive=case_sensitive,
            file_pattern=file_pattern,
            file_types=file_types,
        )
    elif reference_kind == "conversation":
        results = find_conversation_references(
            installation,
            value,
            partial_match=partial_match,
            case_sensitive=case_sensitive,
            file_pattern=file_pattern,
            file_types=file_types,
        )
    else:
        results = find_resref_references(
            installation,
            value,
            partial_match=partial_match,
            case_sensitive=case_sensitive,
            file_pattern=file_pattern,
            file_types=file_types,
        )

    if not module_root:
        return results

    key = module_root.lower()
    return [r for r in results if key in str(r.file_resource.filepath()).lower()]
