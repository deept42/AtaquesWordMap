const COR_RASTRO = "#ff2430";

const ROTULOS = {
  ransomware: "Ransomware",
  vazamento: "Vazamento",
  ataque: "Ataque",
  municipio: "município citado",
  uf: "centro do estado",
  pais: "sem lugar no mapa",
};

const UFS = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"];

const state = {
  catalogo: null,
  estados: null,
  mapa: null,
  selecionado: null,
  retornando: false,
  timerRetorno: 0,
  alvos: [],
};

const elementos = {
  q: document.querySelector("#q"),
  tipo: document.querySelector("#tipo"),
  uf: document.querySelector("#uf"),
  ano: document.querySelector("#ano"),
  somenteMapa: document.querySelector("#somente-mapa"),
  list: document.querySelector("#list"),
  count: document.querySelector("#count"),
  stats: document.querySelector("#stats"),
  notes: document.querySelector("#notes"),
  detail: document.querySelector("#detail"),
  coords: document.querySelector("#coords"),
};

function escapar(valor) {
  return String(valor ?? "").replace(/[&<>"']/g, (caractere) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[caractere]));
}

function urlSegura(url) {
  try {
    const lida = new URL(url);
    if (lida.protocol === "http:" || lida.protocol === "https:") return lida.href;
  } catch (_erro) {
    return null;
  }
  return null;
}

function filtros() {
  return {
    q: norm(elementos.q.value),
    tipo: elementos.tipo.value,
    uf: elementos.uf.value,
    ano: elementos.ano.value,
    somenteMapa: elementos.somenteMapa.checked,
  };
}

function norm(valor) {
  return String(valor ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function passa(item, filtro) {
  if (filtro.tipo && item.tipo !== filtro.tipo) return false;
  if (filtro.uf && item.uf !== filtro.uf) return false;
  if (filtro.ano && !(item.data || "").startsWith(filtro.ano)) return false;
  if (filtro.somenteMapa && !noMapa(item)) return false;
  if (!filtro.q) return true;
  const texto = norm([item.titulo, item.cidade, item.uf, item.setor, item.grupo, item.resumo].join(" "));
  return texto.includes(filtro.q);
}

function noMapa(item) {
  return Number.isFinite(item.lat) && Number.isFinite(item.lon) && item.precisao !== "pais";
}

function visiveis() {
  const filtro = filtros();
  return state.catalogo.incidentes.filter((item) => passa(item, filtro));
}

function corDoEstado(contagem, maximo) {
  if (!contagem || !maximo) return "#05210c";
  const peso = contagem / maximo;
  const verde = Math.round(40 + peso * 160);
  return `rgb(${Math.round(verde * 0.25)}, ${verde}, ${Math.round(verde * 0.35)})`;
}

function estiloBase() {
  const via = ["interpolate", ["linear"], ["zoom"], 4, 0.4, 8, 1.1, 12, 2.6, 14, 6];
  return {
    version: 8,
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    sources: {
      base: { type: "vector", url: "https://tiles.openfreemap.org/planet" },
    },
    layers: [
      { id: "fundo", type: "background", paint: { "background-color": "#000000" } },
      {
        id: "solo",
        type: "fill",
        source: "base",
        "source-layer": "water",
        paint: { "fill-color": "#07140c" },
      },
      {
        id: "mato",
        type: "fill",
        source: "base",
        "source-layer": "landcover",
        filter: ["in", ["get", "class"], ["literal", ["wood", "grass", "farmland"]]],
        paint: {
          "fill-color": ["interpolate", ["linear"], ["zoom"], 3, "#0c2e12", 8, "#145c22", 12, "#1f7a32"],
          "fill-opacity": ["interpolate", ["linear"], ["zoom"], 3, 0.72, 8, 0.9, 12, 1],
        },
      },
      {
        id: "areia",
        type: "fill",
        source: "base",
        "source-layer": "landcover",
        filter: ["in", ["get", "class"], ["literal", ["sand", "wetland"]]],
        paint: { "fill-color": "#0a2410", "fill-opacity": 0.8 },
      },
      {
        id: "parque",
        type: "fill",
        source: "base",
        "source-layer": "park",
        paint: { "fill-color": "#12381a", "fill-opacity": 0.72 },
      },
      {
        id: "uso-residencial",
        type: "fill",
        source: "base",
        "source-layer": "landuse",
        filter: ["==", ["get", "class"], "residential"],
        paint: { "fill-color": "#06140a", "fill-opacity": 0.7 },
      },
      {
        id: "uso-industrial",
        type: "fill",
        source: "base",
        "source-layer": "landuse",
        filter: ["==", ["get", "class"], "industrial"],
        paint: { "fill-color": "#0c2414", "fill-opacity": 0.75 },
      },
      {
        id: "uso-comercial",
        type: "fill",
        source: "base",
        "source-layer": "landuse",
        filter: ["==", ["get", "class"], "commercial"],
        paint: { "fill-color": "#12381a", "fill-opacity": 0.7 },
      },
      {
        id: "costa",
        type: "line",
        source: "base",
        "source-layer": "water",
        minzoom: 5,
        paint: {
          "line-color": "#145c22",
          "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.4, 10, 1.15],
        },
      },
      {
        id: "rio",
        type: "line",
        source: "base",
        "source-layer": "waterway",
        minzoom: 6,
        paint: {
          "line-color": "#145c22",
          "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.35, 12, 1.3],
        },
      },
      {
        id: "via-miuda",
        type: "line",
        source: "base",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["minor", "service", "track"]]],
        paint: { "line-color": "#1a6b2c", "line-width": ["interpolate", ["linear"], ["zoom"], 7, 0.35, 11, 1.1, 14, 2.4] },
      },
      {
        id: "via-media",
        type: "line",
        source: "base",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["secondary", "tertiary"]]],
        paint: { "line-color": "#2d9a45", "line-width": via },
      },
      {
        id: "via-principal",
        type: "line",
        source: "base",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary"]]],
        paint: { "line-color": "#7dff9a", "line-width": via },
      },
      {
        id: "trilho",
        type: "line",
        source: "base",
        "source-layer": "transportation",
        filter: ["==", ["get", "class"], "rail"],
        paint: { "line-color": "#8fbf98", "line-width": 1, "line-dasharray": [2, 2] },
      },
      {
        id: "predio",
        type: "fill",
        source: "base",
        "source-layer": "building",
        minzoom: 13,
        paint: { "fill-color": "#07140c", "fill-outline-color": "#1a6b2c" },
      },
      {
        id: "pista",
        type: "line",
        source: "base",
        "source-layer": "aeroway",
        minzoom: 10,
        filter: ["in", ["get", "class"], ["literal", ["runway", "taxiway"]]],
        paint: {
          "line-color": "#2d9a45",
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.5, 14, 2.8],
        },
      },
      {
        id: "fronteira",
        type: "line",
        source: "base",
        "source-layer": "boundary",
        filter: ["all", ["==", ["get", "admin_level"], 2], ["!=", ["get", "maritime"], 1]],
        paint: { "line-color": "#145c22", "line-width": ["interpolate", ["linear"], ["zoom"], 2, 0.6, 8, 1.8] },
      },
    ],
  };
}

