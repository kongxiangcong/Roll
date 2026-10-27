"""Bounded, non-HTML report renderer. No resource loader or network client exists here.

Adapts cover/TOC/body/page-number/bookmark layout from the frozen MIT reference
scripts/md_to_pdf.py; implementation uses ReportLab instead of browser execution.
"""
import html
import json
import os
from pathlib import Path
import re
import sys
from xml.etree import ElementTree

VERSION = 'roll-report-pdf-1'


def render(request, destination):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, LongTable, TableStyle
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.graphics.shapes import Drawing, PolyLine, Rect, String

    explicit = os.environ.get('ROLL_REPORT_FONT')
    candidates = [explicit] if explicit else [
        str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/simsun.ttc'),
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/truetype/arphic/uming.ttc',
    ]
    font_path = next((p for p in candidates if p and Path(p).is_file()), None)
    if not font_path:
        raise ValueError('PDF_FONT_UNAVAILABLE: Set ROLL_REPORT_FONT to a licensed Chinese TrueType font')
    try:
        pdfmetrics.registerFont(TTFont('ReportChinese',font_path, subfontIndex=0))
    except Exception as error:
        raise ValueError('PDF_FONT_UNAVAILABLE: Chinese TrueType font could not be loaded') from error
    pdfmetrics.registerFontFamily('ReportChinese',normal='ReportChinese',bold='ReportChinese',italic='ReportChinese',boldItalic='ReportChinese')
    width, height = A4
    available = width-86
    body = ParagraphStyle('Body',fontName='ReportChinese',fontSize=9,leading=14,spaceAfter=7,wordWrap='CJK',splitLongWords=True)
    cell = ParagraphStyle('Cell',parent=body,fontSize=7,leading=10,spaceAfter=0)
    heading_styles = {n:ParagraphStyle('Heading'+str(n),parent=body,fontSize={1:17,2:13,3:11}[n],
        leading={1:24,2:19,3:16}[n],spaceBefore=15,spaceAfter=9,keepWithNext=True,textColor=colors.HexColor('#153650')) for n in (1,2,3)}
    cover = ParagraphStyle('Cover',parent=body,fontSize=24,leading=34,alignment=TA_CENTER,spaceAfter=24)

    def inline(value):
        # Escape first: source HTML/ReportLab markup cannot become active content.
        value = html.escape(html.unescape(value))
        value = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m:m[1]+' ('+m[2]+')', value)
        value = re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',value)
        value = value.replace('`','')
        return value

    class Document(BaseDocTemplate):
        def afterFlowable(self, flowable):
            if getattr(flowable,'report_heading',None):
                level,text,key = flowable.report_heading
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text,key,level=0 if level==1 else 1,closed=False)
                if level<=2:
                    self.notify('TOCEntry',(level-1,text,self.page,key))

    def footer(canvas,doc):
        canvas.saveState()
        canvas.setFont('ReportChinese',8)
        canvas.setFillColor(colors.HexColor('#586875'))
        canvas.drawString(43,28,'Roll · '+request['completeness']+' · 研究交付')
        canvas.drawRightString(width-43,28,str(doc.page))
        canvas.restoreState()

    doc = Document(str(destination),pagesize=A4,leftMargin=43,rightMargin=43,topMargin=43,bottomMargin=45,
        title=request['title'],author='Roll Research',allowSplitting=True)
    doc.addPageTemplates(PageTemplate(id='Report',frames=[Frame(43,45,available,height-88,id='body',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=footer))
    story = [Spacer(1,85),Paragraph(inline(request['title']),cover),
        Paragraph('交付状态：'+inline(request['completeness']),body),
        Paragraph('固定报告：'+inline(request['report_id']),body),
        Paragraph('共享快照：'+inline(str(request['snapshot_id'])),body),
        Paragraph('资料截止：'+inline(request['as_of']),body),
        Paragraph('报告原始字节 SHA256：'+inline(request['markdown_sha256']),body),
        Paragraph('PDF仅呈现固定报告，不增加事实核实、估值审核或正式使用资格。缺口及用途限制见正文。',body),PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle('TOC0',parent=body,fontSize=10,leading=16,spaceBefore=7),
        ParagraphStyle('TOC1',parent=body,fontSize=9,leading=14,leftIndent=12,spaceBefore=2)]
    story += [Paragraph('目录',heading_styles[1]),toc,PageBreak()]

    def chart(identifier):
        data = request['charts'].get(identifier)
        if data is None:
            raise ValueError('PDF_ASSET_MISSING: Chart is not bound to this report')
        if '<!DOCTYPE' in data.upper() or '<!ENTITY' in data.upper():
            raise ValueError('PDF_ASSET_UNSAFE: XML declarations are forbidden')
        root = ElementTree.fromstring(data)
        allowed = {'svg','rect','polyline','text'}
        attributes = {'xmlns','width','height','viewBox','x','y','fill','stroke','stroke-width','points','font-size'}
        for node in root.iter():
            if node.tag.split('}')[-1] not in allowed or not set(node.attrib)<=attributes:
                raise ValueError('PDF_ASSET_UNSAFE: Unsupported SVG element or attribute')
        if root.tag.split('}')[-1]!='svg':
            raise ValueError('PDF_ASSET_UNSAFE: Expected static SVG')
        w,h = float(root.attrib['width']),float(root.attrib['height'])
        if not 1<=w<=2000 or not 1<=h<=2000:
            raise ValueError('PDF_ASSET_UNSAFE: Invalid chart dimensions')
        drawing = Drawing(w,h)
        def color(s):
            return None if s=='none' else colors.HexColor(s)
        for node in root:
            tag = node.tag.split('}')[-1]; a=node.attrib
            if tag=='rect':
                drawing.add(Rect(float(a.get('x',0)),h-float(a.get('y',0))-float(a['height']),float(a['width']),float(a['height']),fillColor=color(a.get('fill','#ffffff')),strokeColor=color(a.get('stroke','none'))))
            elif tag=='polyline':
                points = [float(v) for v in re.split(r'[ ,]+',a['points'].strip())]
                if len(points)>2000 or len(points)%2:raise ValueError('PDF_ASSET_UNSAFE: Invalid points')
                points=[v if i%2==0 else h-v for i,v in enumerate(points)]
                drawing.add(PolyLine(points,strokeColor=color(a.get('stroke','#2468a0')),strokeWidth=float(a.get('stroke-width',1)),fillColor=None))
            elif tag=='text':
                drawing.add(String(float(a.get('x',0)),h-float(a.get('y',0)),node.text or '',fontName='ReportChinese',fontSize=float(a.get('font-size',12))))
        factor=min(available/w,245/h,1)
        drawing.scale(factor,factor);drawing.width=w*factor;drawing.height=h*factor
        return drawing

    original_lines=request['markdown'].splitlines()
    lines=[]
    # The frozen host emits blank lines between some appendix rows and can put
    # explanatory text immediately before a header. Normalize presentation only.
    for n,line in enumerate(original_lines):
        following=next((s.strip() for s in original_lines[n+1:] if s.strip()),'')
        if '|' in line and not line.lstrip().startswith('|') and re.fullmatch(r'[\s|:\-]+',following):
            prefix,header=line.split('|',1)
            lines.extend([prefix,'|'+header])
        else:
            lines.append(line)
    index=0;heading_index=0
    while index<len(lines):
        line=lines[index].strip()
        if not line:
            index+=1;continue
        match=re.fullmatch(r'!\[[^\]]*\]\(([^)]+)\)',line)
        if match:
            identifier=re.fullmatch(r'/api/company-research/report-charts/([0-9a-f]{64})',match[1])
            if not identifier:raise ValueError('PDF_ASSET_UNSAFE: Only bound report chart IDs are allowed')
            story.extend([chart(identifier[1]),Spacer(1,8)]);index+=1;continue
        if '![' in line:
            raise ValueError('PDF_ASSET_UNSAFE: Images must be standalone bound charts')
        following=next((s.strip() for s in lines[index+1:] if s.strip()),'')
        if line.startswith('|') and re.fullmatch(r'[\s|:\-]+',following):
            rows=[]
            while index<len(lines):
                if not lines[index].strip():
                    next_row=next((n for n in range(index+1,len(lines)) if lines[n].strip()),len(lines))
                    if next_row<len(lines) and lines[next_row].strip().startswith('|'):
                        index=next_row
                    else:
                        break
                if not lines[index].strip().startswith('|'):
                    break
                following_row=next((s.strip() for s in lines[index+1:] if s.strip()),'')
                if rows and not re.fullmatch(r'[\s|:\-]+',lines[index]) and re.fullmatch(r'[\s|:\-]+',following_row):
                    # A new header/separator starts a separate table, even when
                    # the preceding table uses blank-separated ordinary rows.
                    break
                current=lines[index].strip();index+=1
                if re.fullmatch(r'[\s|:\-]+',current):continue
                rows.append([v.replace('\\|','|') for v in re.split(r'(?<!\\)\|',current.strip('|'))])
            columns=max(len(row) for row in rows)
            if columns>16:raise ValueError('PDF_TABLE_TOO_WIDE: More than sixteen columns')
            data=[[Paragraph(inline(v),cell) for v in row+['']*(columns-len(row))] for row in rows]
            table=LongTable(data,colWidths=[available/columns]*columns,repeatRows=1,splitByRow=1,splitInRow=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eff4')),('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#bbc8d1')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            story.extend([table,Spacer(1,9)]);continue
        heading=re.match(r'^(#{1,6})\s+(.+)$',line)
        if heading:
            level=min(len(heading[1]),3);text=heading[2]
            paragraph=Paragraph(inline(text),heading_styles[level])
            # Only two outline levels: cannot skip an absent intermediate heading.
            if level<=2:
                paragraph.report_heading=(level,text,'heading-'+str(heading_index));heading_index+=1
            story.append(paragraph)
        else:
            story.append(Paragraph(inline(line),body))
        index+=1
    doc.multiBuild(story,maxPasses=4)
    return dict(version=VERSION,font_sha256=__import__('hashlib').sha256(Path(font_path).read_bytes()).hexdigest())


if __name__=='__main__':
    try:
        metadata=render(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')),Path(sys.argv[2]))
        print(json.dumps(metadata))
    except Exception as error:
        print(str(error)[:1000],file=sys.stderr)
        sys.exit(1)
