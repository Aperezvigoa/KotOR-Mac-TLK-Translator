"""UTW (waypoint) generic: GFF-based waypoint definitions and map notes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.common.language import LocalizedString
from pykotor.common.misc import Game, ResRef
from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff, read_gff, write_gff
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.resource.formats.gff import GFFStruct
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class UTW:
    """Stores waypoint data.

    UTW files are GFF-based format files that store waypoint definitions including
    map notes, appearance, and location data.

    Waypoint templates are GFF files with tag, ``TemplateResRef``, localized name, map-note flags
    and text, appearance/palette/comment for the toolset, and optional deprecated linkage/description
    fields. World position and orientation for placed waypoints come from the GIT instance, not
    only the UTW root. Observed retail KotOR I and TSL match this pattern. Loader symbols and RVAs
    are in ``wiki/reverse_engineering_findings.md``.

    Note: ``GFFContent.UTW``.

    Attributes:
    ----------
        resref: "TemplateResRef" field. The resource reference for this waypoint template.

        tag: "Tag" field. Tag identifier for this waypoint.

        name: "LocalizedName" field. Localized name of the waypoint.

        has_map_note: "HasMapNote" field. Whether waypoint has a map note.

        map_note: "MapNote" field. Localized map note text.

        map_note_enabled: "MapNoteEnabled" field. Whether map note is enabled.

        appearance_id: "Appearance" field. Appearance type identifier. Used in toolset only.

        palette_id: "PaletteID" field. Palette identifier. Used in toolset only.

        comment: "Comment" field. Developer comment. Used in toolset only.

        linked_to: "LinkedTo" field. Linked waypoint tag. Not used by the game engine.

        description: "Description" field. Localized description. Not used by the game engine.
    """

    BINARY_TYPE = ResourceType.UTW

    def __init__(self):
        self.resref: ResRef = ResRef.from_blank()
        self.comment: str = ""
        self.tag: str = ""

        self.name: LocalizedString = LocalizedString.from_invalid()

        self.has_map_note: bool = False
        self.map_note_enabled: bool = False
        self.map_note: LocalizedString = LocalizedString.from_invalid()

        self.appearance_id: int = 0
        self.palette_id: int = 0

        # Deprecated:
        self.linked_to: str = ""
        self.description: LocalizedString = LocalizedString.from_invalid()


def construct_utw(
    gff: GFF,
) -> UTW:
    """Constructs a UTW object from a GFF structure.

    Missing fields use blank tag/ResRef, empty localized strings, and false map-note flags (observed
    retail). Instance transforms live on the GIT entry.
    """
    utw = UTW()

    root: GFFStruct = gff.root
    utw.appearance_id = root.acquire("Appearance", 0)
    utw.linked_to = root.acquire("LinkedTo", "")
    utw.resref = root.acquire("TemplateResRef", ResRef.from_blank())
    utw.tag = root.acquire("Tag", "")
    utw.name = root.acquire("LocalizedName", LocalizedString.from_invalid())
    utw.description = root.acquire("Description", LocalizedString.from_invalid())
    # Map note: HasMapNote, MapNote, MapNoteEnabled.
    utw.has_map_note = bool(root.acquire("HasMapNote", 0))
    utw.map_note = root.acquire("MapNote", LocalizedString.from_invalid())
    utw.map_note_enabled = bool(root.acquire("MapNoteEnabled", 0))
    utw.palette_id = root.acquire("PaletteID", 0)
    utw.comment = root.acquire("Comment", "")

    return utw


def dismantle_utw(
    utw: UTW,
    game: Game = Game.K2,  # noqa: ARG001
    *,
    use_deprecated: bool = True,  # noqa: ARG001
) -> GFF:
    """Dismantles a UTW object into a GFF structure (round-trip with :func:`construct_utw`)."""
    gff = GFF(GFFContent.UTW)

    root: GFFStruct = gff.root
    root.set_uint8("Appearance", utw.appearance_id)
    # LinkedTo: GFF string; toolset-only. Default "". Omit OK for engine.
    root.set_string("LinkedTo", utw.linked_to)
    # TemplateResRef: CResRef; template ref. Default blank. Omit OK.
    root.set_resref("TemplateResRef", utw.resref)
    root.set_string("Tag", utw.tag)
    root.set_locstring("LocalizedName", utw.name)
    # Description: GFF LocalizedString; toolset-only. Default empty. Omit OK.
    root.set_locstring("Description", utw.description)
    root.set_uint8("HasMapNote", utw.has_map_note)
    root.set_locstring("MapNote", utw.map_note)
    root.set_uint8("MapNoteEnabled", utw.map_note_enabled)
    # PaletteID: BYTE; toolset-only. Default 0. Omit OK.
    root.set_uint8("PaletteID", utw.palette_id)
    # Comment: GFF string; toolset-only. Default "". Omit OK.
    root.set_string("Comment", utw.comment)

    return gff


def read_utw(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
) -> UTW:
    gff: GFF = read_gff(source, offset, size)
    return construct_utw(gff)


def write_utw(
    utw: UTW,
    target: TARGET_TYPES,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
):
    gff: GFF = dismantle_utw(utw, game, use_deprecated=use_deprecated)
    write_gff(gff, target, file_format)


def bytes_utw(
    utw: UTW,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> bytes:
    gff: GFF = dismantle_utw(utw, game, use_deprecated=use_deprecated)
    return bytes_gff(gff, file_format)
