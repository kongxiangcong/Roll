from pathlib import Path
root=Path('D:/dsh-proj/Roll');out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-ordering-independent'
old=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-company-independent'
s=(old/'preserve_own.py').read_text().replace('ticket30-company-independent','ticket25-ordering-independent').replace("names=['t30ci-first']","names=['t25oi-first']").replace("'method_account_version_zero':True","'method_real_account_actions':0")
(out/'preserve_own.py').write_text(s,encoding='utf-8')
s=(old/'check_owned_processes.ps1').read_text().replace('ticket30-company-independent','ticket25-ordering-independent').replace('ticket30-producer','ticket25-ordering').replace('t30ci-first','t25oi-first')
(out/'check_owned_processes.ps1').write_text(s,encoding='utf-8')
