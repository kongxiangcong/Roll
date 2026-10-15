"""Offline-only extraction from previously saved complete HTTP entities."""
import hashlib,json,socket,sys
from importlib.metadata import version
from pathlib import Path


def denied(*args,**kwargs):raise RuntimeError('OFFLINE_EXTRACTION_NETWORK_DENIED')
socket.create_connection=denied;socket.socket.connect=denied;socket.socket.connect_ex=denied


def main(command):
    reference=json.loads(Path(__file__).with_name('trafilatura-reference.json').read_text())
    if reference.get('status')!='VERIFIED':raise ValueError('TRAFILATURA_RUNTIME_NOT_VERIFIED')
    for name,expected in reference['packages'].items():
        if version(name)!=expected:raise ValueError('TRAFILATURA_PACKAGE_VERSION_MISMATCH')
    runtime=Path(sys.executable).resolve().parent.parent
    for item in reference['artifacts']:
        path=(runtime/item['path']).resolve()
        if not path.is_relative_to(runtime) or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('TRAFILATURA_FINGERPRINT_MISMATCH')
    from trafilatura import bare_extraction
    output=Path(command['output_directory']);manifest=json.loads((output/'capture.json').read_text(encoding='utf-8'));manifest['extractor_version']='2.3.1'
    def save():
        p=output/'capture.json.tmp';p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');p.replace(output/'capture.json')
    for item in manifest['items']:
        if item['body_status']!='ARCHIVED_PENDING_EXTRACTION':continue
        try:
            ordinal=item['body_ordinal'];captured=manifest['captures'][ordinal-1];raw=(output/f'{ordinal:02}.raw').read_bytes()
            if len(raw)>8388608 or not captured['original_complete'] or captured['status_code']!=200 or hashlib.sha256(raw).hexdigest()!=captured['sha256']:raise ValueError('ARCHIVED_BODY_INTEGRITY_MISMATCH')
            result=bare_extraction(raw,url=captured['url'],with_metadata=True,include_comments=False,include_tables=True,fast=False)
            if result is None or not result.text:raise ValueError('FULL_TEXT_EXTRACTION_EMPTY')
            item.update(body_status='EXTRACTED',text=result.text,metadata={key:getattr(result,key,None) for key in ('title','author','date','sitename','url')},errors=[])
        except Exception as error:item.update(body_status='EXTRACTION_FAILED',text=None,errors=[str(error)[:180] if isinstance(error,ValueError) else type(error).__name__])
        save()
    save()


if __name__=='__main__':main(json.loads(sys.stdin.buffer.read()))
