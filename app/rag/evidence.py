from app.core.models import Evidence


class EvidenceRanker:
    """Deduplicates and ranks repository evidence."""

    def rank(
        self,
        evidence: list[Evidence],
        *,
        top_k: int = 10,
    ) -> list[Evidence]:
        """Deduplicate evidence and return the strongest results."""

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than 0."
            )

        if not evidence:
            return []

        best_evidence: dict[str, Evidence] = {}

        for item in evidence:
            key = self._evidence_key(item)

            existing = best_evidence.get(key)

            if existing is None or item.score > existing.score:
                best_evidence[key] = item

        ranked = sorted(
            best_evidence.values(),
            key=lambda item: (
                -item.score,
                item.source,
                item.start_line,
                item.end_line,
            ),
        )

        return ranked[:top_k]

    @staticmethod
    def _evidence_key(
        evidence: Evidence,
    ) -> str:
        """Create a stable identity for an evidence chunk."""

        return (
            f"{evidence.source}:"
            f"{evidence.start_line}:"
            f"{evidence.end_line}:"
            f"{evidence.content}"
        )