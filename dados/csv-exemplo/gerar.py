# -*- coding: utf-8 -*-
"""Regera os CSVs fictícios de dados/csv-exemplo/.

Rode a partir da raiz do repositório: `python dados/csv-exemplo/gerar.py`.
Nenhum dado real entra aqui — nomes, matrículas e gestores são sorteados a
partir das listas deste arquivo, com a mesma *forma* dos dados reais
(distribuição de horários, motivos, matrículas órfãs, duplicatas) para o
dashboard ter o que mostrar.
"""
import io, os, random, datetime

random.seed(20260823)
OUT = 'dados/csv-exemplo'

PRIMEIROS = """ADRIANA ALINE AMANDA ANA BEATRIZ BRUNO CAIO CAMILA CARLA CARLOS CLAUDIA CRISTIANE
DANIEL DANIELA DIEGO EDUARDO ELAINE ELIAS FABIANA FELIPE FERNANDA GABRIEL GISELE
GUSTAVO HELENA IGOR ISABELA IVAN JANAINA JOANA JOAO JORGE JULIANA LARISSA LEANDRO
LETICIA LUCAS LUCIANA MARCELO MARCIA MARCOS MARIANA MATEUS NATALIA OTAVIO PATRICIA
PAULO PEDRO PRISCILA RAFAEL RAQUEL RENATA RICARDO RODRIGO ROSANA SAMUEL SANDRA
SERGIO SILVIA SIMONE TARCISIO TATIANA THIAGO VANESSA VICTOR VIVIANE WAGNER""".split()
MEIOS = """ALVES BARBOSA CARDOSO CORREIA COSTA CUNHA DIAS DUARTE FARIAS FERNANDES
FREITAS GOMES LEITE LIMA LOPES MACHADO MARTINS MELO MENDES MOREIRA NASCIMENTO NEVES
NOGUEIRA NUNES PEREIRA PINHEIRO RAMOS REIS RIBEIRO ROCHA SANTOS SILVA SOARES SOUZA
TEIXEIRA VIEIRA""".split()
LIGACOES = ['DA', 'DE', 'DOS']
PLURAIS = set('SANTOS REIS RAMOS NEVES DIAS FARIAS'.split())
MASCULINOS = set("""BRUNO CAIO CARLOS DANIEL DIEGO EDUARDO ELIAS FELIPE GABRIEL GUSTAVO IGOR
IVAN JOAO JORGE LEANDRO LUCAS MARCELO MARCOS MATEUS OTAVIO PAULO PEDRO RAFAEL RICARDO
RODRIGO SAMUEL SERGIO TARCISIO THIAGO VICTOR WAGNER""".split())

SETORES = [
    'ACESSORIOS PARA BANHEIRO', 'BALCAO DE FERRAMENTAS', 'CABOS E FIOS', 'CAIXA',
    'CREDIARIO', 'DEPOSITOS INTERNOS', 'ELETRODOMESTICOS-ELETROPORTATEIS',
    'ENTREGA', 'EXPEDICAO', 'FRENTE DE LOJA', 'JARDINAGEM', 'LIMPEZA',
    'MANUTENCAO INFRAESTRUTURA', 'MATERIAL ELETRICO', 'METAIS SANITARIOS',
    'MOVEIS E COZINHAS', 'PISOS E REVESTIMENTOS', 'PREVENCAO DE PERDAS',
    'RECEPCAO DE MERCADORIA - LOJA', 'RECURSOS HUMANOS', 'TECNOLOGIA DA INFORMACAO',
    'TESOURARIA', 'TINTAS E ACESSORIOS', 'TRANSPORTE PESADO',
    'UTILIDADES DOMESTICAS - PLASTICOS', 'UTILIDADES DOMESTICAS - PRESENTES', 'VENDAS',
]
# Variações que o dicionário de apelidos de normalize.js resolve.
SETOR_VARIACOES = {
    'MOVEIS E COZINHAS': ['MOVEIS', u'Móveis e Cozinhas'],
    'PISOS E REVESTIMENTOS': ['PISOS', 'pisos e revestimentos'],
    'ELETRODOMESTICOS-ELETROPORTATEIS': ['ELETRO'],
    'ACESSORIOS PARA BANHEIRO': ['ACESSORIOS P/ BANHEIRO'],
}
FUNCOES = [
    'ATENDENTE', 'VENDEDOR', 'PROMOTOR(A)', 'AUX. DE DEPOSITO', 'CONFERENTE DE MERCADORIA',
    'ELETRICISTA', 'AUX.ENTREGA EXTERNA', 'OPERADOR DE EMPILHADEIRA', 'FRENTE DE LOJA',
    'APRENDIZ EM SERVICOS VENDAS', 'AUX. ADMINISTRATIVO', 'AUXILIAR DE LIMPEZA SANITARIA',
    'OPERADOR DE LOJA', 'AUX. DE PREVENCAO DE PERDAS', 'APROVADOR DE CREDITO',
    'TESOUREIRO', 'OPERADOR DE COMPUTADOR', 'AUX. DE ASSISTENCIA TECNICA',
    'MOTORISTA', 'SUPERVISOR DE VENDAS',
]
MOTIVOS = ([u'HORÁRIO NEGADO'] * 88 + ['FOLGA FIXA'] * 4 + [u'ESQUECEU CRACHÁ'] * 3
           + [u'PERDEU CRACHÁ'] * 2 + ['ADM', 'RH', 'OUTRA FILIAL']
           + [u'ARMÁRIO', 'ARMARIOS'])

GESTORES = ['GR1 - ADRIANO', 'GR2 - BEATRIZ', 'GR3 - CLARA', 'GR4 - DENISE',
            'GR5 - EDUARDO', 'GRL - FLAVIA', 'HELIO', 'IARA', 'JONAS', 'KELLY',
            'LUCIO', 'MARINA', 'NILDO', 'OSCAR']
