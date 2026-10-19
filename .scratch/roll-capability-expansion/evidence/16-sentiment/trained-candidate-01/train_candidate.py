"""One authorized local training run. Requires a separate, complete data freeze.

This script has not been run. It never loads development/holdout texts or labels.
Usage: isolated-python train_candidate.py <training-freeze.json> <new-model-dir>
"""
import hashlib,json,math,os,random,socket,sys,time
from datetime import datetime,timezone
from pathlib import Path

script=Path(__file__).resolve();repo=script.parents[5]
manifest_path=Path(sys.argv[1]).resolve();destination=Path(sys.argv[2]).resolve()
assert destination.is_relative_to(repo/'.scratch/rce-runtime/sentiment')
assert not destination.exists()
out=manifest_path.parent
assert out.is_relative_to(repo/'.scratch/roll-capability-expansion/evidence/16-sentiment')
assert not (out/'training-result.json').exists(),'SINGLE_TRAINING_ALREADY_RECORDED'
manifest=json.loads(manifest_path.read_bytes())
assert manifest['status']=='FROZEN_BEFORE_TRAINING'
assert manifest['complete_data_gate'] is True
assert manifest['counts']=={'TRAIN':400,'DEVELOPMENT':120,'HOLDOUT_PRIMARY':120}
assert manifest['training_script_sha256']==hashlib.sha256(script.read_bytes()).hexdigest()
assert manifest['training_settings']=={'seed':42,'cpu_threads':2,'precision':'float32','max_length':256,'learning_rate':2e-5,'batch_size':4,'maximum_epochs':2,'maximum_seconds':3600,'weight_decay':.01,'gradient_clip_norm':1.0}
train_path=(out/manifest['training_file']).resolve()
assert train_path.is_relative_to(out)
assert hashlib.sha256(train_path.read_bytes()).hexdigest()==manifest['training_sha256']
rows=json.loads(train_path.read_bytes())['rows']
assert len(rows)==400
assert all(r['split']=='TRAIN' and r['label'] in ('NEUTRAL','POSITIVE','NEGATIVE') for r in rows)
assert len({r['input_sha256'] for r in rows})==400
for row in rows:assert hashlib.sha256(row['input_text'].encode()).hexdigest()==row['input_sha256']
model_dir=repo/'.scratch/rce-runtime/sentiment/FinBERT-tone-chinese-e91b1a3a-03'
download=json.loads((script.parent.parent/'finbert-candidate-01/download03-receipt.json').read_bytes())
assert download['status']=='DOWNLOADED_VERIFIED'
for artifact in download['artifacts']:
    assert hashlib.sha256((model_dir/artifact['path']).read_bytes()).hexdigest()==artifact['sha256']

def deny(*args,**kwargs):raise RuntimeError('TRAINING_NETWORK_DISABLED')
socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
started=time.monotonic();settings=manifest['training_settings'];result={'status':'FAILED','started_at':datetime.now(timezone.utc).isoformat(),
    'training_authorization':'One bounded user-approved candidate, max2epochs/60min','training_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    'training_rows':400,'network_calls':0,'development_loaded':False,'holdout_loaded':False,'optimizer_steps':0,'settings':settings,'step_log':[]}
try:
    import torch
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    random.seed(42);torch.manual_seed(42);torch.set_num_threads(2)
    tokenizer=AutoTokenizer.from_pretrained(str(model_dir),local_files_only=True)
    model,loading=AutoModelForSequenceClassification.from_pretrained(str(model_dir),local_files_only=True,output_loading_info=True)
    assert not any(loading.values()),'PRETRAINED_WEIGHT_LOADING_MISMATCH'
    mapping={int(k):v.upper() for k,v in model.config.id2label.items()}
    assert mapping=={0:'NEUTRAL',1:'POSITIVE',2:'NEGATIVE'}
    label_to_id={v:k for k,v in mapping.items()}
    optimizer=torch.optim.AdamW(model.parameters(),lr=2e-5,weight_decay=.01)
    result['cold_start_seconds']=time.monotonic()-started
    budget_stop=False
    for epoch in range(2):
        order=list(range(400));random.Random(42+epoch).shuffle(order)
        for begin in range(0,400,4):
            if time.monotonic()-started>=3600:budget_stop=True;break
            batch=[rows[i] for i in order[begin:begin+4]]
            encoded=tokenizer([r['input_text'] for r in batch],padding=True,truncation=True,max_length=256,return_tensors='pt')
            labels=torch.tensor([label_to_id[r['label']] for r in batch],dtype=torch.long)
            model.train();optimizer.zero_grad(set_to_none=True)
            loss=model(**encoded,labels=labels).loss
            assert math.isfinite(loss.item()),'NON_FINITE_TRAINING_LOSS'
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step()
            result['optimizer_steps']+=1
            entry={'step':result['optimizer_steps'],'epoch':epoch+1,'examples_seen_this_epoch':begin+len(batch),'loss':float(loss.item()),'elapsed_seconds':time.monotonic()-started}
            if result['optimizer_steps']%10==0:
                result['step_log'].append(entry);print(json.dumps(entry),flush=True)
        if budget_stop:break
    assert result['optimizer_steps']>0
    destination.mkdir(parents=True,exist_ok=False)
    model.eval();model.save_pretrained(str(destination),safe_serialization=True);tokenizer.save_pretrained(str(destination))
    artifacts=[{'path':str(p.relative_to(destination)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(destination.iterdir()) if p.is_file()]
    result.update(status='TRAINED_LAST_STEP_BUDGET_STOP' if budget_stop else 'TRAINED_LAST_STEP',model_directory=str(destination),artifacts=artifacts)
except Exception as error:
    result['error_type']=type(error).__name__;result['error_code']=str(error)[:240]
finally:
    result['elapsed_seconds']=time.monotonic()-started
    (out/'training-result.json').write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode())
    print(json.dumps({k:v for k,v in result.items() if k not in ('step_log','artifacts')},ensure_ascii=False,indent=2),flush=True)
    if result['status']=='FAILED':raise SystemExit(1)
