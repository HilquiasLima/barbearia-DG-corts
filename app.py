"""DG Cortes — MVP funcional. Execute: pip install -r requirements.txt; python app.py"""
from flask import Flask, request, jsonify, session, render_template, g, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import sqlite3, json, os, re, secrets, smtplib, urllib.request, urllib.error
from email.message import EmailMessage
from PIL import Image, ImageOps, UnidentifiedImageError
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE/'.env')
DATA_DIR = Path(os.environ.get('DG_DATA_DIR',str(BASE/'data')))
DB = Path(os.environ.get('DG_DB_PATH', str(BASE/'dgcortes.sqlite3')))
SECRET_FILE = BASE/'.secret_key'
if os.getenv('SECRET_KEY'):
    SECRET = os.environ['SECRET_KEY']
else:
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32), encoding='utf-8')
        try: os.chmod(SECRET_FILE, 0o600)
        except OSError: pass
    SECRET = SECRET_FILE.read_text(encoding='utf-8').strip()

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE') == '1', MAX_CONTENT_LENGTH=12*1024*1024)
TZ = ZoneInfo('America/Bahia')
SITE_TEXT_DEFAULTS = {'hero_eyebrow': 'BARBEARIA • CUIDADO EM CADA DETALHE', 'hero_line1': 'Seu estilo.', 'hero_line2': 'Sua marca.', 'hero_line3': 'DG Cortes.', 'hero_description': 'A experiência de barbearia que combina tradição, personalidade e horário reservado especialmente para você.', 'hero_book_btn': 'Agendar meu horário', 'hero_services_btn': 'Explorar serviços', 'hero_feature1': 'Agendamento online', 'hero_feature2': 'Profissionais à sua escolha', 'hero_feature3': 'Clube de vantagens', 'services_eyebrow': 'O que fazemos', 'services_title': 'Nossos serviços', 'services_description': 'Preços e duração definidos pela barbearia.', 'services_book_btn': 'Agendar', 'services_empty': 'Em breve: serviços e preços.', 'staff_eyebrow': 'Nossa equipe', 'staff_title': 'Escolha seu barbeiro', 'staff_description': 'Profissionais e horários disponíveis em tempo real dentro do sistema.', 'staff_fallback': 'Profissional DG', 'staff_book_btn': 'Reservar horário', 'plans_eyebrow': 'Vantagens de ser cliente', 'plans_title': 'Planos de fidelidade', 'plans_description': 'Solicitação e ativação sujeitas à confirmação da barbearia. Pagamento feito fora do site.', 'plans_request_btn': 'Solicitar plano', 'plans_empty': 'Novos planos em breve.', 'promos_eyebrow': 'OFERTAS ESPECIAIS', 'promos_book_btn': 'Quero aproveitar', 'booking_title': 'Agende seu corte', 'booking_description': 'Escolha um serviço, um profissional e o melhor horário para você.', 'booking_step_service': 'ESCOLHA O SERVIÇO', 'booking_step_barber': 'ESCOLHA O PROFISSIONAL', 'booking_step_date': 'ESCOLHA O DIA', 'booking_step_slot': 'ESCOLHA UM HORÁRIO', 'booking_slots_note': 'Horários exibidos respeitam a duração do serviço, bloqueios e agendamentos existentes.', 'booking_summary_eyebrow': 'RESUMO DO AGENDAMENTO', 'booking_summary_title': 'Está quase pronto.', 'booking_no_slots': 'Sem vagas nesta data. Escolha outro dia ou barbeiro.', 'booking_choose_slot': 'Selecione ao lado', 'booking_confirm_btn': 'Confirmar horário', 'booking_payment_note': 'Não há pagamento online nesta versão. A barbearia confirma valores e cobranças diretamente.', 'auth_eyebrow': 'ÁREA EXCLUSIVA DG CORTES', 'login_title': 'Bem-vindo de volta.', 'login_description': 'Entre como cliente, barbeiro ou administrador usando sua conta.', 'login_panel_title': 'Entrar no sistema', 'register_title': 'Faça parte do clube.', 'register_description': 'Tenha um perfil, solicite planos especiais e acompanhe seus horários.', 'register_panel_title': 'Criar meu perfil', 'auth_guest_btn': 'Agendar como visitante, sem cadastro', 'confirmation_eyebrow': 'AGENDAMENTO REALIZADO', 'confirmation_title': 'Horário confirmado!', 'confirmation_description': 'Seu atendimento foi reservado com sucesso. Guarde seu comprovante.', 'confirmation_notifications_note': 'WhatsApp e e-mail automáticos só serão enviados depois que a barbearia configurar os serviços de mensagens. O comprovante na tela já confirma a reserva.', 'confirmation_home_btn': 'Voltar ao início', 'confirmation_new_btn': 'Agendar outro', 'brand_subtitle': 'BARBEARIA', 'footer_slogan': 'Estilo e tradição', 'footer_note': 'Horários e valores são configurados pela barbearia.'}

DEFAULT_WEEK = {str(i): {'start':'09:00','end':'18:00'} for i in range(6)} | {'6': None}

def now(): return datetime.now(TZ)
def timestamp(): return now().isoformat(timespec='seconds')
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(str(DB), timeout=10, isolation_level=None)
        g.db.row_factory=sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=10000')
    return g.db

@app.teardown_appcontext
def close_db(_):
    db=g.pop('db',None)
    if db is not None: db.close()

def rows(query, params=()): return [dict(r) for r in get_db().execute(query, params).fetchall()]
def one(query, params=()):
    r=get_db().execute(query,params).fetchone()
    return dict(r) if r else None

def init_db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB) as db:
        db.executescript('''
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'client', active INTEGER NOT NULL DEFAULT 1, courtesy_credits INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS barbers (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE NOT NULL REFERENCES users(id), instagram TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, week_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id), title TEXT NOT NULL, price_cents INTEGER NOT NULL, duration INTEGER NOT NULL, plan_eligible INTEGER NOT NULL DEFAULT 1, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS plans (id INTEGER PRIMARY KEY, title TEXT NOT NULL, price_cents INTEGER NOT NULL, days INTEGER NOT NULL, cuts INTEGER NOT NULL, description TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS subscriptions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), plan_id INTEGER NOT NULL REFERENCES plans(id), status TEXT NOT NULL DEFAULT 'pending', starts_at TEXT, ends_at TEXT, cuts_left INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS promotions (id INTEGER PRIMARY KEY, title TEXT NOT NULL, code TEXT UNIQUE NOT NULL, discount INTEGER NOT NULL, valid_until TEXT, active INTEGER NOT NULL DEFAULT 1, public INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS slot_exceptions (id INTEGER PRIMARY KEY, barber_id INTEGER NOT NULL REFERENCES barbers(id), day TEXT NOT NULL, time TEXT NOT NULL, mode TEXT NOT NULL, UNIQUE(barber_id,day,time));
        CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY, barber_id INTEGER NOT NULL REFERENCES barbers(id), user_id INTEGER REFERENCES users(id), customer_name TEXT NOT NULL, customer_phone TEXT NOT NULL, service_id INTEGER NOT NULL REFERENCES services(id), day TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, amount_cents INTEGER NOT NULL, payment_type TEXT NOT NULL DEFAULT 'normal', subscription_id INTEGER REFERENCES subscriptions(id), promo_id INTEGER REFERENCES promotions(id), status TEXT NOT NULL DEFAULT 'scheduled', created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS ix_appointment_time ON appointments(barber_id,day,status);
        CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, actor_id INTEGER, action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, appointment_id INTEGER REFERENCES appointments(id), event TEXT NOT NULL, channel TEXT NOT NULL, recipient TEXT NOT NULL, status TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS barber_applications(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL, instagram TEXT NOT NULL DEFAULT '', password TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
        ''')
        cols={r[1] for r in db.execute('PRAGMA table_info(appointments)')}
        if 'customer_email' not in cols: db.execute("ALTER TABLE appointments ADD COLUMN customer_email TEXT NOT NULL DEFAULT ''")
        if 'confirmation_token' not in cols: db.execute("ALTER TABLE appointments ADD COLUMN confirmation_token TEXT")
        if 'reward_granted' not in cols: db.execute("ALTER TABLE appointments ADD COLUMN reward_granted INTEGER NOT NULL DEFAULT 0")
        subcols={r[1] for r in db.execute('PRAGMA table_info(subscriptions)')}
        if 'origin' not in subcols: db.execute("ALTER TABLE subscriptions ADD COLUMN origin TEXT NOT NULL DEFAULT 'requested'")
        if 'granted_by' not in subcols: db.execute('ALTER TABLE subscriptions ADD COLUMN granted_by INTEGER REFERENCES users(id)')
        if 'grant_note' not in subcols: db.execute("ALTER TABLE subscriptions ADD COLUMN grant_note TEXT NOT NULL DEFAULT ''")
        ucols={r[1] for r in db.execute('PRAGMA table_info(users)')}
        if 'blocked_reason' not in ucols: db.execute("ALTER TABLE users ADD COLUMN blocked_reason TEXT NOT NULL DEFAULT ''")
        if 'avatar_version' not in ucols: db.execute("ALTER TABLE users ADD COLUMN avatar_version TEXT NOT NULL DEFAULT ''")
        defaults={'site_name':'DG Cortes','logo_url':'/static/logo.jpg','background':'#0c0e11','accent':'#e3bb7b','reward_every':'0','site_text':json.dumps(SITE_TEXT_DEFAULTS,ensure_ascii=False),'visibility':json.dumps({key:['guest','client','barber','admin','owner'] for key in ('services','team','plans','promotions','booking','rewards')})}
        for key,value in defaults.items():db.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(key,value))

