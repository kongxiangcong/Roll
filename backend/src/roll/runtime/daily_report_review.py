"""Read-only holding review over two saved daily report versions."""

from decimal import Decimal

def metadata(report):
    return {key: report[key] for key in ('report_id', 'day', 'revision', 'known_by', 'input_sha256')}


def positions(inputs):
    return {row['instrument']: row for row in inputs['account']['positions']}


def amount(value):
    return Decimal(str(value)) if value is not None else None


def percent(value, total):
    return float(round(value * 100 / total, 4))


def account_review(report):
    inputs = report['inputs']
    account = inputs['account']
    funding = inputs.get('funding') or {}
    valuation = report.get('valuation') or {}
    marks = valuation.get('positions', [])
    assets = amount(valuation.get('cash_plus_holdings'))
    cash = amount(account.get('cash_balance'))
    values = {mark['instrument']: amount(mark.get('market_value')) for mark in marks}
    has_marks = (
        valuation.get('account_version') == account['version']
        and assets is not None and assets > 0 and cash is not None
        and positions(inputs).keys() == values.keys()
        and all(mark.get('quote_status') == 'SAME_DAY_INDICATIVE' for mark in marks)
        and not valuation.get('asynchronous_quotes') and not valuation.get('cash_estimated')
        and None not in values.values()
    )
    weights = {symbol: percent(value, assets) for symbol, value in values.items()} if has_marks else {}
    summary = {
        'version': account['version'],
        'confirmed_at': account.get('confirmed_at'),
        'valuation_id': valuation.get('valuation_id'),
        'cash_weight_pct': percent(cash, assets) if has_marks else None,
        'largest_weight_pct': max(weights.values(), default=0) if has_marks else None,
        'constraints_status': 'UNKNOWN',
        'constraints_reasons': ['缺少适用的冻结资金授权或估值事实。'],
        'constraints_checks': [],
        'funding_version': funding.get('version') or None,
        'valuation_as_of': valuation.get('as_of'),
    }
    if funding.get('scope_kind') != 'ACCOUNT' or funding.get('state') not in {'CONFIRMED', 'PAUSED'}:
        return summary, weights
    if funding['state'] == 'PAUSED':
        summary.update(constraints_status='PAUSED', constraints_reasons=['报告冻结的资金授权已暂停。'])
    elif has_marks and funding['scope_id'] == valuation.get('scope_id') and (
        valuation.get('input_authority') == 'CONFIRMED_ACCOUNT_AND_ARCHIVED_SOURCE'
    ):
        checks = [
            ('TOTAL_EXPOSURE', sum(values.values(), Decimal(0)) > amount(funding['total_exposure']),
             '总市值超过冻结授权的总暴露上限。', '总市值在冻结授权的总暴露上限内。'),
            ('SINGLE_EXPOSURE', any(value > amount(funding['single_exposure']) for value in values.values()),
             '至少一项持仓市值超过冻结授权的单证券上限。', '各持仓市值在冻结授权的单证券上限内。'),
            ('BOOK_CASH_RESERVE', cash < amount(funding['cash_reserve']),
             '账面现金低于冻结授权的现金保留额。', '账面现金达到冻结授权的现金保留额。'),
        ]
        summary['constraints_checks'] = [
            {'kind': kind, 'status': 'BREACHED' if breached else 'WITHIN_BOUNDARY'}
            for kind, breached, _, _ in checks
        ]
        summary['constraints_status'] = 'BREACHED' if any(check[1] for check in checks) else 'UNKNOWN'
        summary['constraints_reasons'] = [above if breached else within for _, breached, above, within in checks]
        summary['constraints_reasons'].append('持续损失与其他交易约束须另行核验。')
    return summary, weights


def change(kind, status, summary, *references):
    return {'kind': kind, 'status': status, 'summary': summary,
            'references': list(dict.fromkeys(ref for ref in references if ref))}


