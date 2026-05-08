"""High-level GFF-backed resource models (ARE, GIT, UTC, …).

These modules map the Generic File Format (GFF) binary tree into Python types via
``read_gff`` / ``write_gff`` (see ``pykotor.resource.formats.gff``). They do not embed
per-type Kaitai parsers: ``GFFBinaryReader`` already validates the wire format with
``kaitai_generated.gff.Gff`` before the legacy tree load.

PyKotor keeps a single GFF decode path here. Binary UTC loads additionally require a ``UTC ``
header via ``kaitai_generated.gff.Gff`` (see ``read_utc``); other generics rely on ``read_gff`` only.
"""
