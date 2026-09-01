#!/usr/bin/env python3
"""Monta o pacote de instalação do Cartão Mestre para intranet.

Copia os arquivos que vão para o servidor da empresa e aplica os ajustes
que a versão interna precisa — basicamente remover o que só faz sentido no
site pessoal (links para o hub, e-mail, GitHub, domínio no rodapé), que na
intranet viram beco sem saída. O crédito de autoria continua, discreto.

Rode da raiz do repositório:

    python deploy/intranet/preparar-pacote.py

Gera `dist/cartao-mestre-intranet/` e o .zip correspondente. `dist/` é
descartável — pode apagar e gerar de novo a qualquer momento.

Os CSVs reais de `dados/csv/` **não** entram no pacote de propósito: dado
de funcionário não deve trafegar por e-mail/chamado, e na instalação final
esses arquivos vêm da pasta de rede (ver README-INTRANET.md, seção 4). Vão
só os dados fictícios de `dados/csv-exemplo/`, que é o fallback do app.

Cada ajuste abaixo é uma substituição exata e obrigatória: se o HTML mudar
e algum trecho não for mais encontrado, o script falha em vez de gerar um
pacote silenciosamente errado (com link morto para o hub, por exemplo).
"""
import shutil
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "dist" / "cartao-mestre-intranet"


class AjusteNaoAplicado(Exception):
    """Trecho esperado não encontrado — HTML mudou, script precisa de revisão."""


def remover_link(html, marcador, arquivo):
    """Remove o elemento <a> inteiro que contém `marcador`.

    Recorta do `<a` que abre o elemento até o `</a>` que o fecha, em vez de
    casar o bloco inteiro por string literal — assim uma mudança de classe
    ou de indentação no meio da tag não quebra o script.
    """
    pos = html.find(marcador)
    if pos == -1:
        raise AjusteNaoAplicado(f"{arquivo}: não achei {marcador!r}")
    inicio = html.rfind("<a", 0, pos)
    fim = html.find("</a>", pos)
    if inicio == -1 or fim == -1:
        raise AjusteNaoAplicado(f"{arquivo}: {marcador!r} não está dentro de um <a>")
    return html[:inicio].rstrip() + "\n" + html[fim + len("</a>"):].lstrip("\n")


def substituir(texto, de, para, arquivo):
    if de not in texto:
        raise AjusteNaoAplicado(f"{arquivo}: não achei {de!r}")
    return texto.replace(de, para)


def ajustar_app_index(caminho):
    html = caminho.read_text(encoding="utf-8")
    nome = caminho.name
    html = remover_link(html, "mailto:contato@eltonmarques.com", nome)
    html = remover_link(html, "github.com/elton-marques", nome)
    html = remover_link(html, "Voltar ao hub", nome)
    html = substituir(
        html,
        "eltonmarques.com · desenvolvido por Elton Marques",
        "desenvolvido por Elton Marques",
        nome,
    )
    caminho.write_text(html, encoding="utf-8")


def ajustar_login_index(caminho):
    html = caminho.read_text(encoding="utf-8")
    html = remover_link(html, "Voltar para eltonmarques.com", caminho.name)
    caminho.write_text(html, encoding="utf-8")


def ajustar_main_js(caminho):
    """'Sair' vai direto para a tela de login.

    Na VPS "/" é o hub pessoal; na intranet "/" só redireciona de volta para
    o dashboard, que por sua vez manda para o login — funciona, mas com um
    pulo a mais e uma piscada de tela no meio.
    """
    js = caminho.read_text(encoding="utf-8")
    js = substituir(js, "doLogout('/');", "doLogout('/login/');", caminho.name)
    caminho.write_text(js, encoding="utf-8")


def copiar(origem, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origem.is_dir():
        shutil.copytree(origem, destino, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        shutil.copy2(origem, destino)


def main():
    if DESTINO.exists():
        shutil.rmtree(DESTINO)

    copiar(RAIZ / "app", DESTINO / "app")
    copiar(RAIZ / "design-system", DESTINO / "design-system")
    copiar(RAIZ / "dados" / "csv-exemplo", DESTINO / "dados" / "csv-exemplo")

    for nome in ("index.html", "historico.html"):
        copiar(RAIZ / "deploy" / "login" / nome, DESTINO / "deploy" / "login" / nome)
    for nome in ("server.py", "db.py", "manage_users.py"):
        copiar(RAIZ / "deploy" / "auth-service" / nome, DESTINO / "deploy" / "auth-service" / nome)
    for nome in (
        "nginx-cartao-mestre-intranet.conf",
        "cartao-mestre-auth.service",
        "README-INTRANET.md",
    ):
        copiar(RAIZ / "deploy" / "intranet" / nome, DESTINO / "deploy" / "intranet" / nome)
    copiar(
        RAIZ / "deploy" / "intranet" / "README-INTRANET.md",
        DESTINO / "LEIA-ME-INSTALACAO.md",
    )

    try:
        ajustar_app_index(DESTINO / "app" / "index.html")
        ajustar_login_index(DESTINO / "deploy" / "login" / "index.html")
        ajustar_main_js(DESTINO / "app" / "js" / "main.js")
    except AjusteNaoAplicado as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        print(
            "O pacote NÃO foi gerado. O arquivo de origem mudou desde a última\n"
            "revisão deste script — ajuste o trecho correspondente aqui.",
            file=sys.stderr,
        )
        return 1

    zip_path = DESTINO.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for arquivo in sorted(DESTINO.rglob("*")):
            if arquivo.is_file():
                z.write(arquivo, Path(DESTINO.name) / arquivo.relative_to(DESTINO))

    print(f"pacote:  {DESTINO}")
    print(f"zip:     {zip_path}  ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
