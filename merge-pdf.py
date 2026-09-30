"""Merge the v02 overview while retaining text, vector artwork and Chrome tags.

Only output PDF image XObjects are resampled/re-encoded. Masters stay untouched.
"""
import argparse,hashlib,io,json,math,re,shutil,zlib,logging
from pathlib import Path
from urllib.parse import urlsplit,unquote,urljoin
from PIL import Image
from pypdf import PdfReader,PdfWriter,Transformation
from pypdf.generic import ArrayObject,BooleanObject,ContentStream,DictionaryObject,EncodedStreamObject,FloatObject,IndirectObject,NameObject,NumberObject,TextStringObject
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pdfplumber
logging.getLogger('pdfminer').setLevel(logging.ERROR)

ROOT=Path(__file__).resolve().parent;TMP=ROOT/'tmp/pdf-v02';QA=ROOT/'qa-v02/pdf'
IDENTITY=(1,0,0,1,0,0)
def matmul(m,n):
 a,b,c,d,e,f=m;A,B,C,D,E,F=n
 return(a*A+b*C,a*B+b*D,c*A+d*C,c*B+d*D,e*A+f*C+E,e*B+f*D+F)
def image_placements(page,pdf):
 result={}
 def walk(content,resources,ctm,depth=0):
  if depth>20:return
  stack=[]
  for args,op in ContentStream(content,pdf).operations:
   if op==b'q':stack.append(ctm)
   elif op==b'Q':ctm=stack.pop() if stack else IDENTITY
   elif op==b'cm':ctm=matmul(tuple(float(v) for v in args),ctm)
   elif op==b'Do':
    xobjects=resources.get('/XObject',{});ref=xobjects.get(args[0])
    if ref is None:continue
    obj=ref.get_object()
    if obj.get('/Subtype')=='/Image':
     key=ref.idnum if hasattr(ref,'idnum') else obj.indirect_reference.idnum
     wh=(math.hypot(ctm[0],ctm[1]),math.hypot(ctm[2],ctm[3]))
     before=result.get(key,(0,0));result[key]=(max(before[0],wh[0]),max(before[1],wh[1]))
    elif obj.get('/Subtype')=='/Form':walk(obj,obj.get('/Resources',resources),matmul(tuple(float(v) for v in obj.get('/Matrix',IDENTITY)),ctm),depth+1)
 walk(page.get_contents(),page['/Resources'],IDENTITY)
 return result
def tree_pairs(tree):
 if tree is None:return []
 tree=tree.get_object();out=[];nums=tree.get('/Nums',[])
 for i in range(0,len(nums),2):out.append((int(nums[i]),nums[i+1]))
 for child in tree.get('/Kids',[]):out.extend(tree_pairs(child))
 return out
def preserve_tags(writer,reader,page,master,children,parent_nums,offset):
 source=reader.root_object.get('/StructTreeRoot')
 if source is None:return offset,False
 copied=source.get_object().clone(writer)
 kids=copied.get('/K',[]);kids=kids if isinstance(kids,ArrayObject) else [kids]
 for kid in kids:
  child=kid.get_object()
  if isinstance(child,DictionaryObject):child[NameObject('/P')]=master
  children.append(kid)
 pairs=tree_pairs(copied.get('/ParentTree'))
 for key,value in pairs:parent_nums.extend([NumberObject(key+offset),value])
 if '/StructParents' in page:page[NameObject('/StructParents')]=NumberObject(int(page['/StructParents'])+offset)
 for a in page.get('/Annots',[]):
  obj=a.get_object()
  if '/StructParent' in obj:obj[NameObject('/StructParent')]=NumberObject(int(obj['/StructParent'])+offset)
 return offset+(max((k for k,_ in pairs),default=-1)+1),True
