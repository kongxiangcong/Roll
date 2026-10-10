"""Ordinary Agents SDK worker. Only two IPC tools; no filesystem or shell agent tools."""
import asyncio
import hashlib
import json
import logging
import platform
import sys
import threading
from dataclasses import asdict
from importlib.metadata import version

sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps({'kind':'bootstrap','stage':'PYTHON_READY'}),flush=True)

import httpx2
import jsonschema
from openai import AsyncOpenAI,APIStatusError
from agents import Agent,Runner,FunctionTool,ModelSettings,RunConfig,set_tracing_disabled
from agents.agent_output import AgentOutputSchemaBase
from agents.exceptions import ModelBehaviorError,MaxTurnsExceeded
from agents.models.openai_responses import OpenAIResponsesModel
from agents.retry import ModelRetrySettings

print(json.dumps({'kind':'bootstrap','stage':'SDK_IMPORTED'}),flush=True)

logging.disable(logging.CRITICAL)
set_tracing_disabled(True)
command=json.loads(sys.stdin.readline())
key=command.pop('key')


def emit(kind,**value):
    # A provider error/output could echo authentication text. Never persist the literal key.
    raw=json.dumps({'kind':kind,**value},ensure_ascii=False).replace(key,'[REDACTED_CREDENTIAL]')
    print(raw,flush=True)


class FinalSchema(AgentOutputSchemaBase):
    def is_plain_text(self):return False
    def name(self):return 'evidence_candidates'
    def json_schema(self):return command['output_schema']
    def is_strict_json_schema(self):return True
    def validate_json(self,value):
        try:jsonschema.validate(json.loads(value),self.json_schema())
        except (ValueError,jsonschema.ValidationError):raise ModelBehaviorError('DEEPSEEK_OUTPUT_SCHEMA_INVALID') from None
        return value


class DeepSeekTransport(httpx2.AsyncBaseTransport):
    """Public HTTP transport adapts only the documented unsupported empty `include` field."""
    def __init__(self):
        self.inner=httpx2.AsyncHTTPTransport(retries=0)
        self.calls=0;self.received=0
    async def handle_async_request(self,request):
        if str(request.url)!=command['endpoint']+'/responses' or request.method!='POST':
            raise ValueError('DEEPSEEK_ENDPOINT_DENIED')
        body=json.loads(request.content)
        if body.get('include')==[]:body.pop('include')
        if {'include','store','previous_response_id','conversation','background','prompt','truncation'}&body.keys():
            raise ValueError('DEEPSEEK_UNSUPPORTED_STATEFUL_PARAMETER')
        if body.get('model')!=command['model']:raise ValueError('DEEPSEEK_MODEL_CHANGED')
        raw=json.dumps(body,ensure_ascii=False).encode()
        if len(raw)>command['limits']['model_input_bytes']:raise ValueError('DEEPSEEK_CONTEXT_BYTE_LIMIT')
        if self.calls>=command['limits']['model_calls']:raise ValueError('DEEPSEEK_MODEL_CALL_LIMIT')
        self.calls+=1
        emit('model_request',number=self.calls,body_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            model=body['model'],protocol='RESPONSES_STATELESS',
            input_items=[v.get('type','message') for v in body['input']],parameter_names=sorted(body))
        headers={k:v for k,v in request.headers.items() if k.lower()!='content-length'}
        adapted=httpx2.Request('POST',request.url,headers=headers,content=raw,extensions=request.extensions)
        response=await self.inner.handle_async_request(adapted)
        received=bytearray()
        try:
            async for chunk in response.aiter_bytes(4096):
                self.received+=len(chunk);received.extend(chunk)
                if len(received)>command['limits']['model_response_bytes'] or self.received>command['limits']['model_total_response_bytes']:
                    emit('model_response',number=self.calls,http_status=response.status_code,
                        body=received[:command['limits']['model_response_bytes']].decode('utf-8',errors='replace'),
                        resolved_model=None,received_bytes=self.received,truncated=True)
                    raise ValueError('DEEPSEEK_MODEL_RESPONSE_BYTE_LIMIT')
        finally:await response.aclose()
        # Bodies are local audit data, never HTTP headers or credentials.
        text=received.decode('utf-8',errors='replace')
        try:resolved=json.loads(text).get('model')
        except ValueError:resolved=None
        emit('model_response',number=self.calls,http_status=response.status_code,body=text,
            resolved_model=resolved,received_bytes=self.received)
        if response.status_code==200:
            payload=json.loads(text)
            if payload.get('status') == 'incomplete' and (payload.get('incomplete_details') or {}).get('reason') == 'max_output_tokens':
                raise ValueError('DEEPSEEK_OUTPUT_TOKEN_LIMIT')
            names={tool['name'] for tool in command['tools']}
            for item in payload.get('output',[]):
                if item.get('type')=='function_call' and item.get('name') not in names:
                    emit('denied',name=str(item.get('name'))[:80],status='DENIED')
                    emit('failure',code='HOST_TOOL_NOT_ALLOWED')
                    raise ValueError('HOST_TOOL_NOT_ALLOWED')
        response_headers={k:v for k,v in response.headers.items() if k.lower() not in {'content-length','content-encoding'}}
        return httpx2.Response(response.status_code,headers=response_headers,content=bytes(received))
    async def aclose(self):await self.inner.aclose()