def err(msg, code=400): return jsonify(error=msg),code

def body(): return request.get_json(silent=True) or {}
def require_fields(data, *fields):
    for key in fields:
        if not str(data.get(key,'')).strip(): raise ValueError(f'Preencha: {key}.')

def settings():return {r['key']:r['value'] for r in rows('SELECT key,value FROM settings')}
def setting(key):
    r=one('SELECT value FROM settings WHERE key=?',(key,))
    return r['value'] if r else ''
def visible(section, role=None):
    role=role or (me() or {}).get('role','guest')
    if role in ('owner','admin'):return True
    try:vis=json.loads(setting('visibility'))
    except (ValueError,TypeError):return True
    return role in vis.get(section,[])
def valid_email(v):return isinstance(v,str) and bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v.strip()))
def notification_entry(aid,event,channel,recipient,status,detail=''):
    get_db().execute('INSERT INTO notifications(appointment_id,event,channel,recipient,status,detail,created_at) VALUES(?,?,?,?,?,?,?)',(aid,event,channel,recipient,status,detail[:250],timestamp()))
def notify_appointment(aid,event='booked'):
    a=one('''SELECT a.*,s.title service_title,u.name barber_name,u.email barber_email,u.phone barber_phone
       FROM appointments a JOIN services s ON s.id=a.service_id JOIN barbers b ON b.id=a.barber_id
       JOIN users u ON u.id=b.user_id WHERE a.id=?''',(aid,))
    if not a:return
    title={'booked':'Agendamento confirmado','cancelled':'Agendamento cancelado','completed':'Atendimento concluído'}.get(event,'Atualização DG Cortes')
    details=f"{title} - {setting('site_name') or 'DG Cortes'}\nCliente: {a['customer_name']}\nServiço: {a['service_title']}\nBarbeiro: {a['barber_name']}\nData: {a['day'][8:10]}/{a['day'][5:7]}/{a['day'][:4]}\nHorário: {a['start_time']}"
    admins=rows("SELECT email FROM users WHERE role IN ('owner','admin') AND active=1")
    emails=set(filter(None,[a['customer_email'],a['barber_email']]+[r['email'] for r in admins]))
    host=os.getenv('SMTP_HOST','');sender=os.getenv('SMTP_FROM','');port=int(os.getenv('SMTP_PORT','587'))
    for address in emails:
        if not host or not sender:notification_entry(aid,event,'email',address,'not_configured');continue
        try:
            msg=EmailMessage();msg['Subject']=title+' | DG Cortes';msg['From']=sender;msg['To']=address;msg.set_content(details)
            with smtplib.SMTP(host,port,timeout=6) as smtp:
                if os.getenv('SMTP_TLS','1')=='1':smtp.starttls()
                if os.getenv('SMTP_USER'):smtp.login(os.getenv('SMTP_USER'),os.getenv('SMTP_PASSWORD',''))
                smtp.send_message(msg)
            notification_entry(aid,event,'email',address,'sent')
        except Exception as ex:notification_entry(aid,event,'email',address,'failed',type(ex).__name__)
    token=os.getenv('WA_ACCESS_TOKEN');phone_id=os.getenv('WA_PHONE_ID');template=os.getenv('WA_TEMPLATE_'+event.upper())
    phones=set(filter(None,[a['customer_phone'],a['barber_phone']]))
    for phone in phones:
        digits=re.sub(r'\D','',phone)
        if len(digits) in (10,11):digits='55'+digits
        if not (token and phone_id and template):notification_entry(aid,event,'whatsapp',digits,'not_configured');continue
        if not re.fullmatch(r'\d{12,13}',digits):notification_entry(aid,event,'whatsapp',digits,'failed','Telefone inválido');continue
        data={'messaging_product':'whatsapp','to':digits,'type':'template','template':{'name':template,'language':{'code':os.getenv('WA_LANGUAGE','pt_BR')},'components':[{'type':'body','parameters':[{'type':'text','text':str(x)} for x in (a['customer_name'],a['barber_name'],a['day'],a['start_time'])]}]}}
        try:
            req=urllib.request.Request(f'https://graph.facebook.com/v22.0/{phone_id}/messages',data=json.dumps(data).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req,timeout=7) as response:response.read()
            notification_entry(aid,event,'whatsapp',digits,'sent')
        except Exception as ex:notification_entry(aid,event,'whatsapp',digits,'failed',type(ex).__name__)

def uid(): return session.get('uid')
def me():
    if not uid(): return None
    user=one('SELECT id,name,phone,email,role,active,courtesy_credits,created_at,avatar_version FROM users WHERE id=?',(uid(),))
    if user: user['avatar_url']=avatar_url(user)
    return user

def avatar_url(user):
    version=user.get('avatar_version')
    return f"/api/avatars/{user['id']}?v={version}" if version else None

def add_avatar_urls(records, user_key='id'):
    for record in records:
        record['avatar_url']=avatar_url({'id':record[user_key], 'avatar_version':record['avatar_version']})
    return records

def auth(roles=None):
    def outer(fn):
        @wraps(fn)
        def inner(*a,**kw):
            u=me()
            if not u or not u['active']: return err('Faça login para continuar.',401)
            if roles and u['role'] not in roles: return err('Acesso não autorizado.',403)
            return fn(*a,**kw)
        return inner
    return outer

def admin(): return me() and me()['role'] in ('owner','admin')
def log(action, detail=''):
    get_db().execute('INSERT INTO audit_log(actor_id,action,detail,created_at) VALUES (?,?,?,?)',(uid(),action,detail,timestamp()))

def money_to_cents(val):
    try: return round(float(str(val).replace(',','.'))*100)
    except: raise ValueError('Informe um preço válido.')

def validate_day(d):
    try: parsed=date.fromisoformat(d)
    except: raise ValueError('Data inválida.')
    if parsed < now().date() or parsed > now().date()+timedelta(days=120): raise ValueError('Agendamentos devem estar entre hoje e os próximos 120 dias.')
    return parsed

