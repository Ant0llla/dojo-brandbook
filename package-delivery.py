"""Build the complete v02 handoff without QA caches, private paths or .pen files.

Usage: python package-delivery.py --check | --build
The overview PDF is concise; the complete HTML catalog stays in this package.
"""
from pathlib import Path,PurePosixPath
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import argparse,hashlib,html,json,re,sys,zipfile
from PIL import Image
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'DOJO-Delivery-v02.zip'
ALLOWED={'.html','.css','.js','.json','.png','.jpg','.jpeg','.webp','.svg','.gif','.ico','.ttf','.otf','.woff','.woff2','.pdf','.csv','.txt','.md','.mp4','.webm'}
PIPELINE={'prepare-pdf-export.py','export-v02.cjs','merge-pdf.py','package-delivery.py'}
EXCLUDED_NAMES={'packaging-check.json','asset-inventory.json','pencil-index.json','DELIVERY-MANIFEST.json','MANIFEST.sha256','v02-change-log.private.json'}
def digest(data):return hashlib.sha256(data).hexdigest()
def jread(path):return json.loads(path.read_text('utf-8-sig'))
def blocked(rel):
 p=PurePosixPath(rel)
 if p.suffix.lower()=='.pen':return True
 if any(x in {'.git','.codex','.agents','tmp','node_modules','__pycache__','.build-deps'} or x.lower().startswith('qa') or x.lower().endswith('-qa') for x in p.parts):return True
 if any(x.lower() in {'references','walls-research'} for x in p.parts):return True
 if rel.startswith(('cards/art/','brand/qa-v02-additions/')):return True
 if p.name in EXCLUDED_NAMES or p.name.endswith(('.zip','.sha256','.log')):return True
 if p.suffix.lower()=='.pdf' and p.name not in {'DOJO-Brandbook-v02.pdf','DOJO-Brandbook.pdf'}:return True
 return p.suffix.lower() not in ALLOWED and rel not in PIPELINE and rel!='.nojekyll'
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.refs=[];self.base=None;self.styles=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='base':self.base=a.get('href');return
  for k in ['src','href','poster','xlink:href']:
   if a.get(k):self.refs.append((a[k],tag=='a'))
  if a.get('srcset'):self.refs.extend((s.strip().split()[0],False) for s in a['srcset'].split(',') if s.strip())
  if a.get('style'):self.styles.append(a['style'])
 def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)
