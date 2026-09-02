# dados/csv-exemplo/

Conjunto de dados **fictício**, versionado, com o mesmo formato dos CSVs
reais de `dados/csv/` (que nunca entram no repositório — ver
`dados/csv/README.md`).

Nada aqui é dado pessoal real: nomes, matrículas, setores, funções e
gestores são sorteados a partir das listas de `gerar.py`. Qualquer
coincidência com uma pessoa real é acaso da combinação de nomes comuns.

O app usa esta pasta automaticamente quando `dados/csv/` não existe — é o
que roda num clone limpo do repositório. A resolução fica em `DATA_DIRS`,
no topo de `app/js/data.js`.

## O que é imitado dos dados reais

A forma, não o conteúdo — para o dashboard ter o que mostrar em todos os
painéis:

- volume por mês (jan–abr/2026, em `2026/`, mesmo layout de pasta por ano
  dos dados reais) e concentração de horários no expediente
  (07:40–20:20);
- distribuição de motivos, com `HORÁRIO NEGADO` dominando;
- gestores com pesos diferentes, alguns grafados com travessão (`–`) em
  vez de hífen;
- variações de setor que o dicionário de apelidos de `app/js/normalize.js`
  resolve (`MOVEIS`, `PISOS`, `ELETRO`, `ACESSORIOS P/ BANHEIRO`);
- os casos de qualidade de dados: matrícula em branco, matrícula sem
  correspondência em `COLABORADORES.csv` ("órfã"), aprovador fora de
  `GESTORES.csv`, duplicatas exatas, setor `0` e uma data com ano
  anterior a 2020.

## Regerar

Da raiz do repositório:

```bash
python dados/csv-exemplo/gerar.py
```

A saída vai para `2026/` (arquivos mensais) e para a raiz
(`COLABORADORES.csv`, `GESTORES.csv`).

A semente é fixa (`random.seed`), mas a geração passa por conjuntos, cuja
ordem de iteração muda a cada processo — então regerar produz outro conjunto
com as mesmas características, não um arquivo idêntico. Mudar a
semente ou as listas gera outro conjunto com as mesmas características.
