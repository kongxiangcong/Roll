"""Relationships for immutable company feature exports and experiment supplements."""
import json
from .service import verified, fingerprint, fail


def require(condition):
    if not condition:
        fail('RESEARCH_REFERENCE_INVALID','Company feature references or canonical archive binding differ',409)


def export_references(value, snapshot):
    require(value['company_id']==snapshot['company_id'] and value['snapshot_id']==snapshot['snapshot_id']
        and value['snapshot_sha256']==snapshot['content_sha256'] and value['core_sha256']==snapshot['core_sha256'])
    require(value['training_started'] is False and value['sealed_read'] is False and value['budget_reserved'] is False)
    for name,feature in value['features'].items():
        refs=feature['source_refs']
        require(refs['snapshot_id']==snapshot['snapshot_id'] and refs['fact_version_ids']==snapshot['fact_version_ids']
            and refs['hypothesis_version_ids']==snapshot['hypothesis_version_ids'] and refs['material_ids']==snapshot['material_ids']
            and refs['economic_review_ids']==snapshot.get('economic_review_ids',[]) and refs['valuation_ids']==snapshot.get('valuation_ids',[])
            and refs['quote_ids']==snapshot.get('quote_ids',[]))
        require(value['missing_mask'][name] == (feature['value'] is None))
        if name=='current_requirement_gap' and feature['economic_status'] not in {'conditional','reviewed'}:
            require(feature['value'] is None)


def validate_features(db, archives):
    names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'company_research_feature_snapshots' not in names:
        return
    snapshots={r[0]:verified(json.loads(r[1])) for r in db.execute('SELECT snapshot_id,value FROM company_research_snapshots')}
    companies={r[0] for r in db.execute('SELECT company_id FROM company_research_companies')}
    def check_archive(value):
        descriptor=value['export_archive']
        body={k:v for k,v in value.items() if k not in {'content_sha256','export_archive'}}
        require(archives.get(descriptor['sha256'])==descriptor and fingerprint(body)==descriptor['sha256'])
    for raw, in db.execute('SELECT value FROM company_research_feature_snapshots'):
        value=verified(json.loads(raw));check_archive(value)
        require(value['snapshot_id'] in snapshots)
        export_references(value,snapshots[value['snapshot_id']])
    if 'company_research_feature_protocols' in names:
        for raw, in db.execute('SELECT value FROM company_research_feature_protocols'):
            value=verified(json.loads(raw));check_archive(value)
            require(set(value['company_ids'])<=companies and fingerprint(value['design'])==value['design_sha256'])
            require(value['training_started'] is False and value['sealed_read'] is False and value['budget_reserved'] is False and value['real_fit_admitted'] is False)
            baseline=value['design']['baseline']
            if baseline:
                require({'research_protocols','research_models'}<=names)
                for table,key,sha_key in [('research_protocols','protocol_id','protocol_sha256'),('research_models','model_id','model_metadata_sha256')]:
                    original=db.execute(f'SELECT value FROM {table} WHERE id=?',(baseline[key],)).fetchone()
                    require(original and fingerprint(json.loads(original[0]))==baseline[sha_key])
