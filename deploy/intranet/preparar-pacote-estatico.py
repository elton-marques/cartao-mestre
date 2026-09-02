#!/usr/bin/env python3
"""Monta o pacote estático do Cartão Mestre — a instalação mais simples.

É só o dashboard, para ser copiado dentro de um servidor web que a empresa
já tem (IIS, Apache, um site interno qualquer). Sem serviço de sessão, sem
nginx próprio, sem nada para instalar no servidor: copiar a pasta é a
instalação inteira.

O preço disso é que **não há login** — quem alcança a URL na rede interna vê
o dashboard, com nomes e matrículas. Se o servidor permitir restringir a
pasta (autenticação integrada do IIS, faixa de IP, grupo do AD), vale
pedir isso ao TI. Para a instalação com tela de login própria, ver
preparar-pacote.py e README-INTRANET.md.

Rode da raiz do repositório:

    python deploy/intranet/preparar-pacote-estatico.py              # com os CSVs reais
    python deploy/intranet/preparar-pacote-estatico.py --sem-dados  # só dados de exemplo

Gera `dist/cartao-mestre/` e o .zip correspondente.

Diferenças em relação ao pacote com login, além de não levar o serviço de
auth: os arquivos ficam achatados (o `index.html` vai para a raiz da pasta,
com `design-system/` e `dados/` ao lado), porque a pasta inteira é publicada
como uma URL só. Isso exige reescrever os caminhos relativos `../` que o app
usa quando é servido em `/cartaomestre/` com as pastas irmãs um nível acima.
"""
import argparse
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ajustes import AjusteNaoAplicado, despersonalizar_app, substituir  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "dist" / "cartao-mestre"

LEIA_ME = """CARTAO MESTRE - dashboard interno
=================================

INSTALACAO
----------
1. Copie a pasta "cartao-mestre" inteira para dentro do site interno
   (no IIS, normalmente C:\\inetpub\\wwwroot\\; no Apache, a pasta de
   documentos configurada).
2. Pronto. O endereco fica http://<servidor>/cartao-mestre/

Nao ha nada para instalar, configurar ou reiniciar: sao arquivos estaticos
(HTML, CSS, JavaScript) e os dados em CSV. Todo o processamento acontece no
navegador de quem abre a pagina; o servidor so entrega os arquivos.

Requisito unico: o servidor precisa entregar arquivos .csv normalmente. Em
IIS recem-instalado isso ja funciona; se a pagina abrir mas os numeros nao,
e quase sempre isso (ver "SE NAO FUNCIONAR").

DADOS
-----
As planilhas ficam em cartao-mestre\\dados\\csv\\, organizadas por ano:

  dados\\csv\\COLABORADORES.csv     <- vale para todos os anos
  dados\\csv\\GESTORES.csv          <- idem
  dados\\csv\\2026\\JANEIRO.csv      <- um arquivo por mes, dentro do ano
  dados\\csv\\2026\\FEVEREIRO.csv
  ...

Mes novo e so soltar o arquivo na pasta do ano: o dashboard descobre sozinho
no proximo carregamento. Nao precisa mexer em codigo nem avisar ninguem.
Ano novo e so criar a pasta (2027\\) e ir colocando os meses la dentro.

O nome do arquivo e o nome do mes - por extenso ou abreviado em tres letras,
maiusculo ou minusculo, tanto faz:

  JANEIRO.csv   janeiro.csv   Janeiro.csv   JAN.csv   jan.csv

Marco vale com ou sem cedilha. Nome fora desse padrao e ignorado - o mes
simplesmente nao aparece no painel.

ACESSO
------
Esta versao nao tem tela de login: qualquer pessoa que alcance o endereco na
rede interna ve o dashboard, que inclui nomes e matriculas de colaboradores.
Se for possivel restringir a pasta no servidor (autenticacao integrada do
IIS, faixa de IP, grupo do AD), vale fazer.

SE NAO FUNCIONAR
----------------
- Pagina abre, mas os numeros parecem errados ou de outra empresa: o
  servidor nao esta entregando os CSVs, e a pagina caiu nos dados ficticios
  de exemplo. No IIS, verifique se o tipo MIME .csv esta liberado.
- Pagina em branco: confirme que o index.html ficou na raiz da pasta
  copiada, com js\\, design-system\\ e dados\\ ao lado dele.
- Um mes nao aparece: nome de arquivo diferente do esperado (acento,
  grafia).
"""


