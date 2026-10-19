"""Read-only METHOD baseline overlay: restore pre18 module code in memory only."""
import importlib.abc,importlib.util,subprocess,sys,json,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parents[4];sys.path.insert(0,str(repo/'backend/src'))
files={'roll.app':'backend/src/roll/app.py','roll.decisions.notifications':'backend/src/roll/decisions/notifications.py','roll.runtime.reviews':'backend/src/roll/runtime/reviews.py'}
sources={name:subprocess.check_output(['git','show','c891d57:'+path],cwd=repo) for name,path in files.items()}
# Preserve the actual pre18 dirty worker context, rather than silently removing it.
sources['roll.runtime.reviews']=(repo/'.scratch/r18-protected/reviews-before.py').read_bytes()
class Loader(importlib.abc.Loader):
 def __init__(self,name):self.name=name
 def create_module(self,spec):return None
 def exec_module(self,module):
  original=str(repo/files[self.name]);module.__file__=original
  exec(compile(sources[self.name],original,'exec'),module.__dict__)
class Finder(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in sources:return importlib.util.spec_from_loader(fullname,Loader(fullname),origin=str(repo/files[fullname]))
sys.meta_path.insert(0,Finder())
print(json.dumps({'baseline':'c891d57 pre18 app/notifications and exact saved pre18 dirty worker; in-memory loader only, disk untouched','modules':{name:hashlib.sha256(value).hexdigest() for name,value in sources.items()}},indent=2),flush=True)
import pytest
raise SystemExit(pytest.main(['-q','--basetemp=../.scratch/r18-notification-baseline',
 'tests/application/test_notifications.py::test_notification_time_chain_augments_intent_query_without_rewriting_original_unknowns',
 'tests/application/test_notifications.py::test_revoke_inflight_preserves_accepted_body_appends_critical_invalidation_without_writer_wait',
 'tests/application/test_notifications.py::test_external_operation_pending_sync_notice_survives_revoke_and_original_intent_is_preserved']))
