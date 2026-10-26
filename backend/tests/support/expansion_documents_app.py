"""METHOD parser transport fixture: real archived PDF, synthetic derivation."""
from fastapi.testclient import TestClient
from expansion_statements_app import app as statements_app


def app():
    application=statements_app()
    async def parser(source,output,command):
        import hashlib
        return {'status':'SUCCESS','parser_version':'2.139.0','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'document':{'texts':[{'text':'METHOD 第66页 合并现金流量表 人民币元','prov':[{'page_no':66,'bbox':{'l':20,'t':30,'r':500,'b':90}}]},{'text':'METHOD 合并现金流量表（续） 人民币元 附注68','prov':[{'page_no':67,'bbox':{'l':20,'t':30,'r':500,'b':90}}]}],
            'tables':[{'prov':[{'page_no':67,'bbox':{'l':20,'t':100,'r':500,'b':600}}],'data':{'num_rows':1,'num_cols':2,'table_cells':[{'text':'投资活动现金流量净额','start_row_offset':0,'start_col_offset':0},{'text':'(23,434,970,323)','start_row_offset':0,'start_col_offset':1}]}}]},
            'confidence':None,'warnings':['METHOD_TRANSPORT_NOT_REAL_DOCLING'],'runtime':{'kind':'METHOD_TRANSPORT_FIXTURE'}}
    application.state.financial_documents.worker=parser
    return application
