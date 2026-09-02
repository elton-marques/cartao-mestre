# dados/csv/

Os CSVs desta pasta **não são versionados** (veja `.gitignore` na raiz —
`dados/csv/*.csv`), porque contêm dados pessoais reais de funcionários
(nome, matrícula, setor) — dado pessoal sob a LGPD, que não entra em repo
público. Ao clonar o repo em outra máquina, copie esses arquivos
separadamente (pendrive, OneDrive, zip à parte) para dentro desta pasta
antes de rodar o app.

Sem eles, o app não quebra: `app/js/data.js` cai automaticamente em
`../dados/csv-exemplo/`, que traz um conjunto **fictício** de mesmo
formato (ver `dados/csv-exemplo/README.md`).

Formato: português, delimitado por vírgula, UTF-8 com acentos, campos
multi-linha entre aspas.

## Arquivos esperados

- **`COLABORADORES.csv`** — registro de funcionários:
  `MATRÍCULA,NOME,FUNÇÃO,SETOR`. `MATRÍCULA` é a chave de junção com os
  logs mensais.

- **`GESTORES.csv`** — lista livre (não tabular) de gestores/aprovadores
  autorizados, sob o cabeçalho "GESTORES AUTORIZADOS". São os valores que
  populam a coluna `RESPONSÁVEL PELA AUTORIZAÇÃO` dos logs mensais, às
  vezes prefixados com código de grupo (ex.: `GR4 - FULANO DE TAL`).

- **Logs mensais de uso** — um arquivo por mês, dentro de uma pasta por ano
  (`2026/JANEIRO.csv`, `2026/FEVEREIRO.csv`, … e `2027/` quando chegar a
  virada). `COLABORADORES.csv` e `GESTORES.csv` ficam na raiz desta pasta,
  porque valem para todos os anos.
  Cada arquivo mensal é um log de uso do Cartão Mestre: quem contornou uma restrição
  de checkout/acesso, quando, e qual gestor autorizou. Layout:
  - Linha 1: banner — `Controle de Uso do Cartão Mestre,...,"FILIAL: 00\nCIDADE"`
  - Linha 2: em branco
  - Linha 3: cabeçalho real —
    `DATA,HORA,MATRÍCULA,NOME,SETOR,FUNÇÃO,MOTIVO,"RESPONSÁVEL\nPELA AUTORIZAÇÃO"`
  - Linha 4+: um registro por evento.

## Adicionar um novo mês

Coloque o CSV na pasta do ano (`2026/`), seguindo o mesmo formato (banner na
linha 1, linha em branco na linha 2, cabeçalho na linha 3). Nada mais: o app
descobre os meses sozinho a cada carregamento.

O nome do arquivo é o nome do mês, por extenso ou abreviado em três letras,
em qualquer caixa — `MAIO.csv`, `maio.csv`, `Maio.csv`, `MAI.csv` valem
igual. Março vale com ou sem cedilha, e `FEVEVEIRO.csv` (o typo da fonte
original) continua aceito, embora os arquivos daqui já usem `FEVEREIRO.csv`.

Ano novo: crie a pasta (`2027/`) e coloque os meses lá dentro. Com mais de um
ano publicado, os rótulos do painel passam a incluir o ano ("Janeiro/2026").

Mais detalhes de limpeza/normalização em `app/README.md`.