function desenhar() {
  const itens = visiveis();
  desenharLista(itens);
  desenharMapa(itens);
  elementos.count.textContent = `${itens.length} de ${state.catalogo.incidentes.length} incidentes`;
}

function desenharLista(itens) {
  const recorte = itens.slice(0, 300);
  elementos.list.innerHTML = recorte.map((item) => {
    const lugar = item.cidade ? `${escapar(item.cidade)} · ${escapar(item.uf)}` : (item.uf || "Brasil");
    const ativo = state.selecionado === item.id ? " active" : "";
    return `<li><button type="button" data-id="${escapar(item.id)}" class="${ativo}">
      <span class="item-title">${escapar(item.titulo)}</span>
      <span class="item-meta">
        <span class="tag ${escapar(item.tipo)}">${escapar(ROTULOS[item.tipo] || item.tipo)}</span>
        <span>${escapar(item.data || "sem data")}</span>
        <span>${lugar}</span>
      </span>
    </button></li>`;
  }).join("");
  if (itens.length > recorte.length) {
    elementos.list.insertAdjacentHTML(
      "beforeend",
      `<li><p class="count">Mostrando ${recorte.length}. Refine a busca para ver o resto.</p></li>`,
    );
  }
}

function desenharMapa(itens) {
  if (!state.mapa || !state.mapa.getSource("incidentes")) return;
  const porUf = new Map();
  itens.forEach((item) => {
    if (!item.uf) return;
    porUf.set(item.uf, (porUf.get(item.uf) || 0) + 1);
  });
  const maximo = Math.max(0, ...porUf.values());
  const pares = [];
  porUf.forEach((total, uf) => pares.push(uf, corDoEstado(total, maximo)));
  const cor = pares.length ? ["match", ["get", "sigla"], ...pares, "#05210c"] : "#05210c";
  state.mapa.setPaintProperty("estados-fill", "fill-color", cor);
  if (state.mapa.getLayer("estados-line")) {
    state.mapa.setFilter("estados-line", ["==", ["get", "sigla"], elementos.uf.value || ""]);
  }
  const grupos = new Map();
  const features = [];
  itens.forEach((item) => {
    if (!noMapa(item)) return;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [item.lon, item.lat] },
      properties: { id: item.id, tipo: item.tipo, precisao: item.precisao },
    });
    const chave = `${item.tipo}:${item.lat.toFixed(2)}:${item.lon.toFixed(2)}`;
    if (!grupos.has(chave)) {
      grupos.set(chave, {
        lon: item.lon,
        lat: item.lat,
        lado: Math.round(item.lat * 10) % 2 === 0 ? 1 : -1,
      });
    }
  });
  state.alvos = [...grupos.values()];
  state.mapa.getSource("incidentes").setData({
    type: "FeatureCollection",
    features,
  });
  if (state.mapa.getLayer("incidentes-anel")) {
    state.mapa.setFilter("incidentes-anel", [
      "all",
      ["!", ["has", "point_count"]],
      ["==", ["get", "id"], state.selecionado || ""],
    ]);
  }
  sincronizarDestaque();
}

