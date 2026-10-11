from pathlib import Path
root=Path('D:/dsh-proj/Roll')
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-company-independent'
old=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-stock-independent'
s=(old/'check_integrity.py').read_text()
s=s.replace('Sixth Ticket30 two-target','Seventh Ticket30 exact-target').replace('sse-stock-suspension','sse-company-contract').replace('ticket30-stock-independent','ticket30-company-independent').replace('f44d1685a808fcba976007ea3e0fc14d218f93c6','53c5d5761604990fe8dabb2979bb32fe85334ec8')
s=s.replace("[('runtime',2728,375082862,''),('composition27',153,20080223,'-composition27')]","[('runtime',1577,181872574,'')]")
s=s.replace("source-composition27-after.json","source-composition-after.json").replace("'files':2881,'bytes':395163085","'files':1577,'bytes':181872574")
start=s.index("reference=source/")
end=s.index("result=",start)
s=s[:start]+"reference=source/'backend/src/roll/market/reference/sse-company-contract'\ndependencies=[]\n"+s[end:]
(out/'check_integrity.py').write_text(s,encoding='utf-8')
s=(old/'preserve_own.py').read_text().replace('ticket30-stock-independent','ticket30-company-independent').replace("names=['t30si-first','t30si-worker-corrected','t30si-worker-watch-corrected']","names=['t30ci-first']").replace("'first_harness_synthetic_method_baseline_retained':True","'method_account_version_zero':True")
(out/'preserve_own.py').write_text(s,encoding='utf-8')