def validate_time(t):
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):(?:00|30)',str(t)): raise ValueError('Horário deve ter intervalos de 30 minutos.')

def h2min(t): return int(t[:2])*60+int(t[3:])
def min2h(n): return f'{n//60:02d}:{n%60:02d}'

def barber_record(barber_id): return one('SELECT b.*,u.name,u.active AS user_active FROM barbers b JOIN users u ON u.id=b.user_id WHERE b.id=?',(barber_id,))

def allowed(barber,day,start,duration):
    parsed=validate_day(day)
    minute=h2min(start)
    if parsed == now().date() and datetime.combine(parsed,datetime.min.time(),tzinfo=TZ)+timedelta(minutes=minute) <= now(): return False
    week=json.loads(barber['week_json'])
    hours=week.get(str(parsed.weekday()))
    exceptions={r['time']:r['mode'] for r in rows('SELECT time,mode FROM slot_exceptions WHERE barber_id=? AND day=?',(barber['id'],day))}
    for t in range(minute,minute+duration,30):
        hh=min2h(t)
        default=hours is not None and h2min(hours['start']) <= t and t+30 <= h2min(hours['end'])
        mode=exceptions.get(hh)
        if mode=='blocked' or not(default or mode=='extra'): return False
    return True

def slots_for(barber,day,service):
    duration=service['duration']
    return [min2h(i) for i in range(0,24*60-duration+1,30) if allowed(barber,day,min2h(i),duration) and not one('SELECT id FROM appointments WHERE barber_id=? AND day=? AND status=? AND start_time < ? AND end_time > ?',(barber['id'],day,'scheduled',min2h(i+duration),min2h(i)))]

def recover_credit(appt):
    if appt['payment_type']=='courtesy' and appt['user_id']:
        get_db().execute('UPDATE users SET courtesy_credits=courtesy_credits+1 WHERE id=?',(appt['user_id'],))
    elif appt['payment_type']=='plan' and appt['subscription_id']:
        get_db().execute('UPDATE subscriptions SET cuts_left=cuts_left+1 WHERE id=?',(appt['subscription_id'],))

def cancel_future_for_barber(barber_id):
    for a in rows("SELECT * FROM appointments WHERE barber_id=? AND status='scheduled' AND day >= ?",(barber_id,str(now().date()))):
        get_db().execute("UPDATE appointments SET status='cancelled' WHERE id=?",(a['id'],))
        recover_credit(a)

@app.before_request
def csrf_check():
    if request.method not in ('GET','HEAD','OPTIONS') and request.path.startswith('/api/'):
        if request.headers.get('X-CSRF-Token') != session.get('csrf') or not session.get('csrf'):
            return err('Sessão expirada. Atualize a página e tente novamente.',403)

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['X-Frame-Options']='DENY'
    if os.getenv('COOKIE_SECURE')=='1':
        response.headers['Strict-Transport-Security']='max-age=31536000'
    return response

@app.route('/')
def index(): return render_template('index.html')

@app.get('/api/bootstrap')
def bootstrap():
    if 'csrf' not in session: session['csrf']=secrets.token_urlsafe(28)
    owner=one("SELECT id FROM users WHERE role='owner'")
    return jsonify(installed=bool(owner),requires_setup_token=bool(os.getenv('SETUP_TOKEN') or os.getenv('RENDER')),csrf=session['csrf'], user=me())

@app.post('/api/setup')
def setup():
    d=body()
    required=os.getenv('SETUP_TOKEN','')
    if os.getenv('RENDER') and not required:
        return err('Configuração inicial bloqueada: falta SETUP_TOKEN no servidor.',403)
    if required and not secrets.compare_digest(str(d.get('setup_token','')),required):
        return err('Código de ativação do proprietário incorreto.',403)
    try:
        require_fields(d,'name','phone','email','password')
        if len(d['password'])<8: return err('A senha deve ter no mínimo 8 caracteres.')
        db=get_db(); db.execute('BEGIN IMMEDIATE')
        if one("SELECT id FROM users WHERE role='owner'"):
            db.rollback(); return err('A barbearia já possui administrador principal.',403)
        cur=db.execute('INSERT INTO users(name,phone,email,password,role,created_at) VALUES (?,?,?,?,?,?)', (d['name'].strip(),d['phone'].strip(),d['email'].strip().lower(),generate_password_hash(d['password']),'owner',timestamp()))
        db.execute('INSERT INTO barbers(user_id,instagram,week_json) VALUES (?,?,?)',(cur.lastrowid,d.get('instagram','').strip(),json.dumps(DEFAULT_WEEK)))
        for c in ('Cabelo','Barba','Combos'):
            db.execute('INSERT INTO categories(name) VALUES (?)',(c,))
        db.execute('INSERT INTO services(category_id,title,price_cents,duration,plan_eligible) VALUES (1,?,?,?,1)',('Corte tradicional',3500,30))
        db.execute('INSERT INTO services(category_id,title,price_cents,duration,plan_eligible) VALUES (2,?,?,?,0)',('Barba',2500,30))
        db.execute('INSERT INTO services(category_id,title,price_cents,duration,plan_eligible) VALUES (3,?,?,?,1)',('Cabelo + barba',5500,60))
        db.execute('INSERT INTO plans(title,price_cents,days,cuts,description) VALUES (?,?,?,?,?)',('Mensal DG',10000,30,4,'Quatro cortes elegíveis em 30 dias. Ativação manual.'))
        db.commit(); session['uid']=cur.lastrowid
        return jsonify(ok=True)
    except sqlite3.IntegrityError: get_db().rollback(); return err('E-mail já cadastrado ou valor duplicado.')
    except (ValueError,TypeError) as e: return err(str(e))

@app.post('/api/register')
def register():
    d=body()
    try:
        if not one("SELECT id FROM users WHERE role='owner'"): return err('A barbearia ainda não foi configurada.')
        require_fields(d,'name','phone','email','password')
        if len(d['password'])<8: return err('A senha deve ter no mínimo 8 caracteres.')
        cur=get_db().execute('INSERT INTO users(name,phone,email,password,role,created_at) VALUES(?,?,?,?,?,?)',(d['name'].strip(),d['phone'].strip(),d['email'].strip().lower(),generate_password_hash(d['password']),'client',timestamp()))
        session['uid']=cur.lastrowid
        return jsonify(ok=True)
    except sqlite3.IntegrityError: return err('E-mail já cadastrado.')
    except (ValueError,TypeError) as e: return err(str(e))

@app.post('/api/login')
def login():
    d=body(); u=one('SELECT * FROM users WHERE email=?',(str(d.get('email','')).strip().lower(),))
    if not u or not u['active'] or not check_password_hash(u['password'],str(d.get('password',''))): return err('E-mail ou senha inválidos.',401)
    session.clear();session['csrf']=secrets.token_urlsafe(28);session['uid']=u['id']
    return jsonify(ok=True,csrf=session['csrf'])

@app.post('/api/logout')
def logout(): session.clear();return jsonify(ok=True)

