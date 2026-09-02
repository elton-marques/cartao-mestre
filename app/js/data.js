/**
 * Carregamento e limpeza (ETL) dos CSVs em dados/csv/.
 * Ver app/README.md para as decisões de limpeza.
 */

// Onde os CSVs são procurados, na ordem. `dados/csv/` guarda os arquivos
// reais e não é versionado; `dados/csv-exemplo/` traz um conjunto
// fictício de mesmo formato, que é o que roda em quem só clonou o repo.
const DATA_DIRS = ['../dados/csv/', '../dados/csv-exemplo/'];

// Para adicionar um novo mês: solte o CSV em dados/csv/ com o nome do mês em
// maiúsculas (`MAIO.csv`) e pronto — o dashboard descobre sozinho no próximo
// carregamento. Nenhum arquivo de código precisa ser tocado.
//
// A descoberta é por tentativa: o app pede cada nome possível ao servidor e
// fica com os que existem. Não dá pra listar o diretório — servidor web não
// entrega índice de pasta por padrão, e é justamente isso que permite servir
// o dashboard como arquivos estáticos em qualquer lugar (IIS, Apache,
// nginx), sem serviço nenhum atrás.
//
// `nomes` são as grafias aceitas de cada mês, na ordem de preferência: nome
// por extenso, abreviação de três letras e, quando existe, a variação
// herdada. Maiúsculas/minúsculas não importam — cada nome daqui é testado
// também em minúsculo e capitalizado (ver grafiasDoMes).
//
// FEVEVEIRO é o typo do arquivo-fonte original: os arquivos do repositório já
// foram renomeados para FEVEREIRO, mas a grafia velha continua aceita para
// não quebrar servidor que ainda tenha o arquivo antigo. Março vale com e sem
// cedilha, porque nem todo mundo digita acento em nome de arquivo.
const MESES_CANONICOS = [
  { mes: 'Janeiro', nomes: ['JANEIRO', 'JAN'] },
  { mes: 'Fevereiro', nomes: ['FEVEREIRO', 'FEV', 'FEVEVEIRO'] },
  { mes: 'Março', nomes: ['MARÇO', 'MARCO', 'MAR'] },
  { mes: 'Abril', nomes: ['ABRIL', 'ABR'] },
  { mes: 'Maio', nomes: ['MAIO', 'MAI'] },
  { mes: 'Junho', nomes: ['JUNHO', 'JUN'] },
  { mes: 'Julho', nomes: ['JULHO', 'JUL'] },
  { mes: 'Agosto', nomes: ['AGOSTO', 'AGO'] },
  { mes: 'Setembro', nomes: ['SETEMBRO', 'SET'] },
  { mes: 'Outubro', nomes: ['OUTUBRO', 'OUT'] },
  { mes: 'Novembro', nomes: ['NOVEMBRO', 'NOV'] },
  { mes: 'Dezembro', nomes: ['DEZEMBRO', 'DEZ'] },
];

// Os CSVs ficam em uma pasta por ano dentro do diretório de dados
// (`dados/csv/2026/JANEIRO.csv`), para que anos novos entrem sem misturar
// com os antigos. Como não dá pra listar diretório pelo navegador, os anos
// procurados vão daqui até o ano que vem — mexer nisso só seria necessário
// se aparecesse dado anterior a 2026.
const ANO_INICIAL = 2026;

// Meses efetivamente encontrados nesta carga, em ordem de calendário —
// preenchido por loadAll(). É a fonte única sobre "quais meses existem" para
// o resto do app (filtro de período, tendência mensal, rankings; ver
// aggregate.js), no lugar da lista fixa que existia aqui antes.
let MESES_ORDEM = [];
const COLABORADORES_FILE = 'COLABORADORES.csv';
const GESTORES_FILE = 'GESTORES.csv';

// Resolvido uma única vez por carga (ver resolveDataDir), junto com o texto
// do COLABORADORES.csv que serviu de sonda — assim não se baixa duas vezes.
let dataDir = null;
let colaboradoresText = null;

