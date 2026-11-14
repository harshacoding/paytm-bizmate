from bizmate.domain.errors import FeaturePending


def segment_inactive_customers():
    """Devi BM-13/BM-14: consent, 30-day boundary, cost, approved send and status read."""
    raise FeaturePending("BM-13", "Customer segmentation is not implemented.")
