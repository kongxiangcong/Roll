"""Append-only market observations and offline DataSnapshot selection."""

from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json

from roll.market.calendar import extended_sessions, is_session
from roll.v3.etf_observations import (
    DISCLOSURE_SELECTION_RULES, DISCLOSURE_SERIES, ETF_SELECTION_RULES, ETF_SERIES, disclosure_observation,
    etf_observation, etf_visible_at, select_etf_observation,
)
from roll.v3.storage import SHANGHAI, database, ensure_schema, instant


STRICT_HISTORICAL_AS_OF = 'STRICT_HISTORICAL_AS_OF'
RECONSTRUCTED_RESEARCH = 'RECONSTRUCTED_RESEARCH'
LIVE_RUN = 'LIVE_RUN'
USE_MODES = (STRICT_HISTORICAL_AS_OF, RECONSTRUCTED_RESEARCH, LIVE_RUN)
SELECTION_RULES_VERSION = 'market-v1'
DEFAULT_SOURCE_PRIORITY = ('fuyao', 'investoday')

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observation (
    seq INTEGER PRIMARY KEY,
    series TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    item_id TEXT NOT NULL,
    source TEXT NOT NULL,
    source_ref TEXT,
    revision TEXT,
    available_at TEXT,
    available_evidence TEXT,
    received_at TEXT NOT NULL,
    assumed_available_at TEXT,
    availability_assumption TEXT,
    unit TEXT NOT NULL,
    quality TEXT NOT NULL,
    reconstruction_only INTEGER NOT NULL,
    withdrawn INTEGER NOT NULL,
    payload TEXT NOT NULL,
    supersedes_seq INTEGER REFERENCES observation(seq)
);
CREATE INDEX IF NOT EXISTS observation_key
    ON observation(series, symbol, trade_date, item_id, source, seq);
CREATE TABLE IF NOT EXISTS data_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    as_of TEXT NOT NULL,
    max_seq INTEGER NOT NULL,
    use_mode TEXT NOT NULL,
    scope TEXT NOT NULL,
    selection_rules_version TEXT NOT NULL,
    source_priority TEXT NOT NULL
);
"""

_VERSION_FIELDS = (
    'source_ref', 'revision', 'available_at', 'available_evidence', 'assumed_available_at',
    'availability_assumption', 'unit', 'quality', 'reconstruction_only', 'withdrawn', 'payload',
)


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def utc_timestamp(value):
    return instant(value).astimezone(timezone.utc).isoformat(timespec='microseconds')


def append_observations(data_dir, observations):
    """Append changed observations and return their committed version waterline."""
    with database(data_dir) as db:
        db.executescript(_SCHEMA)
        db.execute('BEGIN IMMEDIATE')
        first = _waterline(db)
        extension = extended_sessions(db)
        for item in observations:
            series = item['series']
            if series in ETF_SERIES:
                item = etf_observation(item, extension=extension)
            elif series in DISCLOSURE_SERIES:
                item = disclosure_observation(item)
            item_id = item.get('item_id', '')
            payload = item.get('payload', {})
            if series == 'research_feature':
                feature = payload.get('feature', item_id) if isinstance(payload, dict) else None
                if (not isinstance(feature, str) or not feature.strip() or (item_id and item_id != feature)
                        or not (item.get('withdrawn') or type(payload.get('value')) in (str, bool, int, float))):
                    raise ValueError("research_feature 须指定一致的特征标识及标量 value")
                item_id = feature
                payload = {**payload, 'feature': feature}
            key = (series, item['symbol'].upper(), str(date.fromisoformat(item['trade_date'])),
                   item_id, item['source'])
            version = {
                'source_ref': item.get('source_ref'),
                'revision': item.get('revision'),
                'available_at': _optional_time(item.get('available_at')),
                'available_evidence': item.get('available_evidence'),
                'assumed_available_at': _optional_time(item.get('assumed_available_at')),
                'availability_assumption': item.get('availability_assumption'),
                'unit': _encode(item.get('unit', {})),
                'quality': item.get('quality', 'usable'),
                'reconstruction_only': int(item.get('reconstruction_only', False)),
                'withdrawn': int(item.get('withdrawn', False)),
                'payload': _encode(payload),
            }
            previous = db.execute("""
                SELECT * FROM observation
                WHERE series=? AND symbol=? AND trade_date=? AND item_id=? AND source=?
                ORDER BY seq DESC LIMIT 1
            """, key).fetchone()
            if previous and all(previous[field] == version[field] for field in _VERSION_FIELDS):
                continue
            db.execute("""
                INSERT INTO observation(series,symbol,trade_date,item_id,source,
                    source_ref,revision,available_at,available_evidence,assumed_available_at,
                    availability_assumption,unit,quality,reconstruction_only,withdrawn,payload,received_at,supersedes_seq)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (*key, *(version[field] for field in _VERSION_FIELDS),
                  utc_timestamp(item['received_at']), previous['seq'] if previous else None))
        last = _waterline(db)
        db.commit()
    return {'appended': last - first, 'max_seq': last}


