"""Conservative source coverage and static charts from identical-scope facts only."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import html
import re
from .report_archive import archive


INDUSTRY_METRICS=('industry_production','industry_consumption','industry_imports','industry_exports','industry_inventory','industry_price')


def number(fact):
    if fact['value_type']!='NUMBER' or fact['value'] is None:return None
    try:
        value=Decimal(fact['value'])
        return value if value.is_finite() else None
    except (InvalidOperation,TypeError,ValueError):return None


def numeric_basis(fact,materials=()):
    from .report_values import unit_label
    def known(value):
        text=str(value or '').strip().casefold()
        return bool(text) and not re.search(r'unknown|unavailable|未披露|未知|不详|待核|不适用',text) and text not in {'none','null','n/a','na','not_available'}
    if not known(fact.get('scope')) or not known(fact.get('unit')):return False
    if fact.get('unit') in {'ratio','%','percent','bp'} and fact.get('currency') is not None:return False
    prefix=re.match(r'^(CNY|HKD|USD|EUR|GBP)[_/]',str(fact.get('unit')))
    if prefix and prefix[1]!=fact.get('currency'):return False
    return number(fact) is not None and '未知' not in unit_label(fact,materials)


def consecutive_years(years):
    longest=current=0;previous=None
    for year in sorted(set(years)):
        current=current+1 if previous is not None and year==previous+1 else 1
        longest=max(longest,current);previous=year
    return longest


def qualified_peer(peer):
    """Numerical financial context, not independent valuation approval."""
    facts=peer['facts'];materials=peer['materials']
    revenue=[f for f in facts if re.sub(r'_20\d\d$','',f['metric'])=='revenue' and f['kind']=='DISCLOSED' and numeric_basis(f,materials) and f.get('currency') and f['unit'] in {'unit','million','100_million','CNY_MILLION','HKD_MILLION','USD_MILLION','EUR_MILLION','GBP_MILLION','元','万元','百万元','亿元','CNY','HKD','USD','港元','美元'} and (f.get('page') or f.get('table'))]
    margin=[f for f in facts if re.sub(r'_20\d\d$','',f['metric'])=='gross_margin' and f['kind']=='DISCLOSED' and numeric_basis(f,materials) and f['unit'] in {'ratio','%','percent'} and (f.get('page') or f.get('table'))]
    return any(all(a[key]==b[key] for key in ['business','scope','period_start','period_end']) for a in revenue for b in margin)


def prepare_data(evidence,facts,materials):
    by_material={m['material_id']:m for m in materials}
    groups=defaultdict(list)
    for fact in facts:
        if fact['kind']=='ASSUMED' or not numeric_basis(fact,materials):continue
        value=number(fact)
        # Never join point-in-time values with duration measures or different scopes.
        metric=re.sub(r'_20\d\d$','',fact['metric'])
        duration='POINT' if fact['period_start']==fact['period_end'] else fact['period_start'][5:]+'/'+fact['period_end'][5:]
        key=(metric,fact['business'],fact['unit'],fact['currency'],fact['scope'],duration)
        groups[key].append((fact,value))
    charts=[];industry={metric:0 for metric in INDUSTRY_METRICS};industry_basis={metric:[] for metric in INDUSTRY_METRICS}
    for key,rows in groups.items():
        by_period=defaultdict(list)
        for fact,value in rows:by_period[fact['period_end']].append((fact,value))
        # Conflicting heads and repeated periods cannot manufacture a sequence.
        if any(len({v for _,v in values})!=1 for values in by_period.values()):continue
        selected=[by_period[p][0] for p in sorted(by_period)]
        if key[0] in industry:
            comparable=defaultdict(set)
            for fact,_ in selected:
                if fact['kind']!='DISCLOSED':continue
                period_type=fact['period_end'][5:7] if fact['period_start']==fact['period_end'] else key[-1]
                comparable[period_type].add(int(fact['period_end'][:4]))
            count=max((consecutive_years(years) for years in comparable.values()),default=0)
            industry[key[0]]=max(industry[key[0]],count)
            industry_basis[key[0]].append(dict(business=key[1],unit=key[2],currency=key[3],scope=key[4],period_type=key[5],consecutive_years=count,fact_version_ids=[f['version_id'] for f,_ in selected if f['kind']=='DISCLOSED']))
        if len(selected)<3 or len(selected)>20:continue
        values=[v for _,v in selected];minimum=min(values);maximum=max(values);spread=maximum-minimum or Decimal(1)
        points=' '.join(str(50+int(480*i/(len(values)-1)))+','+str(210-int((v-minimum)/spread*160)) for i,v in enumerate(values))
        metric=key[0]
        section='4' if metric.startswith('industry_') else '8' if (metric in {'pe','price_to_earnings'} or metric.startswith(('stock_price','eps','pe_'))) else '3' if metric in {'revenue','sales_volume'} else '6'
        from .report_values import unit_label
        label=unit_label(selected[0][0],materials)
        title=metric+' / '+label+' / '+str(key[4])
        svg=('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300" viewBox="0 0 600 300">'
             '<rect width="600" height="300" fill="white"/><text x="20" y="24" font-size="13">'+html.escape(title)+'</text>'
             '<path d="M50 40V210H550" stroke="#999" fill="none"/><polyline points="'+points+'" stroke="#2468a0" stroke-width="2" fill="none"/>'+
             ''.join('<text x="'+str(50+int(480*i/(len(values)-1)))+'" y="236" font-size="10">'+f['period_end'][:4]+'</text>' for i,(f,_) in enumerate(selected))+
             '<text x="20" y="262" font-size="10">min '+str(minimum)+'; max '+str(maximum)+' / '+html.escape(label)+'</text></svg>')
        chart_archive=archive(evidence,svg.encode(),'REPORT_SOURCE_DATA_CHART',extension='svg')
        charts.append(dict(metric=metric,chart_id=chart_archive['sha256'],section_id=section,title=title,archive=chart_archive,
            fact_version_ids=[f['version_id'] for f,_ in selected],unit=key[2],currency=key[3],scope=key[4],
            data=[dict(period=f['period_end'],value=str(v),fact_version_id=f['version_id'],material_id=f['material_id'],
                raw_sha256=by_material[f['material_id']]['raw_sha256'],page=f['page'],table=f['table']) for f,v in selected],
            limitation='同口径原值时序；未做因果解释、预测或独立事实审计'))
    return dict(charts=charts,coverage=dict(industry_years=industry,industry_basis=industry_basis,
        industry_complete=all(count>=5 for count in industry.values()),peer_count=0,international_peer_count=0,
        peer_complete=False,chart_count=len(charts),chart_sections=sorted({c['section_id'] for c in charts})))
