"""Deterministic, editable vector master for the FarajaMH workflow."""
from pathlib import Path
from html import escape
import json
from reportlab.graphics.shapes import Drawing, Rect, Circle, Line, Polygon, PolyLine, String, Path as RPath
from reportlab.graphics import renderPDF, renderSVG
from reportlab.lib.colors import toColor as HexColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUT = Path(__file__).resolve().parent
BASE = OUT / 'Minority_Report_FarajaMH_workflow_v9'
pdfmetrics.registerFont(TTFont('Arial', '/System/Library/Fonts/Supplemental/Arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', '/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
W, H = 2400, 2220
D = Drawing(W, H)
NAVY = '#142650'
DARK = '#23344D'
GRAY = '#8996A7'
PALE = '#F4F7FB'
TEAL = '#0F766E'
RED = '#B42318'
BODY, LEAD = 27, 34
checks = []
all_text = []

def rect(x,y,w,h,fill='white',stroke=None,r=0,sw=1):
    D.add(Rect(x,H-y-h,w,h,rx=r,ry=r,fillColor=HexColor(fill) if fill else None,
               strokeColor=HexColor(stroke) if stroke else None,strokeWidth=sw))

def line(x1,y1,x2,y2,color=GRAY,sw=4,dash=None):
    q=Line(x1,H-y1,x2,H-y2,strokeColor=HexColor(color),strokeWidth=sw)
    if dash: q.strokeDashArray=dash
    D.add(q)

def circle(x,y,r,fill,stroke=None,sw=1):
    D.add(Circle(x,H-y,r,fillColor=HexColor(fill) if fill else None,
                 strokeColor=HexColor(stroke) if stroke else None,strokeWidth=sw))

def poly(points,fill,stroke=None,sw=1):
    D.add(Polygon([v for x,y in points for v in (x,H-y)],fillColor=HexColor(fill) if fill else None,
                  strokeColor=HexColor(stroke) if stroke else None,strokeWidth=sw))

def txt(s,x,y,size=BODY,bold=False,color=DARK,anchor='start'):
    font='Arial-Bold' if bold else 'Arial'
    D.add(String(x,H-y-size,s,fontName=font,fontSize=size,fillColor=HexColor(color),textAnchor=anchor))
    all_text.append(s)

def wrap(s,width,size=BODY,bold=False):
    font='Arial-Bold' if bold else 'Arial'
    result=[]
    for para in s.split('\n'):
        words=para.split(); current=''
        for word in words:
            trial=(current+' '+word).strip()
            if current and pdfmetrics.stringWidth(trial,font,size)>width:
                result.append(current); current=word
            else: current=trial
        result.append(current)
    return result

def para(s,x,y,width,size=BODY,lead=LEAD,bold=False,color=DARK):
    lines=wrap(s,width,size,bold)
    for a in lines:
        txt(a,x,y,size,bold,color); y+=lead
    return y

def bullet(s,x,y,width,color,size=BODY,lead=LEAD):
    circle(x+5,y+size*.68,5,color)
    end=para(s,x+24,y,width-24,size,lead)
    return end+11

def arrow(x1,y1,x2,y2,color=GRAY,sw=6):
    line(x1,y1,x2,y2,color,sw)
    if x2>x1: pts=[(x2,y2),(x2-15,y2-10),(x2-15,y2+10)]
    elif x2<x1: pts=[(x2,y2),(x2+15,y2-10),(x2+15,y2+10)]
    elif y2>y1: pts=[(x2,y2),(x2-10,y2-15),(x2+10,y2-15)]
    else: pts=[(x2,y2),(x2-10,y2+15),(x2+10,y2+15)]
    poly(pts,color)

def path(points,color=GRAY,sw=6,dash=None):
    q=PolyLine([v for x,y in points for v in (x,H-y)],strokeColor=HexColor(color),strokeWidth=sw,fillColor=None)
    if dash:q.strokeDashArray=dash
    D.add(q)

def icon(kind,cx,top,color,scale=1):
    ox=cx-60*scale
    def pt(x,y): return ox+x*scale,top+y*scale
    def rr(x,y,w,h,fill=None,stroke=NAVY,r=7):
        rect(*pt(x,y),w*scale,h*scale,fill,stroke,r*scale,3*scale)
    def ll(x,y,xx,yy,c=NAVY,sw=4): line(*pt(x,y),*pt(xx,yy),c,sw*scale)
    def cc(x,y,r,fill,stroke=None):circle(*pt(x,y),r*scale,fill,stroke,3*scale)
    def pp(ps,fill,stroke=None):poly([pt(x,y) for x,y in ps],fill,stroke,3*scale)
    if kind=='speech':
        rr(7,8,85,60,'#EDF3FC');pp([(24,66),(24,84),(44,66)],'#EDF3FC',NAVY)
        ll(23,27,73,27,color);ll(23,42,64,42,color)
        rr(64,47,49,36,color,None);cc(77,65,3,'white');cc(89,65,3,'white');cc(101,65,3,'white')
    elif kind=='spans':
        rr(18,5,69,88,'#F4F7FB');
        for yy,ww,co in [(24,42,color),(40,34,'#F59E0B'),(56,44,color)]:
            rr(29,yy,ww,6,co,None,2)
        cc(88,70,20,'white',NAVY);ll(103,85,118,100)
    elif kind=='monitor':
        rr(5,7,109,70,'#F0FDFA');rr(15,17,89,46,'white',None)
        ll(28,31,76,31,color);ll(28,46,61,46,color)
        ll(60,78,60,93);ll(37,95,83,95)
        cc(100,68,18,'white',NAVY);ll(112,81,126,95)
    elif kind=='scales':
        ll(60,9,60,86);ll(20,29,100,29);ll(60,9,50,20);ll(60,9,70,20)
        for xx in (25,95):
            ll(xx,29,xx-18,66);ll(xx,29,xx+18,66)
            pp([(xx-23,67),(xx+23,67),(xx+14,79),(xx-14,79)],color)
        rr(35,87,50,8,NAVY,None,3)
    elif kind=='people':
        cc(61,22,17,color);cc(23,36,13,color);cc(99,36,13,color)
        rr(38,46,46,43,color,None,15);rr(5,55,30,34,'#FFEDD5',None,10);rr(87,55,30,34,'#FFEDD5',None,10)
    elif kind=='lookup':
        ll(20,66,45,20,color);ll(20,66,74,76,color);ll(45,20,81,44,color)
        for xx,yy in [(20,66),(45,20),(74,76)]:cc(xx,yy,12,'#DCFCE7',color)
        cc(91,41,24,'white',NAVY);ll(108,59,125,77)
    elif kind=='records':
        # A document plus database, deliberately distinct from lookup's nodes.
        rr(1,10,55,74,'#F0FDF4');ll(13,27,43,27,color);ll(13,42,43,42,color);ll(13,57,35,57,color)
        rr(67,26,50,61,'#DCFCE7',color,0)
        from reportlab.graphics.shapes import Ellipse
        for yy,fill in [(26,'#F0FDF4'),(46,None),(66,None),(87,None)]:
            xx,yt=pt(92,yy)
            D.add(Ellipse(xx,H-yt,25*scale,8*scale,fillColor=HexColor(fill) if fill else None,strokeColor=HexColor(color),strokeWidth=3*scale))

def robots(x,y):
    for i,co in enumerate(['#0369A1','#6D28D9','#15803D']):
        xx=x+i*113
        line(xx+35,y+8,xx+35,y+20,co,3);circle(xx+35,y+5,5,co)
        rect(xx,y+20,72,49,'#F5F3FF',co,10,3)
        rect(xx+9,y+30,54,26,NAVY,None,7)
        circle(xx+25,y+43,5,'white');circle(xx+48,y+43,5,'white')
        txt('Model '+chr(65+i),xx+36,y+80,23,True,co,'middle')
    rect(x+345,y+24,102,46,'white','#ACB8CE',8,1.5)
    txt('+ more',x+396,y+34,23,True,NAVY,'middle')

rect(0,0,W,H,'#F8FAFD')
txt('The Minority Report · FarajaMH',W/2,28,67,True,NAVY,'middle')

CW, CH = 538, 830
XS = [46,630,1214,1798]
Y1,Y2=142,1090
CO=['#1E3A8A','#1E3A8A','#6D28D9','#0F766E','#0369A1','#C2410C','#15803D','#15803D']
TITLES=['Utterance and context','Identify expressions','Model interpretations','Dictionary evidence','Compare and route','HITL Review: meaning','Terminology lookup','Record and outputs']
for i in range(8):
    x,y=XS[i%4],Y1 if i<4 else Y2
    rect(x,y,CW,CH,'white','#D9E2EF',17,1.8)
    rect(x,y,CW,69,CO[i],None,17)
    rect(x,y+36,CW,33,CO[i])
    circle(x+36,y+34,23,'white')
    txt(str(i+1),x+36,y+10,35,True,CO[i],'middle')
    title_size=30
    assert pdfmetrics.stringWidth(TITLES[i],'Arial-Bold',title_size)<CW-84
    txt(TITLES[i],x+74,y+17,title_size,True,'white')

def example(i,lines,height=175):
    x=XS[i%4]+18; card_y=Y1 if i<4 else Y2
    y=card_y+CH-height-17
    bg=['#EEF4FF','#EEF4FF','#F4EFFF','#EBFAF6','#EDF6FC','#FFF4ED','#EEF9F0','#EEF9F0'][i]
    rect(x,y,CW-36,height,bg,None,10)
    end=para('Illustrative example',x+18,y+14,CW-72,25,31,True,NAVY if i==5 else CO[i])
    for s in lines:
        end=para(s,x+18,end+5,CW-72,26,32)
    assert end<=y+height-4,(i+1,'example overflow',end,y+height)
    return y

def simple(i,kind,bullets,examples,eh=175):
    x=XS[i%4];y=Y1 if i<4 else Y2
    icon(kind,x+CW/2,y+(83 if i==7 else 103),CO[i],.8 if i==7 else (1.45 if i in (0,1) else 1.08))
    yy=y+(190 if i==7 else (285 if i in (0,1) else 224))
    for s in bullets: yy=bullet(s,x+25,yy,CW-50,CO[i])
    limit=example(i,examples,eh)
    checks.append({'card':i+1,'text_bottom':round(yy,1),'example_top':limit,'clearance':round(limit-yy,1)})
    assert yy<=limit-12,(i+1,'body overflow',yy,limit)

simple(0,'speech',[
    'Original wording · language or dialect · setting',
    'Keep the source-language record',
    'No translation before interpretation'],[
    '“Moyo wangu unaniuma”',
    'Synthetic context: grief and reported chest discomfort'],190)
simple(1,'spans',[
    'Extract each expression as a span',
    'Keep full context; reviewers may correct boundaries',
    'Steps 3–7 run once per expression'],[
    'Span: “Moyo wangu unaniuma”',
    'Retain grief and chest-discomfort context'],190)

x=XS[2];y=Y1
robots(x+43,y+93)
yy=y+224
for s in ['Separate calls before dictionary exposure','Model and prompt versions pinned',
          'Literal translation · meanings · category · evidence','Confidence recorded, never used for routing']:
    yy=bullet(s,x+25,yy,CW-50,CO[2])
limit=example(2,['Model A (mock): emotional pain','Model B (mock): possible chest pain','Model C (mock): context unclear'],190)
checks.append({'card':3,'clearance':limit-yy}); assert yy<=limit-10,(3,yy,limit)

x=XS[3];y=Y1
icon('monitor',x+CW/2,y+91,TEAL,1.08)
yy=y+224
for s in ['Growing, versioned idiom library','Proposed seed: FarajaMH workshop library','Meaning · category · context limits · source', 'Missing entry? Continue interpretation and review.']:
    yy=bullet(s,x+25,yy,CW-50,TEAL)
rect(x+24,yy+4,CW-48,44,'#DDF7EE',None,8)
txt('Evidence source, not a vote',x+CW/2,yy+12,25,True,TEAL,'middle')
limit=example(3,['Mock entry: emotional pain','Check applicability to this speaker and context'],190)
assert yy+52<limit-8,(4,yy,limit)

# The second-row cards use smaller icons to give priority to review text.
x=XS[0];y=Y2
icon('scales',x+CW/2,y+81,CO[4],.74)
yy=y+169
for s in ['Model–model: Do the models agree?','Model–dictionary: Do they match the library?',
          'Check category and applicability: negation · experiencer · time',
          'Review all disagreements, all safety flags and a random sample of agreed cases',
          'Other agreed cases: unreviewed; no approved mapping or export']:
    yy=bullet(s,x+25,yy,CW-50,CO[4],25,30)
limit=example(4,['Emotional vs physical reading','Speaker · not negated · current'],190)
checks.append({'card':5,'clearance':limit-yy}); assert yy<=limit-8,(5,yy,limit)
# A separate safety line belongs to the comparison, not an interpretation category.
rect(x+18,y+CH-58,CW-36,41,'#FDECEA',None,7)
poly([(x+33,y+CH-24),(x+45,y+CH-49),(x+57,y+CH-24)],RED)
txt('!',x+45,y+CH-45,19,True,'white','middle')
txt('Chest-pain concern: assess separately',x+CW/2+14,y+CH-51,23,True,RED,'middle')

x=XS[1];y=Y2
icon('people',x+CW/2,y+89,CO[5],.88)
yy=y+197
for s in ['Reviewer: meaning and category','Safety assessment remains separate','Second opinion when needed',
          'Unresolved meaning → request context','Qualified reviewers']:
    yy=bullet(s,x+25,yy,CW-50,CO[5],26,32)
limit=example(5,['Illustrative approved meaning: emotional pain linked to grief',
                 'Chest-pain concern still requires separate assessment'],220)
checks.append({'card':6,'clearance':limit-yy});assert yy<=limit-8,(6,yy,limit)

x=XS[2];y=Y2
icon('lookup',x+CW/2,y+85,CO[6],.75)
yy=y+190
txt('Automated candidates',x+25,yy,27,True,CO[6]);yy+=39
for s in ['From the terminology service, using the approved meaning',
          'Sources: MFOEM · MFOMD · SNOMED CT · LOINC (PHQ-9/GAD-7 items) · OMOP standard vocabularies']:
    yy=bullet(s,x+25,yy,CW-50,CO[6])
txt('Terminologist sign-off',x+25,yy,27,True,CO[6]);yy+=39
for s in ['Exact, close or related match · record a gap · defer',
          'A local concept can remain without an external match.']:
    yy=bullet(s,x+25,yy,CW-50,CO[6])
limit=example(6,['Query: emotional pain linked to grief','External match pending','Related item ≠ questionnaire score'],177)
checks.append({'card':7,'clearance':limit-yy});assert yy<=limit-8,(7,yy,limit)

simple(7,'records',[
    'Versioned decision recorded',
    'SSSOM (versioned): relation · justification · provenance',
    'Suitable validated mappings → OMOP',
    'Custom, non-standard local IDs > 2,000,000,000',
    'Optional export when required'],[
    'Retain reviewed local meaning',
    'No external mapping or export while pending',
    'Mappings are not patient outcomes'],208)

# Main reading arrows. A single wrap connector carries row one into row two.
for yy in [Y1+196,Y2+153]:
    for i in range(3):arrow(XS[i]+CW+3,yy,XS[i+1]-4,yy)
for gap,label in [(0,'Selected for\nreview'),(1,'Approved\nmeaning'),(2,'Record\ndecision')]:
    mid=(XS[gap]+CW+XS[gap+1])/2
    yy=Y2+98
    for s in label.split('\n'):
        txt(s,mid,yy,21,True,NAVY,'middle');yy+=25
wrap_y=1025
path([(XS[3]+CW/2,Y1+CH),(XS[3]+CW/2,wrap_y),(XS[0]+CW/2,wrap_y),(XS[0]+CW/2,Y2-10)],GRAY,6)
arrow(XS[0]+CW/2,Y2-25,XS[0]+CW/2,Y2-2)
rect(707,wrap_y-25,985,51,'#F8FAFD')
txt('For each expression, steps 3–7 repeat',1200,wrap_y-18,29,True,NAVY,'middle')

# Reviewer corrections originate visibly in BOTH reviewer cards, never the record card.
fx=2370
feedback_y=1967
join_y=Y2+CH+22
for reviewer_x in [XS[1]+CW/2,XS[2]+CW/2]:
    path([(reviewer_x,Y2+CH),(reviewer_x,join_y),(1200,join_y)],TEAL,4,[10,8])
    circle(reviewer_x,Y2+CH,5,TEAL)
path([(1200,join_y),(1200,feedback_y),(fx,feedback_y),(fx,Y1+177),(XS[3]+CW+6,Y1+177)],TEAL,4,[10,8])
arrow(XS[3]+CW+20,Y1+177,XS[3]+CW+2,Y1+177,TEAL,4)
rect(70,1942,2260,60,'#E8F6F2','#B8DED2',12,1)
# A clockwise loop icon, drawn as a vector to ensure consistent rendering.
import math
loop_x,loop_y=110,1972
arc=[(loop_x+18*math.cos(math.radians(a)),loop_y+18*math.sin(math.radians(a))) for a in range(30,326,5)]
path(arc,TEAL,3.8)
poly([(loop_x+20,loop_y-3),(loop_x+9,loop_y-6),(loop_x+15,loop_y-17)],TEAL)
txt('New entry and correction proposals (steps 6–7) → curator approval → new dictionary version (no automatic overwrite)',1230,1956,28,True,TEAL,'middle')

# Three principle pills, followed by the exact requested note.
pill_y=2033
pill_w=740
for xx,s in [(46,'Dictionary evidence ≠ model vote'),(830,'Model agreement ≠ correctness'),(1614,'Concept mapping ≠ diagnosis')]:
    rect(xx,pill_y,pill_w,66,NAVY,None,17)
    txt(s,xx+pill_w/2,pill_y+18,29,True,'white','middle')
note='Illustrative example: the context, dictionary entry, model outputs and review are invented; Swahili readings and codes need verification.'
for i,s in enumerate(wrap(note,2220,28)):
    txt(s,W/2,2120+i*35,28,False,DARK,'middle')
txt('No real patient data in consumer chatbots. Proposed design: not yet adopted or implemented.',W/2,2180,26,False,DARK,'middle')

assert 'unaeniuma' not in '\n'.join(all_text)
assert sum(s.count('unaniuma') for s in all_text)==2
assert not any(tag in s for s in all_text for tag in ('R1', 'R2', 'R3', 'JSON'))
assert sum('A local concept can remain' in s for s in all_text)==1
renderPDF.drawToFile(D,str(BASE.with_suffix('.pdf')),title='The Minority Report · FarajaMH',author='FarajaMH workflow design')
svg=renderSVG.drawToString(D)
svg=svg.replace('font-family: Arial-Bold','font-family: Arial; font-weight: bold')
BASE.with_suffix('.svg').write_text(svg)
BASE.with_suffix('.txt').write_text('\n'.join(all_text)+'\n')
BASE.with_name(BASE.name+'-layout-checks.json').write_text(json.dumps(checks,indent=2))
print(json.dumps({'pdf':str(BASE.with_suffix('.pdf')),'svg':str(BASE.with_suffix('.svg')),'checks':checks},indent=2))
