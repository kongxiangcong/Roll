"""Prepare a concrete wire from ticket12 static public evidence. Zero auth/model/network."""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from roll.accounts.ledger import encode
from roll.research.company.report_valuation import ReportValuationRuntime
from roll.research.company.service import verified, fingerprint
from roll.research.company.report_template import code_hashes

source = Path(sys.argv[1])
output = Path(sys.argv[2])
data = json.loads(source.read_text(encoding='utf-8'))
snapshot, packet = verified(data['snapshot']), verified(data['analysis_input'])
assert snapshot['input_id'] == packet['input_id']
assert snapshot['input_sha256'] == packet['packet_sha256'] == fingerprint(packet['payload'])
assert snapshot['valuation_ids'] == [] and not snapshot.get('economic_review_ids')
assert all(f['company_id'] == snapshot['company_id'] for f in packet['payload']['facts'])
class FrozenResearch:
    def analysis_snapshot(self, identifier, purpose=None):
        assert identifier == snapshot['snapshot_id']
        return snapshot
    def analysis_input(self, identifier):
        assert identifier == packet['input_id']
        return packet
request = dict(company_id=snapshot['company_id'], snapshot_id=snapshot['snapshot_id'],
    as_of=snapshot['as_of'], source_mode='REUSE', valuation_purpose='BASELINE_RESEARCH',
    idempotency_key='review-fix-lulu-c549-static-preview')
job = dict(request, model='gpt-6.1-sol', request_cutoff=request['as_of'])
command = ReportValuationRuntime(SimpleNamespace(research=FrozenResearch(), worker=None)).command(job)
output.mkdir(parents=True, exist_ok=True)
wire = encode(command).encode()
(output / 'command.json').write_bytes(wire)
(output / 'request-draft.json').write_text(encode(request), encoding='utf-8')
receipt = dict(kind='STATIC_PUBLIC_SOURCE_VALUATION_PREVIEW_ONLY', source_path=str(source),
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), source_bytes=source.stat().st_size,
    snapshot_id=snapshot['snapshot_id'], snapshot_sha256=snapshot['content_sha256'],
    input_id=packet['input_id'], input_sha256=packet['packet_sha256'],
    fact_count=len(packet['payload']['facts']), material_count=len(packet['payload']['materials']),
    command_sha256=hashlib.sha256(wire).hexdigest(), command_bytes=len(wire),
    model=command['model'], tools=command['tools'], purpose='BASELINE_RESEARCH',
    preparation_code_hashes=code_hashes(),
    network_calls=0, model_calls=0, auth_reads=0, database_access=0,
    limitation='Not executed or authorized for external dispatch. Current pricing remains separately guarded; baseline is reconstructed conditional research, not historical PIT.',
    exclusions='No existing operating model, economic review, valuation input or result included')
(output / 'receipt.json').write_text(encode(receipt), encoding='utf-8')
print(encode(receipt))

