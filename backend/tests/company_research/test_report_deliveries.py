"""METHOD: public report delivery, download and recovery boundaries."""
import hashlib
import pytest
from fastapi import HTTPException
from test_shared_evidence import service, company
from test_daily_research import published


def published_report(directory, monkeypatch):
    from roll.research.company.reports import ReportCommand
    monkeypatch.delenv('ROLL_CODEX_AUTH_FILE', raising=False)
    research = service(directory)
    issuer = research.register(company())
    snapshot = published(research, issuer)
    job = research.reports.start(ReportCommand(company_id=issuer['company_id'],
        snapshot_id=snapshot['snapshot_id'], as_of='2026-02-01T00:00:00+00:00',
        source_mode='REUSE', idempotency_key='delivery-fixture'))
    for _ in range(24):
        job = research.reports.advance(job['job_id'])
        if job['report_id']:
            return research, research.reports.read(job['report_id'])
    pytest.fail('Fixture report did not publish')


def test_fixed_markdown_delivery_manifest_and_download_are_immutable(tmp_path, monkeypatch):
    research, report = published_report(tmp_path, monkeypatch)
    from roll.research.company.report_deliveries import DeliveryCommand
    command = DeliveryCommand(report_id=report['report_id'], idempotency_key='markdown', render_pdf=False)
    delivery = research.report_deliveries.create(command)
    assert research.report_deliveries.create(command) == delivery
    assert delivery['status'] == 'MARKDOWN_ONLY'
    raw, media, filename = research.report_deliveries.download(delivery['delivery_id'], 'markdown')
    assert raw.decode('utf-8') == research.reports.markdown(report['report_id'])
    assert hashlib.sha256(raw).hexdigest() == report['markdown_archive']['sha256']
    manifest, _, _ = research.report_deliveries.download(delivery['delivery_id'], 'manifest')
    import json
    manifest = json.loads(manifest)
    assert manifest['report_id'] == report['report_id']
    assert manifest['core_sha256'] == report['core_sha256']
    assert manifest['artifacts']['markdown'] == report['markdown_archive']
    assert manifest['completeness'] == 'PARTIAL'
    assert media == 'text/markdown; charset=utf-8' and filename.endswith('.md')
    with pytest.raises(HTTPException) as invalid:
        research.report_deliveries.download(delivery['delivery_id'], '../account')
    assert invalid.value.status_code == 404
    assert research.reports.read(report['report_id']) == report


