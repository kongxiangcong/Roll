"""Public METHOD settlement snapshots and immutable original endpoint boundaries."""
import math
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from roll.app import create_app
from test_shadow import setup, freeze
from test_execution_labels import method_archive


def test_later_same_cutoff_sample_does_not_enter_an_earlier_settlement(tmp_path):
    # Direct API client exercises an ordered snapshot contract without entering
    # application lifespan. Real-worker evidence is retained separately.
    clock = [datetime.fromisoformat('2026-06-10T16:00:00+08:00')]
    client = TestClient(create_app(tmp_path, review_clock=lambda: clock[0]))
    try:
        _, protocol, model, dates = setup(client, tmp_path)
        frozen = freeze(client, protocol, model, baseline={'cash_yuan': '1.00', 'positions': []}).json()
        path = '/api/research/complete-freezes/' + frozen['freeze_id'] + '/forward'
        clock[0] = datetime.fromisoformat(dates[110] + 'T16:00:00+08:00')
        client.post(path, json={'purpose': 'METHOD_VALIDATION', 'basis': 'Explicit controlled METHOD sequence'})
        first = client.post(path + '/check', json={'basis': 'First archived sample'}).json()['samples'][0]
        clock[0] = datetime.fromisoformat(dates[130] + 'T16:00:00+08:00')
        assessment = client.post(path + '/settle', json={'basis': 'Snapshot before another same-cutoff sample'}).json()
        assert assessment['shadow']['revision'] == 1
        newer = client.post(path + '/check', json={'basis': 'Later commit, same frozen clock'}).json()
        assert len(newer['samples']) == 2
        assert newer['samples'][-1]['recorded_at'] == assessment['cutoff']
        assert [item['sample_id'] for item in assessment['mature']] == [first['sample_id']]
        assert client.post(path + '/replay').json()['matches_original'] is True
        retained = client.get('/api/data/archives/' + assessment['archive']['sha256']).json()
        assert retained['shadow'] == assessment['shadow']
    finally:
        client.close()


def extended_method(client, directory):
    # Source response/time are agreed external seams. These are synthetic OHLC,
    # never a production evidence packet or a rewritten frozen archive.
    changes = {}
    for index in range(221):
        price = 100 + 12 * math.sin(index / 7)
        changes[index] = {key: str(round(price, 4)) for key in ['open', 'close']}
        changes[index].update(high=str(round(price + 1, 4)), low=str(round(price - 1, 4)),
                              volume_shares=str(10000 + index * 37))
    dates = method_archive(directory, changes, count=221)
    dataset = client.post('/api/research/datasets', json={'archive_id': 'method-execution',
        'method_windows': {'development': 60, 'calibration': 100, 'sealed': 21},
        'basis': 'Extended explicit METHOD endpoint fixture; no real G7'}).json()
    protocol = client.post('/api/research/protocols', json={'dataset_id': dataset['dataset_id'],
        'basis': 'Registered METHOD windows before labels, no altered deadlines'}).json()
    for partition, indices in [('DEVELOPMENT', range(20, 40)), ('CALIBRATION', range(100, 120))]:
        for index in indices:
            response = client.post('/api/research/protocols/' + protocol['protocol_id'] + '/executions', json={
                'partition': partition, 'observation_date': dates[index], 'label_as_of': '2026-10-07T16:00:00+08:00',
                'quantity': '200', 'basis': 'Explicit engineering labels, not production research'})
            assert response.status_code == 201, response.text
    response = client.post('/api/research/protocols/' + protocol['protocol_id'] + '/models', json={
        'purpose': 'METHOD_VALIDATION', 'basis': 'METHOD support only, not qualification'})
    assert response.status_code == 201, response.text
    model = response.json()
    assert model['status'] == 'METHOD_ARTIFACT_ONLY'
    return protocol, model, dates


def test_user_stop_does_not_later_score_outcomes_unmatured_at_original_endpoint(tmp_path):
    clock = [datetime.fromisoformat('2026-06-10T16:00:00+08:00')]
    with TestClient(create_app(tmp_path, review_clock=lambda: clock[0])) as client:
        _, protocol, model, dates = setup(client, tmp_path)
        clock[0] = datetime.fromisoformat(dates[110] + 'T16:00:00+08:00')
        frozen = freeze(client, protocol, model).json()
        path = '/api/research/complete-freezes/' + frozen['freeze_id'] + '/forward'
        client.post(path, json={'purpose': 'METHOD_VALIDATION', 'basis': 'Stopped METHOD endpoint'})
        client.post(path + '/check', json={'basis': 'One original forecast'})
        stopped = client.post(path + '/stop', json={'kind': 'USER_STOP', 'basis': 'Original early endpoint'}).json()
        endpoint = stopped['endpoint']
        assert len(endpoint['unmatured']) == 1 and endpoint['mature'] == []
        clock[0] = datetime.fromisoformat(dates[130] + 'T16:00:00+08:00')
        late = client.post(path + '/settle', json={'basis': 'Later clock cannot extend original scoring'}).json()
        assert late['cutoff'] == endpoint['cutoff']
        assert late['unmatured'] == endpoint['unmatured'] and late['mature'] == []
        assert client.get(path).json()['endpoint'] == endpoint
        assert client.post(path + '/replay').json()['matches_original'] is True


def test_natural_month_deadline_keeps_original_unmatured_results_after_later_settlement(tmp_path):
    clock = [datetime.fromisoformat('2026-01-05T14:00:00+08:00')]
    with TestClient(create_app(tmp_path, review_clock=lambda: clock[0])) as client:
        protocol, model, dates = extended_method(client, tmp_path)
        clock[0] = datetime.fromisoformat(dates[80] + 'T16:00:00+08:00')
        frozen = freeze(client, protocol, model).json()
        path = '/api/research/complete-freezes/' + frozen['freeze_id'] + '/forward'
        client.post(path, json={'purpose': 'METHOD_VALIDATION', 'basis': 'Real natural-month algorithm, synthetic source'})
        first = client.post(path + '/check', json={'basis': 'First METHOD receipt'}).json()
        deadline = datetime.fromisoformat(first['method_deadline'])
        last_day = max(day for day in dates if day < deadline.date().isoformat())
        clock[0] = datetime.fromisoformat(last_day + 'T16:00:00+08:00')
        last = client.post(path + '/check', json={'basis': 'Near original endpoint'}).json()['samples'][-1]
        assert datetime.fromisoformat(last['action']['maturity_date'] + 'T15:05:00+08:00') > deadline
        clock[0] = deadline
        ended = client.post(path + '/check', json={'basis': 'Inclusive original natural-month boundary'}).json()
        endpoint = ended['endpoint']
        assert any(item['sample_id'] == last['sample_id'] for item in endpoint['unmatured'])
        clock[0] = datetime.fromisoformat(last['action']['maturity_date'] + 'T16:00:00+08:00') + timedelta(days=1)
        late = client.post(path + '/settle', json={'basis': 'Later facts cannot prolong original experiment'}).json()
        assert late['cutoff'] == endpoint['cutoff'] == first['method_deadline']
        assert late['mature'] == endpoint['mature'] and late['unmatured'] == endpoint['unmatured']
        assert client.get(path).json()['endpoint'] == endpoint
        assert client.get(path).json()['forward_started_at'] is None
        assert client.post(path + '/replay').json()['matches_original'] is True
