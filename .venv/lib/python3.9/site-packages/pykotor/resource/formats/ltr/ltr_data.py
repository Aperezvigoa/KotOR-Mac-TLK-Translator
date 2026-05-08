"""This module handles classes relating to editing LTR files.

LTR (Letter) files contain Markov chain probability data for generating random names
during character creation. They use a 3rd-order Markov chain model with single-letter,
double-letter (bigram), and triple-letter (trigram) probability tables. Each table
stores probability values for characters appearing at the start, middle, or end of names.

Observed retail behavior:
----------
    Character creation draws random names from ``LTR `` / ``V1.0`` blobs: a letter count plus
    packed float tables for single-, double-, and triple-letter Markov transitions as laid out
    below. It has been observed that KotOR ships 28-letter alphabets in practice.


Binary Format:
-------------
    Header (9 bytes):
    Offset | Size | Type   | Description
    -------|------|--------|-------------
    0x00   | 4    | char[] | File Type ("LTR ")
    0x04   | 4    | char[] | File Version ("V1.0")
    0x08   | 1    | uint8  | Letter Count (26 or 28)
    Single Letters (84 bytes = 28 * 3 * 4):
    Start probabilities: 28 floats (4 bytes each)
    Middle probabilities: 28 floats (4 bytes each)
    End probabilities: 28 floats (4 bytes each)
    Double Letters (2352 bytes = 28 * 28 * 3 * 4):
    28 LetterSets, each containing:
    Start probabilities: 28 floats
    Middle probabilities: 28 floats
    End probabilities: 28 floats
    Triple Letters (65856 bytes = 28 * 28 * 28 * 3 * 4):
    28x28 LetterSets, each containing:
    Start probabilities: 28 floats
    Middle probabilities: 28 floats
    End probabilities: 28 floats
"""

from __future__ import annotations

import random
import secrets
import string

from pykotor.resource.formats._base import BiowareResource, ComparableMixin
from pykotor.resource.type import ResourceType


