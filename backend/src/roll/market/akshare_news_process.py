try:
    from roll.market.observation_symbols import symbols
except ModuleNotFoundError:
    from observation_symbols import symbols
"""Pinned SDK search with anonymous raw-first transport and a fixed article allowlist."""
import contextlib,hashlib,ipaddress,json,os,socket,sys,time
from datetime import datetime,timezone
from importlib.metadata import version
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import urlsplit
from news_contract import SDK_VERSION,SDK_SOURCE_SHA,body_url,list_rows


def main(command):
    output=Path(command['output_directory']);output.mkdir(parents=True,exist_ok=True);start=time.monotonic();used=0
    state={'status':'FAILED','sdk_version':SDK_VERSION,'sdk_source_sha256':SDK_SOURCE_SHA,'captures':[],'items':[],'errors':[],'anonymous':True,'sdk_hardcoded_cookie_forwarded':False}
    def save():
        p=output/'capture.json.tmp';p.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');p.replace(output/'capture.json')
    save()
    try:
        code, symbol, secucode = symbols(command['instrument'])
        import requests
        from curl_cffi import requests as curl_requests
        package=find_spec('akshare');source=Path(package.origin).parent/'news/news_stock.py'
        if version('akshare')!=SDK_VERSION or hashlib.sha256(source.read_bytes()).hexdigest()!=SDK_SOURCE_SHA:raise ValueError('NEWS_SDK_IDENTITY_MISMATCH')
        resolve=socket.getaddrinfo
        def public_addresses(host,port,*args,**kwargs):
            if host not in {'search-api-web.eastmoney.com','finance.eastmoney.com'}:raise ValueError('NEWS_DNS_HOST_NOT_ALLOWED')
            addresses=resolve(host,port,socket.AF_INET,socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('NEWS_DNS_NON_PUBLIC_TARGET')
            return addresses
        socket.getaddrinfo=public_addresses
        session=requests.Session();session.trust_env=False
        fixtures=None
        if command.get('fixture'):
            if os.environ.get('ROLL_ENV')!='test':raise ValueError('NEWS_FIXTURE_TEST_ONLY')
            fixtures=json.loads(Path(command['fixture']).read_text(encoding='utf-8'))
            state['transport_kind']='METHOD_FIXTURE_ZERO_HTTP'
        def fetch(url,role,params=None):
            nonlocal used
            if role=='BODY':url=body_url(url)
            elif url!='https://search-api-web.eastmoney.com/search/jsonp':raise ValueError('NEWS_LIST_TARGET_NOT_ALLOWED')
            remaining=18-(time.monotonic()-start)
            if len(state['captures'])>=8 or remaining<=0:raise ValueError('NEWS_CALL_OR_TIME_BUDGET')
            ordinal=len(state['captures'])+1;c={'ordinal':ordinal,'role':role,'url':url,'received_at':None,'original_complete':False,'status_code':None,'bytes':0,'sha256':hashlib.sha256(b'').hexdigest()}
            state['captures'].append(c);save();data=bytearray()
            prepared=session.prepare_request(requests.Request('GET',url,params=params,headers={'User-Agent':'Roll/1 bounded public observation','Accept-Encoding':'identity'}))
            prepared.headers.pop('Cookie',None);prepared.headers.pop('Authorization',None)
            c['request_cookie_sent']='Cookie' in prepared.headers;save()
            if fixtures is None:response=session.send(prepared,timeout=max(.01,remaining),stream=True,allow_redirects=False)
            else:
                entry=fixtures[ordinal-1]
                if entry['role']!=role or entry['url']!=url:raise ValueError('NEWS_FIXTURE_TARGET_MISMATCH')
                response=requests.Response();response.status_code=entry.get('status_code',200);response.url=prepared.url;response._content=entry['body'].encode('utf-8');response._content_consumed=True
                # METHOD fixture deliberately seeds a cookie as Set-Cookie would.
                session.cookies.set('method_upstream_tracker','must-not-be-sent',domain='.eastmoney.com')
            c['url']=response.url;c['status_code']=response.status_code;save()
            try:
                with (output/f'{ordinal:02}.raw').open('wb') as stream:
                    for chunk in response.iter_content(65536):
                        prefix=chunk[:8388608-used];data.extend(prefix);used+=len(prefix);stream.write(prefix);stream.flush()
                        c.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),received_at=datetime.now(timezone.utc).isoformat());save()
                        if len(prefix)!=len(chunk) or time.monotonic()-start>18:raise ValueError('NEWS_BYTE_OR_TIME_BUDGET_PREFIX')
                    c['original_complete']=True
            finally:
                c.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),received_at=datetime.now(timezone.utc).isoformat());response.close();save()
            response._content=bytes(data);response._content_consumed=True;response.encoding='utf-8'
            if response.status_code!=200:raise ValueError('NEWS_HTTP_'+str(response.status_code))
            return response
        def sdk_get(url,params=None,**kwargs):
            p=json.loads(params['param']);page=p['param']['cmsArticleWebOld']
            if p.get('keyword')!=code or p.get('type')!=['cmsArticleWebOld'] or page.get('pageIndex')!=1 or page.get('pageSize')!=10 or page.get('sort')!='default':raise ValueError('NEWS_SDK_QUERY_SCOPE')
            # SDK contains historic example cookies. Deliberately discard all SDK headers.
            return fetch(url,'LIST',params)
        curl_requests.get=sdk_get
        with contextlib.redirect_stdout(sys.stderr):
            import akshare as ak
            try:frame=ak.stock_news_em(symbol=code);items=frame.to_dict(orient='records')
            except (KeyError,ValueError):
                if not state['captures'] or list_rows((output/'01.raw').read_bytes()):raise
                items=[]
        if len(items)>10:raise ValueError('NEWS_SDK_PAGE_BUDGET')
        state['items']=[{'fields':fields,'body_status':'NOT_FETCHED_BODY_BUDGET','body_ordinal':None,'text':None,'metadata':None,'errors':['BODY_BUDGET']} for fields in items]
        state['status']='CAPTURED';save()
        for item in state['items'][:3]:
            before=len(state['captures'])
            try:
                url=body_url(item['fields']['新闻链接']);fetch(url,'BODY')
                item.update(body_status='ARCHIVED_PENDING_EXTRACTION',body_ordinal=before+1,errors=[])
            except Exception as error:
                ordinal=len(state['captures']);captured=state['captures'][-1] if ordinal else None
                item.update(body_status='BODY_FETCH_FAILED',body_ordinal=ordinal if captured and captured.get('role')=='BODY' and ordinal>before else None,errors=[str(error)[:180] if isinstance(error,ValueError) else type(error).__name__])
            save()
        state['capture_elapsed_seconds']=time.monotonic()-start;save()
    except Exception as error:
        state.update(status='FAILED',errors=[str(error)[:180] if isinstance(error,ValueError) else type(error).__name__]);save()


if __name__=='__main__':main(json.loads(sys.stdin.buffer.read()))
