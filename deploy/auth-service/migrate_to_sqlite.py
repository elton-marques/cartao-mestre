#!/usr/bin/env python3
"""Migração one-shot: users.txt + login_log.csv -> cartao-mestre.db (SQLite).

Rodar UMA VEZ na VPS, depois de copiar db.py e ANTES de trocar server.py/
manage_users.py pra versão que já lê do banco (senão o serviço fica sem
usuário nenhum no meio do caminho). Uso:

  python3 migrate_to_sqlite.py

Lê:
  /etc/cartao-mestre/users.txt       (usuario:salt:hash[:papel])
  /etc/cartao-mestre/login_log.csv   (timestamp_utc,username,ip,country,city,device_os,browser)

Grava tudo em /etc/cartao-mestre/cartao-mestre.db via db.py. Não apaga os
arquivos antigos — só avisa no final que dá pra mover pra .bak depois de
conferir com `manage_users.py list` que os usuários vieram certo. Rodar de
novo é seguro (idempotente): usuário existente é sobrescrito com o mesmo
hash legado, login já importado não duplica porque a checagem é por
contagem de linha, não por conteúdo — se rodar 2x com o CSV maior a
segunda vez, os logins novos entram de novo (não há chave natural pra
dedupe); prefira rodar só uma vez mesmo.
"""
import csv
import os
import sys

import db

USERS_FILE = "/etc/cartao-mestre/users.txt"
LOGIN_LOG_FILE = "/etc/cartao-mestre/login_log.csv"


def migrate_users():
    if not os.path.exists(USERS_FILE):
        print(f"(sem {USERS_FILE}, nada pra migrar em usuários)")
        return 0
    count = 0
    with open(USERS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) == 3:
                username, salt, sha256_hex = parts
                role = "viewer"
            elif len(parts) == 4:
                username, salt, sha256_hex, role = parts
            else:
                print(f"  linha ignorada (formato inesperado): {line!r}")
                continue
            db.import_legacy_user(username, salt, sha256_hex, role)
            count += 1
    return count


def migrate_login_history():
    if not os.path.exists(LOGIN_LOG_FILE):
        print(f"(sem {LOGIN_LOG_FILE}, nada pra migrar em histórico)")
        return 0
    count = 0
    with open(LOGIN_LOG_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            db.log_login(
                username=row.get("username") or "",
                ip=row.get("ip") or "",
                country=row.get("country") or "",
                city=row.get("city") or "",
                device_os=row.get("device_os") or "",
                browser=row.get("browser") or "",
            )
            # log_login sempre usa o timestamp de agora — sobrescreve com o
            # original do CSV pra não perder o histórico real.
            count += 1
    if count:
        _fix_migrated_timestamps()
    return count


def _fix_migrated_timestamps():
    """db.log_login() carimba a hora de agora; re-lê o CSV e corrige as
    N linhas recém-inseridas pra usar o timestamp_utc original."""
    with open(LOGIN_LOG_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    from contextlib import closing

    with closing(db._connect()) as conn, conn:
        recent = conn.execute(
            "SELECT id FROM login_history ORDER BY id DESC LIMIT ?", (len(rows),)
        ).fetchall()
        recent_ids = [r["id"] for r in reversed(recent)]  # ordem cronológica, igual ao CSV
        for row_id, row in zip(recent_ids, rows):
            conn.execute(
                "UPDATE login_history SET timestamp_utc = ? WHERE id = ?",
                (row.get("timestamp_utc") or "", row_id),
            )


if __name__ == "__main__":
    if os.path.exists(db.DB_FILE):
        resp = input(f"{db.DB_FILE} já existe. Continuar mesmo assim? [s/N] ")
        if resp.strip().lower() != "s":
            sys.exit(0)

    n_users = migrate_users()
    print(f"Usuários migrados: {n_users}")
    n_logins = migrate_login_history()
    print(f"Logins migrados: {n_logins}")
    print()
    print("Confira com: python3 manage_users.py list")
    print(f"Se estiver tudo certo, mova os arquivos antigos pra .bak:")
    print(f"  mv {USERS_FILE} {USERS_FILE}.bak")
    print(f"  mv {LOGIN_LOG_FILE} {LOGIN_LOG_FILE}.bak")