class LTR(BiowareResource):
    """Represents a LTR (Letter) file containing Markov chain name generation data.

    LTR files use 3rd-order Markov chains to generate random names. The probability
    tables store likelihood values for characters appearing in different positions
    (start, middle, end) based on previous character context (none, one, or two chars).

    Attributes:
    ----------
        CHARACTER_SET: String of valid characters (28 chars: a-z + apostrophe + hyphen)
            KotOR uses 28-character set: "abcdefghijklmnopqrstuvwxyz'-"
            NWN uses 26-character set: "abcdefghijklmnopqrstuvwxyz"

        NUM_CHARACTERS: Number of characters in character set (28 for KotOR)
            Fixed at 28 for KotOR games

        _singles: Single-letter probability block (no context)
            Contains start/middle/end probabilities for each character
            Used to generate the first character of names

        _doubles: Double-letter probability blocks (1-character context)
            Array of 28 LetterSets, indexed by previous character
            Used to generate second character based on first character

        _triples: Triple-letter probability blocks (2-character context)
            28x28 array of LetterSets, indexed by previous two characters
            Used to generate third and subsequent characters based on previous two
    """

    CHARACTER_SET = string.ascii_lowercase + "'-"
    # O(1) lookup for character index; avoids repeated list.index() in hot paths.
    _CHAR_INDEX: dict[str, int] = {c: i for i, c in enumerate(string.ascii_lowercase + "'-")}
    NUM_CHARACTERS = 28

    BINARY_TYPE = ResourceType.LTR
    COMPARABLE_FIELDS = ("_singles", "_doubles", "_triples")

    def __init__(self):
        # Single-letter probability block (no context, for first character)
        self._singles: LTRBlock = LTRBlock(LTR.NUM_CHARACTERS)

        # Double-letter probability blocks (1-character context, for second character)
        # Array of 28 blocks, indexed by previous character
        self._doubles: list[LTRBlock] = [
            LTRBlock(LTR.NUM_CHARACTERS) for _ in range(LTR.NUM_CHARACTERS)
        ]

        # Triple-letter probability blocks (2-character context, for third+ characters)
        # 28x28 array of blocks, indexed by previous two characters
        self._triples: list[list[LTRBlock]] = [
            [LTRBlock(LTR.NUM_CHARACTERS) for _ in range(LTR.NUM_CHARACTERS)]
            for _ in range(LTR.NUM_CHARACTERS)
        ]

    def __eq__(self, other):
        if not isinstance(other, LTR):
            return NotImplemented  # type: ignore[no-any-return]
        return (
            self._singles == other._singles
            and self._doubles == other._doubles
            and self._triples == other._triples
        )

    def __hash__(self):
        return hash(
            (self._singles, tuple(self._doubles), tuple(tuple(row) for row in self._triples))
        )

    @staticmethod
    def _chance() -> float:
        """Returns a randomly generated float between 0.0 and 1.0 inclusive.

        Returns:
        -------
            A float between 0.0 and 1.0 inclusive.
        """
        return secrets.randbelow(1001) / 1000

    def generate(
        self,
        seed: int | None = None,
    ) -> str:
        """Returns a randomly generated name based on the LTR instance data.

        This method implements a 3rd-order Markov chain name generation algorithm.
        It generates names character-by-character using probability tables, starting
        with single-letter probabilities, then double-letter (bigram), then triple-letter
        (trigram) probabilities for subsequent characters.

        Args:
        ----
            seed: Randomness seed for reproducible name generation.

        Returns:
        -------
            A randomly generated name (capitalized).

        Algorithm:
        ---------
            1. Generate first character using single-letter start probabilities
            2. Generate second character using double-letter start probabilities (based on first char)
            3. Generate third character using triple-letter start probabilities (based on first two chars)
            4. Generate subsequent characters using triple-letter middle probabilities
            5. Terminate when triple-letter end probability is selected or max attempts reached
        """
        # Set random seed for reproducible generation
        random.seed(seed)

        done = False

        while not done:
            attempts = 0
            name: str = ""

            # Generate first character using single-letter start probabilities
            for char in LTR.CHARACTER_SET:
                if LTR._chance() < self._singles.get_start(char):
                    name += char
                    break
            else:
                continue

            # Generate second character using double-letter start probabilities (indexed by first char)
            for char in LTR.CHARACTER_SET:
                index = LTR._CHAR_INDEX[name[-1]]
                if LTR._chance() < self._doubles[index].get_start(char):
                    name += char
                    break
            else:
                continue

            # Generate third character using triple-letter start probabilities (indexed by first two chars)
            for char in LTR.CHARACTER_SET:
                index1 = LTR._CHAR_INDEX[name[-2]]
                index2 = LTR._CHAR_INDEX[name[-1]]
                if LTR._chance() < self._triples[index1][index2].get_start(char):
                    name += char
                    break
            else:
                continue

            # Generate subsequent characters using triple-letter middle/end probabilities
            while True:
                prob: float = LTR._chance()

                # Check if name should end (probability increases with name length)
                if (secrets.randbelow(12) % 12) <= len(name):
                    # Select final character using triple-letter end probabilities
                    for char in LTR.CHARACTER_SET:
                        index1 = LTR._CHAR_INDEX[name[-2]]
                        index2 = LTR._CHAR_INDEX[name[-1]]
                        if prob < self._triples[index1][index2].get_end(char):
                            name += char
                            return name.capitalize()

                # Generate next character using triple-letter middle probabilities
                for char in LTR.CHARACTER_SET:
                    index1 = LTR._CHAR_INDEX[name[-2]]
                    index2 = LTR._CHAR_INDEX[name[-1]]
                    if prob < self._triples[index1][index2].get_middle(char):
                        name += char
                        break
                else:
                    # No valid character found - increment attempts and check termination
                    attempts += 1
                    if len(name) < 4 or attempts > 100:  # noqa: PLR2004
                        break

        msg = f"Unknown problem generating LTR from seed {seed}"
        raise RuntimeError(msg)

    def set_singles_start(
        self,
        char: str,
        chance: float,
    ):
        self._singles.set_start(char, chance)

    def set_singles_middle(
        self,
        char: str,
        chance: float,
    ):
        self._singles.set_middle(char, chance)

    def set_singles_end(
        self,
        char: str,
        chance: float,
    ):
        self._singles.set_end(char, chance)

    def set_doubles_start(
        self,
        previous1: str,
        char: str,
        chance: float,
    ):
        self._doubles[LTR._CHAR_INDEX[previous1]].set_start(char, chance)

    def set_doubles_middle(
        self,
        previous1: str,
        char: str,
        chance: float,
    ):
        self._doubles[LTR._CHAR_INDEX[previous1]].set_middle(char, chance)

    def set_doubles_end(
        self,
        previous1: str,
        char: str,
        chance: float,
    ):
        self._doubles[LTR._CHAR_INDEX[previous1]].set_end(char, chance)

    def set_triples_start(
        self,
        previous2: str,
        previous1: str,
        char: str,
        chance: float,
    ):
        self._triples[LTR._CHAR_INDEX[previous2]][LTR._CHAR_INDEX[previous1]].set_start(
            char, chance
        )

    def set_triples_middle(
        self,
        previous2: str,
        previous1: str,
        char: str,
        chance: float,
    ):
        self._triples[LTR._CHAR_INDEX[previous2]][LTR._CHAR_INDEX[previous1]].set_middle(
            char, chance
        )

    def set_triples_end(
        self,
        previous2: str,
        previous1: str,
        char: str,
        chance: float,
    ):
        self._triples[LTR._CHAR_INDEX[previous2]][LTR._CHAR_INDEX[previous1]].set_end(char, chance)


