from bizmate.domain.errors import FeaturePending


def prepare_handoff():
    """Devi BM-15: detect unavailable capability, ask confirmation, verify support reference."""
    raise FeaturePending("BM-15", "Human-support handoff is not implemented.")