def _optional_time(value):
    return utc_timestamp(value) if value else None


def _waterline(db):
    return db.execute('SELECT COALESCE(MAX(seq), 0) FROM observation').fetchone()[0]


def prepare_snapshot(data_dir, *, as_of, use_mode, scope, source_priority=DEFAULT_SOURCE_PRIORITY, db=None):
    """Capture inputs and a waterline for a local read without storing a new snapshot."""
    if use_mode not in USE_MODES:
        raise ValueError(f'未知快照用途 {use_mode}')
    scope = sorted({
        (item['series'], item['symbol'].upper(), str(date.fromisoformat(item['start'])),
         str(date.fromisoformat(item['end'])))
        for item in scope
    })
    if not scope or any(start > end for _, _, start, end in scope):
        raise ValueError('快照需要有效的输入区间')
    normalized = [dict(series=series, symbol=symbol, start=start, end=end)
                  for series, symbol, start, end in scope]
    all_series = {series for series, *_ in scope}
    rules = SELECTION_RULES_VERSION
    if all_series.intersection(DISCLOSURE_SERIES):
        rules = DISCLOSURE_SELECTION_RULES
    elif all_series.intersection(ETF_SERIES):
        rules = ETF_SELECTION_RULES
    with database(data_dir, db=db) as connection:
        ensure_schema(connection, _SCHEMA)
        return {
            'as_of': utc_timestamp(as_of), 'max_seq': _waterline(connection), 'use_mode': use_mode,
            'scope': normalized, 'selection_rules_version': rules,
            'source_priority': list(dict.fromkeys(source_priority)),
        }


def freeze_snapshot(data_dir, *, as_of, use_mode, scope, source_priority=DEFAULT_SOURCE_PRIORITY, db=None):
    """Freeze an observation waterline, input scope, purpose and version-selection policy."""
    with database(data_dir, write=True, db=db) as connection:
        snapshot = prepare_snapshot(data_dir, as_of=as_of, use_mode=use_mode, scope=scope,
                                    source_priority=source_priority, db=connection)
        return persist_snapshot(data_dir, snapshot, db=connection)


def persist_snapshot(data_dir, snapshot, *, db=None):
    """Store a DataSnapshot already prepared in the caller's transaction."""
    snapshot_id = sha256(_encode(snapshot).encode()).hexdigest()
    with database(data_dir, write=True, db=db) as connection:
        ensure_schema(connection, _SCHEMA)
        connection.execute("""
            INSERT OR IGNORE INTO data_snapshot(snapshot_id,as_of,max_seq,use_mode,scope,
                                               selection_rules_version,source_priority)
            VALUES(?,?,?,?,?,?,?)
        """, (snapshot_id, snapshot['as_of'], snapshot['max_seq'], snapshot['use_mode'], _encode(snapshot['scope']),
              snapshot['selection_rules_version'], _encode(snapshot['source_priority'])))
    return {'snapshot_id': snapshot_id, **snapshot}


def list_snapshots(data_dir, symbol):
    """List stored daily-bar snapshots for research selection."""
    with database(data_dir) as db:
        ensure_schema(db, _SCHEMA)
        rows = db.execute("""
            SELECT snapshot_id, as_of, use_mode, scope FROM data_snapshot AS snapshot
            WHERE EXISTS (
                SELECT 1 FROM json_each(snapshot.scope)
                WHERE json_extract(value, '$.symbol') = ? AND json_extract(value, '$.series') = 'daily_bar'
            )
            ORDER BY as_of DESC, max_seq DESC, snapshot_id
        """, (symbol.upper(),)).fetchall()
    return [{**dict(row), 'scope': json.loads(row['scope'])} for row in rows]


