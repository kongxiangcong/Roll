"""One preregistered transparent candidate; immutable failures are research evidence."""
import hashlib
import json
import math
import time
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import uuid4
from datetime import date,datetime
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.registry import AttemptCommand,FinishCommand


class ModelCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    purpose:Literal['RESEARCH','METHOD_VALIDATION']='RESEARCH'
    basis:str=Field(min_length=1,max_length=2000)


class ForecastCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    observation_date:date
    basis:str=Field(min_length=1,max_length=2000)


def code_fingerprint():
    return hashlib.sha256(Path(__file__).read_text(encoding='utf-8').replace('\r\n','\n').encode()).hexdigest()


FEATURES=['raw_return_5','raw_return_20','raw_return_volatility_20','log_volume_to_trailing20_mean']


def features(facts,observation,method,cutoff):
    rows=sorted([r for r in facts if r['trade_date']<=observation],key=lambda r:r['trade_date'])[-21:]
    if len(rows)!=21:raise ValueError('FEATURE_LOOKBACK_INSUFFICIENT')
    if rows[-1]['trade_date']!=observation:raise ValueError('OBSERVATION_DAY_MISSING')
    prices=[];volumes=[]
    for row in rows:
        if row.get('adjustment')!='RAW' or row.get('volume_unit')!='SHARE' or row.get('errors') or row.get('completion_state')!='COMPLETE_REPORTED_HISTORICAL':raise ValueError('FEATURE_INPUT_NOT_COMPLETE_RAW_SHARE')
        if not row.get('available_at') or datetime.fromisoformat(row['available_at'])>datetime.fromisoformat(cutoff):raise ValueError('FEATURE_NOT_AVAILABLE_TO_CONSUMER')
        if not method:raise ValueError('HISTORICAL_POINT_IN_TIME_NOT_PROVEN')
        if not row.get('method_completion_available_at') or datetime.fromisoformat(row['method_completion_available_at'])>datetime.fromisoformat(observation+'T15:05:00+08:00'):raise ValueError('METHOD_FEATURE_NOT_COMPLETE_AT_OBSERVATION')
        price=Decimal(row['close']);volume=Decimal(row['volume_shares'])
        if not price.is_finite() or not volume.is_finite() or price<=0 or volume<=0:raise ValueError('FEATURE_NONPOSITIVE_OR_UNKNOWN')
        prices.append(price);volumes.append(volume)
    returns=[float(prices[i]/prices[i-1]-1) for i in range(1,21)];mean=sum(returns)/20
    values=[float(prices[-1]/prices[-6]-1),float(prices[-1]/prices[0]-1),math.sqrt(sum((v-mean)**2 for v in returns)/20),math.log(float(volumes[-1]/(sum(volumes[:-1])/20)))]
    return {'features':dict(zip(FEATURES,values)),'values':values,'input_trade_dates':[r['trade_date'] for r in rows],
        'latest_input_trade_date':rows[-1]['trade_date'],'raw_hashes':sorted({r['raw_hash'] for r in rows}),
        'observation_cutoff':observation+'T15:05:00+08:00','consumer_knowledge_cutoff':cutoff,
        'availability_basis':'EXPLICIT_SYNTHETIC_METHOD_CLOCK; actual archive available_at retained, no historical PIT proof'}


def sigmoid(value):
    if value>=0:return 1/(1+math.exp(-value))
    v=math.exp(value);return v/(1+v)


def solve(matrix,vector):
    a=[list(row)+[v] for row,v in zip(matrix,vector)];n=len(vector)
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(a[j][i]));a[i],a[pivot]=a[pivot],a[i]
        if abs(a[i][i])<1e-12:raise ValueError('SINGULAR_MODEL_HESSIAN')
        divisor=a[i][i];a[i]=[v/divisor for v in a[i]]
        for j in range(n):
            if j!=i:
                factor=a[j][i];a[j]=[v-factor*w for v,w in zip(a[j],a[i])]
    return [r[-1] for r in a]