def footer(width,height,number,site):
 buf=io.BytesIO();c=canvas.Canvas(buf,pagesize=(width,height));c.setFillColorRGB(9/255,26/255,42/255);c.rect(0,0,width,height,fill=1,stroke=0)
 c.setFillColorRGB(233/255,229/255,220/255);c.setFont('DOJOGolos',8)
 c.drawString(18,7,'DOJO / ВЕРСИЯ 02');c.drawRightString(width-18,7,str(number).zfill(2))
 c.setFillColorRGB(101/255,181/255,172/255);c.drawCentredString(width/2,7,'HTML-витрина');c.linkURL(site,(width/2-32,4,width/2+32,17),relative=0,thickness=0)
 c.save();return PdfReader(buf).pages[0]
def compress_images(writer,dpi,quality):
 placements={}
 for page in writer.pages:
  for key,wh in image_placements(page,writer).items():
   prior=placements.get(key,(0,0));placements[key]=(max(wh[0],prior[0]),max(wh[1],prior[1]))
 images={}
 for page in writer.pages:
  for image in page.images:
   if image.indirect_reference is not None:images.setdefault(image.indirect_reference.idnum,image)
 report=[]
 for key,entry in images.items():
  old=entry.indirect_reference.get_object();img=entry.image.copy();ow,oh=img.size
  if ow<=32 and oh<=32:continue
  bound=placements.get(key)
  if bound:
   wanted=(max(1,math.ceil(bound[0]/72*dpi)),max(1,math.ceil(bound[1]/72*dpi)))
   scale=min(1,max(wanted[0]/ow,wanted[1]/oh))
  else:scale=1
  size=(max(1,math.ceil(ow*scale)),max(1,math.ceil(oh*scale)))
  if size!=(ow,oh):img=img.resize(size,Image.Resampling.LANCZOS)
  alpha=img.getchannel('A') if 'A' in img.getbands() else None
  rgb=img.convert('RGB');jpeg=io.BytesIO();rgb.save(jpeg,'JPEG',quality=quality,optimize=True,subsampling=0)
  raw=jpeg.getvalue();stream=EncodedStreamObject();stream._data=raw
  stream.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),NameObject('/Width'):NumberObject(size[0]),NameObject('/Height'):NumberObject(size[1]),NameObject('/ColorSpace'):NameObject('/DeviceRGB'),NameObject('/BitsPerComponent'):NumberObject(8),NameObject('/Filter'):NameObject('/DCTDecode')})
  alpha_bytes=0
  if alpha is not None and alpha.getextrema()!=(255,255):
   mask=EncodedStreamObject();mask._data=zlib.compress(alpha.tobytes(),9);alpha_bytes=len(mask._data)
   mask.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),NameObject('/Width'):NumberObject(size[0]),NameObject('/Height'):NumberObject(size[1]),NameObject('/ColorSpace'):NameObject('/DeviceGray'),NameObject('/BitsPerComponent'):NumberObject(8),NameObject('/Filter'):NameObject('/FlateDecode')})
   stream[NameObject('/SMask')]=writer._add_object(mask)
  stream.indirect_reference=entry.indirect_reference;writer._objects[key-1]=stream
  report.append({'xref':key,'sourcePixels':[ow,oh],'exportPixels':list(size),'placementPt':list(bound) if bound else None,'jpegBytes':len(raw),'alphaBytes':alpha_bytes,'quality':quality})
 return report
