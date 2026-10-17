"""Offline binary sentiment inference in the isolated research runtime."""
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
        model=AutoModelForSequenceClassification.from_pretrained(str(model_dir),local_files_only=True)
        model.eval()
        for item in command['items']:
            started=time.monotonic()
            with torch.inference_mode():
                encoded=tokenizer(item['text'][:800],return_tensors='pt',truncation=True,max_length=256)
                probabilities=torch.softmax(model(**encoded).logits[0],dim=-1).tolist()
            result['predictions'].append({'fact_id':item['fact_id'],'prob_negative':float(probabilities[0]),
                'prob_positive':float(probabilities[1]),'latency_seconds':time.monotonic()-started})
        result['status']='SUCCESS'
    except Exception as error:result['errors'].append(type(error).__name__+': '+str(error)[:300])
    Path(command['output']).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')


if __name__=='__main__':main(json.loads(sys.stdin.buffer.read()))
