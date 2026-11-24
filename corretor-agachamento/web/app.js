/* Corretor de Agachamento — interface web.
   O Python faz a visão computacional; esta página só mostra os dados e fala as correções. */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const SVGNS = "http://www.w3.org/2000/svg";

const NOMES_CRITERIO = {
  profundidade: "Profundidade", tronco: "Tronco", alinhamento: "Tronco × canela", subida: "Subida (quadril × peito)",
  equilibrio: "Peso no meio do pé", calcanhar: "Calcanhar", cabeca: "Cabeça", joelhos: "Joelhos para dentro",
  linha_pe: "Joelho × ponta do pé", simetria: "Simetria", ombros: "Ombros", base: "Base dos pés",
  extensao: "Extensão no topo", controle: "Controle no fundo", ritmo: "Ritmo",
};
const DICAS_TELA = {
  "Profundidade insuficiente": "Desça até a coxa ficar paralela ao chão.",
  "Tronco muito inclinado": "Mantenha o peito aberto.",
  "Tronco à frente da canela": "Deixe o tronco mais paralelo à canela.",
  "Calcanhar saindo do chão": "Mantenha os calcanhares no chão.",
  "Joelhos para dentro": "Empurre os joelhos para fora.",
  "Movimento assimétrico": "Distribua o peso nas duas pernas.",
  "Base dos pés inadequada": "Pés na largura dos ombros.",
  "Quadril subindo antes do peito": "Suba o peito junto com o quadril.",
  "Peso fora do meio do pé": "Mantenha o peso no meio do pé.",
  "Não estendeu totalmente": "Suba até ficar totalmente em pé.",
  "Joelho fora da linha do pé": "Joelho na direção da ponta do pé.",
  "Ombros desnivelados": "Mantenha os ombros nivelados.",
  "Quique no fundo": "Controle a descida, sem quicar.",
  "Cabeça desalinhada": "Olhe para a frente, pescoço alinhado.",
};
const FASES = { preparando: "Preparando", executando: "Em execução", descanso: "Descanso", concluido: "Concluído" };
const DICA_ICONE = { "Desça": "azul", "Mantenha o peito": "laranja", "Deixe": "laranja", "Mantenha os": "amarelo", "Empurre": "roxo", "Distribua": "roxo", "Ajuste": "verde" };

/* ============================== utilidades ============================== */
async function api(url, opcoes = {}) {
  const r = await fetch(url, opcoes);
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.erro || `Erro ${r.status}`);
  return dados;
}
const postar = (url, corpo = {}) =>
  api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });

function toast(msg) {
  if (document.body.classList.contains("modo-cheio")) return;  // na tela cheia nada aparece por cima do treino
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 5000);
}
const lerPref = (k, padrao) => { try { return localStorage.getItem(k) ?? padrao; } catch { return padrao; } };
const salvarPref = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sem armazenamento */ } };

function classeNota(n) {
  if (n >= 85) return ["excelente", "Excelente"];
  if (n >= 70) return ["boa", "Boa"];
  if (n >= 50) return ["regular", "Regular"];
  return ["ruim", "Precisa melhorar"];
}
function formatarData(iso, curto = false) {
  const d = new Date(iso);
  const dia = d.toLocaleDateString("pt-BR", { day: "numeric", month: "short" }).replace(".", "");
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return curto ? dia : `${dia}, ${hora}`;
}
function formatarDuracao(s) {
  if (!s) return "–";
  const m = Math.floor(s / 60), r = Math.round(s % 60);
  return m ? `${m}<small>min</small> ${r}<small>s</small>` : `${r}<small>s</small>`;
}
function el(tag, attrs = {}, filhos = []) {
  const e = tag.startsWith("svg:") ? document.createElementNS(SVGNS, tag.slice(4)) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "texto") e.textContent = v;
    else if (k === "html") e.innerHTML = v;
    else if (v !== undefined && v !== null) e.setAttribute(k, v);
  }
  for (const f of [].concat(filhos)) if (f) e.append(f);
  return e;
}
const icone = nome => el("svg:svg", { "aria-hidden": "true" }, el("svg:use", { href: `#i-${nome}` }));
function tile(rotulo, valor, extra = "") {
  return el("div", { class: "tile" }, [
    el("span", { class: "rotulo", texto: rotulo }),
    el("div", { class: "valor", html: valor }),
    extra ? el("div", { class: "extra", texto: extra }) : null,
  ]);
}

/* ============================== anéis (estilo Atividade) ============================== */
function aneis(itens, tamanho = 200) {
  const esp = tamanho * 0.085, gap = tamanho * 0.022;
  const svg = el("svg:svg", { viewBox: `0 0 ${tamanho} ${tamanho}`, class: "aneis", role: "img",
    "aria-label": itens.map(i => `${i.nome}: ${i.texto}`).join(", ") });
  const g = el("svg:g", { transform: `rotate(-90 ${tamanho / 2} ${tamanho / 2})` });
  itens.forEach((it, i) => {
    const r = tamanho / 2 - esp / 2 - i * (esp + gap);
    const circ = 2 * Math.PI * r;
    g.append(el("svg:circle", { cx: tamanho / 2, cy: tamanho / 2, r, class: "trilho", stroke: it.cor, "stroke-width": esp }));
    const valor = el("svg:circle", { cx: tamanho / 2, cy: tamanho / 2, r, class: "valor", stroke: it.cor, "stroke-width": esp,
      "stroke-dasharray": circ, "stroke-dashoffset": circ });
    g.append(valor);
    const frac = Math.max(0, Math.min(it.frac, 1));
    requestAnimationFrame(() => requestAnimationFrame(() => valor.setAttribute("stroke-dashoffset", circ * (1 - frac) || (frac ? 0 : circ - 0.01))));
  });
  svg.append(g);
  return svg;
}
function cartaoAneis(alvo, s, titulo) {
  alvo.innerHTML = "";
  const meta = s.repeticoes_meta ? s.series_planejadas * s.repeticoes_meta : s.total;
  const itens = [
    { nome: "Acerto", frac: s.percentual_acerto / 100, cor: "var(--anel-acerto)", texto: `${s.percentual_acerto}%`, cls: "cor-acerto",
      html: `${s.percentual_acerto}<small>%</small>` },
    { nome: "Nota média", frac: s.nota_media / 100, cor: "var(--anel-nota)", texto: `${s.nota_media}`, cls: "cor-nota",
      html: `${s.nota_media}<small>/100</small>` },
    { nome: "Meta", frac: meta ? s.total / meta : 0, cor: "var(--anel-meta)", texto: `${s.total} de ${meta}`, cls: "cor-meta",
      html: `${s.total}<small>/${meta} reps</small>` },
  ];
  if (titulo) alvo.append(el("div", { class: "titulo-aneis" }, [el("h3", { texto: titulo }), el("span", { class: "sutil pequeno", texto: formatarData(s.data) })]));
  const legenda = el("div", { class: "legenda-aneis" }, itens.map(i =>
    el("div", {}, [el("span", { class: `nome ${i.cls}`, texto: i.nome }), el("span", { class: "num", html: i.html })])));
  if (!titulo) {
    // versão grande (tela de resumo): frase de destaque acima dos números
    const [cls, nome] = classeNota(s.nota_media);
    alvo.append(aneis(itens), el("div", { class: "aneis-texto" }, [
      el("p", { class: `destaque-nota ${cls}`, texto: nome }),
      el("p", { class: "frase-resumo", texto: `${s.corretas} de ${s.total} repetições corretas${s.repeticoes_meta ? `, em ${s.series_feitas} de ${s.series_planejadas} séries` : ""}.` }),
      legenda]));
    return;
  }
  alvo.append(aneis(itens), legenda);
}

