"""Archive ↔ JSON serialization with readable resource embedding."""

from __future__ import annotations

import base64
import json

from io import BytesIO
from pathlib import Path
from typing import Any

from pykotor.common.misc import ResRef
from pykotor.resource.formats.bif import read_bif, write_bif
from pykotor.resource.formats.bif.bif_data import BIF, BIFType
from pykotor.resource.formats.erf import read_erf, write_erf
from pykotor.resource.formats.erf.erf_data import ERF, ERFType
from pykotor.resource.formats.rim import read_rim, write_rim
from pykotor.resource.formats.rim.rim_data import RIM
from pykotor.resource.type import ResourceType
from pykotor.tools.misc import is_any_erf_type_file, is_bif_file, is_rim_file
from pykotor.tools.resource_json import (
    SerializedResourcePayload,
    deserialize_embedded_resource_payload,
    serialize_resource_payload,
)


def _serialize_archive_resource(raw: bytes, restype: ResourceType, *, embed_plaintext: bool):
    if embed_plaintext:
        return serialize_resource_payload(raw, restype, mode="embedded")
    return SerializedResourcePayload("base64", base64.b64encode(raw).decode("ascii"))


def archive_to_dict(
    source: Path | bytes,
    key_source: Path | None = None,
    *,
    embed_plaintext: bool = True,
) -> dict[str, Any]:
    """Convert an archive (ERF, RIM, MOD, SAV, BIF) to a JSON-serializable dict.

    If embed_plaintext is True, resources with a known plaintext format are embedded
    as that format; others are base64. If False, all resources are base64.
    """
    if isinstance(source, bytes):
        data = source
        path = None
    else:
        path = Path(source)
        data = path.read_bytes()

    if path and is_any_erf_type_file(path):
        return _erf_to_dict(data, embed_plaintext=embed_plaintext)
    if path and is_rim_file(path):
        return _rim_to_dict(data, embed_plaintext=embed_plaintext)
    if path and is_bif_file(path):
        key_bytes = key_source.read_bytes() if key_source and key_source.exists() else None
        return _bif_to_dict(data, key_bytes=key_bytes, embed_plaintext=embed_plaintext)
    if isinstance(source, bytes) or path is None:
        if data[:4] in (b"ERF ", b"MOD ", b"SAV "):
            return _erf_to_dict(data, embed_plaintext=embed_plaintext)
        if data[:4] == b"RIM ":
            return _rim_to_dict(data, embed_plaintext=embed_plaintext)
        if data[:4] in (b"BIFF", b"BZF "):
            key_bytes = key_source.read_bytes() if key_source and key_source.exists() else None
            return _bif_to_dict(data, key_bytes=key_bytes, embed_plaintext=embed_plaintext)
    raise ValueError(f"Unsupported archive type: {path or 'bytes'}")


def _erf_to_dict(data: bytes, *, embed_plaintext: bool) -> dict[str, Any]:
    erf = read_erf(data)
    resources: list[dict[str, Any]] = []
    for res in erf:
        resref = str(res.resref) if res.resref else ""
        restype = res.restype
        raw = res.data
        serialized = _serialize_archive_resource(raw, restype, embed_plaintext=embed_plaintext)
        resources.append(
            {
                "resref": resref,
                "restype": restype.extension,
                "data_encoding": serialized.encoding,
                "data": serialized.payload,
            },
        )
    return {
        "format": "erf",
        "erf_type": erf.erf_type.value,
        "resources": resources,
    }


def _rim_to_dict(data: bytes, *, embed_plaintext: bool) -> dict[str, Any]:
    rim = read_rim(data)
    resources = []
    for res in rim:
        resref = str(res.resref) if res.resref else ""
        restype = res.restype
        raw = res.data
        serialized = _serialize_archive_resource(raw, restype, embed_plaintext=embed_plaintext)
        resources.append(
            {
                "resref": resref,
                "restype": restype.extension,
                "data_encoding": serialized.encoding,
                "data": serialized.payload,
            },
        )
    return {
        "format": "rim",
        "resources": resources,
    }


