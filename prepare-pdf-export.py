"""Generate the v02 print contract without rewriting HTML, CSS or JS masters."""
import argparse,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'tmp/pdf-v02'
CSS='''
*{animation:none!important;transition:none!important;caret-color:transparent!important;
  letter-spacing:0!important;word-spacing:0!important;font-kerning:none!important;
  font-variant-ligatures:none!important;text-rendering:optimizeLegibility!important}
#frame-stage footer{visibility:hidden!important}
@media print{
 html,body{margin:0!important;padding:0!important;overflow:hidden!important}
 #frame-stage{position:absolute!important;left:0!important;top:0!important;right:auto!important;bottom:auto!important;margin:0!important;padding:0!important;transform:none!important;zoom:1!important}
 #frame-stage>*{left:0!important;top:0!important;margin:0!important;transform:none!important;zoom:1!important}
}
'''.strip()+'\n'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://127.0.0.1:4192/');args=parser.parse_args()
    manifest=json.loads((ROOT/'v02-overview-manifest.json').read_text('utf-8-sig'))
    pages=manifest['pages'] if isinstance(manifest,dict) else manifest
    ids=[p['id'] for p in pages]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate overview page ID')
    if not 40<=len(ids)<=45:raise ValueError('Overview must contain 40 to 45 pages')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'print.css').write_text(CSS,'utf-8')
    settings={'version':'02','baseURL':args.base.rstrip('/')+'/','dpi':150,'jpegQuality':85,'footerHeightPt':22,'portraitWidthPt':595.2756,'landscapeWidthPt':841.8898,'publicURL':manifest.get('publicURL','https://ant0llla.github.io/dojo-brandbook/') if isinstance(manifest,dict) else 'https://ant0llla.github.io/dojo-brandbook/','pageCount':len(pages),'manifestSHA256':hashlib.sha256((ROOT/'v02-overview-manifest.json').read_bytes()).hexdigest(),'mastersModified':False}
    (OUT/'export-settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'pages':len(pages),'version':'02','baseURL':settings['baseURL'],'printCSS':str((OUT/'print.css').relative_to(ROOT))},ensure_ascii=False))
if __name__=='__main__':main()
