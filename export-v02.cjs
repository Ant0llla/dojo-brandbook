/* Native HTML -> tagged single-page PDFs. No master or bitmap asset is changed. */
const fs=require('fs'),path=require('path'),os=require('os');
function dependency(name){try{return require(name)}catch{return require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',name))}}
const {chromium}=dependency('playwright');
const ROOT=__dirname,TMP=path.join(ROOT,'tmp/pdf-v02'),QA=path.join(ROOT,'qa-v02/pdf');
const read=name=>JSON.parse(fs.readFileSync(path.join(ROOT,name),'utf8').replace(/^\uFEFF/,''));
(async()=>{
 const manifest=read('v02-overview-manifest.json'),raw=manifest.pages||manifest,registry=read('registry.json'),settings=read('tmp/pdf-v02/export-settings.json');
 const base=process.argv.find(x=>x.startsWith('--base='))?.slice(7)||settings.baseURL;
 if(new URL(base).port==='4181')throw new Error('Port 4181 belongs to another project');
 const filter=process.argv.find(x=>x.startsWith('--id='))?.slice(5),pngAll=process.argv.includes('--png-all');
 const selected=(pngAll?registry:raw.map((p,index)=>({...registry.find(b=>b.id===p.id),...p,page:index+1}))).filter(p=>!filter||p.id===filter);
 if(!selected.length)throw new Error('No selected pages');
 fs.mkdirSync(TMP,{recursive:true});fs.mkdirSync(QA,{recursive:true});
 let executable=process.env.DOJO_CHROME_PATH;
 if(!executable&&process.platform==='win32')executable='C:/Program Files/Google/Chrome/Application/chrome.exe';
 const browser=await chromium.launch({headless:true,...(executable?{executablePath:executable}:{})});
 const page=await browser.newPage({viewport:{width:2000,height:2000},deviceScaleFactor:1});
 const audits=[];let errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const b of selected){
  if(!b.source||!b.width||!b.height)throw new Error('Missing overview geometry/source for '+b.id);
  errors=[];await page.emulateMedia({media:'screen'});await page.setViewportSize({width:b.width,height:b.height});
  await page.goto(new URL(b.source+'?frame='+encodeURIComponent(b.id)+'&print=1&pdf=02',base).href,{waitUntil:'networkidle'});
  await page.waitForFunction(id=>window.DOJO_FRAME?.id===id,b.id);
  await page.evaluate(async id=>{await document.fonts.ready;await Promise.all([...document.getElementById(id).querySelectorAll('img')].filter(i=>i.getClientRects().length).map(i=>i.decode().catch(()=>{})));},b.id);
  if(pngAll){
   await page.addStyleTag({content:'*{animation:none!important;transition:none!important;caret-color:transparent!important}'});
   const destination=path.join(ROOT,b.png||('exports/boards/'+b.id+'.png'));fs.mkdirSync(path.dirname(destination),{recursive:true});
   await page.locator('#'+b.id).screenshot({path:destination});
   audits.push({id:b.id,png:path.relative(ROOT,destination),errors:[...errors]});console.log('PNG '+b.id);continue;
  }
  await page.addStyleTag({content:fs.readFileSync(path.join(TMP,'print.css'),'utf8')+`\n@page{size:${b.width}px ${b.height}px;margin:0}@media print{html,body,#frame-stage{width:${b.width}px!important;height:${b.height}px!important}}`});
  await page.evaluate(id=>{const board=document.getElementById(id);for(const a of board.querySelectorAll('[data-target-board]')){a.setAttribute('href','dojo-page://'+a.dataset.targetBoard)}for(const n of board.querySelectorAll(':scope > header span,:scope > header b,.section-head > .index')){if(/^\d{1,3}$/.test(n.textContent.trim()))n.style.visibility='hidden'}},b.id);
  await page.emulateMedia({media:'print'});
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  const audit=await page.evaluate(id=>{const b=document.getElementById(id),rect=b.getBoundingClientRect();return{id,domText:b.innerText,brokenImages:[...b.querySelectorAll('img')].filter(i=>i.getClientRects().length&&getComputedStyle(i).visibility!=='hidden'&&i.getAttribute('src')&&!i.naturalWidth).map(i=>i.getAttribute('src')),headingDots:[...b.querySelectorAll('h1,h2,h3')].map(n=>n.textContent).filter(t=>t.includes('.')),forbiddenLetter:/[Ёё]/.test(b.innerText),geometry:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},links:[...b.querySelectorAll('a[href]')].map(a=>({text:a.innerText,href:a.getAttribute('href')}))}},b.id);
  audit.page=b.page;audit.errors=[...errors];
  if(audit.brokenImages.length||errors.length)throw new Error('Page failed '+b.id+JSON.stringify({images:audit.brokenImages,errors}));
  if(Math.abs(audit.geometry.width-b.width)>1||Math.abs(audit.geometry.height-b.height)>1||Math.abs(audit.geometry.x)>0.01||Math.abs(audit.geometry.y)>0.01)throw new Error('Print geometry differs '+b.id+JSON.stringify(audit.geometry));
  await page.pdf({path:path.join(TMP,b.id+'.pdf'),printBackground:true,tagged:true,outline:false,preferCSSPageSize:true,width:b.width+'px',height:b.height+'px',margin:{top:0,right:0,bottom:0,left:0},scale:1});
  if(process.argv.includes('--screenshots'))await page.screenshot({path:path.join(QA,b.id+'.png')});
  fs.writeFileSync(path.join(TMP,b.id+'.audit.json'),JSON.stringify(audit,null,2));audits.push(audit);
  console.log(`${b.page}/${raw.length} ${b.id}`);
 }
 await browser.close();fs.writeFileSync(path.join(QA,pngAll?'png-audit.json':filter?'export-'+filter+'.json':'export-audit.json'),JSON.stringify(audits,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