def test_http_delivery_downloads_registered_files_and_rejects_arbitrary_paths(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from roll.research.company.api import router
    research, report = published_report(tmp_path, monkeypatch)
    app=FastAPI();app.include_router(router(research))
    with TestClient(app) as client:
        response=client.post('/api/company-research/report-deliveries',json=dict(report_id=report['report_id'],idempotency_key='api',render_pdf=False))
        assert response.status_code==201, response.text
        delivery=response.json()
        base='/api/company-research/report-deliveries/'+delivery['delivery_id']
        markdown=client.get(base+'/files/markdown')
        assert markdown.status_code==200
        assert markdown.content.decode()==research.reports.markdown(report['report_id'])
        assert markdown.headers['x-content-type-options']=='nosniff'
        assert 'attachment;' in markdown.headers['content-disposition']
        assert client.get(base+'/files/roll.sqlite3').status_code==404
        assert client.get(base+'/files/pdf').status_code==404
        assert client.get('/api/company-research/report-deliveries/missing/files/markdown').status_code==404
        assert client.get('/api/company-research/reports/'+report['report_id']+'/deliveries').json()['total']==1
    assert research.ledger.account()['version'] == 0


def test_pdf_failure_retains_markdown_and_retry_creates_new_delivery(tmp_path, monkeypatch):
    from roll.research.company.report_deliveries import DeliveryCommand
    research, report = published_report(tmp_path, monkeypatch)
    monkeypatch.setenv('ROLL_REPORT_FONT', str(tmp_path/'missing.ttf'))
    failed = research.report_deliveries.create(DeliveryCommand(report_id=report['report_id'], idempotency_key='missing-font'))
    assert failed['status'] == 'PDF_FAILED'
    assert failed['render_error']['code'] == 'PDF_FONT_UNAVAILABLE'
    assert research.report_deliveries.download(failed['delivery_id'], 'markdown')[0]
    monkeypatch.delenv('ROLL_REPORT_FONT')
    success = research.report_deliveries.create(DeliveryCommand(report_id=report['report_id'],
        idempotency_key='retry-font', parent_delivery_id=failed['delivery_id']))
    assert success['status'] == 'COMPLETE', success
    raw, media, _ = research.report_deliveries.download(success['delivery_id'], 'pdf')
    assert raw.startswith(b'%PDF-') and media == 'application/pdf'
    from pypdf import PdfReader
    from io import BytesIO
    pdf = PdfReader(BytesIO(raw))
    assert len(pdf.pages) > 2
    assert '附录' in ''.join(page.extract_text() for page in pdf.pages)
    assert pdf.outline
    assert research.report_deliveries.read(failed['delivery_id']) == failed
    assert research.reports.read(report['report_id']) == report


def test_backup_restores_delivery_bytes_and_rejects_rehashed_wrong_core(tmp_path, monkeypatch):
    import json
    from roll.research.company.report_deliveries import DeliveryCommand
    from roll.research.company.service import record
    from roll.accounts.ledger import encode
    from roll.runtime.backups import Backups, restore_at_start
    research, report = published_report(tmp_path/'source', monkeypatch)
    delivery=research.report_deliveries.create(DeliveryCommand(report_id=report['report_id'],idempotency_key='backup',render_pdf=False))
    backup=Backups(tmp_path/'source')
    bundle=backup.export(backup.create()['backup_id'])
    target=Backups(tmp_path/'restored');target.stage_restore(bundle);restore_at_start(target)
    recovered=service(tmp_path/'restored')
    assert recovered.report_deliveries.read(delivery['delivery_id'])==delivery
    for name in ['markdown','manifest','references','valuation','input']:
        assert recovered.report_deliveries.download(delivery['delivery_id'],name)==research.report_deliveries.download(delivery['delivery_id'],name)
    # Fault injection: coherent JSON hash does not authorize a different shared core.
    changed={k:v for k,v in delivery.items() if k!='content_sha256'}
    changed['core_sha256']='0'*64
    with research.ledger.connection() as db:
        db.execute('UPDATE company_research_report_deliveries SET value=? WHERE delivery_id=?',(encode(record(changed)),delivery['delivery_id']))
    with pytest.raises(HTTPException) as invalid:
        backup.create()
    assert invalid.value.detail['code']=='RESEARCH_REFERENCE_INVALID'


def test_pdf_formats_blank_separated_report_tables_as_tables(tmp_path, monkeypatch):
    from roll.research.company.report_deliveries import DeliveryCommand
    from pypdf import PdfReader
    from io import BytesIO
    research,report=published_report(tmp_path,monkeypatch)
    delivery=research.report_deliveries.create(DeliveryCommand(report_id=report['report_id'],idempotency_key='tables'))
    assert delivery['status']=='COMPLETE',delivery
    raw,_,_=research.report_deliveries.download(delivery['delivery_id'],'pdf')
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(raw)).pages)
    assert '|---|' not in text
    assert '|1|' not in text
    assert '存贷双高' in text and '附录 D' in text
    # The final two-column version index must not inherit the preceding
    # three-column source-ledger grid after a blank-separated new header.
    positions={}
    for page in PdfReader(BytesIO(raw)).pages:
        fragments={}
        def visit(value,cm,tm,font,size):
            fragments.setdefault((cm[4]+tm[4],cm[5]),[]).append(value)
        page.extract_text(visitor_text=visit)
        for (x,y),values in fragments.items():
            label=''.join(values).strip()
            if label in ['对象','固定版本/摘要']:
                positions[label]=x
    assert set(positions)=={'对象','固定版本/摘要'}
    assert positions['固定版本/摘要']-positions['对象']>240


def test_public_pdf_renderer_rejects_unbound_images_and_preserves_timeout_diagnosis(tmp_path,monkeypatch):
    """METHOD renderer boundary: untrusted text and registered static chart bytes."""
    from roll.research.company.report_archive import archive
    from pypdf import PdfReader
    from io import BytesIO
    research,report=published_report(tmp_path,monkeypatch)
    packet=research.reports.input(report['input_id'])
    for image in ['file:///C:/Windows/win.ini','https://example.com/chart.svg','/api/company-research/report-charts/'+'0'*64]:
        supplied=dict(report,markdown_archive=archive(research.evidence,('![缺图]('+image+')').encode(),'METHOD_RENDER_INPUT'))
        raw,error,_=research.report_deliveries.render(supplied,packet)
        assert raw is None and error['code'] in {'PDF_ASSET_UNSAFE','PDF_ASSET_MISSING'}
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300"><polyline points="20,200 300,100 560,30" stroke="#2468a0"/><text x="30" y="240">METHOD图表 单位元</text></svg>'
    asset=archive(research.evidence,svg.encode(),'METHOD_RENDER_CHART','svg')
    identifier=asset['sha256']
    packet=dict(packet,payload=dict(packet['payload'],charts=[dict(chart_id=identifier,archive=asset)]))
    text='# 中文长表和静态图\n\n<script>alert(1)</script>\n\n![图](/api/company-research/report-charts/'+identifier+')\n\n|项目|说明|\n\n|---|---|\n\n'+''.join('|长表行'+str(i)+'|https://example.com/'+('long-segment-'*15)+'|\n\n' for i in range(65))
    supplied=dict(report,markdown_archive=archive(research.evidence,text.encode(),'METHOD_RENDER_INPUT'))
    raw,error,_=research.report_deliveries.render(supplied,packet)
    assert error is None,error
    reader=PdfReader(BytesIO(raw))
    assert len(reader.pages)>3 and 'METHOD图表' in ''.join(p.extract_text() for p in reader.pages)
    assert '/JavaScript' not in str(reader.trailer['/Root'])
    (tmp_path/'method-layout.pdf').write_bytes(raw)
    monkeypatch.setenv('ROLL_REPORT_RENDER_TIMEOUT','0.01')
    raw,error,_=research.report_deliveries.render(supplied,packet)
    assert raw is None and error['code']=='PDF_RENDER_TIMEOUT'