const WEEKDAYS = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
const DATE_RE = /^(\d{2})\/(\d{2})\/(\d{4})$/;
const HORA_RE = /^(\d{2}):(\d{2})/;

// Os CSVs são substituídos no servidor sem nenhum aviso ao navegador (é só
// trocar arquivo numa pasta), e a instalação estática pode estar num servidor
// web que não manda cabeçalho de cache nenhum — aí o navegador aplica cache
// por heurística e o usuário continua vendo os números do mês passado. Com
// no-cache toda leitura revalida com o servidor: quando nada mudou, a
// resposta é um 304 vazio; quando mudou, vem o arquivo novo.
const FETCH_SEM_CACHE = { cache: 'no-cache' };

async function fetchText(path) {
  const res = await fetch(encodeURI(path), FETCH_SEM_CACHE);
  if (!res.ok) {
    throw new Error(`Falha ao carregar ${path} (HTTP ${res.status}). Confira o README para rodar via servidor local.`);
  }
  return res.text();
}

/**
 * Descobre qual diretório de DATA_DIRS existe, sondando o COLABORADORES.csv
 * de cada um. Guarda o texto da sonda para o loadColaboradores reaproveitar.
 */
async function resolveDataDir() {
  if (dataDir) return dataDir;
  for (const dir of DATA_DIRS) {
    try {
      const res = await fetch(encodeURI(dir + COLABORADORES_FILE), FETCH_SEM_CACHE);
      if (!res.ok) continue;
      colaboradoresText = await res.text();
      dataDir = dir;
      await detectarSensibilidadeAMaiusculas(dir);
      return dir;
    } catch (_) {
      // diretório ausente/inacessível — tenta o próximo
    }
  }
  throw new Error(
    `Nenhum diretório de dados encontrado (${DATA_DIRS.join(', ')}). Confira o README para rodar via servidor local.`
  );
}

function parseDateBR(d) {
  const m = DATE_RE.exec(d);
  if (!m) return null;
  return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
}

// Em servidor Windows/IIS o sistema de arquivos ignora caixa, então
// `JANEIRO.csv` já atende um pedido por `janeiro.csv` e testar as três
// variações de cada nome seria o triplo de requisições à toa. Em Linux não:
// lá a caixa importa e cada grafia precisa ser testada mesmo.
//
// Descobrir de que lado estamos custa uma requisição: pedir o
// COLABORADORES.csv (que sabidamente existe) em minúsculo. Se vier 200, o
// servidor não diferencia caixa.
let ignoraCaixa = false;

async function detectarSensibilidadeAMaiusculas(dir) {
  try {
    const res = await fetch(encodeURI(dir + COLABORADORES_FILE.toLowerCase()), FETCH_SEM_CACHE);
    ignoraCaixa = res.ok;
  } catch (_) {
    ignoraCaixa = false;
  }
}

/** Grafias a testar para um mês: cada nome aceito em maiúsculo, minúsculo e
 * capitalizado (`JANEIRO`, `janeiro`, `Janeiro`) — só o maiúsculo quando o
 * servidor ignora caixa. */
function grafiasDoMes(nomes) {
  const out = [];
  for (const nome of nomes) {
    const maiusculo = nome.toUpperCase();
    const minusculo = nome.toLowerCase();
    const capitalizado = minusculo.charAt(0).toUpperCase() + minusculo.slice(1);
    for (const grafia of ignoraCaixa ? [maiusculo] : [maiusculo, minusculo, capitalizado]) {
      if (!out.includes(grafia)) out.push(grafia);
    }
  }
  return out;
}

/**
 * Procura o CSV de um mês num diretório, testando cada grafia aceita.
 * Devolve `{ file, text }` do primeiro que existir, ou null se nenhum existir
 * — mês ausente é situação normal (o ano ainda não acabou), não erro.
 *
 * Já devolve o conteúdo junto: quem baixou é quem descobriu, então não vale
 * a pena uma segunda requisição só para ler o arquivo que acabou de chegar.
 */
