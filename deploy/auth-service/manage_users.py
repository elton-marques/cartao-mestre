#!/usr/bin/env python3
"""Gerencia os usuários do login do dashboard Cartão Mestre.

Uso:
  python3 manage_users.py add <usuario> <senha> [papel]   # cria ou troca a senha
                                                            # papel: admin|viewer (default: viewer,
                                                            # ou o papel já existente do usuário se omitido)
  python3 manage_users.py role <usuario> <admin|viewer>    # só troca o papel, mantém a senha
  python3 manage_users.py del <usuario>
  python3 manage_users.py list

Grava em /etc/cartao-mestre/cartao-mestre.db (SQLite — ver db.py pro schema
e pro hash de senha, PBKDF2-HMAC-SHA256). Não é Basic Auth do nginx, é o
banco lido pelo server.py do serviço de login.

Papel "admin" enxerga /login/historico.html (histórico de login de todo
mundo — IP, dispositivo, etc.); "viewer" só usa o dashboard normal.
"""
import sys

import db

ROLES = db.ROLES


def cmd_add(username, password, role=None):
    if role is not None and role not in ROLES:
        print(f"Papel inválido: '{role}'. Use: {' | '.join(ROLES)}")
        sys.exit(1)
    db.set_password(username, password, role)
    print(f"Usuário '{username}' salvo/atualizado (papel: {db.get_user_role(username)}).")


def cmd_role(username, role):
    if role not in ROLES:
        print(f"Papel inválido: '{role}'. Use: {' | '.join(ROLES)}")
        sys.exit(1)
    if not db.set_role(username, role):
        print(f"Usuário '{username}' não encontrado.")
        return
    print(f"Usuário '{username}' agora é '{role}'.")


def cmd_del(username):
    if not db.delete_user(username):
        print(f"Usuário '{username}' não encontrado.")
        return
    print(f"Usuário '{username}' removido.")


def cmd_list():
    for user in db.list_users():
        print(f"{user['username']} ({user['role']})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "add" and len(sys.argv) in (4, 5):
        cmd_add(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) == 5 else None)
    elif cmd == "role" and len(sys.argv) == 4:
        cmd_role(sys.argv[2], sys.argv[3])
    elif cmd == "del" and len(sys.argv) == 3:
        cmd_del(sys.argv[2])
    elif cmd == "list":
        cmd_list()
    else:
        print(__doc__)
        sys.exit(1)
