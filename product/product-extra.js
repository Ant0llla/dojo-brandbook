(()=>{
'use strict';
const catalog=window.DOJO_EXTRA_CATALOG;
for(const board of document.querySelectorAll('.x-shop-map')){
 const cid=board.querySelector('.p-map').dataset.club;
 const sheet=board.querySelector('.x-product-sheet');
 let trigger;
 function close(){sheet.hidden=true;if(trigger)trigger.focus()}
 for(const seat of board.querySelectorAll('.x-seat')){
  seat.addEventListener('click',()=>{
   board.querySelectorAll('.x-seat').forEach(x=>x.setAttribute('aria-pressed',String(x===seat)));
   const z=window.DOJO_PRODUCT_DATA.configs[cid].zones.find(z=>z.id===seat.dataset.zone);
   board.querySelector('.x-chosen-seat').textContent=seat.dataset.seat+' / '+(z?.title||seat.dataset.zone);
  })
 }
 for(const b of board.querySelectorAll('[data-category-filter]'))b.addEventListener('click',()=>{
  board.querySelectorAll('[data-category-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
  board.querySelectorAll('.x-product-card').forEach(x=>x.hidden=b.dataset.categoryFilter!=='all'&&x.dataset.category!==b.dataset.categoryFilter);
 });
 for(const b of board.querySelectorAll('[data-product]'))b.addEventListener('click',()=>{
  const p=catalog[cid].find(p=>p.key===b.dataset.product);trigger=b;
  sheet.querySelector('h2').textContent=p.title;
  sheet.querySelector('img').src='assets/'+p.file;sheet.querySelector('img').alt=p.title+' / '+p.size;
  sheet.querySelector('.x-sheet-category').textContent=p.category;sheet.querySelector('.x-sheet-size').textContent=p.size;
  sheet.querySelector('.x-sheet-price').textContent=p.price+' ₽';sheet.hidden=false;sheet.querySelector('.x-close').focus();
 });
 sheet.querySelector('.x-close').addEventListener('click',close);
 board.addEventListener('keydown',event=>{if(event.key==='Escape'&&!sheet.hidden){event.preventDefault();close()}});
}
const select=document.querySelector('#x-fixture-day'),tv=document.querySelector('#signage-connected');
select.addEventListener('change',()=>{
 const day=select.value,c=window.DOJO_PRODUCT_DATA.prices.clubs[1];
 tv.querySelectorAll('[data-current-rate]').forEach(n=>{n.innerHTML=c.zones[Number(n.dataset.zoneIndex)][day][1]+'<small>₽ / час</small>'});
 tv.querySelector('.x-tv-console strong').textContent=c.ps5[day][1]+' ₽';
 tv.querySelector('.x-tv-clock span').textContent=day==='weekday'?'Вторник / 29 сентября':'Суббота / 3 октября';
 tv.previousElementSibling.querySelector('.x-fixture-caption').textContent='ДЕМО ДАННЫХ · не реальная занятость · '+(day==='weekday'?'29.09.2026':'03.10.2026')+' 18:30 MSK · тарифы из снимка сайта, статусы мест синтетические';
});
tv.querySelector('.x-free-count').textContent=tv.querySelectorAll('[data-state="free"]').length;
})();
