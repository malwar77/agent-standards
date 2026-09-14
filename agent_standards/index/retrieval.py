"""Lexical retrieval (BM25-style) — local, keyless, deterministic.

Given a task description, score approved standards by lexical relevance and
return only the top-k within a token budget. Precision over recall: injecting
three truly relevant standards beats dumping thirty.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .store import Standard

TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list:
    return TOKEN_RE.findall(text.lower())


def _standard_text(std: Standard) -> str:
    # title and tags weighted x3 — they carry the most signal
    parts = [std.title] * 3 + [std.body] + [" ".join(std.tags or [])] * 3
    return " ".join(parts)


class BM25Index:
    def __init__(self, standards: list):
        self.standards = list(standards)
        self.docs = [tokenize(_standard_text(s)) for s in self.standards]
        self.doc_len = [len(d) for d in self.docs]
        self.avgdl = (sum(self.doc_len) / len(self.docs)) if self.docs else 1.0
        self.df = Counter()
        for doc in self.docs:
            for term in set(doc):
                self.df[term] += 1
        self.N = len(self.docs) or 1
        self.k1, self.b = 1.5, 0.75

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query: str, idx: int) -> float:
        q = tokenize(query)
        doc, dl = self.docs[idx], self.doc_len[idx]
        tf = Counter(doc)
        s = 0.0
        for term in q:
            if term not in tf:
                continue
            idf = self._idf(term)
            denom = tf[term] + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            s += idf * tf[term] * (self.k1 + 1) / denom
        return s

    def search(self, query: str, top_k: int = 5, min_score: float = 0.0):
        scored = [(self.score(query, i), self.standards[i], i)
                  for i in range(len(self.standards))]
        scored = [(s, std) for s, std, _ in scored if s > min_score]
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        return scored[:top_k]


def build_index(standards: list) -> BM25Index:
    return BM25Index(standards)


def retrieve(query: str, standards: list, top_k: int = 5):
    """Pure function wrapper for easy testing: query -> ranked standards."""
    return build_index(standards).search(query, top_k=top_k)