function anguloHorario(x, y, cx, cy) {
  return Math.atan2(x - cx, cy - y);
}

function feixeDoRadar() {
  const estilo = getComputedStyle(state.mapa.getContainer(), "::before");
  const matriz = /matrix\(([^)]+)\)/.exec(estilo.transform || "");
  if (!matriz) return ((performance.now() % 5500) / 5500) * Math.PI * 2;
  const [a, b] = matriz[1].split(",").map((parte) => Number(parte.trim()));
  let rotacao = Math.atan2(b, a);
  if (rotacao < 0) rotacao += Math.PI * 2;
  return rotacao + (54 * Math.PI / 180);
}

function bordaDoMapa(cx, cy, ux, uy, largura, altura) {
  const margem = 4;
  const tempos = [];
  if (ux > 0.001) tempos.push((largura - margem - cx) / ux);
  if (ux < -0.001) tempos.push((margem - cx) / ux);
  if (uy > 0.001) tempos.push((altura - margem - cy) / uy);
  if (uy < -0.001) tempos.push((margem - cy) / uy);
  const alcance = Math.min(...tempos.filter((valor) => valor > 0));
  return { x: cx + ux * alcance, y: cy + uy * alcance };
}

function pontoNaCurva(origem, controle, destino, t) {
  const resto = 1 - t;
  return {
    x: resto * resto * origem.x + 2 * resto * t * controle.x + t * t * destino.x,
    y: resto * resto * origem.y + 2 * resto * t * controle.y + t * t * destino.y,
  };
}

