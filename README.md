# KotOR TLK Translator (JSON → Any Language → dialog.tlk)

![Star Wars: Knights of the Old Republic cover](star-wars-knights-of-the-old-republic-pc-mac-juego-steam-cover.jpg)

This folder contains a small Python toolchain to:

1) **Translate** a KotOR strings JSON (`id -> text`) into any target language.  
2) **Compile** the translated JSON into a **KotOR `dialog.tlk`** using **PyKotor**.

It was designed for large files (≈50k entries) and supports **checkpointing/resume** so you can stop and continue later.

---

## What’s in this repo

- `textos_kotor.json`  
  Original strings in JSON format (a dictionary mapping string IDs to text).

- `kotor_translate_json.py`  
  Translates a JSON `id -> text` file using `deep-translator` (GoogleTranslator).  
  Creates/updates a checkpoint file while running so you can resume.

- `dialogo_espanol.json`  
  **Already translated Spanish JSON** (generated output).

- `kotor_compile_tlk.py`  
  Compiles a translated JSON file into `dialog.tlk` using PyKotor.

Note: older wrapper scripts were removed to keep the folder clean. Use the `kotor_*` scripts.

- `dialog.tlk`  
  **Already compiled Spanish TLK** created from `dialogo_espanol.json`.
  If you want **any other language**, you should **delete this `dialog.tlk` and recompile** from your new translated JSON.

- `requirements.txt`  
  Python dependencies.

---

## Requirements

- macOS (instructions below assume macOS, but it should work on Windows/Linux too)
- Python 3.9+ recommended
- Internet access (translation uses Google Translate via `deep-translator`)

---

## Setup (recommended: local virtual environment)

Open Terminal in this folder (example path shown below):

```bash
cd "/Users/aalbizu/Desktop/Traductor"
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

From now on, run scripts using `./.venv/bin/python ...` to ensure the right dependencies are used.

---

## 1) Translate JSON to any language

### Basic usage (English → Spanish)

```bash
./.venv/bin/python kotor_translate_json.py \
  -i textos_kotor.json \
  -o dialogo_espanol.json \
  --source en \
  --target es
```

### Translate to a different language

Use any target language code supported by Google Translate.

Examples:

- English → French:

```bash
./.venv/bin/python kotor_translate_json.py -i textos_kotor.json -o dialogo_fr.json --source en --target fr
```

- English → German:

```bash
./.venv/bin/python kotor_translate_json.py -i textos_kotor.json -o dialogo_de.json --source en --target de
```

- English → Italian:

```bash
./.venv/bin/python kotor_translate_json.py -i textos_kotor.json -o dialogo_it.json --source en --target it
```

### Progress and resume (checkpoint)

Translation can take a long time for ~50k entries. This tool writes a checkpoint file periodically:

- Default checkpoint: `traductor_checkpoint.json`
- By default it saves every 100 translated entries (`--save-every 100`)

If the script stops (you close the terminal, lose internet, etc.), just run the same command again: it will **resume** from the checkpoint automatically.

Note: for a clean folder, you can delete the checkpoint after you are done. It will be recreated automatically on the next run.

Example with a custom checkpoint and more frequent saving:

```bash
./.venv/bin/python kotor_translate_json.py \
  -i textos_kotor.json \
  -o dialogo_fr.json \
  --source en \
  --target fr \
  --checkpoint checkpoint_fr.json \
  --save-every 50
```

### Avoiding rate limits / being nicer to Google

You can insert a small delay between requests:

```bash
./.venv/bin/python kotor_translate_json.py -i textos_kotor.json -o dialogo_fr.json --source en --target fr --sleep 0.2
```

If translation fails for an entry, the script logs a warning and **keeps the original text** for that ID (so the run can continue).

---

## 2) Compile translated JSON into `dialog.tlk`

Once you have a translated JSON (for example `dialogo_espanol.json` or `dialogo_fr.json`), compile it into `dialog.tlk`:

```bash
./.venv/bin/python kotor_compile_tlk.py -i dialogo_espanol.json -o dialog.tlk
```

For a different language:

```bash
./.venv/bin/python kotor_compile_tlk.py -i dialogo_fr.json -o dialog.tlk
```

### Important note about the provided `dialog.tlk`

This folder already includes a `dialog.tlk` that is **Spanish**.

- If you want to use **Spanish**, you can use it as-is.
- If you want **any other language**, **delete `dialog.tlk`** and generate a new one from your translated JSON:
  - Delete: `dialog.tlk`
  - Compile again: `./.venv/bin/python kotor_compile_tlk.py -i dialogo_xx.json -o dialog.tlk`

---

## 3) Install `dialog.tlk` into KotOR (Steam, macOS)

### Make a backup first

Before replacing anything, copy the original `dialog.tlk` somewhere safe.

### Where to place the file

For the Steam version on macOS, you should place the compiled `dialog.tlk` into:

`~/Library/Steam/steamapps/common/swkotor/`

Then:

1) In Finder, **right-click the game app icon** → **Show Package Contents**  
2) Navigate to: `Contents/Assets/`  
3) Copy your new `dialog.tlk` into `Contents/Assets/` (replacing the existing one after making a backup)

---

## Troubleshooting

### “It looks stuck / no output for a while”

By default, progress prints every 100 translated entries (`--save-every 100`).  
If each request takes a second or more, it can feel silent for a while.

- Reduce the save interval:

```bash
./.venv/bin/python kotor_translate_json.py ... --save-every 25
```

### Translation errors / blocked requests

If Google blocks requests or your network requires a proxy, you may see warnings and entries will remain in English.

Things to try:

- Add a delay: `--sleep 0.2` or `--sleep 0.5`
- Run again later (it will resume from checkpoint)
- Use a different translation provider (requires code changes)

---

## Notes / Disclaimer

- This is a community toolchain for modding. Use at your own risk.
- Always keep backups of original game files.
- Machine translation quality varies; consider doing a manual pass for best results.

