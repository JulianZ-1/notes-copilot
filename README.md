# Notes copilot, step 1: ingest and chunk

`ingest.py` reads a OneNote section exported as `.mht`, finds each page (title, date, text),
splits the pages into chunks of about 300-500 words, and saves them to `chunks.json`.

## Run it on Windows

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

## Check the output

The script prints the pages it found first. If that list looks wrong (one page instead of many,
or titles that aren't titles), page detection didn't match your export. Send back:

- the printed page list, but with titles replaced by "xxx", or the error message, and
- the HTML around one page title, with the text replaced by "xxx". Open the .mht in a text
  editor (Notepad works) and copy the few lines around a title.

Don't send note content.

## Files

- `ingest.py` - the script.
- `sample_data/fake_section.mht` - a made-up OneNote export (fictional "Contoso" content).
- `sample_data/make_fake_mht.py` - builds the fake file, so you can see how an MHT is put together.
- `chunks.json` - the output (created when you run the script). Keep it out of anywhere public,
  since for your real file it contains your notes.