def get_snapshot(data_dir, snapshot_id, *, db=None):
    with database(data_dir, db=db) as connection:
        ensure_schema(connection, _SCHEMA)
        return _snapshot(connection, snapshot_id)


def _snapshot(db, snapshot_id):
    row = db.execute('SELECT * FROM data_snapshot WHERE snapshot_id=?', (snapshot_id,)).fetchone()
    if row is None:
        raise ValueError(f'数据快照不存在 {snapshot_id}')
    result = dict(row)
    result['scope'] = json.loads(result['scope'])
    result['source_priority'] = json.loads(result['source_priority'])
    if result['selection_rules_version'] not in (SELECTION_RULES_VERSION, ETF_SELECTION_RULES, DISCLOSURE_SELECTION_RULES):
        raise ValueError(f"未知选源规则 {result['selection_rules_version']}")
    return result


def _ranges(snapshot, series, symbol, start, end):
    for item in snapshot['scope']:
        if (series and item['series'] != series) or (symbol and item['symbol'] != symbol.upper()):
            continue
        left = max(item['start'], start) if start else item['start']
        right = min(item['end'], end) if end else item['end']
        if left <= right:
            yield {**item, 'start': left, 'end': right}


def _observations(db, snapshot, scope):
    rows = db.execute("""
        SELECT * FROM observation
        WHERE seq<=? AND series=? AND symbol=? AND trade_date BETWEEN ? AND ?
        ORDER BY trade_date,item_id,source,seq
    """, (snapshot['max_seq'], scope['series'], scope['symbol'], scope['start'], scope['end']))
    groups = defaultdict(list)
    for row in rows:
        item_id = '' if _uses_etf_rules(row, snapshot) else row['item_id']
        groups[row['trade_date'], item_id].append(row)
    return groups


def _uses_etf_rules(row, snapshot):
    return (row['series'] in ETF_SERIES
            and snapshot.get('selection_rules_version') in (ETF_SELECTION_RULES, DISCLOSURE_SELECTION_RULES))


def _visible_at(row, snapshot):
    if row['series'] in DISCLOSURE_SERIES or _uses_etf_rules(row, snapshot):
        return etf_visible_at(row, snapshot)
    verified = row['available_at'] if row['available_evidence'] else None
    mode = snapshot['use_mode']
    if row['reconstruction_only'] and mode != RECONSTRUCTED_RESEARCH:
        return None
    if mode == STRICT_HISTORICAL_AS_OF:
        return verified
    if mode == LIVE_RUN:
        return max(row['received_at'], row['available_at'] or row['received_at'])
    if row['received_at'] > snapshot['as_of']:
        return None
    assumed = row['assumed_available_at'] if row['availability_assumption'] else None
    return verified or row['available_at'] or assumed or row['received_at']


def _current_versions(rows, snapshot, cutoff, *, separate_items=False):
    current = {}
    for row in rows:
        visible_at = _visible_at(row, snapshot)
        if visible_at is None or visible_at > cutoff:
            continue
        key = (row['source'], row['item_id']) if separate_items else row['source']
        if key not in current or (visible_at, row['seq']) > (current[key][0], current[key][1]['seq']):
            current[key] = (visible_at, row)
    return current


def _decoded_observation(row, visible_at):
    return {**dict(row), 'payload': json.loads(row['payload']), 'unit': json.loads(row['unit']),
            'withdrawn': bool(row['withdrawn']), 'reconstruction_only': bool(row['reconstruction_only']),
            'selected_available_at': visible_at}


