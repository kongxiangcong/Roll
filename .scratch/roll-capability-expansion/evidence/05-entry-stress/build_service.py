from pathlib import Path
root=Path(__file__).resolve().parents[4];folder=root/'backend/src/roll/research'
body=(folder/'successor_controls.py').read_text(encoding='utf-8')
for old,new in [('original comparator contracts','entry-only stress contracts'),('successor-registered-controls-v1','successor-entry-stress-v1'),('ControlsCommand','EntryStressCommand'),('SuccessorRegisteredControls','SuccessorEntryStresses'),('registered_controls','entry_stresses'),('successor_controls_process','successor_entry_process'),('successor-registered-controls','successor-entry-stresses'),('SUCCESSOR_REGISTERED_CONTROLS','SUCCESSOR_ENTRY_STRESS'),('SUCCESSOR_CONTROLS','SUCCESSOR_ENTRY_STRESS'),('comparison_id','diagnostic_id')]:body=body.replace(old,new)
body=body.replace("+Path(__file__).with_name('successor_entry_process.py').read_bytes().replace(b'\\r\\n',b'\\n')", "+Path(__file__).with_name('successor_entry_process.py').read_bytes().replace(b'\\r\\n',b'\\n')+Path(__file__).with_name('successor_entry_engine.py').read_bytes().replace(b'\\r\\n',b'\\n')")
start=body.index("        if original['frozen']['baseline']['positions']:")
end=body.index('        body=encode(payload).encode()',start)
body=body[:start]+"        payload={'source':source,'input':original,'method':method}\n"+body[end:]
body=body.replace("'predecessor_manifest':legacy['archive'],",'').replace("            'cash_adapter_sha256':payload['cash_adapter_sha256'],",'            ')
body=body.replace("('input_archive','method','predecessor_manifest')", "('input_archive','method')")
(folder/'successor_entry.py').write_text(body,encoding='utf-8',newline='\n')
app=root/'backend/src/roll/app.py';text=app.read_text(encoding='utf-8');anchor='    successor_stresses=SuccessorStresses(successor_protocols)\n'
addition='''    from roll.research.successor_entry import SuccessorEntryStresses,EntryStressCommand
    successor_entries=SuccessorEntryStresses(successor_stresses)

    @app.post('/api/research/successor-cost-stresses/{identifier}/entry-stress',status_code=201)
    async def successor_entry_create(identifier:str,command:EntryStressCommand):return await successor_entries.create(identifier,command)

    @app.get('/api/research/successor-cost-stresses/{identifier}/entry-stress')
    def successor_entry_list(identifier:str):return successor_entries.listing(identifier)

    @app.get('/api/research/successor-entry-stresses/{identifier}')
    def successor_entry_get(identifier:str):return successor_entries.get(identifier)

    @app.post('/api/research/successor-entry-stresses/{identifier}/replay')
    async def successor_entry_replay(identifier:str):return await successor_entries.replay(identifier)
'''
assert anchor in text and 'successor_entry_create' not in text
app.write_text(text.replace(anchor,anchor+addition),encoding='utf-8',newline='\n')
