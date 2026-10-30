"""The personal lexicon: the product's core data structure.

A speaker (or family, or speech-language pathologist) builds a lexicon
of the 50-300 phrases they actually say. Each phrase is embedded ONCE,
through the gateway's /v1/embeddings dispatch, and the vector is cached
on the entry. Reranking an n-best list never re-embeds the lexicon.
One-tap corrections grow the lexicon: a corrected phrase is added (or
its use count incremented) so the same utterance is easier next time.
"""
from __future__ import annotations

from app import gateway

MIN_PHRASES = 50   # design target range from the product brief
MAX_PHRASES = 300  # (a target, not a hard cap enforced in v0.1.0)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


class Lexicon:
    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}

    def __len__(self) -> int:
        return len(self.entries)

    def add(self, phrase: str, category: str = "custom") -> dict:
        key = _norm(phrase)
        if not key:
            raise ValueError("phrase must not be empty")
        if key in self.entries:
            return self.entries[key]
        vec = gateway.dispatch_embeddings(key)["data"][0]["embedding"]
        self.entries[key] = {"phrase": key, "category": category,
                             "uses": 0, "embedding": vec}
        return self.entries[key]

    def correct(self, phrase: str, category: str = "learned") -> dict:
        """One-tap correction: the phrase the speaker actually meant.

        Adds it to the lexicon if new (this is how the lexicon grows)
        and counts the use either way.
        """
        entry = self.add(phrase, category=category)
        entry["uses"] += 1
        return entry

    def get(self, phrase: str) -> dict | None:
        return self.entries.get(_norm(phrase))

    def phrases(self) -> list[str]:
        return sorted(self.entries)

    def board(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for e in self.entries.values():
            out.setdefault(e["category"], []).append(e["phrase"])
        return {k: sorted(v) for k, v in sorted(out.items())}

    def public(self) -> list[dict]:
        return [{"phrase": e["phrase"], "category": e["category"],
                 "uses": e["uses"]}
                for e in sorted(self.entries.values(),
                                key=lambda x: x["phrase"])]
