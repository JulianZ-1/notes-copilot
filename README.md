# Notes copilot

Search your OneNote notes by meaning. Everything is saved on your PC; Microsoft AI Foundry is only
called to turn text into vectors.

## Step 1: ingest and chunk

`ingest.py` reads a OneNote section exported as `.mht`, finds each page (title, date, text),
splits the pages into chunks of about 300-500 words, and saves them to `chunks.json`.

### Run it on Windows

```powershell
cd path\to\notes-copilot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Try it on the fake sample first
python ingest.py sample_data\fake_section.mht

# Then on your real export (OneNote: File > Export > Section > Single File Web Page)
python ingest.py "C:\path\to\YourSection.mht" --out chunks.json
```

Options: `--target-words 400`, `--max-words 500`, `--show 3` (how many sample chunks to print).

### Check the output

The script prints the pages it found first. If that list looks wrong (one page instead of many,
or titles that aren't titles), page detection didn't match your export. Send back:

- the printed page list, but with titles replaced by "xxx", or the error message, and
- the HTML around one page title, with the text replaced by "xxx". Open the .mht in a text
  editor (Notepad works) and copy the few lines around a title.

Don't send note content.

## Step 2: make the chunks searchable (embed.py)

`embed.py` sends each chunk (with its page title in front) to your embedding model in Foundry and
saves the vectors it gets back to `vectors.npy`, plus `vectors_index.json` linking each vector to its
chunk. Run it once, and again whenever you re-run `ingest.py`.

One-time setup: in Foundry, deploy an embedding model (for example `text-embedding-3-small`). Then:

```powershell
copy .env.example .env
notepad .env    # paste your endpoint, key and deployment name
```

```powershell
python embed.py --fake   # try the offline stand-in first, no key needed
python embed.py          # the real thing, using your Foundry model
```

## Step 3: search (search.py)

```powershell
python search.py "how do we roll back a deployment?"
python search.py "payment webhook failures" --top 3
```

It turns your question into a vector with the same model and prints the 5 closest chunks, with page
title and a similarity score (1.0 = same meaning, near 0 = unrelated). If you made the vectors with
`--fake`, add `--fake` here too; the script stops if the two don't match, since vectors from different
models can't be compared.

The fake embedder only matches shared words, so its scores are low and it misses synonyms. Your real
Foundry model will do much better; the fake one only proves the plumbing works.

## Files

- `ingest.py` - the script.
- `sample_data/fake_section.mht` - a made-up OneNote export (fictional "Contoso" content).
- `sample_data/make_fake_mht.py` - builds the fake file, so you can see how an MHT is put together.
- `embed.py`, `search.py` - steps 2 and 3.
- `.env.example` - template for your Foundry settings. Your real `.env` is gitignored.
- `chunks.json`, `vectors.npy`, `vectors_index.json` - outputs, created when you run the scripts.
  They're gitignored: for your real file they're made from your notes.
