# Dashboard Cartão Mestre

App estático client-side (HTML + JS puro, sem build/framework) que lê os
CSVs de `dados/csv/` (ou, na ausência deles, os fictícios de
`dados/csv-exemplo/`), aplica a limpeza descrita abaixo e renderiza o
dashboard. Reaproveita o runtime Tailwind já embutido em
`design-system/assets/` para manter a mesma linguagem visual do template
do projeto (tema escuro, cards `rounded-3xl`).

## Rodar localmente

O navegador bloqueia `fetch()` de arquivos locais abertos direto via
`file://`, então é preciso servir a pasta por HTTP. Rode a partir da
**raiz do repositório** (não da pasta `app/`), para que `app/` consiga
acessar `../dados/csv/` corretamente:

```bash
# opção 1 — Node (não precisa instalar nada além do Node)
npx serve .

# opção 2 — Python
python -m http.server 8080
```

Depois abra `http://localhost:PORTA/app/` no navegador.

Sem nenhum CSV real em `dados/csv/`, o app cai automaticamente em
`dados/csv-exemplo/` (dados fictícios versionados) — é o que roda em quem
acabou de clonar o repositório.

## Estrutura

- `index.html` — shell da página e filtros
- `js/csv.js` — parser CSV (lida com aspas/quebras de linha embutidas)
- `js/normalize.js` — normalização de SETOR/MOTIVO/RESPONSÁVEL
- `js/data.js` — resolução do diretório de dados (`DATA_DIRS`),
  carregamento dos 6 CSVs + limpeza (ETL)
- `js/aggregate.js` — KPIs, rankings, heatmap, qualidade de dados
- `js/export.js` — exportação da lista/agregados filtrados em CSV, planilha
  Excel (SpreadsheetML, várias abas) e relatório PDF (via impressão do
  navegador) — tudo montado no cliente, sem lib nem servidor
- `js/render.js` — renderização em DOM puro
- `js/main.js` — bootstrap, filtros interativos, sessão (logout/troca de conta)

## Decisões de limpeza (ver plano completo para o racional)

- Linhas sem data em `dd/mm/aaaa` na 1ª coluna são descartadas (isso já
  remove banner, cabeçalho, linhas em branco e o rodapé fixo
  `FOR.PRP.0017...` de cada arquivo mensal).
- Duplicatas exatas (mesma linha inteira) são removidas e contadas.
- `SETOR`/`MOTIVO`/`RESPONSÁVEL` passam por normalização de
  caixa/espaço/traço; `SETOR` tem também um dicionário pequeno de
  apelidos conhecidos (`js/normalize.js`) — extensível conforme novos
  meses revelarem novas variações.
- Matrícula vazia ou sem correspondência em `COLABORADORES.csv` vira
  `naoCadastrado: true` (exibido como "órfã"), nunca é descartada.
- Aprovador fora de `GESTORES.csv` vira `aprovadorNaoAutorizado: true`
  e aparece no painel de alerta vermelho.
- Datas com ano anterior a 2020 (a fonte real tem uma) **não são
  corrigidas automaticamente** — só entram na contagem do painel de
  qualidade.

## Adicionar um novo mês

Solte o CSV em `dados/csv/` com o nome do mês em maiúsculas (`MAIO.csv`) e
pronto. Nenhum arquivo de código precisa ser tocado: filtro de período,
tendência mensal, KPIs e o texto do cabeçalho ("jan/2026 – mai/2026") se
recalculam sozinhos no próximo carregamento da página.

O formato do arquivo é o mesmo dos existentes: banner na linha 1, linha 2 em
branco, cabeçalho real na linha 3 — ver `CLAUDE.md` da raiz do repo.

Como a descoberta é feita: não dá para listar o conteúdo de uma pasta pelo
navegador (servidor web não entrega índice de diretório por padrão, e é isso
que permite servir o dashboard como arquivos estáticos em qualquer lugar).
Então o app pede ao servidor cada nome de mês possível e fica com os que
existem — ver `MESES_CANONICOS` em `app/js/data.js`.

Por isso o nome importa: precisa ser o nome do mês em maiúsculas. As grafias
alternativas aceitas estão na mesma lista — `FEVEVEIRO.csv` (o typo que veio
do arquivo-fonte original) continua valendo, e março é aceito com ou sem
cedilha. Nome fora dessas opções é simplesmente ignorado, sem erro na tela.

Arquivo que existe mas não tem nenhuma linha de liberação válida fica de fora
do dashboard (com um aviso no console do navegador) — um mês zerado na
tendência sugeriria "não houve ocorrência" quando o caso real é arquivo vazio
ou fora do formato.

## Pendente

- Nenhuma decisão de framework/backend foi necessária: por ser 100%
  client-side, não há servidor de aplicação a escolher. Se o volume de
  dados crescer muito ou for preciso persistir estado entre usuários,
  reavaliar.
