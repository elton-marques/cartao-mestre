"""Ajustes de HTML/JS compartilhados pelos dois montadores de pacote.

`preparar-pacote.py` (instalação com login) e `preparar-pacote-estatico.py`
(só o dashboard, sem login) partem dos mesmos arquivos do repositório e
precisam das mesmas remoções: o que só faz sentido no site pessoal — links
para o hub, e-mail, GitHub, nome próprio no cabeçalho e domínio no rodapé.

Toda substituição aqui é obrigatória: se o trecho não for encontrado, a
função levanta AjusteNaoAplicado e o pacote não é gerado. É de propósito —
um HTML que mudou de forma deve quebrar o build, não virar pacote com link
morto que ninguém percebe até chegar no servidor da empresa.
"""


class AjusteNaoAplicado(Exception):
    """Trecho esperado não encontrado — arquivo mudou, script precisa de revisão."""


def substituir(texto, de, para, arquivo):
    if de not in texto:
        raise AjusteNaoAplicado(f"{arquivo}: não achei {de!r}")
    return texto.replace(de, para)


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


def despersonalizar_app(html, nome_arquivo):
    """Tira do dashboard o que é do site pessoal, mantendo o crédito no rodapé."""
    html = remover_link(html, "mailto:contato@eltonmarques.com", nome_arquivo)
    html = remover_link(html, "github.com/elton-marques", nome_arquivo)
    html = remover_link(html, "Voltar ao hub", nome_arquivo)
    # Cabeçalho: no site pessoal a assinatura ao lado do nome do sistema faz
    # sentido; num sistema interno da empresa, não.
    html = substituir(html, "Dashboard · Elton Marques", "Dashboard", nome_arquivo)
    html = substituir(
        html,
        "eltonmarques.com · desenvolvido por Elton Marques",
        "desenvolvido por Elton Marques",
        nome_arquivo,
    )
    return html