def resolve_links(writer,pages,site):
 indices={p['id']:i for i,p in enumerate(pages)};report=[]
 for index,page in enumerate(writer.pages):
  for ref in page.get('/Annots',[]):
   a=ref.get_object();action=a.get('/A')
   if not action or action.get('/S')!='/URI':continue
   uri=str(action.get('/URI',''));u=urlsplit(uri)
   if u.scheme=='dojo-page':
    target=unquote((u.netloc+u.path).strip('/'))
    if target not in indices:raise ValueError('TOC target not present: '+target)
    a[NameObject('/A')]=DictionaryObject({NameObject('/S'):NameObject('/GoTo'),NameObject('/D'):ArrayObject([writer.pages[indices[target]].indirect_reference,NameObject('/Fit')])})
    report.append({'page':index+1,'targetPage':indices[target]+1,'target':target,'kind':'GoTo'})
   else:
    if u.hostname in {'127.0.0.1','localhost'}:uri=urljoin(site,u.path.lstrip('/')+('?' +u.query if u.query else '')+('#'+u.fragment if u.fragment else ''))
    elif u.scheme=='file':uri=site
    action[NameObject('/URI')]=TextStringObject(uri);report.append({'page':index+1,'url':uri,'kind':'URI'})
 return report
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--legacy-alias',action='store_true');args=parser.parse_args()
 QA.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((ROOT/'v02-overview-manifest.json').read_text('utf-8-sig'));pages=manifest['pages'] if isinstance(manifest,dict) else manifest
 settings=json.loads((TMP/'export-settings.json').read_text('utf-8'));registry={p['id']:p for p in json.loads((ROOT/'registry.json').read_text('utf-8-sig'))}
 pages=[{**registry.get(p['id'],{}),**p} for p in pages]
 if not 40<=len(pages)<=45:raise ValueError('Expected 40-45 overview pages')
 if settings['manifestSHA256']!=hashlib.sha256((ROOT/'v02-overview-manifest.json').read_bytes()).hexdigest():raise ValueError('Manifest changed; run prepare again')
 pdfmetrics.registerFont(TTFont('DOJOGolos',str(ROOT/'assets/golos-text.ttf')))
 w=PdfWriter();tag_root=DictionaryObject({NameObject('/Type'):NameObject('/StructTreeRoot')});tag_ref=w._add_object(tag_root);tag_children=ArrayObject();parent_nums=ArrayObject();offset=0;tagged=[]
 groups={};subgroups={};page_records=[]
 for ix,b in enumerate(pages):
  r=PdfReader(TMP/(b['id']+'.pdf'))
  if len(r.pages)!=1:raise ValueError(b['id']+' does not contain exactly one page')
  p=w.add_page(r.pages[0]);offset,is_tagged=preserve_tags(w,r,p,tag_ref,tag_children,parent_nums,offset);tagged.append(is_tagged)
  width=settings['landscapeWidthPt'] if b['width']>b['height'] else settings['portraitWidthPt'];scale=width/float(p.mediabox.width)
  p.scale_by(scale);height=float(p.mediabox.height);foot=settings['footerHeightPt'];p.add_transformation(Transformation().translate(0,foot))
  for ref in p.get('/Annots',[]):
   a=ref.get_object()
   if '/Rect' in a:
    rect=a['/Rect'];a[NameObject('/Rect')]=ArrayObject([FloatObject(float(rect[0])),FloatObject(float(rect[1])+foot),FloatObject(float(rect[2])),FloatObject(float(rect[3])+foot)])
  p.mediabox.upper_right=(width,height+foot);p.cropbox.upper_right=(width,height+foot)
  f=footer(width,foot,ix+1,settings['publicURL']);p.merge_page(f)
  section=b.get('section',b.get('group','DOJO'));subsection=b.get('subsection')
  if section not in groups:groups[section]=w.add_outline_item(section,ix)
  parent=groups[section]
  if subsection and subsection!=b['title']:
   key=(section,subsection)
   if key not in subgroups:subgroups[key]=w.add_outline_item(subsection,ix,parent=parent)
   parent=subgroups[key]
  w.add_outline_item(b['title'],ix,parent=parent)
  page_records.append({'page':ix+1,'id':b['id'],'title':b['title'],'section':section,'subsection':subsection,'widthPt':width,'heightPt':height+foot,'taggedSource':is_tagged})
 tag_root[NameObject('/K')]=tag_children;tag_root[NameObject('/ParentTree')]=w._add_object(DictionaryObject({NameObject('/Nums'):parent_nums}));tag_root[NameObject('/ParentTreeNextKey')]=NumberObject(offset)
 w.root_object[NameObject('/StructTreeRoot')]=tag_ref;w.root_object[NameObject('/MarkInfo')]=DictionaryObject({NameObject('/Marked'):BooleanObject(True)});w.root_object[NameObject('/Lang')]=TextStringObject('ru-RU');w.root_object[NameObject('/PageMode')]=NameObject('/UseOutlines')
 image_report=compress_images(w,settings['dpi'],settings['jpegQuality']);links=resolve_links(w,pages,settings['publicURL'])
 for p in w.pages:p.compress_content_streams()
 w.add_metadata({'/Title':'DOJO — Брендбук / Версия 02','/Author':'DOJO','/Subject':'Обзор бренд-системы и продуктового UI kit / октябрь 2026','/Keywords':'DOJO, версия 02, брендбук, Tektur, SmartShell','/Producer':'DOJO v02 native HTML / pypdf'})
 # pypdf 6.10 marks old references before redirecting duplicates. Doing orphan
 # removal in that same pass can delete the newly referenced canonical SMask.
 w.compress_identical_objects(remove_duplicates=True,remove_unreferenced=False)
 w.compress_identical_objects(remove_duplicates=False,remove_unreferenced=True)
 dangling=[]
 def check_refs(obj,owner):
  if isinstance(obj,IndirectObject):
   if obj.pdf is not w or obj.idnum>len(w._objects) or w._objects[obj.idnum-1] is None:dangling.append({'owner':owner,'target':obj.idnum})
  elif isinstance(obj,dict):
   for value in obj.values():check_refs(value,owner)
  elif isinstance(obj,(list,ArrayObject)):
   for value in obj:check_refs(value,owner)
 for ix,obj in enumerate(w._objects):
  if obj is not None:check_refs(obj,ix+1)
 if dangling:raise ValueError('Dangling PDF references: '+json.dumps(dangling[:20]))
 output=ROOT/'DOJO-Brandbook-v02.pdf';staging=ROOT/'tmp/pdf-v02/assembled-v02.pdf';w.write(staging);staging.replace(output)
 read=PdfReader(output)
 with pdfplumber.open(output) as document:extracted=[p.extract_text(x_tolerance=2,y_tolerance=3) or '' for p in document.pages]
 text_checks=[]
 for b,text in zip(pages,extracted):
  dom=json.loads((TMP/(b['id']+'.audit.json')).read_text('utf-8'))['domText'];probes=[]
  for phrase in ['Увидимся в клубе','Свой характер','Один знак','Разный масштаб','Твое место','Права и ограничения']:
   if phrase.casefold() in dom.casefold():probes.append({'phrase':phrase,'found':' '.join(phrase.split()).casefold() in ' '.join(text.split()).casefold()})
  text_checks.append({'id':b['id'],'extractableCharacters':len(text),'probes':probes,'forbiddenLocalURL':bool(re.search(r'file:///|C:\\\\Users|127\.0\.0\.1',text))})
 errors=[]
 if output.stat().st_size>25_000_000:errors.append('PDF exceeds 25 MB')
 if not all(tagged):errors.append('Missing tagged source pages')
 if any(not p['found'] for c in text_checks for p in c['probes']):errors.append('One or more text spacing probes failed')
 if any(c['extractableCharacters']<35 for c in text_checks):errors.append('Unexpectedly empty text page')
 for i,t in enumerate(extracted):
  if 'ВЕРСИЯ 02' not in t or str(i+1).zfill(2) not in t:errors.append('Missing version/page footer '+str(i+1))
 if not any(x['kind']=='GoTo' for x in links):errors.append('No internal TOC links')
 if any(x['forbiddenLocalURL'] for x in text_checks):errors.append('Local URL leaked into text')
 report={'version':'02','pageCount':len(read.pages),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'taggedSourcePages':sum(tagged),'bookmarksExpected':len(pages)+len(groups)+len(subgroups),'danglingReferences':dangling,'pages':page_records,'images':image_report,'links':links,'textChecks':text_checks,'errors':errors}
 (QA/'pdf-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8');(QA/'extracted-text.txt').write_text('\n\f\n'.join(extracted),'utf-8')
 if errors:raise RuntimeError('; '.join(errors))
 if args.legacy_alias:shutil.copyfile(output,ROOT/'DOJO-Brandbook.pdf')
 print(json.dumps({k:report[k] for k in ('version','pageCount','bytes','sha256','taggedSourcePages','bookmarksExpected','errors')},ensure_ascii=False))
if __name__=='__main__':main()
