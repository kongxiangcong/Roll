"""Fixed bounded PDF text reader. Its caller owns timeout and all paths."""
import json
from pathlib import Path
import sys
from io import BytesIO
from pypdf import PdfReader

request=json.loads(sys.stdin.readline())
raw=Path(request['path']).read_bytes()
if len(raw)>8*1024*1024:raise ValueError('SOURCE_QUOTE_SIZE_BOUND')
reader=PdfReader(BytesIO(raw))
if not 1<=request['page']<=len(reader.pages)<=2000:raise ValueError('SOURCE_QUOTE_PAGE_BOUND')
text=reader.pages[request['page']-1].extract_text()
if len(text.encode())>65536:raise ValueError('SOURCE_QUOTE_TEXT_BOUND')
print(json.dumps(dict(text=text,page=request['page'],page_count=len(reader.pages)),ensure_ascii=True),flush=True)
