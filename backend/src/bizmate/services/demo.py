from bizmate.domain.models import DemoPreview, Merchant

MERCHANTS = {
    "merchant_demo": Merchant(
        merchant_id="merchant_demo",
        display_name="Sharma General Store",
        scopes=["payments:read", "customers:read", "tickets:write", "campaigns:write"],
    ),
    "merchant_other": Merchant(
        merchant_id="merchant_other",
        display_name="Second Demo Merchant",
        scopes=["payments:read"],
    ),
}


def preview() -> DemoPreview:
    # PRD ground truth for UI development, NOT a reconciliation/segmentation implementation.
    return DemoPreview(
        description="Static synthetic preview only. No investigation or campaign has run.",
        settlement={
            "sales_paise": 2000000,
            "commission_paise": 24000,
            "gst_paise": 4320,
            "refunds_paise": 80000,
            "chargeback_paise": 35000,
            "expected_paise": 1856680,
            "credit_paise": 1840000,
            "residual_paise": 16680,
            "source_references": [
                "fixture:txn-001",
                "fixture:deductions-001",
                "fixture:credit-001",
            ],
        },
        campaign={
            "histories_count": 200,
            "inactivity_days": 30,
            "eligible_count": 120,
            "estimated_cost_paise": 24000,
            "delivered_count": 118,
            "failed_count": 2,
        },
    )
