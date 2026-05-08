"""This module handles classes relating to editing SSF files.

SSF (Sound Set File) files contain mappings from sound event types to string references (StrRefs)
in the TLK file. Each SSF defines a set of 28 sound effects that creatures can play during
various game events (battle cries, pain grunts, selection sounds, etc.). The StrRefs point
to entries in dialog.tlk which contain the actual WAV file references.

Observed retail behavior:
----------
    Creature sound sets map 28 fixed event slots to StrRefs in ``dialog.tlk``. On disk the
    resources use the ``SSF `` / ``V1.1`` header, a table offset (commonly 12), and 28
    consecutive 32-bit StrRef fields; ``-1`` / ``0xFFFFFFFF`` means “no sound” for that slot.
"""

from __future__ import annotations

from enum import IntEnum

from pykotor.resource.formats._base import BiowareResource
from pykotor.resource.type import ResourceType


class SSF(BiowareResource):
    """Represents a SSF (Sound Set File) containing creature sound event mappings.

    SSF files map 28 predefined sound event types to string references (StrRefs) in the
    TLK file. When a creature needs to play a sound (e.g., battle cry, pain grunt), the
    game looks up the StrRef from the SSF and then retrieves the actual WAV filename from
    the TLK entry. This allows different creatures to have different sound sets while
    sharing the same event type system.

    Attributes:
    ----------
        _sounds: Array of 28 StrRef values, one for each sound event type
            Index corresponds to SSFSound enum value
            Each value is a StrRef (int32) into dialog.tlk
            Value -1 indicates no sound for that event type
            Array length fixed at 28 for KotOR (some implementations use 40 for NWN compatibility)
    """

    BINARY_TYPE = ResourceType.SSF
    COMPARABLE_SEQUENCE_FIELDS = ("_sounds",)

    def __init__(self):
        # Array of 28 StrRef values (one per sound event type)
        # Index maps to SSFSound enum, value is StrRef into dialog.tlk
        # -1 indicates no sound for that event type
        self._sounds: list[int] = [-1] * 28

    def __eq__(self, other):
        if not isinstance(other, SSF):
            return NotImplemented  # type: ignore[no-any-return]
        return self._sounds == other._sounds

    def __hash__(self):
        return hash(tuple(self._sounds))

    def __getitem__(
        self,
        item,
    ):
        """Returns the stringref for the specified sound."""
        if not isinstance(item, SSFSound):
            return NotImplemented  # type: ignore[no-any-return]
        return self._sounds[item]

    def __json__(self) -> dict[str, list[dict[str, str]]]:
        """Serialize the SSF object to a JSON-compatible dictionary."""
        json_data: dict[str, list[dict[str, str]]] = {"sounds": []}
        for sound_name, sound in SSFSound.__members__.items():
            json_data["sounds"].append(
                {
                    "id": str(sound.value),
                    "label": sound_name,
                    "strref": str(self.get(sound)),
                }
            )
        return json_data

    @classmethod
    def from_json(cls, data: dict) -> SSF:
        """Hydrate an SSF object from a JSON dictionary."""
        instance = cls()
        sounds = data.get("sounds")
        if not isinstance(sounds, list):
            msg = "The JSON file that was loaded was not a valid SSF."
            raise ValueError(msg)

        for sound_entry in sounds:
            sound = SSFSound(int(sound_entry["id"]))
            stringref = int(sound_entry["strref"])
            instance.set_data(sound, stringref)

        return instance

    def reset(self):
        """Sets all the sound stringrefs to -1."""
        for i in range(28):
            self._sounds[i] = -1

    def set_data(
        self,
        sound: SSFSound,
        stringref: int,
    ):
        """Set the stringref for the specified sound.

        Args:
        ----
            sound: The sound.
            stringref: The new stringref for the sound.
        """
        self._sounds[sound] = stringref

    def get(
        self,
        sound: SSFSound | int,
    ) -> int | None:
        """Returns the stringref for the specified sound.

        Args:
        ----
            sound: The sound.

        Returns:
        -------
            The corresponding stringref.
        """
        if isinstance(sound, SSFSound):
            return self._sounds[sound.value]
        if isinstance(sound, int):
            if sound < 0 or sound >= 28:
                raise ValueError(f"Sound index must be between 0 and 27, got {sound}")
            return self._sounds[sound]
        raise ValueError(f"Sound must be a SSFSound or int, got {type(sound)}")


class SSFSound(IntEnum):
    """Enumeration of sound event types used in SSF files.

        Each value represents a specific game event that can trigger a sound effect.
        The SSF file maps these event types to StrRefs in dialog.tlk, which in turn
        reference the actual WAV files to play. This system allows different creatures
        to have different sound sets while sharing the same event type definitions.

    Sound Event Types:
    ------------------
        - BATTLE_CRY_1-6 (0-5): Battle cry sounds played during combat

                Used when creature enters combat or performs combat actions

        - SELECT_1-3 (6-8): Selection sounds when creature is clicked/selected
                Played when player clicks on creature

        - ATTACK_GRUNT_1-3 (9-11): Grunts during attack animations
                Used during melee/ranged attack animations

        - PAIN_GRUNT_1-2 (12-13): Pain sounds when taking damage
                Played when creature receives damage

        - LOW_HEALTH (14): Sound when health drops below threshold
                Typically played at ~25% health

        - DEAD (15): Death sound when creature dies
                Played on creature death

        - CRITICAL_HIT (16): Sound when creature scores critical hit
                Played when creature lands critical attack

        - TARGET_IMMUNE (17): Sound when target is immune to attack
                Played when attack has no effect

        - LAY_MINE (18): Sound when laying a mine

        - DISARM_MINE (19): Sound when disarming a mine

        - BEGIN_STEALTH (20): Sound when entering stealth mode

        - BEGIN_SEARCH (21): Sound when starting search mode

        - BEGIN_UNLOCK (22): Sound when starting lockpicking

        - UNLOCK_FAILED (23): Sound when lockpicking fails

        - UNLOCK_SUCCESS (24): Sound when lockpicking succeeds

        - SEPARATED_FROM_PARTY (25): Sound when leaving party

        - REJOINED_PARTY (26): Sound when rejoining party

        - POISONED (27): Sound when creature is poisoned
    """

    BATTLE_CRY_1 = 0
    BATTLE_CRY_2 = 1
    BATTLE_CRY_3 = 2
    BATTLE_CRY_4 = 3
    BATTLE_CRY_5 = 4
    BATTLE_CRY_6 = 5
    SELECT_1 = 6
    SELECT_2 = 7
    SELECT_3 = 8
    ATTACK_GRUNT_1 = 9
    ATTACK_GRUNT_2 = 10
    ATTACK_GRUNT_3 = 11
    PAIN_GRUNT_1 = 12
    PAIN_GRUNT_2 = 13
    LOW_HEALTH = 14
    DEAD = 15
    CRITICAL_HIT = 16
    TARGET_IMMUNE = 17
    LAY_MINE = 18
    DISARM_MINE = 19
    BEGIN_STEALTH = 20
    BEGIN_SEARCH = 21
    BEGIN_UNLOCK = 22
    UNLOCK_FAILED = 23
    UNLOCK_SUCCESS = 24
    SEPARATED_FROM_PARTY = 25
    REJOINED_PARTY = 26
    POISONED = 27