def _choose(rows, snapshot, cutoff, *, candidates=None):
    if not rows:
        return None, 'missing'
    etf = _uses_etf_rules(rows[0], snapshot)
    current = _current_versions(rows, snapshot, cutoff, separate_items=etf)
    if not current:
        return None, 'not_visible'
    if etf:
        versions = [_decoded_observation(row, at) for at, row in current.values()]
        if candidates is not None:
            candidates.extend(versions)
        return select_etf_observation(versions)

    ranking = {source: position for position, source in enumerate(snapshot['source_priority'])}
    candidates = [(ranking.get(source, len(ranking)), row['seq'], row)
                  for source, (_, row) in current.items() if not row['withdrawn']]
    if not candidates:
        return None, 'withdrawn'
    candidates.sort()
    rank, _, chosen = candidates[0]
    if any((row['payload'], row['unit'], row['quality']) !=
           (chosen['payload'], chosen['unit'], chosen['quality'])
           for priority, _, row in candidates[1:] if priority == rank):
        return None, 'conflict'
    if chosen['quality'] != 'usable':
        return None, chosen['quality']

    result = _decoded_observation(chosen, current[chosen['source']][0])
    result['alternative_sources'] = [row['source'] for _, _, row in candidates[1:]]
    return result, 'usable'


def _date_range(start, end):
    day = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while day <= stop:
        yield day
        day += timedelta(days=1)


def _coverage(scope, observations, states, warmup):
    price_series = scope['series'] in {'daily_bar', 'daily_open'}
    actual = sorted({row['trade_date'] for row in observations})
    expected = []
    calendar_unknown = []
    if price_series:
        for day in _date_range(scope['start'], scope['end']):
            try:
                if is_session(day):
                    expected.append(str(day))
            except ValueError:
                calendar_unknown.append(str(day))
    day_states = defaultdict(list)
    for (day, _), status in states.items():
        day_states[day].append(status)
    suspended = sorted({row['trade_date'] for row in observations
                        if row['payload'].get('trading_status') == 'suspended'})
    usable = set(actual) - set(suspended)
    gaps = [day for day in expected if day not in actual]
    count = 0
    evaluable = []
    for day in expected:
        if day in usable:
            count += 1
            if count > warmup:
                evaluable.append(day)
        else:
            count = 0
    return {
        **scope, 'first_date': actual[0] if actual else None,
        'last_date': actual[-1] if actual else None, 'expected_count': len(expected) if price_series else None,
        'observation_count': len(observations), 'effective_count': len(usable),
        'suspended_dates': suspended, 'gap_dates': gaps, 'calendar_unknown_dates': calendar_unknown,
        'withdrawn_dates': sorted(day for day, statuses in day_states.items()
                                  if 'withdrawn' in statuses and day not in actual),
        'quality_by_date': {day: sorted(set(statuses)) for day, statuses in sorted(day_states.items())
                            if statuses != ['usable']},
        'warmup_sessions': warmup, 'evaluable_first': evaluable[0] if evaluable else None,
        'evaluable_last': evaluable[-1] if evaluable else None, 'evaluable_count': len(evaluable),
    }


def read_snapshot(data_dir, snapshot_id, *, series='daily_bar', symbol=None, start=None, end=None,
                  cutoff=None, warmup=0, include_candidates=False, db=None):
    """Inspect a persisted snapshot or a locally prepared observation waterline."""
    with database(data_dir, db=db) as connection:
        ensure_schema(connection, _SCHEMA)
        snapshot = snapshot_id if isinstance(snapshot_id, dict) else _snapshot(connection, snapshot_id)
        cutoff = min(utc_timestamp(cutoff), snapshot['as_of']) if cutoff else snapshot['as_of']
        cutoff_day = str(datetime.fromisoformat(cutoff).astimezone(SHANGHAI).date())
        selected = {}
        coverage = []
        details = []
        for scope in _ranges(snapshot, series, symbol, start, end):
            observations = []
            states = {}
            for key, rows in _observations(connection, snapshot, scope).items():
                candidates = [] if include_candidates else None
                if key[0] > cutoff_day:
                    observation, states[key] = None, 'not_visible'
                else:
                    observation, states[key] = _choose(rows, snapshot, cutoff, candidates=candidates)
                if include_candidates:
                    details.append({'series': scope['series'], 'symbol': scope['symbol'],
                                    'trade_date': key[0], 'item_id': key[1], 'status': states[key],
                                    'selected': observation, 'candidates': candidates})
                if observation:
                    observations.append(observation)
                    selected[observation['seq']] = observation
            coverage.append(_coverage(scope, observations, states, warmup))
    return {'snapshot': snapshot, 'cutoff': cutoff,
            'observations': sorted(selected.values(), key=lambda row: (
                row['trade_date'], row['series'], row['symbol'], row['item_id'])),
            'coverage': coverage, **({'items': details} if include_candidates else {})}


