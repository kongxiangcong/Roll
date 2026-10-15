"""Fixed METHOD numerical edge cases against the actual pinned library."""
import json
from pathlib import Path
import subprocess
import pytest


def test_quantstats_keeps_unknown_calendar_and_suppresses_synthetic_months():
    root=Path(__file__).resolve().parents[3]
    python=root/'.scratch/rce-runtime/quantstats/Scripts/python.exe'
    assert python.exists(),'Configure the ticket19 pinned isolated runtime'
    script='''
import importlib.util,json,sys
spec=importlib.util.spec_from_file_location('performance_process',sys.argv[1]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
days=['2026-06-08','2026-06-09','2026-06-10']
cases={'zero':['100','100','100'],'short':['100'],'missing':['100','100'],'null':['100',None,'100'],'loss':['100','90','95'],'large':['100','300','350']}
results={}
for name,values in cases.items():
 points=[{'date':day,'nav_yuan':value} for day,value in zip(days,values)]
 curves={'SHADOW':{'continuous_performance':True,'points':points},'ACTUAL':{'continuous_performance':False,'points':[{'as_of':days[0],'net_assets':'100'},{'as_of':days[1],'net_assets':'200','external_cash_in':'100'}]}}
 command={'curves':curves,'sessions':days[:1] if name=='short' else days}
 result=module.render(command);result.pop('figures');results[name]=result['namespaces']
print(json.dumps(results,allow_nan=False))
'''
    completed=subprocess.run([str(python),'-I','-B','-c',script,str(root/'backend/src/roll/research/performance_process.py')],capture_output=True,text=True,timeout=45)
    assert completed.returncode==0,completed.stderr[-1500:]
    result=json.loads(completed.stdout)
    zero=result['zero']['SHADOW']
    assert zero['total_return']==0 and zero['maximum_drawdown']==0
    assert [m['month'] for m in zero['monthly_returns']]==['2026-06']
    assert zero['annualized_return'] is None and zero['returns'][0]['value'] is None
    assert result['short']['SHADOW']['status']=='INSUFFICIENT_POSITIVE_NAV_SUPPORT'
    for name in ('missing','null'):
        assert result[name]['SHADOW']['status']=='INCOMPLETE_FIXED_WINDOW'
        assert 'total_return' not in result[name]['SHADOW']
    assert result['missing']['SHADOW']['coverage']['missing_sessions']==['2026-06-10']
    assert result['null']['SHADOW']['coverage']['unknown_nav_dates']==['2026-06-09']
    assert result['loss']['SHADOW']['maximum_drawdown']==pytest.approx(-.1)
    assert result['large']['SHADOW']['total_return']==pytest.approx(2.5)
    assert result['large']['SHADOW']['monthly_returns'][0]['value']==pytest.approx(2.5)
    assert all(r['ACTUAL']['status']=='NOT_A_CONTINUOUS_RETURN_SERIES' and not r['ACTUAL']['returns'] for r in result.values())