def position_change(current, previous, current_position, old_position):
    current_quantity = current_position.get('quantity', '0')
    if not previous:
        quantity = current_quantity if current_quantity is not None else '未知'
        return change('POSITION', 'NO_BASELINE', f'当前持仓数量 {quantity}，缺少比较基准。', current['report_id'])
    old_quantity = old_position.get('quantity', '0')
    refs = (previous['report_id'], current['report_id'])
    if not previous['inputs']['account']['version']:
        return change('POSITION', 'UNKNOWN', '基准报告没有已确认账户，无法比较持仓数量。', *refs)
    if current_quantity is None or old_quantity is None:
        return change('POSITION', 'UNKNOWN', '至少一份报告的持仓数量未知。', *refs)
    changed = amount(current_quantity) != amount(old_quantity)
    summary = f'确认数量 {old_quantity} → {current_quantity} 股。' if changed else f'确认数量未变，仍为 {current_quantity} 股。'
    return change('POSITION', 'CHANGED' if changed else 'UNCHANGED', summary, *refs)


def market_row(report, instrument):
    return next((row for row in report['inputs']['market_rows'] if row['instrument'] == instrument), {})


def last_bar(report, instrument):
    return market_row(report, instrument).get('last_complete_daily') or {}


def bar_summary(bar):
    return f"{bar['trade_date']} 收盘 {bar['close']} 元（获知于 {bar.get('available_at') or '未知'}）"


def bar_reference(bar):
    return bar.get('snapshot_id') or bar.get('raw_hash')


def price_change(current, previous, instrument):
    bar = last_bar(current, instrument)
    old = last_bar(previous, instrument) if previous else {}
    refs = (bar_reference(old), bar_reference(bar))
    if not bar or bar.get('close') is None:
        return change('DAILY', 'UNKNOWN', '所选报告缺少可用的已完成日线。', *refs)
    if not previous:
        return change('DAILY', 'NO_BASELINE', f'{bar_summary(bar)}，缺少比较基准。', *refs)
    if not old or old.get('close') is None:
        return change('DAILY', 'UNKNOWN', f'{bar_summary(bar)}，基准报告缺少可比日线。', *refs)
    numeric_fields = ('open', 'high', 'low', 'close', 'volume_shares', 'volume_reported', 'amount_yuan')
    changed = bar['trade_date'] != old['trade_date'] or any(
        amount(bar.get(key)) != amount(old.get(key)) for key in numeric_fields
    ) or bar.get('volume_unit') != old.get('volume_unit')
    summary = f'{bar_summary(old)} → {bar_summary(bar)}。' if changed else f'{bar_summary(bar)}，两份报告所存日线相同。'
    if changed and old['trade_date'] == bar['trade_date']:
        summary += '同一交易日的已保存日线字段有修订。'
    if bar['trade_date'] != current['day']:
        summary += '该收盘价早于所选报告日期。'
    return change('DAILY', 'CHANGED' if changed else 'UNCHANGED', summary, *refs)


def financial_change(current, previous, instrument):
    item = current['inputs']['financial'].get(instrument) or {}
    old = (previous['inputs']['financial'].get(instrument) or {}) if previous else {}
    refs = (old.get('observation_id'), item.get('observation_id'))
    period = item.get('latest_period')
    if not period:
        return [change('FINANCIAL', 'UNKNOWN', '所选报告缺少可用的财务观察。', *refs)]
    scope = f"最新保存报告期 {period}（财务来源截止 {item.get('known_by') or '未知'}）"
    if item.get('status') == 'STALE':
        scope += '，资料陈旧'
    if not previous:
        status, summary = 'NO_BASELINE', '缺少比较基准。'
    elif not old.get('latest_period'):
        status, summary = 'CHANGED', '相对基准首次出现已保存财务观察。'
    else:
        changed = any(item.get(key) != old.get(key) for key in ('periods', 'revision', 'source_versions'))
        status = 'CHANGED' if changed else 'UNCHANGED'
        summary = '已保存财务事实或版本有变化。' if changed else '已保存财务事实未见变化。'
    result = [change('FINANCIAL', status, f'{summary}{scope}。', *refs)]
    if status == 'CHANGED':
        old_texts = {fact['text'] for fact in old.get('analysis', []) if fact.get('kind') == 'FACT'}
        result.extend(
            change('FINANCIAL', status, fact['text'], *fact.get('source_fact_ids', []))
            for fact in item.get('analysis', [])
            if fact.get('kind') == 'FACT' and fact['text'] not in old_texts
        )
    if item.get('gaps') or old.get('gaps'):
        result.append(change('FINANCIAL', 'UNKNOWN', '至少一份报告的财务观察存在指标、原件或适用范围缺口。', *refs))
    return result


