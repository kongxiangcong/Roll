"""Bind saved CAL arithmetic references to one successor, without qualification."""
from decimal import Decimal
import hashlib,json,math
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-probability-evidence-v1.json'


class ProbabilityBindingCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_complete_protocol_fingerprint:str
    probability_reference_id:str
    block_reference_id:str
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


class SuccessorProbabilityEvidence:
    def __init__(self,protocols,probability,blocks):
        self.protocols=protocols;self.probability=probability;self.blocks=blocks;self.ledger=protocols.ledger;self.evidence=protocols.evidence;self.shadow=protocols.shadow
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_successor_probability_bindings(id TEXT PRIMARY KEY,freeze_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(freeze_id,key))')

    def create(self,freeze_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_probability_bindings WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_PROBABILITY_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['binding_id'])
        protocol=self.protocols.get(freeze_id);method_body=METHOD.read_bytes();method=json.loads(method_body)
        if command.expected_complete_protocol_fingerprint!=protocol['complete_protocol_fingerprint']:raise HTTPException(409,'SUCCESSOR_PROBABILITY_PROTOCOL_CHANGED')
        method_archive=self.evidence.archive(method_body,'SUCCESSOR_PROBABILITY_METHOD')
        probability=self.probability.get(command.probability_reference_id);blocks=self.blocks.get(command.block_reference_id)
        if (probability['freeze_id']!=protocol['predecessor_freeze_id'] or probability['complete_protocol_fingerprint']!=protocol['predecessor_complete_protocol_fingerprint'] or
            probability['original_artifact_fingerprints']!=protocol['model_artifact_fingerprints']):raise HTTPException(409,'SUCCESSOR_PROBABILITY_PREDECESSOR_OR_MODEL_MISMATCH')
        if (blocks['probability_reference_id']!=probability['reference_id'] or blocks['probability_manifest']!=probability['archive'] or blocks['cutoff']!=probability['cutoff']):
            raise HTTPException(409,'SUCCESSOR_PROBABILITY_BLOCK_SOURCE_MISMATCH')
        threshold=Decimal(protocol['design']['successor_policy']['entry_threshold'])
        if threshold!=Decimal(method['selection_threshold']):raise HTTPException(409,'SUCCESSOR_PROBABILITY_THRESHOLD_METHOD_MISMATCH')
        source=self.shadow.checked_archive(probability['source']);sessions=source['sessions'];session_set=set(sessions);required=protocol['design']['statistics'];phases={}
        for name,phase in probability['phases'].items():
            if 'accepted_rows' not in phase:raise HTTPException(409,'SUCCESSOR_PROBABILITY_SOURCE_ERROR')
            rows=phase['accepted_rows']
            if len(rows)>method['maximum_events_per_phase']:raise HTTPException(422,'SUCCESSOR_PROBABILITY_EVENT_LIMIT')
            if any(r['observation_date'] not in session_set or not r['mature'] or r['label'] not in (0,1) or not math.isfinite(float(r['probability'])) for r in rows):
                raise HTTPException(409,'SUCCESSOR_PROBABILITY_INVALID_ARCHIVED_EVENT')
            selected=[r for r in rows if Decimal(str(r['probability']))>=threshold]
            unknown={r['observation_date'] for r in phase.get('excluded',[]) if r.get('observation_date') in session_set}
            missing=(session_set-{r['observation_date'] for r in rows})|unknown
            intervals={}
            for label in (' ALL',' SELECTED_P_GE_0.60'):
                for block in (20,40):
                    key='SOURCE:'+name+label+':'+str(block)
                    if key not in blocks['cases']:raise HTTPException(409,'SUCCESSOR_PROBABILITY_BLOCK_CASE_MISSING')
                    intervals[key]=blocks['cases'][key]
            gaps=['CALIBRATION_FIT_WINDOW_REUSED','INDEPENDENT_CALIBRATION_VALIDATION_NOT_BOUND','DEPENDENCE_ASSUMPTIONS_UNVERIFIED']
            if phase['status']!='NUMERICALLY_CONSISTENT':gaps.append('NUMERIC_REFERENCE_NOT_CONSISTENT')
            class_counts={str(label):sum(r['label']==label for r in rows) for label in (0,1)}
            if any(v<required['minimum_calibration_examples_per_class'] for v in class_counts.values()):gaps.append('CLASS_SUPPORT_BELOW_FROZEN_REQUIREMENT')
            if len(selected)<required['minimum_selected_mature_examples']:gaps.append('SELECTED_SUPPORT_BELOW_FROZEN_REQUIREMENT')
            if missing:gaps.append('FULL_CALENDAR_CHECKPOINTS_MISSING_OR_UNKNOWN')
            if any(i.get('effective_block_upper_bound',0)<required['minimum_effective_time_blocks'] or i.get('lower_95') is None for i in intervals.values()):gaps.append('DEPENDENT_INTERVAL_SUPPORT_INSUFFICIENT')
            if any(b['count'] and b['count']<20 for b in phase.get('aligned_bins',[])):gaps.append('OCCUPIED_BIN_SUPPORT_BELOW_FROZEN_REQUIREMENT')
            phases[name]={'mature_unique':len(rows),'class_counts':class_counts,'selected_threshold':str(threshold),'selected_mature':len(selected),
                'selected_brier':sum((float(r['probability'])-r['label'])**2 for r in selected)/len(selected) if selected else None,
                'calendar_sessions':len(sessions),'missing_calendar_sessions':len(missing),'missing_or_unknown_dates':sorted(missing),
                'saved_numeric_status':phase['status'],'saved_aligned_metrics':phase.get('library_aligned',{}),'source_intervals':intervals,
                'gaps':gaps,'G3_status':'INCONCLUSIVE','independent_calibration_validation':False}
        value={'binding_id':str(uuid4()),'successor_freeze_id':freeze_id,'complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],
            'probability_reference_id':probability['reference_id'],'block_reference_id':blocks['reference_id'],
            'probability_manifest':probability['archive'],'block_manifest':blocks['archive'],'method':method_archive,'phases':phases,
            'model_artifact_fingerprints':protocol['model_artifact_fingerprints'],'cutoff':probability['cutoff'],'source_scope':probability['source_scope'],
            'source_evidence_kind':probability['source_evidence_kind'],'recorded_at':now(),'basis':command.basis,
            'method_fingerprint':hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            'G3_status':'INCONCLUSIVE','independent_calibration_validation':False,'assumptions_verified':False,
            'capability':'NOT_GRANTED','system_usable':False,'complete_experiment_frozen':False,'network_calls':0,'new_fit_calls':0,'sealed_reads':0}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_PROBABILITY_BINDING')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_successor_probability_bindings WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_PROBABILITY_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['binding_id'])
            db.execute('INSERT INTO research_successor_probability_bindings VALUES(?,?,?,?,?)',(value['binding_id'],freeze_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_probability_bindings WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_PROBABILITY_BINDING_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'SUCCESSOR_PROBABILITY_MANIFEST_MISMATCH')
        probability=self.probability.get(value['probability_reference_id'])
        blocks=self.blocks.get(value['block_reference_id'])
        if probability['archive']!=value['probability_manifest'] or blocks['archive']!=value['block_manifest']:
            raise HTTPException(409,'SUCCESSOR_PROBABILITY_PARENT_MANIFEST_MISMATCH')
        self.shadow.checked_archive(value['method'])
        return value

    def listing(self,freeze_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_probability_bindings WHERE freeze_id=? ORDER BY rowid',(freeze_id,))]
        return [self.get(identifier) for identifier in ids]
