"""
KotOR TLK compiler
-----------------

Input:  A translated JSON object (dict) of "string_id" -> "text"
Output: A KotOR `dialog.tlk` compiled with PyKotor.

Typical usage:
  ./.venv/bin/python kotor_compile_tlk.py -i dialogo_espanol.json -o dialog.tlk
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Iterable, Tuple

from pykotor.common.misc import ResRef
from pykotor.resource.formats.tlk import TLK, TLKEntry, write_tlk


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object/dict: {\"id\": \"text\", ...}")
    return data


def _iter_sorted_items(data: Dict[str, Any]) -> Iterable[Tuple[int, str]]:
    """
    Ensures IDs are integers (StrRef indices) and returns sorted (id, text) pairs.
    Non-numeric keys are ignored (with a warning).
    """
    items: list[Tuple[int, str]] = []
    bad_keys = 0
    for k, v in data.items():
        try:
            idx = int(k)
        except Exception:
            bad_keys += 1
            continue
        text = v if isinstance(v, str) else ("" if v is None else str(v))
        items.append((idx, text))
    items.sort(key=lambda t: t[0])
    if bad_keys:
        print(f"[WARN] Ignored {bad_keys} non-numeric keys.", file=sys.stderr, flush=True)
    return items


def compile_json_to_tlk(input_json: str, output_tlk: str, *, progress_every: int) -> None:
    if not os.path.exists(input_json):
        raise FileNotFoundError(f"Input JSON not found: {input_json}")

    print(f"Loading JSON: {input_json}", flush=True)
    data = _load_json(input_json)
    items = list(_iter_sorted_items(data))
    total = len(items)
    if total == 0:
        raise ValueError("No valid entries found (numeric id -> text).")

    tlk = TLK()

    print(f"Compiling {total} entries...", flush=True)
    started = time.time()
    for i, (strref, text) in enumerate(items, start=1):
        # TLK is an array indexed by StrRef. Fill missing indices with empty entries.
        while len(tlk.entries) <= strref:
            tlk.entries.append(TLKEntry("", ResRef("")))
        tlk.entries[strref] = TLKEntry(text, ResRef(""))

        if progress_every > 0 and i % progress_every == 0:
            elapsed = time.time() - started
            rate = i / elapsed if elapsed > 0 else 0.0
            print(f"Progress: {i}/{total} | {rate:.0f} entries/sec", flush=True)

    print(f"Writing TLK: {output_tlk}", flush=True)
    write_tlk(tlk, output_tlk)
    print("OK. dialog.tlk generated.", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Compile a translated KotOR strings JSON (id->text) into dialog.tlk.")
    p.add_argument("-i", "--input", default="dialogo_espanol.json", help="Input translated JSON file.")
    p.add_argument("-o", "--output", default="dialog.tlk", help="Output TLK file.")
    p.add_argument("--progress-every", type=int, default=5000, help="Print progress every N entries.")
    args = p.parse_args()

    compile_json_to_tlk(args.input, args.output, progress_every=max(1, args.progress_every))


if __name__ == "__main__":
    main()

