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
// `nomes` é a lista de grafias aceitas de cada mês, na ordem de preferência.
// A segunda entrada de fevereiro não é engano: o arquivo-fonte real veio
// escrito "FEVEVEIRO" e continua valendo, para não quebrar quem já tem esse
// arquivo no servidor. Março aceita com e sem cedilha.
const MESES_CANONICOS = [
  { mes: 'Janeiro', nomes: ['JANEIRO'] },
  { mes: 'Fevereiro', nomes: ['FEVEREIRO', 'FEVEVEIRO'] },
  { mes: 'Março', nomes: ['MARÇO', 'MARCO'] },
  { mes: 'Abril', nomes: ['ABRIL'] },
  { mes: 'Maio', nomes: ['MAIO'] },
  { mes: 'Junho', nomes: ['JUNHO'] },
  { mes: 'Julho', nomes: ['JULHO'] },
  { mes: 'Agosto', nomes: ['AGOSTO'] },
  { mes: 'Setembro', nomes: ['SETEMBRO'] },
  { mes: 'Outubro', nomes: ['OUTUBRO'] },
  { mes: 'Novembro', nomes: ['NOVEMBRO'] },
  { mes: 'Dezembro', nomes: ['DEZEMBRO'] },
];

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

/**
 * Procura o CSV de um mês no diretório de dados, testando cada grafia aceita.
 * Devolve `{ mes, file, text }` do primeiro que existir, ou null se nenhum
 * existir — mês ausente é situação normal (o ano ainda não acabou), não erro.
 *
 * Já devolve o conteúdo junto: quem baixou é quem descobriu, então não vale
 * a pena uma segunda requisição só para ler o arquivo que acabou de chegar.
 */
async function findMonthlyFile({ mes, nomes }) {
  for (const nome of nomes) {
    const file = `${nome}.csv`;
    try {
      const res = await fetch(encodeURI(dataDir + file), FETCH_SEM_CACHE);
      if (!res.ok) continue;
      return { mes, file, text: await res.text() };
    } catch (_) {
      // rede/permissão — trata como ausente e tenta a próxima grafia
    }
  }
  return null;
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
    Promise.all(MESES_CANONICOS.map(findMonthlyFile)),
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
    if (!achado) continue;
    const eventos = parseMonthlyEvents(achado.text, achado.mes);
    if (!eventos.length) {
      console.warn(`${achado.file} não tem nenhuma liberação em formato reconhecido — mês ignorado.`);
      continue;
    }
    meses.push(achado.mes);
    monthlyArrays.push(eventos);
  }

  if (!meses.length) {
    throw new Error(
      `Nenhum CSV mensal encontrado em ${dataDir}. Os arquivos precisam ter o nome do mês em maiúsculas (ex.: JANEIRO.csv).`
    );
  }
  MESES_ORDEM = meses;

  const { records, duplicatesRemoved } = buildDataset(monthlyArrays, colaboradoresMap, gestoresSet);

  return { records, duplicatesRemoved, colaboradoresMap, gestoresSet };
}