@app.get('/api/state')
def state():
    u=me(); isadmin=u and u['role'] in ('owner','admin'); role=u['role'] if u else 'guest'
    categories=rows('SELECT * FROM categories '+('' if isadmin else 'WHERE active=1')+' ORDER BY id')
    services=rows('SELECT * FROM services '+('' if isadmin else 'WHERE active=1')+' ORDER BY id')
    plans=rows('SELECT * FROM plans '+('' if isadmin else 'WHERE active=1')+' ORDER BY id')
    promos=rows('SELECT * FROM promotions '+('' if isadmin else 'WHERE active=1 AND public=1')+' ORDER BY id DESC')
    if isadmin:
        barbers=rows('SELECT b.id,b.user_id,b.instagram,b.active,b.week_json,u.name,u.phone,u.email,u.role,u.avatar_version,u.active AS user_active FROM barbers b JOIN users u ON u.id=b.user_id ORDER BY b.id')
    elif role=='barber':
        barbers=rows('SELECT b.id,b.user_id,b.instagram,b.active,b.week_json,u.name,u.avatar_version,u.active AS user_active FROM barbers b JOIN users u ON u.id=b.user_id WHERE b.active=1 AND u.active=1 ORDER BY b.id')
    else:
        barbers=rows('SELECT b.id,b.user_id,b.instagram,b.active,u.name,u.avatar_version,u.active AS user_active FROM barbers b JOIN users u ON u.id=b.user_id WHERE b.active=1 AND u.active=1 ORDER BY b.id')
    barbers=add_avatar_urls(barbers,'user_id')
    cfg=settings()
    cfg['visibility']=json.loads(cfg.get('visibility','{}'))
    try: cfg['site_text']={**SITE_TEXT_DEFAULTS,**json.loads(cfg.get('site_text') or '{}')}
    except (TypeError,ValueError): cfg['site_text']=SITE_TEXT_DEFAULTS.copy()
    if not isadmin:
        if not visible('plans',role):plans=[]
        if not visible('promotions',role):promos=[]
    result=dict(user=u,categories=categories,services=services,plans=plans,promotions=promos,barbers=barbers,appointments=[],subscriptions=[],users=[],audit=[],config=cfg,notifications=[],applications=[])
    if u:
        if isadmin:
            result['users']=add_avatar_urls(rows('SELECT id,name,phone,email,role,active,blocked_reason,courtesy_credits,created_at,avatar_version FROM users ORDER BY id DESC'))
            result['appointments']=rows('SELECT a.*,s.title AS service_name,b.user_id AS barber_user_id,u.name AS barber_name FROM appointments a JOIN services s ON s.id=a.service_id JOIN barbers b ON b.id=a.barber_id JOIN users u ON u.id=b.user_id ORDER BY a.day DESC,a.start_time DESC LIMIT 600')
            result['subscriptions']=rows('SELECT x.*,u.name AS customer_name,p.title AS plan_name FROM subscriptions x JOIN users u ON u.id=x.user_id JOIN plans p ON p.id=x.plan_id ORDER BY x.id DESC LIMIT 500')
            result['audit']=rows('SELECT a.*,u.name AS actor_name FROM audit_log a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 30')
            result['notifications']=rows('SELECT * FROM notifications ORDER BY id DESC LIMIT 50')
            result['applications']=rows('SELECT id,name,phone,email,instagram,status,created_at FROM barber_applications ORDER BY id DESC LIMIT 100')
        elif u['role']=='barber':
            b=one('SELECT id FROM barbers WHERE user_id=? AND active=1',(u['id'],))
            if b: result['appointments']=rows('SELECT a.*,s.title AS service_name FROM appointments a JOIN services s ON s.id=a.service_id WHERE a.barber_id=? ORDER BY a.day DESC,a.start_time DESC LIMIT 400',(b['id'],))
        else:
            result['appointments']=rows('SELECT a.*,s.title AS service_name,u.name AS barber_name FROM appointments a JOIN services s ON s.id=a.service_id JOIN barbers b ON b.id=a.barber_id JOIN users u ON u.id=b.user_id WHERE a.user_id=? ORDER BY a.day DESC,a.start_time DESC LIMIT 200',(u['id'],))
            result['subscriptions']=rows('SELECT x.*,p.title AS plan_name FROM subscriptions x JOIN plans p ON p.id=x.plan_id WHERE x.user_id=? ORDER BY x.id DESC',(u['id'],))
    return jsonify(result)

@app.get('/api/availability')
def availability():
    try:
        if not visible('booking'):return err('Agendamentos indisponíveis para seu perfil.',403)
        d=request.args.get('day',''); bid=int(request.args.get('barber_id')); sid=int(request.args.get('service_id'))
        validate_day(d)
        b=barber_record(bid); s=one('SELECT s.* FROM services s JOIN categories c ON c.id=s.category_id WHERE s.id=? AND s.active=1 AND c.active=1',(sid,))
        if not b or not b['active'] or not b['user_active'] or not s: return err('Barbeiro ou serviço indisponível.')
        return jsonify(slots=slots_for(b,d,s))
    except (ValueError,TypeError) as e: return err(str(e))

@app.get('/api/slot-exceptions')
@auth(('owner','admin','barber'))
def exceptions():
    try:
        bid=int(request.args.get('barber_id'))
        b=barber_record(bid)
        if not b: return err('Barbeiro não localizado.',404)
        if not admin() and b['user_id']!=uid(): return err('Sem permissão.',403)
        d=request.args.get('day'); validate_day(d)
        return jsonify(rows=rows('SELECT * FROM slot_exceptions WHERE barber_id=? AND day=? ORDER BY time',(bid,d)))
    except (ValueError,TypeError) as e: return err(str(e))

@app.post('/api/slot-exceptions')
@auth(('owner','admin','barber'))
def slot_update():
    d=body()
    try:
        bid=int(d['barber_id']);day=d['day'];hour=d['time'];mode=d['mode']; validate_day(day);validate_time(hour)
        b=barber_record(bid)
        if not b: return err('Barbeiro não localizado.',404)
        if not admin() and b['user_id']!=uid(): return err('Sem permissão.',403)
        if mode not in ('blocked','extra','clear'): return err('Tipo de ajuste inválido.')
        db=get_db(); db.execute('BEGIN IMMEDIATE')
        if mode=='clear': db.execute('DELETE FROM slot_exceptions WHERE barber_id=? AND day=? AND time=?',(bid,day,hour))
        else:
            if mode=='blocked' and one("SELECT id FROM appointments WHERE barber_id=? AND day=? AND status='scheduled' AND start_time < ? AND end_time > ?",(bid,day,min2h(h2min(hour)+30),hour)):
                db.rollback(); return err('Este horário já tem agendamento. Cancele primeiro.')
            db.execute('INSERT INTO slot_exceptions(barber_id,day,time,mode) VALUES(?,?,?,?) ON CONFLICT(barber_id,day,time) DO UPDATE SET mode=excluded.mode',(bid,day,hour,mode))
        log('horario_alterado',f'{bid} {day} {hour} {mode}');db.commit();return jsonify(ok=True)
    except (ValueError,TypeError,KeyError) as e: return err(str(e))