def news_changes(current, previous, instrument):
    item = current['inputs']['news'].get(instrument)
    if item is None:
        return [change('NEWS', 'UNKNOWN', '所选报告缺少新闻采集结果。')]
    old = previous['inputs']['news'].get(instrument) if previous else None
    old_ids = {fact['fact_id'] for fact in old['facts']} if old is not None else set()
    facts = [fact for fact in item['facts'] if fact['fact_id'] not in old_ids]
    status = 'CHANGED' if previous else 'NO_BASELINE'
    changes = []
    for fact in facts:
        relation = (fact.get('event') or {}).get('relation')
        prefix = '新增保存' if old is not None else '已保存（无可比基准）'
        title = fact.get('title') or '事件'
        summary = f"{prefix} · {title} · 获知于 {fact.get('available_at') or '未知'}"
        if relation:
            summary += f' · {relation}'
        changes.append(change('NEWS', status, summary, fact['fact_id'], fact.get('list_sha256'), fact.get('body_sha256')))
    if facts:
        changes.append(change('NEWS', 'UNKNOWN', '新闻来源为有限采集，完整覆盖未知。'))
    else:
        message = '两份报告之间未见新增已保存新闻。' if old is not None else '当前没有已保存新闻可供比较。'
        changes.append(change('NEWS', 'UNKNOWN' if previous else 'NO_BASELINE',
                              message + '新闻来源为有限采集，完整覆盖未知。'))
    return changes


def announcement_changes(current, previous, instrument):
    def announcements(report):
        return [fact for fact in market_row(report, instrument).get('company_facts', [])
                if fact.get('group') in {'ANNOUNCEMENTS', 'MAJOR_EVENTS', 'PERFORMANCE'} and not fact.get('errors')]

    def version(fact):
        identity = fact.get('event_identity') or fact.get('art_code')
        fields = ('group', 'title', 'disclosure_date', 'document_hash', 'document_url',
                  'content_excerpt', 'report_period', 'total_operating_income_yuan',
                  'net_profit_yuan', 'eps_yuan_per_share')
        return (identity, *(fact.get(field) for field in fields))

    seen = {version(fact) for fact in announcements(previous)} if previous else set()
    changes = []
    for fact in announcements(current):
        identity = version(fact)
        if identity not in seen:
            seen.add(identity)
            title = fact.get('title') or fact.get('art_code') or '已保存公司事实'
            disclosure = fact.get('disclosure_date') or '未知'
            available = fact.get('available_at') or '未知'
            summary = f'{title} · 披露日期 {disclosure} · 获知于 {available}'
            changes.append(change('ANNOUNCEMENT', 'CHANGED' if previous else 'NO_BASELINE',
                                  summary, fact.get('snapshot_id'), fact.get('raw_hash'), fact.get('document_hash')))
    coverage = '公告及公司事件完整覆盖未知。' if changes else '未见新增已保存公告或公司事件，完整覆盖未知。'
    changes.append(change('ANNOUNCEMENT', 'UNKNOWN' if previous else 'NO_BASELINE', coverage))
    return changes


def judgments_for(report, instrument):
    notes = {note['note_id']: note for note in report['inputs']['notes']}
    result = []
    for condition in report['conditions']:
        if condition['instrument'] != instrument:
            continue
        note = notes[condition['note_id']]
        bar = condition.get('price_basis') or {}
        due_date = note.get('due_date')
        threshold = note.get('threshold')
        close = amount(bar.get('close'))
        price_state = None
        if threshold is not None:
            if close is None or bar.get('trade_date') != report['day']:
                price_state = 'UNKNOWN'
            else:
                threshold_amount = amount(threshold)
                crossed = close >= threshold_amount if note['comparator'] == 'ABOVE' else close <= threshold_amount
                price_state = 'TRIGGERED' if crossed else 'NOT_TRIGGERED'
        result.append({
            'note_id': note['note_id'], 'thesis': note['thesis'], 'invalidation': note['invalidation'],
            'comparator': note.get('comparator'), 'threshold': threshold,
            'due_date': due_date, 'price_only': note.get('price_only', False),
            'state': condition['state'], 'price_state': price_state,
            'due_triggered': bool(due_date and due_date <= report['day']),
            'price_basis': {key: bar.get(key) for key in ('close', 'trade_date', 'available_at', 'snapshot_id', 'raw_hash')} if bar else None,
        })
    return result


