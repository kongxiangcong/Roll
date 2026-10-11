"""The default pytest command selects current CODEX scope, without executing providers."""
import os
from pathlib import Path
import subprocess
import sys


def test_default_collection_excludes_positive_deepseek_but_keeps_current_contracts():
    backend=Path(__file__).resolve().parents[2]
    result=subprocess.run([sys.executable,'-B','-m','pytest','--collect-only','-q','-p','no:cacheprovider'],
        cwd=backend,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    nodes=[line for line in result.stdout.splitlines() if '.py::' in line]
    historical=['test_backend_switch.py::','test_deepseek_evidence.py::','test_deepseek_process.py::',
        '::test_deepseek_sdk_review_uses_the_same_material_contract_and_freezes_runtime_versions',
        '::test_cross_backend_retry_rejects_revised_archive_and_preserves_original',
        '::test_agent_child_preserves_explicit_fuyao_adjustment_source[DEEPSEEK]']
    assert not [node for node in nodes if any(name in node for name in historical)],result.stdout
    for current in ['test_codex_only_scope.py::','::test_cancel_timeout_retry_and_acquisition_share_the_same_frozen_execution_slot',
                    '::test_agent_child_preserves_explicit_fuyao_adjustment_source[CODEX]',
                    'test_capabilities.py::']:
        assert any(current in node for node in nodes),current
