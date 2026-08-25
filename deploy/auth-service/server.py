#!/usr/bin/env python3
"""Serviço de autenticação por cookie para o dashboard Cartão Mestre.

Substitui o HTTP Basic Auth do nginx por uma sessão de cookie assinada,
pra permitir uma página de login com estilo próprio — o navegador não
deixa estilizar a caixinha nativa do Basic Auth.

Endpoints:
  POST /login   {"username": "...", "password": "..."}  -> Set-Cookie + 200 / 401
                   429 se o IP estourou o limite de tentativas (ver
                   MAX_LOGIN_ATTEMPTS/LOGIN_ATTEMPT_WINDOW) — sem isso,
                   qualquer um podia tentar senha de qualquer usuário
                   (viewer incluso, que já enxerga COLABORADORES.csv no
                   dashboard) sem limite algum.
  POST /logout  -> limpa o cookie, 200
  GET  /verify  -> 200 se o cookie de sessão é válido, 401 caso contrário
                   (chamado pelo nginx via auth_request — sub-requisição
                   interna, não é o navegador batendo aqui direto). Header
                   X-User com o usuário e X-User-Role com o papel (admin/
                   viewer) — nginx ignora esses headers, é o app JS
                   (fetchUsername em app/js/main.js) que os lê.
  GET  /history -> 200 + JSON com os últimos logins. Exige cookie de sessão
                   válido E papel "admin" (401 sem sessão, 403 se for
                   "viewer") — histórico expõe IP/dispositivo de todo mundo,
                   não é algo que qualquer usuário logado deva ver.

Usuários e histórico de login ficam em /etc/cartao-mestre/cartao-mestre.db
(SQLite — ver db.py pro schema e pra lógica de hash de senha). "papel" é
"admin" ou "viewer" — default "viewer" (mais restritivo é o seguro).
Gerencie usuários com manage_users.py (add/del/list/role) — nunca abrir o
banco na mão.

Cada login bem-sucedido é gravado na tabela login_history
(timestamp ISO UTC, usuário, IP, país, cidade, SO/dispositivo, navegador).
O IP vem do header CF-Connecting-IP (Cloudflare Tunnel injeta esse header
com o IP real do visitante) com fallback pra X-Forwarded-For e, por fim,
pro socket da conexão. País/cidade vêm dos headers CF-IPCountry/CF-IPCity
que o Cloudflare injeta — CF-IPCountry vem de graça em qualquer zona
proxiada; CF-IPCity só aparece se "Add visitor location headers" estiver
ligado no painel Cloudflare (Network settings, disponível no free tier).
SO/dispositivo/navegador vêm de um parse heurístico do User-Agent — não é
100% preciso (nenhum parser de UA é), mas cobre os casos comuns.

Sem dependências externas de propósito (só stdlib) pra não precisar de
venv/pip nesse serviço pequeno — sqlite3 (db.py) também é stdlib.
"""
import hashlib
import hmac
import http.server
import json
import os
import secrets
import threading
import time

import db

SECRET_FILE = "/etc/cartao-mestre/secret.key"
SESSION_TTL = 12 * 3600  # 12h
COOKIE_NAME = "cm_session"
LISTEN = ("127.0.0.1", 8082)
HISTORY_MAX_ROWS = 500  # retorna só os últimos N logins na resposta de /history

# Rate-limit de /login por IP — sem isso um IP podia tentar senha sem
# limite (brute-force/credential-stuffing contra qualquer usuário,
# inclusive "viewer", que já tem acesso legítimo ao CSV de colaboradores).
# Chave é o IP (get_client_ip), não o usuário: também trava enumeração de
# usuário por tentativa-e-erro. Em memória de propósito — serviço roda
# como processo único (ThreadingHTTPServer), reiniciar zera os contadores,
# o que é aceitável pra esse limite.
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW = 15 * 60  # tentativas falhas mais velhas que isso não contam
LOGIN_LOCKOUT_SECONDS = 15 * 60  # Retry-After sugerido quando o limite estoura

_login_attempts_lock = threading.Lock()
_failed_logins = {}  # ip -> [timestamp de cada tentativa falha, mais recente por último]


def _is_ip_locked_out(ip):
    now = time.time()
    with _login_attempts_lock:
        attempts = [t for t in _failed_logins.get(ip, []) if now - t < LOGIN_ATTEMPT_WINDOW]
        if attempts:
            _failed_logins[ip] = attempts
        else:
            _failed_logins.pop(ip, None)
        return len(attempts) >= MAX_LOGIN_ATTEMPTS


def _record_failed_login(ip):
    with _login_attempts_lock:
        _failed_logins.setdefault(ip, []).append(time.time())


def _clear_failed_logins(ip):
    with _login_attempts_lock:
        _failed_logins.pop(ip, None)


def _load_secret():
    if not os.path.exists(SECRET_FILE):
        os.makedirs(os.path.dirname(SECRET_FILE), exist_ok=True)
        with open(SECRET_FILE, "w") as f:
            f.write(secrets.token_hex(32))
        os.chmod(SECRET_FILE, 0o600)
    with open(SECRET_FILE) as f:
        return f.read().strip()


