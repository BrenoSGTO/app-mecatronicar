/**
 * MecatroniCar v3 - tv.js
 * Painel de TV do pátio (rota /tv).
 *
 * Princípios:
 *  - Sempre cabe na tela: todos os carros ficam numa grade só (sem colunas por status),
 *    em cards horizontais de proporção fixa. O JS escolhe o nº de colunas que deixa os
 *    cards maiores (sem rolagem em 1280x720, 1920x1080 ou 3840x2160).
 *  - Atualiza só o que mudou: cada carro é um nó DOM com assinatura; o polling compara
 *    por id e só mexe nos cards novos/alterados/removidos.
 *  - Rodando 12 h+: um único timer de polling (setTimeout encadeado), pausa com a aba
 *    oculta, um único AudioContext, nenhum listener acumulado, Map limpo a cada remoção.
 *  - Resiliente: se o servidor cair, mantém o último estado na tela, mostra
 *    "Reconectando..." discreto e tenta de novo com recuo progressivo.
 */
(function () {
    'use strict';

    // ------------------------------------------------------------------
    // Configuração
    // ------------------------------------------------------------------
    var POLL_MS = 5000;            // pátio
    var AGENDA_MS = 30000;         // agenda do dia
    var BACKOFF_MAX_MS = 30000;
    var FETCH_TIMEOUT_MS = 8000;
    var STALE_AFTER_MS = 24 * 3600 * 1000; // tempo no status destacado em âmbar

    // Card único, sempre horizontal e sempre na mesma proporção, medido em "u"
    // (1u = font-size do card). O layout só escolhe quantas colunas e o tamanho de "u".
    var CARD_W = 17.6;
    var CARD_H = 10.8;

    // Ordem do fluxo da oficina: os cards seguem esta ordem na grade.
    var PHASES = [
        // label: legenda e avisos; short: pílula do card (cabe ao lado do tempo no status)
        { key: 'diagnostico', label: 'Em diagnóstico',        short: 'Diagnóstico',       re: /diagn/ },
        { key: 'orcamento',   label: 'Esperando orçamento',   short: 'Orçamento',         re: /orcam/ },
        { key: 'aprovacao',   label: 'Esperando aprovação',   short: 'Aprovação',         re: /aprov/ },
        { key: 'pecas',       label: 'Esperando peças',       short: 'Esperando peças',   re: /peca/ },
        { key: 'execucao',    label: 'Em execução',           short: 'Em execução',       re: /execu/ },
        { key: 'pronto',      label: 'Pronto p/ retirada',    short: 'Pronto p/ retirada', re: /client|retir|pronto/ },
        { key: 'terceiro',    label: 'Retirada por terceiro', short: 'Retira terceiro',   re: /terceir/ }
    ];
    var PHASE_BY_KEY = {};
    var PHASE_INDEX = {};
    PHASES.forEach(function (p, i) { PHASE_BY_KEY[p.key] = p; PHASE_INDEX[p.key] = i; });

    var PHASE_ICON = {
        diagnostico: 'search', orcamento: 'file-text', aprovacao: 'hourglass',
        pecas: 'package', execucao: 'wrench', pronto: 'circle-check', terceiro: 'key-round'
    };

    // ------------------------------------------------------------------
    // Utilidades
    // ------------------------------------------------------------------
    function $(id) { return document.getElementById(id); }

    function norm(s) {
        return String(s == null ? '' : s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
    }

    function esc(text) {
        if (text == null || text === '') return '';
        return String(text)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function icon(name, cls) {
        return (window.TVIcons && window.TVIcons.svg(name, cls)) || '';
    }

    function resolvePhase(status) {
        var s = norm(status);
        // "terceiro" precisa vir antes: "Liberado p/ Retirada por Terceiro" também contém "retir"
        if (s.indexOf('terceir') >= 0) return PHASE_BY_KEY.terceiro;
        for (var i = 0; i < PHASES.length; i++) {
            if (PHASES[i].re.test(s)) return PHASES[i];
        }
        return PHASE_BY_KEY.diagnostico;
    }

    function prefersReducedMotion() {
        return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    }

    function pad2(n) { return (n < 10 ? '0' : '') + n; }

    // "YYYY-MM-DD HH:MM:SS" (horário naive do servidor) -> ms, lido como horário local.
    // Servidor e TV usam o mesmo critério, então a diferença entre eles é consistente.
    function parseNaive(str) {
        if (!str) return NaN;
        var m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(String(str));
        if (!m) return NaN;
        return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0)).getTime();
    }

    function isoDate(ms) {
        var d = new Date(ms);
        return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
    }

    function fmtElapsed(ms) {
        if (!(ms >= 0)) return '';
        var min = Math.floor(ms / 60000);
        if (min < 1) return 'agora';
        if (min < 60) return min + ' min';
        var h = Math.floor(min / 60);
        if (h < 24) return h + 'h ' + pad2(min % 60) + 'min';
        var d = Math.floor(h / 24);
        return d + (d === 1 ? ' dia ' : ' dias ') + (h % 24) + 'h';
    }

    // Placa: antiga LLL-NNNN com hífen; Mercosul LLLNLNN sem hífen.
    function fmtPlate(raw) {
        var clean = String(raw || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
        if (!clean) return 'SEM PLACA';
        if (/^[A-Z]{3}[0-9]{4}$/.test(clean)) return clean.slice(0, 3) + '-' + clean.slice(3);
        return clean;
    }

    // ------------------------------------------------------------------
    // Estado
    // ------------------------------------------------------------------
    var state = {
        cars: new Map(),          // id -> { vm, raw, el, flashT }
        offsetMs: 0,              // relógio do servidor - relógio da TV
        loaded: false,
        conn: 'connecting',
        failCount: 0,
        inFlight: false,
        pollTimer: null,
        lastAgendaAt: 0,
        agenda: [],
        agendaSig: '',
        soundOn: false,
        layoutQueued: false,
        audioCtx: null,
        toastT: null,
        sinceT: null,
        brandCache: new Map()
    };

    var el = {
        app: $('tv-app'),
        board: $('tv-board'),
        grid: $('tv-grid'),
        legend: $('tv-legend'),
        empty: $('tv-empty-state'),
        total: $('tv-total-cars'),
        clockTime: $('tv-clock-time'),
        clockDate: $('tv-clock-date'),
        conn: $('tv-conn'),
        connText: $('tv-conn-status'),
        lastSync: $('tv-last-sync'),
        lanUrl: $('tv-lan-url'),
        agenda: $('tv-agenda'),
        agendaList: $('tv-agenda-list'),
        agendaCount: $('tv-agenda-count'),
        agendaMore: $('tv-agenda-more'),
        toast: $('tv-toast')
    };

    function serverNow() { return Date.now() + state.offsetMs; }

    // ------------------------------------------------------------------
    // Relógio (usa a hora do servidor, não a da TV, que costuma estar errada)
    // ------------------------------------------------------------------
    var clockHM = document.createTextNode('00:00');
    var clockSec = document.createElement('span');
    clockSec.className = 'tv-clock-sec';
    clockSec.textContent = ':00';
    el.clockTime.textContent = '';
    el.clockTime.appendChild(clockHM);
    el.clockTime.appendChild(clockSec);
    var lastHM = '', lastSec = '', lastDay = '', lastAgendaMinute = -1;

    function tickClock() {
        var now = new Date(serverNow());
        var hm = pad2(now.getHours()) + ':' + pad2(now.getMinutes());
        var sec = ':' + pad2(now.getSeconds());
        if (hm !== lastHM) { clockHM.nodeValue = hm; lastHM = hm; }
        if (sec !== lastSec) { clockSec.textContent = sec; lastSec = sec; }
        var day = isoDate(now.getTime());
        if (day !== lastDay) {
            lastDay = day;
            var txt = now.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });
            el.clockDate.textContent = txt.charAt(0).toUpperCase() + txt.slice(1);
        }
        var minute = now.getMinutes();
        if (minute !== lastAgendaMinute) { // "próximo" e "atrasado" mudam com o passar dos minutos
            lastAgendaMinute = minute;
            renderAgenda();
        }
    }

    // ------------------------------------------------------------------
    // Toast, conexão e som
    // ------------------------------------------------------------------
    function showToast(msg) {
        if (!el.toast) return;
        el.toast.textContent = msg;
        el.toast.hidden = false;
        clearTimeout(state.toastT);
        state.toastT = setTimeout(function () { el.toast.hidden = true; }, 4000);
    }

    function setConn(next) {
        if (state.conn === next && next !== 'ok') return;
        state.conn = next;
        el.conn.setAttribute('data-state', next);
        if (next === 'ok') {
            el.connText.textContent = 'Ao vivo';
        } else if (next === 'retry') {
            el.connText.textContent = 'Reconectando...';
        } else {
            el.connText.textContent = 'Conectando...';
        }
        if (next === 'ok') {
            var d = new Date(serverNow());
            el.lastSync.textContent = pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
        }
    }

    function getAudio() {
        if (state.audioCtx) return state.audioCtx;
        var Ctor = window.AudioContext || window.webkitAudioContext;
        if (!Ctor) return null;
        try { state.audioCtx = new Ctor(); } catch (e) { state.audioCtx = null; }
        return state.audioCtx;
    }

    function chime() {
        if (!state.soundOn) return;
        var ctx = getAudio();
        if (!ctx) return;
        try {
            if (ctx.state === 'suspended' && ctx.resume) ctx.resume();
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(587.33, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15);
            gain.gain.setValueAtTime(0.25, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.onended = function () { try { osc.disconnect(); gain.disconnect(); } catch (e) { /* ok */ } };
            osc.start();
            osc.stop(ctx.currentTime + 0.4);
        } catch (e) { /* áudio bloqueado pelo navegador */ }
    }

    // ------------------------------------------------------------------
    // Rede
    // ------------------------------------------------------------------
    function fetchJson(url, opts) {
        var ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
        var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, FETCH_TIMEOUT_MS) : null;
        var init = opts || {};
        init.cache = 'no-store';
        if (ctrl) init.signal = ctrl.signal;
        return fetch(url, init).then(function (res) {
            if (timer) clearTimeout(timer);
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return res.json();
        }, function (err) {
            if (timer) clearTimeout(timer);
            throw err;
        });
    }

    // ------------------------------------------------------------------
    // Modelo de visualização do carro
    // ------------------------------------------------------------------
    function stripColor(model, color) {
        var m = String(model || '').trim();
        if (!m) return '';
        if (color) {
            var suffix = ' - ' + String(color).trim();
            if (m.toLowerCase().slice(-suffix.length) === suffix.toLowerCase()) m = m.slice(0, -suffix.length).trim();
        }
        return m;
    }

    function toViewModel(car) {
        var statusText = car.status_display || car.status || '';
        var phase = resolvePhase(statusText);
        var model = stripColor(car.car_model, car.car_color) || 'Veículo';
        var vm = {
            id: car.id,
            phase: phase.key,
            plate: fmtPlate(car.plate_display || car.plate),
            model: model,
            client: String(car.client_name || '').trim(),
            notes: String(car.notes || '').trim(),
            box: String(car.box_mecanico || car.mechanic_name || '').trim(),
            authName: String(car.authorized_name || car.third_party_name || '').trim(),
            authDoc: String(car.authorized_doc || car.third_party_doc || '').trim(),
            updatedAt: car.updated_at || car.updated_time || '',
            since: parseNaive(car.updated_at || car.updated_time)
        };
        vm.sig = [vm.phase, vm.plate, vm.model, vm.client, vm.notes, vm.box, vm.authName, vm.authDoc, vm.updatedAt].join('␟');
        return vm;
    }

    function identify(model) {
        var key = model || '';
        if (state.brandCache.has(key)) return state.brandCache.get(key);
        var info = { brand: 'generic', logo: '', silhouette: '' };
        try {
            if (window.CarCatalog && window.CarCatalog.identifyCar) {
                var r = window.CarCatalog.identifyCar(model);
                info.brand = r.brandKey || 'generic';
                info.logo = r.brandLogo ? 'brands/' + String(r.brandLogo).split('/').pop() : '';
                info.silhouette = r.silhouette ? 'models/' + String(r.silhouette).split('/').pop() : '';
            }
        } catch (e) { /* catálogo indisponível */ }
        if (state.brandCache.size > 400) state.brandCache.clear();
        state.brandCache.set(key, info);
        return info;
    }

    function plateHtml(text) {
        return '<div class="mercosul-plate" title="Placa ' + esc(text) + '">' +
            '<div class="mercosul-top-bar"><span>BRASIL</span>' +
            '<svg class="mercosul-flag" viewBox="0 0 20 14" aria-hidden="true"><rect width="20" height="14" rx="1.5" fill="#009b3a"/>' +
            '<polygon points="10,1.8 18,7 10,12.2 2,7" fill="#fedf00"/><circle cx="10" cy="7" r="3" fill="#002776"/></svg></div>' +
            '<div class="mercosul-body-area"><span class="mercosul-number">' + esc(text) + '</span></div></div>';
    }

    function brandHtml(info, model) {
        if (info.brand === 'generic' || !info.logo) {
            return '<span class="brand-logo-container">' + icon('car') + '</span>';
        }
        return '<span class="brand-logo-container has-img"><img class="brand-logo-img" src="' + esc(info.logo) +
            '" alt="" onerror="this.parentNode.innerHTML=\'\'"></span>';
    }

    function cardInner(vm) {
        var info = identify(vm.model);
        var phase = PHASE_BY_KEY[vm.phase];
        var foot = '';
        if (vm.phase === 'terceiro') {
            foot = '<div class="tv-pickup">' + icon('key-round') +
                '<div class="tv-pickup-text"><span class="tv-pickup-label">Retira' +
                (vm.authDoc ? '<span class="tv-pickup-doc"> · Doc. ' + esc(vm.authDoc) + '</span>' : '') + '</span>' +
                '<span class="tv-pickup-name">' + esc(vm.authName || 'Terceiro autorizado') + '</span></div>' +
                '</div>';
        } else if (vm.notes || vm.box) {
            foot = '<div class="tv-card-notes">' +
                (vm.box ? '<span class="tv-card-box">' + esc(vm.box) + '</span>' : '') +
                (vm.notes ? '<span class="tv-card-notes-text" title="' + esc(vm.notes) + '">' + esc(vm.notes) + '</span>' : '') +
                '</div>';
        }
        return '<i class="tv-card-bar"></i>' +
            (info.silhouette ? '<div class="car-silhouette-container"><img class="car-silhouette-img" src="' + esc(info.silhouette) +
                '" alt="" loading="lazy" onerror="this.parentNode.style.display=\'none\'"></div>' : '') +
            '<div class="tv-card-status"><span class="tv-status-pill">' + icon(PHASE_ICON[vm.phase]) +
            '<span title="' + esc(phase.label) + '">' + esc(phase.short) + '</span></span>' +
            '<span class="tv-since" data-since>' + icon('clock') + '<span></span></span></div>' +
            '<div class="tv-card-top">' + brandHtml(info, vm.model) +
            '<div class="tv-card-model" title="' + esc(vm.model) + '">' + esc(vm.model) + '</div></div>' +
            '<div class="tv-card-mid">' + plateHtml(vm.plate) +
            '<span class="tv-who">' + icon('user') + '<span>' + esc(vm.client || 'Cliente da oficina') + '</span></span></div>' +
            foot;
    }

    function paintCard(rec) {
        var vm = rec.vm;
        rec.el.setAttribute('data-phase', vm.phase);
        rec.el.setAttribute('aria-label', vm.plate + ', ' + vm.model + ', ' + PHASE_BY_KEY[vm.phase].label);
        rec.el.innerHTML = cardInner(vm);
        rec.sinceEl = rec.el.querySelector('[data-since] span');
        rec.sinceText = '';
        updateSinceFor(rec);
    }

    function updateSinceFor(rec) {
        if (!rec.sinceEl) return;
        var elapsed = isNaN(rec.vm.since) ? NaN : serverNow() - rec.vm.since;
        var text = fmtElapsed(elapsed);
        if (text !== rec.sinceText) {
            rec.sinceEl.textContent = text;
            rec.sinceText = text;
            var wrap = rec.sinceEl.parentNode;
            if (elapsed >= STALE_AFTER_MS) wrap.classList.add('is-stale'); else wrap.classList.remove('is-stale');
            wrap.hidden = !text;
        }
    }

    function updateAllSince() {
        state.cars.forEach(updateSinceFor);
    }

    function createCardEl() {
        var card = document.createElement('article');
        card.className = 'tv-card';
        card.tabIndex = 0;
        card.setAttribute('role', 'button');
        return card;
    }

    // ------------------------------------------------------------------
    // Reconciliação (diff por id) + animação FLIP
    // ------------------------------------------------------------------
    function applyPatio(data) {
        if (data.server_time) {
            var s = parseNaive(data.server_time);
            if (!isNaN(s)) state.offsetMs = s - Date.now();
        }
        el.lanUrl.textContent = data.tv_url || (location.origin + '/tv');

        var list = Array.isArray(data.active_cars) ? data.active_cars : (data.cars || []).filter(function (c) {
            return norm(c.status_display || c.status).indexOf('entregue') < 0;
        });

        var incoming = new Map();
        list.forEach(function (c) { if (c && c.id != null) incoming.set(c.id, c); });

        var added = [], changed = [], removed = [];
        incoming.forEach(function (raw, id) {
            var rec = state.cars.get(id);
            var vm = toViewModel(raw);
            if (!rec) added.push({ vm: vm, raw: raw });
            else if (rec.vm.sig !== vm.sig) changed.push({ rec: rec, vm: vm, raw: raw });
            else rec.raw = raw;
        });
        state.cars.forEach(function (rec, id) { if (!incoming.has(id)) removed.push(rec); });

        var firstLoad = !state.loaded;
        state.loaded = true;

        if (!added.length && !changed.length && !removed.length && !firstLoad) {
            updateAllSince();
            return;
        }

        var animate = !prefersReducedMotion() && !firstLoad && typeof Element.prototype.animate === 'function';

        // 1) posições "antes"
        var first = new Map();
        if (animate) {
            state.cars.forEach(function (rec, id) { first.set(id, rec.el.getBoundingClientRect()); });
        }

        // 2) aplica mudanças no modelo e no DOM
        var movedRecs = [];
        removed.forEach(function (rec) {
            var rect = first.get(rec.vm.id);
            leave(rec, animate ? rect : null);
            state.cars.delete(rec.vm.id);
        });
        var statusEvents = [];
        changed.forEach(function (c) {
            var phaseChanged = c.rec.vm.phase !== c.vm.phase;
            c.rec.vm = c.vm;
            c.rec.raw = c.raw;
            paintCard(c.rec);
            if (phaseChanged) { movedRecs.push(c.rec); statusEvents.push(c.vm); }
        });
        var addedRecs = [];
        added.forEach(function (a) {
            var rec = { vm: a.vm, raw: a.raw, el: createCardEl(), flashT: null, sinceEl: null, sinceText: '' };
            rec.el.setAttribute('data-id', a.vm.id);
            paintCard(rec);
            state.cars.set(a.vm.id, rec);
            addedRecs.push(rec);
        });

        place();
        relayout();

        // 3) FLIP: anima da posição antiga até a nova
        if (animate) {
            state.cars.forEach(function (rec, id) {
                var from = first.get(id);
                if (!from) return;
                var to = rec.el.getBoundingClientRect();
                var dx = from.left - to.left, dy = from.top - to.top;
                if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
                var moved = movedRecs.indexOf(rec) >= 0;
                rec.el.classList.add('is-moving');
                var anim = rec.el.animate(
                    [{ transform: 'translate(' + dx + 'px,' + dy + 'px)' }, { transform: 'none' }],
                    { duration: moved ? 650 : 380, easing: 'cubic-bezier(.2,.7,.2,1)' }
                );
                anim.onfinish = anim.oncancel = function () { rec.el.classList.remove('is-moving'); };
            });
            addedRecs.forEach(function (rec) {
                rec.el.animate(
                    [{ opacity: 0, transform: 'translateY(.8em) scale(.97)' }, { opacity: 1, transform: 'none' }],
                    { duration: 420, easing: 'cubic-bezier(.2,.7,.2,1)' }
                );
            });
        }

        // 4) destaque + aviso de mudança de status
        movedRecs.forEach(flash);
        if (!firstLoad) {
            if (statusEvents.length) {
                chime();
                var v = statusEvents[0];
                var label = PHASE_BY_KEY[v.phase].label;
                showToast(statusEvents.length === 1
                    ? v.plate + ' agora está em: ' + label
                    : statusEvents.length + ' veículos mudaram de status');
            } else if (addedRecs.length) {
                showToast(addedRecs.length === 1 ? addedRecs[0].vm.plate + ' entrou no pátio' : addedRecs.length + ' veículos entraram no pátio');
            }
        }

        updateAllSince();
    }

    function flash(rec) {
        var node = rec.el;
        node.classList.remove('is-changed');
        void node.offsetWidth; // reinicia a animação
        node.classList.add('is-changed');
        clearTimeout(rec.flashT);
        rec.flashT = setTimeout(function () { node.classList.remove('is-changed'); }, 3400);
    }

    function leave(rec, rect) {
        clearTimeout(rec.flashT);
        var node = rec.el;
        var parent = node.parentNode;
        if (!rect || !parent) {
            if (parent) parent.removeChild(node);
            return;
        }
        node.classList.add('is-leaving');
        node.style.left = rect.left + 'px';
        node.style.top = rect.top + 'px';
        node.style.width = rect.width + 'px';
        node.style.height = rect.height + 'px';
        node.style.fontSize = getComputedStyle(parent).fontSize;
        document.body.appendChild(node);
        var done = function () { if (node.parentNode) node.parentNode.removeChild(node); };
        var anim = node.animate(
            [{ opacity: 1, transform: 'scale(1)' }, { opacity: 0, transform: 'scale(.94)' }],
            { duration: 320, easing: 'ease-out', fill: 'forwards' }
        );
        anim.onfinish = done;
        setTimeout(done, 600); // garantia caso onfinish não dispare
    }

    function sortRecs(list) {
        return list.sort(function (a, b) {
            var pa = PHASE_INDEX[a.vm.phase], pb = PHASE_INDEX[b.vm.phase];
            if (pa !== pb) return pa - pb;              // ordem do fluxo da oficina
            var sa = isNaN(a.vm.since) ? Infinity : a.vm.since;
            var sb = isNaN(b.vm.since) ? Infinity : b.vm.since;
            if (sa !== sb) return sa - sb;             // quem espera há mais tempo vem antes
            return (a.vm.id || 0) - (b.vm.id || 0);
        });
    }

    var legendSig = '';

    function place() {
        var list = [];
        var counts = {};
        state.cars.forEach(function (rec) {
            list.push(rec);
            counts[rec.vm.phase] = (counts[rec.vm.phase] || 0) + 1;
        });
        sortRecs(list);
        for (var i = 0; i < list.length; i++) {
            if (el.grid.children[i] !== list[i].el) el.grid.insertBefore(list[i].el, el.grid.children[i] || null);
        }
        el.total.textContent = state.cars.size;

        var sig = PHASES.map(function (p) { return counts[p.key] || 0; }).join(',');
        if (sig !== legendSig) {
            legendSig = sig;
            el.legend.innerHTML = PHASES.filter(function (p) { return counts[p.key]; }).map(function (p) {
                return '<span class="tv-legend-item" data-phase="' + p.key + '">' + icon(PHASE_ICON[p.key]) +
                    '<span class="tv-legend-label">' + esc(p.label) + '</span><b>' + counts[p.key] + '</b></span>';
            }).join('');
        }
    }

    // ------------------------------------------------------------------
    // Layout: calcula colunas, grade e tamanho de fonte de cada coluna
    // ------------------------------------------------------------------
    function queueLayout() {
        if (state.layoutQueued) return;
        state.layoutQueued = true;
        requestAnimationFrame(function () {
            state.layoutQueued = false;
            relayout();
            renderAgenda(true);
        });
    }

    function px(v) { return parseFloat(v) || 0; }

    function relayout() {
        var total = state.cars.size;
        if (!state.loaded) {
            el.board.setAttribute('data-empty', 'loading');
            el.empty.hidden = true;
            return;
        }
        if (total === 0) {
            el.board.setAttribute('data-empty', 'true');
            el.empty.hidden = false;
            return;
        }
        el.board.setAttribute('data-empty', 'false');
        el.empty.hidden = true;

        // Todos os cards com o mesmo tamanho e a mesma proporção (CARD_W x CARD_H em "u").
        // Testa cada nº de colunas e fica com o que deixa o card maior; a grade é centralizada.
        var cs = getComputedStyle(el.grid);
        var g = px(cs.columnGap) || 8;
        var W = el.grid.clientWidth;
        var H = el.grid.clientHeight;
        if (W <= 0 || H <= 0) return;
        var best = null;
        for (var c = 1; c <= total; c++) {
            var r = Math.ceil(total / c);
            var u = Math.min((W - (c - 1) * g) / (c * CARD_W), (H - (r - 1) * g) / (r * CARD_H));
            if (u <= 0) continue;
            if (!best || u > best.u + 0.01) best = { c: c, r: r, u: u };
        }
        if (!best) return;
        // Com poucos carros o card não vira um outdoor.
        var uMax = Math.max(16, window.innerHeight * 0.05);
        var uFinal = Math.min(best.u, uMax);
        var cardW = uFinal * CARD_W;
        var cardH = uFinal * CARD_H;

        el.grid.style.setProperty('--u', uFinal.toFixed(2) + 'px');
        el.grid.style.gridTemplateColumns = 'repeat(' + best.c + ', ' + cardW.toFixed(1) + 'px)';
        el.grid.style.gridAutoRows = cardH.toFixed(1) + 'px';
        el.grid.setAttribute('data-size', uFinal < 9 ? 's' : (uFinal < 13 ? 'm' : 'l'));
    }

    // ------------------------------------------------------------------
    // Agenda do dia
    // ------------------------------------------------------------------
    function fetchAgenda() {
        var today = isoDate(serverNow());
        return fetchJson('/api/agendamentos?date=' + encodeURIComponent(today)).then(function (data) {
            if (!data || data.success === false) throw new Error('agenda');
            state.agenda = (data.agendamentos || []).filter(function (a) {
                return norm(a.status) !== 'cancelado';
            }).sort(function (a, b) {
                return String(a.scheduled_time || '').localeCompare(String(b.scheduled_time || '')) || (a.id - b.id);
            });
            state.lastAgendaAt = Date.now();
            renderAgenda();
        });
    }

    function nowHM() {
        var d = new Date(serverNow());
        return pad2(d.getHours()) + ':' + pad2(d.getMinutes());
    }

    function renderAgenda(force) {
        var items = state.agenda;
        var hm = nowHM();

        if (!items.length) {
            if (!el.agenda.hidden) { el.agenda.hidden = true; state.agendaSig = ''; }
            return;
        }
        var wasHidden = el.agenda.hidden;
        el.agenda.hidden = false;

        // marca o "próximo" = primeiro ainda não atendido com horário >= agora (tolerância 15 min)
        var limit = new Date(serverNow() - 15 * 60000);
        var limitHM = pad2(limit.getHours()) + ':' + pad2(limit.getMinutes());
        var nextId = null;
        for (var i = 0; i < items.length; i++) {
            var a = items[i];
            if (norm(a.status) !== 'concluido' && String(a.scheduled_time || '') >= limitHM) { nextId = a.id; break; }
        }

        var listH = el.agendaList.clientHeight;
        var sig = items.map(function (a) { return [a.id, a.scheduled_time, a.status, a.car_model, a.car_plate, a.client_name, a.title].join('|'); }).join('~') +
            '#' + nextId + '#' + limitHM + '#' + Math.round(listH / 8);
        if (!force && !wasHidden && sig === state.agendaSig) return;
        state.agendaSig = sig;

        el.agendaCount.textContent = items.length;

        // 1ª passada: mede quantos itens cabem
        var visible = items.slice();
        paintAgenda(visible, nextId, hm);
        var rows = el.agendaList.children;
        var capacity = visible.length;
        if (rows.length && listH > 0) {
            var itemH = rows[0].offsetHeight;
            var gapPx = px(getComputedStyle(el.agendaList).rowGap);
            var moreReserve = itemH * 0.6;
            capacity = Math.max(1, Math.floor((listH - moreReserve + gapPx) / (itemH + gapPx)));
        }
        if (capacity < items.length) {
            // prioriza os que ainda vão acontecer; descarta primeiro os já atendidos/passados
            var ranked = items.slice().sort(function (a, b) {
                var da = (norm(a.status) === 'concluido' || String(a.scheduled_time || '') < limitHM) ? 1 : 0;
                var db = (norm(b.status) === 'concluido' || String(b.scheduled_time || '') < limitHM) ? 1 : 0;
                if (da !== db) return da - db;
                return String(a.scheduled_time || '').localeCompare(String(b.scheduled_time || ''));
            });
            var keep = {};
            ranked.slice(0, capacity).forEach(function (a) { keep[a.id] = true; });
            visible = items.filter(function (a) { return keep[a.id]; });
            paintAgenda(visible, nextId, hm);
            el.agendaMore.textContent = '+ ' + (items.length - visible.length) + ' mais hoje';
            el.agendaMore.hidden = false;
        } else {
            el.agendaMore.hidden = true;
        }
    }

    function paintAgenda(items, nextId, hm) {
        var limit = new Date(serverNow() - 15 * 60000);
        var limitHM = pad2(limit.getHours()) + ':' + pad2(limit.getMinutes());
        var STATUS_LABEL = { agendado: 'Agendado', confirmado: 'Confirmado', concluido: 'Atendido' };
        var html = items.map(function (a) {
            var st = norm(a.status) || 'agendado';
            var done = st === 'concluido';
            var cls = 'tv-agenda-item' + (a.id === nextId ? ' is-next' : '') + (done || (String(a.scheduled_time || '') < limitHM) ? ' is-done' : '');
            var plate = a.car_plate_display || a.car_plate || '';
            return '<li class="' + cls + '" data-ag-id="' + esc(a.id) + '" data-status="' + esc(st) + '" tabindex="0" role="button">' +
                '<span class="tv-ag-time">' + esc(a.scheduled_time || '--:--') + '</span>' +
                '<span class="tv-ag-main"><span class="tv-ag-model">' + esc(a.car_model || 'Veículo') + '</span>' +
                (plate ? '<span class="tv-ag-plate">' + esc(plate) + '</span>' : '') + '</span>' +
                '<span class="tv-ag-sub">' + esc(a.client_name || '') + (a.title ? ' · ' + esc(a.title) : '') + '</span>' +
                '<span class="tv-ag-state">' + esc(STATUS_LABEL[st] || st) + '</span></li>';
        }).join('');
        el.agendaList.innerHTML = html;
    }

    // ------------------------------------------------------------------
    // Loop de atualização
    // ------------------------------------------------------------------
    function scheduleNext() {
        clearTimeout(state.pollTimer);
        state.pollTimer = null;
        if (document.hidden) return; // aba oculta: pausa; retoma no visibilitychange
        var delay = state.failCount ? Math.min(POLL_MS * Math.pow(2, state.failCount), BACKOFF_MAX_MS) : POLL_MS;
        state.pollTimer = setTimeout(tick, delay);
    }

    function tick() {
        if (state.inFlight) return;
        state.inFlight = true;
        clearTimeout(state.pollTimer);
        fetchJson('/api/patio').then(function (data) {
            if (!data || data.success === false) throw new Error('patio');
            state.failCount = 0;
            applyPatio(data);
            setConn('ok');
            if (Date.now() - state.lastAgendaAt >= AGENDA_MS) {
                return fetchAgenda().catch(function () { /* agenda não derruba a conexão */ });
            }
        }).catch(function (err) {
            if (window.console && console.warn) console.warn('Painel TV: falha ao atualizar', err);
            state.failCount = Math.min(state.failCount + 1, 6);
            setConn('retry');
            if (!state.loaded) { // primeira carga falhou: mostra aviso no lugar do quadro
                el.board.setAttribute('data-empty', 'true');
                el.empty.hidden = false;
                el.empty.querySelector('.tv-empty-title').textContent = 'Aguardando o servidor';
                el.empty.querySelector('.tv-empty-sub').textContent = 'Reconectando automaticamente...';
            }
        }).then(function () {
            state.inFlight = false;
            scheduleNext();
        });
    }

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            clearTimeout(state.pollTimer);
            state.pollTimer = null;
        } else {
            tick();
        }
    });

    // ------------------------------------------------------------------
    // Controles do cabeçalho
    // ------------------------------------------------------------------
    var btnSound = $('btn-toggle-sound');
    btnSound.addEventListener('click', function () {
        state.soundOn = !state.soundOn;
        btnSound.classList.toggle('is-on', state.soundOn);
        btnSound.setAttribute('aria-pressed', state.soundOn ? 'true' : 'false');
        $('sound-icon').innerHTML = icon(state.soundOn ? 'volume-2' : 'volume-x');
        showToast(state.soundOn ? 'Aviso sonoro ativado' : 'Aviso sonoro desativado');
        if (state.soundOn) chime(); // o clique libera o áudio no navegador
    });

    var btnFull = $('btn-fullscreen');
    btnFull.addEventListener('click', function () {
        if (!document.fullscreenElement) {
            var root = document.documentElement;
            (root.requestFullscreen ? root.requestFullscreen() : Promise.reject()).catch(function () { /* recusado */ });
        } else if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    });
    document.addEventListener('fullscreenchange', function () {
        $('fullscreen-icon').innerHTML = icon(document.fullscreenElement ? 'minimize' : 'maximize');
    });

    // ------------------------------------------------------------------
    // Modal: carro no pátio
    // ------------------------------------------------------------------
    var modal = $('tv-manage-modal');
    var carForm = $('tv-car-form');
    var selectStatus = $('form-status');
    var thirdBox = $('third-party-section');
    var btnDelete = $('btn-delete-car');

    function setVal(id, v) { var n = $(id); if (n) n.value = v == null ? '' : v; }
    function getVal(id) { var n = $(id); return n ? n.value.trim() : ''; }

    function toggleThird() {
        thirdBox.hidden = !/terceir/i.test(selectStatus.value);
    }
    selectStatus.addEventListener('change', toggleThird);

    function openModal(car) {
        carForm.reset();
        setVal('form-car-id', car ? car.id : '');
        $('tv-modal-title').textContent = car ? 'Gerenciar ' + fmtPlate(car.plate_display || car.plate) : 'Adicionar carro ao pátio';
        btnDelete.hidden = !car;
        if (car) {
            setVal('form-plate', car.plate_display || car.plate);
            setVal('form-client', car.client_name);
            setVal('form-model', stripColor(car.car_model, car.car_color));
            setVal('form-color', car.car_color);
            setVal('form-box', car.box_mecanico || car.mechanic_name);
            setVal('form-notes', car.notes);
            setVal('form-auth-name', car.authorized_name || car.third_party_name);
            setVal('form-auth-doc', car.authorized_doc || car.third_party_doc);
            setVal('form-auth-phone', car.authorized_phone || car.third_party_phone);
            var phase = resolvePhase(car.status_display || car.status);
            for (var i = 0; i < selectStatus.options.length; i++) {
                if (resolvePhase(selectStatus.options[i].value) === phase) { selectStatus.selectedIndex = i; break; }
            }
        }
        toggleThird();
        modal.hidden = false;
        setTimeout(function () { var f = $('form-plate'); if (f) f.focus(); }, 30);
    }

    function closeModal() { modal.hidden = true; }

    $('btn-open-manage-modal').addEventListener('click', function () { openModal(null); });
    $('btn-close-modal').addEventListener('click', closeModal);
    $('btn-cancel-modal').addEventListener('click', closeModal);
    modal.addEventListener('mousedown', function (e) { if (e.target === modal) closeModal(); });

    carForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var id = getVal('form-car-id');
        var payload = {
            id: id ? parseInt(id, 10) : null,
            plate: getVal('form-plate').toUpperCase(),
            client_name: getVal('form-client'),
            car_model: getVal('form-model'),
            car_color: getVal('form-color'),
            status: selectStatus.value,
            box_mecanico: getVal('form-box'),
            notes: getVal('form-notes'),
            authorized_name: getVal('form-auth-name'),
            authorized_doc: getVal('form-auth-doc'),
            authorized_phone: getVal('form-auth-phone')
        };
        fetchJson('/api/patio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function (res) {
            if (!res.success) throw new Error(res.error || 'Tente novamente');
            closeModal();
            showToast('Veículo salvo no pátio');
            tick();
        }).catch(function (err) {
            showToast('Não foi possível salvar: ' + err.message);
        });
    });

    btnDelete.addEventListener('click', function () {
        var id = getVal('form-car-id');
        if (!id || !window.confirm('Confirmar a saída / baixa deste veículo do pátio?')) return;
        fetchJson('/api/patio/' + encodeURIComponent(id), { method: 'DELETE' }).then(function (res) {
            if (!res.success) throw new Error(res.error || 'Tente novamente');
            closeModal();
            showToast('Veículo removido do pátio');
            tick();
        }).catch(function (err) {
            showToast('Não foi possível remover: ' + err.message);
        });
    });

    // Clique/Enter num card abre a gestão (delegação: um único listener)
    function cardFromEvent(e) {
        var node = e.target && e.target.closest ? e.target.closest('.tv-card') : null;
        if (!node) return null;
        var rec = state.cars.get(Number(node.getAttribute('data-id'))) || state.cars.get(node.getAttribute('data-id'));
        return rec || null;
    }
    el.board.addEventListener('click', function (e) {
        var rec = cardFromEvent(e);
        if (rec) openModal(rec.raw);
    });
    el.board.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var rec = cardFromEvent(e);
        if (rec) { e.preventDefault(); openModal(rec.raw); }
    });

    // ------------------------------------------------------------------
    // Modal: agendamento (só atualiza status; cadastro completo fica no app)
    // ------------------------------------------------------------------
    var agModal = $('tv-agenda-modal');
    var agCurrent = null;

    function row(dt, dd) {
        return dd ? '<dt>' + esc(dt) + '</dt><dd>' + esc(dd) + '</dd>' : '';
    }

    function openAgenda(id) {
        var a = null;
        for (var i = 0; i < state.agenda.length; i++) if (String(state.agenda[i].id) === String(id)) a = state.agenda[i];
        if (!a) return;
        agCurrent = a;
        $('tv-agenda-modal-title').textContent = 'Agendamento das ' + (a.scheduled_time || '--:--');
        $('tv-agenda-detail').innerHTML = '<dl class="tv-agenda-detail">' +
            row('Cliente', a.client_name) + row('Telefone', a.phone) +
            row('Veículo', a.car_model) + row('Placa', a.car_plate_display || a.car_plate) +
            row('Serviço', a.title) + row('Descrição', a.description) + row('Observações', a.notes) +
            row('Status', a.status) + '</dl>';
        agModal.hidden = false;
    }

    function closeAgenda() { agModal.hidden = true; agCurrent = null; }

    el.agendaList.addEventListener('click', function (e) {
        var li = e.target.closest ? e.target.closest('.tv-agenda-item') : null;
        if (li) openAgenda(li.getAttribute('data-ag-id'));
    });
    el.agendaList.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var li = e.target.closest ? e.target.closest('.tv-agenda-item') : null;
        if (li) { e.preventDefault(); openAgenda(li.getAttribute('data-ag-id')); }
    });
    $('btn-close-agenda-modal').addEventListener('click', closeAgenda);
    agModal.addEventListener('mousedown', function (e) { if (e.target === agModal) closeAgenda(); });
    agModal.addEventListener('click', function (e) {
        var b = e.target.closest ? e.target.closest('[data-agenda-status]') : null;
        if (!b || !agCurrent) return;
        var id = agCurrent.id;
        fetchJson('/api/agendamentos/' + encodeURIComponent(id) + '/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: b.getAttribute('data-agenda-status') })
        }).then(function (res) {
            if (!res.success) throw new Error(res.error || 'Tente novamente');
            closeAgenda();
            showToast('Agendamento atualizado');
            return fetchAgenda();
        }).catch(function (err) {
            showToast('Não foi possível atualizar: ' + err.message);
        });
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { closeModal(); closeAgenda(); }
    });

    // ------------------------------------------------------------------
    // Inicialização
    // ------------------------------------------------------------------
    if (window.TVIcons) window.TVIcons.hydrate(document);

    if (typeof ResizeObserver === 'function') {
        var ro = new ResizeObserver(queueLayout);
        ro.observe(el.grid);
        ro.observe(el.agendaList);
    }
    window.addEventListener('resize', queueLayout);

    tickClock();
    setInterval(tickClock, 1000);
    state.sinceT = setInterval(updateAllSince, 20000);

    el.lanUrl.textContent = location.origin + '/tv';
    el.board.setAttribute('data-empty', 'loading');
    tick();
})();