def _bif_to_dict(
    data: bytes,
    *,
    key_bytes: bytes | None = None,
    embed_plaintext: bool = True,
) -> dict[str, Any]:
    bif = read_bif(data, key_source=key_bytes)
    resources = []
    for res in bif.resources:
        resref = str(res.resref) if res.resref else ""
        restype = res.restype
        raw = res.data
        serialized = _serialize_archive_resource(raw, restype, embed_plaintext=embed_plaintext)
        resources.append(
            {
                "resref": resref,
                "restype": restype.extension,
                "resname_key_index": res.resname_key_index,
                "data_encoding": serialized.encoding,
                "data": serialized.payload,
            },
        )
    return {
        "format": "bif",
        "bif_type": bif.bif_type.value,
        "resources": resources,
    }


def dict_to_archive(data: dict[str, Any]) -> tuple[bytes, str]:
    """Convert a dict (from archive_to_dict) back to binary archive. Returns (bytes, suggested_extension)."""
    fmt = data.get("format")
    if fmt == "erf":
        return _dict_to_erf(data), "erf"
    if fmt == "rim":
        return _dict_to_rim(data), "rim"
    if fmt == "bif":
        return _dict_to_bif(data), "bif"
    raise ValueError(f"Unknown archive format in JSON: {fmt}")


def _dict_to_erf(data: dict[str, Any]) -> bytes:
    erf_type_str = data.get("erf_type", "ERF ")
    erf_type = next((x for x in ERFType if x.value == erf_type_str), ERFType.ERF)
    erf = ERF(erf_type=erf_type)
    for r in data.get("resources", []):
        resref = r["resref"]
        restype = ResourceType.from_extension(r["restype"])
        enc = r.get("data_encoding", "base64")
        payload = r["data"]
        raw = deserialize_embedded_resource_payload(enc, payload, restype)
        erf.set_data(ResRef(resref), restype, raw)
    out = BytesIO()
    write_erf(erf, out)
    return out.getvalue()


def _dict_to_rim(data: dict[str, Any]) -> bytes:
    rim = RIM()
    for r in data.get("resources", []):
        resref = r["resref"]
        restype = ResourceType.from_extension(r["restype"])
        enc = r.get("data_encoding", "base64")
        payload = r["data"]
        raw = deserialize_embedded_resource_payload(enc, payload, restype)
        rim.set_data(ResRef(resref), restype, raw)
    out = BytesIO()
    write_rim(rim, out)
    return out.getvalue()


def _dict_to_bif(data: dict[str, Any]) -> bytes:
    bif_type_str = data.get("bif_type", "BIFF")
    bif_type = BIFType.BZF if bif_type_str == "BZF " else BIFType.BIF
    bif = BIF(bif_type=bif_type)
    for r in data.get("resources", []):
        resref = r["resref"]
        restype = ResourceType.from_extension(r["restype"])
        res_id = r.get("resname_key_index")
        enc = r.get("data_encoding", "base64")
        payload = r["data"]
        raw = deserialize_embedded_resource_payload(enc, payload, restype)
        bif.set_data(ResRef(resref), restype, raw, res_id=res_id)
    out: bytearray = bytearray()
    write_bif(bif, out)
    return bytes(out)


def convert_archive_to_json(
    input_path: Path,
    output_path: Path,
    *,
    key_path: Path | None = None,
    embed_plaintext: bool = True,
) -> None:
    """Write archive at input_path to JSON file at output_path."""
    d = archive_to_dict(input_path, key_source=key_path, embed_plaintext=embed_plaintext)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(d, indent=2), encoding="utf-8")


def convert_json_to_archive(input_path: Path, output_path: Path) -> None:
    """Read JSON from input_path and write binary archive to output_path."""
    d = json.loads(input_path.read_text(encoding="utf-8"))
    raw, ext = dict_to_archive(d)
    out = output_path if output_path.suffix else output_path.with_suffix(f".{ext}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
