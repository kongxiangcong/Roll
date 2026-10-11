from pathlib import Path
root=Path('D:/dsh-proj/Roll');out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket28-independent';old=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-ordering-independent'
s=(old/'check_owned_processes.ps1').read_text().replace('ticket25-ordering-independent','ticket28-independent').replace('ticket25-ordering','ticket28').replace('t25oi-first','t28i-first')
(out/'check_owned_processes.ps1').write_text(s,encoding='utf-8')
s=(old/'preserve_own.py').read_text().replace('ticket25-ordering-independent','ticket28-independent').replace("names=['t25oi-first']","names=['t28i-first']").replace('jobs=[]','jobs=[];excluded=[]')
s=s.replace("s=Path(str(current/filename)[4:]);d=dest/name/s.relative_to(source);assert stat.S_ISREG(guard(s).st_mode)","s=Path(str(current/filename)[4:]);d=dest/name/s.relative_to(source);assert stat.S_ISREG(guard(s).st_mode)\n            if s.parent.name=='notification-private' and s.name in {'channel.json','channel.lock'}:\n                excluded.append({'source':str(s),'bytes_metadata_only':guard(s).st_size,'fixture':'owned fresh test_public.py','opened_hashed_copied':False});continue")
s=s.replace("'all_failure_namespaces_retained':True","'all_failure_namespaces_retained':True,'exact_private_metadata_exclusions':excluded,'private_contents_read_hashed_copied':0")
(out/'preserve_own.py').write_text(s,encoding='utf-8')