def holding_review(current, previous, instrument, weight, position_delta, account_triggered):
    changes = [position_delta, price_change(current, previous, instrument)]
    changes.extend(financial_change(current, previous, instrument))
    changes.extend(news_changes(current, previous, instrument))
    changes.extend(announcement_changes(current, previous, instrument))
    judgments = judgments_for(current, instrument)
    triggered = []
    if account_triggered:
        triggered.append('报告的账户摘要显示至少一项已冻结约束触发，请核对本持仓。')
    if any(item['price_state'] == 'TRIGGERED' for item in judgments):
        triggered.append('保存的收盘价触发了至少一条推翻条件。')
    if any(item['due_triggered'] for item in judgments):
        triggered.append('至少一条判断已到预定复查日期。')
    scoped_to_price = bool(judgments) and all(item['price_only'] for item in judgments)
    changed = [item['summary'] for item in changes if item['status'] == 'CHANGED'
               and (item['kind'] != 'DAILY' or not scoped_to_price)]
    gaps = []
    if not previous:
        gaps.append('缺少比较基准。')
    if not judgments:
        gaps.append('缺少原持仓理由，请补记。')
    elif not scoped_to_price:
        gaps.append('自由文本推翻条件需要人工核对。')
    if any(item['price_state'] == 'UNKNOWN' for item in judgments):
        gaps.append('至少一条价格条件缺少有效日线。')
    if any(item['kind'] in {'POSITION', 'DAILY'} and item['status'] == 'UNKNOWN' for item in changes):
        gaps.append('持仓或日线缺少可比事实。')
    if triggered or changed:
        status = 'REVIEW_REQUIRED'
        impact = '已发现复查触发项。请结合保存的原判断核对影响。'
        reasons = triggered + changed + gaps
    elif gaps or any(item['state'] != 'NOT_TRIGGERED' for item in judgments):
        status = 'INSUFFICIENT'
        impact = '依据不足，原持仓理由的影响待判断。'
        reasons = gaps or ['尚有条件需要人工确认。']
    else:
        status = 'NO_NEW_REVIEW'
        impact = '在用户明确限定的价格检查范围内，已保存的本日收盘价未触发推翻条件。'
        reasons = ['可比较的持仓数量未变，价格条件已核对且均未触发，复查日期未到。',
                   '已保存的财务与新闻证据未提供新的复查触发项，各来源覆盖见变化明细。']
    return {'instrument': instrument, 'weight_pct': weight, 'status': status, 'reasons': reasons,
            'impact': impact, 'changes': changes, 'judgments': judgments}


def build_review(report, previous):
    account, weights = account_review(report)
    current_positions = positions(report['inputs'])
    previous_positions = positions(previous['inputs']) if previous else {}
    confirmed = bool(report['inputs']['account']['version'] and previous and previous['inputs']['account']['version'])
    exited = [
        {'instrument': instrument, 'change': position_change(report, previous, {}, position)}
        for instrument, position in previous_positions.items()
        if confirmed and instrument not in current_positions and amount(position.get('quantity')) not in (None, Decimal(0))
    ]
    return {
        **metadata(report), 'comparison': metadata(previous) if previous else None, 'account': account,
        'holdings': [holding_review(report, previous, instrument, weights.get(instrument),
                                    position_change(report, previous, position,
                                                    previous_positions.get(instrument, {})),
                                    account['constraints_status'] in {'BREACHED', 'PAUSED'})
                     for instrument, position in current_positions.items()],
        'exited_holdings': exited,
        'authority': 'OBSERVATION_ONLY',
    }
