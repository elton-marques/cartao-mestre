#!/usr/bin/env python3
"""Banco SQLite do serviço de auth do Cartão Mestre.

Substitui os antigos /etc/cartao-mestre/users.txt e login_log.csv (arquivos
texto lidos/reescritos por inteiro a cada operação) por um único arquivo
SQLite (`sqlite3`, stdlib — mantém o serviço sem dependências externas) em
/etc/cartao-mestre/cartao-mestre.db.

server.py (runtime) e manage_users.py (CLI de administração) só falam com
o banco através das funções deste módulo — nenhum dos dois deve montar SQL
ou abrir o arquivo direto.

Tabelas:
  users(username PK, password_hash, role)
  login_history(id PK autoincrement, timestamp_utc, username, ip, country,
                 city, device_os, browser)

Hash de senha — PBKDF2-HMAC-SHA256 (100k iterações), formato
  "pbkdf2_sha256$<iterações>$<salt_hex>$<hash_hex>"
Usuário migrado do users.txt antigo entra com o hash legado intacto
  "sha256$<salt_hex>$<hash_hex>"  (salt + sha256 simples, sem iteração)
— continua autenticando normalmente; check_password() faz o upgrade pra
PBKDF2 sozinho assim que a senha certa é digitada de novo (é o único
momento em que a senha em texto puro existe em memória pra poder re-gerar
o hash forte). Ver migrate_to_sqlite.py pra importar o formato antigo.
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

DB_FILE = "/etc/cartao-mestre/cartao-mestre.db"
PBKDF2_ITERATIONS = 100_000
ROLES = ("admin", "viewer")


def _connect():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(_connect()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                username TEXT NOT NULL,
                ip TEXT,
                country TEXT,
                city TEXT,
                device_os TEXT,
                browser TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_login_history_ts ON login_history (timestamp_utc)"
        )
    if os.path.exists(DB_FILE):
        os.chmod(DB_FILE, 0o600)


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def hash_password_legacy(salt, sha256_hex):
    """Só pra importar users.txt antigo (migrate_to_sqlite.py) — nunca usar
    isso pra senha nova, é o esquema fraco que estamos deixando pra trás."""
    return f"sha256${salt}${sha256_hex}"


def _verify(password, stored):
    """-> (senha_confere, precisa_upgrade_pra_pbkdf2)"""
    try:
        scheme, rest = stored.split("$", 1)
    except ValueError:
        return False, False
    if scheme == "pbkdf2_sha256":
        iterations, salt, digest = rest.split("$")
        got = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(got, digest), False
    if scheme == "sha256":
        salt, digest = rest.split("$")
        got = hashlib.sha256((salt + password).encode()).hexdigest()
        return hmac.compare_digest(got, digest), True
    return False, False


def get_user(username):
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT username, password_hash, role FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def check_password(username, password):
    user = get_user(username)
    if not user:
        return False
    ok, needs_upgrade = _verify(password, user["password_hash"])
    if ok and needs_upgrade:
        set_password(username, password)  # upgrade transparente pra PBKDF2
    return ok


def get_user_role(username):
    user = get_user(username)
    return user["role"] if user else None


def set_password(username, password, role=None):
    """Cria o usuário (se não existir) ou troca a senha; mantém o papel
    atual se `role` não for informado (default 'viewer' pra usuário novo)."""
    existing = get_user(username)
    role = role or (existing["role"] if existing else "viewer")
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?) "
            "ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash, role = excluded.role",
            (username, hash_password(password), role),
        )


def import_legacy_user(username, salt, sha256_hex, role):
    """Só usado por migrate_to_sqlite.py — grava o hash antigo como veio do
    users.txt, sem recalcular (não temos a senha em texto puro aqui)."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?) "
            "ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash, role = excluded.role",
            (username, hash_password_legacy(salt, sha256_hex), role),
        )


def set_role(username, role):
    with closing(_connect()) as conn, conn:
        cur = conn.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
        return cur.rowcount > 0


def delete_user(username):
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
        return cur.rowcount > 0


def list_users():
    with closing(_connect()) as conn:
        return [dict(r) for r in conn.execute("SELECT username, role FROM users ORDER BY username")]


def log_login(username, ip, country, city, device_os, browser):
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO login_history (timestamp_utc, username, ip, country, city, device_os, browser) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                username,
                ip,
                country,
                city,
                device_os,
                browser,
            ),
        )


def read_login_history(limit=500):
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT timestamp_utc, username, ip, country, city, device_os, browser "
            "FROM login_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


init_db()