def fit_logit(examples,deadline):
    means=[sum(r['feature_snapshot']['values'][j] for r in examples)/len(examples) for j in range(4)]
    scales=[math.sqrt(sum((r['feature_snapshot']['values'][j]-means[j])**2 for r in examples)/len(examples)) or 1.0 for j in range(4)]
    x=[[1,*[(v-m)/s for v,m,s in zip(r['feature_snapshot']['values'],means,scales)]] for r in examples];y=[r['label'] for r in examples]
    weights=[0.0]*5
    for iteration in range(100):
        if time.monotonic()>deadline:raise ValueError('PREREGISTERED_60_SECOND_FIT_LIMIT')
        p=[sigmoid(sum(a*b for a,b in zip(row,weights))) for row in x]
        gradient=[sum((v-t)*row[j] for row,v,t in zip(x,p,y))+(weights[j] if j else 0) for j in range(5)]
        hessian=[[sum(max(v*(1-v),1e-12)*row[j]*row[k] for row,v in zip(x,p))+(1 if j==k and j else 0) for k in range(5)] for j in range(5)]
        step=solve(hessian,gradient);weights=[w-d for w,d in zip(weights,step)]
        if max(abs(d) for d in step)<1e-8:break
    else:raise ValueError('MODEL_DID_NOT_CONVERGE_WITHIN_100_STEPS')
    return {'weights':weights,'means':means,'scales':scales,'iterations':iteration+1,'lambda':1,
        'objective':'sum binary negative log likelihood + 0.5 * sum(non-intercept weight^2)',
        'standardization_partition':'DEVELOPMENT','feature_names':FEATURES,'volume_definition':'current reported shares / mean preceding20 reported shares; positive units required',
        'fitted_observation_dates':[r['observation_date'] for r in examples]}


def predict(fit,snapshot,intercept=0.0):
    values=[1,*[(v-m)/s for v,m,s in zip(snapshot['values'],fit['means'],fit['scales'])]]
    logit=sum(v*w for v,w in zip(values,fit['weights']))
    return {'uncalibrated_probability':sigmoid(logit),'probability':sigmoid(logit+intercept),'logit':logit}


def calibrate(predictions,deadline):
    shift=0.0
    for iteration in range(100):
        if time.monotonic()>deadline:raise ValueError('PREREGISTERED_60_SECOND_FIT_LIMIT')
        p=[sigmoid(r['logit']+shift) for r in predictions];g=sum(v-r['label'] for v,r in zip(p,predictions));h=sum(v*(1-v) for v in p)
        if h<1e-12:raise ValueError('CALIBRATOR_SINGULAR_OR_SINGLE_CLASS')
        step=max(-5,min(5,g/h));shift-=step
        if abs(step)<1e-8:return {'intercept_shift':shift,'slope':1,'iterations':iteration+1,'partition':'CALIBRATION','statistical_validation':'NOT_PROVEN'}
    raise ValueError('CALIBRATOR_DID_NOT_CONVERGE_WITHIN_100_STEPS')


def reliability(predictions,base_rate,intercept=0):
    probabilities=[sigmoid(r['logit']+intercept) for r in predictions];labels=[r['label'] for r in predictions]
    bins=[]
    for i in range(5):
        pairs=[(p,y) for p,y in zip(probabilities,labels) if min(4,int(p*5))==i]
        bins.append({'lower':i/5,'upper':(i+1)/5,'count':len(pairs),'mean_probability':sum(p for p,y in pairs)/len(pairs) if pairs else None,
            'observed_positive_rate':sum(y for p,y in pairs)/len(pairs) if pairs else None,'minimum_required':20,'supported':len(pairs)>=20})
    positives=[p for p,y in zip(probabilities,labels) if y];negatives=[p for p,y in zip(probabilities,labels) if not y]
    return {'count':len(labels),'brier':sum((p-y)**2 for p,y in zip(probabilities,labels))/len(labels),
        'base_rate_brier':sum((base_rate-y)**2 for y in labels)/len(labels),
        'log_loss':-sum(y*math.log(max(p,1e-15))+(1-y)*math.log(max(1-p,1e-15)) for p,y in zip(probabilities,labels))/len(labels),
        'roc_auc':sum((p>n)+.5*(p==n) for p in positives for n in negatives)/(len(positives)*len(negatives)) if positives and negatives else None,
        'reliability_bins':bins,'selected_count':sum(p>=.60 for p in probabilities),'selected_minimum':40,
        'independent_samples':None,'effective_nonoverlap20_block_upper_bound':len(labels)//20,'minimum_effective_blocks':30,
        'calibrated_assessment':'CALIBRATION_FIT_IN_SAMPLE; NOT_AN_INDEPENDENT_CALIBRATED_TEST','qualification':'NONE; Brier/ROC/win rate alone cannot establish reliability or profitability'}


