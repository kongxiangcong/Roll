"""Check tracked Markdown's local links without crawling ignored runtimes."""
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
paths = subprocess.check_output(['git', '-c', 'core.quotePath=false', 'ls-files', '*.md'], cwd=ROOT, text=True).splitlines()
paths += subprocess.check_output(['git', '-c', 'core.quotePath=false', 'ls-files', '--others', '--exclude-standard', '*.md'],
                                 cwd=ROOT, text=True).splitlines()
missing = []
checked = 0
for relative in sorted(set(paths)):
    source = ROOT / relative
    for raw in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', source.read_text(encoding='utf-8-sig')):
        target = raw.strip()
        if target.startswith('<') and '>' in target:
            target = target[1:target.index('>')]
        else:
            target = re.split(r'\s+[\"\']', target, maxsplit=1)[0]
        if not target or target.startswith('#') or re.match(r'^(https?://|mailto:|app:|codex:|plugin:|data:)', target):
            continue
        target = unquote(target.split('#', 1)[0])
        resolved = Path(target) if Path(target).is_absolute() else source.parent / target
        checked += 1
        if not resolved.exists():
            missing.append({'source': relative, 'target': target})
result = {'checked_git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'markdown_files': len(set(paths)), 'local_links': checked, 'missing': missing}
(EVIDENCE / 'final-document-links.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
if missing:
    raise SystemExit(1)
