"""Testes sem dependências externas (além da biblioteca padrão)."""
from pathlib import Path
import ast
import json
import os
import tempfile
import hashlib
import hmac
import sqlite3
import time
from datetime import datetime
from backup_lib import make_backup, verify_backup, restore_backup

ROOT=Path(__file__).parent
source=(ROOT/'app.py').read_text()
node=ast.parse(source)
functions={x.name:x for x in node.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}

def extracted(name, scope):
    func=functions[name]
    pure=ast.FunctionDef(name=func.name,args=func.args,body=func.body,decorator_list=[],returns=func.returns,type_comment=None,type_params=[])
    ast.fix_missing_locations(pure)
    exec(compile(ast.Module(body=[pure],type_ignores=[]),str(ROOT/'app.py'),'exec'),scope)
    return scope[name]

with tempfile.TemporaryDirectory(prefix='dg-security-tests-') as dirname:
    tmp=Path(dirname)
    dbpath=tmp/'real.sqlite3'
    # Execute a migração real com globals artificiais, sem servidor Flask.
    scope={'DB':dbpath,'json':json,'SITE_TEXT_DEFAULTS':{'hero_line1':'Seu estilo'},'DEFAULT_WEEK':{'0':{'start':'09:00','end':'18:00'}},'sqlite3':sqlite3}
    extracted('init_db',scope)()
    with sqlite3.connect(dbpath) as db:
        assert 'email_verified' in [r[1] for r in db.execute('PRAGMA table_info(users)')]
        assert db.execute("SELECT name FROM sqlite_master WHERE name='email_verifications'").fetchone()
        assert db.execute("SELECT name FROM sqlite_master WHERE name='throttle_events'").fetchone()
        db.execute("INSERT INTO users(name,phone,email,password,created_at,role) VALUES('Dono Teste','71999999999','dono@example.com','hash','2026','owner')")
        assert db.execute('SELECT email_verified FROM users WHERE id=1').fetchone()[0]==1
    extracted('init_db',scope)() # migração idempotente
    # Backup completo e restauração em banco de testes novo.
    asset=tmp/'data'/'avatars'/'1.webp';asset.parent.mkdir(parents=True)
    asset.write_bytes(b'test-image-bytes')
    archive=make_backup(dbpath,tmp/'data',tmp/'backup.zip')
    details=verify_backup(archive)
    assert details['entries']==2
    restored=tmp/'restore'/'db.sqlite3';photos=tmp/'restore'/'data'
    restore_backup(archive,restored,photos)
    with sqlite3.connect(restored) as conn:
        assert conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]==1
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert (photos/'avatars'/'1.webp').read_bytes()==b'test-image-bytes'
    try: restore_backup(archive,restored,photos)
    except FileExistsError: pass
    else: raise AssertionError('Restauração sobrescreveu destino sem autorização')
    # O zip detecta tampering via hash
    import zipfile
    archive2=tmp/'alterado.zip'
    with zipfile.ZipFile(archive) as z,zipfile.ZipFile(archive2,'w') as out:
        for name in z.namelist():
            data=z.read(name)
            if name=='data/avatars/1.webp':data=b'file-tampered'
            out.writestr(name,data)
    try: verify_backup(archive2)
    except ValueError: pass
    else: raise AssertionError('Backup adulterado deveria ser rejeitado')
    print('PASSOU: migração de banco, compatibilidade clientes antigos e execução repetida')
    print('PASSOU: backup consistente, hashes, integridade SQLite e restauração de fotos')
    print('PASSOU: bloqueio de restauração acidental e backup adulterado')

    # Limite persistente de login na base: 2 tentativas no intervalo para simular.
    class DummyG:pass
    db=sqlite3.connect(':memory:',isolation_level=None)
    db.row_factory=sqlite3.Row
    db.executescript('CREATE TABLE throttle_events (event_id INTEGER PRIMARY KEY, bucket TEXT NOT NULL, at_seconds INTEGER NOT NULL); CREATE INDEX throttle_lookup ON throttle_events(bucket,at_seconds);')
    class LimitResponse:
        def __init__(self,content):self.content=content;self.status_code=200;self.headers={}
    scope={'SECRET':'secret_for_tests','get_db':lambda:db,'one':lambda q,params:dict(db.execute(q,params).fetchone()),'hmac':hmac,'hashlib':hashlib,'time':time,'jsonify':lambda **kw:LimitResponse(kw)}
    guard=extracted('guard_bucket',scope)
    assert guard('login','client@example.com',2,900) is None
    assert guard('login','client@example.com',2,900) is None
    result=guard('login','client@example.com',2,900)
    assert result.status_code==429 and int(result.headers['Retry-After'])>0
    assert guard('login','other@example.com',2,900) is None
    print('PASSOU: limite de requisições, Retry-After e contas isoladas')

# Verificação de cabeçalho e requisitos básicos do código.
assert "secrets.token_urlsafe(36)" in source
assert "token_digest" in source and "valid_until" in source
assert "if verify_email_required() and not u['email_verified']" in source
assert "EMAIL_VERIFICATION_REQUIRED', '0'" in source
print('PASSOU: tokens de e-mail expiráveis e opção desativada por padrão')
