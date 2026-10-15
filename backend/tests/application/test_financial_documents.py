import json
from fastapi.testclient import TestClient
from roll.app import create_app
from test_financial_metrics import prepare


def test_document_parse_keeps_source_pages_parentheses_and_failed_attempts(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        base=prepare(client);fact=client.get(base+'/income').json()['facts'][0];sha=fact['semantic_document']['sha256']
        async def parser(source,output,command):
            return {'status':'SUCCESS','parser_version':'2.139.0','source_sha256':sha,'document':{'texts':[{'text':'人民币元；合并现金流量表（续）；附注68','prov':[{'page_no':67,'bbox':{'l':20,'t':40,'r':500,'b':100}}]}],
                'tables':[{'prov':[{'page_no':67,'bbox':{'l':20,'t':100,'r':500,'b':600}}],'data':{'num_rows':2,'num_cols':2,'table_cells':[{'text':'投资活动现金流量净额','row_span':1,'col_span':1},{'text':'(23,434,970,323)','row_span':1,'col_span':1}]}}]},'confidence':None,'warnings':['MULTIPAGE_HEADERS_REQUIRE_REVIEW'],'runtime':{'kind':'METHOD_TRANSPORT_FIXTURE'}}
        client.app.state.financial_documents.worker=parser
        path='/api/market/financial/documents/'+sha+'/parses';command={'first_page':66,'last_page':67,'idempotency_key':'parse-once','basis':'METHOD parser transport fixture, source actual saved PDF'}
        response=client.post(path,json=command);assert response.status_code==201,response.text
        saved=response.json();assert saved['status']=='PARTIAL' and saved['evidence_kind']=='METHOD_CASE'
        assert saved['warnings'][-1]=='PAGES_WITHOUT_TEXT_OR_TABLE:66'
        assert saved['source_sha256']==sha and saved['review_required'] is True
        assert client.post(path,json=command).json()==saved
        view=client.get('/api/market/financial/document-parses/'+saved['parse_id']).json();assert view==saved
        artifact=client.get('/api/data/archives/'+saved['artifact']['sha256']).json()
        assert artifact['document']['tables'][0]['data']['table_cells'][1]['text']=='(23,434,970,323)'
        assert artifact['document']['texts'][0]['prov'][0]['page_no']==67
        assert client.get('/api/data/archives/'+sha).content.startswith(b'%PDF')
        assert client.post(path,json={**command,'last_page':100}).status_code==422
        async def failed(source,output,command):raise ValueError('DOCLING_PARSE_FAILED')
        client.app.state.financial_documents.worker=failed
        failure=client.post(path,json={**command,'idempotency_key':'failed'}).json();assert failure['status']=='FAILED'
        assert client.get('/api/data/archives/'+sha).status_code==200
        assert len(client.get(path).json()['parses'])==2
        assert client.get('/api/account').json()['version']==0
    with TestClient(create_app(tmp_path)) as client:assert client.get('/api/market/financial/document-parses/'+saved['parse_id']).json()==saved


def test_document_cancel_and_wrong_page_provenance_keep_original_readable(tmp_path):
    import asyncio,threading
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(create_app(tmp_path)) as client:
        base=prepare(client);sha=client.get(base+'/income').json()['facts'][0]['semantic_document']['sha256'];path='/api/market/financial/documents/'+sha+'/parses'
        command={'first_page':66,'last_page':67,'idempotency_key':'cancel','basis':'METHOD explicit cancellation'}
        entered=threading.Event()
        async def waiting(source,output,command):entered.set();await asyncio.sleep(60)
        client.app.state.financial_documents.worker=waiting
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(client.post,path,json=command);assert entered.wait(5)
            identifier=client.get(path).json()['parses'][0]['parse_id']
            assert client.post('/api/market/financial/document-parses/'+identifier+'/cancel').status_code==200
            assert pending.result(timeout=5).json()['status']=='CANCELLED'
        async def wrong_page(source,output,command):return {'status':'SUCCESS','parser_version':'2.139.0','source_sha256':sha,'document':{'texts':[{'text':'wrong page','prov':[{'page_no':68}]}]}}
        client.app.state.financial_documents.worker=wrong_page
        failed=client.post(path,json={**command,'idempotency_key':'wrong-page'}).json()
        assert failed['status']=='FAILED' and failed['errors']==['DOCLING_PAGE_PROVENANCE_OUT_OF_RANGE']
        assert client.get('/api/data/archives/'+sha).content.startswith(b'%PDF')


def test_document_output_directory_failure_is_terminal_and_does_not_lock_next_parse(tmp_path):
    with TestClient(create_app(tmp_path),raise_server_exceptions=False) as client:
        base=prepare(client);sha=client.get(base+'/income').json()['facts'][0]['semantic_document']['sha256'];path='/api/market/financial/documents/'+sha+'/parses'
        command={'first_page':66,'last_page':66,'idempotency_key':'disk-failure','basis':'METHOD output directory fault'}
        output=client.app.state.evidence.directory/'document-parses';assert output.is_relative_to(tmp_path);output.write_text('METHOD directory conflict',encoding='utf-8')
        response=client.post(path,json=command);assert response.status_code==201,response.text
        failed=response.json();assert failed['status']=='FAILED' and failed['artifact'] is None
        assert client.post(path,json=command).json()==failed
        assert client.get(path).json()['parses'][0]['status']=='FAILED'
        output.unlink()
        async def parsed(source,output,command):return {'status':'SUCCESS','parser_version':'2.139.0','source_sha256':sha,'document':{'texts':[{'text':'METHOD recovered output directory','prov':[{'page_no':66}]}]}}
        client.app.state.financial_documents.worker=parsed
        recovered=client.post(path,json={**command,'idempotency_key':'after-disk-repair'}).json()
        assert recovered['status']=='COMPLETE'
        assert client.get('/api/data/archives/'+sha).status_code==200
