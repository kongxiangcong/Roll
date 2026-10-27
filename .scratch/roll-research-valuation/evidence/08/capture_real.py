"""Read public report records and copy exact registered bytes, without exposure APIs."""
import argparse
import hashlib
import json
from pathlib import Path
import httpx


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',required=True);parser.add_argument('--base-url',required=True);parser.add_argument('--output-directory',required=True)
    args=parser.parse_args();prepared=json.loads(Path(args.prepare).read_bytes());root=Path(prepared['data_directory']).resolve()
    target=Path(args.output_directory);target.mkdir(parents=True,exist_ok=True);manifest=[]
    def write(name,value):
        (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def copy(name,archive):
        source=(root/archive['path']).resolve()
        if not source.is_relative_to(root):raise RuntimeError('Unsafe registered archive path')
        raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest!=archive['sha256']:raise RuntimeError('Registered archive bytes changed')
        (target/name).write_bytes(raw);manifest.append(dict(file=name,sha256=digest,bytes=len(raw),archive=archive))
    with httpx.Client(base_url=args.base_url,timeout=20) as client:
        def get(path):
            response=client.get('/api/company-research'+path);response.raise_for_status();return response.json()
        job=get('/jobs/'+prepared['job_id']);write('job.json',job)
        report=get('/reports/'+job['report_id']) if job['report_id'] else None
        packet=get('/report-inputs/'+job['input_id']) if job['input_id'] else None
        if report:
            write('report.json',report);copy('report.md',report['markdown_archive'])
        if packet:
            write('packet.json',packet);copy('frozen-input.json',packet['input_archive'])
        sections=[];runs=[]
        for identifier in job['section_ids']:
            section=get('/report-sections/'+identifier);run=get('/report-runs/'+section['run_id']);sid=section['section_id']
            sections.append(section);runs.append(run);write('run-'+sid+'.json',run)
            copy('command-'+sid+'.json',run['command_archive'])
            if run.get('candidate_output_archive'):copy('output-'+sid+'.json',run['candidate_output_archive'])
        write('sections.json',sections)
        for index,receipt in enumerate(job['acquisition'].get('receipts',[])):
            if receipt.get('raw_archive'):copy('source-'+str(index)+'.pdf',receipt['raw_archive'])
        write('manifest.json',manifest)
        if not report:
            summary=dict(job_id=job['job_id'],status=job['status'],stage=job['stage'],section_count=len(sections),
                chapter_statuses={s['section_id']:s['status'] for s in sections},real_turns_started=sum(bool(r.get('runtime_turn_id')) for r in runs),
                generated_raw_outputs=sum(bool(r.get('candidate_output_archive')) for r in runs),accepted_real_chapters=sum(r['evidence_kind']=='REAL_MODEL_CHAPTER' for r in runs),
                raw_capture_count=len(manifest),snapshot_id=job['snapshot_id'],input_sha256=packet['packet_sha256'] if packet else None,
                model_requests_from_capture=0,network_refreshes_from_capture=0)
            write('summary.json',summary);print(json.dumps(summary,ensure_ascii=False));return
        summary=dict(job_id=job['job_id'],report_id=report['report_id'],snapshot_id=report['snapshot_id'],core_sha256=report['core_sha256'],
            completeness=report['completeness'],chapter_statuses={s['section_id']:s['status'] for s in sections},
            confirmed_real_chapters=sum(r['evidence_kind']=='REAL_MODEL_CHAPTER' for r in runs),
            source_status=job['acquisition']['status'],core_origin=prepared['snapshot_origin'],
            current_status=packet['payload']['valuation_presentation']['status'],baseline_status=packet['payload']['valuation_binding']['baseline']['status'],
            source_network_attempts=len(job['acquisition'].get('receipts',[])),raw_capture_count=len(manifest),
            unincorporated_material_ids=packet['payload']['unincorporated_material_ids'],historical_pit_eligible=False,
            quality_counts={outcome:sum(r['outcome']==outcome for r in report['quality']['reference_rules']) for outcome in ['PASS','FAIL','UNKNOWN','NOT_APPLICABLE']})
        write('summary.json',summary);print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
