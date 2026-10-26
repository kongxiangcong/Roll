from pathlib import Path
root=Path(__file__).resolve().parents[4];folder=root/'backend/src/roll/research'
body=(folder/'successor_entry.py').read_text(encoding='utf-8')
for old,new in [('entry-only stress','paired scenario stress'),('successor-entry-stress-v1','successor-joint-stress-v1'),('EntryStressCommand','JointStressCommand'),('SuccessorEntryStresses','SuccessorJointStresses'),('entry_stresses','joint_stresses'),('successor_entry_process','successor_joint_process'),('successor-entry-stresses','successor-joint-stresses'),('SUCCESSOR_ENTRY_STRESS','SUCCESSOR_JOINT_STRESS'),('diagnostic_id','joint_id')]:body=body.replace(old,new)
body=body.replace("+Path(__file__).with_name('successor_entry_engine.py').read_bytes().replace(b'\\r\\n',b'\\n')",'')
body=body.replace("    basis:str=Field", "    controls_id:str=Field(min_length=1,max_length=128)\n    entry_id:str=Field(min_length=1,max_length=128)\n    basis:str=Field")
body=body.replace('def __init__(self,stresses):','def __init__(self,stresses,controls,entries):').replace('        self.stresses=stresses;', '        self.controls=controls;self.entries=entries\n        self.stresses=stresses;')
body=body.replace("        payload={'source':source,'input':original,'method':method}","""        controls=self.controls.get(command.controls_id);entries=self.entries.get(command.entry_id)
        for item in (controls,entries):
            if any(item[key]!=source[key] for key in ('stress_id','successor_freeze_id','complete_protocol_fingerprint')) or item['source_manifest']!=source['archive'] or item['source_input']!=source['source']:
                raise HTTPException(409,'JOINT_STRESS_COMPONENT_PREFIX_MISMATCH')
        payload={'source':source,'controls':controls,'entries':entries,'control_input':self.shadow.checked_archive(controls['input_archive']),'method':method}""")
body=body.replace("'input_archive':input_archive,", "'controls_id':controls['comparison_id'],'entry_id':entries['diagnostic_id'],'controls_manifest':controls['archive'],'entry_manifest':entries['archive'],'input_archive':input_archive,")
body=body.replace("        for key in ('input_archive','method'):", """        if self.controls.get(value['controls_id'])['archive']!=value['controls_manifest'] or self.entries.get(value['entry_id'])['archive']!=value['entry_manifest']:raise HTTPException(409,'JOINT_STRESS_COMPONENT_MANIFEST_MISMATCH')
        for key in ('input_archive','method'):""")
(folder/'successor_joint.py').write_text(body,encoding='utf-8',newline='\n')
app=root/'backend/src/roll/app.py';text=app.read_text(encoding='utf-8');anchor='    successor_stresses=SuccessorStresses(successor_protocols)\n';place="    from roll.research.successor_evidence_review import SuccessorEvidenceReviews,EvidenceReviewCommand\n"
addition='''    from roll.research.successor_joint import SuccessorJointStresses,JointStressCommand
    successor_joint=SuccessorJointStresses(successor_stresses,successor_controls,successor_entries)

    @app.post('/api/research/successor-cost-stresses/{identifier}/joint-stress',status_code=201)
    async def successor_joint_create(identifier:str,command:JointStressCommand):return await successor_joint.create(identifier,command)

    @app.get('/api/research/successor-cost-stresses/{identifier}/joint-stress')
    def successor_joint_list(identifier:str):return successor_joint.listing(identifier)

    @app.get('/api/research/successor-joint-stresses/{identifier}')
    def successor_joint_get(identifier:str):return successor_joint.get(identifier)

    @app.post('/api/research/successor-joint-stresses/{identifier}/replay')
    async def successor_joint_replay(identifier:str):return await successor_joint.replay(identifier)
'''
assert place in text and 'successor_joint_create' not in text
app.write_text(text.replace(place,addition+place),encoding='utf-8',newline='\n')
