# Instalação estática (a mais simples)

Publica o dashboard como pasta de arquivos dentro de um servidor web que a
empresa já tem — IIS, Apache, qualquer site interno. **Copiar a pasta é a
instalação inteira**: nada para instalar, nenhum serviço para registrar,
nenhum comando para rodar.

Para a instalação com tela de login própria (mais partes móveis, controle de
quem entra e histórico de acessos), ver `README-INTRANET.md`.

## O que muda em relação à versão com login

| | Estática | Com login |
|---|---|---|
| Instalação | copiar uma pasta | nginx + serviço Python + firewall |
| Precisa de admin no servidor | não (só permissão de escrita na pasta do site) | sim |
| Controle de acesso | nenhum: quem alcança a URL vê tudo | usuário e senha, papéis admin/viewer |
| Histórico de acessos | não | sim |
| Atualizar dados | substituir os CSVs na pasta | idem |

O dashboard mostra nomes e matrículas de colaboradores. Sem login, isso fica
visível para qualquer pessoa que alcance o endereço na rede interna. Se o
servidor permitir restringir a pasta — autenticação integrada do IIS, faixa
de IP, grupo do AD —, vale pedir ao TI; é a mesma proteção que outros
sistemas internos costumam usar, e não exige nada do nosso lado.

## Gerar o pacote

Da raiz do repositório:

```bash
python deploy/intranet/preparar-pacote-estatico.py              # com os CSVs reais
python deploy/intranet/preparar-pacote-estatico.py --sem-dados  # só dados de exemplo
```

Sai `dist/cartao-mestre/` e `dist/cartao-mestre.zip` (~2,6 MB), com esta
estrutura:

```
cartao-mestre/
├── index.html          ← a página
├── js/                 ← o código do dashboard
├── design-system/      ← fontes, CSS, ícones
├── dados/csv/          ← as planilhas reais
├── dados/csv-exemplo/  ← dados fictícios (fallback, se csv/ estiver vazia)
└── LEIA-ME.txt         ← instruções curtas para o TI
```

Com os CSVs reais dentro, o zip é documento interno: contém nomes e
matrículas. Se preferir mandar o pacote sem dado nenhum e colocar as
planilhas depois, use `--sem-dados`.

## O que pedir ao TI

> Preciso publicar um dashboard interno na rede. São arquivos estáticos
> (HTML/JavaScript) — não tem instalação, serviço, banco de dados nem
> dependência: é copiar a pasta anexa para dentro do site interno e o
> endereço passa a funcionar.
>
> O que preciso:
> 1. a pasta `cartao-mestre` copiada para a raiz do site interno
>    (`C:\inetpub\wwwroot\` no IIS, ou a pasta equivalente no Apache);
> 2. confirmação do endereço final (algo como
>    `http://<servidor>/cartao-mestre/`);
> 3. que o servidor entregue arquivos `.csv` normalmente — em IIS recém
>    instalado já funciona, mas se o tipo MIME estiver bloqueado a página
>    abre sem os dados;
> 4. se for possível restringir o acesso à pasta (autenticação integrada,
>    faixa de IP ou grupo do AD), prefiro assim: o painel mostra nomes e
>    matrículas de colaboradores.

## Atualizar depois

**Dados do mês** — substituir os arquivos em `dados/csv/` na pasta
publicada. A página mostra os novos números no próximo carregamento; nada
para reiniciar. Os nomes precisam bater exatamente com os atuais, acento e
tudo (inclusive `FEVEVEIRO.csv`, que vem com essa grafia da origem).

**Mês novo** — além do arquivo, entra uma linha na lista `MONTHLY_FILES` de
`js/data.js` (ver "Adicionar um novo mês" em `app/README.md`). Na prática:
gerar o pacote de novo e recopiar.

**Versão nova do dashboard** — gerar o pacote e recopiar a pasta.

## Verificação

Abrir `http://<servidor>/cartao-mestre/` de uma estação da rede. O
cabeçalho deve mostrar o período real dos dados (ex.: "jan/2026 –
abr/2026"). Se aparecerem números que não são da filial, o servidor não está
entregando os CSVs e a página caiu nos dados de exemplo — quase sempre é o
tipo MIME de `.csv` no IIS.
