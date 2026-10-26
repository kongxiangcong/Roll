"""Literal values and known scale; never infer money scale from currency alone."""
from .report_template import cell


def unit_label(fact, materials=()):
    unit,currency=fact.get('unit'),fact.get('currency')
    material=next((m for m in materials if m['material_id']==fact.get('material_id')),{})
    limitations=' '.join(material.get('limitations',[]))
    if unit=='unit' and currency=='CNY' and 'unit=unit means whole CNY with unchanged numeric scale' in limitations:
        unit='元'
    elif unit in {'元','CNY'} and currency=='CNY':unit='元'
    elif unit in {'CNY_MILLION','million CNY'} and currency=='CNY':unit='百万元'
    elif unit in {'million','100_million'} and currency in {'CNY','HKD','USD'}:
        unit=('百万' if unit=='million' else '亿')+{'CNY':'元','HKD':'港元','USD':'美元'}[currency]
    elif unit=='share':return '股'
    elif unit in {'million shares','million_shares'}:return '百万股'
    elif unit=='100_million_shares':return '亿股'
    elif unit=='ratio':return '比值（原始小数，不统一换算百分比）'
    elif not unit or unit=='unit':unit='单位/尺度未知'
    return str(unit)+(('（'+str(currency)+'）') if currency else '（币种不适用或未知）')


def literal(fact,materials=()):
    return cell(fact['value'])+' '+cell(unit_label(fact,materials))


def company_attributes(payload):
    """Positive issuer financial attributes only; macro/model/price inputs are excluded."""
    allowed={'revenue','operating_profit','net_profit','net_profit_parent','net_income_parent','cash_flow_operating','cfo',
             'total_assets','total_equity','equity_parent','cash','gross_margin','employees','sales_volume','production_volume'}
    import re
    by_material={m['material_id']:m for m in payload['materials']}
    eligible={}
    for fact in payload['facts']:
        metric=re.sub(r'_20\d\d$','',fact['metric']).lower()
        material=by_material.get(fact['material_id'],{})
        if (fact['kind']=='DISCLOSED' and fact['value_type']=='NUMBER' and metric in allowed
            and material.get('media_type')=='application/pdf' and (fact.get('page') or fact.get('table'))
            and not fact['business'].startswith(('MACRO','PEER:'))):
            eligible.setdefault(metric,[]).append(fact)
    chosen=[]
    for metric,rows in sorted(eligible.items()):
        latest=max(f['period_end'] for f in rows);rows=[f for f in rows if f['period_end']==latest]
        if len({(f['value'],f['unit'],f['currency'],f['scope']) for f in rows})==1:chosen.append(rows[0])
    return chosen[:6]


def typed_packet(packet):
    """Build host-owned readable tables from fixed typed values; no arithmetic or latest reads."""
    import copy
    from .report_template import table
    value=copy.deepcopy(packet)
    # Derive display labels from the fixed typed basis plus its original unit evidence.
    binding=value['payload']['valuation_binding'];model=binding.get('fixed_operating_model')
    if model and binding['review']['applicability']!='NOT_APPLICABLE':
        materials=value['payload']['materials'];facts=value['payload']['facts'];config=model['config'];meta=config['metadata']
        # Resolve source-scale evidence only through the fixed model's corresponding monetary roles.
        # Unrelated source facts (e.g. historical market cap) cannot rename forecast outputs.
        monetary_provenance=[('config/'+path,p) for path,p in model['provenance'].items() if p.get('currency')==meta['currency']]
        monetary_provenance += [('drivers/'+path,p) for path,p in model['drivers'].get('provenance',{}).items() if p.get('currency')==meta['currency']]
        support=set()
        for path,p in monetary_provenance:
            support.update(p.get('references',[]))
            support.update(model['economic_basis'].get('assumption_basis',{}).get(path,{}).get('support_fact_version_ids',[]))
        monetary=[f for f in facts if f['version_id'] in support and f.get('currency')==meta['currency'] and f['value_type']=='NUMBER']
        money_labels={unit_label(f,materials) for f in monetary}
        whole=(money_labels=={'元（CNY）'} and meta['currency']=='CNY' and meta['amount_unit']=='unit'
            and bool(monetary_provenance) and all(p.get('unit')=='unit' for _,p in monetary_provenance))
        money='元（CNY）' if whole else unit_label(dict(unit=meta['amount_unit'],currency=meta['currency']))
        shares=unit_label(dict(unit=meta['shares_unit'],currency=None))
        per_share=money+' / '+shares
        sub=value['payload']['valuation_subsections']
        sub['2']='固定正常化调整；比率为小数口径；金额单位与来源见逐项依据。\n'+table(
            ['调整项','目标','调整前','调整后','差额','单位/币种/范围','依据'],[[r['adjustment_id'],r['target'],r['before'],r['after'],r['delta'],
            unit_label(r.get('provenance',{}).get('before',{}))+' / '+str(r.get('provenance',{}).get('before',{}).get('scope')),r['reason']] for r in model['normalization_schedule']])
        sub['3']='固定年度研究假设；各金额列单位：'+money+'。范围沿用固定模型；未重算现金流。\n'+table(
            ['情景','期间','收入','经营利润','税','税后经营利润','折旧','维持投资','增长投资','营运资金变化','企业自由现金流'],
            [[s['name'],y['period'],y['revenue'],y['operating_profit'],y['tax'],y['nopat'],y['normalized_inputs']['depreciation'],y['normalized_inputs']['maintenance_capex'],y['normalized_inputs']['growth_capex'],y['normalized_inputs']['delta_working_capital'],y['fcff']] for s in model['cashflows'] for y in s['years']])
        wacc=model['economic_basis']['wacc']
        sub['4']='固定折现率与权益桥。利率与权重以小数表示；beta为无量纲系数。\n'+table(['项目','固定值','单位/口径'],[
            *[[k,wacc.get(k),'系数' if k=='beta' else '原始小数比率'] for k in ['risk_free','beta','equity_risk_premium','cost_of_debt','tax_rate','equity_weight','debt_weight']],
            ['WACC',config['wacc'],'原始小数比率'],['g',config['terminal_g'],'原始小数比率'],['稀释股数',config['shares'],shares]])+'\n\n'+table(['桥接项','金额（'+money+'）','处理','说明'],[[i['name'],i['amount'],i['treatment'],i.get('reason','固定原件/假设引用见附录J')] for i in config['equity_bridge']])
        def summary(presentation):
            result='用途 '+presentation.get('purpose','CURRENT_PRICING')+' / '+presentation['status']+'；'+('有条件可用' if presentation.get('usable_range') else '不可用')
            if presentation.get('usable_range'):
                result+='\n'+table(['情景','企业价值（'+money+'）','归母权益价值（'+money+'）','每股条件值（'+per_share+'）','终值占比（原始小数）'],[[s['name'],s['enterprise_value'],s['equity_value'],s['per_share'],s['terminal_share_of_ev']] for s in presentation['scenarios']])
            else:result+='；'+str(presentation.get('reason') or presentation.get('current_pricing_gaps') or presentation.get('limitations'))
            return result
        sub['5']='当前定价用途：\n'+summary(value['payload']['valuation_presentation'])+'\n\n历史基准条件研究（非历史PIT）：\n'+summary(binding['baseline'])
    return value