@app.post('/api/book')
def book():
    d=body(); db=get_db()
    try:
        if not visible('booking'):return err('Agendamentos indisponíveis para seu perfil.',403)
        bid=int(d['barber_id']);sid=int(d['service_id']); day=d['day'];start=d['time'];validate_day(day);validate_time(start)
        b=barber_record(bid);s=one('SELECT s.* FROM services s JOIN categories c ON c.id=s.category_id WHERE s.id=? AND s.active=1 AND c.active=1',(sid,))
        if not b or not b['active'] or not b['user_active'] or not s: return err('Barbeiro ou serviço indisponível.')
        u=me()
        if u and not u['active']:return err('Perfil bloqueado. Fale com a barbearia.',403)
        client_id=u['id'] if u and u['role']=='client' else None
        name=u['name'] if client_id else str(d.get('name','')).strip()
        phone=u['phone'] if client_id else str(d.get('phone','')).strip()
        customer_email=u['email'] if client_id else str(d.get('email','')).strip().lower()
        if len(name.split())<2 or len(phone)<8 or not valid_email(customer_email): return err('Informe nome completo, WhatsApp e e-mail válido para agendar.')
        if one('SELECT id FROM users WHERE active=0 AND phone=?',(phone,)):return err('Este telefone está bloqueado para agendamentos. Contate a barbearia.',403)
        end=min2h(h2min(start)+s['duration'])
        db.execute('BEGIN IMMEDIATE')
        if not allowed(b,day,start,s['duration']): db.rollback();return err('Horário fora da disponibilidade.')
        if one("SELECT id FROM appointments WHERE barber_id=? AND day=? AND status='scheduled' AND start_time < ? AND end_time > ?",(bid,day,end,start)):
            db.rollback();return err('Horário acabou de ser ocupado. Escolha outro.')
        kind='normal'; price=s['price_cents']; sub_id=None; promo_id=None
        if client_id and d.get('use_courtesy'):
            if u['courtesy_credits']<=0: db.rollback();return err('Você não possui cortesias disponíveis.')
            db.execute('UPDATE users SET courtesy_credits=courtesy_credits-1 WHERE id=?',(client_id,));kind='courtesy';price=0
        elif client_id and d.get('use_plan'):
            if not s['plan_eligible']: db.rollback();return err('Este serviço não aceita plano.')
            sub=one("SELECT * FROM subscriptions WHERE user_id=? AND status='active' AND ends_at>=? AND cuts_left>0 ORDER BY id DESC LIMIT 1",(client_id,day))
            if not sub or sub['starts_at']>day: db.rollback();return err('Plano sem cortes disponíveis para esta data.')
            db.execute('UPDATE subscriptions SET cuts_left=cuts_left-1 WHERE id=?',(sub['id'],)); sub_id=sub['id'];kind='plan';price=0
        elif d.get('promo'):
            code=str(d['promo']).strip().upper();p=one('SELECT * FROM promotions WHERE code=? AND active=1',(code,))
            if not p or (p['valid_until'] and p['valid_until']<day): db.rollback();return err('Cupom inexistente ou vencido.')
            kind='promo';promo_id=p['id'];price=round(price*(100-p['discount'])/100)
        confirmation_token=secrets.token_urlsafe(28)
        cur=db.execute('INSERT INTO appointments(barber_id,user_id,customer_name,customer_phone,customer_email,service_id,day,start_time,end_time,amount_cents,payment_type,subscription_id,promo_id,created_at,confirmation_token) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,client_id,name,phone,customer_email,sid,day,start,end,price,kind,sub_id,promo_id,timestamp(),confirmation_token))
        db.commit()
        notify_appointment(cur.lastrowid,'booked')
        return jsonify(ok=True,id=cur.lastrowid,amount_cents=price,token=confirmation_token,barber_name=b['name'],service_name=s['title'],day=day,time=start,customer_name=name,notifications='automaticas se configuradas')
    except (ValueError,TypeError,KeyError) as e:
        if db.in_transaction:db.rollback()
        return err(str(e))

@app.post('/api/appointments/<int:aid>/status')
@auth()
def appointment_status(aid):
    d=body();status=d.get('status')
    if status not in ('cancelled','completed'): return err('Status inválido.')
    a=one('SELECT * FROM appointments WHERE id=?',(aid,))
    if not a: return err('Agendamento não localizado.',404)
    u=me()
    if not admin():
        isbarber=u['role']=='barber' and one('SELECT id FROM barbers WHERE id=? AND user_id=?',(a['barber_id'],uid()))
        isclient=u['role']=='client' and a['user_id']==uid() and status=='cancelled'
        if not (isbarber or isclient): return err('Sem permissão.',403)
    if a['status']!='scheduled': return err('Este agendamento já foi finalizado.')
    if status=='completed' and (a['day']>str(now().date()) or (a['day']==str(now().date()) and a['start_time']>now().strftime('%H:%M'))):
        return err('Não é possível concluir um atendimento futuro.')
    db=get_db(); db.execute('BEGIN IMMEDIATE')
    fresh=one('SELECT * FROM appointments WHERE id=?',(aid,))
    if fresh['status']!='scheduled':db.rollback();return err('Atendimento já atualizado.')
    db.execute('UPDATE appointments SET status=? WHERE id=?',(status,aid))
    if status=='cancelled':recover_credit(fresh)
    if status=='completed' and fresh['user_id']:
        every=int(setting('reward_every') or 0)
        if every>0:
            count=one("SELECT COUNT(*) AS n FROM appointments WHERE user_id=? AND status='completed'",(fresh['user_id'],))['n']
            if count%every==0:
                db.execute('UPDATE users SET courtesy_credits=courtesy_credits+1 WHERE id=?',(fresh['user_id'],))
                db.execute('UPDATE appointments SET reward_granted=1 WHERE id=?',(aid,))
    log('agendamento_'+status,str(aid));db.commit()
    notify_appointment(aid,status)
    return jsonify(ok=True)

@app.post('/api/subscriptions/request')
@auth(('client',))
def request_plan():
    try: pid=int(body()['plan_id'])
    except: return err('Plano inválido.')
    p=one('SELECT * FROM plans WHERE id=? AND active=1',(pid,))
    if not p:return err('Plano indisponível.')
    if one("SELECT id FROM subscriptions WHERE user_id=? AND status IN ('pending','active') AND (status='pending' OR ends_at>=?)",(uid(),str(now().date()))):return err('Você já possui um plano ativo ou em análise.')
    get_db().execute('INSERT INTO subscriptions(user_id,plan_id,created_at) VALUES(?,?,?)',(uid(),pid,timestamp()))
    return jsonify(ok=True)

@app.post('/api/users/<int:target>/grant-plan')
@auth(('owner','admin'))
def grant_plan_to_client(target):
    """Ativa um plano existente por cortesia, com registro do administrador."""
    d=body()
    try: plan_id=int(d.get('plan_id'))
    except (ValueError,TypeError): return err('Selecione um plano válido.')
    note=str(d.get('note') or '').strip()
    if len(note)>250:return err('A observação deve ter no máximo 250 caracteres.')
    db=get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        client=one('SELECT id,name,role,active FROM users WHERE id=?',(target,))
        if not client or client['role']!='client' or not client['active']:
            db.rollback();return err('Selecione um perfil de cliente ativo.')
        plan=one('SELECT id,title,days,cuts FROM plans WHERE id=?',(plan_id,))
        if not plan or plan['days']<1 or plan['cuts']<1:
            db.rollback();return err('Plano não encontrado ou inválido.')
        busy=one("SELECT id FROM subscriptions WHERE user_id=? AND (status='pending' OR (status='active' AND ends_at>=?))",(target,str(now().date())))
        if busy:
            db.rollback();return err('Este cliente já tem um plano ativo ou uma solicitação pendente. Resolva-a primeiro.')
        start=now().date()
        end=start+timedelta(days=plan['days']-1)
        cur=db.execute("INSERT INTO subscriptions(user_id,plan_id,status,starts_at,ends_at,cuts_left,created_at,origin,granted_by,grant_note) VALUES(?,?,'active',?,?,?,?,?,?,?)",
            (target,plan_id,str(start),str(end),plan['cuts'],timestamp(),'courtesy',uid(),note))
        log('plano_cortesia_atribuido',f"cliente={target};plano={plan_id};assinatura={cur.lastrowid}")
        db.commit()
        return jsonify(ok=True,subscription_id=cur.lastrowid)
    except sqlite3.Error:
        if db.in_transaction:db.rollback()
        return err('Não foi possível conceder o plano. Tente novamente.',500)

@app.post('/api/subscriptions/<int:sid>/status')
@auth(('owner','admin'))
def subscription_status(sid):
    status=body().get('status')
    if status not in ('active','rejected','cancelled'): return err('Status inválido.')
    sub=one('SELECT x.*,p.days,p.cuts FROM subscriptions x JOIN plans p ON p.id=x.plan_id WHERE x.id=?',(sid,))
    if not sub:return err('Solicitação inexistente.',404)
    if sub['status'] not in ('pending','active'): return err('Não é possível alterar esta solicitação.')
    if status=='active' and sub['status']!='pending': return err('O plano já foi ativado.')
    db=get_db()
    if status=='active':
        if one("SELECT id FROM subscriptions WHERE user_id=? AND status='active' AND ends_at>=? AND id<>?",(sub['user_id'],str(now().date()),sid)):
            return err('Cliente já possui outro plano ativo.')
        start=now().date();end=start+timedelta(days=sub['days']-1)
        db.execute('UPDATE subscriptions SET status=?,starts_at=?,ends_at=?,cuts_left=? WHERE id=?',('active',str(start),str(end),sub['cuts'],sid))
    elif status=='cancelled':
        if one("SELECT id FROM appointments WHERE subscription_id=? AND status='scheduled'",(sid,)):return err('Cancele os agendamentos vinculados antes de encerrar o plano.')
        db.execute('UPDATE subscriptions SET status=? WHERE id=?',(status,sid))
    else:
        if sub['status']!='pending':return err('Somente solicitações pendentes podem ser rejeitadas.')
        db.execute('UPDATE subscriptions SET status=? WHERE id=?',(status,sid))
    log('plano_'+status,str(sid));return jsonify(ok=True)

@app.post('/api/staff')
@auth(('owner','admin'))
def add_staff():
    d=body();db=get_db()
    try:
        require_fields(d,'name','phone','email','password')
        if len(d['password'])<8:return err('Senha com no mínimo 8 caracteres.')
        db.execute('BEGIN IMMEDIATE')
        count=one("SELECT COUNT(*) AS n FROM barbers b JOIN users u ON u.id=b.user_id WHERE u.role<>'owner' AND b.active=1")['n']
        if count>=5:db.rollback();return err('Limite de cinco barbeiros além do proprietário atingido.')
        cur=db.execute('INSERT INTO users(name,phone,email,password,role,created_at) VALUES(?,?,?,?,?,?)',(d['name'].strip(),d['phone'].strip(),d['email'].strip().lower(),generate_password_hash(d['password']),'barber',timestamp()))
        db.execute('INSERT INTO barbers(user_id,instagram,week_json) VALUES(?,?,?)',(cur.lastrowid,str(d.get('instagram','')).strip(),json.dumps(DEFAULT_WEEK)))
        log('barbeiro_adicionado',str(cur.lastrowid));db.commit();return jsonify(ok=True)
    except sqlite3.IntegrityError: db.rollback();return err('Este e-mail já está em uso.')
    except (ValueError,TypeError) as e:
        if db.in_transaction:db.rollback()
        return err(str(e))

@app.post('/api/staff/<int:bid>/active')
@auth(('owner','admin'))
def staff_active(bid):
    b=barber_record(bid)
    if not b:return err('Barbeiro não existe.',404)
    if one('SELECT role FROM users WHERE id=?',(b['user_id'],))['role']=='owner':return err('Não é possível desativar o proprietário.')
    active=int(bool(body().get('active')));db=get_db();db.execute('BEGIN IMMEDIATE')
    if active and not b['active']:
        count=one("SELECT COUNT(*) AS n FROM barbers b JOIN users u ON u.id=b.user_id WHERE u.role<>'owner' AND b.active=1")['n']
        if count>=5:db.rollback();return err('Limite de cinco barbeiros atingido.')
    db.execute('UPDATE barbers SET active=? WHERE id=?',(active,bid))
    db.execute('UPDATE users SET active=? WHERE id=?',(active,b['user_id']))
    if not active: cancel_future_for_barber(bid)
    log('barbeiro_ativo',f'{bid}:{active}');db.commit();return jsonify(ok=True)

@app.post('/api/users/<int:target>/role')
@auth(('owner','admin'))
def change_role(target):
    if target==uid():return err('Você não pode alterar seu próprio nível de acesso.')
    user=one('SELECT * FROM users WHERE id=?',(target,))
    if not user:return err('Usuário não encontrado.',404)
    if user['role']=='owner':return err('O administrador principal é protegido.',403)
    if not user['active']:return err('Não é possível promover um perfil inativo.')
    role=body().get('role')
    if role=='admin': target_role='admin'
    elif role=='regular': target_role='barber' if one('SELECT id FROM barbers WHERE user_id=?',(target,)) else 'client'
    else:return err('Papel inválido.')
    get_db().execute('UPDATE users SET role=? WHERE id=?',(target_role,target))
    log('perfil_promovido_ou_rebaixado',f'{target}:{target_role}');return jsonify(ok=True)

@app.post('/api/users/<int:target>/courtesy')
@auth(('owner','admin'))
def add_courtesy(target):
    try:delta=int(body()['delta'])
    except:return err('Quantidade inválida.')
    if delta==0 or abs(delta)>100:return err('Informe uma quantidade entre -100 e 100, diferente de zero.')
    u=one('SELECT * FROM users WHERE id=?',(target,))
    if not u:return err('Cliente não localizado.',404)
    if u['courtesy_credits']+delta<0:return err('Saldo de cortesias insuficiente.')
    get_db().execute('UPDATE users SET courtesy_credits=courtesy_credits+? WHERE id=?',(delta,target))
    log('cortesia',f'{target}:{delta}');return jsonify(ok=True)

@app.post('/api/users/<int:target>/active')
@auth(('owner','admin'))
def user_active(target):
    if target==uid():return err('Não é possível desativar seu próprio acesso.')
    u=one('SELECT * FROM users WHERE id=?',(target,))
    if not u:return err('Perfil não localizado.',404)
    if u['role']=='owner':return err('O proprietário não pode ser desativado.',403)
    if one('SELECT id FROM barbers WHERE user_id=?',(target,)):return err('Use a gestão de barbeiros para desativar este usuário.')
    active=int(bool(body().get('active')));db=get_db();db.execute('BEGIN IMMEDIATE')
    if not active:
        for a in rows("SELECT * FROM appointments WHERE user_id=? AND status='scheduled'",(target,)):
            db.execute("UPDATE appointments SET status='cancelled' WHERE id=?",(a['id'],));recover_credit(a)
    reason=str(body().get('reason','')).strip()[:180] if not active else ''
    db.execute('UPDATE users SET active=?,blocked_reason=? WHERE id=?',(active,reason,target))
    log('usuario_ativo',f'{target}:{active}');db.commit();return jsonify(ok=True)

@app.post('/api/categories')
@auth(('owner','admin'))
def save_category():
    d=body()
    try:
        require_fields(d,'name');key=d.get('id');active=int(bool(d.get('active',True)))
        if key: get_db().execute('UPDATE categories SET name=?,active=? WHERE id=?',(d['name'].strip(),active,int(key)))
        else:get_db().execute('INSERT INTO categories(name,active) VALUES(?,?)',(d['name'].strip(),active))
        log('categoria_alterada',d['name']);return jsonify(ok=True)
    except sqlite3.IntegrityError:return err('Categoria já cadastrada.')
    except (ValueError,TypeError) as e:return err(str(e))

@app.post('/api/services')
@auth(('owner','admin'))
def save_service():
    d=body()
    try:
        require_fields(d,'title');cat=int(d['category_id']);duration=int(d['duration']);price=money_to_cents(d['price']);
        if duration<30 or duration>240 or duration%30 or price<0:return err('Duração deve ser múltipla de 30 minutos e preço não pode ser negativo.')
        if not one('SELECT id FROM categories WHERE id=?',(cat,)):return err('Categoria inexistente.')
        args=(cat,d['title'].strip(),price,duration,int(bool(d.get('plan_eligible'))),int(bool(d.get('active',True))))
        if d.get('id'):get_db().execute('UPDATE services SET category_id=?,title=?,price_cents=?,duration=?,plan_eligible=?,active=? WHERE id=?',args+(int(d['id']),))
        else:get_db().execute('INSERT INTO services(category_id,title,price_cents,duration,plan_eligible,active) VALUES(?,?,?,?,?,?)',args)
        log('servico_alterado',d['title']);return jsonify(ok=True)
    except (ValueError,TypeError,KeyError) as e:return err(str(e))

@app.post('/api/plans')
@auth(('owner','admin'))
def save_plan():
    d=body()
    try:
        require_fields(d,'title');price=money_to_cents(d['price']);days=int(d['days']);cuts=int(d['cuts'])
        if price<0 or days<1 or days>365 or cuts<1 or cuts>100:return err('Preço, dias ou cortes inválidos.')
        args=(d['title'].strip(),price,days,cuts,str(d.get('description','')).strip(),int(bool(d.get('active',True))))
        if d.get('id'):get_db().execute('UPDATE plans SET title=?,price_cents=?,days=?,cuts=?,description=?,active=? WHERE id=?',args+(int(d['id']),))
        else:get_db().execute('INSERT INTO plans(title,price_cents,days,cuts,description,active) VALUES(?,?,?,?,?,?)',args)
        log('plano_alterado',d['title']);return jsonify(ok=True)
    except (ValueError,TypeError,KeyError) as e:return err(str(e))

@app.post('/api/promotions')
@auth(('owner','admin'))
def save_promotion():
    d=body()
    try:
        require_fields(d,'title','code');discount=int(d['discount']);
        if discount<1 or discount>100:return err('Desconto entre 1% e 100%.')
        until=str(d.get('valid_until') or '')
        if until: date.fromisoformat(until)
        args=(d['title'].strip(),d['code'].strip().upper(),discount,until,int(bool(d.get('active',True))),int(bool(d.get('public',True))))
        if d.get('id'):get_db().execute('UPDATE promotions SET title=?,code=?,discount=?,valid_until=?,active=?,public=? WHERE id=?',args+(int(d['id']),))
        else:get_db().execute('INSERT INTO promotions(title,code,discount,valid_until,active,public) VALUES(?,?,?,?,?,?)',args)
        log('promocao_alterada',d['code']);return jsonify(ok=True)
    except sqlite3.IntegrityError:return err('Código promocional já existe.')
    except (ValueError,TypeError) as e:return err(str(e))


@app.get('/api/appointments/<int:aid>/confirmation')
def appointment_confirmation(aid):
    token=request.args.get('token','')
    a=one('''SELECT a.id,a.user_id,a.confirmation_token,a.customer_name,a.day,a.start_time,a.end_time,a.status,a.amount_cents,
        s.title service_name,u.name barber_name FROM appointments a
        JOIN services s ON s.id=a.service_id JOIN barbers b ON b.id=a.barber_id
        JOIN users u ON u.id=b.user_id WHERE a.id=?''',(aid,))
    if not a:return err('Não encontrado.',404)
    if not (token and secrets.compare_digest(token,a['confirmation_token'] or '')) and not (uid() and (a['user_id']==uid() or admin())):
        return err('Acesso negado.',403)
    return jsonify({k:v for k,v in a.items() if k not in ('user_id','confirmation_token')})

@app.post('/api/settings')
@auth(('owner','admin'))
def change_settings():
    d=body()
    try:
        if 'site_name' in d:
            name=str(d['site_name']).strip()
            if not 2<=len(name)<=50:return err('Nome da barbearia inválido.')
            get_db().execute('UPDATE settings SET value=? WHERE key=?',(name,'site_name'))
        for key in ('background','accent'):
            if key in d:
                color=str(d[key])
                if not re.fullmatch('#[0-9a-fA-F]{6}',color):return err('Cor inválida.')
                get_db().execute('UPDATE settings SET value=? WHERE key=?',(color,key))
        if 'reward_every' in d:
            every=int(d['reward_every'])
            if every<0 or every>100:return err('Quantidade deve ser de 0 até 100.')
            get_db().execute('UPDATE settings SET value=? WHERE key=?',(str(every),'reward_every'))
        if 'site_text' in d:
            edits=d['site_text']
            if not isinstance(edits,dict) or any(key not in SITE_TEXT_DEFAULTS for key in edits):
                return err('Campo de texto não permitido.')
            clean={}
            for key,value in edits.items():
                if not isinstance(value,str): return err('Informe textos válidos.')
                value=value.strip()
                maximum=650 if ('description' in key or 'note' in key) else 140
                if len(value)>maximum: return err(f'Texto muito longo: {key} (máximo {maximum} caracteres).')
                # Texto puro: todo conteúdo é escapado pelo frontend antes de aparecer no HTML.
                clean[key]=value
            previous=json.loads(setting('site_text') or '{}')
            merged={**SITE_TEXT_DEFAULTS,**previous,**clean}
            get_db().execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                             ('site_text',json.dumps(merged,ensure_ascii=False)))
        if 'visibility' in d:
            vis=d['visibility']; keys=('services','team','plans','promotions','booking','rewards')
            if not isinstance(vis,dict) or any(k not in keys or not isinstance(v,list) or any(r not in ('guest','client','barber','admin','owner') for r in v) for k,v in vis.items()):return err('Permissões inválidas.')
            saved=json.loads(setting('visibility'))
            for key,roles in vis.items():saved[key]=sorted(set(roles)|{'owner','admin'})
            get_db().execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(saved), 'visibility'))
        log('configuracao_geral','aparencia_recompensas_visibilidade')
        return jsonify(ok=True)
    except (ValueError,TypeError) as exc:return err(str(exc))