def read_research_features(data_dir, snapshot_id, *, symbol, cutoff, db=None):
    """Resolve the latest visible observation period for each structured research feature."""
    with database(data_dir, db=db) as connection:
        ensure_schema(connection, _SCHEMA)
        snapshot = _snapshot(connection, snapshot_id)
        cutoff = min(utc_timestamp(cutoff), snapshot['as_of'])
        day = str(instant(cutoff).date())
        latest = {}
        for scope in _ranges(snapshot, 'research_feature', symbol, None, day):
            for (period, feature), observations in _observations(connection, snapshot, scope).items():
                observation, status = _choose(observations, snapshot, cutoff)
                if status != 'not_visible' and (feature not in latest or period >= latest[feature][0]):
                    latest[feature] = period, observation
    return {feature: observation for feature, (_, observation) in latest.items() if observation is not None}


def snapshot_rolling_selections(data_dir, snapshot_id, *, series='daily_bar', symbol, cutoffs, lookback):
    """Return selection changes within a rolling trading-session window at each cutoff."""
    if lookback < 1:
        raise ValueError('历史选择窗口至少包含一个交易日')
    if not cutoffs:
        return {}
    with database(data_dir) as db:
        ensure_schema(db, _SCHEMA)
        snapshot = _snapshot(db, snapshot_id)
        versions = {}
        for scope in _ranges(snapshot, series, symbol, min(cutoffs), max(cutoffs)):
            versions.update(_observations(db, snapshot, scope))
    days = sorted(cutoffs)
    result = {day: {} for day in days}
    positions = {day: index for index, day in enumerate(days)}
    timestamps = [min(utc_timestamp(cutoffs[day]), snapshot['as_of']) for day in days]
    cutoff_days = [str(instant(at).date()) for at in timestamps]
    for (day, item_id), rows in versions.items():
        if day not in positions:
            continue
        first = positions[day]
        end = min(first + lookback, len(days))
        changes = {first}
        for row in rows:
            availability = _visible_at(row, snapshot)
            if availability is not None and timestamps[first] < availability <= timestamps[end - 1]:
                changes.add(bisect_left(timestamps, availability, first, end))
        previous = None
        for index in sorted(changes):
            selection = (_choose(rows, snapshot, timestamps[index])
                         if day <= cutoff_days[index] else (None, 'not_visible'))
            if selection != previous:
                result[days[index]][day, item_id] = selection
                previous = selection
    return result


def snapshot_window_selections(data_dir, snapshot_id, *, series='daily_bar', symbol, cutoffs):
    """Resolve item versions and quality at a separate cutoff for each trading date."""
    selected = snapshot_rolling_selections(data_dir, snapshot_id, series=series, symbol=symbol,
                                           cutoffs=cutoffs, lookback=1)
    return {day: {item_id: value for (_, item_id), value in selected[day].items()} for day in cutoffs}


def snapshot_windows(data_dir, snapshot_id, *, series='daily_bar', symbol, cutoffs):
    """Resolve the default item at one time cutoff per trading date."""
    selected = snapshot_window_selections(data_dir, snapshot_id, series=series, symbol=symbol, cutoffs=cutoffs)
    return {day: items.get('', (None, 'missing'))[0] for day, items in selected.items()}


def available_dates(data_dir, *, series, symbol, start, end, as_of, use_mode=RECONSTRUCTED_RESEARCH):
    """Return dates already covered by a usable local observation."""
    as_of = utc_timestamp(as_of)
    with database(data_dir) as db:
        db.executescript(_SCHEMA)
        rules = ETF_SELECTION_RULES if series in ETF_SERIES else SELECTION_RULES_VERSION
        snapshot = {'as_of': as_of, 'max_seq': _waterline(db), 'use_mode': use_mode,
                    'source_priority': DEFAULT_SOURCE_PRIORITY, 'selection_rules_version': rules}
        scope = dict(series=series, symbol=symbol, start=start, end=end)
        return {key[0] for key, rows in _observations(db, snapshot, scope).items()
                if _choose(rows, snapshot, as_of)[0] is not None}