SECRET = _load_secret()


def make_token(username):
    exp = int(time.time()) + SESSION_TTL
    payload = f"{username}|{exp}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def verify_token(token):
    try:
        username, exp, sig = token.split("|")
    except (ValueError, AttributeError):
        return None
    payload = f"{username}|{exp}"
    expected_sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    if int(exp) < time.time():
        return None
    return username


def get_cookie(headers, name):
    raw = headers.get("Cookie", "")
    for part in raw.split(";"):
        part = part.strip()
        if part.startswith(name + "="):
            return part[len(name) + 1:]
    return None


def get_client_ip(headers, client_address):
    cf_ip = headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    fwd = headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return client_address[0]


def get_location(headers):
    country = (headers.get("CF-IPCountry") or "").strip()
    city = (headers.get("CF-IPCity") or "").strip()
    return country or "?", city or "?"


# Parse heurístico de User-Agent — não é biblioteca, só regex simples.
# Cobre os casos comuns (Windows/macOS/Android/iOS/Linux, os navegadores
# grandes); UA raro cai em "Desconhecido". Ordem dos elif importa: UA de
# navegador costuma citar mais de uma engine (ex. Edge inclui "Chrome" e
# "Safari" na string), então o mais específico precisa vir primeiro.
def parse_user_agent(ua):
    if not ua:
        return "Desconhecido", "Desconhecido"
    u = ua.lower()

    # iPhone/iPad UA também contém "like Mac OS X" — checar iOS antes de
    # macOS, senão todo celular/tablet Apple cai errado em "macOS".
    if "windows" in u:
        os_name = "Windows"
    elif "iphone" in u or "ipad" in u or "ios " in u:
        os_name = "iOS"
    elif "mac os x" in u or "macintosh" in u:
        os_name = "macOS"
    elif "android" in u:
        os_name = "Android"
    elif "linux" in u:
        os_name = "Linux"
    else:
        os_name = "Desconhecido"

    if "ipad" in u or ("android" in u and "mobile" not in u):
        device = "Tablet"
    elif "mobi" in u or "iphone" in u:
        device = "Mobile"
    else:
        device = "Desktop"

    if "edg/" in u:
        browser = "Edge"
    elif "opr/" in u or "opera" in u:
        browser = "Opera"
    elif "firefox" in u:
        browser = "Firefox"
    elif "chrome" in u:
        browser = "Chrome"
    elif "safari" in u:
        browser = "Safari"
    else:
        browser = "Desconhecido"

    return f"{os_name} ({device})", browser


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "cartao-mestre-auth/1.0"

    def log_message(self, fmt, *args):
        pass  # o journal do systemd já guarda o essencial via stdout/stderr

    def _send_json(self, status, obj, extra_headers=None):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra_headers or []:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/verify"):
            token = get_cookie(self.headers, COOKIE_NAME)
            username = verify_token(token) if token else None
            if username:
                self.send_response(200)
                self.send_header("X-User", username)
                self.send_header("X-User-Role", db.get_user_role(username) or "viewer")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self.send_response(401)
                self.send_header("Content-Length", "0")
                self.end_headers()
            return

        if self.path.startswith("/history"):
            token = get_cookie(self.headers, COOKIE_NAME)
            username = verify_token(token) if token else None
            if not username:
                self._send_json(401, {"ok": False, "error": "Não autenticado."})
                return
            if db.get_user_role(username) != "admin":
                self._send_json(403, {"ok": False, "error": "Sem permissão pra ver o histórico de login."})
                return
            self._send_json(200, {"ok": True, "logins": db.read_login_history(HISTORY_MAX_ROWS)})
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            data = {}

        if self.path.startswith("/login"):
            ip = get_client_ip(self.headers, self.client_address)
            if _is_ip_locked_out(ip):
                self._send_json(
                    429,
                    {"ok": False, "error": "Muitas tentativas. Tente novamente em alguns minutos."},
                    [("Retry-After", str(LOGIN_LOCKOUT_SECONDS))],
                )
                return

            username = (data.get("username") or "").strip()
            password = data.get("password") or ""
            if username and db.check_password(username, password):
                _clear_failed_logins(ip)
                token = make_token(username)
                cookie = (
                    f"{COOKIE_NAME}={token}; Path=/; Max-Age={SESSION_TTL}; "
                    f"HttpOnly; Secure; SameSite=Lax"
                )
                country, city = get_location(self.headers)
                device_os, browser = parse_user_agent(self.headers.get("User-Agent", ""))
                db.log_login(username, ip, country, city, device_os, browser)
                self._send_json(200, {"ok": True}, [("Set-Cookie", cookie)])
            else:
                _record_failed_login(ip)
                self._send_json(401, {"ok": False, "error": "Usuário ou senha inválidos."})
            return

        if self.path.startswith("/logout"):
            cookie = f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
            self._send_json(200, {"ok": True}, [("Set-Cookie", cookie)])
            return

        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    httpd = http.server.ThreadingHTTPServer(LISTEN, Handler)
    print(f"cartao-mestre-auth ouvindo em {LISTEN[0]}:{LISTEN[1]}")
    httpd.serve_forever()
