"""Conservative source coverage and static charts from identical-scope facts only."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import html
import re
from .report_archive import archive


def prepare_data(evidence,facts,materials):
    by_material={m['material_id']:m for m in materials}
    groups=defaultdict(list)
    for fact in facts:
        if fact['value_type']!='NUMBER' or fact['kind']=='ASSUMED':
            continue
        try:
            value=Decimal(fact['value'])
            if not value.is_finite():continue
        except (InvalidOperation,TypeError):
            continue
        # Never join point-in-time values with duration measures or different scopes.
        metric=re.sub(r'_20\d\d$','',fact['metric'])
        duration='POINT' if fact['period_start']==fact['period_end'] else fact['period_start'][5:]+'/'+fact['period_end'][5:]
        key=(metric,fact['business'],fact['unit'],fact['currency'],fact['scope'],duration)
        groups[key].append((fact,value))
    charts=[]
    for key,rows in groups.items():
        by_period=defaultdict(list)
        for fact,value in rows:by_period[fact['period_end']].append((fact,value))
        # Conflicting heads and repeated periods cannot manufacture a sequence.
        if len(by_period)<3 or any(len({v for _,v in values})!=1 for values in by_period.values()):continue
        selected=[by_period[p][0] for p in sorted(by_period)]
        if len(selected)>20:continue
        values=[v for _,v in selected];minimum=min(values);maximum=max(values);spread=maximum-minimum or Decimal(1)
        points=' '.join(str(50+int(480*i/(len(values)-1)))+','+str(210-int((v-minimum)/spread*160)) for i,v in enumerate(values))
        metric=key[0]
        section='4' if metric.startswith('industry_') else '8' if metric.startswith(('stock_price','eps','pe_')) else '3' if metric in {'revenue','sales_volume'} else '6'
        from .report_values import unit_label
        label=unit_label(selected[0][0],materials)
        title=metric+' / '+label+' / '+str(key[4])
        svg=('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300" viewBox="0 0 600 300">'
             '<rect width="600" height="300" fill="white"/><text x="20" y="24" font-size="13">'+html.escape(title)+'</text>'
             '<path d="M50 40V210H550" stroke="#999" fill="none"/><polyline points="'+points+'" stroke="#2468a0" stroke-width="2" fill="none"/>'+
             ''.join('<text x="'+str(50+int(480*i/(len(values)-1)))+'" y="236" font-size="10">'+f['period_end'][:4]+'</text>' for i,(f,_) in enumerate(selected))+
             '<text x="20" y="262" font-size="10">min '+str(minimum)+'; max '+str(maximum)+' / '+html.escape(label)+'</text></svg>')
        chart_archive=archive(evidence,svg.encode(),'REPORT_SOURCE_DATA_CHART',extension='svg')
        charts.append(dict(chart_id=chart_archive['sha256'],section_id=section,title=title,archive=chart_archive,
            fact_version_ids=[f['version_id'] for f,_ in selected],unit=key[2],currency=key[3],scope=key[4],
            data=[dict(period=f['period_end'],value=str(v),fact_version_id=f['version_id'],material_id=f['material_id'],
                raw_sha256=by_material[f['material_id']]['raw_sha256'],page=f['page'],table=f['table']) for f,v in selected],
            limitation='同口径原值时序；未做因果解释、预测或独立事实审计'))
    industry={metric:{f['period_end'][:4] for f in facts if f['metric']==metric and f['kind']=='DISCLOSED'}
              for metric in ['industry_production','industry_consumption','industry_imports','industry_exports','industry_inventory','industry_price']}
    peers=defaultdict(list)
    for fact in facts:
        if fact['business'].startswith('PEER:'):peers[fact['business']].append(fact)
    qualified=[rows for rows in peers.values() if {'revenue','gross_margin','listing_market'}<={f['metric'] for f in rows}
        and all(f['kind']=='DISCLOSED' and (f['page'] or f['table']) for f in rows)]
    intl=sum(any(f['metric']=='listing_market' and f['value'] in {'NYSE','NASDAQ','LSE','TSE','HKEX'} for f in rows) for rows in qualified)
    return dict(charts=charts,coverage=dict(industry_years={k:len(v) for k,v in industry.items()},
        industry_complete=all(len(v)>=5 for v in industry.values()),peer_count=len(qualified),international_peer_count=intl,
        peer_complete=len(qualified)>=5 and intl>=2,chart_count=len(charts),chart_sections=sorted({c['section_id'] for c in charts})))