AVATAR_DIR = DATA_DIR/'avatars'

@app.get('/api/avatars/<int:target>')
def get_avatar(target):
    target_user=one('SELECT id,role,active,avatar_version FROM users WHERE id=?',(target,))
    if not target_user or not target_user['avatar_version']:
        return err('Foto não encontrada.',404)
    viewer=me()
    is_self=bool(viewer and viewer['id']==target)
    is_admin=bool(viewer and viewer['role'] in ('owner','admin') and viewer['active'])
    is_public_barber=bool(target_user['active'] and one('SELECT id FROM barbers WHERE user_id=? AND active=1',(target,)))
    # Clients' images aren't public. A barber may see a customer's image only when
    # the customer has an appointment with that barber.
    is_linked_barber=bool(viewer and viewer['active'] and one("""SELECT a.id FROM appointments a
        JOIN barbers b ON b.id=a.barber_id
        WHERE a.user_id=? AND b.user_id=? LIMIT 1""",(target,viewer['id'])))
    if not (is_self or is_admin or is_public_barber or is_linked_barber):
        return err('Você não tem permissão para ver esta foto.',403)
    path=AVATAR_DIR/f'{target}.webp'
    if not path.is_file():return err('Foto não encontrada.',404)
    response=send_file(path,mimetype='image/webp',conditional=True)
    response.headers['Cache-Control']='private, max-age=300'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.post('/api/profile/photo')