function desenharRastros(ctx, largura, altura) {
  ctx.clearRect(0, 0, largura, altura);
  if (!state.alvos.length) return;
  const cx = largura / 2;
  const cy = altura / 2;
  const reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const feixe = feixeDoRadar();
  const crescer = 26 * Math.PI / 180;
  const janela = 98 * Math.PI / 180;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  state.alvos.forEach((alvo) => {
    const tela = state.mapa.project([alvo.lon, alvo.lat]);
    if (tela.x < -20 || tela.y < -20 || tela.x > largura + 20 || tela.y > altura + 20) return;
    const dx = tela.x - cx;
    const dy = tela.y - cy;
    const distCentro = Math.hypot(dx, dy);
    if (distCentro < 12) return;
    const angulo = anguloHorario(tela.x, tela.y, cx, cy);
    let atraso = feixe - angulo;
    atraso = (atraso % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
    let alpha = 0.42;
    let progresso = 1;
    if (!reduzido) {
      if (atraso > janela) return;
      progresso = Math.min(1, atraso / crescer);
      alpha = atraso <= crescer ? 0.35 + 0.65 * progresso : 1 - (atraso - crescer) / (janela - crescer);
      if (alpha <= 0.02 || progresso <= 0.02) return;
    }
    const ux = dx / distCentro;
    const uy = dy / distCentro;
    const origem = bordaDoMapa(cx, cy, ux, uy, largura, altura);
    const distancia = Math.hypot(tela.x - origem.x, tela.y - origem.y);
    if (distancia < 28) return;
    const curva = Math.min(84, distancia * 0.24);
    const lado = alvo.lado;
    const controle = {
      x: (origem.x + tela.x) / 2 + (-uy) * curva * lado,
      y: (origem.y + tela.y) / 2 + ux * curva * lado,
    };
    const destino = { x: tela.x, y: tela.y };
    const passos = Math.max(8, Math.round(18 * progresso));
    ctx.save();
    ctx.beginPath();
    let anterior = pontoNaCurva(origem, controle, destino, 0);
    ctx.moveTo(anterior.x, anterior.y);
    for (let i = 1; i <= passos; i += 1) {
      const t = progresso * (i / passos);
      const ponto = pontoNaCurva(origem, controle, destino, t);
      ctx.lineTo(ponto.x, ponto.y);
      anterior = ponto;
    }
    ctx.strokeStyle = COR_RASTRO;
    ctx.shadowColor = COR_RASTRO;
    ctx.shadowBlur = 18;
    ctx.globalAlpha = alpha * 0.9;
    ctx.lineWidth = 2.2;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.globalAlpha = alpha;
    ctx.lineWidth = 1.15;
    ctx.stroke();
    ctx.fillStyle = COR_RASTRO;
    ctx.beginPath();
    ctx.arc(anterior.x, anterior.y, progresso > 0.92 ? 4 : 2.6, 0, Math.PI * 2);
    ctx.shadowColor = COR_RASTRO;
    ctx.shadowBlur = 16;
    ctx.fill();
    ctx.restore();
  });
  ctx.globalAlpha = 1;
}

function iniciarRastros() {
  const canvas = document.createElement("canvas");
  canvas.className = "rastros";
  state.mapa.getContainer().append(canvas);
  const ctx = canvas.getContext("2d");
  const quadro = () => {
    const dpr = window.devicePixelRatio || 1;
    const largura = canvas.clientWidth;
    const altura = canvas.clientHeight;
    const bitmapL = Math.round(largura * dpr);
    const bitmapA = Math.round(altura * dpr);
    if (canvas.width !== bitmapL || canvas.height !== bitmapA) {
      canvas.width = bitmapL;
      canvas.height = bitmapA;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    desenharRastros(ctx, largura, altura);
    state.quadroRastros = requestAnimationFrame(quadro);
  };
  state.quadroRastros = requestAnimationFrame(quadro);
}

function selecionar(id, voar) {
  const item = state.catalogo.incidentes.find((candidato) => candidato.id === id);
  if (!item) return;
  state.selecionado = id;
  desenhar();
  const botao = elementos.list.querySelector(`[data-id="${CSS.escape(id)}"]`);
  if (botao) botao.scrollIntoView({ block: "nearest" });
  abrirFicha(item);
  if (voar && noMapa(item)) {
    state.mapa.flyTo({
      center: [item.lon, item.lat],
      zoom: item.precisao === "municipio" ? 11 : 6,
      duration: 700,
    });
  }
}

function abrirFicha(item) {
  const fontes = (item.fontes || []).map((fonte) => {
    const href = urlSegura(fonte.url);
    const rotulo = escapar(fonte.nome || href || "fonte");
    if (!href) return `<li>${rotulo}</li>`;
    return `<li><a href="${escapar(href)}" target="_blank" rel="noreferrer">${rotulo}</a></li>`;
  }).join("");
  const lugar = item.cidade
    ? `${item.cidade} (${item.uf})`
    : (item.uf ? `estado ${item.uf}` : "país, sem município");
  elementos.detail.hidden = false;
  elementos.detail.innerHTML = `
    <button class="close" type="button" id="fechar">Fechar</button>
    <span class="tag ${escapar(item.tipo)}">${escapar(ROTULOS[item.tipo] || item.tipo)}</span>
    <h2>${escapar(item.titulo)}</h2>
    <p>${escapar(item.data || "Sem data")} · ${escapar(lugar)}</p>
    <p>Precisão: ${escapar(ROTULOS[item.precisao] || item.precisao)}</p>
    <p>${escapar(item.resumo || "")}</p>
    ${item.website ? `<p>Site: ${escapar(item.website)}</p>` : ""}
    <ul>${fontes}</ul>`;
  elementos.detail.querySelector("#fechar").addEventListener("click", () => {
    elementos.detail.hidden = true;
    state.selecionado = null;
    desenhar();
  });
}

function preencherFiltros() {
  UFS.forEach((uf) => {
    const opcao = document.createElement("option");
    opcao.value = uf;
    opcao.textContent = uf;
    elementos.uf.append(opcao);
  });
  const anos = [...new Set(state.catalogo.incidentes.map((item) => (item.data || "").slice(0, 4)).filter(Boolean))];
  anos.sort().reverse().forEach((ano) => {
    const opcao = document.createElement("option");
    opcao.value = ano;
    opcao.textContent = ano;
    elementos.ano.append(opcao);
  });
}

function preencherResumo() {
  const totais = state.catalogo.totais;
  const blocos = [
    ["Incidentes", totais.incidentes],
    ["No mapa", totais.no_mapa],
    ["Município", totais.por_precisao.municipio || 0],
  ];
  elementos.stats.innerHTML = blocos.map(([rotulo, valor]) => (
    `<div><dt>${escapar(rotulo)}</dt><dd>${escapar(valor)}</dd></div>`
  )).join("");
  const quando = new Date(state.catalogo.gerado_em);
  const data = Number.isNaN(quando.getTime()) ? state.catalogo.gerado_em : quando.toLocaleString("pt-BR");
  elementos.notes.textContent = `Catálogo gerado em ${data}. ${(state.catalogo.avisos || []).join(" ")}`;
}

function nomeLocal() {
  return ["coalesce", ["get", "name:pt"], ["get", "name"]];
}

function aneisDoBrasil(geojson, tolerancia) {
  const t2 = tolerancia * tolerancia;
  const aneis = [];
  for (const feature of geojson.features) {
    const geom = feature.geometry;
    if (!geom) continue;
    const poligonos = geom.type === "Polygon" ? [geom.coordinates] : geom.type === "MultiPolygon" ? geom.coordinates : [];
    for (const poligono of poligonos) {
      const bruto = poligono[0];
      if (!bruto || bruto.length < 4) continue;
      const pts = [bruto[0]];
      for (let i = 1; i < bruto.length; i += 1) {
        const dx = bruto[i][0] - pts[pts.length - 1][0];
        const dy = bruto[i][1] - pts[pts.length - 1][1];
        if (dx * dx + dy * dy >= t2) pts.push(bruto[i]);
      }
      let minX = 180;
      let minY = 90;
      let maxX = -180;
      let maxY = -90;
      for (const ponto of pts) {
        if (ponto[0] < minX) minX = ponto[0];
        if (ponto[1] < minY) minY = ponto[1];
        if (ponto[0] > maxX) maxX = ponto[0];
        if (ponto[1] > maxY) maxY = ponto[1];
      }
      aneis.push({ pts, minX, minY, maxX, maxY });
    }
  }
  return aneis;
}

const LIMITES_BRASIL = [[-74, -33.8], [-34.7, 5.3]];

function cruzarBorda(a, b, lado, xmin, ymin, xmax, ymax) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  if (lado === 0 || lado === 1) {
    if (Math.abs(dx) < 1e-6) return null;
    const x = lado === 0 ? xmin : xmax;
    return { x, y: a.y + dy * (x - a.x) / dx };
  }
  if (Math.abs(dy) < 1e-6) return null;
  const y = lado === 2 ? ymin : ymax;
  return { x: a.x + dx * (y - a.y) / dy, y };
}

function recortarNaTela(pontos, xmin, ymin, xmax, ymax) {
  const dentro = [
    (p) => p.x >= xmin,
    (p) => p.x <= xmax,
    (p) => p.y >= ymin,
    (p) => p.y <= ymax,
  ];
  let atual = pontos;
  for (let lado = 0; lado < 4; lado += 1) {
    if (atual.length < 3) return [];
    const proximo = [];
    for (let i = 0; i < atual.length; i += 1) {
      const ponto = atual[i];
      const anterior = atual[(i + atual.length - 1) % atual.length];
      const estaDentro = dentro[lado](ponto);
      const anteriorDentro = dentro[lado](anterior);
      if (estaDentro) {
        if (!anteriorDentro) {
          const meio = cruzarBorda(anterior, ponto, lado, xmin, ymin, xmax, ymax);
          if (meio) proximo.push(meio);
        }
        proximo.push(ponto);
      } else if (anteriorDentro) {
        const meio = cruzarBorda(anterior, ponto, lado, xmin, ymin, xmax, ymax);
        if (meio) proximo.push(meio);
      }
    }
    atual = proximo;
  }
  return atual;
}

function cobreATela(pedacos, largura, altura) {
  if (!state.ctxRecorte) state.ctxRecorte = document.createElement("canvas").getContext("2d");
  let caminho;
  try {
    caminho = new Path2D(pedacos.join(" "));
  } catch (_erro) {
    return false;
  }
  const amostras = [
    [largura * 0.5, altura * 0.42],
    [largura * 0.5, altura * 0.62],
    [largura * 0.32, altura * 0.5],
    [largura * 0.68, altura * 0.5],
  ];
  const dentro = amostras.filter(([x, y]) => state.ctxRecorte.isPointInPath(caminho, x, y)).length;
  return dentro >= 3;
}

function recortarNoBrasil() {
  const canvas = state.mapa.getCanvas();
  const largura = canvas.clientWidth;
  const altura = canvas.clientHeight;
  const margem = 64;
  const lista = state.mapa.getZoom() < 6.5 ? state.recorteLonge : state.recortePerto;
  const pedacos = [];
  for (const anel of lista) {
    const tela = [];
    let invalido = false;
    for (let i = 0; i < anel.pts.length; i += 1) {
      const ponto = state.mapa.project(anel.pts[i]);
      if (!Number.isFinite(ponto.x) || !Number.isFinite(ponto.y)) {
        invalido = true;
        break;
      }
      tela.push(ponto);
    }
    if (invalido || tela.length < 3) continue;
    const cortado = recortarNaTela(tela, -margem, -margem, largura + margem, altura + margem);
    if (cortado.length < 3) continue;
    let desenho = "";
    for (let i = 0; i < cortado.length; i += 1) {
      desenho += `${i === 0 ? "M" : "L"}${cortado[i].x.toFixed(1)} ${cortado[i].y.toFixed(1)} `;
    }
    pedacos.push(`${desenho}Z`);
  }
  if (!pedacos.length) {
    if (state.ultimoRecorte) canvas.style.clipPath = state.ultimoRecorte;
    return;
  }
  const zoomPerto = state.mapa.getZoom() >= 7.5 || state.mapa.getPitch() > 12;
  if (zoomPerto && !cobreATela(pedacos, largura, altura)) {
    canvas.style.clipPath = "none";
    return;
  }
  state.ultimoRecorte = `path("${pedacos.join(" ")}")`;
  canvas.style.clipPath = state.ultimoRecorte;
}

function limitesDoEstado(feature) {
  let minX = 180;
  let minY = 90;
  let maxX = -180;
  let maxY = -90;
  const geometria = feature.geometry;
  const poligonos = geometria.type === "Polygon" ? [geometria.coordinates] : geometria.coordinates;
  for (const poligono of poligonos) {
    for (const ponto of poligono[0]) {
      if (ponto[0] < minX) minX = ponto[0];
      if (ponto[1] < minY) minY = ponto[1];
      if (ponto[0] > maxX) maxX = ponto[0];
      if (ponto[1] > maxY) maxY = ponto[1];
    }
  }
  return [[minX, minY], [maxX, maxY]];
}

function animarAltura(destino) {
  cancelAnimationFrame(state.quadroAltura || 0);
  const de = state.alturaAtual || 0;
  const inicio = performance.now();
  const passo = (agora) => {
    const t = Math.min(1, (agora - inicio) / 700);
    const suave = 1 - (1 - t) ** 3;
    state.alturaAtual = de + (destino - de) * suave;
    if (state.mapa.getLayer("estado-bloco")) {
      state.mapa.setPaintProperty("estado-bloco", "fill-extrusion-height", state.alturaAtual);
    }
    if (t < 1) state.quadroAltura = requestAnimationFrame(passo);
  };
  state.quadroAltura = requestAnimationFrame(passo);
}

function liberarZoom() {
  state.retornando = false;
  window.clearTimeout(state.timerRetorno);
  if (state.mapa) state.mapa.scrollZoom.enable();
}

function soltarEstado() {
  if (!state.mapa.getSource("estado-destaque")) return;
  state.mapa.getSource("estado-destaque").setData({ type: "FeatureCollection", features: [] });
  state.mapa.setFilter("estados-fill", null);
  state.mapa.setFilter("estados-line", ["==", ["get", "sigla"], ""]);
  state.mapa.setPaintProperty("estados-fill", "fill-opacity", 0.22);
  animarAltura(0);
  state.retornando = true;
  window.clearTimeout(state.timerRetorno);
  state.mapa.scrollZoom.disable();
  state.mapa.stop();
  state.mapa.fitBounds(LIMITES_BRASIL, {
    padding: 28,
    pitch: 0,
    bearing: 0,
    duration: 800,
  });
  state.timerRetorno = window.setTimeout(liberarZoom, 980);
}

function sincronizarDestaque() {
  if (!state.mapa.getSource("estado-destaque")) return;
  const sigla = elementos.uf.value;
  if (sigla === state.siglaDestacada) return;
  state.siglaDestacada = sigla;
  if (!sigla) {
    soltarEstado();
    return;
  }
  const feature = state.estados.features.find((item) => item.properties.sigla === sigla);
  if (!feature) return;
  state.mapa.getSource("estado-destaque").setData(feature);
  state.mapa.setFilter("estados-fill", ["!=", ["get", "sigla"], sigla]);
  state.mapa.setPaintProperty("estados-fill", "fill-opacity", 0.1);
  animarAltura(90000);
  state.mapa.fitBounds(limitesDoEstado(feature), {
    padding: 80,
    pitch: 55,
    bearing: -20,
    duration: 900,
  });
}

function desenharIcone(tipo) {
  const tela = document.createElement("canvas");
  tela.width = 64;
  tela.height = 64;
  const ctx = tela.getContext("2d");
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.fillStyle = "#000000";
  ctx.strokeStyle = "#39ff14";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.arc(32, 32, 28, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.lineWidth = 3;
  ctx.fillStyle = "#39ff14";
  if (tipo === "ransomware") {
    ctx.strokeRect(22, 30, 20, 16);
    ctx.beginPath();
    ctx.arc(32, 30, 7, Math.PI, 0);
    ctx.stroke();
  } else if (tipo === "vazamento") {
    ctx.beginPath();
    ctx.moveTo(32, 16);
    ctx.bezierCurveTo(46, 30, 44, 46, 32, 50);
    ctx.bezierCurveTo(20, 46, 18, 30, 32, 16);
    ctx.fill();
  } else {
    ctx.beginPath();
    ctx.arc(32, 32, 8, 0, Math.PI * 2);
    ctx.moveTo(32, 14);
    ctx.lineTo(32, 22);
    ctx.moveTo(32, 42);
    ctx.lineTo(32, 50);
    ctx.moveTo(14, 32);
    ctx.lineTo(22, 32);
    ctx.moveTo(42, 32);
    ctx.lineTo(50, 32);
    ctx.stroke();
  }
  return ctx.getImageData(0, 0, 64, 64);
}

function iniciarMapa() {
  state.recorteLonge = aneisDoBrasil(state.estados, 0.12);
  state.recortePerto = aneisDoBrasil(state.estados, 0.035);
  state.mapa = new maplibregl.Map({
    container: "map",
    style: estiloBase(),
    center: [-52, -14.2],
    zoom: 3.4,
    minZoom: 2.5,
    maxZoom: 14,
    attributionControl: true,
    renderWorldCopies: false,
    dragRotate: false,
    pitchWithRotate: false,
    touchPitch: false,
  });
  state.mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
  state.mapa.on("load", () => {
    state.mapa.addSource("estados", { type: "geojson", data: state.estados });
    state.mapa.addLayer({
      id: "estados-fill",
      type: "fill",
      source: "estados",
      paint: { "fill-color": "#05210c", "fill-opacity": 0.22 },
    });
    state.mapa.addLayer({
      id: "estados-tracejado",
      type: "line",
      source: "estados",
      paint: {
        "line-color": "#1a6b2c",
        "line-width": 1,
        "line-dasharray": [1.6, 1.2],
        "line-opacity": 0.9,
      },
    });
    state.mapa.addLayer({
      id: "estados-line",
      type: "line",
      source: "estados",
      filter: ["==", ["get", "sigla"], ""],
      paint: { "line-color": "#b6ffc4", "line-width": 2.4 },
    });
    state.mapa.addSource("estado-destaque", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    state.mapa.addLayer({
      id: "estado-bloco",
      type: "fill-extrusion",
      source: "estado-destaque",
      paint: {
        "fill-extrusion-color": "#1f7a32",
        "fill-extrusion-height": 0,
        "fill-extrusion-base": 0,
        "fill-extrusion-opacity": 0.34,
        "fill-extrusion-vertical-gradient": true,
      },
    }, "via-miuda");
    state.siglaDestacada = "";
    state.alturaAtual = 0;
    state.mapa.addLayer({
      id: "lugar",
      type: "symbol",
      source: "base",
      "source-layer": "place",
      filter: ["step", ["zoom"],
        ["match", ["get", "class"], ["country", "state"], true, false],
        4, ["match", ["get", "class"], ["country", "state", "city"], true, false],
        6, ["match", ["get", "class"], ["country", "state", "city", "town"], true, false],
        9, ["match", ["get", "class"], ["country", "state", "city", "town", "village"], true, false],
      ],
      layout: {
        "text-field": nomeLocal(),
        "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 3, 11, 8, 14, 12, 16],
      },
      paint: {
        "text-color": ["match", ["get", "class"], "city", "#8fd9a0", "town", "#2d9a45", "village", "#1a6b2c", "state", "#b6ffc4", "#7dff9a"],
        "text-halo-color": "#000000",
        "text-halo-width": 1.2,
      },
    });
    state.mapa.addLayer({
      id: "nome-via",
      type: "symbol",
      source: "base",
      "source-layer": "transportation_name",
      minzoom: 12,
      layout: {
        "symbol-placement": "line",
        "text-field": nomeLocal(),
        "text-font": ["Noto Sans Regular"],
        "text-size": 11,
      },
      paint: { "text-color": "#9dffb0", "text-halo-color": "#000000", "text-halo-width": 1 },
    });
    state.mapa.addSource("incidentes", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
      cluster: true,
      clusterRadius: 42,
      clusterMaxZoom: 9,
    });
    state.mapa.addLayer({
      id: "incidentes-contagem",
      type: "symbol",
      source: "incidentes",
      filter: ["has", "point_count"],
      layout: {
        "text-field": ["concat", "[", ["to-string", ["get", "point_count_abbreviated"]], "]"],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["step", ["get", "point_count"], 13, 20, 15, 50, 17],
        "text-allow-overlap": true,
      },
      paint: {
        "text-color": "#7dff9a",
        "text-halo-color": "#000000",
        "text-halo-width": 1.6,
      },
    });
    ["ransomware", "vazamento", "ataque"].forEach((tipo) => {
      if (!state.mapa.hasImage(`ico-${tipo}`)) {
        state.mapa.addImage(`ico-${tipo}`, desenharIcone(tipo), { pixelRatio: 2 });
      }
    });
    state.mapa.addLayer({
      id: "incidentes-anel",
      type: "circle",
      source: "incidentes",
      filter: ["==", ["get", "id"], ""],
      paint: {
        "circle-radius": 18,
        "circle-color": "rgba(0,0,0,0)",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ff2430",
      },
    });
    state.mapa.addLayer({
      id: "incidentes-ponto",
      type: "symbol",
      source: "incidentes",
      filter: ["!", ["has", "point_count"]],
      layout: {
        "icon-image": ["match", ["get", "tipo"], "ransomware", "ico-ransomware", "vazamento", "ico-vazamento", "ataque", "ico-ataque", "ico-ataque"],
        "icon-size": ["case", ["==", ["get", "precisao"], "municipio"], 0.9, 0.62],
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
    });
    state.mapa.on("click", (evento) => {
      const ponto = state.mapa.queryRenderedFeatures(evento.point, { layers: ["incidentes-ponto"] });
      if (ponto.length) {
        selecionar(ponto[0].properties.id, false);
        return;
      }
      const grupo = state.mapa.queryRenderedFeatures(evento.point, { layers: ["incidentes-contagem"] });
      if (grupo.length) {
        const fonte = state.mapa.getSource("incidentes");
        const coordenadas = grupo[0].geometry.coordinates;
        Promise.resolve(fonte.getClusterExpansionZoom(grupo[0].properties.cluster_id)).then((zoom) => {
          state.mapa.easeTo({ center: coordenadas, zoom });
        });
        return;
      }
      const bloco = state.mapa.queryRenderedFeatures(evento.point, { layers: ["estado-bloco"] });
      const estado = bloco.length ? bloco : state.mapa.queryRenderedFeatures(evento.point, { layers: ["estados-fill"] });
      if (estado.length) {
        const sigla = estado[0].properties.sigla || "";
        elementos.uf.value = elementos.uf.value === sigla ? "" : sigla;
        state.selecionado = null;
        elementos.detail.hidden = true;
        desenhar();
        return;
      }
      if (state.siglaDestacada) {
        elementos.uf.value = "";
        state.selecionado = null;
        elementos.detail.hidden = true;
        desenhar();
      }
    });
    state.mapa.on("mousemove", (evento) => {
      const alvo = state.mapa.queryRenderedFeatures(evento.point, {
        layers: ["incidentes-ponto", "incidentes-contagem", "estados-fill", "estado-bloco"],
      });
      state.mapa.getCanvas().style.cursor = alvo.length ? "pointer" : "";
      if (elementos.coords && evento.lngLat) {
        elementos.coords.textContent = `LAT ${evento.lngLat.lat.toFixed(3)}   LON ${evento.lngLat.lng.toFixed(3)}`;
      }
    });
    state.mapa.on("mouseout", () => {
      if (elementos.coords) elementos.coords.textContent = "LAT —   LON —";
    });
    state.mapa.fitBounds(LIMITES_BRASIL, { padding: 28, duration: 0 });
    state.mapa.getContainer().addEventListener("wheel", (evento) => {
      if (state.retornando) {
        evento.preventDefault();
        evento.stopPropagation();
        return;
      }
      const afastando = evento.deltaY > 0;
      const inclinado = state.mapa.getPitch() > 1 || Math.abs(state.mapa.getBearing()) > 1;
      if (afastando && (state.siglaDestacada || inclinado)) {
        evento.preventDefault();
        evento.stopPropagation();
        elementos.uf.value = "";
        state.selecionado = null;
        elementos.detail.hidden = true;
        desenhar();
        return;
      }
      if (evento.target === state.mapa.getCanvas()) return;
      evento.preventDefault();
      evento.stopPropagation();
      const caixa = state.mapa.getContainer().getBoundingClientRect();
      const bruto = evento.deltaMode === 1 ? evento.deltaY * 16 : evento.deltaY;
      const passo = Math.max(-1.2, Math.min(1.2, -bruto / 220));
      if (!passo) return;
      state.mapa.easeTo({
        zoom: Math.min(14, Math.max(2.5, state.mapa.getZoom() + passo)),
        around: [evento.clientX - caixa.left, evento.clientY - caixa.top],
        duration: 0,
      });
    }, { passive: false, capture: true });
    state.mapa.getContainer().addEventListener("click", (evento) => {
      if (evento.target === state.mapa.getCanvas() || !state.siglaDestacada) return;
      if (evento.target.closest(".maplibregl-ctrl, button, a")) return;
      elementos.uf.value = "";
      state.selecionado = null;
      elementos.detail.hidden = true;
      desenhar();
    });
    document.addEventListener("click", (evento) => {
      if (!state.siglaDestacada) return;
      if (evento.target.closest("#map, button, a, input, select, label")) return;
      elementos.uf.value = "";
      state.selecionado = null;
      elementos.detail.hidden = true;
      desenhar();
    });
    state.mapa.on("render", recortarNoBrasil);
    recortarNoBrasil();
    desenhar();
    iniciarRastros();
  });
  window.addEventListener("resize", () => state.mapa.resize());
}

async function carregar() {
  const [catalogo, estados] = await Promise.all([
    fetch("data/catalog.json").then((resposta) => resposta.json()),
    fetch("data/brazil-states.geojson").then((resposta) => resposta.json()),
  ]);
  state.catalogo = catalogo;
  state.estados = estados;
  preencherFiltros();
  preencherResumo();
  iniciarMapa();
  desenhar();
  elementos.q.form.addEventListener("input", desenhar);
  elementos.q.form.addEventListener("change", desenhar);
  elementos.list.addEventListener("click", (evento) => {
    const botao = evento.target.closest("button[data-id]");
    if (!botao) return;
    selecionar(botao.dataset.id, true);
  });
}

carregar().catch((erro) => {
  elementos.notes.textContent = `Não foi possível abrir o catálogo. Sirva a pasta web por HTTP e rode python scripts/build_catalog.py. (${erro})`;
});
