"""
Step 1 of the notes copilot: turn a OneNote .mht export into text chunks.

What it does:
  1. Reads the .mht file and pulls out the HTML inside it.
  2. Finds each OneNote page (title + text) in that HTML.
  3. Splits each page into chunks of roughly 300-500 words.
  4. Saves the chunks to a JSON file and prints a few so you can check them.

Usage (Windows, from this folder):
  python ingest.py "C:\\path\\to\\MySection.mht"
  python ingest.py sample_data\\fake_section.mht --out chunks.json --show 3
"""

import argparse
import email
import json
import re
import sys
from email import policy
from pathlib import Path

from bs4 import BeautifulSoup

# Windows consoles sometimes can't print characters like "é" or "–".
# This makes print() replace them instead of crashing.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# A paragraph counts as a page title if its font is at least this big.
# OneNote writes page titles at 20pt and normal text at 11pt.
TITLE_MIN_FONT_PT = 18

# OneNote writes the page's date and time under the title in this grey.
DATE_COLOR = "#767676"

# The HTML elements we treat as one "block" of text, in document order.
# <tr> is a table row: we join its cells with " | " so tables stay readable.
BLOCK_TAGS = ["p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"]


# ---------------------------------------------------------------------------
# 1. Read the MHT file
# ---------------------------------------------------------------------------
def read_html_parts(mht_path):
    """Return the HTML parts inside an .mht file, as BeautifulSoup objects.

    An .mht file is a MIME message (the same format as an email). Python's
    built-in `email` module can open it and walk through its parts: usually
    one HTML part plus some images.
    """
    with open(mht_path, "rb") as f:
        message = email.message_from_binary_file(f, policy=policy.default)

    soups = []
    for part in message.walk():  # walk() visits every part, nested or not
        if part.get_content_type() != "text/html":
            continue
        # decode=True undoes the transfer encoding (quoted-printable/base64)
        # and gives us raw bytes.
        raw = part.get_payload(decode=True)
        # Let BeautifulSoup work out the text encoding, using the part's
        # declared charset if there is one.
        soups.append(BeautifulSoup(raw, "html.parser", from_encoding=part.get_content_charset()))
    return soups


# ---------------------------------------------------------------------------
# 2. Find the pages
# ---------------------------------------------------------------------------
def clean(text):
    """Collapse runs of spaces, tabs, newlines and &nbsp; into single spaces."""
    return " ".join(text.split())


def font_size_pt(element):
    """Largest font-size (in pt) set on this element or anything inside it."""
    styles = [element.get("style", "")]
    styles += [child.get("style", "") for child in element.find_all(style=True)]
    sizes = re.findall(r"font-size:\s*([\d.]+)pt", " ".join(styles))
    return max((float(s) for s in sizes), default=0)


def is_grey_date(element):
    styles = element.get("style", "") + " ".join(c.get("style", "") for c in element.find_all(style=True))
    return DATE_COLOR in styles.lower()


def iter_blocks(soup):
    """Yield (element, text) for each block of text, in document order.

    We skip blocks nested inside other blocks (e.g. a <p> inside a table
    row) so the same text isn't counted twice.
    """
    for el in soup.find_all(BLOCK_TAGS):
        if el.find_parent(BLOCK_TAGS):
            continue
        if el.name == "tr":
            cells = [clean(td.get_text(" ")) for td in el.find_all(["td", "th"])]
            text = " | ".join(c for c in cells if c)
        else:
            text = clean(el.get_text(" "))
        if text:
            yield el, text


