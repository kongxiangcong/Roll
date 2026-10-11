"""Fresh host-bound METHOD browser evidence; no actual qualification/provider."""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from roll.app import create_app
from capability_method_app import save_package
from test_capability_monitoring import monitored_package


def factory():
    directory = Path(os.environ['ROLL_DATA_DIR'])
    file = directory.parent / 'qualification.json'
    clock_file = directory.parent / 'method-clock.json'
    if not file.exists():
        package = monitored_package(20, outside=4)
        instant = datetime.fromisoformat(package['required_as_of'])
        later = instant + timedelta(seconds=2)
        package['monitoring_basis']['observations'] += [{'observation_date':day,'known_at':later.isoformat(),
            'instrument':'SSE:600001','features':{'x':50},'source_binding':'literal-later-'+day}
            for day in package['monitoring_basis']['eligible_sessions']]
        save_package(file, package)
        clock_file.write_text(json.dumps({'time':instant.isoformat(),'later':later.isoformat(),
            'namespace':'METHOD_ENGINEERING','system_usable':False}),encoding='utf-8')
    def clock(): return datetime.fromisoformat(json.loads(clock_file.read_text(encoding='utf-8'))['time'])
    # Native isolated host time seam, as used by public API tests. This is not a
    # production endpoint or permission override. The immutable package holds
    # both fixed inputs and their explicit METHOD first-knowledge cutoffs.
    import roll.decisions.capabilities as capabilities
    import roll.decisions.actions as actions
    import roll.decisions.monitoring as monitoring
    capabilities.now = actions.now = monitoring.now = lambda: clock().isoformat()
    return create_app(directory, capability_method_file=file, review_clock=clock)