class TransparentModels:
    def __init__(self,registry,executions):
        self.registry=registry;self.executions=executions;self.ledger=registry.ledger;self.evidence=registry.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_models(id TEXT PRIMARY KEY,protocol_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS research_forecasts(id TEXT PRIMARY KEY,model_id TEXT NOT NULL,value TEXT NOT NULL)')

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_models WHERE id=?',(identifier,)).fetchone()
        if row is None:raise HTTPException(404,'模型尝试不存在')
        return json.loads(row[0])

    def list(self,protocol_id):
        self.registry.get(protocol_id)
        with self.ledger.connection() as db:return [json.loads(r[0]) for r in db.execute('SELECT value FROM research_models WHERE protocol_id=? ORDER BY rowid',(protocol_id,))]

    def check_feature_calendar(self,snapshot,protocol):
        scope=protocol['design']['g5']['migration_scope'];instrument=scope['instruments'][0]
        exchange=scope['identity_context'][instrument]['exchange']
        dates=snapshot['input_trade_dates']
        for earlier,later in zip(dates,dates[1:]):
            if self.evidence.market.rules.next_trading_day(exchange,date.fromisoformat(earlier))!=later:
                raise ValueError('FEATURE_CALENDAR_GAP_OR_UNSUPPORTED')

    def create(self,protocol_id,command):
        protocol=self.registry.get(protocol_id)
        attempt=self.registry.start_attempt(protocol_id,AttemptCommand(category='PRIMARY_FIT',partition='DEVELOPMENT',
            configuration={'candidate':'PRICE_VOLUME_LOGIT_V1','purpose':command.purpose,'lambda':'1','code_fingerprint':code_fingerprint()},basis=command.basis))
        support={name:self.executions.support(protocol_id,name) for name in ['DEVELOPMENT','CALIBRATION']}
        run={'model_run_id':str(uuid4()),'protocol_id':protocol_id,'attempt_id':attempt['attempt_id'],'registered_at':now(),
            'purpose':command.purpose,'basis':command.basis,'namespace':'HISTORICAL','capability':'NOT_GRANTED',
            'protocol_fingerprint':protocol['protocol_fingerprint'],'data_fingerprint':protocol.get('data_fingerprint'),
            'code_fingerprint':code_fingerprint(),'status':'FAILED','reasons':['INSUFFICIENT_SCORABLE_SUPPORT'],
            'support':support,'model_artifact':None,'calibrator_artifact':None,'forecast_probability':None,
            'complete_experiment_frozen':False,'validation_verdict':None,'forward_started_at':None}
        calibration_attempt=None
        try:
            dataset=self.registry.dataset(protocol['dataset_id']);run['evidence_kind']=dataset['source_evidence_kind']
            readiness=dataset.get('training_readiness')
            if readiness and readiness['state']=='BLOCKED':
                run['reasons']=readiness['blockers'][:]
                run['input_archive']=self.evidence.archive(encode({'dataset':dataset,'protocol':protocol,'purpose':command.purpose,
                    'code_fingerprint':run['code_fingerprint'],'preflight_only':True}).encode(),'RESEARCH_MODEL_INPUT',research_namespace='HISTORICAL')
                raise ValueError('SOURCE_QUALIFICATION_BLOCKED')
            parts={name:self.registry.partition(dataset['dataset_id'],name) for name in support}
            method=command.purpose=='METHOD_VALIDATION' and dataset['source_evidence_kind']=='METHOD_CASE'
            examples={};excluded={}
            for name,part in parts.items():
                selected=[];gaps=[]
                dates=[r['observation_date'] for r in support[name]['records']]
                for r in support[name]['records']:
                    outcome=r['result'];definition=r['definition'];day=r['observation_date']
                    reason=None
                    if dates.count(day)>1:reason='REPEATED_OBSERVATION_REQUIRES_UNIQUE_PREREGISTERED_PRIMARY'
                    elif day<part['metadata']['first_date'] or not outcome.get('maturity_date') or outcome['maturity_date']>part['metadata']['last_date']:reason='LABEL_CROSSES_FROZEN_PARTITION'
                    elif not outcome.get('scoreable') or outcome.get('label') not in [0,1] or not outcome.get('label_available_at'):reason='LABEL_NOT_MATURE_SCORABLE'
                    elif not method and not outcome.get('eligible_for_training'):reason='NOT_ELIGIBLE_REAL_TRAINING'
                    elif definition['order']['delay']!='NEXT_OPEN' or definition['order']['fill_fraction']!='1' or definition['costs']['commission_scenario_rate']!='0.0003' or definition['costs']['slippage_each_side_rate']!='0.0005':reason='NOT_PREREGISTERED_PRIMARY_EXECUTION'
                    else:
                        try:
                            snapshot=features(part['facts'],day,method,part['consumer_knowledge_cutoff'])
                            self.check_feature_calendar(snapshot,protocol)
                        except (ValueError,KeyError,ArithmeticError) as error:reason=str(error)
                    if reason:gaps.append({'execution_id':r['execution_id'],'observation_date':day,'reason':reason});continue
                    selected.append({'execution_id':r['execution_id'],'observation_date':day,'maturity_date':outcome['maturity_date'],
                        'label':outcome['label'],'label_available_at':outcome['label_available_at'],'execution_input_sha256':r['input_sha256'],
                        'feature_snapshot':snapshot,'net_return_on_invested_cash':outcome['net_return_on_invested_cash'],'net_pnl_yuan':outcome['net_pnl_yuan']})
                examples[name]=sorted(selected,key=lambda r:r['observation_date']);excluded[name]=gaps
            inputs={'examples':examples,'excluded':excluded,'parts':parts,'protocol':protocol,'evidence_kind':dataset['source_evidence_kind'],
                'purpose':command.purpose,'code_fingerprint':run['code_fingerprint'],'historical_point_in_time_proven':False}
            run['input_archive']=self.evidence.archive(encode(inputs).encode(),'RESEARCH_MODEL_INPUT',research_namespace='HISTORICAL')
            run['excluded']=excluded
            minimum=protocol['design']['statistics']['minimum_calibration_examples_per_class'];cal=examples['CALIBRATION'];dev=examples['DEVELOPMENT']
            classes={str(y):sum(r['label']==y for r in cal) for y in [0,1]}
            run['statistical_support']={'development_total':len(dev),'calibration_total':len(cal),'calibration_per_class':classes,
                'minimum_per_class':minimum,'calibration_metadata_mature_upper_bound':protocol['design']['support_projection']['calibration_mature_label_upper_bound']}
            run['reasons']=[]
            if not dev or not cal or len({r['label'] for r in dev})<2 or len({r['label'] for r in cal})<2:run['reasons'].append('INSUFFICIENT_SCORABLE_SUPPORT')
            if any(n<minimum for n in classes.values()):run['reasons'].append('CALIBRATION_PER_CLASS_SUPPORT_BELOW_20')
            if protocol['design']['support_projection']['calibration_mature_label_upper_bound']<minimum*2:run['reasons'].append('REGISTERED_CALIBRATION_WINDOW_CANNOT_SUPPORT_BOTH_CLASSES')
            if not method:run['reasons'].extend(['HISTORICAL_POINT_IN_TIME_NOT_PROVEN','REAL_MODEL_AND_CALIBRATOR_NOT_FROZEN'])
            if 'INSUFFICIENT_SCORABLE_SUPPORT' in run['reasons'] or not method:raise ValueError('INSUFFICIENT_SCORABLE_SUPPORT')
            deadline=time.monotonic()+60
            fit=fit_logit(dev,deadline);base_rate=sum(r['label'] for r in dev)/len(dev)
            model={'fit':fit,'candidate_id':'PRICE_VOLUME_LOGIT_V1','features':FEATURES,'base_rate':base_rate,
                'purpose':command.purpose,'evidence_kind':'METHOD_CASE','protocol_fingerprint':run['protocol_fingerprint'],
                'data_fingerprint':run['data_fingerprint'],'input_sha256':run['input_archive']['sha256'],'code_fingerprint':run['code_fingerprint']}
            run['model_artifact']=self.evidence.archive(encode(model).encode(),'RESEARCH_MODEL_ARTIFACT',research_namespace='HISTORICAL')
            predictions=[{**{k:r[k] for k in ['observation_date','label','execution_input_sha256']},**predict(fit,r['feature_snapshot']),
                'prediction_phase':'BEFORE_CALIBRATOR_FIT','model_artifact_sha256':run['model_artifact']['sha256']} for r in cal]
            run['calibration_prediction_archive']=self.evidence.archive(encode(predictions).encode(),'RESEARCH_TIME_OUT_PREDICTIONS',research_namespace='HISTORICAL')
            # Persist pre-calibration predictions before registering/calculating the only calibration fit.
            self.registry.event(protocol_id,'MODEL_PRECALIBRATION_PREDICTIONS_ARCHIVED',model_run_id=run['model_run_id'],sha256=run['calibration_prediction_archive']['sha256'])
            calibration_attempt=self.registry.start_attempt(protocol_id,AttemptCommand(category='CALIBRATION',partition='CALIBRATION',
                configuration={'model_sha256':run['model_artifact']['sha256'],'method':'INTERCEPT_ONLY','purpose':command.purpose},basis=command.basis))
            calibrator=calibrate(predictions,deadline)
            run['calibrator_artifact']=self.evidence.archive(encode({**calibrator,'model_sha256':run['model_artifact']['sha256'],'prediction_sha256':run['calibration_prediction_archive']['sha256'],
                'code_fingerprint':run['code_fingerprint'],'purpose':command.purpose,'evidence_kind':'METHOD_CASE'}).encode(),'RESEARCH_CALIBRATOR_ARTIFACT',research_namespace='HISTORICAL')
            run.update(status='METHOD_ARTIFACT_ONLY',fit=fit,calibrator=calibrator,calibration_predictions=predictions,
                reliability={'before_calibration':reliability(predictions,base_rate),'after_calibration':reliability(predictions,base_rate,calibrator['intercept_shift'])},
                artifact_fingerprints={'model':run['model_artifact']['sha256'],'calibrator':run['calibrator_artifact']['sha256'],'features_and_inputs':run['input_archive']['sha256'],
                    'code':run['code_fingerprint'],'data':run['data_fingerprint'],'protocol':run['protocol_fingerprint']})
            run['baseline_comparison']={}
            for name in examples:
                opportunities=[]
                for example in examples[name]:
                    closes=[Decimal(r['close']) for r in parts[name]['facts'] if r['trade_date']<=example['observation_date']][-20:]
                    signal=sum(closes[-5:])/5>sum(closes)/20
                    probability=predict(fit,example['feature_snapshot'])['uncalibrated_probability']
                    opportunities.append({'observation_date':example['observation_date'],'label':example['label'],'execution_input_sha256':example['execution_input_sha256'],
                        'fixed_ma_signal':signal,'candidate_before_calibration_signal':probability>=.60,'matched_round_trip_net_pnl_yuan':example['net_pnl_yuan'],
                        'cash_net_pnl_yuan':'0','candidate_round_trip_net_pnl_yuan':example['net_pnl_yuan'] if probability>=.60 else '0',
                        'ma_round_trip_net_pnl_yuan':example['net_pnl_yuan'] if signal else '0'})
                run['baseline_comparison'][name]={'opportunities':opportunities,'base_rate_probability':base_rate,
                    'CASH':{'zero_exposure':True,'net_pnl_yuan':'0'},
                    'START_HOLD':{'status':'CONTINUOUS_MATCHED_NAV_NOT_EVALUATED','reason':'20 must freeze continuous economic policy; overlapping round trips cannot be concatenated into initial buy-and-hold wealth'},
                    'MA5_MA20':{'lookbacks':[5,20],'maximum_exposure':'0.50','same_execution_cost_inputs':True},
                    'evaluation_basis':'METHOD per-opportunity economic sanity checks only; no portfolio NAV/drawdown/improvement/PASS conclusion'}
            run['reasons'].extend(['METHOD_CASE_NOT_REAL_TRAINING_INPUT','CALIBRATED_RELIABILITY_HAS_NO_INDEPENDENT_TEST','EFFECTIVE_DEPENDENT_BLOCK_SUPPORT_INSUFFICIENT'])
            self.registry.finish_attempt(calibration_attempt['attempt_id'],FinishCommand(status='SUCCEEDED',reason='仅METHOD截距校准工件；统计支持不足，非实际校准资格',artifact_fingerprints={'calibrator':run['calibrator_artifact']['sha256']}))
        except (ValueError,HTTPException,KeyError,ArithmeticError) as error:
            reason=error.detail if isinstance(error,HTTPException) else str(error)
            run['reasons']=list(dict.fromkeys([*run['reasons'],str(reason)]))
            if calibration_attempt:self.registry.finish_attempt(calibration_attempt['attempt_id'],FinishCommand(status='FAILED',reason=str(reason)[:2000]))
        self.registry.finish_attempt(attempt['attempt_id'],FinishCommand(status='SUCCEEDED' if run['status']=='METHOD_ARTIFACT_ONLY' else 'FAILED',
            reason='METHOD数值工件完成，未授实际资格' if run['status']=='METHOD_ARTIFACT_ONLY' else '支持不足/失败：'+','.join(run['reasons'])[:1800],artifact_fingerprints=run.get('artifact_fingerprints',{})))
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO research_models VALUES(?,?,?)',(run['model_run_id'],protocol_id,encode(run)))
            self.registry.event(protocol_id,'MODEL_ATTEMPT_RECORDED',db=db,model_run_id=run['model_run_id'],status=run['status'],reasons=run['reasons']);db.commit()
        return run

    def forecast(self,identifier,command):
        run=self.get(identifier)
        if run['status']!='METHOD_ARTIFACT_ONLY':raise HTTPException(409,'没有已冻结且有支持的模型；不能生成概率')
        protocol=self.registry.get(run['protocol_id']);day=command.observation_date.isoformat()
        cal=protocol['design']['windows']['CALIBRATION']
        if not cal['first_date']<=day<=cal['last_date']:raise HTTPException(403,'本票只允许固定CALIBRATION窗口，封存及正式范围不可查询预测')
        if run['code_fingerprint']!=code_fingerprint():raise HTTPException(409,'模型代码版本不同，不能以当前算法冒充原输入预测')
        inputs=json.loads(self.evidence.raw(run['input_archive']['sha256']).read_text(encoding='utf-8'))
        part=inputs['parts']['CALIBRATION']
        try:
            snapshot=features(part['facts'],day,True,part['consumer_knowledge_cutoff'])
            self.check_feature_calendar(snapshot,protocol)
        except (ValueError,KeyError,ArithmeticError) as error:raise HTTPException(409,str(error)) from None
        prediction=predict(run['fit'],snapshot,run['calibrator']['intercept_shift'])
        base_rate=sum(r['label'] for r in inputs['examples']['DEVELOPMENT'])/len(inputs['examples']['DEVELOPMENT'])
        closes=[Decimal(r['close']) for r in part['facts'] if r['trade_date']<=day][-20:]
        ma_signal=sum(closes[-5:])/5>sum(closes)/20
        returns=sorted(Decimal(r['net_return_on_invested_cash']) for r in inputs['examples']['DEVELOPMENT'])
        bundle={'forecast_id':str(uuid4()),'model_run_id':identifier,'protocol_id':run['protocol_id'],'recorded_at':now(),'basis':command.basis,
            'evidence_kind':'METHOD_CASE','purpose':run['purpose'],'namespace':'HISTORICAL','capability':'NOT_GRANTED',
            'instrument':protocol['design']['g5']['migration_scope']['instruments'][0],'event':protocol['design']['event'],'horizon_sessions':20,
            'observation_cutoff':snapshot['observation_cutoff'],'consumer_knowledge_cutoff':now(),'feature_snapshot':snapshot,**prediction,
            'artifact_fingerprints':run['artifact_fingerprints'],'execution':protocol['design']['execution'],'costs':protocol['design']['costs'],
            'scope':protocol['design']['g5']['migration_scope'],'statistical_support':run['statistical_support'],
            'uncertainty':{'qualification':'NONE','reasons':run['reasons'],'conditional_method_only':True,'historical_point_in_time_proven':False,
                'calibration_reliability':'FIT_IN_SAMPLE; NO_INDEPENDENT_CALIBRATED_TEST','formal_forward_prediction':False},
            'baselines':{'CASH':{'exposure':'0','return':'0','event_probability':None},'START_HOLD':{'maximum_exposure':'0.50','event_probability_base_rate':base_rate},
                'MA5_MA20':{'signal':bool(ma_signal),'maximum_exposure':'0.50','probability':None,'probability_basis':'deterministic signal not calibrated probability'}},
            'return_scenarios':{'lower':str(returns[0]),'median':str(returns[len(returns)//2]),'upper':str(returns[-1]),
                'basis':'DEVELOPMENT empirical METHOD per-round-trip fee-after return on invested cash; not confidence interval/future wealth/continuous NAV'},
            'action_published':False,'complete_experiment_frozen':False}
        archive=self.evidence.archive(encode(bundle).encode(),'RESEARCH_FORECAST_BUNDLE',research_namespace='HISTORICAL');bundle['archive']=archive
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO research_forecasts VALUES(?,?,?)',(bundle['forecast_id'],identifier,encode(bundle)))
            self.registry.event(run['protocol_id'],'METHOD_FORECAST_RECORDED',db=db,forecast_id=bundle['forecast_id'],sha256=archive['sha256'],actual_forward_start=False);db.commit()
        return bundle

    def get_forecast(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_forecasts WHERE id=?',(identifier,)).fetchone()
        if row is None:raise HTTPException(404,'研究预测不存在')
        return json.loads(row[0])

    def replay(self,identifier):
        bundle=self.get_forecast(identifier);run=self.get(bundle['model_run_id'])
        if run['code_fingerprint']!=code_fingerprint():raise HTTPException(409,'原算法版本不同，不能冒充同输入重放')
        original=json.loads(self.evidence.raw(bundle['archive']['sha256']).read_text(encoding='utf-8'))
        inputs=json.loads(self.evidence.raw(run['input_archive']['sha256']).read_text(encoding='utf-8'))
        part=inputs['parts']['CALIBRATION']
        snapshot=features(part['facts'],original['observation_cutoff'][:10],True,part['consumer_knowledge_cutoff'])
        self.check_feature_calendar(snapshot,inputs['protocol'])
        model=json.loads(self.evidence.raw(run['model_artifact']['sha256']).read_text(encoding='utf-8'))
        calibrator=json.loads(self.evidence.raw(run['calibrator_artifact']['sha256']).read_text(encoding='utf-8'))
        prediction=predict(model['fit'],snapshot,calibrator['intercept_shift'])
        self.registry.event(run['protocol_id'],'MODEL_FORECAST_OFFLINE_REPLAY',forecast_id=identifier,input_sha256=run['input_archive']['sha256'],network_calls=0)
        return {'forecast_id':identifier,'network_calls':0,'matches_original':snapshot==original['feature_snapshot'] and all(original[k]==v for k,v in prediction.items()),'prediction':prediction,
            'input_sha256':run['input_archive']['sha256'],'forecast_sha256':bundle['archive']['sha256']}