/* ============================== voz e tema ============================== */
const Voz = {
  // modo: "francisca" / "antonio" (vozes naturais geradas no Python), "navegador" ou "off"
  modo: "francisca",
  ultimoModoLigado: "francisca",
  vozNavegador: null,
  fila: [],
  tocando: null,
  naturalFalhou: false,
  init() {
    this.modo = lerPref("voz_modo", "francisca");
    if (this.modo !== "off") this.ultimoModoLigado = this.modo;
    const sel = $("#escolha-voz");
    sel.value = this.modo;
    sel.addEventListener("change", () => this.definir(sel.value));
    $("#botao-ouvir").addEventListener("click", () => {
      this.parar();
      if (this.modo === "off") { toast("A voz está desligada."); return; }
      this.falar("Boa! Desça até a coxa ficar paralela ao chão.", "teste");
    });
    $("#botao-voz").addEventListener("click", () => this.definir(this.modo === "off" ? this.ultimoModoLigado : "off"));
    this.botao();
    if ("speechSynthesis" in window) {
      const escolher = () => (this.vozNavegador = this.melhorVozNavegador());
      escolher();
      speechSynthesis.onvoiceschanged = escolher;
    }
  },
  definir(modo) {
    this.modo = modo;
    if (modo !== "off") this.ultimoModoLigado = modo;
    this.naturalFalhou = false;
    salvarPref("voz_modo", modo);
    $("#escolha-voz").value = modo;
    if (modo === "off") this.parar();
    this.botao();
  },
  get ligada() { return this.modo !== "off"; },
  get natural() { return this.modo === "francisca" || this.modo === "antonio"; },
  botao() {
    const b = $("#botao-voz");
    b.innerHTML = "";
    b.append(icone(this.ligada ? "som" : "mudo"));
    b.classList.toggle("desligado", !this.ligada);
    b.title = this.ligada ? "Voz ligada" : "Voz desligada";
  },
  melhorVozNavegador() {
    // vozes "Natural"/"Online" (Edge) e as do Google soam bem melhores que as vozes locais
    const vozes = speechSynthesis.getVoices().filter(v => v.lang.replace("_", "-").toLowerCase().startsWith("pt"));
    const pontos = v => (/natural|online|neural/i.test(v.name) ? 4 : 0) + (/google/i.test(v.name) ? 2 : 0) +
      (v.lang.replace("_", "-") === "pt-BR" ? 1 : 0);
    return vozes.sort((a, b) => pontos(b) - pontos(a))[0] || null;
  },
  destravar() {
    // o navegador só toca som depois de um clique; este áudio vazio "libera" o som
    // o navegador só toca som depois de um clique do usuário; o clique em "Iniciar treino" já libera
    if ("speechSynthesis" in window) speechSynthesis.speak(new SpeechSynthesisUtterance(""));
  },
  parar() {
    this.fila = [];
    if (this.tocando) { this.tocando.pause(); this.tocando = null; }
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  },
  falar(texto, tipo) {
    if (!this.ligada) return;
    const urgente = ["contagem", "rep_ok", "rep_erro", "inicio", "teste"].includes(tipo);
    const ocupado = this.tocando || this.fila.length || ("speechSynthesis" in window && speechSynthesis.speaking);
    if (tipo === "alerta" && ocupado) return;   // não empilha alertas repetidos
    if (urgente) this.parar();
    this.fila.push(texto);
    if (!this.tocando && !("speechSynthesis" in window && speechSynthesis.speaking)) this.proxima();
  },
  proxima() {
    const texto = this.fila.shift();
    if (texto === undefined) return;
    if (this.natural && !this.naturalFalhou) {
      const audio = new Audio(`/api/voz?v=${this.modo}&t=${encodeURIComponent(texto)}`);
      this.tocando = audio;
      const seguir = () => { if (this.tocando === audio) { this.tocando = null; this.proxima(); } };
      audio.addEventListener("ended", seguir);
      audio.addEventListener("error", () => {
        if (this.tocando !== audio) return;
        this.tocando = null;
        this.naturalFalhou = true;  // sem internet: usa a voz do navegador até trocar a voz de novo
        console.info("Voz natural indisponível (sem internet?). Usando a voz do navegador.");
        this.fila.unshift(texto);
        this.proxima();
      });
      audio.play().catch(() => {});
      return;
    }
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = "pt-BR";
    u.rate = 1.05;
    if (this.vozNavegador) u.voice = this.vozNavegador;
    u.onend = () => this.proxima();
    speechSynthesis.speak(u);
  },
};

const Tema = {
  init() {
    const salvo = lerPref("tema", null);
    if (salvo) document.documentElement.dataset.theme = salvo;
    this.botao();
    $("#botao-tema").addEventListener("click", () => {
      const escuro = this.escuro();
      document.documentElement.dataset.theme = escuro ? "light" : "dark";
      salvarPref("tema", document.documentElement.dataset.theme);
      this.botao();
      navegar({ type: "resize" });
    });
  },
  escuro() {
    const t = document.documentElement.dataset.theme;
    return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  },
  botao() {
    const b = $("#botao-tema");
    b.innerHTML = "";
    b.append(icone(this.escuro() ? "sol" : "lua"));
  },
};

/* ============================== boneco animado ============================== */
function poseBoneco(anguloJoelho, base = { x: 120, y: 262 }, esc = 1) {
  const L = 78 * esc, T = 92 * esc;
  const a = ((180 - anguloJoelho) / 2) * Math.PI / 180;
  const tornozelo = { x: base.x, y: base.y };
  const joelho = { x: tornozelo.x + L * Math.sin(a), y: tornozelo.y - L * Math.cos(a) };
  const quadril = { x: joelho.x - L * Math.sin(a), y: joelho.y - L * Math.cos(a) };
  const prof = Math.min(Math.max((175 - anguloJoelho) / 85, 0), 1);
  const t = (8 + 30 * prof) * Math.PI / 180;
  const ombro = { x: quadril.x + T * Math.sin(t), y: quadril.y - T * Math.cos(t) };
  // braços: quase soltos ao lado do corpo em pé, esticados à frente no fundo do agachamento
  const fi = (75 - 75 * prof) * Math.PI / 180;
  const cotovelo = { x: ombro.x + 36 * esc * Math.cos(fi), y: ombro.y + 36 * esc * Math.sin(fi) };
  const punho = { x: cotovelo.x + 34 * esc * Math.cos(fi - 0.1), y: cotovelo.y + 34 * esc * Math.sin(fi - 0.1) };
  const cabeca = { x: ombro.x + 27 * esc * Math.sin(t * 0.8), y: ombro.y - 27 * esc * Math.cos(t * 0.8) };
  return { tornozelo, joelho, quadril, ombro, cotovelo, punho, cabeca, pe: { x: tornozelo.x + 30 * esc, y: tornozelo.y } };
}