@auth()
def upload_profile_photo():
    target_raw=request.form.get('user_id',str(uid()))
    try:target=int(target_raw)
    except (ValueError,TypeError):return err('Perfil inválido.')
    if target!=uid() and not admin():return err('Você só pode editar sua própria foto.',403)
    target_user=one('SELECT id,active,role FROM users WHERE id=?',(target,))
    if not target_user or not target_user['active']:return err('Perfil não localizado ou desativado.',404)
    if target_user['role']=='owner' and target!=uid():return err('A foto do proprietário só pode ser alterada por ele.',403)
    uploaded=request.files.get('photo')
    if not uploaded:return err('Selecione uma foto JPG, PNG ou WEBP.')
    try:
        uploaded.stream.seek(0,2)
        total=uploaded.stream.tell()
        uploaded.stream.seek(0)
        if total>10*1024*1024:return err('A foto deve ter no máximo 10 MB.')
        if total==0:return err('A imagem está vazia.')
        pic=Image.open(uploaded.stream)
        if pic.format not in ('JPEG','PNG','WEBP'):return err('Use JPG, PNG ou WEBP.')
        width,height=pic.size
        if min(width,height)<100:return err('Envie uma foto com pelo menos 100 pixels em cada lado.')
        if width>8000 or height>8000 or width*height>32_000_000:
            return err('Imagem muito grande. Limite de 32 megapixels e 8000 px por lado.')
        pic=ImageOps.exif_transpose(pic)
        pic.thumbnail((1600,1600),Image.Resampling.LANCZOS)
        if pic.mode=='RGBA' or ('transparency' in pic.info):
            rgba=pic.convert('RGBA')
            background=Image.new('RGB',rgba.size,(242,242,242))
            background.paste(rgba,mask=rgba.getchannel('A'))
            pic=background
        else:pic=pic.convert('RGB')
        AVATAR_DIR.mkdir(parents=True,exist_ok=True)
        destination=AVATAR_DIR/f'{target}.webp'
        temp_file=AVATAR_DIR/f'.{target}-{secrets.token_hex(8)}.webp'
        try:
            pic.save(temp_file,'WEBP',quality=90,method=5)
            os.replace(temp_file,destination)
        finally:
            temp_file.unlink(missing_ok=True)
        version=secrets.token_hex(6)
        get_db().execute('UPDATE users SET avatar_version=? WHERE id=?',(version,target))
        log('foto_perfil_atualizada',str(target))
        return jsonify(ok=True,avatar_url=f'/api/avatars/{target}?v={version}')
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
        return err('Imagem inválida ou corrompida. Envie JPG, PNG ou WEBP.')

