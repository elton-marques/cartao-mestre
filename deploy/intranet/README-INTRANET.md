# Instalação do Cartão Mestre em servidor de intranet

Documento de instalação para a equipe de TI. Descreve como publicar o
dashboard **Cartão Mestre** em um servidor da rede interna, acessível pelo
navegador dos usuários em `http://<servidor>/cartaomestre/`.

Esta pasta (`deploy/intranet/`) contém a variante dos arquivos de
configuração para rede interna. A pasta irmã `deploy/` documenta a
instalação pública original (VPS + Cloudflare Tunnel) e **não** deve ser
usada aqui — as duas diferem em pontos que quebram o login se misturados.

---

## 1. O que é o sistema

Três peças, todas rodando no mesmo servidor:

| Peça | O que é | Onde escuta |
|---|---|---|
| Dashboard | Site estático (HTML/CSS/JavaScript). Não tem backend, não escreve nada: lê arquivos CSV e monta os gráficos no navegador do usuário. | servido pelo nginx |
| nginx | Servidor web. Publica o dashboard, a tela de login e os CSVs; exige sessão válida antes de entregar dado. | `0.0.0.0:80` |
| Serviço de sessão | Script Python (`server.py`), só biblioteca padrão — **sem pip, sem venv, sem dependência externa**. Valida usuário/senha e assina o cookie de sessão. | `127.0.0.1:8082` (nunca exposto à rede) |

Os dados ficam em arquivos CSV lidos de uma pasta de rede (seção 4). O
sistema não usa banco de dados de negócio; o único SQLite existente guarda
apenas os usuários do login e o histórico de acessos.

### Requisitos

- Servidor Linux (Ubuntu/Debian/RHEL) **ou** Windows Server.
- nginx (qualquer versão atual; precisa do módulo `http_auth_request`, que
  vem compilado por padrão nos pacotes oficiais e no build oficial para
  Windows).
- Python 3.8 ou superior.
- Porta 80/TCP liberada no firewall do servidor para a faixa de IPs da rede
  interna. Nenhuma porta precisa ser aberta para a internet.
- Acesso de leitura à pasta de rede onde ficam os CSVs (seção 4).

### Antes de começar: HTTP sem criptografia

A instalação descrita aqui serve o app por **HTTP puro**, sem certificado.
Nesse modo, a senha digitada na tela de login e o cookie de sessão trafegam
em texto claro pela rede interna, legíveis por quem conseguir capturar o
tráfego do segmento. Isso é aceitável em muitas redes corporativas
fechadas, mas é uma decisão de segurança que cabe à TI — não uma
recomendação deste documento.

Se houver certificado interno disponível (CA corporativa), configure o
nginx com TLS na porta 443 e, no serviço de sessão, **remova** a linha
`CM_COOKIE_SECURE=0` das seções 5/6 abaixo: com HTTPS, o cookie volta a
ficar marcado como `Secure`, que é o comportamento correto.

---

## 2. Arquivos que compõem a entrega

O pacote entregue (`cartao-mestre-intranet.zip`) contém:

```
app/                  → dashboard (HTML + JS)
design-system/        → fontes, CSS e JS do tema visual
dados/csv-exemplo/    → dados fictícios; o app usa isso enquanto a pasta de rede não estiver disponível
deploy/login/         → tela de login e página de histórico de acessos
deploy/auth-service/  → serviço de sessão em Python (server.py, db.py, manage_users.py)
deploy/intranet/      → os arquivos de configuração citados neste documento
```

Não é necessário compilar nem instalar dependências: o dashboard não tem
etapa de build e o serviço Python usa apenas a biblioteca padrão.

Os CSVs reais não vão no pacote — eles vêm da pasta de rede (seção 4).

> Nota para quem mantém o projeto: o pacote é gerado com
> `python deploy/intranet/preparar-pacote.py`, a partir da raiz do
> repositório. Além de copiar os arquivos, o script remove da versão interna
> os links que só existem no site pessoal (voltar ao hub, e-mail, GitHub,
> domínio no rodapé) e faz o "Sair" ir direto para a tela de login. Se algum
> desses trechos mudar no HTML, o script falha e não gera pacote — de
> propósito, para não publicar link morto sem ninguém perceber.

---

## 3. Layout no servidor

### Linux

