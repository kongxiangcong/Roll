"""Inventory actual final report code, caller, fixtures and dedicated runner bytes."""
import hashlib, json
from pathlib import Path
tree=Path(__file__).resolve().parents[5]
paths=['backend/src/roll/research/reports.py','backend/src/roll/runtime/reviews.py','backend/src/roll/app.py',
       'frontend/src/app.tsx','frontend/src/pages/history.tsx','frontend/src/pages/shadow.tsx',
       'frontend/src/components/research-report.tsx','backend/tests/application/test_reports.py',
       'backend/tests/support/report_method_app.py','frontend/playwright.reports.config.ts',
       'frontend/vite.reports.config.ts','frontend/tests/e2e/reports.spec.ts']
entries=[]
for name in paths:
    raw=(tree/name).read_bytes();entries.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
value={'entries':entries,'protected_product_sources':15,'product_source_inventory':'source-final.json',
       'runtime_preservation':'runtime-preservation.json','root_preservation_manifest':'D:/dsh-proj/Roll/.roll-data/implementation-evidence/ticket29-r01/manifest.json',
       'preserved_own_optimizer_cache':'.scratch/t29-vite-cache','excluded_dependency_paths':['frontend/node_modules','frontend/frontend/node_modules','backend/.venv'],
       'dependency_paths_reason':'existing installed packages only; root interpreter and dependency junctions not copied/traversed',
       'private_config_exclusions':'four exact metadata-only paths in runtime-preservation.json',
       'backend_final_run':'31-final-api.log','frontend_final_run':'36-final-browser.log','build_final_run':'35-final-build.log'}
Path(__file__).with_name('handoff-inventory.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
print('12 final implementation/fixture/runner files inventoried; owned cache included, installed dependencies excluded.')