async def main():
    pending={};queue=asyncio.Queue();counter=0;lock=asyncio.Lock()
    loop=asyncio.get_running_loop()
    def drain():
        for line in sys.stdin:
            try:loop.call_soon_threadsafe(queue.put_nowait,json.loads(line))
            except (ValueError,RuntimeError):return
    threading.Thread(target=drain,daemon=True).start()
    async def read():
        while True:
            event=await queue.get()
            if event['kind']=='cancel':
                task.cancel();return
            future=pending.pop(event.get('id'),None)
            if future and not future.done():future.set_result(event['result'])
    async def invoke(context,arguments):
        nonlocal counter
        async with lock:
            counter+=1
            if counter>command['limits']['tool_calls']:raise ValueError('TOOL_BUDGET_EXHAUSTED')
            call_id='deepseek-'+str(counter)
            future=asyncio.get_running_loop().create_future();pending[call_id]=future
            emit('tool',id=call_id,name=context.tool_name,arguments=json.loads(arguments))
            return json.dumps(await future,ensure_ascii=False)
    tools=[FunctionTool(name=t['name'],description=t['description'],params_json_schema=t['inputSchema'],
        on_invoke_tool=invoke,strict_json_schema=True) for t in command['tools']]
    transport=DeepSeekTransport()
    async with httpx2.AsyncClient(transport=transport,timeout=15,follow_redirects=False,trust_env=False) as http:
        async with AsyncOpenAI(api_key=key,base_url=command['endpoint'],http_client=http,max_retries=0,timeout=15) as client:
            model=OpenAIResponsesModel(command['model'],client)
            agent=Agent(name='Roll bounded evidence',instructions=command['instructions'],model=model,
                tools=tools,output_type=FinalSchema(),handoffs=[],mcp_servers=[],
                model_settings=ModelSettings(max_tokens=command['limits']['max_output_tokens'],parallel_tool_calls=False,
                    store=None,response_include=[],tool_choice='auto',retry=ModelRetrySettings(max_retries=0)))
            emit('runtime',sdk_versions={n:version(n) for n in ['openai-agents','openai','httpx2']},
                python=platform.python_version(),tracing_disabled=True,transport='HTTP_RESPONSES_STATELESS',
                agent_tools=[t.name for t in tools],handoffs=[],mcp_servers=[],skills_loaded=False,
                builtin_tools=[],credential_persisted=False)
            task=asyncio.create_task(Runner.run(agent,command['prompt'],max_turns=command['limits']['model_calls'],
                auto_previous_response_id=False,run_config=RunConfig(tracing_disabled=True,trace_include_sensitive_data=False)))
            reader=asyncio.create_task(read())
            try:
                result=await task
                usage=result.context_wrapper.usage
                emit('completed',output=result.final_output,usage={field:getattr(usage,field) for field in
                    ['requests','input_tokens','output_tokens','total_tokens']})
            finally:reader.cancel()


try:asyncio.run(main())
except asyncio.CancelledError:emit('failure',code='DEEPSEEK_CANCELLED')
except APIStatusError as error:
    code='DEEPSEEK_AUTH_REJECTED' if error.status_code in {401,403} else 'DEEPSEEK_QUOTA_OR_RATE_LIMIT' if error.status_code==429 else 'DEEPSEEK_MODEL_UNAVAILABLE' if error.status_code==404 else 'DEEPSEEK_PROVIDER_ERROR'
    emit('failure',code=code,http_status=error.status_code,error_type=type(error).__name__)
except MaxTurnsExceeded:emit('failure',code='DEEPSEEK_MODEL_CALL_LIMIT')
except ModelBehaviorError:emit('failure',code='DEEPSEEK_OUTPUT_SCHEMA_INVALID')
except Exception as error:
    # Do not propagate arbitrary provider/tool text, headers or request objects.
    code=str(error) if isinstance(error,ValueError) and str(error) in {
        'DEEPSEEK_ENDPOINT_DENIED','DEEPSEEK_UNSUPPORTED_STATEFUL_PARAMETER','DEEPSEEK_CONTEXT_BYTE_LIMIT',
        'DEEPSEEK_MODEL_CALL_LIMIT','DEEPSEEK_MODEL_RESPONSE_BYTE_LIMIT','DEEPSEEK_OUTPUT_TOKEN_LIMIT','TOOL_BUDGET_EXHAUSTED'} else 'DEEPSEEK_RUNTIME_ERROR'
    emit('failure',code=code,error_type=type(error).__name__)
