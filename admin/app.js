let token=null,refresh=null,editing=null;
const $=id=>document.getElementById(id);
async function api(path,method='GET',body){
 const send=()=>fetch('/api/v1'+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:body?JSON.stringify(body):undefined});
 let r=await send();
 if(r.status===401&&refresh&&path!='/auth/refresh'){
  const rr=await fetch('/api/v1/auth/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh_token:refresh})});
  if(rr.ok){const s=await rr.json();token=s.access_token;refresh=s.refresh_token;r=await send();}
 }
 if(!r.ok){let e=await r.json();throw Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail));}
 return r.status===204?null:r.json();
}
async function run(fn){try{$('status').textContent='';await fn();}catch(e){$('status').textContent=e.message;}}
async function load(){await loadRequests();const groups=await api('/admin/groups');$('groups').replaceChildren();for(const g of groups){const b=document.createElement('button');b.textContent=g.name+(g.published?' · опубликована':' · скрыта');b.onclick=()=>{editing=g.id;$('name').value=g.name;$('published').checked=g.published;$('active').checked=g.active;$('timezone').value=g.timezone;$('anchor').value=g.anchor_monday;$('week').value=g.anchor_week;$('password').value='';$('title').textContent='Группа '+g.name;};$('groups').append(b);}}
$('login').onsubmit=e=>{e.preventDefault();run(async()=>{const s=await api('/auth/login','POST',{password:$('master').value});token=s.access_token;refresh=s.refresh_token;$('master').value='';$('login').hidden=true;$('panel').hidden=false;await load();});};
$('editor').onsubmit=e=>{e.preventDefault();run(async()=>{const p=$('password').value;if(!editing&&!p)throw Error('Укажите пароль новой группы');await api('/admin/groups'+(editing?'/'+editing:''),editing?'PUT':'POST',{name:$('name').value,password:p||null,published:$('published').checked,active:$('active').checked,timezone:$('timezone').value,anchor_monday:$('anchor').value,anchor_week:$('week').value});$('password').value='';await load();$('status').textContent='Сохранено';});};
$('reset').onclick=()=>{editing=null;$('editor').reset();$('title').textContent='Новая группа';};
$('revoke').onclick=()=>run(async()=>{if(editing){await api('/admin/groups/'+editing+'/revoke','POST');$('status').textContent='Сессии отозваны';}});
$('logout').onclick=()=>run(async()=>{await api('/auth/logout','POST');token=refresh=null;$('panel').hidden=true;$('login').hidden=false;});

let requestCursor=null;
async function loadRequests(append=false){
 const page=await api('/admin/group-requests'+(append&&requestCursor?'?before='+requestCursor:''));
 if(!append)$('requests').replaceChildren();
 for(const r of page.items){
  const card=document.createElement('article');
  const title=document.createElement('strong');title.textContent='Группа '+r.group_number;
  const contact=document.createElement('p');contact.textContent=r.contacts;contact.style.whiteSpace='pre-wrap';
  const status=document.createElement('p');status.textContent=({'pending':'Новая','approved':'Обработана','rejected':'Отклонена'})[r.status]+' · '+new Date(r.created_at).toLocaleDateString('ru-RU');
  card.append(title,contact,status);
  const create=document.createElement('button');create.textContent='Создать группу';create.onclick=()=>{$('reset').click();$('name').value=r.group_number;$('editor').scrollIntoView({behavior:'smooth',block:'center'});};card.append(create);
  for(const [value,label] of [['approved','Отметить обработанной'],['rejected','Отклонить'],['pending','Вернуть в новые']]){
   if(r.status===value)continue;
   const b=document.createElement('button');b.textContent=label;b.onclick=()=>run(async()=>{await api('/admin/group-requests/'+r.id,'PATCH',{status:value});await loadRequests();});card.append(b);
  }
  $('requests').append(card);
 }
 requestCursor=page.next_cursor;$('moreRequests').hidden=!requestCursor;
}
$('moreRequests').onclick=()=>run(()=>loadRequests(true));
