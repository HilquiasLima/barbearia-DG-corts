"""Backups portáteis do DG Cortes: cópia SQLite consistente, fotos e SHA-256."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile

MAX_MEMBER = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_backup(db_path: Path, data_dir: Path, destination: Path) -> Path:
    db_path, data_dir, destination = map(Path, (db_path, data_dir, destination))
    if not db_path.is_file():
        raise FileNotFoundError('O banco SQLite não existe.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dg-bk-') as tempdir:
        db_copy = Path(tempdir) / 'dgcortes.sqlite3'
        with sqlite3.connect(str(db_path)) as source, sqlite3.connect(str(db_copy)) as out:
            source.backup(out)
            if out.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Banco não passou na verificação de integridade.')
        paths = {'dgcortes.sqlite3': db_copy}
        for section in ('avatars', 'branding'):
            directory = data_dir / section
            if directory.exists():
                for file in directory.rglob('*'):
                    if file.is_file() and not file.is_symlink():
                        paths['data/' + str(file.relative_to(data_dir).as_posix())] = file
        hashes = {}
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
            for internal, source_file in sorted(paths.items()):
                data = source_file.read_bytes()
                hashes[internal] = digest_bytes(data)
                archive.writestr(internal, data)
            archive.writestr('manifest.json', json.dumps({'format':1,'created_at':datetime.now().isoformat(timespec='seconds'),'sha256':hashes},ensure_ascii=False,indent=2))
    verify_backup(destination)
    return destination


def verify_backup(archive_path: Path) -> dict:
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)) or 'dgcortes.sqlite3' not in names or 'manifest.json' not in names:
            raise ValueError('Backup incompleto ou com entradas duplicadas.')
        size = 0
        for item in members:
            if item.filename not in ('manifest.json', 'dgcortes.sqlite3') and not item.filename.startswith(('data/avatars/', 'data/branding/')):
                raise ValueError('Arquivo não permitido dentro do backup.')
            if item.filename.startswith('/') or '..' in Path(item.filename).parts or '\\' in item.filename:
                raise ValueError('Caminho inseguro dentro do backup.')
            if item.file_size > MAX_MEMBER:
                raise ValueError('Arquivo muito grande para restauração.')
            size += item.file_size
            if size > MAX_TOTAL:
                raise ValueError('Backup excede tamanho permitido.')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 1 or set(manifest.get('sha256',{})) != set(names)-{'manifest.json'}:
            raise ValueError('Manifesto inválido.')
        for name, hexdigest in manifest['sha256'].items():
            if digest_bytes(archive.read(name)) != hexdigest:
                raise ValueError(f'Arquivo adulterado ou corrompido: {name}')
        with tempfile.TemporaryDirectory(prefix='dg-verify-') as directory:
            db_file = Path(directory)/'db.sqlite3'
            db_file.write_bytes(archive.read('dgcortes.sqlite3'))
            with sqlite3.connect(str(db_file)) as conn:
                if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Banco SQLite corrompido.')
    return {'entries':len(names)-1, 'bytes':size, 'created_at':manifest.get('created_at')}


def restore_backup(archive_path: Path, dest_db: Path, dest_data: Path, *, replace=False):
    """Restaura com aplicação DESLIGADA. Ao substituir produção, faça backup ANTES."""
    verify_backup(archive_path)
    dest_db, dest_data = Path(dest_db), Path(dest_data)
    if dest_db.exists() and not replace:
        raise FileExistsError('Banco de destino já existe. Informe --replace explicitamente.')
    with tempfile.TemporaryDirectory(prefix='dg-restore-') as directory:
        temp = Path(directory)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(temp)
        # Verifique TODOS os conflitos antes de substituir qualquer arquivo.
        source_data = temp/'data'
        if source_data.exists() and not replace:
            for file in source_data.rglob('*'):
                if file.is_file() and (dest_data/file.relative_to(source_data)).exists():
                    raise FileExistsError('Já existe uma foto em destino. Use --replace.')
        dest_db.parent.mkdir(parents=True,exist_ok=True)
        staged = dest_db.with_suffix(dest_db.suffix + '.restoring')
        shutil.copyfile(temp/'dgcortes.sqlite3', staged)
        os.replace(staged, dest_db)
        copied = 0
        source_data = temp/'data'
        if source_data.exists():
            for file in source_data.rglob('*'):
                if file.is_file():
                    out = dest_data/file.relative_to(source_data)
                    out.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(file,out)
                    copied += 1
    return {'photos':copied}