def split_into_pages(soup, fallback_title):
    """Group the blocks of one HTML document into pages.

    A new page starts at every block whose font is big enough to be a title.
    The grey date/time lines right after a title are saved as the page date.
    Returns a list of dicts: {"title", "date", "paragraphs"}.
    """
    pages = []
    current = None

    for el, text in iter_blocks(soup):
        if el.name in ("p", "h1") and font_size_pt(el) >= TITLE_MIN_FONT_PT:
            current = {"title": text, "date": "", "paragraphs": []}
            pages.append(current)
            continue

        if current is None:
            # Text before the first title (or a file with no titles at all).
            current = {"title": fallback_title, "date": "", "paragraphs": []}
            pages.append(current)

        if not current["paragraphs"] and is_grey_date(el):
            current["date"] = (current["date"] + " " + text).strip()
        else:
            current["paragraphs"].append(text)

    return [p for p in pages if p["paragraphs"]]  # drop empty pages


# ---------------------------------------------------------------------------
# 3. Chunk the pages
# ---------------------------------------------------------------------------
def chunk_paragraphs(paragraphs, target_words, max_words):
    """Pack paragraphs into chunks of about target_words (never more than max_words).

    We split on paragraph boundaries so a chunk doesn't stop mid-thought.
    A single paragraph longer than max_words is cut into word-count pieces.
    """
    # First, cut any huge paragraph into pieces that fit.
    pieces = []
    for para in paragraphs:
        words = para.split()
        for start in range(0, len(words), max_words):
            pieces.append(" ".join(words[start:start + max_words]))

    chunks, current, current_len = [], [], 0
    for piece in pieces:
        n = len(piece.split())
        # Start a new chunk if this piece would push us past the max,
        # or if we've already reached the target size.
        if current and (current_len + n > max_words or current_len >= target_words):
            chunks.append("\n".join(current))
            current, current_len = [], 0
        current.append(piece)
        current_len += n
    if current:
        chunks.append("\n".join(current))
    return chunks


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------
def ingest(mht_path, target_words=400, max_words=500):
    mht_path = Path(mht_path)
    soups = read_html_parts(mht_path)
    if not soups:
        sys.exit(f"No HTML found inside {mht_path}. Is it really an .mht export?")

    pages = []
    for soup in soups:
        title_tag = soup.find("title")
        fallback = clean(title_tag.get_text()) if title_tag else mht_path.stem
        pages += split_into_pages(soup, fallback)

    chunks = []
    for page in pages:
        for i, text in enumerate(chunk_paragraphs(page["paragraphs"], target_words, max_words)):
            chunks.append({
                "id": f"{len(chunks):04d}",
                "source_file": mht_path.name,
                "page_title": page["title"],
                "page_date": page["date"],
                "chunk_index": i,  # position of this chunk within its page
                "word_count": len(text.split()),
                "text": text,
            })
    return pages, chunks


def main():
    parser = argparse.ArgumentParser(description="Chunk a OneNote .mht export into JSON.")
    parser.add_argument("mht_file", help="path to the .mht file")
    parser.add_argument("--out", default="chunks.json", help="output JSON file (default: chunks.json)")
    parser.add_argument("--target-words", type=int, default=400)
    parser.add_argument("--max-words", type=int, default=500)
    parser.add_argument("--show", type=int, default=3, help="how many chunks to print as samples")
    args = parser.parse_args()

    pages, chunks = ingest(args.mht_file, args.target_words, args.max_words)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    # Summary: if page detection is wrong, you'll see it here first
    # (e.g. 1 page when you expected 20).
    print(f"Found {len(pages)} pages:")
    for page in pages:
        words = sum(len(p.split()) for p in page["paragraphs"])
        print(f"  - {page['title'][:60]!r}  ({words} words, {page['date'] or 'no date'})")
    print(f"\nWrote {len(chunks)} chunks to {args.out}\n")

    for chunk in chunks[:args.show]:
        preview = chunk["text"][:300].replace("\n", " ")
        print(f"--- chunk {chunk['id']} | {chunk['page_title']} #{chunk['chunk_index']} | {chunk['word_count']} words")
        print(preview + ("..." if len(chunk["text"]) > 300 else ""))
        print()


if __name__ == "__main__":
    main()