class LTRBlock(ComparableMixin):
    """Stores probability values for characters appearing in different name positions.

    Each LTRBlock contains three probability arrays (start, middle, end) that define
    the likelihood of each character appearing at the start, middle, or end of a name
    segment. These probabilities are cumulative (values increase monotonically) and
    are used with random number generation to select characters.

    On-disk layout:
    ----------
    Each letter set stores three parallel float tables (start, middle, end) sized by the
    file's letter count.


    Attributes:
    ----------
        _start: Probability array for characters at start of name segment
            Array of 28 floats (one per character)
            Cumulative probabilities (monotonically increasing)
            Used when generating first character or after name breaks

        _middle: Probability array for characters in middle of name segment
            Array of 28 floats (one per character)
            Cumulative probabilities (monotonically increasing)
            Used when generating characters after start but before end

        _end: Probability array for characters at end of name segment
            Array of 28 floats (one per character)
            Cumulative probabilities (monotonically increasing)
            Used when generating final character of name
    """

    COMPARABLE_SEQUENCE_FIELDS = ("_start", "_middle", "_end")

    def __init__(
        self,
        num_characters: int,
    ):
        # Probability array for characters at start of name segment
        # Cumulative probabilities (monotonically increasing)
        self._start: list[float] = [0.0] * num_characters

        # Probability array for characters in middle of name segment
        # Cumulative probabilities (monotonically increasing)
        self._middle: list[float] = [0.0] * num_characters

        # Probability array for characters at end of name segment
        # Cumulative probabilities (monotonically increasing)
        self._end: list[float] = [0.0] * num_characters

    def __eq__(self, other):
        if not isinstance(other, LTRBlock):
            return NotImplemented  # type: ignore[no-any-return]
        return (
            self._start == other._start
            and self._middle == other._middle
            and self._end == other._end
        )

    def __hash__(self):
        return hash((tuple(self._start), tuple(self._middle), tuple(self._end)))

    def set_start(
        self,
        char: str,
        chance: float,
    ):
        """Sets the chance of a specified character at the start of the block.

        Args:
        ----
            char: The specified character from LTR.CHARACTER_SET.
            chance: The chance of occurrence from 0.0 to 1.0 inclusive.

        Raises:
        ------
            ValueError: If length of char is not 0 OR if the chance was not between 0.0 and 1.0 inclusive.
            IndexError: If char is not present in LTR.CHARACTER_SET.
        """
        if len(char) != 1:
            msg = "The character specified was not a real character."
            raise ValueError(msg)
        if char not in LTR.CHARACTER_SET:
            msg = "The character specified was invalid."
            raise IndexError(msg)
        if 0.0 > chance > 1.0:
            msg = "The chance specified must be between 0.0 and 1.0 inclusive."
            raise ValueError(msg)

        char_id = LTR._CHAR_INDEX[char]
        self._start[char_id] = chance

    def set_middle(
        self,
        char: str,
        chance: float,
    ):
        """Sets the chance of a specified character at the middle of the block.

        Args:
        ----
            char: char: The specified character from LTR.CHARACTER_SET.
            chance: The chance of occurrence from 0.0 to 1.0 inclusive.

        Raises:
        ------
            ValueError: If length of char is not 0 OR if the chance was not between 0.0 and 1.0 inclusive.
            IndexError: If char is not present in LTR.CHARACTER_SET.
        """
        if len(char) != 1:
            msg = "The character specified was not a real character."
            raise ValueError(msg)
        if char not in LTR.CHARACTER_SET:
            msg = "The character specified was invalid."
            raise IndexError(msg)
        if 0.0 > chance > 1.0:
            msg = "The chance specified must be between 0.0 and 1.0 inclusive."
            raise ValueError(msg)

        char_id = LTR._CHAR_INDEX[char]
        self._middle[char_id] = chance

    def set_end(
        self,
        char: str,
        chance: float,
    ):
        """Sets the chance of a specified character at the end of the block.

        Args:
        ----
            char: char: The specified character from LTR.CHARACTER_SET.
            chance: The chance of occurrence from 0.0 to 1.0 inclusive.

        Raises:
        ------
            ValueError: If length of char is not 0 OR if the chance was not between 0.0 and 1.0 inclusive.
            IndexError: If char is not present in LTR.CHARACTER_SET.
        """
        if len(char) != 1:
            msg = "The character specified was not a real character."
            raise ValueError(msg)
        if char not in LTR.CHARACTER_SET:
            msg = "The character specified was invalid."
            raise IndexError(msg)
        if 0.0 > chance > 1.0:
            msg = "The chance specified must be between 0.0 and 1.0 inclusive."
            raise ValueError(msg)

        char_id = LTR._CHAR_INDEX[char]
        self._end[char_id] = chance

    def get_start(
        self,
        char: str,
    ) -> float:
        """Returns the chance of a specified character at the start of the block.

        Args:
        ----
            char: char: The specified character from LTR.CHARACTER_SET.

        Raises:
        ------
            ValueError: If length of char is not 0.
            IndexError: If char is not present in LTR.CHARACTER_SET.

        Returns:
        -------
            The chance of a specified character at the start of the block.

        """
        if len(char) != 1:
            msg = "The character specified was not a real character."
            raise ValueError(msg)
        if char not in LTR.CHARACTER_SET:
            msg = "The character specified was invalid."
            raise IndexError(msg)

        char_id = LTR._CHAR_INDEX[char]
        return self._start[char_id]

    def get_middle(
        self,
        char: str,
    ) -> float:
        """Returns the chance of a specified character at the middle of the block.

        Args:
        ----
            char: char: The specified character from LTR.CHARACTER_SET.

        Raises:
        ------
            ValueError: If length of char is not 0.
            IndexError: If char is not present in LTR.CHARACTER_SET.

        Returns:
        -------
            The chance of a specified character at the start of the block.

        """
        if len(char) != 1:
            msg = "The character specified was not a real character."
            raise ValueError(msg)
        if char not in LTR.CHARACTER_SET:
            msg = "The character specified was invalid."
            raise IndexError(msg)

        char_id = LTR._CHAR_INDEX[char]
        return self._middle[char_id]

    def get_end(
        self,
        char: str,
    ) -> float:
        """Returns the chance of a specified character at the end of the block.

        Args:
        ----
            char: char: The specified character from LTR.CHARACTER_SET.

        Raises:
        ------
            ValueError: If length of char is not 0.
            IndexError: If char is not present in LTR.CHARACTER_SET.

        Returns:
        -------
            The chance of a specified character at the start of the block.

        """
        if len(char) != 1:
            msg = "The character specified was not a real character."
            raise ValueError(msg)
        if char not in LTR.CHARACTER_SET:
            msg = "The character specified was invalid."
            raise IndexError(msg)

        char_id = LTR._CHAR_INDEX[char]
        return self._end[char_id]
