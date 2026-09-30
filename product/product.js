(() => {
  'use strict';
  const D=window.DOJO_PRODUCT_DATA;
  const $=(selector,scope=document)=>scope.querySelector(selector);
  const $$=(selector,scope=document)=>[...scope.querySelectorAll(selector)];
  const clone=x=>JSON.parse(JSON.stringify(x));
  const clean=x=>String(x).replace(/ё/g,'е').replace(/Ё/g,'Е');
  function safeSave(key,value){try{localStorage.setItem(key,JSON.stringify(value));return true}catch{return false}}
  function zoneTitle(club,id){return D.configs[club].zones.find(x=>x.id===id)?.title||id}
  function selectSeat(board,seat){
    $$('.p-seat',board).forEach(x=>x.setAttribute('aria-pressed',String(x===seat)));
    const number=$('.p-selected-number',board);if(number)number.textContent=seat.dataset.seat;
    const zone=$('.p-selected-zone',board);if(zone)zone.textContent=zoneTitle(seat.closest('.p-map').dataset.club,seat.dataset.zone);
  }
  $$('.p-map-board').forEach(board=>{
    $$('.p-seat',board).forEach(seat=>seat.addEventListener('click',()=>selectSeat(board,seat)));
    $$('[data-map-zone]',board).forEach(button=>button.addEventListener('click',()=>{
      $$('[data-map-zone]',board).forEach(x=>x.setAttribute('aria-pressed',String(x===button)));
      $$('.p-seat',board).forEach(x=>x.classList.toggle('is-dim',button.dataset.mapZone!=='all'&&x.dataset.zone!==button.dataset.mapZone));
    }));
  });
  // Local editor owns no API session and never writes to the deployed club
  const editor=$('#map-editor'),editorForm=$('#p-editor-form');
  let editorClub='7043',selected='PC-01',history=[];
  const edits={};
  for(const [club,conf]of Object.entries(D.configs)){
    edits[club]=Object.fromEntries(Object.values(conf.hosts).map(h=>[h.title,{x:h.x,y:h.y,zone:h.zone,rotation:0}]));
  }
  const original=clone(edits);
  const sourceSeat=(club,number)=>D.maps.clubs.find(m=>String(m.crmId)===club).seats.find(s=>s.number===number);
  function currentPlan(){return $(`[data-editor-club="${editorClub}"]`,editor)}
  function editorStatus(text,error=false){const el=$('#p-editor-status');$('p',el).textContent=text;el.classList.toggle('p-offline',error)}
  function renderEditorSeat(number){
    const el=$(`[data-seat="${number}"]`,currentPlan());if(!el)return;
    const v=edits[editorClub][number],base=original[editorClub][number],source=sourceSeat(editorClub,number);
    const m=D.maps.clubs.find(m=>String(m.crmId)===editorClub),bounds=D.configs[editorClub].layout.bounds;
    el.style.left=(source.bounds.x/m.plan.width*100+(v.x-base.x)/(bounds.maxX-bounds.minX)*100)+'%';
    el.style.top=(source.bounds.y/m.plan.height*100+(v.y-base.y)/(bounds.maxY-bounds.minY)*100)+'%';
    el.style.transform=`rotate(${v.rotation}deg)`;el.dataset.zone=v.zone;
    el.setAttribute('aria-label',`${number}, ${zoneTitle(editorClub,v.zone)}, редактирование места`);
  }
  function pickEditor(number){
    selected=number;const v=edits[editorClub][number];
    $('#p-editor-selected').textContent=number;
    editorForm.elements.x.value=v.x;editorForm.elements.y.value=v.y;editorForm.elements.rotation.value=v.rotation;
    const zs=editorForm.elements.zone;zs.replaceChildren();
    D.configs[editorClub].zones.forEach(z=>{const o=document.createElement('option');o.value=z.id;o.textContent=clean(z.title);zs.append(o)});zs.value=v.zone;
    $$('[data-seat]',editor).forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.seat===number&&x.closest('[data-editor-club]').dataset.editorClub===editorClub)));
    const bounds=D.configs[editorClub].layout.bounds;
    editorForm.elements.x.min=bounds.minX;editorForm.elements.x.max=bounds.maxX;
    editorForm.elements.y.min=bounds.minY;editorForm.elements.y.max=bounds.maxY;
  }
  function historyState(){ $('#p-editor-undo').disabled=history.length===0 }
  $$('.p-seat',editor).forEach(el=>el.addEventListener('click',()=>pickEditor(el.dataset.seat)));
  $('#p-editor-club').addEventListener('change',event=>{
    editorClub=event.target.value;
    $$('[data-editor-club]',editor).forEach(x=>x.hidden=x.dataset.editorClub!==editorClub);
    pickEditor('PC-01');editorStatus('Выбран клуб · изменения остаются в локальном черновике');
  });
  editorForm.addEventListener('submit',event=>{
    event.preventDefault();if(!editorForm.reportValidity())return;
    const prior=clone(edits[editorClub][selected]);
    const next={x:+editorForm.elements.x.value,y:+editorForm.elements.y.value,rotation:+editorForm.elements.rotation.value,zone:editorForm.elements.zone.value};
    if(JSON.stringify(prior)===JSON.stringify(next)){editorStatus('Изменений нет');return}
    history.push({club:editorClub,seat:selected,prior});edits[editorClub][selected]=next;renderEditorSeat(selected);historyState();
    editorStatus(`${selected} изменен · черновик еще не сохранен`);
  });
  $('#p-editor-undo').addEventListener('click',()=>{
    const change=history.pop();if(!change)return;
    edits[change.club][change.seat]=change.prior;
    if(editorClub!==change.club){$('#p-editor-club').value=change.club;$('#p-editor-club').dispatchEvent(new Event('change'))}
    renderEditorSeat(change.seat);pickEditor(change.seat);historyState();editorStatus('Последнее изменение отменено');
  });
  $('#p-editor-reset').addEventListener('click',()=>{
    Object.assign(edits[editorClub],clone(original[editorClub]));history=history.filter(x=>x.club!==editorClub);
    Object.keys(edits[editorClub]).forEach(renderEditorSeat);pickEditor('PC-01');historyState();editorStatus('Восстановлен исходный план выбранного клуба');
  });
  $('#p-editor-save').addEventListener('click',()=>{
    const ok=safeSave('dojo-zero-map-draft',{savedAt:new Date().toISOString(),edits});
    editorStatus(ok?'Черновик сохранен только в этом браузере · сервер не изменен':'Не удалось сохранить черновик · хранилище браузера недоступно',!ok);
  });
  $('#p-editor-conflict').addEventListener('click',()=>editorStatus('Пример ошибки 409 · план изменен в другом окне · локальный черновик сохранен в памяти, обновите серверную версию перед публикацией',true));
  pickEditor('PC-01');
  // Settings form with source-derived fields and local-only persistence
  $('#p-wheel-settings').addEventListener('submit',event=>{
    event.preventDefault();const form=event.target;if(!form.reportValidity())return;
    for(const level of D.wheel.levelRules){
      const sum=$$(`[data-weight-level="${level.id}"]`).reduce((total,el)=>total+Number(el.value),0);
      if(Math.abs(sum-100)>.001){$('#p-settings-status').textContent=`Сумма весов для уровня «${clean(level.title)}» должна равняться 100% · сейчас ${sum.toFixed(2)}%`;return}
    }
    const value={};for(const el of form.elements)if(el.name)value[el.name]=el.type==='checkbox'?el.checked:Number(el.value);
    $('#p-settings-status').textContent=safeSave('dojo-zero-wheel-settings',value)?'Настройки сохранены только в локальный черновик':'Не удалось сохранить · хранилище браузера недоступно';
  });
  $$('[data-reward-filter]').forEach(button=>button.addEventListener('click',()=>{
    $$('[data-reward-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===button)));
    $$('.p-reward-row').forEach(x=>x.hidden=button.dataset.rewardFilter!=='all'&&x.dataset.category!==button.dataset.rewardFilter);
  }));
  const prizeForm=$('#p-prize-form');let activePrize='bonus_67';const rewardDrafts={};
  function kindFields(){
    const kind=prizeForm.elements.kind.value;
    $$('.p-kind-amount',prizeForm).forEach(x=>x.hidden=!['bonus','coins','steam'].includes(kind));
    $$('.p-kind-discount',prizeForm).forEach(x=>x.hidden=!['discount','full_discount'].includes(kind));
    $('#p-prize-preview').textContent=clean(prizeForm.elements.title.value)||'Название приза';
    $('#p-prize-meta').textContent=prizeForm.elements.category.value+' / '+prizeForm.elements.claimStatus.selectedOptions[0].textContent;
  }
  function loadPrize(id){
    const r=rewardDrafts[id]||D.wheel.rewards.find(x=>x.id===id);if(!r)return;activePrize=id;
    for(const name of ['title','id','category','kind','weight','amount','percent','hours','claimStatus']){
      const el=prizeForm.elements[name];el.value=r[name]??(name==='title'?r.name??'':name==='claimStatus'?'pending_issue':name==='hours'?24:0);
    }
    prizeForm.elements.soon.checked=r.availability==='soon'||r.status==='soon'||r.soon===true;
    prizeForm.elements.requiresSteamReady.checked=!!r.requiresSteamReady;
    $('#p-prize-errors').hidden=true;$('#p-prize-status').textContent='Изменения появятся только в локальном черновике пула';kindFields();
  }
  $$('.p-reward-row').forEach(row=>row.addEventListener('click',()=>{loadPrize(row.dataset.rewardId);location.hash='roulette-prize-editor'}));
  prizeForm.addEventListener('input',kindFields);prizeForm.addEventListener('change',kindFields);
  $('#p-prize-reset').addEventListener('click',()=>loadPrize(activePrize));
  prizeForm.addEventListener('submit',event=>{
    event.preventDefault();const f=prizeForm.elements,errors=[];
    if(!f.title.value.trim())errors.push('Введите название приза');
    if(!/^[a-z0-9_-]+$/.test(f.id.value))errors.push('Идентификатор может содержать только латиницу, цифры, дефис и нижнее подчеркивание');
    if(D.wheel.rewards.some(r=>r.id===f.id.value&&r.id!==activePrize))errors.push('Такой идентификатор уже есть в пуле');
    if(f.weight.value===''||+f.weight.value<0||!Number.isFinite(+f.weight.value))errors.push('Вес должен быть числом от нуля');
    if(['bonus','coins','steam'].includes(f.kind.value)&&(f.amount.value===''||+f.amount.value<0))errors.push('Введите сумму от нуля');
    if(['discount','full_discount'].includes(f.kind.value)){
      if(f.percent.value===''||+f.percent.value<0||+f.percent.value>100)errors.push('Скидка должна быть от 0 до 100 процентов');
      if(f.hours.value===''||+f.hours.value<1)errors.push('Длительность должна быть не меньше часа');
    }
    const box=$('#p-prize-errors');box.replaceChildren();box.hidden=!errors.length;
    if(errors.length){const ul=document.createElement('ul');for(const message of errors){const li=document.createElement('li');li.textContent=message;ul.append(li)}box.append(ul);box.scrollIntoView({block:'center'});return}
    const draft={id:f.id.value,title:clean(f.title.value.trim()),category:f.category.value,kind:f.kind.value,weight:f.soon.checked?0:+f.weight.value,claimStatus:f.claimStatus.value,soon:f.soon.checked,requiresSteamReady:f.requiresSteamReady.checked};
    if(['bonus','coins','steam'].includes(draft.kind))draft.amount=+f.amount.value;
    if(['discount','full_discount'].includes(draft.kind)){draft.percent=+f.percent.value;draft.hours=+f.hours.value}
    rewardDrafts[activePrize]=draft;
    const row=$(`[data-reward-id="${activePrize}"]`);if(row){$('span',row).textContent=draft.title;$('b',row).textContent=draft.weight;row.dataset.category=draft.category;row.children[1].textContent=draft.category;row.children[3].textContent=draft.soon?'Скоро / черновик':'Черновик'}
    const ok=safeSave('dojo-zero-reward-drafts',rewardDrafts);
    $('#p-prize-status').textContent=ok?'Приз применен в локальный черновик · серверный пул не изменен':'Приз изменен в памяти · хранилище браузера недоступно';
  });
  $$('.p-retry').forEach(button=>button.addEventListener('click',()=>{
    const board=button.closest('.p-board'),message=$('.p-retry-message',board);
    message.textContent='Соединение не настроено · локальный предпросмотр';
  }));
  kindFields();
})();