def ajustar_index(caminho, versao):
    """Despersonaliza, aponta o design-system para a pasta irmã e versiona os assets."""
    html = despersonalizar_app(caminho.read_text(encoding="utf-8"), caminho.name)
    html = substituir(html, "../design-system/", "design-system/", caminho.name)
    html = versionar_assets(html, versao)
    caminho.write_text(html, encoding="utf-8")


def versionar_assets(html, versao):
    """Acrescenta ?v=<versao> aos .js/.css locais da página.

    Numa instalação estática ninguém controla cabeçalho de cache do servidor:
    depois de recopiar a pasta, o navegador de quem já tinha visitado pode
    continuar rodando o JavaScript antigo por horas — e um arquivo velho junto
    com um novo costuma dar tela em branco, não "versão anterior". Como a
    query muda a cada pacote gerado, o navegador é obrigado a buscar de novo.
    Os CSVs não precisam disso: data.js já os lê com revalidação.
    """
    return re.sub(
        r'(src|href)="((?:js|design-system)/[^"]+\.(?:js|css))"',
        lambda m: f'{m.group(1)}="{m.group(2)}?v={versao}"',
        html,
    )


def ajustar_data_js(caminho):
    js = caminho.read_text(encoding="utf-8")
    js = substituir(
        js,
        "const DATA_DIRS = ['../dados/csv/', '../dados/csv-exemplo/'];",
        "const DATA_DIRS = ['dados/csv/', 'dados/csv-exemplo/'];",
        caminho.name,
    )
    caminho.write_text(js, encoding="utf-8")


def ajustar_main_js(caminho):
    """Liga o modo sem sessão: o menu de conta some do header."""
    js = caminho.read_text(encoding="utf-8")
    js = substituir(js, "const SEM_LOGIN = false;", "const SEM_LOGIN = true;", caminho.name)
    caminho.write_text(js, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sem-dados",
        action="store_true",
        help="não inclui os CSVs reais; o pacote sobe com os dados fictícios de exemplo",
    )
    args = parser.parse_args()

    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)

    # app/ vira a raiz do pacote: index.html + js/ direto na pasta publicada.
    for item in (RAIZ / "app").iterdir():
        if item.name == "README.md":
            continue  # documentação do repositório, não do servidor
        if item.is_dir():
            shutil.copytree(item, DESTINO / item.name)
        else:
            shutil.copy2(item, DESTINO / item.name)

    shutil.copytree(RAIZ / "design-system", DESTINO / "design-system")
    shutil.copytree(RAIZ / "dados" / "csv-exemplo", DESTINO / "dados" / "csv-exemplo")

    csv_real = RAIZ / "dados" / "csv"
    destino_csv = DESTINO / "dados" / "csv"
    destino_csv.mkdir(parents=True)
    incluidos = 0
    if not args.sem_dados:
        # rglob: os arquivos mensais ficam em subpasta por ano (2026/, 2027/…),
        # e COLABORADORES/GESTORES na raiz. Preserva a mesma estrutura no
        # pacote, que é o que o app procura.
        for arquivo in sorted(csv_real.rglob("*.csv")):
            destino = destino_csv / arquivo.relative_to(csv_real)
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(arquivo, destino)
            incluidos += 1

    (DESTINO / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")

    try:
        ajustar_index(DESTINO / "index.html", datetime.now().strftime("%Y%m%d%H%M"))
        ajustar_data_js(DESTINO / "js" / "data.js")
        ajustar_main_js(DESTINO / "js" / "main.js")
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
    if incluidos:
        print(
            f"ATENÇÃO: {incluidos} CSVs reais incluídos — o zip contém nomes e\n"
            "matrículas de colaboradores. Trate como documento interno."
        )
    else:
        print("sem CSVs reais: o dashboard sobe com os dados fictícios de exemplo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
