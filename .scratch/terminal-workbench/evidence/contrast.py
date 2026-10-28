import json
from pathlib import Path
themes={'dark':{'panel':'181b22','raised':'222630','text':'e5e7eb','muted':'a7afbe','blue':'80aaff','up':'ff838c','down':'55c99b','selected':'223553'},'light':{'panel':'ffffff','raised':'ffffff','text':'202630','muted':'596579','blue':'245bc5','up':'b42332','down':'14734b','selected':'e8effc'}}
def luminance(s):
 v=[int(s[i:i+2],16)/255 for i in (0,2,4)];v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v];return sum(a*b for a,b in zip(v,[.2126,.7152,.0722]))
result={}
for name,t in themes.items():
 result[name]={}
 for fg in ['text','muted','blue','up','down']:
  for bg in ['panel','raised','selected']:
   a,b=sorted([luminance(t[fg]),luminance(t[bg])]);ratio=(b+.05)/(a+.05);result[name][fg+'/'+bg]=round(ratio,2);assert ratio>=4.5,(name,fg,bg,ratio)
Path('terminal-contrast.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