function desenharBoneco(svg, ang, opcoes = {}) {
  const esc = opcoes.escala || 1;
  const p = poseBoneco(ang, opcoes.base, esc);
  svg.innerHTML = "";
  svg.classList.add("boneco");
  const linha = (a, b, cls) => svg.append(el("svg:line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: cls }));
  linha({ x: p.tornozelo.x - 70 * esc, y: p.tornozelo.y + 9 }, { x: p.tornozelo.x + 90 * esc, y: p.tornozelo.y + 9 }, "chao");
  if (opcoes.guia) linha({ x: p.joelho.x - 120 * esc, y: p.joelho.y }, { x: p.joelho.x + 30 * esc, y: p.joelho.y }, "guia-linha");
  if (opcoes.angulo) {
    const r = 28 * esc;
    const a1 = Math.atan2(p.quadril.y - p.joelho.y, p.quadril.x - p.joelho.x);
    const a2 = Math.atan2(p.tornozelo.y - p.joelho.y, p.tornozelo.x - p.joelho.x);
    const ponto = a => `${p.joelho.x + r * Math.cos(a)} ${p.joelho.y + r * Math.sin(a)}`;
    svg.append(el("svg:path", { d: `M ${p.joelho.x} ${p.joelho.y} L ${ponto(a1)} A ${r} ${r} 0 0 0 ${ponto(a2)} Z`, class: "arco" }));
  }
  linha(p.quadril, p.ombro, "osso");
  linha(p.tornozelo, p.pe, "osso perna");
  linha(p.quadril, p.joelho, "osso perna"); linha(p.joelho, p.tornozelo, "osso perna");
  svg.append(el("svg:circle", { cx: p.cabeca.x, cy: p.cabeca.y, r: 17 * esc, class: "cabeca" }));
  linha(p.ombro, p.cotovelo, "osso"); linha(p.cotovelo, p.punho, "osso");
  for (const j of [p.ombro, p.quadril, p.joelho, p.tornozelo]) svg.append(el("svg:circle", { cx: j.x, cy: j.y, r: 6 * esc, class: "junta" }));
  if (opcoes.angulo) svg.append(el("svg:text", { x: p.joelho.x + 20 * esc, y: p.joelho.y + 5, class: "texto-angulo", texto: `${Math.round(ang)}°` }));
}

function animarBoneco(svg, aoAtualizar, opcoes = {}) {
  let inicio = null;
  const ciclo = 3600;
  const passo = ts => {
    inicio ??= ts;
    const t = ((ts - inicio) % ciclo) / ciclo;
    let prof;
    if (t < 0.12) prof = 0;
    else if (t < 0.5) prof = (1 - Math.cos(((t - 0.12) / 0.38) * Math.PI)) / 2;
    else if (t < 0.6) prof = 1;
    else if (t < 0.95) prof = (1 + Math.cos(((t - 0.6) / 0.35) * Math.PI)) / 2;
    else prof = 0;
    const ang = 175 - 87 * prof;
    if (svg.closest(".tela.visivel")) {
      desenharBoneco(svg, ang, opcoes);
      aoAtualizar?.(ang);
    }
    requestAnimationFrame(passo);
  };
  requestAnimationFrame(passo);
}

/* ============================== gráficos (SVG feito à mão) ============================== */
const Tooltip = {
  mostrar(evt, html) {
    const t = $("#tooltip");
    t.innerHTML = html;
    t.hidden = false;
    const x = Math.min(evt.clientX + 14, window.innerWidth - t.offsetWidth - 8);
    t.style.left = `${x}px`;
    t.style.top = `${evt.clientY - t.offsetHeight - 14}px`;
  },
  esconder() { $("#tooltip").hidden = true; },
};

function graficoEvolucao(alvo, sessoes) {
  alvo.innerHTML = "";
  if (sessoes.length === 0) {
    alvo.append(el("div", { class: "vazio", texto: "Faça o primeiro treino para ver sua evolução aqui." }));
    return;
  }
  const series = [
    { chave: "percentual_acerto", nome: "% de acerto", curto: "Acerto", cor: "var(--serie-a)", sufixo: "%" },
    { chave: "nota_media", nome: "Nota média", curto: "Nota", cor: "var(--serie-b)", sufixo: "" },
  ];
  const legenda = el("div", { class: "legenda" }, series.map(s => el("span", { html: `<i style="background:${s.cor}"></i>${s.nome}` })));
  const W = Math.max(alvo.clientWidth, 320), H = 240, m = { t: 14, r: 92, b: 30, l: 34 };
  const w = W - m.l - m.r, h = H - m.t - m.b;
  const n = sessoes.length;
  const x = i => m.l + (n === 1 ? w / 2 : (i / (n - 1)) * w);
  const y = v => m.t + h - (v / 100) * h;
  const svg = el("svg:svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Evolução do percentual de acerto e da nota média por treino" });
  const grade = el("svg:g", { class: "grade" }), eixo = el("svg:g", { class: "eixo" });
  for (const v of [0, 25, 50, 75, 100]) {
    grade.append(el("svg:line", { x1: m.l, x2: m.l + w, y1: y(v), y2: y(v) }));
    eixo.append(el("svg:text", { x: m.l - 10, y: y(v) + 4, "text-anchor": "end", texto: v }));
  }
  const passoRotulo = Math.ceil(n / 8);
  sessoes.forEach((s, i) => {
    if (i % passoRotulo === 0 || i === n - 1)
      eixo.append(el("svg:text", { x: x(i), y: H - 6, "text-anchor": "middle", texto: formatarData(s.data, true) }));
  });
  svg.append(grade, eixo);
  for (const s of series) {
    const d = sessoes.map((ses, i) => `${i ? "L" : "M"}${x(i)},${y(ses[s.chave])}`).join(" ");
    svg.append(el("svg:path", { d, fill: "none", stroke: s.cor, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    sessoes.forEach((ses, i) => svg.append(el("svg:circle", {
      cx: x(i), cy: y(ses[s.chave]), r: 4.5, fill: s.cor, stroke: "var(--cartao)", "stroke-width": 2 })));
  }
  const ult = sessoes[n - 1];
  const rotulos = series.map(s => ({ s, yy: y(ult[s.chave]) + 4 })).sort((a, b) => a.yy - b.yy);
  if (rotulos[1].yy - rotulos[0].yy < 16) {
    const meio = (rotulos[0].yy + rotulos[1].yy) / 2;
    rotulos[0].yy = meio - 8; rotulos[1].yy = meio + 8;
  }
  for (const { s, yy } of rotulos)
    svg.append(el("svg:text", { x: x(n - 1) + 12, y: yy, class: "rotulo-direto", texto: `${s.curto} ${ult[s.chave]}${s.sufixo}` }));

  const cruz = el("svg:line", { y1: m.t, y2: m.t + h, stroke: "var(--sutil)", "stroke-width": 1, opacity: 0 });
  svg.append(cruz);
  const area = el("svg:rect", { x: m.l - 10, y: m.t, width: w + 20, height: h, fill: "transparent" });
  area.addEventListener("mousemove", evt => {
    const r = svg.getBoundingClientRect();
    const px = ((evt.clientX - r.left) / r.width) * W;
    const i = n === 1 ? 0 : Math.max(0, Math.min(n - 1, Math.round(((px - m.l) / w) * (n - 1))));
    const s = sessoes[i];
    cruz.setAttribute("x1", x(i)); cruz.setAttribute("x2", x(i)); cruz.setAttribute("opacity", .5);
    Tooltip.mostrar(evt, `<strong>${formatarData(s.data)}</strong><br>Acerto ${s.percentual_acerto}% · Nota ${s.nota_media}<br><span style="opacity:.7">${s.corretas} de ${s.total} repetições corretas</span>`);
  });
  area.addEventListener("mouseleave", () => { cruz.setAttribute("opacity", 0); Tooltip.esconder(); });
  svg.append(area);
  alvo.append(legenda, svg);
}

function graficoNotas(alvo, reps) {
  alvo.innerHTML = "";
  if (!reps.length) { alvo.append(el("div", { class: "vazio", texto: "Nenhuma repetição registrada." })); return; }
  const W = Math.max(alvo.clientWidth, 320), H = 240, m = { t: 14, r: 8, b: 30, l: 34 };
  const w = W - m.l - m.r, h = H - m.t - m.b;
  const n = reps.length, passo = w / n, larg = Math.max(Math.min(passo - 4, 26), 3);
  const y = v => m.t + h - (v / 100) * h;
  const svg = el("svg:svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Nota de cada repetição" });
  const grade = el("svg:g", { class: "grade" }), eixo = el("svg:g", { class: "eixo" });
  for (const v of [0, 50, 70, 85, 100]) {
    grade.append(el("svg:line", { x1: m.l, x2: m.l + w, y1: y(v), y2: y(v) }));
    eixo.append(el("svg:text", { x: m.l - 10, y: y(v) + 4, "text-anchor": "end", texto: v }));
  }
  svg.append(grade, eixo);
  let serieAnterior = null, numero = 0;
  reps.forEach((r, i) => {
    const cx = m.l + passo * i + passo / 2;
    if (r.serie !== serieAnterior) {
      numero = 0;
      eixo.append(el("svg:text", { x: m.l + passo * i + 4, y: H - 6, texto: `Série ${r.serie}` }));
      if (serieAnterior !== null) grade.append(el("svg:line", { x1: m.l + passo * i, x2: m.l + passo * i, y1: m.t, y2: m.t + h, "stroke-dasharray": "3 4" }));
      serieAnterior = r.serie;
    }
    numero += 1;
    const topo = y(Math.max(r.nota, 2)), base = y(0), raio = Math.min(5, larg / 2);
    const d = `M${cx - larg / 2},${base} V${topo + raio} Q${cx - larg / 2},${topo} ${cx - larg / 2 + raio},${topo} H${cx + larg / 2 - raio} Q${cx + larg / 2},${topo} ${cx + larg / 2},${topo + raio} V${base} Z`;
    const barra = el("svg:path", { d, fill: r.correta ? "var(--verde)" : "var(--vermelho)" });
    const n2 = numero;
    const alvoHover = el("svg:rect", { x: m.l + passo * i, y: m.t, width: passo, height: h, fill: "transparent" });
    alvoHover.addEventListener("mousemove", evt => Tooltip.mostrar(evt,
      `<strong>Série ${r.serie}, repetição ${n2}</strong><br>Nota ${r.nota} · ${classeNota(r.nota)[1]}<br><span style="opacity:.7">${r.erros.length ? r.erros.join(", ") : "Sem erros"}</span>`));
    alvoHover.addEventListener("mouseleave", Tooltip.esconder);
    svg.append(barra, alvoHover);
  });
  alvo.append(svg);
}

function graficoErros(alvo, erros, total) {
  alvo.innerHTML = "";
  const itens = Object.entries(erros).sort((a, b) => b[1] - a[1]);
  if (!itens.length) {
    alvo.append(el("div", { class: "vazio", html: "Nenhum erro de técnica.<br><strong>Execução impecável!</strong>" }));
    return;
  }
  const W = Math.max(alvo.clientWidth, 320), linha = 64, H = itens.length * linha;
  const max = Math.max(...itens.map(i => i[1]));
  const svg = el("svg:svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Quantidade de repetições com cada erro" });
  itens.forEach(([nome, qtd], i) => {
    const yy = i * linha, larg = ((W - 90) * qtd) / max;
    svg.append(el("svg:text", { x: 0, y: yy + 18, fill: "var(--texto)", "font-size": 15, "font-weight": 500, "font-family": "var(--fonte)", texto: nome }));
    svg.append(el("svg:rect", { x: 0, y: yy + 28, width: W - 90, height: 10, rx: 5, fill: "var(--preenchimento)" }));
    svg.append(el("svg:rect", { x: 0, y: yy + 28, width: Math.max(larg, 10), height: 10, rx: 5, fill: "var(--azul)" }));
    svg.append(el("svg:text", { x: W, y: yy + 38, "text-anchor": "end", fill: "var(--texto)", "font-size": 15, "font-weight": 600, "font-family": "var(--fonte)",
      texto: `${qtd} · ${Math.round((100 * qtd) / total)}%` }));
  });
  alvo.append(svg);
}

/* ============================== telas ============================== */
const Telas = {};

function itemSessao(s) {
  const [cls] = classeNota(s.nota_media);
  return el("a", { class: "item-lista", href: `#/resumo/${s.id}` }, [
    el("div", {}, [el("div", { class: "titulo", texto: formatarData(s.data) }),
      el("div", { class: "sub", texto: `${s.total} repetições · ${s.series_feitas} ${s.series_feitas === 1 ? "série" : "séries"}` })]),
    el("span", { class: "estado " + (s.percentual_acerto >= 70 ? "ok" : "erro"), texto: `${s.percentual_acerto}%` }),
    el("span", { class: `nota-badge ${cls}`, style: "font-size:20px", texto: s.nota_media }),
    icone("chevron"),
  ]);
}

Telas.inicio = async () => {
  const sessoes = await api("/api/historico").catch(() => []);
  const ultima = sessoes[sessoes.length - 1];
  const cartao = $("#cartao-ultimo");
  if (ultima) cartaoAneis(cartao, ultima, "Último treino");
  else {
    cartao.innerHTML = "";
    cartao.append(el("div", { class: "titulo-aneis" }, el("h3", { texto: "Último treino" })),
      aneis([{ frac: 0, cor: "var(--anel-acerto)", nome: "", texto: "" }, { frac: 0, cor: "var(--anel-nota)", nome: "", texto: "" }, { frac: 0, cor: "var(--anel-meta)", nome: "", texto: "" }]),
      el("div", { class: "legenda-aneis" }, [el("p", { class: "sutil", texto: "Seus anéis de acerto, nota e meta aparecem aqui depois do primeiro treino." }),
        el("a", { class: "link-seta", href: "#/treinar", html: 'Começar agora <svg><use href="#i-chevron"/></svg>' })]));
  }
  const tiles = $("#tiles-inicio");
  tiles.innerHTML = "";
  const reps = sessoes.reduce((a, s) => a + s.total, 0);
  const corretas = sessoes.reduce((a, s) => a + s.corretas, 0);
  const notaMedia = reps ? Math.round(sessoes.reduce((a, s) => a + s.nota_media * s.total, 0) / reps) : null;
  tiles.append(
    tile("Treinos", sessoes.length, ultima ? `último em ${formatarData(ultima.data, true)}` : "nenhum ainda"),
    tile("Repetições", reps, `${corretas} corretas`),
    tile("Acerto geral", reps ? `${Math.round((100 * corretas) / reps)}<small>%</small>` : "–", "sem erro de técnica"),
    tile("Nota média", notaMedia ?? "–", notaMedia !== null ? classeNota(notaMedia)[1] : "de 0 a 100"),
  );
  graficoEvolucao($("#grafico-evolucao-inicio"), sessoes.slice(-10));
  const lista = $("#lista-recentes");
  lista.innerHTML = "";
  if (!sessoes.length) lista.append(el("div", { class: "vazio", texto: "Seus treinos aparecem aqui." }));
  for (const s of sessoes.slice(-5).reverse()) lista.append(itemSessao(s));
};

/* ---------- configurar treino ---------- */
const DESEMPENHO = {
  rapido: "Rápido: modelo leve e imagem menor. Use se a câmera estiver travando ou atrasada (notebooks mais simples).",
  equilibrado: "Equilibrado: o padrão, bom para a maioria dos computadores.",
  preciso: "Preciso: modelo mais pesado, detecta melhor de longe. Precisa de um computador mais forte; na primeira vez o modelo é baixado.",
};
const Config = {
  valores: { series: 3, repeticoes: 10, descanso: 45 },
  fonte: "webcam",
  video: null,
  vista: "auto",
  desempenho: null,  // null = o padrão do servidor (python app.py --modelo ...)
  init() {
    $$(".campo-numero").forEach(c => {
      const campo = c.dataset.campo;
      c.addEventListener("click", e => {
        const d = e.target.closest("[data-delta]")?.dataset.delta;
        if (!d) return;
        const passo = Number(c.dataset.passo), min = Number(c.dataset.min), max = Number(c.dataset.max);
        this.valores[campo] = Math.min(max, Math.max(min, this.valores[campo] + Number(d) * passo));
        $$("#presets button").forEach(b => b.classList.remove("ativo"));
        this.atualizar();
      });
    });
    $$("#presets button").forEach(b => b.addEventListener("click", () => {
      const [s, r, d] = b.dataset.preset.split(",").map(Number);
      Object.assign(this.valores, { series: s, repeticoes: r, descanso: d });
      $$("#presets button").forEach(x => x.classList.toggle("ativo", x === b));
      this.atualizar();
    }));
    $$("#seg-fonte button").forEach(b => b.addEventListener("click", () => {
      this.fonte = b.dataset.fonte;
      $$("#seg-fonte button").forEach(x => x.classList.toggle("ativo", x === b));
      $("#fonte-webcam").hidden = this.fonte !== "webcam";
      $("#fonte-video").hidden = this.fonte !== "video";
      this.atualizar();
    }));
    $$("#opcoes-vista button").forEach(b => b.addEventListener("click", () => {
      this.vista = b.dataset.vista;
      $$("#opcoes-vista button").forEach(x => x.classList.toggle("ativo", x === b));
    }));
    $$("#seg-desempenho button").forEach(b => b.addEventListener("click", () => {
      this.escolherDesempenho(b.dataset.desempenho);
      salvarPref("desempenho", this.desempenho);
    }));
    const salvo = lerPref("desempenho", null);
    if (salvo) this.escolherDesempenho(salvo);
    else api("/api/info").then(i => this.escolherDesempenho(i.desempenho)).catch(() => this.escolherDesempenho("equilibrado"));
    $("#arquivo-video").addEventListener("change", e => this.enviar(e.target.files[0]));
    $("#botao-iniciar").addEventListener("click", () => this.iniciar());
    this.atualizar();
  },
  escolherDesempenho(modo) {
    if (!DESEMPENHO[modo]) modo = "equilibrado";
    this.desempenho = modo;
    $$("#seg-desempenho button").forEach(x => x.classList.toggle("ativo", x.dataset.desempenho === modo));
    $("#nota-desempenho").textContent = DESEMPENHO[modo];
  },
  atualizar() {
    for (const [k, v] of Object.entries(this.valores))
      $(`.campo-numero[data-campo="${k}"] output`).textContent = k === "descanso" ? `${v} s` : v;
    const { series, repeticoes, descanso } = this.valores;
    let texto = repeticoes === 0
      ? "Modo livre: conta todas as repetições até você encerrar."
      : `${series} × ${repeticoes} = ${series * repeticoes} repetições${series > 1 && descanso ? `, com ${descanso} s de descanso entre as séries` : ""}.`;
    if (this.fonte === "video") texto += " Com vídeo, as séries seguem direto (sem contagem e sem descanso) e o treino termina quando o vídeo acaba.";
    $("#resumo-meta").textContent = texto;
  },
  async enviar(arquivo) {
    if (!arquivo) return;
    $("#nome-upload").textContent = arquivo.name;
    $("#status-upload").textContent = "Enviando...";
    const dados = new FormData();
    dados.append("video", arquivo);
    try {
      const r = await api("/api/upload", { method: "POST", body: dados });
      this.video = r.fonte;
      $("#status-upload").textContent = "Pronto para analisar · clique para trocar";
      $("#area-upload").classList.add("pronto");
    } catch (e) {
      $("#nome-upload").textContent = "Escolher vídeo";
      $("#status-upload").textContent = "";
      toast(e.message);
    }
  },
  async iniciar() {
    Voz.destravar();
    if (AoVivo.cheio) TelaCheia.entrar();  // o clique em "Iniciar" permite abrir a tela cheia
    let fonte = $("#indice-webcam").value;
    if (this.fonte === "video") {
      if (!this.video) { TelaCheia.sair(); toast("Escolha um vídeo primeiro."); return; }
      fonte = this.video;
    }
    const botao = $("#botao-iniciar");
    botao.disabled = true;
    try {
      await postar("/api/iniciar", { fonte, vista: this.vista, voz: Voz.modo, desempenho: this.desempenho, ...this.valores });
      location.hash = "#/ao-vivo";
    } catch (e) {
      TelaCheia.sair();
      toast(e.message);
    } finally {
      botao.disabled = false;
    }
  },
};

/* ---------- treino ao vivo ---------- */
const AoVivo = {
  timer: null,
  ultimoEvento: 0,
  repsMostradas: 0,
  pausado: false,
  ocupado: false,
  cheio: false,
  init() {
    this.cheio = lerPref("modo_treino", "normal") === "cheio";
    document.addEventListener("click", async evt => {
      const b = evt.target.closest("[data-acao]");
      if (!b || !b.closest("#tela-ao-vivo")) return;
      const acao = b.dataset.acao;
      if (acao === "modo") this.definirModo(!this.cheio);
      if (acao === "pausar") {
        this.pausado = !this.pausado;
        await postar("/api/pausar", { pausado: this.pausado });
        this.botoesPausa();
      }
      if (acao === "encerrar") {
        $$('[data-acao="encerrar"]').forEach(x => (x.disabled = true));
        const r = await postar("/api/parar").catch(() => ({}));
        $$('[data-acao="encerrar"]').forEach(x => (x.disabled = false));
        this.parar();
        location.hash = r.sessao_id ? `#/resumo/${r.sessao_id}` : "#/treinar";
      }
    });
    $("#botao-pular").addEventListener("click", () => postar("/api/pular-descanso"));
    // Esc sai da tela cheia do navegador: volta também para o modo normal
    document.addEventListener("fullscreenchange", () => {
      if (!document.fullscreenElement && this.cheio && this.timer) this.definirModo(false, false);
    });
  },
  definirModo(cheio, mexerTelaCheia = true) {
    this.cheio = cheio;
    salvarPref("modo_treino", cheio ? "cheio" : "normal");
    $("#ao-vivo").classList.toggle("cheio", cheio);
    document.body.classList.toggle("modo-cheio", cheio && !!this.timer);
    if (mexerTelaCheia) cheio ? TelaCheia.entrar() : TelaCheia.sair();
  },
  botoesPausa() {
    $$('[data-acao="pausar"]').forEach(b => {
      if (b.classList.contains("botao-hud")) { b.innerHTML = ""; b.append(icone(this.pausado ? "play" : "pausa")); }
      else b.textContent = this.pausado ? "Continuar" : "Pausar";
      b.title = this.pausado ? "Continuar" : "Pausar";
    });
  },
  iniciar() {
    this.ultimoEvento = 0;
    this.repsMostradas = 0;
    this.pausado = false;
    this.botoesPausa();
    $$('[data-v="trilha"]').forEach(t => (t.innerHTML = ""));
    $$('[data-v="criterios"]').forEach(c => (c.innerHTML = '<p class="sutil pequeno">A nota de cada articulação aparece quando você terminar a primeira repetição.</p>'));
    this.texto("ultima-nota", "–");
    $("#video").src = `/video?t=${Date.now()}`;
    clearInterval(this.timer);
    this.timer = setInterval(() => this.atualizar(), 120);
    this.definirModo(this.cheio, false);
    this.atualizar();
  },
  parar() {
    clearInterval(this.timer);
    this.timer = null;
    $("#video").removeAttribute("src");
    document.body.classList.remove("modo-cheio");
    TelaCheia.sair();
  },
  async atualizar() {
    if (this.ocupado) return;
    this.ocupado = true;
    let e;
    try { e = await api(`/api/estado?desde=${this.ultimoEvento}`); } catch { this.ocupado = false; return; }
    this.ocupado = false;
    if (!this.timer) return;
    if (!e.fase) {
      this.parar();
      if (e.erro) toast(e.erro);
      location.hash = "#/treinar";
      return;
    }
    for (const ev of e.eventos) {
      this.ultimoEvento = Math.max(this.ultimoEvento, ev.id);
      Voz.falar(ev.texto, ev.tipo);
    }
    this.render(e);
    if (!e.ativo) {
      clearInterval(this.timer);
      if (e.erro) { this.parar(); toast(e.erro); location.hash = "#/treinar"; return; }
      this.mensagem(e.fim_do_video ? "info" : "ok", "check", e.fim_do_video ? "Fim do vídeo" : "Treino concluído!",
        `${e.total} repetições, ${e.percentual ?? 0}% corretas. Abrindo o resumo...`);
      setTimeout(() => { this.parar(); location.hash = e.sessao_id ? `#/resumo/${e.sessao_id}` : "#/treinar"; }, 1800);
    }
  },
  // preenche todos os elementos com o mesmo data-v (os dois modos ao mesmo tempo)
  texto(chave, valor) {
    $$(`[data-v="${chave}"]`).forEach(x => { if (x.textContent !== String(valor)) x.textContent = valor; });
  },
  mensagem(tipo, iconeNome, titulo, sub) {
    this.texto("msg-titulo", titulo);
    this.texto("msg-sub", sub);
    $$('[data-v="msg-ponto"]').forEach(x => (x.className = `msg-ponto ${tipo}`));
    $$('[data-v="msg-icone"]').forEach(x => {
      x.className = `treinador-icone ${tipo}`;
      if (x.dataset.icone !== iconeNome) { x.innerHTML = ""; x.append(icone(iconeNome)); x.dataset.icone = iconeNome; }
    });
  },
  medidas(e) {
    // medidas ao vivo de cada articulação, conforme a posição da câmera
    const a = e.analise || {};
    const alerta = (a.alertas || []).join(" ").toLowerCase();
    const fmt = (v, suf = "°") => (v == null ? "–" : `${v}${suf}`);
    const peso = a.equilibrio == null ? "–" : Math.abs(a.equilibrio) < 0.3 ? "centro" : a.equilibrio > 0 ? "à frente" : "atrás";
    const itens = a.vista === "diagonal"
      ? [["Quadril", fmt(a.quadril), false], ["Tronco", fmt(a.tronco), alerta.includes("peito")],
         ["Câmera", "diagonal", false]]
      : a.vista === "frontal"
      ? [["Abertura joelhos", a.abertura != null ? `${Math.round(a.abertura * 100)}%` : "–", alerta.includes("joelhos para fora") || alerta.includes("ponta do pé")],
         ["Simetria", a.simetria != null ? `${a.simetria}°` : "–", alerta.includes("duas pernas")],
         ["Ombros", fmt(a.ombros), alerta.includes("ombros")],
         ["Base dos pés", a.base != null ? `${String(a.base).replace(".", ",")}×` : "–", false]]
      : [["Quadril", fmt(a.quadril), false],
         ["Tronco", fmt(a.tronco), alerta.includes("peito")],
         ["Peso no pé", peso, alerta.includes("meio do pé")],
         ["Calcanhar", a.calcanhar == null ? "–" : a.calcanhar < 3 ? "no chão" : `+${a.calcanhar}%`, alerta.includes("calcanhares")]];
    const chave = JSON.stringify(itens);
    if (chave === this._ultimasMedidas) return;
    this._ultimasMedidas = chave;
    for (const alvo of $$('[data-v="medidas"], [data-v="medidas-mini"]')) {
      alvo.innerHTML = "";
      for (const [nome, valor, erro] of itens)
        alvo.append(el("div", { class: erro ? "erro" : "" }, [el("span", { texto: nome }), el("strong", { texto: valor })]));
    }
  },
  render(e) {
    const livre = e.meta === 0;
    const a = e.analise;
    const reps = livre ? e.total : e.reps_na_serie;

    this.texto("reps", reps);
    this.texto("meta", livre ? "reps" : `/ ${e.meta}`);
    this.texto("meta-texto", livre ? "repetições" : `de ${e.meta}`);
    this.texto("status", e.pausado ? "Pausado" : e.video ? "Vídeo" : "Ao vivo");
    this.texto("serie", livre ? "Modo livre" : `Série ${e.serie} de ${e.series}`);
    this.texto("fps", e.fps ? `${Math.round(e.fps)} fps` : "– fps");
    // abaixo de ~12 quadros por segundo a análise perde parte do movimento: avisa em amarelo
    $$('[data-v="fps"]').forEach(x => x.classList.toggle("lento", !!e.fps && e.fps < 12 && !e.pausado));
    $$(".ilha, .hud-serie").forEach(x => x.classList.toggle("pausado", e.pausado));
    this.texto("acerto", e.percentual != null ? `${e.percentual}%` : "–");
    this.texto("nota", e.nota_media ?? "–");
    $$('[data-v="fase"]').forEach(x => { x.textContent = e.pausado ? "Pausado" : FASES[e.fase]; x.className = `pilula ${e.pausado ? "" : e.fase}`; });
    const circ = 2 * Math.PI * 84;
    $$('[data-v="anel"]').forEach(x => {
      x.style.strokeDasharray = circ;
      x.style.strokeDashoffset = livre ? (e.total ? 0 : circ) : circ * (1 - Math.min(e.reps_na_serie / e.meta, 1));
    });

    // profundidade (barra horizontal no modo normal, vertical na tela cheia)
    const frac = a?.joelho != null ? Math.min(Math.max((170 - a.joelho) / 80, 0), 1) : 0;
    $("#ao-vivo").style.setProperty("--prof", frac);
    $$('[data-v="prof-barra"]').forEach(x => x.classList.toggle("alvo", a?.joelho != null && a.joelho <= 100));
    this.texto("joelho", a?.joelho != null ? `${a.joelho}°` : "–");
    this.medidas(e);

    // contagem regressiva e descanso
    const sobre = $("#sobreposicao");
    if (e.fase === "preparando" && a?.pessoa) {
      sobre.hidden = false;
      $("#sobre-titulo").textContent = livre || e.serie === 1 ? "Prepare-se" : `Série ${e.serie}`;
      $("#sobre-numero").textContent = Math.ceil(e.restante_s) || "Já";
      $("#sobre-texto").textContent = "Começando em...";
      $("#botao-pular").hidden = true;
    } else if (e.fase === "descanso") {
      sobre.hidden = false;
      $("#sobre-titulo").textContent = "Descanso";
      $("#sobre-numero").textContent = Math.ceil(e.restante_s);
      $("#sobre-texto").textContent = `A seguir: série ${e.serie + 1} de ${e.series}`;
      $("#botao-pular").hidden = false;
    } else {
      sobre.hidden = true;
    }

    // mensagem do treinador
    if (e.pausado) this.mensagem("info", "relogio", "Pausado", "Continue quando estiver pronto.");
    else if (e.fase === "descanso") this.mensagem("info", "relogio", "Descanso", "Respire e prepare-se para a próxima série.");
    else if (!a?.pessoa) this.mensagem("aviso", "pessoa", "Apareça de corpo inteiro", "A câmera precisa ver da cabeça aos pés.");
    else if (e.fase === "preparando") this.mensagem("info", "pessoa", "Prepare-se", "Fique em pé, de lado ou de frente para a câmera.");
    else if (a.alertas?.length) this.mensagem("erro", "alerta", a.alertas[0], "Corrija nesta repetição.");
    else if (a.movimento === "Descendo")
      a.joelho > 100 ? this.mensagem("info", "seta-baixo", "Desça mais", `Joelho em ${a.joelho}°. O alvo é 100° ou menos.`)
                     : this.mensagem("ok", "check", "Boa profundidade!", "Agora suba empurrando o chão.");
    else if (a.movimento === "Subindo") this.mensagem("ok", "seta-cima", "Suba controlando", "Empurre o chão com o pé inteiro.");
    else if (e.ultima && e.ultima.avisos?.length)
      this.mensagem("aviso", "alerta", "Sinal de fadiga", "A técnica está caindo. Se precisar, encerre a série.");
    else if (e.ultima)
      e.ultima.correta ? this.mensagem("ok", "check", `Repetição ${reps} correta · nota ${e.ultima.nota}`, "Continue assim.")
                       : this.mensagem("erro", "alerta", `Repetição ${reps}: ${e.ultima.erros[0].toLowerCase()}`, `Nota ${e.ultima.nota}. ${DICAS_TELA[e.ultima.erros[0]] || "Ajuste na próxima."}`);
    else if (a.vista === "diagonal")
      this.mensagem("aviso", "camera", "Câmera na diagonal", "Dá para treinar, mas pés, joelhos e ombros só são avaliados de lado ou de frente.");
    else this.mensagem("info", "seta-baixo", "Pode começar", "Cada repetição é contada na subida.");

    // última repetição: nota de cada articulação com o valor medido
    if (e.ultima && e.reps.length !== this.repsMostradas) {
      const [cls] = classeNota(e.ultima.nota);
      $$('[data-v="ultima-nota"]').forEach(x => { x.textContent = e.ultima.nota; x.className = `nota-badge ${cls}`; });
      for (const crit of $$('[data-v="criterios"]')) {
        crit.innerHTML = "";
        for (const [k, v] of Object.entries(e.ultima.notas)) {
          const cor = v >= 85 ? "var(--verde)" : v >= 70 ? "#7ac943" : v >= 50 ? "var(--laranja)" : "var(--vermelho)";
          crit.append(el("div", { class: "criterio" }, [
            el("span", { class: "nome-c" }, [document.createTextNode(NOMES_CRITERIO[k] || k), e.ultima.medidas?.[k] ? el("small", { texto: e.ultima.medidas[k] }) : null]),
            el("div", { class: "barra-c" }, el("i", { style: `width:${v}%;background:${cor}` })),
            el("b", { texto: v }),
          ]));
        }
        if (e.ultima.erros.length) crit.append(el("div", { class: "erros-ultima", texto: e.ultima.erros.join(" · ") }));
      }
    }

    // nova repetição: o número muda de cor por um instante
    if (e.reps.length > this.repsMostradas && e.ultima) {
      const cls = e.ultima.correta ? "ok" : "erro";
      $$('[data-v="contador"]').forEach(c => (c.className = `contador ${cls}`));
      $$('.anel-centro [data-v="reps"]').forEach(c => (c.className = cls));
      clearTimeout(this.corTimer);
      this.corTimer = setTimeout(() => {
        $$('[data-v="contador"]').forEach(c => (c.className = "contador"));
        $$('.anel-centro [data-v="reps"]').forEach(c => (c.className = ""));
      }, 1200);
    }
    if (e.reps.length < this.repsMostradas) { $$('[data-v="trilha"]').forEach(t => (t.innerHTML = "")); this.repsMostradas = 0; }
    for (const trilha of $$('[data-v="trilha"]')) {
      for (let i = this.repsMostradas; i < e.reps.length; i++) {
        const r = e.reps[i];
        if (!livre && i > 0 && e.reps[i - 1].serie !== r.serie) trilha.append(el("span", { class: "divisor-serie" }));
        trilha.append(el("div", { class: `rep-ponto ${r.correta ? "ok" : "erro"} nova`, title: `Série ${r.serie} · nota ${r.nota}`, texto: r.nota }));
      }
      trilha.scrollLeft = trilha.scrollWidth;
    }
    this.repsMostradas = e.reps.length;
  },
};

const TelaCheia = {
  entrar() {
    try { document.documentElement.requestFullscreen?.().catch(() => {}); } catch { /* sem suporte */ }
  },
  sair() {
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  },
};

/* ---------- resumo ---------- */
Telas.resumo = async id => {
  let s;
  try { s = await api(`/api/historico/${id}`); } catch (e) { toast(e.message); location.hash = "#/historico"; return; }
  $("#resumo-data").textContent = formatarData(s.data) + (s.fonte && !/^\d+$/.test(s.fonte) ? ` · ${s.fonte}` : " · Webcam");
  cartaoAneis($("#resumo-aneis"), s);
  const tiles = $("#tiles-resumo");
  tiles.innerHTML = "";
  const erros = Object.entries(s.erros).sort((a, b) => b[1] - a[1]);
  tiles.append(
    tile("Repetições corretas", `${s.corretas}<small>/${s.total}</small>`, `${s.total - s.corretas} com erro`),
    tile("Melhor nota", s.melhor_nota, `em ${s.series_feitas} ${s.series_feitas === 1 ? "série" : "séries"}`),
    tile("Erro mais comum", erros.length ? `${erros[0][1]}<small>×</small>` : "0", erros.length ? erros[0][0] : "nenhum erro de técnica"),
    tile("Duração", formatarDuracao(s.duracao_s), "tempo em execução"),
  );
  const dica = $("#resumo-dica");
  dica.innerHTML = "";
  const cor = Object.entries(DICA_ICONE).find(([k]) => s.dica.startsWith(k))?.[1] || "verde";
  dica.append(el("span", { class: `icone-redondo ${cor}` }, icone("lampada")),
    el("div", {}, [el("h3", { texto: "Para o próximo treino" }), el("p", { class: "sutil", texto: s.dica })]));
  const fadiga = $("#resumo-fadiga");
  fadiga.hidden = !s.series_com_fadiga?.length;
  if (s.series_com_fadiga?.length) {
    fadiga.innerHTML = "";
    const lista = s.series_com_fadiga.map(n => `série ${n}`).join(", ").replace(/, ([^,]*)$/, " e $1");
    fadiga.append(el("span", { class: "icone-redondo laranja" }, icone("alerta")),
      el("div", {}, [el("h3", { texto: "Sinal de fadiga" }),
        el("p", { class: "sutil", texto: `A nota ou a profundidade caíram no fim da ${lista}. Descanse mais entre as séries ou faça menos repetições: técnica ruim por cansaço é uma causa comum de lesão.` })]));
  }
  graficoNotas($("#grafico-notas"), s.repeticoes);
  graficoErros($("#grafico-erros"), s.erros, s.total);
  const tabela = $("#tabela-reps");
  tabela.innerHTML = "<thead><tr><th>Série</th><th>Rep.</th><th>Nota</th><th>Joelho mín.</th><th>Descida</th><th>Resultado</th><th></th></tr></thead>";
  const corpo = el("tbody");
  const contagem = {};
  for (const r of s.repeticoes) {
    contagem[r.serie] = (contagem[r.serie] || 0) + 1;
    const resultado = r.correta ? "Correta" : r.erros.join(", ");
    const linha = el("tr", { class: "linha-rep" }, [
      el("td", { texto: r.serie }), el("td", { texto: contagem[r.serie] }),
      el("td", { class: `nota-cel ${classeNota(r.nota)[0]}`, texto: r.nota }),
      el("td", { texto: `${Math.round(r.angulo_minimo_joelho)}°` }),
      el("td", { texto: `${(r.descida_s ?? r.duracao_s).toFixed(1).replace(".", ",")} s` }),
      el("td", {}, [el("span", { class: `estado ${r.correta ? "ok" : "erro"}`, texto: resultado }),
        r.avisos?.length ? el("span", { class: "aviso-tag", texto: "fadiga" }) : null]),
      el("td", { class: "seta-detalhe" }, icone("chevron")),
    ]);
    // detalhe: nota e valor medido de cada articulação
    const detalhe = el("tr", { class: "detalhe-rep", hidden: "" }, el("td", { colspan: 7 },
      el("div", { class: "grade-criterios" }, Object.entries(r.notas || {}).map(([k, v]) => {
        const cor = v >= 85 ? "var(--verde)" : v >= 70 ? "#7ac943" : v >= 50 ? "var(--laranja)" : "var(--vermelho)";
        return el("div", { class: "criterio-detalhe" }, [
          el("div", { class: "topo-c" }, [el("span", { texto: NOMES_CRITERIO[k] || k }), el("b", { texto: v })]),
          el("div", { class: "barra-c" }, el("i", { style: `width:${v}%;background:${cor}` })),
          el("small", { texto: r.medidas?.[k] || "" }),
        ]);
      }))));
    linha.addEventListener("click", () => { detalhe.hidden = !detalhe.hidden; linha.classList.toggle("aberta", !detalhe.hidden); });
    corpo.append(linha, detalhe);
  }
  tabela.append(corpo);
};

/* ---------- histórico ---------- */
Telas.historico = async () => {
  const sessoes = await api("/api/historico").catch(() => []);
  graficoEvolucao($("#grafico-evolucao"), sessoes);
  const lista = $("#lista-historico");
  lista.innerHTML = "";
  if (!sessoes.length) lista.append(el("div", { class: "vazio", texto: "Nenhum treino salvo ainda." }));
  for (const s of [...sessoes].reverse()) {
    const item = itemSessao(s);
    const apagar = el("button", { class: "botao-redondo", title: "Apagar treino", "aria-label": "Apagar treino" }, icone("lixo"));
    apagar.addEventListener("click", async evt => {
      evt.preventDefault();
      evt.stopPropagation();
      if (!confirm("Apagar este treino do histórico?")) return;
      await api(`/api/historico/${s.id}`, { method: "DELETE" });
      Telas.historico();
    });
    item.insertBefore(apagar, item.lastChild);
    lista.append(item);
  }
};

/* ============================== rotas ============================== */
function navegar(evento) {
  const [, rota = "inicio", param] = location.hash.split("/");
  const id = { inicio: "inicio", treinar: "treinar", "ao-vivo": "ao-vivo", resumo: "resumo", guia: "guia", historico: "historico" }[rota] || "inicio";
  const redesenho = evento?.type === "resize";
  if (!redesenho) $$(".tela").forEach(t => t.classList.toggle("visivel", t.id === `tela-${id}`));
  const menu = id === "ao-vivo" ? "treinar" : id === "resumo" ? "historico" : id;
  $$(".abas-nav a").forEach(a => a.classList.toggle("ativo", a.dataset.rota === menu));
  if (id !== "ao-vivo" && AoVivo.timer) AoVivo.parar();
  if (id === "ao-vivo" && !redesenho) AoVivo.iniciar();
  if (id === "inicio") Telas.inicio();
  if (id === "historico") Telas.historico();
  if (id === "resumo") Telas.resumo(param);
  if (!redesenho) window.scrollTo(0, 0);
}

document.addEventListener("DOMContentLoaded", () => {
  Tema.init();
  Voz.init();
  Config.init();
  AoVivo.init();
  animarBoneco($("#hero-boneco"), ang => { $("#vitrine-angulo").textContent = `${Math.round(ang)}°`; }, { base: { x: 120, y: 262 } });
  animarBoneco($("#boneco-guia"), ang => {
    $("#guia-angulo").textContent = `${Math.round(ang)}°`;
    $("#guia-fase").textContent = ang > 168 ? "Em pé" : ang < 92 ? "Coxa paralela" : "Em movimento";
  }, { angulo: true, guia: true });
  window.addEventListener("hashchange", navegar);
  let espera;
  window.addEventListener("resize", evt => {
    clearTimeout(espera);
    espera = setTimeout(() => { if (!location.hash.startsWith("#/ao-vivo")) navegar(evt); }, 250);
  });
  navegar();
});
