"""Immutable file deliveries derived exclusively from a published report."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import BoundedSemaphore
from uuid import uuid4
from typing import Literal
from pydantic import Field
from roll.accounts.ledger import encode
from .models import Command
from .service import fail, record, verified, fingerprint, page_bounds
from .report_archive import archive

_RENDER_SLOTS=BoundedSemaphore(2)


class DeliveryCommand(Command):
    report_id: str
    idempotency_key: str = Field(min_length=1, max_length=128)
    render_pdf: bool = True
    parent_delivery_id: str | None = None


class ReportDeliveries:
    def __init__(self, research):
        self.research = research
        with research.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS company_research_report_deliveries(delivery_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, value TEXT NOT NULL)')

    def read(self, delivery_id):
        value = self.research.analysis.read('report_deliveries', 'delivery_id', delivery_id)
        report = self.research.reports.read(value['report_id'])
        if (value['report_sha256'] != report['content_sha256'] or value['company_id'] != report['company_id'] or
            any(value[k]!=report[k] for k in ['core_sha256','snapshot_id','input_id','input_sha256','template','completeness','quality'])):
            fail('RESEARCH_REFERENCE_INVALID', 'Delivery differs from its immutable report', 409)
        for descriptor in value['artifacts'].values():
            self.research.evidence.raw(descriptor['sha256'])
        manifest = json.loads(self.research.evidence.raw(value['manifest_archive']['sha256']).read_bytes())
        if manifest != {k:v for k,v in value.items() if k not in {'manifest_archive','content_sha256'}}:
            fail('RESEARCH_REFERENCE_INVALID', 'Delivery manifest differs from registered record', 409)
        return value

    def list(self, report_id, limit=50, offset=0):
        self.research.reports.read(report_id)
        page_bounds(limit, offset, 200)
        with self.research.ledger.connection() as db:
            rows = db.execute("SELECT delivery_id FROM company_research_report_deliveries WHERE json_extract(value,'$.report_id')=? ORDER BY rowid DESC", (report_id,)).fetchall()
        return dict(total=len(rows), deliveries=[self.read(r[0]) for r in rows[offset:offset+limit]])

    def create(self, command):
        report = self.research.reports.read(command.report_id)
        request = command.model_dump()
        with self.research.ledger.connection() as db:
            prior = db.execute("SELECT value FROM company_research_report_deliveries WHERE json_extract(value,'$.report_id')=? AND json_extract(value,'$.idempotency_key')=?", (command.report_id, command.idempotency_key)).fetchone()
        if prior:
            value = verified(json.loads(prior[0]))
            if value['request_sha256'] != fingerprint(request):
                fail('IDEMPOTENCY_CONFLICT', 'Delivery key identifies another request', 409)
            return self.read(value['delivery_id'])
        if command.parent_delivery_id and self.read(command.parent_delivery_id)['report_id'] != command.report_id:
            fail('CROSS_REPORT_REFERENCE', 'Delivery retry must belong to this report')
        packet = self.research.reports.input(report['input_id'])
        evidence = self.research.evidence
        artifacts = dict(markdown=report['markdown_archive'], input=packet['input_archive'])
        references = dict(references=packet['payload']['references'], materials=packet['payload']['materials'],
            facts=packet['payload']['facts'], peer_facts=packet['payload']['peer_facts'])
        artifacts['references'] = archive(evidence, encode(references).encode(), 'REPORT_REFERENCE_INDEX', 'json')
        artifacts['valuation'] = archive(evidence, encode(dict(valuation_binding=packet['payload']['valuation_binding'],
            core=report['core'], core_sha256=report['core_sha256'],
            host_revision=self.research.reports.revision(report['host_revision_id']) if report.get('host_revision_id') else None)).encode(), 'REPORT_FIXED_VALUATION_INDEX', 'json')
        status, error, renderer = 'MARKDOWN_ONLY', None, None
        if command.render_pdf:
            pdf, error, renderer = self.render(report, packet)
            status = 'PDF_FAILED' if error else 'COMPLETE'
            if pdf:
                artifacts['pdf'] = archive(evidence, pdf, 'REPORT_PDF', 'pdf')
        payload = record(dict(delivery_id=str(uuid4()), company_id=report['company_id'], report_id=command.report_id,
            report_sha256=report['content_sha256'], snapshot_id=report['snapshot_id'], core_sha256=report['core_sha256'],
            input_id=report['input_id'], input_sha256=report['input_sha256'], template=report['template'],
            completeness=report['completeness'], quality=report['quality'], parent_delivery_id=command.parent_delivery_id,
            idempotency_key=command.idempotency_key, request_sha256=fingerprint(request), status=status,
            render_error=error, renderer=renderer, artifacts=artifacts, formal_authority=False))
        manifest = {k:v for k,v in payload.items() if k!='content_sha256'}
        descriptor = archive(evidence, encode(manifest).encode(), 'REPORT_DELIVERY_MANIFEST', 'json')
        value = record(manifest | dict(manifest_archive=descriptor))
        with self.research.transaction() as db:
            # Serialize publication and enforce idempotency even after concurrent rendering.
            other = db.execute("SELECT delivery_id FROM company_research_report_deliveries WHERE json_extract(value,'$.report_id')=? AND json_extract(value,'$.idempotency_key')=?", (command.report_id, command.idempotency_key)).fetchone()
            if other:
                existing=self.read(other[0])
                if existing['request_sha256']!=fingerprint(request):
                    fail('IDEMPOTENCY_CONFLICT','Concurrent delivery key identifies another request',409)
                return existing
            self.research.analysis.insert(db, 'report_deliveries', 'delivery_id', value)
        return self.read(value['delivery_id'])

    def render(self, report, packet):
        """Public file renderer seam; supplied evidence is data, never executable input."""
        if not _RENDER_SLOTS.acquire(blocking=False):
            return None,dict(code='PDF_RENDER_BUSY',detail='Two local renders are already active',retryable=True),None
        try:
            return self._render(report,packet)
        finally:
            _RENDER_SLOTS.release()

    def _render(self, report, packet):
        from .report_pdf import VERSION
        import hashlib
        evidence = self.research.evidence
        source = Path(__file__).with_name('report_pdf.py')
        try:
            dependency_version=__import__('importlib.metadata',fromlist=['version']).version('reportlab')
        except __import__('importlib.metadata',fromlist=['PackageNotFoundError']).PackageNotFoundError:
            dependency_version=None
        renderer = dict(version=VERSION, source_archive=archive(evidence, source.read_bytes(), 'REPORT_PDF_RENDERER_SOURCE', 'py'),
            reportlab_version=dependency_version)
        request = dict(markdown=evidence.raw(report['markdown_archive']['sha256']).read_bytes().decode('utf-8'),
            markdown_sha256=report['markdown_archive']['sha256'], report_id=report['report_id'],
            snapshot_id=report['snapshot_id'], completeness=report['completeness'], title=packet['payload']['company']['legal_name']+' 深度研究与条件估值',
            as_of=packet['payload'].get('request_cutoff',packet['payload'].get('as_of','UNKNOWN')), charts={})
        for chart in packet['payload']['charts']:
            request['charts'][chart['chart_id']] = evidence.raw(chart['archive']['sha256']).read_bytes().decode('utf-8')
        renderer['request_sha256'] = hashlib.sha256(encode(request).encode()).hexdigest()
        try:
            timeout = min(90,max(0.01,float(os.environ.get('ROLL_REPORT_RENDER_TIMEOUT','45'))))
            renderer['timeout_seconds'] = timeout
            child_env = {k:os.environ[k] for k in ['PATH','SYSTEMROOT','WINDIR','TEMP','TMP','ROLL_REPORT_FONT'] if k in os.environ}
            child_env.update(PYTHONPATH=str(source.parents[3]),PYTHONIOENCODING='utf-8')
            temporary_root=evidence.directory/'runtime'/'report-render'
            temporary_root.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='render-',dir=temporary_root) as directory:
                directory=Path(directory)
                child_env.update(TEMP=str(directory),TMP=str(directory))
                path=directory/'request.json';output=directory/'report.pdf'
                path.write_text(encode(request),encoding='utf-8')
                result=subprocess.run([sys.executable,'-m','roll.research.company.report_pdf',str(path),str(output)],
                    cwd=directory,env=child_env,capture_output=True,timeout=timeout)
                if result.returncode:
                    detail=result.stderr.decode('utf-8',errors='replace')[-1500:]
                    code=next((c for c in ['PDF_FONT_UNAVAILABLE','PDF_ASSET_MISSING','PDF_ASSET_UNSAFE','PDF_TABLE_TOO_WIDE'] if c in detail),'PDF_RENDER_FAILED')
                    return None,dict(code=code,detail=detail,retryable=True),renderer
                if not output.is_file() or not 1<=output.stat().st_size<=25*1024*1024:
                    raise ValueError('PDF output missing or exceeds25MiB')
                raw=output.read_bytes()
                from io import BytesIO
                from pypdf import PdfReader
                pages=len(PdfReader(BytesIO(raw)).pages)
                if not 1<=pages<=300:raise ValueError('PDF page count outside1–300')
                renderer.update(json.loads(result.stdout.decode('utf-8')),pages=pages)
                return raw,None,renderer
        except subprocess.TimeoutExpired:
            return None,dict(code='PDF_RENDER_TIMEOUT',detail='Bounded render exceeded wall timeout; Markdown retained',retryable=True),renderer
        except Exception as error:
            return None,dict(code='PDF_RENDER_FAILED',detail=str(error)[:1000],retryable=True),renderer

    def download(self, delivery_id, artifact):
        value = self.read(delivery_id)
        formats = dict(markdown=('text/markdown; charset=utf-8','md'), pdf=('application/pdf','pdf'),
            references=('application/json','json'), valuation=('application/json','json'),
            input=('application/json','json'), manifest=('application/json','json'))
        descriptor = value['manifest_archive'] if artifact=='manifest' else value['artifacts'].get(artifact)
        if artifact not in formats or not descriptor:
            fail('REPORT_FILE_NOT_FOUND', 'This delivery has no such registered file', 404)
        media, extension = formats[artifact]
        raw = self.research.evidence.raw(descriptor['sha256']).read_bytes()
        return raw, media, f'report-{value["delivery_id"]}-{artifact}.{extension}'
