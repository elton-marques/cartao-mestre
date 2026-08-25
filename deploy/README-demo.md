# Deploy de demonstração — eltonmarques.com/cartaomestre-demo

Segunda instância do Cartão Mestre, isolada de produção (`deploy/README.md`),
com dados fictícios e sem login. Não altera nada do deploy real.

## Diferenças em relação a produção

| | Produção | Demo |
|---|---|---|
| Deploy na VPS | `scp` manual (ver `deploy/README.md`) | `git clone` — atualiza com `git pull` |
| URL | `eltonmarques.com/cartaomestre/` | `eltonmarques.com/cartaomestre-demo/app/` (redirect a partir de `/cartaomestre-demo`) |
| Porta nginx | `127.0.0.1:8080` | `127.0.0.1:8083` |
| Login | sim (`deploy/login/` + `cartao-mestre-auth.service`) | não — sem `auth_request`, sem processo de auth |
| Dados | `dados/csv/` real | só `dados/csv-exemplo/` (fictício) |
| `X-Robots-Tag` | não | `noindex, nofollow` em toda a instância |
| Aviso na UI | não | banner fixo "ambiente de demonstração" |
| Processo systemd próprio | `cartao-mestre-auth.service` | nenhum — app é estático, só a location nova no nginx já basta |

## Por que `/cartaomestre-demo/app/` e não `/cartaomestre-demo/` puro

`app/index.html` e `app/js/data.js` usam paths **relativos**
(`../design-system/`, `../dados/csv/`), que resolvem contra a profundidade
da URL atual — não contra o nome do path. Em produção isso funciona porque
`/cartaomestre/` tem 1 segmento e `../dados/` sobe pra `/dados/`, location
irmã dedicada.

Se a demo fosse servida em `/cartaomestre-demo/` (também 1 segmento), a
mesma conta faria `../dados/` subir pra `/dados/` — a location de
**produção**, que exige cookie de sessão. Sem serviço de auth na demo, o
fetch bateria 401 e o dashboard quebraria (sem vazar dado real, mas sem
subir também).

Com `/cartaomestre-demo/app/` (2 segmentos), `../dados/` resolve pra
`/cartaomestre-demo/dados/` — location própria desta instância, isolada.
Zero mudança em `app/js/data.js`. `/cartaomestre-demo` (sem barra) e
`/cartaomestre-demo/` redirecionam pra `.../app/` automaticamente (nginx),
então o link que se divulga pode ser só `/cartaomestre-demo`.

## Banner de aviso

`app/index.html` tem um banner fixo (`#demo-banner`) que só aparece quando
`location.pathname` contém `/cartaomestre-demo/` — checagem em runtime, não
arquivo separado. Mesmo `app/index.html` serve as duas instâncias (2º
checkout do mesmo repo), sem divergir a fonte de verdade.

## Deploy inicial

Na VPS:

```bash
KEY=~/caminho/para/sua/chave.key
VPS=ubuntu@<ip-da-vps>

# 1. Segundo checkout — repositório público, não precisa de credencial
ssh -i "$KEY" "$VPS" 'sudo mkdir -p /var/www/cartao-mestre-demo && \
  sudo chown ubuntu:ubuntu /var/www/cartao-mestre-demo && \
  git clone https://github.com/elton-marques/cartao-mestre.git /var/www/cartao-mestre-demo'

# 2. Nginx
scp -i "$KEY" deploy/nginx/cartao-mestre-demo.conf "$VPS":/tmp/ && \
  ssh -i "$KEY" "$VPS" 'sudo mv /tmp/cartao-mestre-demo.conf /etc/nginx/sites-available/ && \
    sudo ln -sf /etc/nginx/sites-available/cartao-mestre-demo.conf /etc/nginx/sites-enabled/ && \
    sudo nginx -t && sudo systemctl reload nginx'

# 3. Confere localmente na VPS (antes do túnel/Cloudflare)
ssh -i "$KEY" "$VPS" 'curl -sI http://127.0.0.1:8083/cartaomestre-demo/app/ | head -1'
```

Não há `scp` de `app/`/`design-system/`/`dados/` — o `git clone` já traz
tudo. `dados/csv/` não vem (gitignored, nunca existiu neste checkout), então
`data.js` cai automaticamente pro fallback `dados/csv-exemplo/`.

## Atualizar depois

```bash
ssh -i "$KEY" "$VPS" 'cd /var/www/cartao-mestre-demo && git pull'
```

Sem reload de nginx nem restart de processo — é tudo estático.

## Roteamento no Cloudflare Tunnel (passo manual, fora do repo)

Igual à produção, essa config vive só no painel Cloudflare Zero Trust (não
tem `config.yml` local pra versionar) — adicionar uma entrada de *Public
Hostname*, ANTES das entradas catch-all existentes (ordem importa — a
primeira que casa vence):

```
eltonmarques.com/cartaomestre-demo   → http://localhost:8083
```

Sem token de API da Cloudflare disponível neste ambiente pra automatizar —
precisa ser feito no painel (Zero Trust → Networks → Tunnels →
`leitor-matriculas` → Public Hostnames) ou me passar um token com escopo de
`Cloudflare Tunnel:Edit` pra eu configurar via API.

## Teste final (depois do passo acima)

- `https://eltonmarques.com/cartaomestre-demo` → redireciona pra
  `.../cartaomestre-demo/app/`, carrega sem tela de login.
- Banner "ambiente de demonstração" visível no topo.
- KPIs/gráficos populados com nomes/matrículas fictícios (`dados/csv-exemplo/`).
- `curl -sI` na resposta mostra `X-Robots-Tag: noindex, nofollow`.
- Console do navegador sem erro 404 de asset (css/js/ícones sob o subpath).