```
/var/www/cartao-mestre/
├── app/               ← cópia de app/
├── design-system/     ← cópia de design-system/
└── dados/csv/         ← ponto de montagem da pasta de rede com os CSVs

/var/www/login/
├── index.html         ← deploy/login/index.html
└── historico.html     ← deploy/login/historico.html

/opt/cartao-mestre-auth/
├── server.py
├── db.py
└── manage_users.py

/etc/cartao-mestre/     ← criado na primeira execução; contém dados sensíveis
├── cartao-mestre.db   ← usuários (senha com hash) + histórico de login
└── secret.key         ← chave que assina os cookies de sessão
```

### Windows Server

Mesmo desenho, com raízes diferentes:

```
C:\inetdata\cartao-mestre\{app,design-system,dados\csv}
C:\inetdata\login\{index.html,historico.html}
C:\Servicos\cartao-mestre-auth\{server.py,db.py,manage_users.py}
C:\ProgramData\cartao-mestre\{cartao-mestre.db,secret.key}
```

A pasta `C:\ProgramData\cartao-mestre` guarda hash de senha e chave de
assinatura: restrinja o acesso NTFS à conta que roda o serviço e aos
administradores.

---

## 4. Origem dos dados (pasta de rede)

Os CSVs (`JANEIRO.csv`, `FEVEVEIRO.csv`, `MARÇO.csv`, `ABRIL.csv`,
`COLABORADORES.csv`, `GESTORES.csv`) ficam em um compartilhamento de rede
onde a equipe já salva as planilhas. O servidor só precisa de **leitura**.

Dois detalhes importantes:

- Os nomes dos arquivos são lidos exatamente como estão, **com acento e com
  o erro de grafia de origem** (`FEVEVEIRO.csv`, não `FEVEREIRO.csv`). O
  compartilhamento e a montagem precisam preservar acentuação — daí o
  `iocharset=utf8` no exemplo abaixo.
- Se a pasta estiver vazia ou inacessível, o dashboard **não quebra**: ele
  cai automaticamente nos dados fictícios de exemplo que acompanham a
  aplicação. Ou seja, um dashboard que abre com números estranhos é o
  sintoma típico de montagem que falhou — vale conferir a seção 8.

### Linux — montar o compartilhamento (CIFS/SMB)

```bash
sudo apt install cifs-utils                    # Debian/Ubuntu

# Credenciais de uma conta de serviço só-leitura, fora do fstab:
sudo install -m 600 /dev/null /etc/cartao-mestre-share.cred
sudo tee /etc/cartao-mestre-share.cred >/dev/null <<'EOF'
username=CONTA_DE_SERVICO
password=SENHA
domain=DOMINIO
EOF

sudo mkdir -p /var/www/cartao-mestre/dados/csv
```

Em `/etc/fstab`, uma linha (ajuste servidor/compartilhamento e o `uid` para
o usuário que roda o nginx — `www-data` no Debian/Ubuntu, `nginx` no RHEL):

```
//servidor-arquivos/compartilhamento/CartaoMestre  /var/www/cartao-mestre/dados/csv  cifs  credentials=/etc/cartao-mestre-share.cred,ro,iocharset=utf8,uid=www-data,gid=www-data,file_mode=0440,dir_mode=0550,_netdev,nofail  0  0
```

```bash
sudo mount -a
ls -l /var/www/cartao-mestre/dados/csv     # deve listar os CSVs
```

`nofail` evita que o servidor pare o boot se o compartilhamento estiver
indisponível — combinando com o fallback do dashboard, uma indisponibilidade
do file server degrada a tela, não derruba o serviço.

### Windows — dar acesso ao compartilhamento

Serviço rodando sob conta de domínio com leitura no compartilhamento; então,
como Administrador:

```
mklink /J C:\inetdata\cartao-mestre\dados\csv \\servidor-arquivos\compartilhamento\CartaoMestre
```

Se a junção para caminho UNC não funcionar no ambiente, a alternativa é uma
tarefa agendada que copia os arquivos do compartilhamento para a pasta local
uma vez por dia (`robocopy \\servidor\share\CartaoMestre C:\inetdata\cartao-mestre\dados\csv /MIR`).
Nesse caso o dashboard mostra os dados da última cópia, não os do instante.

---

## 5. Instalação no Linux

