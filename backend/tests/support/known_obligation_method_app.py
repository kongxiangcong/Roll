"""Only own synthetic protocol metadata; never fits models or opens SEALED."""
import hashlib
import json
from io import BytesIO
import pyarrow as pa
import pyarrow.parquet as pq
from test_research_protocol import engineering_archive


def protocol(client,directory):
    engineering_archive(directory)
    source=directory/'research-inputs/method-181'
    path=source/'browser-live.json'
    manifest=json.loads(path.read_bytes())
    manifest['request']['identity_context']={'SSE:600362':{'exchange':'SSE','board':'MAIN','instrument_type':'STOCK'}}
    for fact in manifest['snapshot']['facts']:fact['instrument']='SSE:600362'
    buffer=BytesIO()
    pq.write_table(pa.Table.from_pylist([{'payload':json.dumps(f)} for f in manifest['snapshot']['facts']]),buffer)
    body=buffer.getvalue();sha=hashlib.sha256(body).hexdigest()
    (source/(sha+'.parquet')).write_bytes(body)
    manifest['snapshot']['parquet'].update(sha256=sha,path='parquet/'+sha+'.parquet',bytes=len(body))
    path.write_text(json.dumps(manifest),encoding='utf-8')
    response=client.post('/api/research/datasets',json={'archive_id':'method-181','basis':'METHOD metadata only; no fit or SEALED reads'})
    assert response.status_code==201,response.text
    response=client.post('/api/research/protocols',json={'dataset_id':response.json()['dataset_id'],'basis':'METHOD protocol effective window context'})
    assert response.status_code==201,response.text
    return response.json()
