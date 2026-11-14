from collections import defaultdict
from typing import Literal

from pydantic import AwareDatetime

from bizmate.domain.context import MerchantContext, require_context
from bizmate.domain.models import Model, Scope
from bizmate.domain.types import MAX_SAFE_INTEGER, Identifier, Paise
from bizmate.services.mock_models import PaymentRecord, SettlementReport
from bizmate.services.mocks import MockServices


class ReconciliationRequest(Model):
    settlement_reference: Identifier = "settlement-001"


class ProofLine(Model):
    amount_paise: Paise | None
    source_references: tuple[Identifier, ...] = ()
    status: Literal["known", "missing", "conflicting"]
    explanation: str


class SettlementProof(Model):
    merchant_id: Identifier
    settlement_reference: Identifier
    captured_at: AwareDatetime
    sales: ProofLine
    commission: ProofLine
    gst: ProofLine
    refunds: ProofLine
    chargeback: ProofLine
    expected: ProofLine
    credit: ProofLine
    residual: ProofLine
    sources: tuple[PaymentRecord, ...]
    status: Literal["complete", "incomplete", "conflicting"]
    warnings: tuple[str, ...]
    simulated: Literal[True] = True


def reconcile_settlement(context: MerchantContext, report: SettlementReport) -> SettlementProof:
    """Source-linked integer arithmetic. Missing components remain unknown, including deductions."""
    require_context(context)
    context.require(Scope.PAYMENTS_READ)
    report = SettlementReport.model_validate(report)
    records = tuple(
        record
        for record in report.records
        if record.settlement_reference == report.settlement_reference
        and record.available_at <= report.captured_at
    )
    by_reference: dict[str, list[PaymentRecord]] = defaultdict(list)
    for record in records:
        by_reference[record.reference].append(record)
    conflict_kinds = set()
    sources = []
    warnings = []
    for reference, values in sorted(by_reference.items()):
        if any(value != values[0] for value in values[1:]):
            conflict_kinds.update(value.kind for value in values)
            warnings.append(f"Conflicting records share source reference {reference}.")
        else:
            sources.append(values[0])
    lines = {}
    for name, kind in [
        ("sales", "sale"),
        ("commission", "commission"),
        ("gst", "gst"),
        ("refunds", "refund"),
        ("chargeback", "chargeback"),
        ("credit", "credit"),
    ]:
        matching = [record for record in sources if record.kind == kind]
        references = tuple(record.reference for record in matching)
        if kind in conflict_kinds:
            lines[name] = ProofLine(
                amount_paise=None,
                source_references=tuple(
                    sorted(
                        reference
                        for reference, values in by_reference.items()
                        if any(value.kind == kind for value in values)
                    )
                ),
                status="conflicting",
                explanation="Source records conflict. Amount is unknown.",
            )
        elif not matching:
            lines[name] = ProofLine(
                amount_paise=None,
                status="missing",
                explanation="No available source evidence. Amount is unknown.",
            )
        else:
            total = sum(record.amount_paise for record in matching)
            if total > MAX_SAFE_INTEGER:
                lines[name] = ProofLine(
                    amount_paise=None,
                    source_references=references,
                    status="conflicting",
                    explanation="Total exceeds the supported exact money range.",
                )
            else:
                lines[name] = ProofLine(
                    amount_paise=total,
                    source_references=references,
                    status="known",
                    explanation=f"Sum of source-linked {name} records.",
                )

    def derived(names, amount, explanation):
        inputs = [lines[name] for name in names]
        references = tuple(
            sorted({reference for line in inputs for reference in line.source_references})
        )
        if any(line.status != "known" for line in inputs):
            return ProofLine(
                amount_paise=None,
                source_references=references,
                status="conflicting"
                if any(line.status == "conflicting" for line in inputs)
                else "missing",
                explanation="Required evidence is incomplete or conflicting. Result is unknown.",
            )
        value = amount()
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            return ProofLine(
                amount_paise=None,
                source_references=references,
                status="conflicting",
                explanation="Result exceeds the supported exact money range.",
            )
        return ProofLine(
            amount_paise=value,
            source_references=references,
            status="known",
            explanation=explanation,
        )

    deductions = ["commission", "gst", "refunds", "chargeback"]
    lines["expected"] = derived(
        ["sales", *deductions],
        lambda: lines["sales"].amount_paise - sum(lines[name].amount_paise for name in deductions),
        "Sales less commission, GST, refunds and chargeback, calculated in integer paise.",
    )
    lines["residual"] = derived(
        ["expected", "credit"],
        lambda: lines["expected"].amount_paise - lines["credit"].amount_paise,
        "Expected settlement less bank credit. Positive means unexplained shortfall.",
    )
    if len(records) != len(report.records):
        warnings.append("Records for other settlements or future availability were excluded.")
    if any(line.status == "conflicting" for line in lines.values()):
        status = "conflicting"
    elif any(line.status == "missing" for line in lines.values()):
        status = "incomplete"
    else:
        status = "complete"
    return SettlementProof(
        merchant_id=context.merchant_id,
        settlement_reference=report.settlement_reference,
        captured_at=report.captured_at,
        sources=tuple(sources),
        status=status,
        warnings=tuple(warnings),
        **lines,
    )


def prepare_settlement_proof(
    context: MerchantContext, services: MockServices, request: ReconciliationRequest
) -> SettlementProof:
    require_context(context)
    context.require(Scope.PAYMENTS_READ)
    request = ReconciliationRequest.model_validate(request)
    report = services.report(context).with_updates(
        settlement_reference=request.settlement_reference
    )
    return reconcile_settlement(context, report)
