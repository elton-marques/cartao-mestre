# Cartão Mestre

Dashboard de controle de uso do cartão mestre — quem contornou uma
restrição de checkout, quando e qual gestor autorizou. App estático
client-side (HTML + JS puro, sem build/framework), publicado em
`eltonmarques.com/cartaomestre` atrás de login por sessão.

> **Dados.** Este repositório não contém dado pessoal real. Os CSVs de
> produção (nome, matrícula, setor de funcionários — dado pessoal sob a
> LGPD) ficam fora do versionamento; o que está aqui é o conjunto
> fictício de `dados/csv-exemplo/`, gerado por
> `dados/csv-exemplo/gerar.py`.

## Estrutura

- `app/` — o dashboard em si (ver `app/README.md` pra detalhes de
  estrutura, como rodar localmente e as decisões de limpeza dos dados)
- `dados/csv/` — os CSVs de origem (dados reais, **não versionados** — ver
  `dados/csv/README.md`)
- `dados/csv-exemplo/` — conjunto fictício de mesmo formato, versionado, que
  o app usa quando `dados/csv/` não existe (é o que roda num clone limpo)
- `design-system/` — fontes self-hosted, runtime Tailwind e ícones usados
  pelo dashboard e pela tela de login
- `deploy/login/` — tela de login própria (substitui o Basic Auth nativo)
- `deploy/auth-service/` — serviço Python (stdlib, sem dependências) de
  sessão por cookie
- `deploy/nginx/cartao-mestre.conf`, `deploy/systemd/` — config de
  publicação na VPS
- `deploy/README.md` — como o deploy funciona (VPS, Cloudflare Tunnel,
  fluxo de login, passo a passo pra publicar uma atualização)

## Projeto irmão

A landing pessoal em `eltonmarques.com/` (raiz) — de onde se chega até
este dashboard — vive num repo separado:
[eltonmarques-site](https://github.com/elton-marques/eltonmarques-site).

## Deploy

Ver `deploy/README.md`.
