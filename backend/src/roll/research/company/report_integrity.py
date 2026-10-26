"""Company report relationships for existing backup/recovery validation."""
import json
from .service import verified, fail, fingerprint


def validate_reports(db,archives):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='company_research_jobs'").fetchone():
        return
    def load(table,key):
        return {r[0]:verified(json.loads(r[1])) for r in db.execute(f'SELECT {key},value FROM company_research_{table}')}
    jobs=load('jobs','job_id');inputs=load('report_inputs','input_id')
    sections=load('report_sections','section_version_id');reports=load('reports','report_id');runs=load('report_runs','run_id')
    revisions=load('report_revisions','revision_id') if db.execute("SELECT 1 FROM sqlite_master WHERE name='company_research_report_revisions'").fetchone() else {}
    snapshots=load('snapshots','snapshot_id');materials=load('materials','material_id');facts=load('facts','version_id')
    def require(ok):
        if not ok:
            fail('RESEARCH_REFERENCE_INVALID','Report job, frozen input, chapter or publication binding is inconsistent',409)
    def archive(value):
        require(value and archives.get(value['sha256'])==value)
    for packet in inputs.values():
        job=jobs.get(packet['job_id']); payload=packet['payload'];snapshot=payload['snapshot']
        require(job and packet['company_id']==job['company_id'] and fingerprint(payload)==packet['packet_sha256'])
        archive(packet['input_archive'])
        if snapshot:
            require(snapshots.get(snapshot['snapshot_id'])==snapshot and snapshot['company_id']==packet['company_id'] and payload['core_sha256']==snapshot['core_sha256'])
        for item in payload['facts']:
            require(facts.get(item['version_id'])==item and item['company_id']==packet['company_id'])
        for item in payload['materials']:
            require(materials.get(item['material_id'])==item and item['company_id']==packet['company_id'])
        for peer in payload['peers']:
            peer_snapshot=peer['snapshot'];peer_id=peer['company']['company_id']
            require(peer_id!=packet['company_id'] and snapshots.get(peer_snapshot['snapshot_id'])==peer_snapshot and peer_snapshot['company_id']==peer_id)
            for item in peer['facts']:
                require(facts.get(item['version_id'])==item and item['company_id']==peer_id and item['version_id'] in peer_snapshot['fact_version_ids'])
        for item in packet['template']['assets']:
            archive(item['archive']);require(item['sha256']==item['archive']['sha256'])
        archive(packet['template']['gate_map_archive'])
        for name,value in packet.get('algorithm_archives',{}).items():
            archive(value);require(packet['code_hashes'].get(name)==value['sha256'])
        archive(payload['screening_archive'])
        for chart in payload['charts']:
            archive(chart['archive'])
            require(set(chart['fact_version_ids'])<=set(f['version_id'] for f in payload['facts']))
    def revision_binding(value,packet):
        revision=revisions.get(value.get('host_revision_id'))
        require(revision and revision['input_id']==packet['input_id'] and revision['input_sha256']==packet['packet_sha256'] and revision['generation_code_hashes']==packet['code_hashes'])
        return revision
    for revision in revisions.values():
        packet=inputs.get(revision['input_id']);require(packet is not None)
        require(revision['input_sha256']==packet['packet_sha256'] and revision['core_sha256']==packet['payload']['core_sha256'] and revision['generation_code_hashes']==packet['code_hashes'])
        require(revision['original_plan_sha256'] in archives and revision['host_version']=='08.3')
        for name,value in revision['execution_algorithm_archives'].items():
            archive(value);require(revision['execution_code_hashes'][name]==value['sha256'])
        for sid,value in revision['commands'].items():
            archive(value['archive']);require(value['sha256']==value['archive']['sha256'])
        for sid,value in revision['reusable'].items():
            section=sections.get(value['section_version_id']);run=runs.get(value['run_id'])
            require(section and run and section['input_id']==packet['input_id'] and section['job_id']==revision['parent_job_id'] and run['candidate_output_archive']==value['output_archive'])
            archive(value['output_archive'])
        for finding in revision['findings']:
            source=revision['reusable'].get(finding['section_id']);require(source and source['output_archive']['sha256']==finding['output_sha256'])
    for run in runs.values():
        packet=inputs.get(run['input_id']);run_job=jobs.get(run['job_id'])
        require(run_job and packet and run_job['input_id']==packet['input_id'] and run_job['company_id']==packet['company_id'])
        require(packet and run['company_id']==packet['company_id'] and (run['job_id']==packet['job_id'] or (run.get('host_revision_id') and revision_binding(run,packet))) and run['input_sha256']==packet['packet_sha256'] and run['model']==packet['model'])
        if run.get('host_revision_id'):
            revision=revision_binding(run,packet);require(run_job.get('host_revision_id')==revision['revision_id']);require(run['execution_code_hashes']==revision['execution_code_hashes'] and run['command_sha256']==revision['commands'][run['section_id']]['sha256'])
        archive(run['command_archive'])
        if run.get('candidate_output_archive'):
            archive(run['candidate_output_archive'])
    for section in sections.values():
        packet=inputs.get(section['input_id']);run=runs.get(section['run_id'])
        require(packet and run and (section['job_id']==packet['job_id'] or (section.get('host_revision_id') and revision_binding(section,packet))) and section['company_id']==packet['company_id'] and
            section['input_sha256']==packet['packet_sha256'] and section['section_id']==run['section_id'] and run['input_id']==packet['input_id'] and run['company_id']==packet['company_id'])
        require(section['output_archive']==run.get('candidate_output_archive'))
        if section.get('host_revision_id'):
            revision=revision_binding(section,packet);require(jobs[section['job_id']]['host_revision_id']==revision['revision_id'])
            require(section['command_archive']['sha256']==revision['commands'][section['section_id']]['sha256'])
            if section.get('source_section_version_id'):
                source=sections.get(section['source_section_version_id']);binding=revision['reusable'].get(section['section_id']);require(source and binding and binding['section_version_id']==source['section_version_id'] and binding['run_id']==run['run_id'] and source['run_id']==run['run_id'] and source['output_archive']==section['output_archive'] and source['job_id']==run['job_id']==revision['parent_job_id'])
            else:
                require(run['job_id']==section['job_id'] and run.get('host_revision_id')==section['host_revision_id'])
        else:
            require(run['job_id']==section['job_id'])
        require(set(section['reference_ids'])<=set(f['version_id'] for f in [*packet['payload']['facts'],*packet['payload']['peer_facts']]))
        archive(section['command_archive'])
        if section['output_archive']:
            archive(section['output_archive'])
    for report in reports.values():
        packet=inputs.get(report['input_id']);job=jobs.get(report['job_id'])
        require(packet and job and report['company_id']==packet['company_id'] and report['input_sha256']==packet['packet_sha256'])
        snapshot=packet['payload']['snapshot']
        require(report['snapshot_id']==(snapshot['snapshot_id'] if snapshot else None) and report['core']==(snapshot['core'] if snapshot else None) and report['core_sha256']==packet['payload']['core_sha256'])
        require(report['template']==packet['template'] and report['model']==packet['model'])
        require(len(report['quality']['reference_rules'])==94 and report['completeness']==report['quality']['completeness'])
        if report.get('host_revision_id'):
            revision=revision_binding(report,packet);require(job['host_revision_id']==revision['revision_id'] and report['host_revision_archive']['sha256']==fingerprint(revision));archive(report['host_revision_archive'])
        archive(report['markdown_archive'])
        for identifier in report['section_ids']:
            section=sections.get(identifier)
            require(section and section['input_id']==packet['input_id'] and section['job_id']==job['job_id'])
        if report['parent_report_id']:
            parent=reports.get(report['parent_report_id'])
            require(parent and parent['company_id']==report['company_id'])
    for job in jobs.values():
        if job.get('parent_job_id'):
            parent=jobs.get(job['parent_job_id'])
            require(parent and parent['company_id']==job['company_id'])
        if job['snapshot_id']:
            require(job['snapshot_id'] in snapshots and snapshots[job['snapshot_id']]['company_id']==job['company_id'])
        if job.get('host_revision_id'):
            revision=revision_binding(job,inputs[job['input_id']]);archive(job['host_revision_archive']);require(job['host_revision_archive']['sha256']==fingerprint(revision))
        if job['input_id']:
            require(job['input_id'] in inputs and (inputs[job['input_id']]['job_id']==job['job_id'] or (job.get('host_revision_id') and revision_binding(job,inputs[job['input_id']]))))
        if job['report_id']:
            require(job['report_id'] in reports and reports[job['report_id']]['job_id']==job['job_id'])
