'use strict';
let boot = null, S = null, screen = 'home', authMode = 'login', selectedSlot = '', slots = [], currentBooking = {}, timeEditor = { barber_id:'', day:'' }, toastTimer, confirmedBooking=null;
const $=s=>document.querySelector(s);
const e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>(Number(v||0)/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const dateText=v=>v?String(v).split('-').reverse().join('/'):'—';
const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Bahia',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const initials=v=>String(v||'DG').split(' ').slice(0,2).map(x=>x[0]).join('').toUpperCase();
const avatar=(user,extra='')=>`<div class="avatar ${e(extra)}">${user?.avatar_url?`<img src="${e(user.avatar_url)}" alt="Foto de ${e(user.name)}" loading="lazy">`:e(initials(user?.name))}</div>`;
const ADMIN=()=>S?.user&&['owner','admin'].includes(S.user.role);
const ROLE=()=>S?.user?.role||'guest';
const show=key=>ADMIN()||(!S?.config?.visibility||S.config.visibility[key]?.includes(ROLE()));
const logo=()=>e(S?.config?.logo_url||'/static/logo.jpg');
function brandSettings(){if(!S?.config)return;document.documentElement.style.setProperty('--bg',S.config.background);document.documentElement.style.setProperty('--gold',S.config.accent);document.documentElement.style.setProperty('--gold2',S.config.accent);$('#brand-name').textContent=S.config.site_name.toUpperCase();}

const BARBER=()=>S?.user?.role==='barber';
const pill=(v)=>({scheduled:'<span class="chip blue">Agendado</span>',cancelled:'<span class="chip red">Cancelado</span>',completed:'<span class="chip green">Concluído</span>',pending:'<span class="chip">Pendente</span>',active:'<span class="chip green">Ativo</span>',rejected:'<span class="chip red">Rejeitado</span>',owner:'<span class="chip green">Principal</span>',admin:'<span class="chip blue">Administrador</span>',barber:'<span class="chip">Barbeiro</span>',client:'<span class="chip">Cliente</span>'}[v]||`<span class="chip">${e(v)}</span>`);
function toast(msg,error=false){const el=$('#toast');el.textContent=msg;el.className='toast'+(error?' error':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.className='toast hidden',4600)}
async function api(path,options={}){
  let headers={'Content-Type':'application/json'};
  if(options.method&&options.method!=='GET') headers['X-CSRF-Token']=boot?.csrf||'';
  let response=await fetch(path,{credentials:'same-origin',...options,headers:{...headers,...options.headers}});
  let json=await response.json().catch(()=>({error:'Resposta inválida do servidor.'}));
  if(!response.ok)throw Error(json.error||'Não foi possível concluir a operação.');
  return json;
}
async function refresh(){boot=await api('/api/bootstrap');if(boot.installed)S=await api('/api/state');else S=null;render()}
function openModal(content){$('#modal-content').innerHTML=content;$('#modal').classList.remove('hidden')}
function closeModal(){$('#modal').classList.add('hidden');$('#modal-content').innerHTML=''}
const field=(label,name,value='',type='text',opt='')=>`<div class="field"><label>${e(label)}</label><input name="${e(name)}" type="${e(type)}" value="${e(value)}" ${opt}></div>`;
const check=(label,name,val=false)=>`<div class="field check"><input type="checkbox" name="${e(name)}" id="ck_${e(name)}" ${val?'checked':''}><label for="ck_${e(name)}">${e(label)}</label></div>`;
const select=(label,name,options,val='')=>`<div class="field"><label>${e(label)}</label><select name="${e(name)}">${options.map(x=>`<option value="${e(x[0])}" ${String(x[0])===String(val)?'selected':''}>${e(x[1])}</option>`).join('')}</select></div>`;
const form=(endpoint,content,submit='Salvar',close=true)=>`<form data-api="${e(endpoint)}" class="stack">${content}<div class="form-footer">${close?'<button type="button" class="btn alt" data-close>Voltar</button>':''}<button type="submit" class="btn">${e(submit)} →</button></div></form>`;
function go(next){
  $('#menu-panel')?.classList.add('hidden');
  $('#menu-toggle')?.setAttribute('aria-expanded','false');
  if(next==='booking'&&!show('booking')){toast('Agendamento indisponível para este perfil.',true);return;}
  if(['dashboard','team','clients','catalog','plans-admin','promos-admin','hours','appointments','account','settings'].includes(next)&&!S?.user){authMode='login';next='auth'}
  if(['dashboard','team','clients','catalog','plans-admin','promos-admin','hours','settings'].includes(next)&&!ADMIN() && !(next==='hours'&&BARBER())){toast('Área restrita à equipe.',true);return}
  screen=next;render();
  if(next!=='confirmation')history.replaceState(null,'','#'+next);
  window.scrollTo({top:0,behavior:'smooth'});
}
function navLinks(){
  if(!boot?.installed)return [];
  if(ADMIN())return [['dashboard','Painel','▦'],['appointments','Agenda','▣'],['team','Equipe','♟'],['clients','Clientes','♙'],['catalog','Serviços','✂'],['plans-admin','Planos','◈'],['promos-admin','Promoções','✦'],['hours','Horários','◷'],['settings','Personalizar','⚙']];
  if(BARBER())return [['home','Início','⌂'],['appointments','Minha agenda','▣'],['hours','Horários','◷'],['account','Meu perfil','◉']];
  if(S?.user)return [['home','Início','⌂'],['booking','Agendar','◷'],['appointments','Meus agendamentos','▣'],['account','Meu perfil','◉']];
  return [['home','Início','⌂'],['booking','Agendar','◷'],['home#services','Serviços','✂'],['home#plans','Planos','◈']];
}
function renderNav(){
  let links=navLinks();
  $('#desktop-nav').innerHTML=(!S?.user?[]:links).map(([k,l])=>`<button class="navbtn ${screen===k?'active':''}" data-go="${k}">${e(l)}</button>`).join('');
  $('#top-actions').className='top-actions';
  $('#top-actions').innerHTML=`${S?.user?`<button data-go="account" class="btn alt small"><span class="top-text">${e(S.user.name.split(' ')[0])}</span> ${avatar(S.user,'avatar-top')}</button>`:''}<button class="menu-button" id="menu-toggle" aria-expanded="false" aria-controls="menu-panel" data-action="menu" aria-label="Abrir menu">☰</button>`;
  const items=S?.user?links.concat([['account','Minha conta'],['logout','Sair']]):[['home','Página inicial'],['booking','Agendamento'],['login','Login'],['register','Novo cadastro'],['apply-barber','Sou barbeiro']];
  $('#menu-panel').innerHTML=items.map(([key,label])=>`<button data-menu="${e(key)}">${e(label)}</button>`).join('');
  let mobile=S?.user?links.slice(0,5):[];if(ADMIN())mobile=[['dashboard','Painel','▦'],['appointments','Agenda','▣'],['team','Equipe','♟'],['catalog','Serviços','✂'],['account','Conta','◉']];
  $('#mobile-dock').innerHTML=mobile.map(([k,l,ico])=>`<button class="${screen===k?'active':''}" data-go="${k}"><b>${ico}</b>${e(l.replace('Meus ','').replace('Minha ',''))}</button>`).join('');
}
function heading(title,desc='',action=''){return `<div class="dashboard-head"><div><div class="eyebrow">DG CORTES / SISTEMA</div><h1>${title}</h1><p class="subtitle">${desc}</p></div>${action}</div>`}
function render(){
 $('#year').textContent=new Date().getFullYear();brandSettings();renderNav();
 if(!boot?.installed){$('#top-actions').innerHTML='';$('#desktop-nav').innerHTML='';$('#mobile-dock').innerHTML='';$('#app-content').innerHTML=setupHTML();return}
 const app=$('#app-content');
 app.innerHTML=({'home':homeHTML,'auth':authHTML,'booking':bookingHTML,'dashboard':dashboardHTML,'appointments':appointmentsHTML,'team':teamHTML,'clients':clientsHTML,'catalog':catalogHTML,'plans-admin':plansAdminHTML,'promos-admin':promosAdminHTML,'hours':hoursHTML,'account':accountHTML,'settings':settingsHTML,'confirmation':confirmationHTML,'apply-barber':applyBarberHTML}[screen]||homeHTML)();
 if(screen==='booking')loadSlots();if(screen==='hours')loadExceptions();if(screen==='confirmation')loadConfirmation();
}
function setupHTML(){return `<section class="page auth-layout"><div class="auth-copy"><div class="eyebrow">Bem-vindo ao seu sistema</div><h1 class="page-title">A barbearia começa por aqui.</h1><p class="lead">Cadastre o proprietário da DG Cortes. Esta será a conta principal, protegida contra exclusão ou perda de acesso por outros administradores.</p><img src="${logo()}" alt="Logo da DG Cortes"></div><div class="card auth-panel"><h2>Configuração inicial</h2><div class="notice">Crie uma senha forte. Não há usuário ou senha padrão.</div>${form('/api/setup',`<div class="form-grid">${field('Nome e sobrenome','name','','text','required minlength="3"')}${field('Telefone','phone','','tel','required minlength="8"')}${field('E-mail do dono','email','','email','required')}${field('Instagram (opcional)','instagram','','text')}${boot?.requires_setup_token?field('Código de ativação do proprietário','setup_token','','password','required'):''}${field('Senha (mínimo 8 caracteres)','password','','password','required minlength="8"')}</div>`,'Criar conta principal',false)}</div></section>`}
function homeHTML(){
 const services=show('services')?S.services.filter(s=>s.active&&S.categories.some(c=>c.id===s.category_id&&c.active)):[];
 const staff=show('team')?S.barbers.filter(b=>b.active&&b.user_active):[];
 const plans=show('plans')?S.plans.filter(p=>p.active):[];
 const promos=show('promotions')?S.promotions.filter(p=>p.active&&p.public&&(!p.valid_until||p.valid_until>=today())):[];
 return `<section class="hero"><div><div class="eyebrow">✦ BARBEARIA • CUIDADO EM CADA DETALHE</div><h1>Seu estilo.<br>Sua marca.<br><em>DG Cortes.</em></h1><p class="lead">A experiência de barbearia que combina tradição, personalidade e horário reservado especialmente para você.</p><div class="hero-buttons">${show('booking')?'<button class="btn" data-go="booking">Agendar meu horário ↗</button>':''}<button class="btn alt" data-go="home#services">Explorar serviços</button></div><div class="brand-features"><span>Agendamento online</span><span>Profissionais à sua escolha</span><span>Clube de vantagens</span></div></div><div class="hero-visual"><img src="${logo()}" alt="Logotipo original Barbearia DG Cortes"></div></section>
 ${show('services')?`<section class="section" id="services"><div class="section-head"><div><div class="eyebrow">O que fazemos</div><h2>Nossos serviços</h2><p>Preços e duração definidos pela barbearia.</p></div></div><div class="grid cols3">${services.length?services.map(s=>`<article class="card"><div class="card-top"><span class="chip">${e(S.categories.find(c=>c.id===s.category_id)?.name||'Serviço')}</span><span class="muted">${s.duration} min</span></div><h3>${e(s.title)}</h3><div class="service-price">${money(s.price_cents)}</div><div class="card-actions"><button class="btn small outline" data-go="booking">Agendar →</button></div></article>`).join(''):'<div class="empty">Em breve: serviços e preços.</div>'}</div></section>`:''}
 ${show('team')?`<section class="section" id="staff"><div class="section-head"><div><div class="eyebrow">Nossa equipe</div><h2>Escolha seu barbeiro</h2><p>Profissionais e horários disponíveis em tempo real dentro do sistema.</p></div></div><div class="grid cols3">${staff.map(b=>`<div class="card"><div class="staff-row">${avatar(b)}<div><h3>${e(b.name)}</h3><p>${e(b.instagram||'Profissional DG')}</p></div></div><div class="card-actions"><button class="btn small" data-action="book-with" data-id="${b.id}">Reservar horário →</button></div></div>`).join('')}</div></section>`:''}
 ${show('plans')?`<section class="section" id="plans"><div class="section-head"><div><div class="eyebrow">Vantagens de ser cliente</div><h2>Planos de fidelidade</h2><p>Solicitação e ativação sujeitas à confirmação da barbearia. Pagamento feito fora do site.</p></div></div><div class="grid cols3">${plans.length?plans.map(p=>`<div class="card"><span class="chip">${p.days} dias</span><h3 style="margin-top:13px">${e(p.title)}</h3><div class="service-price">${money(p.price_cents)}</div><p>${e(p.cuts)} corte(s) elegíveis no período</p><p>${e(p.description)}</p><div class="card-actions"><button class="btn outline small" data-action="request-plan" data-id="${p.id}">Solicitar plano →</button></div></div>`).join(''):'<div class="empty">Novos planos em breve.</div>'}</div>
 </section>`:''}
 ${show('promotions')&&promos.length?`<div class="home-callout"><div><span class="eyebrow">OFERTAS ESPECIAIS</span><h2>${e(promos[0].title)}</h2><p>${promos[0].discount}% de desconto com o código <b>${e(promos[0].code)}</b>${promos[0].valid_until?' • Até '+dateText(promos[0].valid_until):''}</p></div><button class="btn" data-go="booking">Quero aproveitar ↗</button></div>`:''}`;
}
function authHTML(){let register=authMode==='register';return `<section class="page auth-layout"><div class="auth-copy"><div class="eyebrow">ÁREA EXCLUSIVA DG CORTES</div><h1 class="page-title">${register?'Faça parte do clube.':'Bem-vindo de volta.'}</h1><p class="lead">${register?'Tenha um perfil, solicite planos especiais e acompanhe seus horários.':'Entre como cliente, barbeiro ou administrador usando sua conta.'}</p><img src="${logo()}" alt="DG Cortes"></div><div class="card auth-panel"><div class="eyebrow">ACESSO SEGURO</div><h2>${register?'Criar meu perfil':'Entrar no sistema'}</h2>${form(register?'/api/register':'/api/login',`${register?field('Nome e sobrenome','name','','text','required minlength="3"')+field('Telefone / WhatsApp','phone','','tel','required minlength="8"'):''}${field('E-mail','email','','email','required')}${field('Senha','password','','password','required minlength="8"')}`,register?'Cadastrar':'Entrar',false)}<p class="muted">${register?'Já tem conta?':'Ainda não é cliente?'} <button class="auth-switch" data-action="auth-mode" data-mode="${register?'login':'register'}">${register?'Entrar':'Criar cadastro grátis'}</button></p><div class="divider"></div><button class="btn alt block" data-go="booking">Agendar como visitante, sem cadastro</button></div></section>`}
function bookingHTML(){
 const b=S.barbers.filter(x=>x.active&&x.user_active),svc=S.services.filter(x=>x.active&&S.categories.some(c=>c.id===x.category_id&&c.active));
 if(!b.length||!svc.length)return `<section class="page">${heading('Agendar horário','A barbearia está configurando a agenda.')}<div class="empty">Ainda não há barbeiros ou serviços disponíveis.</div></section>`;
 const bid=currentBooking.barber_id&&b.some(x=>x.id==currentBooking.barber_id)?currentBooking.barber_id:b[0].id;
 const sid=currentBooking.service_id&&svc.some(x=>x.id==currentBooking.service_id)?currentBooking.service_id:svc[0].id;
 currentBooking={...currentBooking,barber_id:bid,service_id:sid,day:currentBooking.day||today()};
 let service=svc.find(x=>x.id==sid), barber=b.find(x=>x.id==bid);
 const sub=S?.subscriptions.find(x=>x.status==='active'&&x.cuts_left>0&&x.starts_at<=currentBooking.day&&x.ends_at>=currentBooking.day);
 const credit=S.user?.role==='client'&&(S.user.courtesy_credits>0||sub&&service.plan_eligible);
 return `<section class="page">${heading('Agende seu corte','Escolha um serviço, um profissional e o melhor horário para você.')}<div class="booking"><div class="card stack"><div class="eyebrow">01 / ESCOLHA O SERVIÇO</div>${select('Serviço','service_id',svc.map(s=>[s.id,`${s.title} • ${money(s.price_cents)} • ${s.duration} min`]),sid).replace('<select','<select id="book-service"')}
 <div class="divider"></div><div class="eyebrow">02 / ESCOLHA O PROFISSIONAL</div>${select('Barbeiro','barber_id',b.map(x=>[x.id,x.name]),bid).replace('<select','<select id="book-barber"')}
 <div class="divider"></div><div class="eyebrow">03 / ESCOLHA O DIA</div>${field('Data de atendimento','day',currentBooking.day,'date',`id="book-day" min="${today()}"`)}
 <div class="divider"></div><div class="eyebrow">04 / ESCOLHA UM HORÁRIO</div><div id="booking-slots" class="slot-grid"><span class="muted">Consultando horários...</span></div><div class="tiny-note">Horários exibidos respeitam a duração do serviço, bloqueios e agendamentos existentes.</div></div>
 <div class="card book-summary"><div class="eyebrow">RESUMO DO AGENDAMENTO</div><h3 style="font:600 27px Georgia,serif;margin:8px 0 20px">Está quase pronto.</h3><div class="detail"><span>Serviço</span><strong>${e(service.title)}</strong></div><div class="detail"><span>Barbeiro</span><strong class="barber-summary">${avatar(barber,'avatar-sm')}${e(barber.name)}</strong></div><div class="detail"><span>Data</span><strong>${dateText(currentBooking.day)}</strong></div><div class="detail"><span>Horário</span><strong id="chosen-time">${selectedSlot||'Selecione ao lado'}</strong></div><div class="detail"><span>Valor de referência</span><strong class="highlight-number">${money(service.price_cents)}</strong></div>
 <form id="booking-form" class="stack" style="margin-top:20px">${S?.user?.role==='client'?`<div class="notice">Reserva para ${e(S.user.name)} • ${e(S.user.phone)}</div>${credit?select('Como quer usar seu benefício?','benefit', [['normal','Preço normal'],...(S.user.courtesy_credits>0?[['courtesy',`Cortesia (${S.user.courtesy_credits} disponível)`]]:[]),...(sub&&service.plan_eligible?[['plan',`Plano ${sub.plan_name} (${sub.cuts_left} cortes)`]]:[])],'normal'):''}`:`${field('Nome e sobrenome','name','','text','required minlength="3"')}${field('Telefone / WhatsApp','phone','','tel','required minlength="8"')}${field('E-mail para confirmação','email','','email','required')}`}${field('Código de promoção (opcional)','promo','','text','placeholder="Ex.: DGCORTES10"')}<button type="submit" id="btn-book" class="btn block" ${!selectedSlot?'disabled':''}>Confirmar horário →</button></form><p class="tiny-note">Não há pagamento online nesta versão. A barbearia confirma valores e cobranças diretamente.</p></div></div></section>`;
}
async function loadSlots(){
 const target=$('#booking-slots');if(!target)return;
 try{
   let result=await api(`/api/availability?barber_id=${encodeURIComponent(currentBooking.barber_id)}&service_id=${encodeURIComponent(currentBooking.service_id)}&day=${encodeURIComponent(currentBooking.day)}`);
   if(screen!=='booking')return;
   slots=result.slots;
   if(selectedSlot&&!slots.includes(selectedSlot))selectedSlot='';
   target.innerHTML=slots.length?slots.map(t=>`<button class="slot ${selectedSlot===t?'active':''}" data-action="choose-slot" data-time="${t}">${t}</button>`).join(''):'<div class="inline-empty" style="grid-column:1/-1">Sem vagas nesta data. Escolha outro dia ou barbeiro.</div>';
   $('#chosen-time').textContent=selectedSlot||'Selecione ao lado';$('#btn-book').disabled=!selectedSlot;
 }catch(err){if(target)target.innerHTML=`<div class="inline-empty" style="grid-column:1/-1">${e(err.message)}</div>`;selectedSlot='';let btn=$('#btn-book');if(btn)btn.disabled=true;}
}
function dashboardHTML(){
 if(!ADMIN())return homeHTML();const todayA=S.appointments.filter(x=>x.day===today()&&x.status==='scheduled');const active=S.appointments.filter(x=>x.status==='scheduled');const pend=S.subscriptions.filter(x=>x.status==='pending');const counts=[['Agendamentos de hoje',todayA.length,'◷'],['Agendamentos futuros',active.filter(x=>x.day>=today()).length,'▣'],['Clientes cadastrados',S.users.filter(x=>x.role==='client').length,'♙'],['Planos pendentes',pend.length,'◈']];
 return `<section class="page">${heading(`Olá, ${e(S.user.name.split(' ')[0])}.`,'Aqui está um resumo da DG Cortes neste momento.','<button class="btn" data-go="appointments">Ver agenda completa ↗</button>')}<div class="grid cols4">${counts.map(([label,n,ico])=>`<div class="card"><div class="metric-icon">${ico}</div><div class="metric-value">${n}</div><div class="metric-label">${e(label)}</div></div>`).join('')}</div><div class="grid cols2" style="margin-top:22px"><div class="card"><div class="tile-inline"><h3>Atendimentos de hoje</h3><button class="btn alt small" data-go="appointments">Abrir →</button></div>${todayA.length?todayA.slice(0,8).map(a=>appointmentRow(a,true)).join(''):'<p class="inline-empty">Nenhum horário reservado hoje.</p>'}</div><div class="card"><div class="tile-inline"><h3>Solicitações de planos</h3><button class="btn alt small" data-go="plans-admin">Analisar →</button></div>${pend.length?pend.slice(0,8).map(p=>`<div class="list-row"><div><strong>${e(p.customer_name)}</strong><small>${e(p.plan_name)} • ${dateText(p.created_at.slice(0,10))}</small></div>${pill(p.status)}</div>`).join(''):'<p class="inline-empty">Não há solicitações pendentes.</p>'}</div></div><div class="home-callout"><div><div class="eyebrow">CONTROLE DE ACESSOS</div><h2>Sua equipe, suas permissões.</h2><p>Você pode transformar outro usuário em administrador sem alterar a conta principal.</p></div><button class="btn" data-go="clients">Gerenciar acessos →</button></div></section>`
}
function appointmentRow(a,more=false){
 let bName=a.barber_name||S.barbers.find(b=>b.id===a.barber_id)?.name||'';
 let can=ADMIN()||BARBER()||S?.user?.role==='client'&&a.user_id===S.user.id;
 return `<div class="list-row"><div><strong>${e(a.customer_name)} <span style="color:var(--gold)">• ${e(a.start_time)}</span></strong><small>${dateText(a.day)} · ${e(a.service_name)} · ${e(bName)} · ${money(a.amount_cents)}</small>${more?'':`<small>${e(a.customer_phone)} • ${e(a.payment_type==='normal'?'Pagamento normal':a.payment_type==='plan'?'Corte incluso no plano':a.payment_type==='courtesy'?'Cortesia':'Promoção')}</small>`}</div><div class="row-actions">${pill(a.status)}${can&&a.status==='scheduled'?`<button class="btn danger small" data-action="appointment" data-id="${a.id}" data-status="cancelled">Cancelar</button>${(ADMIN()||BARBER())?`<button class="btn alt small" data-action="appointment" data-id="${a.id}" data-status="completed">Concluir</button>`:''}`:''}</div></div>`;
}
function appointmentsHTML(){
 if(!S.user)return authHTML();let upcoming=S.appointments.filter(a=>a.status==='scheduled'&&a.day>=today()).sort((a,b)=>(a.day+a.start_time).localeCompare(b.day+b.start_time));let history=S.appointments.filter(a=>!upcoming.includes(a));
 return `<section class="page">${heading(ADMIN()?'Agenda da barbearia':BARBER()?'Minha agenda':'Meus horários',ADMIN()?'Todos os atendimentos e profissionais em um só lugar.':BARBER()?'Você só visualiza e altera seus próprios atendimentos.':'Acompanhe e gerencie seus agendamentos.',ADMIN()?'<button class="btn" data-go="hours">Editar horários →</button>':'<button class="btn" data-go="booking">Novo agendamento →</button>')}<div class="card"><div class="section-head"><h2 style="font-size:24px">Próximos agendamentos</h2><span class="chip">${upcoming.length} reservado(s)</span></div>${upcoming.length?upcoming.map(a=>appointmentRow(a)).join(''):'<div class="empty">Nenhum agendamento futuro. Sua agenda está livre.</div>'}</div>${history.length?`<div class="card" style="margin-top:20px"><h3>Histórico recente</h3>${history.slice(0,50).map(a=>appointmentRow(a)).join('')}</div>`:''}</section>`
}
function teamHTML(){
 let bs=S.barbers;if(!ADMIN())return homeHTML();const active=bs.filter(b=>b.active&&b.role!=='owner').length;
 return `<section class="page">${heading('Equipe de barbeiros',`${active}/5 barbeiros adicionais • o proprietário não entra nesse limite.`,'<button class="btn" data-edit="staff:new">+ Cadastrar barbeiro</button>')}<div class="notice">Cada barbeiro usa o próprio e-mail e senha. O proprietário e os administradores podem acessar todas as agendas. Quem for promovido a administrador continua com sua agenda de barbeiro.</div><div class="grid cols3" style="margin-top:20px">${bs.map(b=>`<div class="card"><div class="staff-row">${avatar(b)}<div><h3>${e(b.name)}</h3><p>${e(b.instagram||'Instagram não informado')}</p></div></div><div class="divider"></div><div class="detail"><span>Telefone</span><strong>${e(b.phone)}</strong></div><div class="detail"><span>E-mail</span><strong>${e(b.email)}</strong></div><div class="detail"><span>Acesso</span>${pill(b.role)}</div><div class="detail"><span>Situação</span>${pill(b.active?'active':'cancelled')}</div><div class="card-actions">${b.role!=='owner'||S.user.role==='owner'?`<button class="btn alt small" data-action="photo-editor" data-id="${b.user_id}">Foto</button>`:''}<button class="btn alt small" data-action="manage-barber-hours" data-id="${b.id}">Horários</button>${b.role!=='owner'?`<button class="btn ${b.active?'danger':'outline'} small" data-action="toggle-staff" data-id="${b.id}" data-active="${b.active?'0':'1'}">${b.active?'Desativar':'Reativar'}</button>`:''}</div></div>`).join('')}</div><div class="card" style="margin-top:24px"><h3>Solicitações para entrar na equipe</h3>${S.applications.filter(a=>a.status==='pending').length?S.applications.filter(a=>a.status==='pending').map(a=>`<div class="list-row"><div><strong>${e(a.name)} • ${e(a.instagram)}</strong><small>${e(a.email)} · ${e(a.phone)}</small></div><div class="row-actions"><button class="btn small" data-action="application" data-id="${a.id}" data-status="approved">Aprovar</button><button class="btn danger small" data-action="application" data-id="${a.id}" data-status="rejected">Recusar</button></div></div>`).join(''):'<p class="muted">Nenhum cadastro pendente.</p>'}</div></section>`;
}
function clientsHTML(){
 if(!ADMIN())return homeHTML();let users=S.users;
 return `<section class="page">${heading('Perfis e permissões','Clientes, barbeiros, administradores e cortesias.')}<div class="notice">Um administrador pode promover outro usuário a administrador. A conta do proprietário é protegida e ninguém pode remover seu acesso principal.</div><div class="card" style="margin-top:19px"><div class="toolbar"><h3>Usuários cadastrados <span class="chip">${users.length}</span></h3><input class="search-input" id="user-search" placeholder="Buscar por nome, e-mail ou telefone" style="max-width:330px" autocomplete="off"></div><div class="table-wrap"><table class="table"><thead><tr><th>Nome</th><th>Contato</th><th>Perfil</th><th>Cortesias</th><th>Ações</th></tr></thead><tbody id="users-list">${users.map(userRow).join('')}</tbody></table></div></div></section>`;
}
function userRow(u){
 const staff=S.barbers.some(b=>b.user_id===u.id);const owner=u.role==='owner';const self=u.id===S.user.id;
 return `<tr data-user-row="${e((u.name+' '+u.email+' '+u.phone).toLowerCase())}"><td><div class="user-identity">${avatar(u, 'avatar-sm')}<strong>${e(u.name)}</strong></div><br>${u.active?'':'<span class="chip red">Inativo</span>'}</td><td>${e(u.email)}<br><span class="muted">${e(u.phone)}</span></td><td>${pill(u.role)}</td><td>${u.courtesy_credits}</td><td class="actions">${!owner&&!self&&u.active?`<button class="btn small ${u.role==='admin'?'danger':'alt'}" data-action="toggle-admin" data-id="${u.id}" data-role="${u.role==='admin'?'regular':'admin'}">${u.role==='admin'?'Retirar admin':'Tornar admin'}</button>`:''} ${!owner||self?`<button class="btn alt small" data-action="photo-editor" data-id="${u.id}">Foto</button>`:''} <button class="btn alt small" data-action="courtesy" data-id="${u.id}">Cortesias</button> ${!owner&&!self&&!staff?`<button class="btn small ${u.active?'danger':'outline'}" data-action="toggle-user" data-id="${u.id}" data-active="${u.active?'0':'1'}">${u.active?'Desativar':'Reativar'}</button>`:''}</td></tr>`;
}
function catalogHTML(){
 if(!ADMIN())return homeHTML();
 return `<section class="page">${heading('Catálogo e preços','Crie categorias e serviços, ajuste duração e defina quais entram nos planos.')}<div class="toolbar"><h2 class="page-title" style="font-size:25px">Categorias</h2><button class="btn small" data-edit="category:new">+ Categoria</button></div><div class="grid cols3">${S.categories.map(c=>`<div class="card tile-inline"><div><strong>${e(c.name)}</strong><p>${c.active?'Visível para o público':'Oculta do público'}</p></div><button class="btn alt small" data-edit="category:${c.id}">Editar</button></div>`).join('')}</div><div class="toolbar" style="margin-top:30px"><h2 class="page-title" style="font-size:25px">Serviços</h2><button class="btn" data-edit="service:new">+ Novo serviço</button></div><div class="grid cols3">${S.services.map(s=>`<div class="card"><div class="card-top"><span class="chip">${e(S.categories.find(c=>c.id===s.category_id)?.name||'Categoria')}</span>${pill(s.active?'active':'cancelled')}</div><h3>${e(s.title)}</h3><div class="service-price">${money(s.price_cents)}</div><p>${s.duration} min · ${s.plan_eligible?'Aceita cortes do plano':'Não aceita plano'}</p><div class="card-actions"><button class="btn alt small" data-edit="service:${s.id}">Editar serviço →</button></div></div>`).join('')}</div></section>`
}
function plansAdminHTML(){
 if(!ADMIN())return homeHTML();const pend=S.subscriptions.filter(x=>x.status==='pending');
 return `<section class="page">${heading('Planos e assinaturas','Configure valores e duração. Aprovação e pagamento são controlados pela barbearia.','<button class="btn" data-edit="plan:new">+ Criar plano</button>')}<div class="grid cols3">${S.plans.map(p=>`<div class="card"><div class="card-top"><span class="chip">${p.days} dias</span>${pill(p.active?'active':'cancelled')}</div><h3>${e(p.title)}</h3><div class="service-price">${money(p.price_cents)}</div><p>${p.cuts} corte(s) incluídos</p><p>${e(p.description)}</p><button class="btn alt small" data-edit="plan:${p.id}">Editar plano →</button></div>`).join('')}</div><div class="card" style="margin-top:25px"><h3>Solicitações de clientes ${pend.length?`<span class="chip">${pend.length} aguardando</span>`:''}</h3><p class="help">Ative um plano somente depois de confirmar o pagamento ou conceder a assinatura ao cliente.</p>${S.subscriptions.length?S.subscriptions.map(s=>`<div class="list-row"><div><strong>${e(s.customer_name)} • ${e(s.plan_name)}</strong><small>${pill(s.status)} · Solicitado em ${dateText(s.created_at.slice(0,10))}</small><small>${s.starts_at?dateText(s.starts_at)+' a '+dateText(s.ends_at)+' · '+s.cuts_left+' cortes restantes':''}</small></div><div class="row-actions">${s.status==='pending'?`<button class="btn small" data-action="subscription" data-id="${s.id}" data-status="active">Aprovar</button><button class="btn danger small" data-action="subscription" data-id="${s.id}" data-status="rejected">Rejeitar</button>`:s.status==='active'?`<button class="btn danger small" data-action="subscription" data-id="${s.id}" data-status="cancelled">Encerrar</button>`:''}</div></div>`).join(''):'<div class="empty">Ainda não há assinaturas solicitadas.</div>'}</div></section>`;
}
function promosAdminHTML(){
 if(!ADMIN())return homeHTML();return `<section class="page">${heading('Promoções e cupons','Crie um código, configure o desconto e decida se a oferta aparece ao público.','<button class="btn" data-edit="promo:new">+ Criar promoção</button>')}<div class="grid cols3">${S.promotions.map(p=>`<div class="card"><div class="card-top"><span class="chip">${p.discount}% OFF</span>${pill(p.active?'active':'cancelled')}</div><h3>${e(p.title)}</h3><div class="service-price">${e(p.code)}</div><p>${p.valid_until?'Válido até '+dateText(p.valid_until):'Sem prazo definido'}</p><p>${p.public?'Oferta aparece no site':'Oferta não aparece no site'}</p><button class="btn alt small" data-edit="promo:${p.id}">Editar promoção →</button></div>`).join('')||'<div class="empty">Nenhuma promoção criada.</div>'}</div></section>`}
function hoursHTML(){
 if(!ADMIN()&&!BARBER())return homeHTML();let bs=ADMIN()?S.barbers.filter(b=>b.active&&b.user_active):S.barbers.filter(b=>b.user_id===S.user.id&&b.active);
 if(!bs.length)return `<section class="page"><div class="empty">Seu perfil não possui agenda de barbeiro ativa.</div></section>`;
 if(!bs.some(b=>b.id==timeEditor.barber_id))timeEditor.barber_id=bs[0].id;
 timeEditor.day=timeEditor.day||today();
 return `<section class="page">${heading('Horários e disponibilidade','Bloqueie horários, libere encaixes extras e administre a agenda de cada barbeiro.')}<div class="grid cols2"><div class="card stack"><div class="eyebrow">AGENDA DO PROFISSIONAL</div>${select('Barbeiro','hours-barber',bs.map(b=>[b.id,b.name]),timeEditor.barber_id).replace('<select','<select id="hours-barber"')}${field('Data','hours-day',timeEditor.day,'date',`id="hours-day" min="${today()}"`)}<div class="notice">O horário padrão é de segunda a sábado, das 09:00 às 18:00. Para abrir horários fora deste período, adicione encaixes extras. Para bloquear uma hora de atendimento, bloqueie seus intervalos de 30 minutos.</div><form id="hours-form" class="stack">${select('Horário (início)','time',Array.from({length:32},(_,i)=>{let h=String(7+Math.floor(i/2)).padStart(2,'0')+':'+(i%2?'30':'00');return [h,h]}))}${select('Ação','mode',[['blocked','Bloquear intervalo'],['extra','Adicionar encaixe extra'],['clear','Remover bloqueio / encaixe']])}<button class="btn" type="submit">Salvar horário</button></form><div class="divider"></div><button class="btn alt" data-action="weekly-hours">Editar semana padrão →</button></div><div class="card"><div class="eyebrow">AJUSTES NESTE DIA</div><h3>Exceções da agenda</h3><div id="exceptions-list" class="stack"><p class="muted">Carregando...</p></div></div></div></section>`
}
async function loadExceptions(){
 const el=$('#exceptions-list');if(!el)return;
 try{const r=await api(`/api/slot-exceptions?barber_id=${timeEditor.barber_id}&day=${timeEditor.day}`);
 if(!$('#exceptions-list'))return;
 el.innerHTML=r.rows.length?r.rows.map(x=>`<div class="list-row"><span class="slot-tag ${e(x.mode)}">${e(x.time)} • ${x.mode==='blocked'?'Bloqueado':'Encaixe extra'}</span><button class="btn small alt" data-action="clear-exception" data-id="${x.id}" data-time="${x.time}">Remover</button></div>`).join(''):'<div class="empty">Nenhum ajuste especial. Agenda padrão em vigor.</div>';
 }catch(err){el.innerHTML=`<p class="muted">${e(err.message)}</p>`}
}
function confirmationHTML(){
 return `<section class="page confirm-page"><div class="card confirmation-card"><div class="confirm-icon">✓</div><div class="eyebrow">AGENDAMENTO REALIZADO</div><h1>Horário confirmado!</h1><p>Seu atendimento foi reservado com sucesso. Guarde seu comprovante.</p><div id="confirm-details"><div class="loading">Consultando detalhes...</div></div><p class="notice">WhatsApp e e-mail automáticos só serão enviados depois que a barbearia configurar os serviços de mensagens. O comprovante na tela já confirma a reserva.</p><div class="card-actions"><button class="btn" data-go="home">Voltar ao início</button><button class="btn alt" data-go="booking">Agendar outro</button></div></div></section>`;
}
async function loadConfirmation(){
 const box=$('#confirm-details');if(!box)return;
 try {
  const hash=location.hash.match(/^#confirmacao\/(\d+)\/([^/]+)/);
  const a=confirmedBooking || (hash?await api(`/api/appointments/${hash[1]}/confirmation?token=${encodeURIComponent(hash[2])}`):null);
  if(!a){box.innerHTML='<p class="notice">O link deste comprovante não está disponível. Consulte seus agendamentos no perfil.</p>';return}
  const id=a.id;const barber=a.barber_name;const service=a.service_name;const day=a.day;const time=a.time||a.start_time;const amount=a.amount_cents;
  box.innerHTML=`<div class="confirm-code">PROTOCOLO #${e(id)}</div><div class="detail"><span>Serviço</span><strong>${e(service)}</strong></div><div class="detail"><span>Barbeiro</span><strong>${e(barber)}</strong></div><div class="detail"><span>Data</span><strong>${dateText(day)}</strong></div><div class="detail"><span>Horário</span><strong>${e(time)}</strong></div><div class="detail"><span>Valor</span><strong>${money(amount)}</strong></div>`;
 }catch(x){box.innerHTML=`<p class="notice red">${e(x.message)}</p>`}
}
function applyBarberHTML(){return `<section class="page auth-layout"><div class="auth-copy"><div class="eyebrow">TRABALHE CONOSCO</div><h1 class="page-title">Solicitar acesso de barbeiro.</h1><p class="lead">Seu pedido ficará pendente até que um administrador o aprove. Há limite de cinco barbeiros adicionais.</p><img src="${logo()}" alt="Logotipo da barbearia"></div><div class="card auth-panel"><h2>Solicitação de cadastro</h2>${form('/api/apply-barber',field('Nome e sobrenome','name','','text','required')+field('Celular / WhatsApp','phone','','tel','required')+field('E-mail de acesso','email','','email','required')+field('Instagram','instagram','','text','placeholder="@usuario"')+field('Crie sua senha de acesso','password','','password','required minlength="8"'),'Enviar solicitação',false)}</div></section>`}
function settingsHTML(){
 if(!ADMIN())return homeHTML();
 const conf=S.config, keys=[['services','Serviços e preços'],['team','Equipe de barbeiros'],['plans','Planos'],['promotions','Promoções'],['booking','Permitir agendar'],['rewards','Prêmios e cortesias']];
 const roles=[['guest','Visitantes'],['client','Clientes'],['barber','Barbeiros']];
 return `<section class="page">${heading('Personalização e controle','Edite logo, cores, recompensas e o que cada perfil visualiza.')}
 <div class="grid cols2"><div class="card"><div class="eyebrow">IDENTIDADE VISUAL</div><h3>Marca e aparência</h3><form id="settings-form" class="stack">${field('Nome exibido no site','site_name',conf.site_name,'text','required maxlength="50"')}<div class="form-grid">${field('Cor de fundo','background',conf.background,'color')}${field('Cor de destaque','accent',conf.accent,'color')}</div>${field('Ganhar uma cortesia a cada N atendimentos concluídos (0 = desativado)','reward_every',conf.reward_every,'number','min="0" max="100" required')}<button class="btn" type="submit">Salvar aparência e fidelidade</button></form><div class="divider"></div><h3>Atualizar logotipo</h3><div class="logo-preview"><img src="${logo()}" alt="Logo atual"></div><form id="logo-form" class="stack"><input type="file" name="logo" accept="image/png,image/jpeg,image/webp" required><button class="btn alt" type="submit">Enviar nova logo</button></form><p class="tiny-note">JPG, PNG ou WEBP, até 3 MB. Recomendado: fundo escuro e logo centralizada.</p></div>
 <div class="card"><div class="eyebrow">CONTROLE DE VISIBILIDADE</div><h3>O que cada pessoa pode ver?</h3><p class="muted">Defina as seções do site. Administradores continuam vendo todas as áreas; o proprietário nunca perde o controle.</p><form id="visibility-form"><div class="table-wrap"><table class="table visibility-table"><thead><tr><th>Seção</th>${roles.map(r=>`<th>${r[1]}</th>`).join('')}</tr></thead><tbody>${keys.map(([k,label])=>`<tr><td><strong>${label}</strong></td>${roles.map(([r])=>`<td><input type="checkbox" data-section="${k}" data-role="${r}" ${conf.visibility[k]?.includes(r)?'checked':''} aria-label="${label} para ${r}"></td>`).join('')}</tr>`).join('')}</tbody></table></div><button type="submit" class="btn block" style="margin-top:20px">Salvar permissões de exibição</button></form><div class="divider"></div><h3>Mensagens enviadas pelo sistema</h3><p class="help">Cada agendamento e conclusão registra tentativas de notificação. O envio real exige SMTP e WhatsApp Business API configurados no servidor.</p>${S.notifications?.length?S.notifications.slice(0,7).map(n=>`<div class="list-row"><div><b>#${n.appointment_id} · ${e(n.channel)}</b><small>${e(n.event)} • ${e(n.recipient)}</small></div><span class="chip">${e(n.status)}</span></div>`).join(''):'<p class="muted">Nenhuma notificação registrada.</p>'}</div></div></section>`;
}
function accountHTML(){
 if(!S.user)return authHTML();let u=S.user;const sub=S.subscriptions||[];
 return `<section class="page">${heading('Minha conta','Sua identificação e informações do perfil.')}<div class="grid cols2"><div class="card"><div class="staff-row">${avatar(u,'avatar-lg')}<div><h3>${e(u.name)}</h3>${pill(u.role)}</div></div><div class="divider"></div><form id="photo-form" class="stack photo-upload-form"><h3>Minha foto de perfil</h3><p class="help">Escolha uma foto sua para identificar o perfil. Formatos JPG, PNG ou WEBP, até 10 MB. Recomendado: foto quadrada de 1200 × 1200 px ou maior. O sistema otimiza automaticamente em alta qualidade, até 1600 px.</p><div class="photo-upload-preview">${avatar(u,'avatar-preview')}<div class="field"><label for="photo-input">Selecionar imagem</label><input type="file" name="photo" id="photo-input" accept="image/jpeg,image/png,image/webp" required></div></div><div class="card-actions"><button type="submit" class="btn small">Salvar minha foto</button>${u.avatar_url?'<button type="button" class="btn alt small" data-action="remove-photo" data-id="'+u.id+'">Remover foto</button>':''}</div></form><div class="divider"></div><div class="detail"><span>E-mail</span><strong>${e(u.email)}</strong></div><div class="detail"><span>Telefone</span><strong>${e(u.phone)}</strong></div>${show('rewards')?`<div class="detail"><span>Cortesias disponíveis</span><strong class="highlight-number">${u.courtesy_credits}</strong></div>`:''}<div class="card-actions">${!ADMIN()&&!BARBER()?'<button class="btn" data-go="booking">Agendar corte ↗</button>':''}<button class="btn alt" data-action="change-password">Alterar senha</button></div></div><div class="card"><h3>Planos e benefícios</h3>${sub.length?sub.map(s=>`<div class="list-row"><div><strong>${e(s.plan_name)}</strong><small>${s.status==='active'?`${s.cuts_left} cortes restantes · até ${dateText(s.ends_at)}`:'Solicitado: '+dateText(s.created_at.slice(0,10))}</small></div>${pill(s.status)}</div>`).join(''):'<p class="muted">Você ainda não possui planos solicitados.</p>'}${!ADMIN()&&!BARBER()?'<button class="btn outline small" data-go="home#plans" style="margin-top:16px">Conhecer planos →</button>':''}</div></div></section>`;
}
function editModal(type,id){
 const fresh=id==='new',find=(array)=>fresh?{}:array.find(x=>x.id===Number(id))||{};let d={},html='',title='',endpoint='';
 if(type==='staff'){
   title='Cadastrar novo barbeiro';endpoint='/api/staff';html=field('Nome e sobrenome','name','','text','required minlength="3"')+field('Telefone / WhatsApp','phone','','tel','required minlength="8"')+field('E-mail de acesso','email','','email','required')+field('Instagram','instagram','','text','placeholder="@barbeiro"')+field('Senha inicial (mínimo 8)','password','','password','required minlength="8"')+'<p class="help">Informe a senha inicial ao barbeiro por um canal privado. Ele poderá trocá-la depois.</p>';
 }
 if(type==='category'){
   d=find(S.categories);title=fresh?'Nova categoria':'Editar categoria';endpoint='/api/categories';html=(fresh?'':field('Código','id',d.id,'hidden'))+field('Nome da categoria','name',d.name,'text','required')+check('Categoria visível', 'active',d.active!==0);
 }
 if(type==='service'){
   d=find(S.services);title=fresh?'Novo serviço':'Editar serviço';endpoint='/api/services';html=(fresh?'':field('Código','id',d.id,'hidden'))+field('Nome do serviço','title',d.title,'text','required')+select('Categoria','category_id',S.categories.map(c=>[c.id,c.name]),d.category_id||S.categories[0]?.id)+`<div class="form-grid">${field('Preço (R$)','price',d.price_cents==null?'':(d.price_cents/100).toFixed(2),'number','step="0.01" min="0" required')}${select('Duração','duration',[30,60,90,120,150,180,210,240].map(x=>[x,x+' minutos']),d.duration||30)}</div>`+check('Aceita cortes de planos','plan_eligible',fresh?true:!!d.plan_eligible)+check('Serviço disponível no site','active',fresh?true:!!d.active);
 }
 if(type==='plan'){
   d=find(S.plans);title=fresh?'Criar plano':'Editar plano';endpoint='/api/plans';html=(fresh?'':field('Código','id',d.id,'hidden'))+field('Nome do plano','title',d.title,'text','required')+`<div class="form-grid">${field('Preço (R$)','price',d.price_cents==null?'':(d.price_cents/100).toFixed(2),'number','step="0.01" min="0" required')}${field('Duração (dias)','days',d.days||30,'number','min="1" max="365" required')}${field('Cortes incluídos','cuts',d.cuts||4,'number','min="1" max="100" required')}</div>`+field('Descrição','description',d.description||'')+check('Plano disponível para solicitação','active',fresh?true:!!d.active);
 }
 if(type==='promo'){
   d=find(S.promotions);title=fresh?'Nova promoção':'Editar promoção';endpoint='/api/promotions';html=(fresh?'':field('Código','id',d.id,'hidden'))+field('Título','title',d.title,'text','required')+field('Código promocional','code',d.code,'text','required placeholder="EX: DG10"')+`<div class="form-grid">${field('Desconto (%)','discount',d.discount||10,'number','min="1" max="100" required')}${field('Validade (opcional)','valid_until',d.valid_until,'date')}</div>`+check('Promoção ativa','active',fresh?true:!!d.active)+check('Exibir no site','public',fresh?true:!!d.public);
 }
 openModal(`<div class="eyebrow">PAINEL ADMINISTRATIVO</div><h2>${e(title)}</h2>${form(endpoint,html)}`);
}
async function actionCall(path,payload,message,confirmation){
 if(confirmation&&!confirm(confirmation))return;
 await api(path,{method:'POST',body:JSON.stringify(payload)});closeModal();await refresh();toast(message||'Alterações salvas.');
}
document.addEventListener('click',async event=>{
 const menuItem=event.target.closest('[data-menu]');
 if(menuItem){
   const action=menuItem.dataset.menu;$('#menu-panel').classList.add('hidden');
   if(action==='logout'){try{await actionCall('/api/logout',{},'Sessão encerrada.');go('home')}catch(ex){toast(ex.message,true)}return}
   if(action==='register'||action==='login'){authMode=action==='register'?'register':'login';go('auth');return}
   go(action);return;
 }
 if(!event.target.closest('#menu-panel,#menu-toggle'))$('#menu-panel').classList.add('hidden');
 const tgt=event.target.closest('[data-go],[data-action],[data-edit],[data-close]');if(!tgt)return;
 if(tgt.hasAttribute('data-close')){closeModal();return}
 if(tgt.dataset.go){let [page,anchor]=tgt.dataset.go.split('#');go(page);if(anchor)setTimeout(()=>document.getElementById(anchor)?.scrollIntoView({behavior:'smooth'}),60);return}
 if(tgt.dataset.edit){let [kind,id]=tgt.dataset.edit.split(':');editModal(kind,id);return}
 const id=Number(tgt.dataset.id);const action=tgt.dataset.action;
 try{
 if(action==='auth-mode'){authMode=tgt.dataset.mode;render();}
 if(action==='menu'){let panel=$('#menu-panel');panel.classList.toggle('hidden');tgt.setAttribute('aria-expanded',String(!panel.classList.contains('hidden')))}
 if(action==='application')await actionCall(`/api/applications/${id}/status`,{status:tgt.dataset.status},'Solicitação de barbeiro atualizada.',`Deseja ${tgt.dataset.status==='approved'?'aprovar':'recusar'} o cadastro?`);
 if(action==='weekly-hours'){
   let b=S.barbers.find(x=>x.id==timeEditor.barber_id), wk=JSON.parse(b.week_json), days=['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'];
   openModal(`<div class="eyebrow">JORNADA SEMANAL</div><h2>Horários de ${e(b.name)}</h2><form id="weekly-form" class="stack">${days.map((name,i)=>`<div class="week-row"><label>${name}</label><input type="checkbox" data-d="${i}" class="week-on" ${wk[i]?'checked':''}><input type="time" data-day="${i}" data-which="start" step="1800" value="${wk[i]?.start||'09:00'}"><input type="time" data-day="${i}" data-which="end" step="1800" value="${wk[i]?.end||'18:00'}"></div>`).join('')}<button type="submit" class="btn">Salvar semana</button></form>`);
 }
 if(action==='logout'){await actionCall('/api/logout',{},'Você saiu da sua conta.');go('home')}
 if(action==='book-with'){currentBooking.barber_id=id;selectedSlot='';go('booking')}
 if(action==='choose-slot'){selectedSlot=tgt.dataset.time;$('#chosen-time').textContent=selectedSlot;$('#btn-book').disabled=false;document.querySelectorAll('.slot').forEach(b=>b.classList.toggle('active',b.dataset.time===selectedSlot))}
 if(action==='request-plan'){
   if(!S.user){authMode='register';go('auth');toast('Crie seu cadastro para solicitar um plano.');return}
   if(S.user.role!=='client')return toast('Planos são solicitados por clientes.',true);
   await actionCall('/api/subscriptions/request',{plan_id:id},'Solicitação recebida! Aguarde aprovação.','Solicitar este plano? A ativação depende de aprovação da barbearia.');
 }
 if(action==='appointment')await actionCall(`/api/appointments/${id}/status`,{status:tgt.dataset.status},'Agendamento atualizado.',tgt.dataset.status==='cancelled'?'Deseja realmente cancelar este agendamento?':'Marcar atendimento como concluído?');
 if(action==='toggle-staff')await actionCall(`/api/staff/${id}/active`,{active:tgt.dataset.active==='1'},'Equipe atualizada.',tgt.dataset.active==='0'?'Desativar barbeiro? Todos os agendamentos futuros dele serão cancelados e créditos serão devolvidos.':'Reativar barbeiro?');
 if(action==='toggle-user')await actionCall(`/api/users/${id}/active`,{active:tgt.dataset.active==='1'},'Usuário atualizado.',tgt.dataset.active==='0'?'Desativar esta conta e cancelar seus agendamentos?':'Reativar esta conta?');
 if(action==='toggle-admin')await actionCall(`/api/users/${id}/role`,{role:tgt.dataset.role},'Permissões atualizadas.',tgt.dataset.role==='admin'?'Tornar este usuário administrador? Ele poderá gerenciar o sistema e promover outras pessoas.':'Retirar os privilégios de administrador deste usuário?');
 if(action==='courtesy')openModal(`<div class="eyebrow">BENEFÍCIOS</div><h2>Ajustar cortesias</h2><p class="help">Use número positivo para acrescentar cortes e negativo para retirar.</p>${form(`/api/users/${id}/courtesy`,field('Quantidade de cortes','delta',1,'number','required min="-100" max="100"'))}`);
 if(action==='subscription')await actionCall(`/api/subscriptions/${id}/status`,{status:tgt.dataset.status},'Assinatura atualizada.',tgt.dataset.status==='active'?'Confirma que o pagamento ou a concessão do plano foi verificado?':'Confirma a alteração desta assinatura?');
 if(action==='manage-barber-hours'){timeEditor.barber_id=id;go('hours')}
 if(action==='photo-editor'){
   const user=S.users.find(u=>u.id===id);
   if(!user)throw Error('Usuário não encontrado.');
   openModal(`<div class="eyebrow">FOTO DE PERFIL</div><h2>${e(user.name)}</h2><div class="photo-admin-preview">${avatar(user,'avatar-preview')}</div><p class="help">JPG, PNG ou WEBP, até 10 MB. Recomendação: 1200 × 1200 pixels ou maior. Otimização automática para até 1600 px.</p><form id="photo-form" class="stack"><input type="hidden" name="user_id" value="${user.id}"><div class="field"><label for="photo-input">Nova foto</label><input type="file" name="photo" id="photo-input" accept="image/jpeg,image/png,image/webp" required></div><button type="submit" class="btn">Salvar foto</button></form>${user.avatar_url?`<button class="btn alt small" style="margin-top:12px" data-action="remove-photo" data-id="${user.id}">Remover foto</button>`:''}`);
 }
 if(action==='remove-photo')await actionCall('/api/profile/photo/remove',{user_id:id},'Foto removida com sucesso.','Tem certeza que deseja remover esta foto de perfil?');
 if(action==='clear-exception')await actionCall('/api/slot-exceptions',{barber_id:timeEditor.barber_id,day:timeEditor.day,time:tgt.dataset.time,mode:'clear'},'Ajuste removido.');
 if(action==='change-password')openModal(`<div class="eyebrow">SEGURANÇA</div><h2>Alterar sua senha</h2>${form('/api/password',field('Senha atual','old','','password','required')+field('Nova senha (mínimo 8 caracteres)','new','','password','required minlength="8"'))}<div class="help">Após a troca, você precisará entrar novamente.</div>`)
 }catch(ex){toast(ex.message,true)}
});
document.addEventListener('change',async event=>{
 let t=event.target;
 if(t.id==='photo-input'&&t.files?.[0]){
   const file=t.files[0];
   if(file.size>10*1024*1024){toast('Foto acima do limite de 10 MB.',true);t.value='';return;}
   const preview=t.closest('form')?.parentElement?.querySelector('.avatar-preview')||t.closest('form')?.querySelector('.avatar-preview');
   if(preview){
     const blob=URL.createObjectURL(file);
     const img=new Image();img.onload=()=>{preview.replaceChildren(img);URL.revokeObjectURL(blob)};
     img.onerror=()=>{URL.revokeObjectURL(blob);toast('Não foi possível visualizar a foto.',true)};
     img.alt='Prévia da foto de perfil';img.src=blob;
   }
 }

 if(t.id==='book-service'||t.id==='book-barber'||t.id==='book-day'){
   if(t.id==='book-service')currentBooking.service_id=Number(t.value);
   if(t.id==='book-barber')currentBooking.barber_id=Number(t.value);
   if(t.id==='book-day')currentBooking.day=t.value;
   selectedSlot='';render();
 }
 if(t.id==='hours-barber'){timeEditor.barber_id=Number(t.value);loadExceptions()}
 if(t.id==='hours-day'){timeEditor.day=t.value;loadExceptions()}
});
document.addEventListener('input',ev=>{
 if(ev.target.id==='user-search'){
   let val=ev.target.value.toLowerCase();document.querySelectorAll('[data-user-row]').forEach(row=>row.hidden=!row.dataset.userRow.includes(val));
 }
});
document.addEventListener('submit',async event=>{
 const f=event.target;
 if(!(f.matches('form[data-api]')||['booking-form','hours-form','settings-form','visibility-form','logo-form','weekly-form','photo-form'].includes(f.id)))return;
 event.preventDefault();let btn=f.querySelector('button[type=submit]');if(btn)btn.disabled=true;
 try{
 if(f.id==='booking-form'){
   if(!selectedSlot)throw Error('Escolha um horário disponível.');
   let data=Object.fromEntries(new FormData(f).entries());
   let body={...data,barber_id:currentBooking.barber_id,service_id:currentBooking.service_id,day:currentBooking.day,time:selectedSlot};
   body.use_courtesy=data.benefit==='courtesy';body.use_plan=data.benefit==='plan';
   let r=await api('/api/book',{method:'POST',body:JSON.stringify(body)});
   selectedSlot='';currentBooking={};confirmedBooking=r;await refresh();
   history.replaceState(null,'','#confirmacao/'+r.id+'/'+r.token);
   go('confirmation');toast('Agendamento confirmado com sucesso.');
 }
 else if(f.id==='settings-form'){
   const d=Object.fromEntries(new FormData(f).entries());await api('/api/settings',{method:'POST',body:JSON.stringify(d)});await refresh();toast('Visual e fidelidade atualizados.');
 }
 else if(f.id==='visibility-form'){
   const vis={};f.querySelectorAll('input[data-section]').forEach(c=>{(vis[c.dataset.section]??=[]);if(c.checked)vis[c.dataset.section].push(c.dataset.role)});
   await api('/api/settings',{method:'POST',body:JSON.stringify({visibility:vis})});await refresh();toast('Permissões de exibição atualizadas.');
 }
 else if(f.id==='photo-form'){
   const input=f.querySelector('input[name="photo"]');const file=input?.files?.[0];
   if(!file)throw Error('Escolha sua foto.');
   if(file.size>10*1024*1024)throw Error('A foto pode ter até 10 MB.');
   if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw Error('Formatos aceitos: JPG, PNG e WEBP.');
   const response=await fetch('/api/profile/photo',{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':boot.csrf},body:new FormData(f)});
   const payload=await response.json().catch(()=>({error:'Erro ao enviar a foto.'}));
   if(!response.ok)throw Error(payload.error||'Não foi possível enviar a foto.');
   closeModal();await refresh();toast('Foto de perfil salva em alta qualidade.');
 }
 else if(f.id==='logo-form'){
   const resp=await fetch('/api/branding/logo',{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':boot.csrf},body:new FormData(f)});
   const payload=await resp.json();if(!resp.ok)throw Error(payload.error||'Falha ao enviar imagem.');await refresh();toast('Logotipo alterado com sucesso.');
 }
 else if(f.id==='weekly-form'){
   const wk={};for(let i=0;i<7;i++){let on=f.querySelector(`[data-d="${i}"]`).checked;wk[i]=on?{start:f.querySelector(`[data-day="${i}"][data-which="start"]`).value,end:f.querySelector(`[data-day="${i}"][data-which="end"]`).value}:null;}
   await api(`/api/barbers/${timeEditor.barber_id}/week`,{method:'POST',body:JSON.stringify({week:wk})});closeModal();await refresh();toast('Semana de trabalho alterada.');
 }
 else if(f.id==='hours-form'){
   let d=Object.fromEntries(new FormData(f).entries());await api('/api/slot-exceptions',{method:'POST',body:JSON.stringify({...d,barber_id:timeEditor.barber_id,day:timeEditor.day})});await loadExceptions();toast('Horário atualizado.');
 }
 else{
   const data=Object.fromEntries(new FormData(f).entries());f.querySelectorAll('input[type=checkbox]').forEach(c=>data[c.name]=c.checked);
   const endpoint=f.dataset.api;let r=await api(endpoint,{method:'POST',body:JSON.stringify(data)});
   if(endpoint==='/api/login'&&r.csrf)boot.csrf=r.csrf;
   closeModal();await refresh();if(endpoint==='/api/apply-barber'){go('home');toast('Solicitação enviada! Aguarde aprovação da equipe.');return;}if(endpoint==='/api/login'||endpoint==='/api/register'||endpoint==='/api/setup')go('dashboard'===S.user?.role?'dashboard':ADMIN()?'dashboard':BARBER()?'appointments':'account');
   if(endpoint==='/api/password'){go('auth');toast('Senha alterada. Entre novamente.')}
   else toast('Salvo com sucesso!');
 }
 }catch(err){toast(err.message,true)}finally{if(btn&&document.contains(btn))btn.disabled=false}
});
refresh().then(()=>{
 const match=location.hash.match(/^#confirmacao\/(\d+)\/([^/]+)/);
 if(match)go('confirmation');else if(location.hash==='#agendamento')go('booking');
}).catch(error=>{$('#app-content').innerHTML=`<section class="page"><div class="notice red">Não foi possível iniciar o aplicativo: ${e(error.message)}. Execute o servidor Python conforme o LEIA-ME.</div></section>`});
