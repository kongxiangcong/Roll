"""Deterministic news event grouping and instrument association.

Exact canonical URL and content SHA256 are the only merge keys. Near-duplicate
similarity is deliberately not used: the observed single-stock sample does not
justify datasketch, and exact keys cannot merge number/date/negation changes.
"""
import hashlib,re,uuid
from urllib.parse import urlsplit

GROUPING_VERSION=1
ASSOCIATION_VERSION=1
EVENT_NAMESPACE=uuid.UUID('6f2d8d0e-3c1a-5a0b-9c47-6a3f0b1e2d31')
ALIAS_SUFFIXES=('股份有限公司','有限责任公司','有限公司','集团')
INDUSTRY_MARKERS=('行业','板块','有色金属','资金流','净流入','净流出')
THEME_MARKERS=('概念',)
MASK='ALIAS_CONFLICT'


def canonical_url(url):
    parsed=urlsplit(url or '')
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('NEWS_EVENT_URL_INVALID')
    return 'https://'+parsed.netloc.lower()+parsed.path


def normalize_text(value):
    return re.sub(r'\s+',' ',value or '').strip()


def fact_text(fact):
    return normalize_text((fact.get('title') or '')+'\n'+(fact.get('body_text') or fact.get('excerpt') or ''))


def content_digest(fact):
    return hashlib.sha256(fact_text(fact).encode('utf-8')).hexdigest()


def name_aliases(name):
    name=normalize_text(name)
    values={name} if name else set()
    for suffix in ALIAS_SUFFIXES:
        if name.endswith(suffix) and len(name)>len(suffix)+1:
            values.add(name[:-len(suffix)])
    return values


def _occurrences(text,needle):
    if not needle:return 0
    return text.count(needle)


def _code_occurrences(text,code):
    return len(re.findall(r'(?<![0-9])'+re.escape(code)+r'(?![0-9])',text))


def associate(fact,identities):
    """Return the fixed association decision for one stored fact."""
    title=normalize_text(fact.get('title'))
    body=normalize_text(fact.get('body_text') or fact.get('excerpt') or '')
    target=fact['instrument']
    aliases={};codes={}
    for identity in identities:
        for alias in name_aliases(identity.get('name')):
            aliases.setdefault(alias,set()).add(identity['instrument'])
        if identity.get('code'):
            codes.setdefault(identity['instrument'],identity['code'])
    objects=[];conflicts=[]
    def add(instrument,surface,where,count,kind,ambiguous):
        if count:objects.append({'instrument':instrument,'surface':surface,'where':where,'occurrences':count,
            'role':'SUBJECT' if where=='TITLE' else 'MENTION','kind':kind,'ambiguous':ambiguous})
    for alias,instruments in sorted(aliases.items()):
        ambiguous=len(instruments)>1
        if ambiguous:
            conflicts.append({'surface':alias,'instruments':sorted(instruments)})
        for instrument in sorted(instruments):
            add(instrument,alias,'TITLE',_occurrences(title,alias),'NAME',ambiguous)
            add(instrument,alias,'BODY',_occurrences(body,alias),'NAME',ambiguous)
    for instrument,code in sorted(codes.items()):
        add(instrument,code,'TITLE',_code_occurrences(title,code),'CODE',False)
        add(instrument,code,'BODY',_code_occurrences(body,code),'CODE',False)
    merged={}
    for item in objects:
        key=(item['instrument'],item['where'],item['role'],item['kind'])
        if key in merged:
            merged[key]['occurrences']+=item['occurrences']
            if len(item['surface'])>len(merged[key]['surface']):merged[key]['surface']=item['surface']
        else:merged[key]=dict(item)
    objects=sorted(merged.values(),key=lambda item:(item['instrument'],item['where'],item['kind'],item['surface']))
    target_objects=[item for item in objects if item['instrument']==target and not item['ambiguous']]
    name_in_title=any(item['where']=='TITLE' and item['kind']=='NAME' for item in target_objects)
    code_in_title=any(item['where']=='TITLE' and item['kind']=='CODE' for item in target_objects)
    name_in_body=any(item['where']=='BODY' and item['kind']=='NAME' for item in target_objects)
    code_in_body=any(item['where']=='BODY' and item['kind']=='CODE' for item in target_objects)
    target_conflict=any(target in item['instruments'] for item in conflicts)
    basis=[]
    if name_in_title:basis.append('TARGET_NAME_IN_TITLE')
    if code_in_title:basis.append('TARGET_CODE_IN_TITLE')
    if name_in_body:basis.append('TARGET_NAME_IN_BODY')
    if code_in_body:basis.append('TARGET_CODE_IN_BODY')
    if target_conflict:basis.append(MASK)
    if target_conflict and not code_in_title and not name_in_title:
        classification='UNCERTAIN'
    elif name_in_title or code_in_title:
        classification='COMPANY_SUBJECT'
    elif name_in_body:
        classification='COMPANY_MENTIONED'
    elif code_in_body:
        if any(marker in title for marker in THEME_MARKERS) and '行业' not in title:
            classification='UNRELATED'
        elif any(marker in title or marker in body for marker in INDUSTRY_MARKERS):
            classification='INDUSTRY_BACKGROUND'
        else:
            classification='UNCERTAIN'
    else:
        classification='UNCERTAIN'
    if classification=='UNRELATED':basis.append('THEME_PAGE_KEYWORD_ONLY')
    if classification=='INDUSTRY_BACKGROUND':basis.append('INDUSTRY_MARKER_WITH_KEYWORD_ONLY')
    if classification=='UNCERTAIN' and not basis:basis.append('NO_TARGET_MENTION')
    return {'version':ASSOCIATION_VERSION,'classification':classification,'basis':basis,'objects':objects,
        'conflicts':conflicts,'keyword_only':classification in ('UNRELATED','INDUSTRY_BACKGROUND')}


