"""
Step 2: turn each chunk into a vector (a list of numbers) so it can be searched.

    python embed.py                      # uses your Foundry model from .env
    python embed.py --fake               # offline stand-in, no key needed

What it does:
  1. Reads chunks.json (made by ingest.py).
  2. Sends the chunk texts, a batch at a time, to your embedding model in
     Microsoft AI Foundry. The model sends back one vector per chunk. Chunks
     about similar things get vectors that point in similar directions.
  3. Saves all vectors to vectors.npy (one row per chunk, same order as
     chunks.json), plus vectors_index.json, which says which chunk each row
     is and which model made the vectors.

Your notes stay on your PC. Foundry only sees the text while it computes the
vectors, like a calculator; the vectors are saved here, locally.

Run it again whenever chunks.json changes.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# How many chunks to send per request. Fewer requests is faster, but a very
# big batch can hit the model's per-request token limit.
BATCH_SIZE = 32

# Size of the fake vectors. Real models use 1536 or 3072; this is plenty for testing.
FAKE_DIMENSIONS = 512


# ---------------------------------------------------------------------------
# What we send to the model for each chunk
# ---------------------------------------------------------------------------
def text_for_embedding(chunk):
    """The page title is added in front of the chunk text.

    A chunk from the middle of a long page often doesn't mention what the page
    is about; the title gives the model that context, so searches match better.
    """
    return f"{chunk['page_title']}\n\n{chunk['text']}"


# ---------------------------------------------------------------------------
# Two embedders with the same shape: a list of texts in, a 2D array out.
# ---------------------------------------------------------------------------
class FoundryEmbedder:
    """Calls your embedding deployment in Microsoft AI Foundry (Azure OpenAI)."""

    def __init__(self):
        from dotenv import load_dotenv
        from openai import AzureOpenAI

        load_dotenv()  # reads .env into environment variables
        missing = [name for name in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
                                     "AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
                   if not os.getenv(name)]
        if missing:
            sys.exit(f"Missing in .env: {', '.join(missing)}. Copy .env.example to .env and fill it in.")

        self.client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            max_retries=5,  # waits and retries automatically if you hit a rate limit
        )
        # In Azure you call a model by the *deployment name* you gave it.
        self.deployment = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
        self.name = f"foundry:{self.deployment}"

    def embed(self, texts):
        response = self.client.embeddings.create(model=self.deployment, input=texts)
        # The response holds one item per input text, in the same order.
        return np.array([item.embedding for item in response.data], dtype=np.float32)


class FakeEmbedder:
    """Offline stand-in for testing, no key or network needed.

    It's the "hashing trick": every word is mapped to one of FAKE_DIMENSIONS
    slots, and the vector counts how often each slot's words appear. So two
    texts score as similar when they share words. A real model is far smarter
    (it knows "deploy" and "release" are related), but the plumbing is the same.
    """

    name = "fake"

    def embed(self, texts):
        vectors = np.zeros((len(texts), FAKE_DIMENSIONS), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                slot = int(hashlib.md5(word.encode()).hexdigest(), 16) % FAKE_DIMENSIONS
                vectors[row, slot] += 1
        return vectors


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def get_embedder(fake):
    return FakeEmbedder() if fake else FoundryEmbedder()


def normalize(vectors):
    """Scale every vector to length 1.

    Then the dot product of two vectors *is* their cosine similarity, which
    makes searching a single matrix multiplication (see search.py).
    """
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(lengths, 1e-12)  # avoid dividing by zero


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Embed chunks.json into vectors.npy.")
    parser.add_argument("--chunks", default="chunks.json", help="input from ingest.py (default: chunks.json)")
    parser.add_argument("--out", default="vectors.npy", help="output vectors (default: vectors.npy)")
    parser.add_argument("--fake", action="store_true", help="use the offline fake embedder (for testing)")
    args = parser.parse_args()

    with open(args.chunks, encoding="utf-8") as f:
        chunks = json.load(f)
    if not chunks:
        sys.exit(f"{args.chunks} has no chunks. Run ingest.py first.")

    embedder = get_embedder(args.fake)
    texts = [text_for_embedding(c) for c in chunks]

    batches = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        print(f"Embedding chunks {start + 1}-{start + len(batch)} of {len(texts)}...")
        batches.append(embedder.embed(batch))
    vectors = normalize(np.vstack(batches))

    np.save(args.out, vectors)

    # The index ties row N of vectors.npy back to its chunk, and remembers
    # which model made the vectors: a question must be embedded by the same
    # model, or the numbers can't be compared.
    index_path = Path(args.out).with_name(Path(args.out).stem + "_index.json")
    index = {
        "embedder": embedder.name,
        "dimensions": int(vectors.shape[1]),
        "chunks_file": args.chunks,
        # A fingerprint of chunks.json, so search.py can tell if it changed since.
        "chunks_sha256": file_sha256(args.chunks),
        "chunk_ids": [c["id"] for c in chunks],
    }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"\nSaved {vectors.shape[0]} vectors of {vectors.shape[1]} numbers each "
          f"to {args.out} (index: {index_path}), using {embedder.name}.")


if __name__ == "__main__":
    main()
