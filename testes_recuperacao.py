"""Testa funções reais do app.py sem instalar Flask; simula SQLite, SMTP e sessão.
Execute: python testes_recuperacao.py
"""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import ast, hashlib, hmac, json, os, re, secrets, sqlite3, tempfile, time
from email.message import EmailMessage

ROOT=Path(__file__).resolve().parent
source=(ROOT/'app.py').read_text('utf-8')
tree=ast.parse(source)
funcs={n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

def extract(name,scope):
    orig=funcs[name]
    cloned=ast.FunctionDef(name=orig.name,args=orig.args,body=orig.body,decorator_list=[],returns=orig.returns,type_comment=None,type_params=[])
    ast.fix_missing_locations(cloned)
    exec(compile(ast.Module(body=[cloned],type_ignores=[]), str(ROOT/'app.py'),'exec'),scope)
    return scope[name]

class SMTPFake:
    mails=[]
    def __init__(self,*a,**kw):pass
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def starttls(self):pass
    def login(self,*a):pass
    def send_message(self,m):self.mails.append(m)

with tempfile.TemporaryDirectory(prefix='dg-reset-') as directory:
    dbpath=Path(directory)/'dados.sqlite3'
    envscope={'DB':dbpath,'sqlite3':sqlite3,'json':json,'SITE_TEXT_DEFAULTS':{'hero_line1':'Seu estilo'},'DEFAULT_WEEK':{'0':{'start':'09:00','end':'18:00'}}}
    extract('init_db',envscope)()
    c=sqlite3.connect(dbpath,isolation_level=None,timeout=10)
    c.row_factory=sqlite3.Row
    def one(q,params=()):
        x=c.execute(q,params).fetchone();return dict(x) if x else None
    def password_hash(p):return 'fake_salted_hash:'+p
    def check_password(h,p):return h=='fake_salted_hash:'+p
    fake_session={}
    data={}
    def err(message,code=400):return ({'error':message},code)
    scope={
        'SECRET':'testing_key_only_never_use_in_server',
        'get_db':lambda:c,'one':one, 'body':lambda:data,'err':err,
        'hmac':hmac,'hashlib':hashlib,'time':time,'secrets':secrets,'re':re,'os':os,
        'jsonify':lambda **kw:kw,'session':fake_session,
        'check_password_hash':check_password,'generate_password_hash':password_hash,
        'valid_email':lambda x:isinstance(x,str) and '@' in x and '.' in x.split('@')[-1],
        'verify_email_required':lambda:False,
        'email_configured':lambda:bool((os.getenv('SMTP_HOST') and os.getenv('SMTP_FROM')) or (os.getenv('RESEND_API_KEY') and os.getenv('RESEND_FROM'))),
        'send_transactional_email':lambda to,subject,content:(lambda m:(m.__setitem__('Subject',subject),m.__setitem__('To',to),m.set_content(content),SMTPFake.mails.append(m)))(EmailMessage()),
        'bot_field_present':lambda d:bool(d.get('website','')),
        'smtplib':SimpleNamespace(SMTP=SMTPFake),'EmailMessage':EmailMessage,
        'app':SimpleNamespace(logger=SimpleNamespace(exception=lambda *args:None)),
    }
    for name in ['login_email_key','otp_digest','recovery_invalid','login','request_password_reset','confirm_password_reset','me']:
        extract(name,scope)
    scope['uid']=lambda:fake_session.get('uid')
    scope['avatar_url']=lambda user:None
    c.execute('INSERT INTO users(name,phone,email,password,role,created_at) VALUES(?,?,?,?,?,?)',
              ('Proprietário','71912345678','dono@example.com',password_hash('senha-correta'),'owner','2026-10-17'))
    c.execute('INSERT INTO users(name,phone,email,password,role,created_at) VALUES(?,?,?,?,?,?)',
              ('Cliente','71999999999','cliente@example.com',password_hash('cliente-correto'),'client','2026-10-17'))
    user=one('SELECT id,auth_version FROM users WHERE email=?',('dono@example.com',))
    data={'email':'dono@example.com','password':'senha-correta'}
    assert scope['login']()['ok'] is True
    assert scope['me']()['id']==user['id']
    print('PASSOU: login inicial e sessão ativa')
    for n in range(1,5):
        data={'email':'dono@example.com','password':'errada'}
        res,status=scope['login']()
        assert status==401 and res['attempts_remaining']==5-n
    res,status=scope['login']()
    assert status==423 and res['code']=='PASSWORD_RESET_REQUIRED'
    assert one('SELECT password_reset_required FROM users WHERE id=?',(user['id'],))['password_reset_required']==1
    assert scope['me']() is None
    data={'email':'dono@example.com','password':'senha-correta'}
    res,status=scope['login']()
    assert status==423 and res['code']=='PASSWORD_RESET_REQUIRED'
    print('PASSOU: cinco erros obrigam redefinição, mesmo com senha correta e sessão anterior')
    old=dict(os.environ)
    os.environ.update(SMTP_HOST='smtp.example.com',SMTP_FROM='dg@example.com',SMTP_PORT='587')
    try:
        data={'email':'dono@example.com'}
        response=scope['request_password_reset']()
        assert response['ok'] and len(SMTPFake.mails)==1
        assert 'senha-correta' not in SMTPFake.mails[0].get_content()
        match=re.search(r'\b([0-9]{6})\b',SMTPFake.mails[0].get_content())
        assert match
        code=match.group(1)
        first=one('SELECT expires_at,sent_at FROM password_reset_codes WHERE user_id=?',(user['id'],))
        assert first['expires_at']-first['sent_at']==600
        # Unknown email receives exactly the same public response.
        data={'email':'naoexiste@example.com'}
        assert scope['request_password_reset']()==response
        assert len(SMTPFake.mails)==1
        data={'email':'dono@example.com','code':'123456' if code!='123456' else '654321',
              'new_password':'nova-super-segura','confirm_password':'nova-super-segura'}
        invalid=scope['confirm_password_reset']()
        assert invalid[1]==400 and one('SELECT attempts FROM password_reset_codes WHERE user_id=?',(user['id'],))['attempts']==1
        data['code']=code
        assert scope['confirm_password_reset']()['ok']
        assert one('SELECT password_reset_required,auth_version FROM users WHERE id=?',(user['id'],))=={'password_reset_required':0,'auth_version':2}
        assert one('SELECT * FROM password_reset_codes WHERE user_id=?',(user['id'],)) is None
        assert not fake_session
        assert scope['confirm_password_reset']()[1]==400
        data={'email':'dono@example.com','password':'nova-super-segura'}
        assert scope['login']()['ok'] is True
        print('PASSOU: envio de código, validade 10 min, código único, senha nova e desbloqueio')
        # A janela de 60 segundos evita envios repetidos; validar expiração separadamente.
        data={'email':'cliente@example.com'}
        scope['request_password_reset']()
        newcode=re.search(r'\b([0-9]{6})\b',SMTPFake.mails[-1].get_content()).group(1)
        other=one('SELECT id FROM users WHERE email=?',('cliente@example.com',))['id']
        c.execute('UPDATE password_reset_codes SET expires_at=? WHERE user_id=?',(int(time.time())-1,other))
        data={'email':'cliente@example.com','code':newcode,'new_password':'senao-expira','confirm_password':'senao-expira'}
        assert scope['confirm_password_reset']()[1]==400
        c.execute('UPDATE password_reset_codes SET expires_at=? WHERE user_id=?',(int(time.time())+600,other))
        for i in range(5):
            data['code']='000000' if newcode!='000000' else '999999'
            assert scope['confirm_password_reset']()[1]==400
        assert one('SELECT * FROM password_reset_codes WHERE user_id=?',(other,)) is None
        print('PASSOU: código expirado, 5 códigos errados cancelam o código')
    finally:
        os.environ.clear();os.environ.update(old)
print('Todos os testes de recuperação passaram.')

# Confere que a API HTTPS é usada quando RESEND_API_KEY está presente,
# contornando o bloqueio de portas SMTP em instâncias gratuitas da Render.
import urllib.request
api_messages=[]
class ResponseFake:
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self):return b'{"id":"test"}'
def fake_urlopen(req,timeout=0):
    assert req.full_url=='https://api.resend.com/emails'
    assert req.get_method()=='POST'
    api_messages.append(json.loads(req.data.decode('utf-8')))
    assert req.headers['Authorization']=='Bearer re_test_fake'
    return ResponseFake()
real_urlopen=urllib.request.urlopen
saved=dict(os.environ)
try:
    os.environ.update(RESEND_API_KEY='re_test_fake',RESEND_FROM='DG Cortes <teste@example.com>')
    scope2={'os':os,'json':json,'urllib':urllib,'EmailMessage':EmailMessage,'smtplib':SimpleNamespace(SMTP=lambda *a: (_ for _ in ()).throw(RuntimeError('SMTP deve ficar desligado')))}
    urllib.request.urlopen=fake_urlopen
    extract('send_transactional_email',scope2)('destino@example.com','Código DG','012345')
    assert len(api_messages)==1 and api_messages[0]['text']=='012345'
    print('PASSOU: envio HTTPS (API Resend) sem conexão SMTP')
finally:
    urllib.request.urlopen=real_urlopen
    os.environ.clear();os.environ.update(saved)
