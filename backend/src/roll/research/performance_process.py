"""Offline QuantStats rendering from host-supplied saved observations only."""
from decimal import Decimal
import hashlib
import html
from importlib.metadata import version
import io
import json
import math
from pathlib import Path
import socket
import sys

VERSION='0.0.86'


def saved_interval(points,expected,pd,qs):
    dates=[p['date'] for p in points]
    missing=sorted(set(expected)-set(dates));unexpected=sorted(set(dates)-set(expected))
    unknown=[p['date'] for p in points if p.get('nav_yuan') is None]
    result={'status':'INCOMPLETE_FIXED_WINDOW','original_points':points,'window':[dates[0],dates[-1]] if dates else None,
        'annualized_return':None,'returns':[],'monthly_returns':[],
        'coverage':{'original_points':len(points),'missing_sessions':missing,'unknown_nav_dates':unknown,'unexpected_sessions':unexpected}}
    if dates!=sorted(set(dates)) or dates!=expected or missing or unexpected or unknown:return result,None
    values=[Decimal(p['nav_yuan']) for p in points]
    if len(values)<2 or any(not v.is_finite() or v<=0 for v in values):
        result['status']='INSUFFICIENT_POSITIVE_NAV_SUPPORT';return result,None
    returns=[None]+[values[i]/values[i-1]-1 for i in range(1,len(values))]
    numeric=[float(v) for v in returns[1:]];equity=[float(v/values[0]*100) for v in values]
    if not all(math.isfinite(v) for v in numeric+equity):raise ValueError('QUANTSTATS_FLOAT_RANGE_UNSUPPORTED')
    series=pd.Series(numeric,index=pd.to_datetime(dates[1:]),dtype=float)
    normalized=pd.Series(equity,index=pd.to_datetime(dates),dtype=float)
    compounded=qs.stats.compsum(series);drawdown=qs.stats.to_drawdown_series(normalized)
    monthly=qs.stats.monthly_returns(series,eoy=False,compounded=True,prepare_returns=False)
    # Ignore QuantStats zero placeholders for unobserved months.
    monthly_rows=[]
    for month in sorted(set(series.index.strftime('%Y-%m'))):
        stamp=pd.Timestamp(month+'-01');observed=series[series.index.strftime('%Y-%m')==month]
        monthly_rows.append({'month':month,'value':float(monthly.loc[str(stamp.year),stamp.strftime('%b').upper()]),
            'coverage':'OBSERVED_CLOSE_INTERVAL_ONLY','first_return_date':observed.index[0].date().isoformat(),
            'last_return_date':observed.index[-1].date().isoformat()})
    result.update(status='DESCRIPTIVE_SAVED_CLOSE_INTERVAL',returns=[{'date':d,'value':None if r is None else str(r)} for d,r in zip(dates,returns)],
        total_return=float(qs.stats.comp(series)),maximum_drawdown=float(qs.stats.max_drawdown(normalized)),
        drawdown=[{'date':d,'value':float(v)} for d,v in zip(dates,drawdown)],monthly_returns=monthly_rows,
        annualized_return=(1+float(qs.stats.comp(series)))**(252/len(series))-1 if len(series)>=252 else None)
    return result,{'dates':pd.to_datetime(dates),'cumulative':[0]+[float(v) for v in compounded],
        'drawdown':[float(v) for v in drawdown],'monthly':[r['value'] for r in monthly_rows],'months':[r['month'] for r in monthly_rows]}