async function findMonthlyFile(dir, nomes) {
  for (const nome of grafiasDoMes(nomes)) {
    const file = `${nome}.csv`;
    try {
      const res = await fetch(encodeURI(dir + file), FETCH_SEM_CACHE);
      if (!res.ok) continue;
      return { file, text: await res.text() };
    } catch (_) {
      // rede/permissão — trata como ausente e tenta a próxima grafia
    }
  }
  return null;
}

/** Todos os meses achados num diretório, em ordem de calendário. */
async function coletarMeses(dir) {
  const achados = await Promise.all(
    MESES_CANONICOS.map(async (def, indice) => {
      const achado = await findMonthlyFile(dir, def.nomes);
      return achado && { ...achado, mes: def.mes, indice };
    })
  );
  return achados.filter(Boolean);
}

/**
 * Descobre onde estão os meses: uma pasta por ano (`2026/`, `2027/`, …) e,
 * se nenhuma existir, os arquivos soltos direto no diretório de dados —
 * layout das instalações anteriores a essa mudança, que continua funcionando.
 *
 * Pasta de ano tem precedência: se as duas existirem, os arquivos soltos são
 * ignorados, senão o mesmo mês entraria duas vezes no painel.
 *
 * O rótulo do mês só ganha o ano ("Janeiro/2026") quando há mais de um ano
 * publicado — com um ano só, "Janeiro" é o que a tela inteira já dizia e não
 * há ambiguidade a resolver.
 */
async function descobrirMeses() {
  const anos = [];
  for (let ano = ANO_INICIAL; ano <= new Date().getFullYear() + 1; ano++) anos.push(ano);

  const porAno = await Promise.all(
    anos.map(async (ano) => ({ ano, meses: await coletarMeses(`${dataDir}${ano}/`) }))
  );
  const anosComDados = porAno.filter((grupo) => grupo.meses.length);

  if (!anosComDados.length) {
    return (await coletarMeses(dataDir)).map((m) => ({ ...m, rotulo: m.mes }));
  }

  const varios = anosComDados.length > 1;
  return anosComDados.flatMap(({ ano, meses }) =>
    meses.map((m) => ({ ...m, rotulo: varios ? `${m.mes}/${ano}` : m.mes }))
  );
}

function parseMonthlyEvents(text, mes) {
  const rows = parseCSV(text);
  // Só nos interessam linhas cuja primeira coluna é uma data dd/mm/aaaa —
  // isso já descarta banner, cabeçalho, linhas em branco e o rodapé fixo
  // "FOR.PRP.0017..." presentes em todos os arquivos mensais.
  return rows
    .filter((r) => DATE_RE.test((r[0] || '').trim()))
    .map((r) => ({
      mes,
      data: (r[0] || '').trim(),
      hora: (r[1] || '').trim(),
      matricula: (r[2] || '').trim(),
      nome: (r[3] || '').trim(),
      setorRaw: (r[4] || '').trim(),
      funcaoRaw: (r[5] || '').trim(),
      motivoRaw: (r[6] || '').trim(),
      aprovadorRaw: (r[7] || '').trim(),
    }));
}

async function loadColaboradores() {
  const text = colaboradoresText;
  const rows = parseCSV(text);
  const map = new Map();
  for (let i = 1; i < rows.length; i++) {
    const r = rows[i];
    const mat = (r[0] || '').trim();
    if (!mat) continue;
    map.set(mat, {
      nome: (r[1] || '').trim(),
      funcao: (r[2] || '').trim(),
      setor: (r[3] || '').trim(),
    });
  }
  return map;
}

async function loadGestoresSet() {
  const text = await fetchText(dataDir + GESTORES_FILE);
  const rows = parseCSV(text);
  const set = new Set();
  for (const r of rows) {
    const v = (r[0] || '').trim();
    if (!v) continue;
    const upper = v.toUpperCase();
    if (upper.includes('GESTORES') || upper.includes('AUTORIZADOS')) continue; // cabeçalho
    set.add(normalizeAprovador(v));
  }
  return set;
}

/**
 * Junta os meses encontrados, remove duplicatas exatas, faz o join com
 * COLABORADORES/GESTORES e calcula todas as flags de qualidade usadas
 * pelo dashboard. Não filtra nada por padrão — quem decide o que
 * mostrar são os filtros da UI (ver aggregate.js).
 */
