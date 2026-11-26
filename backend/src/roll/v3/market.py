"""Append-only market observations and offline DataSnapshot selection."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json

from roll.market.calendar import is_session
from roll.v3.storage import SHANGHAI, database, instant


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
        for item in observations:
            key = (item['series'], item['symbol'].upper(), str(date.fromisoformat(item['trade_date'])),
                   item.get('item_id', ''), item['source'])
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
                'payload': _encode(item.get('payload', {})),
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


def freeze_snapshot(data_dir, *, as_of, use_mode, scope, source_priority=DEFAULT_SOURCE_PRIORITY):
    """Freeze an observation waterline, input scope, purpose and version-selection policy."""
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
    with database(data_dir) as db:
        db.executescript(_SCHEMA)
        db.execute('BEGIN IMMEDIATE')
        snapshot = {
            'as_of': utc_timestamp(as_of), 'max_seq': _waterline(db), 'use_mode': use_mode,
            'scope': normalized, 'selection_rules_version': SELECTION_RULES_VERSION,
            'source_priority': list(dict.fromkeys(source_priority)),
        }
        snapshot_id = sha256(_encode(snapshot).encode()).hexdigest()
        db.execute("""
            INSERT OR IGNORE INTO data_snapshot(snapshot_id,as_of,max_seq,use_mode,scope,
                                               selection_rules_version,source_priority)
            VALUES(?,?,?,?,?,?,?)
        """, (snapshot_id, snapshot['as_of'], snapshot['max_seq'], use_mode, _encode(normalized),
              SELECTION_RULES_VERSION, _encode(snapshot['source_priority'])))
        db.commit()
    return {'snapshot_id': snapshot_id, **snapshot}


def get_snapshot(data_dir, snapshot_id):
    with database(data_dir) as db:
        db.executescript(_SCHEMA)
        return _snapshot(db, snapshot_id)


def _snapshot(db, snapshot_id):
    row = db.execute('SELECT * FROM data_snapshot WHERE snapshot_id=?', (snapshot_id,)).fetchone()
    if row is None:
        raise ValueError(f'数据快照不存在 {snapshot_id}')
    result = dict(row)
    result['scope'] = json.loads(result['scope'])
    result['source_priority'] = json.loads(result['source_priority'])
    if result['selection_rules_version'] != SELECTION_RULES_VERSION:
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
        groups[row['trade_date'], row['item_id']].append(row)
    return groups


def _visible_at(row, snapshot):
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


def _choose(rows, snapshot, cutoff):
    if not rows:
        return None, 'missing'
    current = {}
    for row in rows:
        visible_at = _visible_at(row, snapshot)
        if visible_at is None or visible_at > cutoff:
            continue
        source = row['source']
        if source not in current or (visible_at, row['seq']) > (
            current[source][0], current[source][1]['seq']
        ):
            current[source] = (visible_at, row)
    if not current:
        return None, 'not_visible'

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

    result = dict(chosen)
    result['payload'] = json.loads(result['payload'])
    result['unit'] = json.loads(result['unit'])
    result['withdrawn'] = bool(result['withdrawn'])
    result['reconstruction_only'] = bool(result['reconstruction_only'])
    result['selected_available_at'] = current[chosen['source']][0]
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
                  cutoff=None, warmup=0):
    """Inspect a frozen observation range and its coverage at a decision cutoff."""
    with database(data_dir) as db:
        db.executescript(_SCHEMA)
        snapshot = _snapshot(db, snapshot_id)
        cutoff = min(utc_timestamp(cutoff), snapshot['as_of']) if cutoff else snapshot['as_of']
        cutoff_day = str(datetime.fromisoformat(cutoff).astimezone(SHANGHAI).date())
        selected = {}
        coverage = []
        for scope in _ranges(snapshot, series, symbol, start, end):
            observations = []
            states = {}
            for key, rows in _observations(db, snapshot, scope).items():
                if key[0] > cutoff_day:
                    states[key] = 'not_visible'
                    continue
                observation, states[key] = _choose(rows, snapshot, cutoff)
                if observation:
                    observations.append(observation)
                    selected[observation['seq']] = observation
            coverage.append(_coverage(scope, observations, states, warmup))
    return {'snapshot': snapshot, 'cutoff': cutoff,
            'observations': sorted(selected.values(), key=lambda row: (
                row['trade_date'], row['series'], row['symbol'], row['item_id'])),
            'coverage': coverage}


def snapshot_windows(data_dir, snapshot_id, *, series='daily_bar', symbol, cutoffs):
    """Resolve one time cutoff per trading date without querying each session."""
    if not cutoffs:
        return {}
    with database(data_dir) as db:
        db.executescript(_SCHEMA)
        snapshot = _snapshot(db, snapshot_id)
        versions = {}
        for scope in _ranges(snapshot, series, symbol, min(cutoffs), max(cutoffs)):
            versions.update(_observations(db, snapshot, scope))
    result = {}
    for day, cutoff in cutoffs.items():
        cutoff = min(utc_timestamp(cutoff), snapshot['as_of'])
        cutoff_day = str(datetime.fromisoformat(cutoff).astimezone(SHANGHAI).date())
        rows = versions.get((day, ''), ()) if day <= cutoff_day else ()
        result[day] = _choose(rows, snapshot, cutoff)[0]
    return result


def available_dates(data_dir, *, series, symbol, start, end, as_of):
    """Return dates already covered by a usable local observation."""
    as_of = utc_timestamp(as_of)
    with database(data_dir) as db:
        db.executescript(_SCHEMA)
        snapshot = {'as_of': as_of, 'max_seq': _waterline(db),
                    'use_mode': RECONSTRUCTED_RESEARCH, 'source_priority': DEFAULT_SOURCE_PRIORITY}
        scope = dict(series=series, symbol=symbol, start=start, end=end)
        return {key[0] for key, rows in _observations(db, snapshot, scope).items()
                if _choose(rows, snapshot, as_of)[0] is not None}
