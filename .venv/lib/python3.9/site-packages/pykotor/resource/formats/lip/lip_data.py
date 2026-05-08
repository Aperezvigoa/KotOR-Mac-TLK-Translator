"""This module handles classes relating to editing LIP files.

LIP (Lip Sync) files contain animation data for synchronizing character mouth movements
with voice-over audio. Each LIP file contains a series of keyframes that specify mouth
shapes (visemes) at specific timestamps, allowing the game engine to animate character
lips during dialogue playback.

Observed retail behavior:
----------
    KotOR streams ``LIP `` / ``V1.0`` lip-sync blobs keyed to VO lines: a float duration,
    a keyframe count, then repeating ``(timestamp, viseme id)`` pairs as in the binary layout
    below. It has been observed that retail builds load these through the same resource pipeline
    as other table data.

    Third-party GitHub URL lines removed from this module are archived at
    ``wiki/reverse_engineering_findings_lip_data_github_urls_pre_scrub.md``.

    Binary Format:
    ------------
    Header (16 bytes):
    Offset | Size | Type   | Description
    -------|------|--------|-------------
    0x00   | 4    | char[] | File Type ("LIP ")
    0x04   | 4    | char[] | File Version ("V1.0")
    0x08   | 4    | float  | Sound Length (duration in seconds)
    0x0C   | 4    | uint32 | Entry Count (number of keyframes)
    Keyframe Entry (5 bytes each):
    Offset | Size | Type   | Description
    -------|------|--------|-------------
    0x00   | 4    | float  | Time Stamp (seconds from start)
    0x04   | 1    | uint8  | Shape (mouth shape index, 0-15)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from pykotor.resource.formats._base import BiowareResource, ComparableMixin
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from collections.abc import Iterator


class LIPShape(IntEnum):
    """Represents different mouth shapes (visemes) for lip sync animation.

    These shapes correspond to visual phonemes used in lip-sync animation. Each shape
    represents a specific mouth position for speech sounds, based on the Preston Blair
    phoneme series adapted for KotOR's animation system. The game engine interpolates
    between shapes to create smooth lip movement during dialogue.

        Binary Format:
        -------------
        Stored as uint8 (single byte) in keyframe entries
        Valid range: 0-15 (16 possible shapes)
        Shape 0 is typically NEUTRAL/rest position
        Shape Definitions:
        -----------------
        NEUTRAL = 0: Neutral/rest position (used for pauses)

            Default shape when no speech is occurring

        EE = 1: Teeth slightly apart, corners wide (as in "see", "teeth")
            Used for long 'e' sounds

        EH = 2: Mouth relaxed, slightly open (as in "get", "bet", "red")
            Used for short 'e' sounds

        AH = 3: Mouth open (as in "father", "bat", "cat")
            Used for 'a' sounds

        OH = 4: Rounded lips (as in "go", "boat", "or")
            Used for 'o' sounds

        OOH = 5: Pursed lips (as in "too", "blue", "wheel")
            Used for 'u' and 'w' sounds

        Y = 6: Slight smile (as in "yes", "you")
            Used for 'y' sounds

        STS = 7: Teeth together (as in "stop", "sick", "nets")
            Used for 's', 'z', 'ts' sounds

        FV = 8: Lower lip touching upper teeth (as in "five", "fish", "very")
            Used for 'f' and 'v' sounds

        NG = 9: Back of tongue up (as in "ring", "nacho", "running")
            Used for 'n' and 'ng' sounds

        TH = 10: Tongue between teeth (as in "thin", "think", "that")
            Used for 'th' sounds

        MPB = 11: Lips pressed together (as in "bump", "moose", "pop", "book")
            Used for 'm', 'p', 'b' sounds

        TD = 12: Tongue up (as in "top", "table", "door")
            Used for 't' and 'd' sounds

        SH = 13: Rounded but relaxed (as in "measure", "cheese", "jee")
            Used for 'sh', 'ch', 'j', 'zh' sounds

        L = 14: Tongue forward (as in "lip", "read")
            Used for 'l' and 'r' sounds

        KG = 15: Back of tongue raised (as in "kick", "green", "key", "he")
            Used for 'k', 'g', 'h' sounds
    """

    NEUTRAL = 0  # Neutral/rest position (used for pauses)
    EE = 1  # Teeth slightly apart, corners wide (as in "see")
    EH = 2  # Mouth relaxed, slightly open (as in "get")
    AH = 3  # Mouth open (as in "father")
    OH = 4  # Rounded lips (as in "go")
    OOH = 5  # Pursed lips (as in "too")
    Y = 6  # Slight smile (as in "yes")
    STS = 7  # Teeth together (as in "stop")
    FV = 8  # Lower lip touching upper teeth (as in "five")
    NG = 9  # Back of tongue up (as in "ring")
    TH = 10  # Tongue between teeth (as in "thin")
    MPB = 11  # Lips pressed together (as in "bump")
    TD = 12  # Tongue up (as in "top")
    SH = 13  # Rounded but relaxed (as in "measure")
    L = 14  # Tongue forward (as in "lip")
    KG = 15  # Back of tongue raised (as in "kick")

    @classmethod
    def from_phoneme(cls, phoneme: str) -> LIPShape:
        """Convert a phoneme to its corresponding lip shape.

        This helps with automatic lip sync generation from text/phonemes.
        """
        phoneme = phoneme.upper()
        mapping: dict[str, LIPShape] = {
            "AA": cls.AH,  # father
            "AE": cls.AH,  # cat
            "AH": cls.AH,  # but
            "AO": cls.OH,  # bought
            "AW": cls.AH,  # down
            "AY": cls.AH,  # bite
            "B": cls.MPB,  # be
            "CH": cls.SH,  # cheese
            "D": cls.TD,  # dee
            "DH": cls.TH,  # thee
            "EH": cls.EH,  # bet
            "ER": cls.EH,  # bird
            "EY": cls.EE,  # bait
            "F": cls.FV,  # fee
            "G": cls.KG,  # green
            "HH": cls.KG,  # he
            "IH": cls.EE,  # bit
            "IY": cls.EE,  # beet
            "JH": cls.SH,  # jee
            "K": cls.KG,  # key
            "L": cls.L,  # lee
            "M": cls.MPB,  # me
            "N": cls.NG,  # knee
            "NG": cls.NG,  # ping
            "OW": cls.OH,  # boat
            "OY": cls.OH,  # boy
            "P": cls.MPB,  # pee
            "R": cls.L,  # read
            "S": cls.STS,  # sea
            "SH": cls.SH,  # she
            "T": cls.TD,  # tea
            "TH": cls.TH,  # theta
            "UH": cls.OOH,  # book
            "UW": cls.OOH,  # boot
            "V": cls.FV,  # vee
            "W": cls.OOH,  # we
            "Y": cls.Y,  # yield
            "Z": cls.STS,  # zee
            "ZH": cls.SH,  # seizure
            " ": cls.NEUTRAL,  # pause
            "-": cls.NEUTRAL,  # pause
        }
        return mapping.get(phoneme, cls.NEUTRAL)


class LIP(BiowareResource):
    """Represents a LIP (Lip Sync) file containing mouth animation data.

    LIP files synchronize character mouth movements with voice-over audio during dialogue.
    They contain a series of keyframes that specify mouth shapes (visemes) at specific
    timestamps. The game engine interpolates between keyframes to create smooth lip
    animation that matches the spoken dialogue.

    Attributes:
    ----------
        length: Total duration of lip animation in seconds
            Matches the duration of the associated voice-over WAV file
            Stored as float32 in binary format (4 bytes)
            Used to determine animation playback bounds

        frames: List of keyframes defining mouth shapes at specific times
            Each keyframe contains a timestamp and mouth shape
            Keyframes must be sorted by time for proper animation playback
            Game engine interpolates between consecutive keyframes
    """

    BINARY_TYPE = ResourceType.LIP
    FILE_HEADER = "LIP V1.0"
    COMPARABLE_FIELDS = ("length",)
    COMPARABLE_SEQUENCE_FIELDS = ("frames",)

    def __init__(self) -> None:
        # Total duration of lip animation (matches voice-over length)
        self.length: float = 0.0

        # List of keyframes (timestamp + mouth shape pairs)
        self.frames: list[LIPKeyFrame] = []

    def __iter__(self) -> Iterator[LIPKeyFrame]:
        """Iterates through the stored list of keyframes yielding the LIPKeyFrame each iteration."""
        yield from self.frames

    def __len__(self) -> int:
        """Returns the number of stored keyframes."""
        return len(self.frames)

    def __getitem__(self, item: int) -> LIPKeyFrame:
        """Returns a keyframe from the specified index.

        Args:
        ----
            item: The index of the keyframe.

        Raises:
        ------
            IndexError: If the index is out of bounds.

        Returns:
        -------
            The corresponding LIPKeyFrame object.
        """
        return self.frames[item]

    def add(self, time: float, shape: LIPShape) -> None:
        """Adds a new keyframe and maintains time-based sorting.

        Args:
        ----
            time: The keyframe start time in seconds
            shape: The mouth shape for the keyframe

        The keyframes are automatically sorted by time to ensure proper animation playback.
        If a keyframe already exists at the given time, it will be replaced.
        """
        # Remove any existing keyframe at this time
        self.frames = [f for f in self.frames if abs(f.time - time) > 0.0001]

        frame = LIPKeyFrame(time, shape)
        self.frames.append(frame)
        self.frames.sort()  # Sort by time
        self.length = max(self.length, time)

    def remove(self, index: int) -> None:
        """Remove a keyframe at the specified index.

        Args:
        ----
            index: Index of the keyframe to remove

        Raises:
        ------
            IndexError: If index is out of range
        """
        if 0 <= index < len(self.frames):
            del self.frames[index]
            if self.frames:
                self.length = max(frame.time for frame in self.frames)
            else:
                self.length = 0.0

    def get_shapes(self, time: float) -> tuple[LIPShape, LIPShape, float] | None:
        """Gets interpolated shape data for a given time.

        Args:
        ----
            time: The time to get shapes for, in seconds

        Returns:
        -------
            A tuple containing:
            - Left shape (the previous keyframe's shape)
            - Right shape (the next keyframe's shape)
            - Interpolation factor between the shapes (0.0 to 1.0)
            Returns None if no valid keyframes exist for the given time.

        The interpolation factor can be used to blend between the two shapes
        for smooth animation. A factor of 0.0 means use the left shape entirely,
        while 1.0 means use the right shape entirely.
        """
        if not self.frames:
            return None

        # Handle time before first keyframe
        if time <= self.frames[0].time:
            return self.frames[0].shape, self.frames[0].shape, 0.0

        # Handle time after last keyframe
        if time >= self.frames[-1].time:
            return self.frames[-1].shape, self.frames[-1].shape, 0.0

        # Find surrounding keyframes
        left_frame: LIPKeyFrame = self.frames[0]
        right_frame: LIPKeyFrame = self.frames[0]

        for frame in self.frames:
            if time > frame.time:
                left_frame = frame
            if time <= frame.time:
                right_frame = frame
                break

        return left_frame.interpolate(right_frame, time)

    def get(self, index: int) -> LIPKeyFrame | None:
        """Returns the keyframe at the specified index if it exists.

        Args:
        ----
            index: The index of the keyframe.

        Returns:
        -------
            The corresponding LIPKeyFrame object or None if index is out of bounds.
        """
        return self.frames[index] if 0 <= index < len(self.frames) else None

    def get_shape_at_time(self, time: float) -> LIPShape | None:
        """Get the interpolated shape at a specific time.

        This is a convenience method that returns just the appropriate shape
        for the given time, handling interpolation internally.

        Args:
        ----
            time: The time to get the shape for

        Returns:
        -------
            The appropriate LIPShape for the given time, or None if no animation exists
        """
        shapes: tuple[LIPShape, LIPShape, float] | None = self.get_shapes(time)
        if not shapes:
            return None

        left_shape, right_shape, factor = shapes

        # For now, just return the shape we're closest to
        # In a full implementation, this would do proper shape interpolation
        return right_shape if factor > 0.5 else left_shape

    def clear(self) -> None:
        """Clear all keyframes from the animation."""
        self.frames.clear()
        self.length = 0.0

    def validate(self) -> list[str]:
        """Validate the LIP data for common issues.

        Returns:
        -------
            List of validation error messages, empty if valid
        """
        errors: list[str] = []

        if not self.frames:
            errors.append("No keyframes defined")
            return errors

        # Check for negative times
        for frame in self.frames:
            if frame.time < 0:
                errors.append(f"Negative time value: {frame.time}")

        # Check for proper ordering
        last_time: float = -1
        for frame in self.frames:
            if frame.time < last_time:
                errors.append(f"Keyframes out of order: {frame.time} after {last_time}")
            last_time = frame.time

        # Check length matches last keyframe
        if self.frames and abs(self.length - self.frames[-1].time) > 0.0001:
            errors.append(
                f"Length ({self.length}) doesn't match last keyframe time ({self.frames[-1].time})"
            )

        return errors

    def __json__(self) -> dict[str, Any]:
        """Serialize the LIP object to a JSON-compatible dictionary."""
        return {
            "duration": str(self.length),
            "keyframes": [
                {
                    "time": str(frame.time),
                    "shape": str(frame.shape.value),
                }
                for frame in self.frames
            ],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> LIP:
        """Create a LIP object from a JSON dictionary."""
        instance = cls()

        # Support legacy io_lip_json reader format that wrapped it in "lip":{"elements":[]}
        if "lip" in data and "elements" in data["lip"]:
            instance.length = float(data["lip"].get("duration", 0.0))
            for keyframe_dict in data["lip"]["elements"]:
                time = float(keyframe_dict["time"])
                shape = LIPShape(int(keyframe_dict["shape"]))
                instance.add(time, shape)
            return instance

        # Support the standard un-nested "keyframes" layout
        instance.length = float(data.get("duration", 0.0))
        for keyframe_dict in data.get("keyframes", []):
            time = float(keyframe_dict["time"])
            shape = LIPShape(int(keyframe_dict["shape"]))
            instance.add(time, shape)

        return instance


@dataclass
class LIPKeyFrame(ComparableMixin):
    """A single keyframe in a LIP animation sequence.

    Each keyframe specifies a mouth shape at a specific timestamp. The game engine
    interpolates between consecutive keyframes to create smooth lip movement during
    dialogue playback. Keyframes are sorted by time to enable efficient lookup and
    interpolation.

    References:
    ----------
        Keyframe layout (timestamp + shape).
        Binary Format (5 bytes):
        -----------------------
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 4    | float  | Time Stamp (seconds from start of audio)
        0x04   | 1    | uint8  | Shape (mouth shape index, 0-15)

    Attributes:
    ----------
        time: Timestamp when this keyframe occurs (seconds from start)
            Stored as float32 in binary format (4 bytes)
            Must be >= 0.0 and <= animation length
            Keyframes should be sorted by time for proper playback

        shape: Mouth shape (viseme) for this keyframe
            Stored as uint8 in binary format (1 byte)
            Valid range: 0-15 (16 possible shapes, see LIPShape enum)
            Index into character's "talk" animation keyframes
            Game engine uses this to select the appropriate mouth mesh pose
    """

    time: float
    shape: LIPShape
    COMPARABLE_FIELDS = ("time", "shape")

    def interpolate(self, other: LIPKeyFrame, time: float) -> tuple[LIPShape, LIPShape, float]:
        """Calculate interpolation between this keyframe and another.

        Args:
        ----
            other: The next keyframe to interpolate towards
            time: The current time to interpolate at

        Returns:
        -------
            Tuple of (left shape, right shape, interpolation factor)
        """
        if self == other:
            return self.shape, other.shape, 0.0

        factor = (time - self.time) / (other.time - self.time)
        factor = max(0.0, min(1.0, factor))  # Clamp between 0 and 1

        return self.shape, other.shape, factor

    def __lt__(self, other: LIPKeyFrame) -> bool:
        """Enable sorting keyframes by time."""
        return self.time < other.time
