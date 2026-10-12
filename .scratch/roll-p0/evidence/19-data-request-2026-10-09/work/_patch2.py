import io

p = 'build_package.py'
s = io.open(p, encoding='utf-8').read()

old = (
    'write_jsonl(PKG / "evidence/search_log.jsonl", SEARCH)\n'
    '_b = (PKG / "evidence/search_log.jsonl").read_bytes()\n'
    'for f in MANIFEST["files"]:\n'
    '    if f["path"] == "evidence/search_log.jsonl":\n'
    '        f["sha256"] = sha_bytes(_b)\n'
    '        f["bytes"] = len(_b)\n'
    '        f["record_count"] = len(SEARCH)\n'
)

new = (
    'write_jsonl(PKG / "evidence/search_log.jsonl", SEARCH)\n'
    '_b = (PKG / "evidence/search_log.jsonl").read_bytes()\n'
    'for f in MANIFEST["files"]:\n'
    '    if f["path"] == "evidence/search_log.jsonl":\n'
    '        f["sha256"] = sha_bytes(_b)\n'
    '        f["bytes"] = len(_b)\n'
    '        f["record_count"] = len(SEARCH)\n'
    'write_json(PKG / "manifest.json", MANIFEST)   # re-write AFTER the search_log hash refresh\n'
)

assert old in s, 'marker not found'
s = s.replace(old, new, 1)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('patched ok')
