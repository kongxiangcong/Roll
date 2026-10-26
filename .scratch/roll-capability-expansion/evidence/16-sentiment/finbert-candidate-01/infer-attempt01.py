"""One offline candidate evaluation; never imports or modifies production state."""
import ctypes
import hashlib
import json
import math
import os
import platform
import socket
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from importlib.metadata import version

out = Path(__file__).resolve().parent
repo = Path(__file__).resolve().parents[5]
output = out / 'inference.json'
assert not output.exists()
frozen = json.loads((out / 'freeze-manifest.json').read_bytes())
for name, expected in frozen['files'].items():
    assert hashlib.sha256((out / name).read_bytes()).hexdigest() == expected, name
dataset = json.loads((out / 'frozen-dataset.json').read_bytes())
plan = json.loads((out / 'download03-plan.json').read_bytes())
receipt = json.loads((out / 'download03-receipt.json').read_bytes())
assert receipt['status'] == 'DOWNLOADED_VERIFIED'
model_dir = repo / plan['destination']
for artifact in receipt['artifacts']:
    assert hashlib.sha256((model_dir / artifact['path']).read_bytes()).hexdigest() == artifact['sha256']


def deny(*args, **kwargs):
    raise RuntimeError('CANDIDATE_NETWORK_DISABLED')


socket.create_connection = deny
socket.socket.connect = deny
socket.socket.connect_ex = deny
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
started = time.monotonic()
result = {'status': 'FAILED', 'started_at': datetime.now(timezone.utc).isoformat(), 'model': plan['model'], 'revision': plan['revision'], 'license': plan['license'], 'artifacts': receipt['artifacts'], 'freeze_manifest_sha256': hashlib.sha256((out / 'freeze-manifest.json').read_bytes()).hexdigest(), 'network_calls': 0, 'training': False, 'rows': []}
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    sys.path.insert(0, str(repo / 'backend' / 'src'))
    from roll.market.news_events import associate
    torch.set_num_threads(2)
    model, loading = AutoModelForSequenceClassification.from_pretrained(str(model_dir), local_files_only=True, output_loading_info=True)
    result['loading_info'] = loading
    assert not loading.get('missing_keys') and not loading.get('unexpected_keys') and not loading.get('mismatched_keys'), 'CHECKPOINT_NOT_EXACTLY_LOADABLE'
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model.eval()
    mapping = {int(key): value.upper() for key, value in model.config.id2label.items()}
    assert mapping == {0:'NEUTRAL', 1:'POSITIVE', 2:'NEGATIVE'}
    result['cold_start_seconds'] = time.monotonic() - started
    identity = [{'instrument': 'SSE:600362', 'name': '江西铜业股份有限公司', 'code': '600362'}]
    for row in dataset['included']:
        if time.monotonic() - started > 600:
            raise RuntimeError('EVALUATION_TIME_LIMIT')
        title = row['title'] or ''
        text = title + '\n' + (row['summary'] or '')
        assert hashlib.sha256(text.encode()).hexdigest() == row['input_sha256']
        fact = {'fact_id': str(row['index']), 'instrument':'SSE:600362', 'title':title, 'excerpt':row['summary'], 'url': 'https://finance.eastmoney.com/a/1.html', 'body_text':None}
        association = associate(fact, identity)['classification']
        reason = None
        if '江西铜业' not in title and any(marker in title for marker in ('ETF','指数','收评','午评')):
            reason = 'ABSTAIN_MARKET_INDEX'
        elif '江西铜业' not in title and any(marker in title for marker in ('资金流入','资金流出','资金流向','主力资金')):
            reason = 'ABSTAIN_FUND_FLOW'
        elif association in ('INDUSTRY_BACKGROUND','UNRELATED','UNCERTAIN'):
            reason = 'ABSTAIN_RELEVANCE'
        probabilities = None
        latency = None
        confidence = None
        prediction = reason
        if not reason:
            tick = time.monotonic()
            with torch.inference_mode():
                encoded = tokenizer(text[:800], return_tensors='pt', truncation=True, max_length=256)
                values = torch.softmax(model(**encoded).logits[0], dim=-1).tolist()
            latency = time.monotonic() - tick
            assert len(values)==3 and all(math.isfinite(value) and 0<=value<=1 for value in values) and abs(sum(values)-1)<1e-5
            probabilities = {mapping[index]: value for index,value in enumerate(values)}
            confidence = max(values)
            prediction = mapping[max(range(3), key=lambda index:values[index])] if confidence>=0.65 else 'ABSTAIN_LOW_CONFIDENCE'
        result['rows'].append({'index':row['index'], 'group_id':row['group_id'], 'split':row['split'], 'label':row['label'], 'input_sha256':row['input_sha256'], 'association':association, 'prediction':prediction, 'confidence':confidence, 'probabilities':probabilities, 'latency_seconds':latency})
    assert len(result['rows']) == len(dataset['included'])
    result['packages'] = {name:version(name) for name in ('torch','transformers','tokenizers','safetensors')}
    result['status'] = 'COMPLETE'
except Exception as error:
    result['error'] = type(error).__name__ + ': ' + str(error)[:300]
finally:
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_ = [('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)] + [(name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        memory = Memory(); memory.cb = ctypes.sizeof(memory)
        handle = ctypes.windll.kernel32.GetCurrentProcess
        handle.restype = ctypes.c_void_p
        read_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        read_memory.argtypes = [ctypes.c_void_p,ctypes.POINTER(Memory),ctypes.c_ulong]
        if read_memory(handle(),ctypes.byref(memory),memory.cb):
            result['peak_working_set_bytes'] = memory.PeakWorkingSetSize
    result.update(elapsed_seconds=time.monotonic()-started, hardware={'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'torch_threads':2,'device':'CPU','precision':'float32'})
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key not in ('rows','artifacts')},ensure_ascii=False,indent=2))
    if result['status']!='COMPLETE':
        sys.exit(1)
