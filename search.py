"""
Step 3: find the chunks most related to a question.

    python search.py "how do we roll back a deployment?"
    python search.py "webhook failures" --top 3
    python search.py "webhook failures" --fake    # if you ran embed.py --fake

What it does:
  1. Turns your question into a vector with the same model embed.py used.
  2. Compares it to every saved chunk vector with cosine similarity: a score
     of how closely two vectors point the same way (1.0 = same meaning,
     around 0 = unrelated).
  3. Prints the best-scoring chunks with their page title and score.

No database needed: a few thousand vectors fit in memory and numpy compares
them all in a few milliseconds.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from embed import file_sha256, get_embedder, normalize

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_index(vectors_path):
    """Load the vectors, their index, and the chunks they belong to."""
    vectors = np.load(vectors_path)
    index_path = Path(vectors_path).with_name(Path(vectors_path).stem + "_index.json")
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    # If chunks.json was re-made after embedding, the rows no longer line up.
    if file_sha256(index["chunks_file"]) != index["chunks_sha256"]:
        sys.exit(f"{index['chunks_file']} changed since the vectors were made. Run embed.py again.")

    with open(index["chunks_file"], encoding="utf-8") as f:
        chunks_by_id = {c["id"]: c for c in json.load(f)}

    chunks = [chunks_by_id[cid] for cid in index["chunk_ids"]]  # row N -> chunk
    return vectors, index, chunks


def search(question, vectors, chunks, embedder, top_k=5):
    """Return the top_k (score, chunk) pairs, best first."""
    query = normalize(embedder.embed([question]))[0]

    # The vectors are all length 1, so a dot product is the cosine similarity.
    # vectors @ query gives one score per chunk in a single step.
    scores = vectors @ query

    best = np.argsort(-scores)[:top_k]  # row numbers of the highest scores
    return [(float(scores[i]), chunks[i]) for i in best]


def main():
    parser = argparse.ArgumentParser(description="Search your notes by meaning.")
    parser.add_argument("question", help="what you're looking for, in plain words")
    parser.add_argument("--top", type=int, default=5, help="how many chunks to show (default: 5)")
    parser.add_argument("--vectors", default="vectors.npy", help="made by embed.py (default: vectors.npy)")
    parser.add_argument("--fake", action="store_true", help="use the offline fake embedder (for testing)")
    args = parser.parse_args()

    vectors, index, chunks = load_index(args.vectors)
    embedder = get_embedder(args.fake)

    # Vectors from different models live in different "spaces": comparing them
    # gives meaningless scores, so stop early instead.
    if embedder.name != index["embedder"]:
        sys.exit(f"The vectors were made with {index['embedder']}, but this search uses {embedder.name}. "
                 f"Run embed.py again{' with --fake' if args.fake else ' without --fake'}, "
                 f"or match the --fake flag here.")

    print(f"Top {args.top} chunks for: {args.question!r}\n")
    for rank, (score, chunk) in enumerate(search(args.question, vectors, chunks, embedder, args.top), 1):
        preview = chunk["text"][:300].replace("\n", " ")
        print(f"{rank}. [{score:.3f}] {chunk['page_title']} (part {chunk['chunk_index'] + 1}, {chunk['page_date'] or 'no date'})")
        print(f"   {preview}{'...' if len(chunk['text']) > 300 else ''}\n")


if __name__ == "__main__":
    main()