```bash
# 1. Estrutura e arquivos estáticos (a partir da pasta do projeto)
sudo mkdir -p /var/www/cartao-mestre /var/www/login /opt/cartao-mestre-auth
sudo cp -r app design-system /var/www/cartao-mestre/
sudo cp deploy/login/index.html deploy/login/historico.html /var/www/login/
sudo cp deploy/auth-service/server.py deploy/auth-service/db.py \
        deploy/auth-service/manage_users.py /opt/cartao-mestre-auth/

# 2. Usuário de serviço (sem shell, sem home)
sudo useradd --system --no-create-home --shell /usr/sbin/nologin cartaomestre
sudo mkdir -p /etc/cartao-mestre
sudo chown cartaomestre:cartaomestre /etc/cartao-mestre
sudo chmod 750 /etc/cartao-mestre

# 3. Serviço de sessão
sudo cp deploy/intranet/cartao-mestre-auth.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cartao-mestre-auth
systemctl status cartao-mestre-auth        # deve estar "active (running)"

# 4. nginx
sudo cp deploy/intranet/nginx-cartao-mestre-intranet.conf \
        /etc/nginx/sites-available/cartao-mestre.conf
sudo ln -s /etc/nginx/sites-available/cartao-mestre.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default     # se o vhost padrão ocupar a porta 80
sudo nginx -t && sudo systemctl reload nginx

# 5. Firewall (exemplo com ufw; ajuste a faixa da rede interna)
sudo ufw allow from 10.0.0.0/8 to any port 80 proto tcp
```

Em RHEL/Rocky, o arquivo do nginx vai em `/etc/nginx/conf.d/cartao-mestre.conf`
(sem `sites-enabled`), o usuário do nginx é `nginx`, e o SELinux precisa
liberar a conexão do nginx com o serviço local:

```bash
sudo setsebool -P httpd_can_network_connect 1
```

---

## 6. Instalação no Windows Server

