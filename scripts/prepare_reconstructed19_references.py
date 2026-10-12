"""Verify archived official originals and pin only rule/equity audit locators."""
import hashlib,json,re
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-09'
REF=ROOT/'backend/src/roll/research/reference/reconstruction'
def main():
    REF.mkdir(parents=True,exist_ok=True)
    gap=BASE/'.roll-data/gap-research-v1'
    records=[r for n in ['manifest.json','annual-additional-manifest.json'] for r in json.loads((gap/n).read_text(encoding='utf-8'))['records'] if r.get('sha256')]
    annual=[];imports=[]
    for year in range(2016,2024):
        if year==2022:
            r=json.loads((BASE/'annual-report-2022-followup.json').read_text(encoding='utf-8'));path=Path(r['path']);page=81
        else:
            r=next(r for r in records if str(year) in r['title'] and '半年度' not in r['title'] and '修订' not in r['title'])
            path=gap/r['path']
            page=next((p['pdf_page'] for p in r['selected_status_action_pages'] if '未发生变化' in p['text'] and '股本结构' in p['text']),None)
            if page is None:
                reader=PdfReader(path)
                page=next(i+1 for i,p in enumerate(reader.pages[:100]) if '股本结构未发生变化' in re.sub(r'\s+','',p.extract_text()))
        body=path.read_bytes();assert len(body)==r['bytes'] and hashlib.sha256(body).hexdigest()==r['sha256']
        text=PdfReader(path).pages[page-1].extract_text();compact=re.sub(r'\s+','',text)
        assert '股本结构未发生变化' in compact
        start=compact.index('报告期内');end=compact.index('未发生变化',start)+len('未发生变化')
        claim=compact[start:end]
        annual.append({'year':year,'sha256':r['sha256'],'bytes':r['bytes'],'file':path.name,'url':r['url'],'received_at':r['received_at'],
            'pdf_page':page,'statement':claim,'purpose':'RETROSPECTIVE_SHARE_STRUCTURE_AUDIT_ONLY; NEVER_A_MODEL_FEATURE'})
        imports.append({'path':str(path),'kind':'RECONSTRUCTED_EQUITY_AUDIT_SOURCE','metadata':annual[-1]})
    rules=json.loads((gap/'additional-primary-manifest.json').read_text())
    rule=next(r for r in rules if r['name']=='rules-2012');body=(gap/rule['path']).read_bytes();assert hashlib.sha256(body).hexdigest()==rule['sha256']
    (REF/'sse-rules-2013.html').write_bytes(body)
    manifest={'version':'19-reconstruction-references-v1','instrument':'SSE:600362','scope':['2016-12-01','2023-12-31'],
        'share_structure_audits':annual,'rule_source':{k:rule[k] for k in ['url','received_at','sha256','bytes']},
        'rule_file':'sse-rules-2013.html','rule_scope':'NORMAL_SSE_MAIN_100_LOT_T1_TICK001_LIMIT10_DAILY_ONLY',
        'limitations':['ANNUAL_RETROSPECTIVE_AUDIT_IS_NOT_HISTORICAL_PIT','CASH_INVENTORY_AND_UNCHANGED_SHARE_STRUCTURE_NOT_UNIVERSAL_CORPORATE_ACTION_PROOF','DAILY_TRADE_AND_ST_FLAGS_NOT_INTRADAY_EXECUTION_PROOF']}
    (REF/'sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/reference-imports.json').write_text(json.dumps(imports,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'annual':annual,'rule_sha256':rule['sha256']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
