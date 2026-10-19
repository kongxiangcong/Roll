"""Offline, fingerprint-bound sentiment inference in the isolated research runtime."""
import hashlib,json,socket,sys,time
from importlib.metadata import version
from pathlib import Path


def deny(*args,**kwargs):raise RuntimeError('SENTIMENT_NETWORK_DISABLED')


def main(command):
    result={'status':'FAILED','model':command['reference'].get('model'),'weights_sha256':command['reference'].get('weights_sha256'),'predictions':[],'errors':[]}
    socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny
    try:
        reference=command['reference']
        if reference.get('status')!='VERIFIED':raise ValueError('SENTIMENT_RUNTIME_NOT_VERIFIED')
        for package,expected in reference['packages'].items():
            if version(package)!=expected:raise ValueError('SENTIMENT_PACKAGE_VERSION_MISMATCH')
        model_dir=Path(command['model_directory']).resolve()
        for item in reference['artifacts']:
            path=(model_dir/item['path']).resolve()
            if not path.is_relative_to(model_dir) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('SENTIMENT_FINGERPRINT_MISMATCH')
        import torch
        from transformers import AutoModelForSequenceClassification,AutoTokenizer
        torch.set_num_threads(2)
        tokenizer=AutoTokenizer.from_pretrained(str(model_dir),local_files_only=True)
        model,loading=AutoModelForSequenceClassification.from_pretrained(str(model_dir),local_files_only=True,output_loading_info=True)
        if any(loading.values()):raise ValueError('SENTIMENT_CHECKPOINT_LOADING_MISMATCH')
        research=reference.get('task')=='CHINESE_FINANCIAL_SENTIMENT_3_CLASS'
        mapping={int(key):value.upper() for key,value in model.config.id2label.items()}
        expected={0:'NEUTRAL',1:'POSITIVE',2:'NEGATIVE'} if research else {0:'NEGATIVE',1:'POSITIVE'}
        if mapping!=expected:raise ValueError('SENTIMENT_MODEL_LABEL_MAPPING_MISMATCH')
        model.eval()
        for item in command['items']:
            started=time.monotonic()
            with torch.inference_mode():
                encoded=tokenizer(item['text'][:800],return_tensors='pt',truncation=True,max_length=256)
                probabilities=torch.softmax(model(**encoded).logits[0],dim=-1).tolist()
            if len(probabilities)!=len(expected):raise ValueError('SENTIMENT_MODEL_LABEL_COUNT_MISMATCH')
            values={mapping[index]:float(value) for index,value in enumerate(probabilities)}
            result['predictions'].append({'fact_id':item['fact_id'],'prob_negative':values['NEGATIVE'],
                'prob_positive':values['POSITIVE'],'probabilities':values,'latency_seconds':time.monotonic()-started})
        result['status']='SUCCESS'
    except Exception as error:result['errors'].append(type(error).__name__+': '+str(error)[:300])
    Path(command['output']).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')


if __name__=='__main__':main(json.loads(sys.stdin.buffer.read()))
