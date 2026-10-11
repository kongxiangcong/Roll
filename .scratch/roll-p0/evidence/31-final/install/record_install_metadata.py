"""Read installed public package metadata only; do not import the application."""
import importlib.metadata as metadata
import json
import platform
import sqlite3
import sys
from pathlib import Path
import roll

directory=Path(__file__).resolve().parent
source=directory.parents[4]/'backend'/'src'
roll_path=Path(roll.__file__).resolve()
assert roll_path.is_relative_to(source.resolve()),(roll_path,source)
packages=[]
for distribution in metadata.distributions():
    packages.append({'name':distribution.metadata['Name'],'version':distribution.version,
        'location':str(distribution.locate_file('').resolve()),
        'license_expression':distribution.metadata.get('License-Expression'),
        'license':distribution.metadata.get('License'),
        'license_files':distribution.metadata.get_all('License-File',[])})
report={'python':sys.version,'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,
        'sqlite_library':sqlite3.sqlite_version,'os':platform.platform(),'machine':platform.machine(),
        'roll_module_path':str(roll_path),'packages':sorted(packages,key=lambda r:r['name'].lower()),
        'application_imported':False,'database_connections':0,'provider_calls':0,'fits':0,'forecasts':0,
        'test_runs':0,'physical_venv':not Path(sys.prefix).is_symlink()}
(directory/'python-installed.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'roll_module':str(roll_path),
                  'packages':len(packages),'physical_venv':report['physical_venv']},ensure_ascii=False))
