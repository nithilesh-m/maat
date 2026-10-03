from __future__ import annotations

from pathlib import Path

from rank_bm25 import BM25Okapi


class Retriever:
    def __init__(self, corpus_dirs: list[str]) -> None:
        self.chunks = [
            p.strip()
            for d in corpus_dirs
            for f in sorted(Path(d).glob("*.md"))
            for p in f.read_text(encoding="utf-8").split("\n\n")
            if p.strip()
        ]
        self._bm = BM25Okapi([c.lower().split() for c in self.chunks]) if self.chunks else None

    def top(self, query: str, k: int) -> list[str]:
        if not self._bm:
            return []
        scores = self._bm.get_scores(query.lower().split())
        return [self.chunks[i] for i in sorted(range(len(scores)), key=lambda i: -scores[i])[:k]]