function buildDataset(monthlyEventArrays, colaboradoresMap, gestoresSet) {
  const seen = new Set();
  let duplicatesRemoved = 0;
  const records = [];

  for (const ev of monthlyEventArrays.flat()) {
    const dupKey = [ev.data, ev.hora, ev.matricula, ev.nome, ev.setorRaw, ev.funcaoRaw, ev.motivoRaw, ev.aprovadorRaw].join('|');
    if (seen.has(dupKey)) {
      duplicatesRemoved++;
      continue;
    }
    seen.add(dupKey);

    const dateObj = parseDateBR(ev.data);
    const suspiciousDate = !!dateObj && dateObj.getFullYear() < 2020;
    const horaMatch = HORA_RE.exec(ev.hora);
    const hour = horaMatch ? Number(horaMatch[1]) : null;
    const minute = horaMatch ? Number(horaMatch[2]) : null;
    // minutos desde 00:00 — usado pelas faixas de horário (HORA_BANDS em
    // aggregate.js), que precisam de precisão de minuto pra bater com o
    // expediente real (abre 8h/fecha 20h, colaboradores de 7h40 a 20h20).
    const minutesOfDay = hour != null && minute != null ? hour * 60 + minute : null;
    const horaAusente = !horaMatch;

    const colInfo = ev.matricula ? colaboradoresMap.get(ev.matricula) : null;
    const naoCadastrado = !colInfo; // inclui matrícula vazia e matrícula não encontrada

    const setor = normalizeSetor(ev.setorRaw || (colInfo && colInfo.setor) || '');
    const motivo = normalizeMotivo(ev.motivoRaw);
    const aprovador = normalizeAprovador(ev.aprovadorRaw);
    // "Não informado" (matrícula sem aprovador no CSV) não é um gestor
    // irregular — é falta de dado, não alguém de fora de GESTORES.csv.
    const aprovadorNaoAutorizado = !!aprovador && aprovador !== NAO_INFORMADO && !gestoresSet.has(aprovador);

    records.push({
      ...ev,
      dateObj,
      weekday: dateObj ? WEEKDAYS[dateObj.getDay()] : null,
      hour,
      minutesOfDay,
      horaAusente,
      suspiciousDate,
      setor,
      motivo,
      aprovador,
      aprovadorNaoAutorizado,
      naoCadastrado,
      nomeDisplay: ev.nome || (colInfo && colInfo.nome) || '(sem nome)',
    });
  }

  return { records, duplicatesRemoved };
}

async function loadAll() {
  await resolveDataDir();
  const [encontrados, colaboradoresMap, gestoresSet] = await Promise.all([
    descobrirMeses(),
    loadColaboradores(),
    loadGestoresSet(),
  ]);

  // Mês cujo arquivo existe mas não tem nenhuma linha de liberação válida
  // fica de fora: entraria no filtro de período e na tendência mensal como
  // uma coluna zerada, sugerindo "mês sem ocorrência" quando o caso real é
  // arquivo vazio ou fora do formato esperado.
  const meses = [];
  const monthlyArrays = [];
  for (const achado of encontrados) {
    const eventos = parseMonthlyEvents(achado.text, achado.rotulo);
    if (!eventos.length) {
      console.warn(`${achado.file} não tem nenhuma liberação em formato reconhecido — mês ignorado.`);
      continue;
    }
    meses.push(achado.rotulo);
    monthlyArrays.push(eventos);
  }

  if (!meses.length) {
    throw new Error(
      `Nenhum CSV mensal encontrado em ${dataDir}. Os arquivos ficam numa pasta por ano (ex.: ${dataDir}${ANO_INICIAL}/JANEIRO.csv) e o nome do arquivo é o nome do mês.`
    );
  }
  MESES_ORDEM = meses;

  const { records, duplicatesRemoved } = buildDataset(monthlyArrays, colaboradoresMap, gestoresSet);

  return { records, duplicatesRemoved, colaboradoresMap, gestoresSet };
}