O mesmo desenho, com o build oficial do nginx para Windows
(<https://nginx.org/en/download.html>) descompactado em `C:\nginx`.

1. **Arquivos** — copie `app\` e `design-system\` para
   `C:\inetdata\cartao-mestre\`, os dois HTML de `deploy\login\` para
   `C:\inetdata\login\`, e os três `.py` de `deploy\auth-service\` para
   `C:\Servicos\cartao-mestre-auth\`.

2. **nginx** — use `deploy\intranet\nginx-cartao-mestre-intranet.conf` como
   bloco `server` dentro de `C:\nginx\conf\nginx.conf`, trocando os caminhos
   Linux pelos do Windows **com barras normais**, que é o que o nginx espera:

   ```
   root C:/inetdata/cartao-mestre;
   ...
   location /cartaomestre/   { ... alias C:/inetdata/cartao-mestre/app/; ... }
   location /design-system/  { alias C:/inetdata/cartao-mestre/design-system/; }
   location /dados/          { ... alias C:/inetdata/cartao-mestre/dados/; ... }
   location /login/          { alias C:/inetdata/login/; ... }
   ```

3. **Porta 80** — se o IIS já estiver ocupando a porta, ou pare o site
   padrão, ou troque para `listen 8080;` no nginx e divulgue a URL com a
   porta.

4. **Serviço de sessão** — o Python não vira serviço do Windows sozinho.
   Com o [NSSM](https://nssm.cc/) (`nssm install`):

   - Application: `C:\Program Files\Python312\python.exe`
   - Arguments: `C:\Servicos\cartao-mestre-auth\server.py`
   - Startup directory: `C:\Servicos\cartao-mestre-auth`
   - Environment (aba *Environment*, uma variável por linha):

     ```
     CM_COOKIE_SECURE=0
     CM_DB_FILE=C:\ProgramData\cartao-mestre\cartao-mestre.db
     CM_SECRET_FILE=C:\ProgramData\cartao-mestre\secret.key
     ```

   - Log On: a conta de domínio com leitura no compartilhamento dos CSVs.

   Sem NSSM, uma Tarefa Agendada com gatilho "ao iniciar o sistema",
   executando o mesmo comando sob a mesma conta, resolve — só perde o
   reinício automático em caso de falha.

5. **nginx como serviço** — o nginx para Windows também roda em primeiro
   plano por padrão; registre-o com NSSM da mesma forma (`C:\nginx\nginx.exe`).

6. **Firewall** — regra de entrada para TCP 80 (ou 8080) restrita à faixa da
   rede interna.

---

## 7. Usuários do sistema

Não há cadastro pela tela: usuários são criados no servidor, por linha de
comando. Dois papéis:

- **admin** — usa o dashboard e enxerga o item "Histórico de login" no menu
  de conta, que lista quem acessou, quando, de qual IP e de qual navegador.
- **viewer** — usa o dashboard. É o padrão, e é o papel adequado para a
  maioria.

```bash
# Linux
sudo -u cartaomestre CM_DB_FILE=/etc/cartao-mestre/cartao-mestre.db \
  python3 /opt/cartao-mestre-auth/manage_users.py add 'usuario' 'senha' viewer
sudo -u cartaomestre CM_DB_FILE=/etc/cartao-mestre/cartao-mestre.db \
  python3 /opt/cartao-mestre-auth/manage_users.py list
```

```powershell
# Windows (PowerShell, como a conta do serviço ou administrador)
$env:CM_DB_FILE = "C:\ProgramData\cartao-mestre\cartao-mestre.db"
python C:\Servicos\cartao-mestre-auth\manage_users.py add 'usuario' 'senha' viewer
```

Subcomandos: `add <usuario> <senha> [papel]`, `del <usuario>`,
`role <usuario> <admin|viewer>`, `list`.

A senha nunca é gravada em texto puro — o banco guarda hash PBKDF2-HMAC-SHA256
com salt individual e 100 mil iterações. Não existe recuperação de senha:
para redefinir, remova e recrie o usuário.

A sessão dura 12 horas; depois disso o usuário loga de novo.

---

## 8. Verificação pós-instalação

Do próprio servidor:

```bash
curl -si http://localhost/cartaomestre/ | head -1     # 302 (redireciona pro login) — correto
curl -si http://localhost/login/        | head -1     # 200
curl -si -X POST http://localhost/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"usuario","password":"senha"}' | head -20
```

A resposta do login precisa trazer `HTTP/1.1 200` **e** um cabeçalho
`Set-Cookie: cm_session=...`. Se o `Set-Cookie` contiver a palavra `Secure`
em uma instalação HTTP, o login vai falhar no navegador — falta a variável
`CM_COOKIE_SECURE=0` (seção 5/6).

De uma estação da rede, abra `http://<ip-ou-nome-do-servidor>/cartaomestre/`:
deve cair na tela de login, e após autenticar, mostrar o dashboard com os
meses reais vindos da pasta de rede.

### Sintomas comuns

| Sintoma | Causa provável |
|---|---|
| Login aceita a senha mas a tela volta para o login | Cookie com `Secure` em conexão HTTP. Confirme `CM_COOKIE_SECURE=0` e reinicie o serviço de sessão. |
| Toda página cai em 502 | Serviço de sessão parado. `systemctl status cartao-mestre-auth` / serviço no Windows. |
| Dashboard abre com dados que não são da filial | Pasta de rede não montada; o app entrou no fallback de dados de exemplo. Confira a seção 4. |
| Um mês não aparece | Nome do arquivo diferente do esperado (acento, grafia). Os nomes precisam bater exatamente. |
| Histórico de login mostra IP `127.0.0.1` | O bloco `/auth/` do nginx está sem `proxy_set_header X-Forwarded-For`. |
| Histórico mostra país/cidade em branco | Esperado: essa informação vinha da borda da Cloudflare, que não existe na intranet. |

---

## 9. Atualizações

**Novo mês de dados** — o arquivo do mês entra na pasta de rede e a
aplicação precisa passar a conhecê-lo: é uma linha na lista `MONTHLY_FILES`
de `app/js/data.js` (ver `app/README.md`, seção "Adicionar um novo mês").
Feita a alteração no projeto, basta recopiar a pasta `app/` para o servidor;
não há reinício de serviço nem de nginx.

**Nova versão do dashboard** — recopiar `app/` e `design-system/`. Os
arquivos são servidos com `Cache-Control: no-store`, então o usuário pega a
versão nova no próximo carregamento, sem limpar cache.

**Serviço de sessão** — recopiar os `.py` e reiniciar o serviço
(`sudo systemctl restart cartao-mestre-auth`, ou o serviço equivalente no
Windows).

## 10. Backup

Um único item precisa de backup: `/etc/cartao-mestre/` no Linux, ou
`C:\ProgramData\cartao-mestre\` no Windows — usuários, senhas e histórico de
acessos. Os CSVs já estão sob a política de backup do file server, e o resto
é código, reinstalável a partir do repositório.

Trocar ou perder `secret.key` invalida todas as sessões ativas (os usuários
precisam logar de novo), mas não perde nenhum cadastro.