def render(command):
    def denied(*args,**kwargs):raise RuntimeError('PERFORMANCE_NETWORK_DISABLED')
    socket.socket.connect=denied
    socket.create_connection=denied
    socket.getaddrinfo=denied
    import requests
    requests.sessions.Session.request=denied
    import curl_cffi.requests
    curl_cffi.requests.Session.request=denied
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    import pandas as pd
    import quantstats as qs
    qs.utils.download_returns=denied
    if version('quantstats')!=VERSION:raise ValueError('QUANTSTATS_PIN_MISMATCH')
    library={'name':'QuantStats','version':VERSION,'license':'Apache-2.0',
        'source_sha256':{n:hashlib.sha256((Path(qs.__file__).parent/n).read_bytes()).hexdigest() for n in ('stats.py','utils.py')}}
    result={'library':library,'namespaces':{},'network_calls':0,'system_usable':False,'capability':'NOT_GRANTED',
        'method':{'periods_per_year':252,'risk_free_rate':'0','annualization':'SUPPRESSED_BELOW_252_OBSERVED_RETURNS',
            'preprocessing':'No date matching/dropna/forward-fill. First saved close is the interval anchor, not an earned return.',
            'initial_funding_return':'UNKNOWN_NOT_INCLUDED','monthly_values':'Only months containing observed returns; partial boundary months labelled.'},'figures':{}}
    for namespace,curve in command['curves'].items():
        points=curve['points']
        base={'status':'NOT_A_CONTINUOUS_RETURN_SERIES','original_points':points,'window':None,
            'benchmark_status':'NO_SAVED_MATCHED_BASELINE_SERIES','annualized_return':None,
            'returns':[],'monthly_returns':[],'coverage':{'original_points':len(points),'missing_sessions':[],'unknown_nav_dates':[]}}
        result['namespaces'][namespace]=base
        if namespace!='SHADOW' or not curve['continuous_performance']:continue
        interval,plot=saved_interval(points,command['sessions'],pd,qs);base.update(interval)
        base['benchmarks']={};plots={namespace:plot} if plot else {}
        for label,baseline_points in command.get('benchmarks',{}).items():
            baseline,baseline_plot=saved_interval(baseline_points,command['sessions'],pd,qs)
            baseline['comparison_scope']='SAVED_SHADOW_CLOSE_INTERVAL_ONLY; NOT_RISK_MATCHED_QUALIFICATION'
            if plot and baseline_plot:
                baseline['interval_return_difference']=base['total_return']-baseline['total_return'];plots[label]=baseline_plot
            base['benchmarks'][label]=baseline
        if base['benchmarks']:
            base['benchmark_status']='SAVED_MATCHED_CLOSE_INTERVALS' if plot and all(b['status']=='DESCRIPTIVE_SAVED_CLOSE_INTERVAL' for b in base['benchmarks'].values()) else 'SAVED_BASELINE_WINDOW_MISMATCH'
        if not plot:continue
        figure,axes=plt.subplots(3,1,figsize=(9,8),layout='constrained')
        for label,series_plot in plots.items():
            axes[0].plot(series_plot['dates'],series_plot['cumulative'],label=label)
            axes[1].plot(series_plot['dates'],series_plot['drawdown'],label=label)
        axes[1].fill_between(plot['dates'],plot['drawdown'],0,color='#964b4b',alpha=.2)
        axes[0].set_title(namespace+' cumulative return (first saved close anchor)');axes[0].legend()
        axes[1].set_title('Drawdown from saved close peak');axes[1].legend()
        width=.8/len(plots)
        for i,(label,series_plot) in enumerate(plots.items()):axes[2].bar([m-.4+width/2+i*width for m in range(len(plot['months']))],series_plot['monthly'],width=width,label=label)
        axes[2].set_xticks(range(len(plot['months'])),plot['months']);axes[2].legend()
        axes[2].set_title('Observed monthly intervals; boundary months are partial')
        for axis in axes:axis.yaxis.set_major_formatter(PercentFormatter(xmax=1,decimals=1))
        stream=io.StringIO();figure.savefig(stream,format='svg',metadata={'Date':None});plt.close(figure)
        result['figures'][namespace]=stream.getvalue()
    return result


if __name__=='__main__':
    command=json.loads(sys.stdin.read())
    result=render(command)
    output=Path(command['output_directory'])
    for name,svg in result.pop('figures').items():(output/(name+'.svg')).write_text(svg,encoding='utf-8')
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