def css_refs(text):return re.findall(r'url\(\s*[\'"]?([^\)\'\"]+)[\'"]?\s*\)',text,re.I)+re.findall(r'@import\s+[\'"]([^\'\"]+)[\'"]',text,re.I)
def dependencies(files):
 errors=[];external=[]
 def ref(value,owner,base=None,is_link=False):
  value=html.unescape(value.strip())
  if not value or value.startswith(('#','data:','blob:','mailto:','tel:','javascript:','dojo-page:')) or '${' in value:return
  url=urlsplit(value)
  if url.scheme or url.netloc:
   if url.scheme=='file' or re.match(r'^[A-Za-z]:',value):errors.append({'file':owner,'kind':'local URI'})
   elif not is_link and url.scheme not in {'http','https'}:errors.append({'file':owner,'kind':'unsupported runtime URI'})
   elif not is_link:external.append({'file':owner,'url':value})
   return
  part=unquote(url.path)
  if not part:return
  parent=ROOT/PurePosixPath(owner).parent
  if base:parent=(parent/unquote(urlsplit(base).path)).resolve()
  target=(ROOT/part.lstrip('/')).resolve() if part.startswith('/') else (parent/part).resolve()
  if target.is_dir():target=target/'index.html'
  try:rel=target.relative_to(ROOT).as_posix()
  except ValueError:errors.append({'file':owner,'kind':'dependency outside package'});return
  if rel not in files:errors.append({'file':owner,'dependency':rel,'kind':'missing link' if is_link else 'missing asset'})
 for rel,p in files.items():
  if p.suffix.lower() in {'.html','.svg'}:
   parser=Parser();parser.feed(p.read_text('utf-8-sig'))
   for value,is_link in parser.refs:ref(value,rel,parser.base,is_link)
   for style in parser.styles:
    for value in css_refs(style):ref(value,rel,parser.base)
  elif p.suffix.lower()=='.css':
   for value in css_refs(p.read_text('utf-8-sig')):ref(value,rel)
 return errors,external
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
 files={p.relative_to(ROOT).as_posix():p for p in ROOT.rglob('*') if p.is_file() and not blocked(p.relative_to(ROOT).as_posix())}
 errors=[];registry=jread(ROOT/'registry.json');overview=jread(ROOT/'v02-overview-manifest.json');cards=jread(ROOT/'cards/card-manifest.json')
 pages=overview['pages'];pdf=ROOT/'DOJO-Brandbook-v02.pdf'
 for name in ['index.html','registry.json','registry.js','v02-overview-manifest.json','DOJO-Brandbook-v02.pdf','DELIVERY.txt','LICENSES.md','ASSET-SOURCES.json','cards/cards.html','cards/catalog.html','cards/templates.html','cards/card-manifest.json']:
  if name not in files:errors.append('Missing required deliverable '+name)
 if cards.get('count')!=81 or len(cards['cards'])!=81:errors.append('Expected exactly 81 original cards')
 if not 40<=len(pages)<=45:errors.append('Overview page count outside 40-45')
 if pdf.is_file():
  reader=PdfReader(pdf)
  if len(reader.pages)!=len(pages):errors.append('PDF and overview manifest disagree')
  if pdf.stat().st_size>25_000_000:errors.append('PDF exceeds 25 MB')
  if '/StructTreeRoot' not in reader.root_object:errors.append('PDF structure tags missing')
  legacy=ROOT/'DOJO-Brandbook.pdf'
  if legacy.is_file() and digest(legacy.read_bytes())!=digest(pdf.read_bytes()):errors.append('Legacy PDF alias is stale; merge with --legacy-alias')
  if not reader.outline:errors.append('PDF bookmarks missing')
  internal_links=sum(1 for p in reader.pages for a in p.get('/Annots',[]) if a.get_object().get('/A',{}).get('/S')=='/GoTo')
  if internal_links<40:errors.append('PDF TOC links missing')
  for ix,page in enumerate(reader.pages):
   text=page.extract_text() or ''
   if 'ВЕРСИЯ 02' not in text:errors.append('Missing PDF version footer '+str(ix+1))
  audit=ROOT/'qa-v02/pdf/pdf-audit.json'
  if audit.is_file() and (jread(audit).get('errors') or jread(audit).get('sha256')!=digest(pdf.read_bytes())):errors.append('Existing PDF audit failed or is stale')
 for board in registry:
  for key in ['source','png']:
   if board.get(key) not in files:errors.append('Missing full-catalog '+key+' '+board['id'])
  if board.get('webSource') and board['webSource'] not in files:errors.append('Missing web frame '+board['id'])
 card_checks=[]
 for card in cards['cards']:
  p=ROOT/'cards'/card['file']
  if not p.is_file():errors.append('Missing card '+card['key']);continue
  with Image.open(p) as img:
   alpha=img.convert('RGBA').getchannel('A').getextrema();size=img.size
  ok=size==(600,900) and alpha[0]==0 and p.stat().st_size<=250000
  if not ok:errors.append('Card export gate failed '+card['key'])
  card_checks.append({'key':card['key'],'bytes':p.stat().st_size,'size':size,'transparent':alpha[0]==0,'sha256':digest(p.read_bytes())})
 # Preserve the price/product snapshot, independently of any presentation changes.
 snapshot={}
 source_zip=ROOT.parent/'dojo-zero/DOJO-Delivery.zip'
 if source_zip.is_file():
  with zipfile.ZipFile(source_zip) as z:before=json.loads(z.read('DOJO-Delivery/product/product-data.js').decode('utf-8').split('=',1)[1].strip().rstrip(';'))
  after=json.loads((ROOT/'product/product-data.js').read_text('utf-8').split('=',1)[1].strip().rstrip(';'))
  for key in ['prices','goods']:
   snapshot[key]=before[key]==after[key]
   if not snapshot[key]:errors.append('Original '+key+' snapshot changed')
 dependencies_errors,external=dependencies(files)
 errors.extend(json.dumps(x,ensure_ascii=False) for x in dependencies_errors)
 if external:errors.append('External runtime assets must be local: '+json.dumps(external,ensure_ascii=False))
 sensitive=re.compile(r'[A-Za-z]:[\\/]+Users[\\/]|file:///|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sourceMessageId|mail-under-dojo',re.I)
 privacy=[]
 for rel,p in files.items():
  if p.suffix.lower() in {'.html','.css','.js','.json','.svg','.txt','.md','.csv'} and sensitive.search(p.read_text('utf-8-sig')):privacy.append(rel)
 if privacy:errors.append('Private data/path audit failed in '+', '.join(privacy))
 report={'version':'02','files':len(files),'bytesUncompressed':sum(p.stat().st_size for p in files.values()),'fullCatalogBoards':len(registry),'overviewPages':len(pages),'cards':len(card_checks),'snapshotUnchanged':snapshot,'privacyFindings':privacy,'errors':errors}
 (ROOT/'packaging-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
 if errors:
  print(json.dumps(report,ensure_ascii=False,indent=2));return 1
 if args.build:
  entries=[{'file':rel,'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())} for rel,p in sorted(files.items())]
  package_manifest=json.dumps({'version':'02','overviewPDF':'DOJO-Brandbook-v02.pdf','overviewPages':len(pages),'fullCatalogBoards':len(registry),'cards':81,'snapshot':'2026-09-29','files':entries},ensure_ascii=False,indent=2).encode('utf-8')
  hashes=[e['sha256']+'  '+e['file'] for e in entries]+[digest(package_manifest)+'  DELIVERY-MANIFEST.json']
  temp=OUT.with_suffix('.zip.part')
  with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for rel,p in sorted(files.items()):z.write(p,'DOJO-Delivery-v02/'+rel)
   z.writestr('DOJO-Delivery-v02/DELIVERY-MANIFEST.json',package_manifest)
   z.writestr('DOJO-Delivery-v02/MANIFEST.sha256','\n'.join(hashes)+'\n')
  with zipfile.ZipFile(temp) as z:
   if z.testzip() is not None:raise ValueError('Archive CRC check failed')
   for entry in entries:
    if digest(z.read('DOJO-Delivery-v02/'+entry['file']))!=entry['sha256']:raise ValueError('Archive SHA mismatch '+entry['file'])
  temp.replace(OUT);OUT.with_suffix('.zip.sha256').write_text(digest(OUT.read_bytes())+'  '+OUT.name+'\n','utf-8')
  report['archive']={'file':OUT.name,'bytes':OUT.stat().st_size,'sha256':digest(OUT.read_bytes()),'crcAndEveryMemberSHA256':'passed'}
  (ROOT/'packaging-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':
 if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
 raise SystemExit(main())
