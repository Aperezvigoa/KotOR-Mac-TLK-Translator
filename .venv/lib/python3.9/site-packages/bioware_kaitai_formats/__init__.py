"""Kaitai Struct generated parsers for BioWare / KotOR wire formats.

Source ``.ksy`` files: upstream ``OldRepublicDevs/bioware-kaitai-formats`` (see package README).
Generated Python is committed in this distribution; regenerate with ``scripts/regenerate_python.py``.

**Consumers:** import concrete modules, e.g. ``from bioware_kaitai_formats.gff import Gff``.

**KotOR loaders in PyKotor** (Kaitai-first where applicable): SSF, TLK, LIP, RIM, TwoDA, KEY, BIF,
BZF, ERF, WAV, BWM, NCS (plus ``ncs_minimal`` fallback), GFF, MDL, MDX, DDS, TPC, TGA, VIS, LYT,
TXI, LTR, MDL_ASCII. Wrapper specs expose ``json_content`` / ``xml_content`` / ``csv_content`` /
``raw_content`` where the ``.ksy`` is a blob wrapper.

**Auxiliary / shared specs** (import-tested; not all wired to game I/O): ``plt``, ``da2s``, ``das``,
``pcc``, ``bioware_extract_common``, ``bioware_tslpatcher_common``, ``bioware_type_ids``, ``nss``,
``itp_xml``.
"""

__version__ = "0.1.0"
