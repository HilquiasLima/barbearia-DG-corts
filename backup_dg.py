"""Ferramenta de backup/restauração local: python backup_dg.py backup|verify|restore"""
import argparse
import os
from pathlib import Path
from datetime import datetime
from backup_lib import make_backup, verify_backup, restore_backup

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description='Backup DG Cortes (contém dados pessoais: guarde em local PRIVADO).')
sub=parser.add_subparsers(dest='operation',required=True)
back=sub.add_parser('backup'); back.add_argument('--out',default=str(ROOT/'backups'))
check=sub.add_parser('verify');check.add_argument('zip')
restore=sub.add_parser('restore');restore.add_argument('zip');restore.add_argument('--db',required=True);restore.add_argument('--data',required=True);restore.add_argument('--confirm',action='store_true');restore.add_argument('--replace',action='store_true')
args=parser.parse_args()
if args.operation=='backup':
    db=Path(os.environ.get('DG_DB_PATH',str(ROOT/'dgcortes.sqlite3')))
    data=Path(os.environ.get('DG_DATA_DIR',str(ROOT/'data')))
    file=Path(args.out)/f'dg-backup-{datetime.now():%Y%m%d-%H%M%S}.zip'
    print('Gerado:',make_backup(db,data,file));print('Verificação:',verify_backup(file))
elif args.operation=='verify':print('Verificação OK:',verify_backup(Path(args.zip)))
else:
    if not args.confirm:parser.error('Desligue a aplicação primeiro e passe --confirm após conferir destinos.')
    print('Restaurado:',restore_backup(Path(args.zip),Path(args.db),Path(args.data),replace=args.replace))
