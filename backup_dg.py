"""Backup manual local: py backup_dg.py [pasta_de_destino]
Não é agendamento automático e não transfere dados para outro servidor.
"""
import os, sqlite3, sys, zipfile
from pathlib import Path
from datetime import datetime
BASE=Path(__file__).resolve().parent
DB=Path(os.environ.get('DG_DB_PATH',str(BASE/'dgcortes.sqlite3')))
DATA=Path(os.environ.get('DG_DATA_DIR',str(BASE/'data')))
if not DB.is_file():
    sys.exit('Não encontrei o banco de dados. Confira DG_DB_PATH ou inicie o aplicativo primeiro.')
target=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else BASE/'backups'
target.mkdir(parents=True,exist_ok=True)
name=target/f'dg_cortes_backup_{datetime.now():%Y%m%d_%H%M%S}.zip'
backup_db=target/'.dg_backup_temporario.sqlite3'
try:
    with sqlite3.connect(DB) as source, sqlite3.connect(backup_db) as output:
        source.backup(output)
    with zipfile.ZipFile(name,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.write(backup_db,'dgcortes.sqlite3')
        for path in DATA.rglob('*'):
            if path.is_file() and ('avatars' in path.parts or 'branding' in path.parts):
                z.write(path,'data/'+str(path.relative_to(DATA)))
    print('Backup gerado em:',name)
    print('IMPORTANTE: contém dados pessoais. Guarde em local privado e copie para fora do servidor.')
finally:
    backup_db.unlink(missing_ok=True)
