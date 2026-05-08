"""This module handles classes relating to working with TLK files.

Talk Table (TLK) files contain all text strings used in the game, both written and spoken.
They enable easy localization by providing a lookup table from string reference numbers (StrRef)
to localized text and associated voice-over audio files.

Observed retail behavior:
----------
    KotOR I and TSL ship a primary ``dialog.tlk`` (plus optional companion files in some builds).
    The games resolve in-game text and VO hooks through StrRefs that index rows in the binary
    table layout below. It has been observed that the default table uses the ``TLK `` magic,
    ``V3.0`` version for KotOR-era titles, and the on-disk row layout described here.

Binary Format:
-------------
    Header (20 bytes):
    - 4 bytes: File Type ("TLK ")
    - 4 bytes: File Version ("V3.0" for KotOR, "V4.0" for Jade Empire)
    - 4 bytes: Language ID (int32)
    - 4 bytes: String Count (int32)
    - 4 bytes: String Entries Offset (int32)
    String Data Table (40 bytes per entry):
    - 4 bytes: Flags (bit 0=text present, bit 1=sound present, bit 2=sound length present)
    - 16 bytes: Sound ResRef (null-terminated ASCII, max 16 chars)
    - 4 bytes: Volume Variance (unused in KotOR)
    - 4 bytes: Pitch Variance (unused in KotOR)
    - 4 bytes: Offset to String (from String Entries Offset)
    - 4 bytes: String Size (length in bytes)
    - 4 bytes: Sound Length (float, seconds)
    String Entries:
    - Variable length null-terminated strings
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from pykotor.common.language import Language
from pykotor.common.misc import ResRef
from pykotor.resource.formats._base import BiowareResource, ComparableMixin
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from typing import Any


class TLK(BiowareResource):
    """Talk Table containing localized strings and voice-over references.

    The TLK file is the central localization mechanism for KotOR, mapping string reference
    numbers (StrRef) to localized text and optional voice-over audio files. The game loads
    dialog.tlk at startup and references strings throughout the game using StrRef numbers.

    On-disk layout (KotOR ``V3.0`` talk tables): file type ``TLK `` at offset 0, version
    ``V3.0`` at 4, language id at 8, string count at 0x0C, string-entry base offset at 0x10,
    then the 40-byte fixed records followed by pooled string bytes.

    Attributes:
    ----------
        entries: List of TLKEntry objects indexed by StrRef

        language: Language identifier for this talk table
            NOTE: Game itself ignores this field in KotOR, always uses dialog.tlk
            Used primarily for modding tools to identify language
    """

    BINARY_TYPE = ResourceType.TLK
    COMPARABLE_FIELDS = ("language",)
    COMPARABLE_SEQUENCE_FIELDS = ("entries",)

    def __init__(
        self,
        language: Language = Language.ENGLISH,
    ):
        # List of string entries indexed by StrRef (0-based array index)
        self.entries: list[TLKEntry] = []

        # Language ID field - unused by game but present in file format
        self.language: Language = language  # game does not use this field

    def __len__(self) -> int:
        """Returns the number of stored entries."""
        return len(self.entries)

    def __iter__(self):
        """Iterates through the stored entry with each iteration yielding a stringref and the corresponding entry data."""
        yield from enumerate(self.entries)

    def __json__(self) -> dict[str, list[dict[str, str]]]:
        """Serialize the TLK object to a JSON-compatible dictionary."""
        json_data: dict[str, list[dict[str, str]]] = {"strings": []}
        for stringref, entry in self:
            json_data["strings"].append(
                {
                    "_index": str(stringref),
                    "text": entry.text,
                    "soundResRef": str(entry.voiceover),
                }
            )
        return json_data

    @classmethod
    def from_json(cls, data: dict) -> TLK:
        """Hydrate a TLK object from a JSON dictionary."""
        instance = cls()

        strings = data.get("strings", [])
        if strings:
            instance.resize(max(int(s.get("_index", 0)) for s in strings) + 1)

        for string_data in strings:
            index = int(string_data["_index"])
            instance.entries[index].text = string_data["text"]
            instance.entries[index].voiceover = ResRef(string_data["soundResRef"])

        return instance

    def __getitem__(
        self,
        item,
    ):
        """Returns an entry for the specified stringref.

        Args:
        ----
            item: The stringref.

        Raises:
        ------
            IndexError: If the stringref does not exist.

        Returns:
        -------
            The corresponding TLKEntry.
        """
        return self.entries[item] if isinstance(item, int) else NotImplemented

    def get(
        self,
        stringref: int,
    ) -> TLKEntry | None:
        """Returns an entry for the specified stringref if it exists, otherwise returns None.

        Args:
        ----
            stringref: The stringref.

        Returns:
        -------
            The corresponding TLKEntry or None.
        """
        return self.entries[stringref] if 0 <= stringref < len(self) else None

    def add(
        self,
        text: str,
        sound_resref: str = "",
    ) -> int:
        entry = TLKEntry(text, ResRef(sound_resref))
        self.entries.append(entry)
        return len(self.entries) - 1

    def replace(self, stringref: int, text: str, sound_resref: str = ""):
        """Replaces an entry at the specified stringref with the provided text and sound resref.

        Args:
        ----
            stringref: The stringref of the entry to be replaced.
            text: The new text for the entry.
            sound_resref: The new sound resref for the entry.
        """
        if not 0 <= stringref < len(self.entries):
            msg = f"Cannot replace nonexistent stringref in dialog.tlk: '{stringref}'"
            raise IndexError(msg)
        old_text: str = self.entries[stringref].text
        old_sound: ResRef = self.entries[stringref].voiceover
        self.entries[stringref] = TLKEntry(
            text or old_text, ResRef(sound_resref) if sound_resref else old_sound
        )

    def resize(
        self,
        size: int,
    ):
        """Resizes the number of entries to the specified size.

        Args:
        ----
            size: The new number of entries.
        """
        if len(self) > size:
            self.entries = self.entries[:size]
        else:
            self.entries.extend([TLKEntry("", ResRef.from_blank()) for _ in range(len(self), size)])

    def compare(self, other: object, log_func: Callable[[str], Any] = print) -> bool:  # noqa: C901, PLR0912, PLR0915
        """Smart TLK comparison that detects insertions/deletions and shows meaningful diffs.

        Args:
        ----
            other: The other TLK to compare against
            log_func: Function to call with comparison output messages

        Returns:
        -------
            True if TLKs are identical, False otherwise
        """
        if not isinstance(other, TLK):
            log_func(
                f"Type mismatch: 'TLK' vs '{other.__class__.__name__ if isinstance(other, object) else type(other)}'"
            )
            return False

        # Build content-based lookup to detect moved/reordered entries
        def entry_key(entry: TLKEntry) -> tuple[str, str]:
            """Create a hashable key for an entry."""
            return (entry.text, str(entry.voiceover))

        # Build maps of content to indices
        entries1_map: dict[tuple[str, str], list[int]] = {}  # content -> list of indices
        entries2_map: dict[tuple[str, str], list[int]] = {}  # content -> list of indices

        for idx, entry in enumerate(self.entries):
            key = entry_key(entry)
            if key not in entries1_map:
                entries1_map[key] = []
            entries1_map[key].append(idx)

        for idx, entry in enumerate(other.entries):
            key = entry_key(entry)
            if key not in entries2_map:
                entries2_map[key] = []
            entries2_map[key].append(idx)

        # Find entries that exist in both (at any index)
        added_keys = set(entries2_map.keys()) - set(entries1_map.keys())
        removed_keys = set(entries1_map.keys()) - set(entries2_map.keys())

        # Track which entries we've reported
        reported_indices1: set[int] = set()
        reported_indices2: set[int] = set()

        # Report size difference
        len1 = len(self.entries)
        len2 = len(other.entries)

        if len1 != len2:
            log_func(
                f"TLK size mismatch: Old has {len1} entries, New has {len2} entries (diff: {len2 - len1:+d})"
            )

        # Report added entries (in new file only)
        if added_keys:
            log_func(f"\n{len(added_keys)} entries added in new TLK:")
            for key in sorted(added_keys):
                indices = entries2_map[key]
                for idx in indices:
                    entry = other.entries[idx]
                    log_func(f"  [New:{idx}] {entry}")
                    reported_indices2.add(idx)

        # Report removed entries (in old file only)
        if removed_keys:
            log_func(f"\n{len(removed_keys)} entries removed from old TLK:")
            for key in sorted(removed_keys):
                indices = entries1_map[key]
                for idx in indices:
                    entry = self.entries[idx]
                    log_func(f"  [Old:{idx}] {entry}")
                    reported_indices1.add(idx)

        # Check for entries at same index that have different content
        modified_count = 0
        max_index = min(len1, len2)
        for idx in range(max_index):
            if idx in reported_indices1 or idx in reported_indices2:
                continue
            entry1 = self.entries[idx]
            entry2 = other.entries[idx]

            if entry1 != entry2:
                # This is a genuine content change at the same index
                if modified_count == 0:
                    log_func("\nEntries modified at same index:")
                modified_count += 1
                log_func(f"  [{idx}] Old: {entry1}")
                log_func(f"  [{idx}] New: {entry2}")
                reported_indices1.add(idx)
                reported_indices2.add(idx)

        # Summary
        has_differences = bool(added_keys or removed_keys or modified_count)

        if has_differences:
            log_func(
                f"\nTLK Summary: {len(added_keys)} added, {len(removed_keys)} removed, {modified_count} modified"
            )

        return not has_differences


class TLKEntry(ComparableMixin):
    """A single string entry in a Talk Table.

    Each entry represents one localized string that can be referenced by its StrRef (array index).
    Entries contain the text content and an optional reference to a voice-over audio file.

    Binary Format (40 bytes):
    ------------------------
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 4    | uint32 | Flags (bit 0=text, bit 1=sound, bit 2=sound length)
        0x04   | 16   | char[] | Sound ResRef (null-terminated, max 16 chars)
        0x14   | 4    | uint32 | Volume Variance (unused in KotOR)
        0x18   | 4    | uint32 | Pitch Variance (unused in KotOR)
        0x1C   | 4    | int32  | Offset to String (from String Entries Offset)
        0x20   | 4    | int32  | String Size (length in bytes)
        0x24   | 4    | float  | Sound Length (seconds)

    Attributes:
    ----------
        text: The localized text string
            Encoding: ASCII for English, language-specific for others
            Can contain special tokens like <CUSTOM0>, <FullName>, etc.

        voiceover: Reference to voice-over WAV file (ResRef)
            Max 16 characters, stored as null-terminated string in binary
            If empty/blank, no voice-over is associated with this entry
            Game looks for WAV files in StreamVoice/ or StreamWaves/ folders

        sound_length: Duration of voice-over audio in seconds
            NOTE: Unused by KotOR game engine, but present in file format
    """

    COMPARABLE_FIELDS = ("text", "voiceover")

    def __init__(
        self,
        text: str,
        voiceover: ResRef,
    ):
        # Localized text string (encoding depends on language)
        self.text: str = text

        # Voice-over WAV file reference (max 16 chars)
        self.voiceover: ResRef = voiceover

        # Duration of voice-over in seconds (unused by game, but present in format)
        self.sound_length: int = 0  # This remains a regular attribute

    # The following fields exist in TLK format, but do not perform any function in KOTOR. The game ignores these.
    # entry flags. These are set in both game's TLKs
    @property
    def text_present(self) -> bool:
        """Always True; present for compatibility (TLK field)."""
        return True

    @text_present.setter
    def text_present(self, value: bool):
        self._text_present = value

    @property
    def sound_present(self) -> bool:
        """Always True; present for compatibility (TLK field)."""
        return True

    @sound_present.setter
    def sound_present(self, value: bool):
        self._sound_present = value

    @property
    def soundlength_present(self) -> bool:
        """Always True; present for compatibility (TLK field)."""
        return True

    @soundlength_present.setter
    def soundlength_present(self, value: bool):
        self._soundlength_present = value

    def __eq__(self, other: object):
        """Returns True if the text and voiceover match."""
        if self is other:
            return True
        if not isinstance(other, TLKEntry):
            return NotImplemented  # type: ignore[no-any-return]
        return other.text == self.text and other.voiceover == self.voiceover

    def __hash__(self) -> int:
        """Returns a hash of the TLKEntry."""
        return hash((self.text, self.voiceover))

    def __repr__(self) -> str:
        """Returns a string representation of the TLKEntry."""
        max_repr_length = 50
        text_preview = (
            self.text[:max_repr_length] + "..." if len(self.text) > max_repr_length else self.text
        )
        text_preview = text_preview.replace("\n", "\\n").replace("\r", "\\r")
        return f"TLKEntry(text={text_preview!r}, voiceover={self.voiceover!r})"

    def __str__(self) -> str:
        """Returns a human-readable string representation of the TLKEntry."""
        return f"text: {self.text}, voiceover: {self.voiceover!r}"

    @property
    def text_length(self) -> int:
        return len(self.text)

    @text_length.setter
    def text_length(self, value: int):
        self._text_length = value
