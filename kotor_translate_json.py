"""
KotOR JSON translator
--------------------

Input:  A JSON object (dict) of "string_id" -> "text"
Output: A JSON object (dict) of "string_id" -> "translated text"

Designed for big files (~50k entries):
- Saves a checkpoint every N entries so you can resume if it stops
- Retries translations with exponential backoff

Typical usage (EN -> ES):
  ./.venv/bin/python kotor_translate_json.py -i textos_kotor.json -o dialogo_espanol.json --source en --target es
"""

import argparse
import json
import os
import random
import sys
import time
from typing import Any, Dict, Tuple

from deep_translator import GoogleTranslator


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object/dict: {\"id\": \"text\", ...}")
    return data


def _load_checkpoint(path: str) -> Dict[str, str]:
    """
    Checkpoint format:
      {
        "done": <int>,
        "total": <int>,
        "translated": { "0": "...", "1": "...", ... },
        "saved_at": <unix_seconds>
      }
    """
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        return {}
    translated = obj.get("translated", {})
    return translated if isinstance(translated, dict) else {}


def _save_checkpoint(path: str, translated: Dict[str, str], total: int) -> None:
    tmp_path = f"{path}.tmp"
    payload = {"done": len(translated), "total": total, "translated": translated, "saved_at": time.time()}
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _translate_with_retry(
    translator: GoogleTranslator,
    text: str,
    *,
    max_retries: int,
    base_sleep_s: float,
    jitter_s: float,
) -> str:
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return translator.translate(text)
        except Exception as e:
            last_err = e
            if attempt >= max_retries:
                break
            # Exponential backoff + jitter (helps with temporary rate limits).
            sleep_s = base_sleep_s * (2**attempt) + (random.random() * jitter_s)
            time.sleep(sleep_s)
    raise last_err  # type: ignore[misc]


def translate_json(
    input_file: str,
    output_file: str,
    *,
    source: str,
    target: str,
    checkpoint_file: str,
    save_every: int,
    max_retries: int,
    per_item_sleep_s: float,
    retry_base_sleep_s: float,
    retry_jitter_s: float,
) -> None:
    data = _load_json(input_file)
    total = len(data)

    translator = GoogleTranslator(source=source, target=target)

    translated = _load_checkpoint(checkpoint_file)
    if translated:
        print(f"Resuming from checkpoint: {len(translated)}/{total}", flush=True)

    started = time.time()

    for str_id, raw_text in data.items():
        # Skip already translated IDs (resume support).
        if str_id in translated:
            continue

        # Only translate non-empty strings. Everything else is passed through safely.
        if not isinstance(raw_text, str) or not raw_text.strip():
            translated[str_id] = "" if raw_text is None else (raw_text if isinstance(raw_text, str) else str(raw_text))
        else:
            try:
                translated[str_id] = _translate_with_retry(
                    translator,
                    raw_text,
                    max_retries=max_retries,
                    base_sleep_s=retry_base_sleep_s,
                    jitter_s=retry_jitter_s,
                )
            except Exception as e:
                # If a single entry fails, keep original text and continue.
                translated[str_id] = raw_text
                print(f"[WARN] Translation failed id={str_id}: {e}", file=sys.stderr, flush=True)

        # Optional fixed sleep between items (useful to reduce rate-limits).
        if per_item_sleep_s > 0:
            time.sleep(per_item_sleep_s)

        done = len(translated)
        if done % save_every == 0:
            _save_checkpoint(checkpoint_file, translated, total)
            elapsed = time.time() - started
            rate = done / elapsed if elapsed > 0 else 0.0
            print(f"Progress: {done}/{total} | {rate:.2f} items/sec | checkpoint saved", flush=True)

    # Final save + final output JSON
    _save_checkpoint(checkpoint_file, translated, total)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)

    print(f"Done. Output JSON: {output_file}", flush=True)
    print(f"Checkpoint: {checkpoint_file}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Translate a KotOR strings JSON (id->text) to another language.")
    p.add_argument("-i", "--input", default="textos_kotor.json", help="Input JSON file (dict).")
    p.add_argument("-o", "--output", default="dialogo_espanol.json", help="Output translated JSON file.")
    p.add_argument("--source", default="en", help="Source language code (example: en).")
    p.add_argument("--target", default="es", help="Target language code (example: es).")
    p.add_argument(
        "--checkpoint",
        default="traductor_checkpoint.json",
        help="Checkpoint JSON file (allows resume).",
    )
    p.add_argument("--save-every", type=int, default=100, help="Save checkpoint every N translated entries.")
    p.add_argument("--max-retries", type=int, default=4, help="Max retries per entry if translation fails.")
    p.add_argument("--sleep", type=float, default=0.0, help="Fixed sleep seconds between entries (rate-limit help).")
    p.add_argument("--retry-base-sleep", type=float, default=1.0, help="Retry backoff base sleep seconds.")
    p.add_argument("--retry-jitter", type=float, default=0.25, help="Random jitter seconds added to retry sleeps.")
    args = p.parse_args()

    translate_json(
        args.input,
        args.output,
        source=args.source,
        target=args.target,
        checkpoint_file=args.checkpoint,
        save_every=max(1, args.save_every),
        max_retries=max(0, args.max_retries),
        per_item_sleep_s=max(0.0, args.sleep),
        retry_base_sleep_s=max(0.0, args.retry_base_sleep),
        retry_jitter_s=max(0.0, args.retry_jitter),
    )


if __name__ == "__main__":
    main()