@app.post('/api/profile/photo/remove')
@auth()
def remove_profile_photo():
    d=body()
    try:target=int(d.get('user_id',uid()))
    except (ValueError,TypeError):return err('Perfil inválido.')
    if target!=uid() and not admin():return err('Você só pode remover sua própria foto.',403)
    target_user=one('SELECT id,role FROM users WHERE id=?',(target,))
    if not target_user:return err('Perfil não localizado.',404)
    if target_user['role']=='owner' and target!=uid():return err('A foto do proprietário só pode ser alterada por ele.',403)
    get_db().execute("UPDATE users SET avatar_version='' WHERE id=?",(target,))
    (AVATAR_DIR/f'{target}.webp').unlink(missing_ok=True)
    log('foto_perfil_removida',str(target))
    return jsonify(ok=True)

@app.get('/api/branding/logo')
def get_custom_logo():
    location=DATA_DIR/'branding'/'logo_custom.jpg'
    if not location.is_file():return err('Logo não encontrada.',404)
    resp=send_file(location,mimetype='image/jpeg',conditional=True)
    resp.headers['Cache-Control']='public, max-age=300'
    return resp

@app.post('/api/branding/logo')
@auth(('owner','admin'))
def upload_logo():
    uploaded=request.files.get('logo')
    if not uploaded:return err('Selecione uma imagem.')
    uploaded.stream.seek(0,2)
    logo_size=uploaded.stream.tell()
    uploaded.stream.seek(0)
    if logo_size>3*1024*1024:return err('Logotipo deve ter até 3 MB.')
    try:
        uploaded.stream.seek(0)
        pic=Image.open(uploaded.stream)
        if pic.width>4096 or pic.height>4096 or pic.width<200 or pic.height<100:return err('Use imagem entre 200 e 4096 pixels.')
        pic=pic.convert('RGB')
        folder=DATA_DIR/'branding';folder.mkdir(parents=True,exist_ok=True)
        location=folder/'logo_custom.jpg';pic.save(location,'JPEG',quality=90,optimize=True)
        url='/api/branding/logo?v='+secrets.token_hex(5)
        get_db().execute('UPDATE settings SET value=? WHERE key=?',(url,'logo_url'))
        log('logo_alterada','logo da barbearia')
        return jsonify(ok=True,logo_url=url)
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):return err('Arquivo inválido. Envie PNG, JPG ou WEBP.')

@app.post('/api/barbers/<int:bid>/week')
@auth(('owner','admin','barber'))
def update_week(bid):
    b=barber_record(bid)
    if not b:return err('Barbeiro inexistente.',404)
    if not admin() and b['user_id']!=uid():return err('Sem permissão.',403)
    d=body().get('week')
    if not isinstance(d,dict):return err('Agenda semanal inválida.')
    try:
        new={}
        for day in range(7):
            val=d.get(str(day))
            if val is None:new[str(day)]=None;continue
            start=val['start'];end=val['end'];validate_time(start);validate_time(end)
            if h2min(end)<=h2min(start):return err('Abertura deve ser antes do fechamento.')
            new[str(day)]={'start':start,'end':end}
        get_db().execute('UPDATE barbers SET week_json=? WHERE id=?',(json.dumps(new),bid))
        log('agenda_semanal_alterada',str(bid));return jsonify(ok=True)
    except (KeyError,ValueError,TypeError) as ex:return err(str(ex))

@app.post('/api/apply-barber')
def apply_barber():
    d=body()
    try:
        require_fields(d,'name','phone','email','password')
        email=str(d['email']).strip().lower()
        if len(d['name'].split())<2 or not valid_email(email) or len(str(d['password']))<8 or len(str(d['phone']))<8:return err('Informe nome completo, contato, e-mail válido e senha de 8 caracteres.')
        if one('SELECT id FROM users WHERE email=?',(email,)) or one("SELECT id FROM barber_applications WHERE email=? AND status='pending'",(email,)):return err('E-mail já cadastrado ou em análise.')
        get_db().execute('INSERT INTO barber_applications(name,phone,email,instagram,password,created_at) VALUES(?,?,?,?,?,?)',(d['name'].strip(),d['phone'].strip(),email,str(d.get('instagram','')).strip(),generate_password_hash(d['password']),timestamp()))
        return jsonify(ok=True)
    except (ValueError,TypeError) as ex:return err(str(ex))

@app.post('/api/applications/<int:aid>/status')
@auth(('owner','admin'))
def approve_barber(aid):
    choice=body().get('status'); db=get_db()
    if choice not in ('approved','rejected'):return err('Decisão inválida.')
    try:
        db.execute('BEGIN IMMEDIATE')
        appl=one('SELECT * FROM barber_applications WHERE id=?',(aid,))
        if not appl or appl['status']!='pending':db.rollback();return err('Solicitação indisponível.')
        if choice=='approved':
            count=one("SELECT COUNT(*) AS n FROM barbers b JOIN users u ON u.id=b.user_id WHERE u.role<>'owner' AND b.active=1")['n']
            if count>=5:db.rollback();return err('Limite de cinco barbeiros atingido.')
            cur=db.execute('INSERT INTO users(name,phone,email,password,role,created_at) VALUES (?,?,?,?,?,?)',(appl['name'],appl['phone'],appl['email'],appl['password'],'barber',timestamp()))
            db.execute('INSERT INTO barbers(user_id,instagram,week_json) VALUES(?,?,?)',(cur.lastrowid,appl['instagram'],json.dumps(DEFAULT_WEEK)))
        db.execute('UPDATE barber_applications SET status=? WHERE id=?',(choice,aid))
        log('solicitacao_barbeiro_'+choice,str(aid));db.commit();return jsonify(ok=True)
    except sqlite3.IntegrityError:db.rollback();return err('E-mail já em uso.')

@app.post('/api/password')
@auth()
def change_password():
    d=body();u=one('SELECT password FROM users WHERE id=?',(uid(),))
    if not check_password_hash(u['password'],str(d.get('old',''))): return err('Senha atual incorreta.')
    if len(str(d.get('new','')))<8:return err('Nova senha deve ter pelo menos 8 caracteres.')
    get_db().execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(d['new']),uid()))
    session.clear();return jsonify(ok=True)

@app.errorhandler(500)
def internal(_):
    app.logger.exception('Unexpected app exception')
    return err('Erro interno. Verifique o terminal do servidor.',500)

init_db()
if __name__ == '__main__':
    app.run(host='127.0.0.1',port=int(os.environ.get('PORT','5000')),debug=os.getenv('FLASK_DEBUG')=='1')