def _find(parent,index):
    while parent[index]!=index:
        parent[index]=parent[parent[index]];index=parent[index]
    return index


def _union(parent,left,right):
    left,right=_find(parent,left),_find(parent,right)
    if left!=right:parent[max(left,right)]=min(left,right)


def group_facts(facts,associations):
    """Group facts in persisted (rowid ascending) order by exact URL or content digest."""
    count=len(facts);parent=list(range(count))
    by_url={};by_digest={}
    for index,fact in enumerate(facts):
        url=canonical_url(fact.get('url'));digest=content_digest(fact)
        if url in by_url:_union(parent,by_url[url],index)
        else:by_url[url]=index
        if digest in by_digest:_union(parent,by_digest[digest],index)
        else:by_digest[digest]=index
    components={}
    for index in range(count):components.setdefault(_find(parent,index),[]).append(index)
    memberships={};events=[]
    for indexes in components.values():
        indexes.sort()
        primary=indexes[0]
        event_id=str(uuid.uuid5(EVENT_NAMESPACE,f"{facts[primary]['instrument']}|{GROUPING_VERSION}|{facts[primary]['fact_id']}"))
        previous_url={}
        for index in indexes:
            fact=facts[index];url=canonical_url(fact['url']);digest=content_digest(fact)
            if index==primary:
                relation,parent_fact='ORIGINAL',None
            elif digest==content_digest(facts[primary]):
                relation,parent_fact='REPRINT',primary
            elif url==canonical_url(facts[primary]['url']) and digest!=content_digest(facts[primary]):
                relation,parent_fact='REVISION',previous_url.get(url,primary)
            else:
                relation,parent_fact='LINKED',primary
            previous_url[url]=index
            memberships[fact['fact_id']]={'event_id':event_id,'relation':relation,
                'parent_fact_id':facts[parent_fact]['fact_id'] if parent_fact is not None else None}
        events.append({'event_id':event_id,'instrument':facts[primary]['instrument'],'primary_fact_id':facts[primary]['fact_id'],
            'fact_ids':[facts[i]['fact_id'] for i in indexes],
            'reprints':sum(1 for i in indexes if memberships[facts[i]['fact_id']]['relation']=='REPRINT'),
            'revisions':sum(1 for i in indexes if memberships[facts[i]['fact_id']]['relation']=='REVISION'),
            'classification':associations[facts[primary]['fact_id']]['classification'],
            'available_at':facts[primary].get('available_at')})
    events.sort(key=lambda item:(item['available_at'] or '',item['event_id']),reverse=True)
    return memberships,events