PESO_GESTOR = [30, 8, 16, 4, 15, 14, 10, 6, 12, 5, 8, 7, 3, 3]
# Aprovadores fora do GESTORES.csv — alimentam o alerta de aprovador não autorizado.
NAO_AUTORIZADOS = ['QUEZIA', 'ROMULO', 'TEREZA']


def nome_completo():
    primeiro = random.choice(PRIMEIROS)
    partes = [primeiro]
    if random.random() < 0.55:
        partes.append(random.choice(PRIMEIROS))
    partes.append(random.choice(MEIOS))
    if random.random() < 0.6:
        sobrenome = random.choice(MEIOS)
        ligacao = 'DOS' if sobrenome in PLURAIS else random.choice(['DA', 'DE'])
        partes += [ligacao, sobrenome]
    if primeiro in MASCULINOS and random.random() < 0.12:
        partes.append(random.choice(['JUNIOR', 'FILHO', 'NETO']))
    return ' '.join(partes)


matriculas = random.sample(range(15000, 39999), 420)
colaboradores = []
usados = set()
for mat in matriculas:
    nome = nome_completo()
    while nome in usados:
        nome = nome_completo()
    usados.add(nome)
    colaboradores.append({'mat': str(mat), 'nome': nome,
                          'funcao': random.choice(FUNCOES),
                          'setor': random.choice(SETORES)})

# Os arquivos mensais ficam numa pasta por ano (dados/csv-exemplo/2026/),
# mesmo layout dos dados reais; COLABORADORES/GESTORES ficam na raiz, porque
# valem para todos os anos.
ANO = 2026
OUT_ANO = os.path.join(OUT, str(ANO))
if not os.path.isdir(OUT_ANO):
    os.makedirs(OUT_ANO)


def w(path, linhas, pasta=OUT):
    io.open(os.path.join(pasta, path), 'w', encoding='utf-8', newline='').write(
        '\r\n'.join(linhas) + '\r\n')


w('COLABORADORES.csv',
  [u'MATRÍCULA,NOME,FUNÇÃO,SETOR,'] +
  [u'%s,%s,%s,%s,' % (c['mat'], c['nome'], c['funcao'], c['setor']) for c in colaboradores])

w('GESTORES.csv', [u'"GESTORES', u'AUTORIZADOS"'] + GESTORES)

BANNER = u'Controle de Uso do Cartão Mestre,,,,,,,"FILIAL: 99'
BANNER2 = u'CIDADE EXEMPLO"'
HEADER = u'DATA,HORA,MATRÍCULA,NOME,SETOR,FUNÇÃO,MOTIVO,"RESPONSÁVEL'
HEADER2 = u'PELA AUTORIZAÇÃO"'
RODAPE = (u'FOR.PRP.0017,,Início da Vigência: 29/10/2020,,,'
          u'Última Revisão: 29/10/2020,,')


def csv_field(v):
    return u'"%s"' % v.replace('"', '""') if (',' in v or '"' in v) else v


def hora_plausivel():
    """Concentra no expediente 07:40–20:20, como os dados reais."""
    minuto = int(random.triangular(7 * 60 + 40, 20 * 60 + 20, 8 * 60))
    seg = random.choice([0, 0, 0, random.randint(0, 59)])
    return u'%02d:%02d:%02d' % (minuto // 60, minuto % 60, seg)


MESES = [('JANEIRO.csv', 1, 520), ('FEVEREIRO.csv', 2, 372),
         (u'MARÇO.csv', 3, 448), ('ABRIL.csv', 4, 305)]

for arquivo, mes, n in MESES:
    dias = (datetime.date(ANO, mes + 1, 1) - datetime.date(ANO, mes, 1)).days
    linhas = []
    for _ in range(n):
        c = random.choice(colaboradores)
        data = u'%02d/%02d/2026' % (random.randint(1, dias), mes)
        mat, nome, setor, funcao = c['mat'], c['nome'], c['setor'], c['funcao']
        r = random.random()
        if r < 0.02:            # matrícula em branco, como na fonte real
            mat = ''
            nome = nome.split()[0]
        elif r < 0.035:         # matrícula sem correspondência: vira "órfã"
            mat = str(random.randint(90000, 99999))
        if setor in SETOR_VARIACOES and random.random() < 0.15:
            setor = random.choice(SETOR_VARIACOES[setor])
        elif random.random() < 0.02:
            setor = '0'         # setor não informado
        if random.random() < 0.015:
            aprovador = random.choice(NAO_AUTORIZADOS)
        else:
            aprovador = random.choices(GESTORES, weights=PESO_GESTOR)[0]
        if random.random() < 0.08:   # travessão no lugar do hífen, como na fonte
            aprovador = aprovador.replace(' - ', u' – ')
        linhas.append(u','.join(csv_field(x) for x in
                                [data, hora_plausivel(), mat, nome, setor, funcao,
                                 random.choice(MOTIVOS), aprovador]))
    linhas.sort(key=lambda l: (l[3:5], l[0:2], l[11:19]))
    for _ in range(3):           # duplicatas exatas, contadas no painel de qualidade
        linhas.insert(random.randrange(len(linhas)), random.choice(linhas))
    if arquivo == 'JANEIRO.csv':  # data suspeita (ano < 2020), igual à fonte real
        linhas.insert(4, linhas[4].replace('/2026', '/2006', 1))
    w(arquivo, [BANNER, BANNER2, u',,,,,,,', HEADER, HEADER2] + linhas + [RODAPE],
      pasta=OUT_ANO)

print('gerado:', sorted(os.listdir(OUT)), '+', sorted(os.listdir(OUT_ANO)))
