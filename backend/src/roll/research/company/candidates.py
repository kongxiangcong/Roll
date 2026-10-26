"""Deterministic validation of provisional company operating analysis."""
import re
from datetime import date
from pydantic import Field, ValidationError
from .models import Command
from .service import fail


class Claim(Command):
    text: str = Field(min_length=1, max_length=3000)
    fact_version_ids: list[str] = Field(max_length=80)
    gap_reason: str | None = Field(max_length=2000)


class Event(Command):
    description: str = Field(min_length=1, max_length=1000)
    date: str | None
    date_unknown_reason: str | None = Field(max_length=1000)
    date_fact_version_ids: list[str] = Field(default_factory=list, max_length=80)


class Hypothesis(Command):
    key: str = Field(min_length=1, max_length=128)
    previous_version_id: str | None
    business: str = Field(min_length=1, max_length=160)
    statement: str = Field(min_length=1, max_length=3000)
    horizon: str = Field(min_length=1, max_length=1000)
    observation_metrics: list[str] = Field(min_length=1, max_length=20)
    support_fact_version_ids: list[str] = Field(max_length=80)
    counter_fact_version_ids: list[str] = Field(max_length=80)
    invalidation_conditions: list[str] = Field(min_length=1, max_length=20)
    next_validation_event: Event
    gaps: list[str] = Field(max_length=30)
    change_reason: str = Field(min_length=1, max_length=2000)


class Candidate(Command):
    company_id: str
    input_sha256: str
    business_structure: list[dict] = Field(max_length=20)
    attention_reasons: list[dict] = Field(max_length=20)
    counterevidence: list[dict] = Field(max_length=20)
    hypotheses: list[dict] = Field(max_length=5)
    insufficient_hypotheses_reason: str | None = Field(max_length=2000)
    limitations: list[str] = Field(min_length=1, max_length=30)
    valuation_unavailable_reason: str = Field(min_length=1, max_length=2000)


def validate_candidate(research, packet, raw):
    try:
        candidate = Candidate.model_validate(raw).model_dump()
    except ValidationError:
        fail('MODEL_OUTPUT_INVALID', 'Candidate envelope has invalid structure')
    if len(candidate['hypotheses']) < 3 and not candidate['insufficient_hypotheses_reason']:
        fail('EVIDENCE_GAP_REQUIRED', 'Fewer than three hypotheses requires an explicit evidence insufficiency reason')
    facts = {f['version_id']: f for f in packet['payload']['facts']}
    rejections, keys = [], set()

    def references(ids):
        for identifier in ids:
            if identifier not in facts:
                try:
                    external = research.fact(identifier)
                except Exception:
                    external = None
                fail('CROSS_COMPANY_REFERENCE' if external and external['company_id'] != packet['company_id'] else 'UNKNOWN_CITATION',
                     'Citation is outside the frozen company evidence packet')
        return [facts[i] for i in ids]

    def numbers(text, cited):
        # This checks literal numeric support, never semantic factual truth.
        tokens = lambda s: set(re.findall(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?', s.replace(',', '')))
        permitted = tokens(' '.join(str(f.get(k) or '') for f in cited for k in ['value', 'period_start', 'period_end']))
        if tokens(text) - permitted:
            fail('UNSUPPORTED_NUMBER', 'Numeric assertions require literal support in the cited facts')

    def checked(field, item):
        if field != 'hypotheses':
            value = Claim.model_validate(item).model_dump()
            cited = references(value['fact_version_ids'])
            if not cited and not value['gap_reason']:
                fail('EVIDENCE_GAP_REQUIRED', 'An unsupported claim must be marked unable to judge with a gap')
            numbers(value['text'], cited)
            value['judgment_status'] = 'EVIDENCE_BOUND' if cited else 'UNABLE_TO_JUDGE'
            return value
        value = Hypothesis.model_validate(item).model_dump()
        if value['key'] in keys:
            fail('HYPOTHESIS_CONFLICT', 'Repeated hypothesis key requires one explicit candidate revision')
        keys.add(value['key'])
        cited = references(value['support_fact_version_ids'] + value['counter_fact_version_ids'])
        if not cited and not value['gaps']:
            fail('EVIDENCE_GAP_REQUIRED', 'An unsupported hypothesis must preserve its evidence gap')
        value['overlapping_evidence_roles'] = sorted(set(value['support_fact_version_ids']) & set(value['counter_fact_version_ids']))
        previous = next((h for h in packet['payload']['prior_hypotheses'] if h['key'] == value['key']), None)
        if (previous['version_id'] if previous else None) != value['previous_version_id']:
            fail('HYPOTHESIS_REVISION_CONFLICT', 'Hypothesis revision must name the frozen previous version')
        event = value['next_validation_event']
        if event['date']:
            date.fromisoformat(event['date'])
            dated = references(event['date_fact_version_ids'])
            if not dated or not any(event['date'] in (f['value'] or '') for f in dated):
                fail('EVENT_DATE_UNSUPPORTED', 'A scheduled date must occur literally in cited frozen evidence')
        elif not event['date_unknown_reason']:
            fail('EVIDENCE_GAP_REQUIRED', 'Unknown validation date must retain its reason')
        numbers(value['statement'], cited)
        return value

    for field in ['business_structure', 'attention_reasons', 'counterevidence', 'hypotheses']:
        accepted = []
        for index, item in enumerate(candidate[field]):
            try:
                accepted.append(checked(field, item))
            except (ValidationError, ValueError):
                rejections.append({'field': field, 'index': index, 'code': 'MODEL_OUTPUT_INVALID'})
            except Exception as error:
                from fastapi import HTTPException
                if not isinstance(error, HTTPException):
                    raise
                rejections.append({'field': field, 'index': index, 'code': error.detail['code']})
        candidate[field] = accepted
    if len(candidate['hypotheses']) < 3 and not candidate['insufficient_hypotheses_reason']:
        candidate['insufficient_hypotheses_reason'] = 'Host rejected unsupported candidates; evidence is insufficient for three usable hypotheses'
    return candidate, rejections
