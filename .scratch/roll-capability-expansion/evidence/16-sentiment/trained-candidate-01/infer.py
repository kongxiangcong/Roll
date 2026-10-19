"""Single fresh frozen evaluation, offline; old holdout never loaded."""
import ctypes
import hashlib
import json
import math
import os
import platform
import socket
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

out = Path(__file__).resolve().parent
repo = Path(__file__).resolve().parents[5]
assert not (out/'inference.json').exists()
manifest = json.loads((out/'evaluation-freeze.json').read_bytes())
for name,digest in manifest['files'].items():
    assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest,name
data_freeze=json.loads((out/'training-freeze.json').read_bytes())
frozen={'model':{'name':'Roll Chinese FinBERT bounded adaptation01','label_mapping':{'0':'NEUTRAL','1':'POSITIVE','2':'NEGATIVE'}},'confidence_floor':data_freeze['confidence_floor'],'rows':json.loads((out/'development.json').read_bytes())['rows']+json.loads((out/'primary.json').read_bytes())['rows']}
receipt=json.loads((out/'training-result.json').read_bytes())
model_dir=Path(receipt['model_directory'])
assert receipt['status'] in ['TRAINED_LAST_STEP','TRAINED_LAST_STEP_BUDGET_STOP']
for artifact in receipt['artifacts']:
    assert hashlib.sha256((model_dir/artifact['path']).read_bytes()).hexdigest()==artifact['sha256']


def deny(*args,**kwargs):
    raise RuntimeError('FRESH_SENTIMENT_NETWORK_DISABLED')


socket.create_connection=deny
socket.socket.connect=deny
socket.socket.connect_ex=deny
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
started = time.monotonic()
result = {'status':'FAILED','started_at':datetime.now(timezone.utc).isoformat(),'model':frozen['model'],'evaluation_freeze_sha256':hashlib.sha256((out/'evaluation-freeze.json').read_bytes()).hexdigest(),
          'network_calls':0,'training':False,'old_holdout_loaded':False,'rows':[]}
try:
    import torch
    from transformers import AutoModelForSequenceClassification,AutoTokenizer
    from object_contract import project
    torch.set_num_threads(2)
    model,loading = AutoModelForSequenceClassification.from_pretrained(str(model_dir),local_files_only=True,output_loading_info=True)
    result['loading_info'] = {key:sorted(value) if isinstance(value,set) else value for key,value in loading.items()}
    assert not any(loading.values()),'CHECKPOINT_LOADING_MISMATCH'
    mapping = {int(key):value.upper() for key,value in model.config.id2label.items()}
    assert mapping=={int(key):value for key,value in frozen['model']['label_mapping'].items()}
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir),local_files_only=True)
    model.eval()
    result['cold_start_seconds'] = time.monotonic()-started
    assert len(frozen['rows'])==240
    for row in frozen['rows']:
        if time.monotonic()-started>600:
            raise RuntimeError('EVALUATION_TIME_LIMIT')
        projection = project(row['title'],row['summary'])
        assert projection==row['projection']
        assert hashlib.sha256(projection['text'].encode()).hexdigest()==row['input_sha256']
        prediction = projection['reject_reason']
        probabilities = None
        confidence = None
        latency = None
        if prediction is None:
            tick = time.monotonic()
            with torch.inference_mode():
                encoded = tokenizer(projection['text'],return_tensors='pt',truncation=True,max_length=256)
                values = torch.softmax(model(**encoded).logits[0],dim=-1).tolist()
            latency = time.monotonic()-tick
            assert len(values)==3 and all(math.isfinite(value) and 0<=value<=1 for value in values) and abs(sum(values)-1)<1e-5
            probabilities = {mapping[index]:value for index,value in enumerate(values)}
            confidence = max(values)
            prediction = mapping[max(range(3),key=lambda index:values[index])] if confidence>=frozen['confidence_floor'] else 'ABSTAIN_LOW_CONFIDENCE'
        result['rows'].append({key:row[key] for key in ('id','split','event_id','label','input_sha256')} | {'prediction':prediction,'probabilities':probabilities,'confidence':confidence,'latency_seconds':latency})
    result['packages'] = {name:version(name) for name in ('torch','transformers','tokenizers','safetensors')}
    result['status'] = 'COMPLETE'
except Exception as error:
    result['error'] = type(error).__name__+': '+str(error)[:300]
finally:
    class Memory(ctypes.Structure):
        _fields_ = [('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)] + [(name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    memory=Memory();memory.cb=ctypes.sizeof(memory)
    handle=ctypes.windll.kernel32.GetCurrentProcess;handle.restype=ctypes.c_void_p
    read_memory=ctypes.windll.psapi.GetProcessMemoryInfo;read_memory.argtypes=[ctypes.c_void_p,ctypes.POINTER(Memory),ctypes.c_ulong]
    if read_memory(handle(),ctypes.byref(memory),memory.cb):
        result['peak_working_set_bytes']=memory.PeakWorkingSetSize
    result.update(elapsed_seconds=time.monotonic()-started,hardware={'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'threads':2,'device':'CPU','precision':'float32'})
    (out/'inference.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key!='rows'},ensure_ascii=False,indent=2))
    if result['status']!='COMPLETE':
        sys.exit(1)
