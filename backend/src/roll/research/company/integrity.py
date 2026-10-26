"""Verify research JSON relationships when the existing backup enumerates files."""
import json

from .service import fail, verified


def validate_references(db):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'company_research_companies' not in names:
        return
    companies = [verified(json.loads(r[0])) for r in db.execute('SELECT value FROM company_research_companies')]
    company_ids = {c['company_id'] for c in companies}
    listings = {r[0]: verified(json.loads(r[1])) for r in db.execute('SELECT version_id,value FROM company_research_listings')}
    archives = {r[0]: json.loads(r[1]) for r in db.execute('SELECT sha256,value FROM evidence_archives')}
    materials = {r[0]: verified(json.loads(r[1])) for r in db.execute('SELECT material_id,value FROM company_research_materials')}
    facts = {r[0]: verified(json.loads(r[1])) for r in db.execute('SELECT version_id,value FROM company_research_facts')}

    def require(condition):
        if not condition:
            fail('RESEARCH_REFERENCE_INVALID', 'Company research references are missing or inconsistent', 409)

    for company in companies:
        for listing in company['listings']:
            verified(listing)
            require(listing['company_id'] == company['company_id'] and listings.get(listing['version_id']) == listing)
    for material in materials.values():
        require(material['company_id'] in company_ids)
        archive = material['archive']
        require(archives.get(archive['sha256']) == archive and material['raw_sha256'] == archive['sha256'])
    for fact in facts.values():
        material = materials.get(fact['material_id'])
        require(material and material['company_id'] == fact['company_id'] and
                material['archive']['sha256'] == fact['archive_sha256'])
        if fact['supersedes']:
            parent = facts.get(fact['supersedes'])
            require(parent and parent['company_id'] == fact['company_id'] and parent['fact_id'] == fact['fact_id'])
    for row in db.execute('SELECT value FROM company_research_conflict_resolutions'):
        resolution = verified(json.loads(row[0]))
        require(resolution['company_id'] in company_ids)
        for version_id in resolution['version_ids']:
            fact = facts.get(version_id)
            require(fact and fact['company_id'] == resolution['company_id'] and fact['fact_id'] == resolution['fact_id'])
        require(resolution['selected_version_id'] is None or resolution['selected_version_id'] in resolution['version_ids'])
    for row in db.execute('SELECT value FROM company_research_checks'):
        check = verified(json.loads(row[0]))
        require(check['company_id'] in company_ids)
        for material_id in check['material_ids']:
            require(material_id in materials and materials[material_id]['company_id'] == check['company_id'])
    for row in db.execute('SELECT result FROM company_research_commands'):
        verified(json.loads(row[0]))
    from .analysis_integrity import validate_analysis
    validate_analysis(db, archives, materials, facts, companies)

    from .valuation_integrity import validate_valuations
    validate_valuations(db, archives, companies)
