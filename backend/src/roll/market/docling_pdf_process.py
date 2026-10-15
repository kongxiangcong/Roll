"""Pinned Docling worker. Receives only a verified archived PDF, never a URL."""
import hashlib,json,socket,sys
from importlib.metadata import version
from pathlib import Path


def main(command):
    output=Path(command['output']);reference=command['reference']
    result={'status':'FAILED','parser_version':'2.139.0','source_sha256':command['source_sha256'],'document':{},'confidence':None,'warnings':[],'runtime':reference}
    def deny(*args,**kwargs):raise RuntimeError('DOCLING_NETWORK_DISABLED')
    socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny
    try:
        if reference['status']!='VERIFIED':raise ValueError('DOCLING_RUNTIME_NOT_VERIFIED')
        for package,expected in reference['packages'].items():
            if version(package)!=expected:raise ValueError('DOCLING_PACKAGE_VERSION_MISMATCH')
        source=Path(command['source'])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=command['source_sha256']:raise ValueError('DOCLING_SOURCE_CHANGED')
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.accelerator_options import AcceleratorOptions,AcceleratorDevice
        from docling.datamodel.pipeline_options import PdfPipelineOptions,RapidOcrOptions,TableFormerMode
        from docling.document_converter import DocumentConverter,PdfFormatOption
        models=Path(command['models'])
        ocr={k:str(models/v) for k,v in reference['ocr_models'].items()}
        options=PdfPipelineOptions(artifacts_path=models,enable_remote_services=False,do_ocr=True,do_table_structure=True,document_timeout=100)
        options.accelerator_options=AcceleratorOptions(num_threads=2,device=AcceleratorDevice.CPU)
        options.ocr_options=RapidOcrOptions(backend='onnxruntime',lang=['iso:zh-Hans'],text_score=0.0,**ocr)
        options.table_structure_options.mode=TableFormerMode.ACCURATE
        converter=DocumentConverter(allowed_formats=[InputFormat.PDF],format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=options)})
        converted=converter.convert(source,page_range=(command['first_page'],command['last_page']),max_num_pages=command['source_page_count'],max_file_size=16*1024*1024,raises_on_error=False)
        result['status']=converted.status.value.upper()
        result['document']=converted.document.export_to_dict()
        confidence=getattr(converted,'confidence',None)
        result['confidence']=confidence.model_dump(mode='json') if confidence is not None else None
        result['warnings']=[str(error)[:300] for error in getattr(converted,'errors',[])][:100]+['PARSER_OUTPUT_REQUIRES_REVIEW','CROSS_PAGE_HEADERS_AND_FOOTNOTES_NOT_AUTOMATICALLY_MERGED']
    except Exception as error:result['warnings'].append(type(error).__name__+': '+str(error)[:300])
    temporary=output.with_suffix('.tmp');temporary.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');temporary.replace(output)


if __name__=='__main__':main(json.loads(sys.stdin.buffer.read()))
