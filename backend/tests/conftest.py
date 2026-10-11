"""Current CODEX acceptance scope; positive DeepSeek suites remain historical files."""
collect_ignore=['application/test_backend_switch.py','application/test_deepseek_evidence.py',
                'recovery/test_deepseek_process.py']


def pytest_collection_modifyitems(config,items):
    historical_files={'test_backend_switch.py','test_deepseek_evidence.py','test_deepseek_process.py'}
    historical_cases={
        ('test_agent_source_contract.py','test_cross_backend_retry_rejects_revised_archive_and_preserves_original'),
        ('test_technical_review.py','test_deepseek_sdk_review_uses_the_same_material_contract_and_freezes_runtime_versions')}
    excluded=[];current=[]
    for item in items:
        case=item.nodeid.split('::')[-1].split('[')[0]
        if item.path.name in historical_files or (item.path.name,case) in historical_cases:
            excluded.append(item)
        else:current.append(item)
    if excluded:config.hook.pytest_deselected(items=excluded)
    items[:]=current
