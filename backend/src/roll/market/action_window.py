"""Consume explicit saved reported action rows in a registered reference window.

This successor adds no event identity, effective instant, lifecycle or admissibility.
The predecessor and obligation audit remain immutable and are revalidated by owners.
"""
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from roll.accounts.ledger import encode, now
from roll.market.rules import SHANGHAI


class ActionWindowCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    protocol_id: str = Field(min_length=1)
    predecessor_packet_id: str = Field(min_length=1)
    known_obligation_audit_id: str = Field(min_length=1)
    basis: str = Field(min_length=8)


def fingerprint():
    return hashlib.sha256(b'ACTION_WINDOW_V1\n'+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def candidate_audit(candidate, window, cutoff):
    dates = [date.fromisoformat(candidate[k]) for k in ['record_date_reported','dividend_date_reported']]
    start = date.fromisoformat(window['start_date'])
    end = date.fromisoformat(window['end_date']) if window['end_date'] else None
    relation = ('OLDER_REPORTED_DATES_LIFECYCLE_UNKNOWN' if max(dates)<start else
        'REFERENCE_WINDOW_END_UNKNOWN' if end is None else
        'REPORTED_DATES_INTERSECT_REFERENCE_WINDOW' if any(start<=d<=end for d in dates) else
        'REPORTED_DATES_OUTSIDE_REFERENCE_WINDOW_LIFECYCLE_UNKNOWN')
    local_day = cutoff.astimezone(SHANGHAI).date()
    return {**candidate, 'window_relation':relation, 'date_precision':'DATE',
        'reported_dates_relation_to_cutoff': ['BEFORE_CUTOFF_DATE' if d<local_day else
            'AFTER_CUTOFF_DATE' if d>local_day else 'ON_CUTOFF_DATE_TIME_UNKNOWN' for d in dates],
        'notice_identity_link':None, 'payment_date_inferred':False,
        'lifecycle_state':'UNKNOWN', 'pending_obligation_inferred':False}


class ActionWindows:
    def __init__(self, actions):
        self.actions = actions
        self.prospective = actions.prospective
        self.daily = self.prospective.post_close
        self.ledger, self.evidence = actions.ledger, actions.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS action_window_packets(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,protocol_id TEXT NOT NULL,value TEXT NOT NULL)')

    def payload(self, plan_id, protocol_id, predecessor_id, audit_id, cutoff):
        predecessor = self.actions.packet(plan_id, predecessor_id)
        if datetime.fromisoformat(predecessor['knowledge_cutoff'])>cutoff:
            raise HTTPException(409,'ACTION_WINDOW_PREDECESSOR_NOT_KNOWN')
        audits = self.daily.obligations(plan_id,cutoff,protocol_id=protocol_id,ids=[audit_id])
        audit = audits[0]
        if datetime.fromisoformat(audit['knowledge_cutoff'])>cutoff:
            raise HTTPException(409,'ACTION_WINDOW_OBLIGATION_NOT_KNOWN')
        # Revalidate the registered design even when the action selection is empty.
        context = self.daily.obligation_protocol(protocol_id,self.prospective.plan(plan_id)['instrument'])
        if context != audit['protocol_context']:
            raise HTTPException(409,'ACTION_WINDOW_PROTOCOL_CONTEXT_CHANGED')
        window = audit['protocol_effective_window']
        candidates = [candidate_audit(c,window,cutoff) for c in predecessor['action_candidates']]
        # Preserve assessment duplicates as separate provenance; do not count them as more rows.
        role_audits = {a['source_receipt_id']:a['role_audits'] for a in predecessor['assessments']}
        missing = sum(roles['dividend']['missing_reported_rows'] for roles in role_audits.values())
        gaps = sorted(set(predecessor['gaps']+audit['gaps']+
            ['ACTION_WINDOW_AUTHORITATIVE_NOTICE_LINK_UNPROVEN','ACTION_WINDOW_LIFECYCLE_AND_ALL_CATEGORY_COVERAGE_UNPROVEN']))
        if missing:gaps.append('ACTION_SOURCE_REPORTED_ROWS_MISSING:'+str(missing))
        daily = predecessor['predecessor']
        if daily.get('packet_type')=='PRICE_SUCCESSOR':daily=daily['predecessor']
        reference_inputs = {'packet_ids':[], 'assessment_ids':predecessor['assessment_ids'],
            'source_receipt_ids':predecessor['source_receipt_ids'],
            'action_candidates':candidates, 'missing_reported_rows':missing}
        return {'predecessor':predecessor, 'source_receipt_ids':predecessor['source_receipt_ids'],
            'assessment_ids':predecessor['assessment_ids'], 'known_obligation_audit':audit,
            'protocol_context':context, 'protocol_effective_window':window,
            'candidate_audits':candidates, 'missing_reported_rows':missing,
            'daily_reference_packet_id':daily['packet_id'],
            'daily_reference_knowledge_cutoff':daily['knowledge_cutoff'],
            'reference_rows':self.enrich_rows(daily['rows'],reference_inputs),
            'source_role_audits':list(role_audits.values()), 'gaps':gaps,
            'complete_action_coverage':False, 'negative_coverage':False,
            'pending_older_obligations_complete':False, 'system_usable':False,
            'model_daily_input_allowed':False, 'forward_admissible':False,
            'forward_started_at':None, 'capability':'NOT_GRANTED',
            'account_events_added':0, 'confirmatory_checkpoints_added':0, 'network_calls':0}

    def build(self, plan_id, command):
        cutoff = datetime.fromisoformat(now())
        value = {'packet_type':'ACTION_WINDOW_SUCCESSOR', 'packet_id':str(uuid4()),
            'plan_id':plan_id, 'protocol_id':command.protocol_id,
            'predecessor_packet_id':command.predecessor_packet_id,
            'known_obligation_audit_id':command.known_obligation_audit_id,
            'knowledge_cutoff':cutoff.isoformat(), 'created_at':cutoff.isoformat(),
            'basis':command.basis, 'parser_fingerprint':fingerprint(),
            **self.payload(plan_id,command.protocol_id,command.predecessor_packet_id,
                command.known_obligation_audit_id,cutoff)}
        kind = 'METHOD_CASE' if (value['known_obligation_audit']['evidence_kind']=='METHOD_CASE' or
            value['predecessor']['archive']['evidence_kind']=='METHOD_CASE') else 'REAL_SOURCE_ASSESSMENT'
        value['archive'] = self.evidence.archive(encode(value).encode(),'ACTION_WINDOW_SUCCESSOR',evidence_kind=kind)
        with self.ledger.connection() as db:
            db.execute('INSERT INTO action_window_packets VALUES(?,?,?,?)',(value['packet_id'],plan_id,command.protocol_id,encode(value)))
        return value

    def saved_packet(self, packet_id):
        with self.ledger.connection() as db:
            row = db.execute('SELECT value FROM action_window_packets WHERE id=?',(packet_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def packet(self, plan_id, packet_id):
        value = self.saved_packet(packet_id)
        if not value or value['plan_id']!=plan_id:raise HTTPException(404,'ACTION_WINDOW_PACKET_MISSING')
        original = json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
        if original!={k:v for k,v in value.items() if k!='archive'}:
            raise HTTPException(409,'ACTION_WINDOW_ARCHIVE_MISMATCH')
        if value['parser_fingerprint']!=fingerprint():
            raise HTTPException(409,'ACTION_WINDOW_CODE_CHANGED_SUCCESSOR_REQUIRED')
        payload = self.payload(plan_id,value['protocol_id'],value['predecessor_packet_id'],
            value['known_obligation_audit_id'],datetime.fromisoformat(value['knowledge_cutoff']))
        if any(value[k]!=v for k,v in payload.items()):
            raise HTTPException(409,'ACTION_WINDOW_NORMALIZED_ORIGINAL_MISMATCH')
        return value

    def replay(self, packet_id):
        value = self.saved_packet(packet_id)
        if not value:raise HTTPException(404,'ACTION_WINDOW_PACKET_MISSING')
        self.packet(value['plan_id'],packet_id)
        return {'packet_id':packet_id,'packet_type':'ACTION_WINDOW_SUCCESSOR','matches_original':True,
            'network_calls':0,'forward_admissible':False,'capability':'NOT_GRANTED'}

    def consume(self, plan_id, protocol_id, cutoff=None):
        cutoff = cutoff or datetime.fromisoformat(now())
        self.daily.obligation_protocol(protocol_id,self.prospective.plan(plan_id)['instrument'])
        with self.ledger.connection() as db:
            saved = [json.loads(r[0]) for r in db.execute(
                'SELECT value FROM action_window_packets WHERE plan_id=? AND protocol_id=? ORDER BY rowid',(plan_id,protocol_id))]
        day = cutoff.astimezone(SHANGHAI).date().isoformat()
        applicable = [v for v in saved if datetime.fromisoformat(v['knowledge_cutoff'])<=cutoff and
            v['protocol_effective_window']['start_date']==day]
        selected = [self.packet(plan_id,applicable[-1]['packet_id'])] if applicable else []
        return {'protocol_id':protocol_id,'consumer_knowledge_cutoff':cutoff.isoformat(),
            'packet_ids':[v['packet_id'] for v in selected],
            'assessment_ids':[i for v in selected for i in v['assessment_ids']],
            'source_receipt_ids':[i for v in selected for i in v['source_receipt_ids']],
            'known_obligation_audit_ids':[v['known_obligation_audit_id'] for v in selected],
            'action_candidates':[c for v in selected for c in v['candidate_audits']],
            'reference_rows':[r for v in selected for r in v['reference_rows']],
            'missing_reported_rows':sum(v['missing_reported_rows'] for v in selected),
            'gaps':sorted(set([g for v in selected for g in v['gaps']]+
                ['ACTION_WINDOW_PACKET:'+v['packet_id'] for v in selected])) if selected else ['ACTION_WINDOW_CURRENT_PROTOCOL_INPUT_MISSING'],
            'system_usable':False,'model_daily_input_allowed':False,'forward_admissible':False,
            'forward_started_at':None,'capability':'NOT_GRANTED','network_calls':0}

    def enrich_rows(self, rows, inputs):
        return [{**row,'action_window_packet_ids':inputs['packet_ids'],
            'reported_action_candidates':inputs['action_candidates'],
            'action_missing_reported_rows':inputs['missing_reported_rows'],
            'action_source_receipt_ids':inputs['source_receipt_ids'],
            'action_assessment_ids':inputs['assessment_ids']} for row in rows]
