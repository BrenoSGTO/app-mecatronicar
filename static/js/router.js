/**
 * Roteador por hash: #/inicio, #/busca?q=fox, #/veiculo/ABC1D23 ...
 *
 * Cada rota aponta para um objeto "view" (ver docs/FRONTEND.md):
 *   {
 *     id: 'inicio',              // usado em data-view e nas classes CSS
 *     title: 'Início',           // título da janela
 *     mount(el) {},              // 1ª vez: monta a marcação dentro de <section class="view">
 *     enter(params, query) {},   // toda vez que a rota fica ativa (inclusive troca de parâmetro)
 *     leave() {},                // ao sair para OUTRA view
 *   }
 * A <section> de cada view é criada uma vez e mantida (só fica hidden), então
 * filtros e rolagem interna são preservados entre visitas.
 */
import { emit } from './state.js';

const routes = [];
const mounted = new Map(); // view.id -> section
let host = null;
let fallbackPath = '/inicio';
let current = null;
let started = false;

function compile(pattern) {
    const keys = [];
    const source = pattern
        .replace(/\/+$/, '')
        .replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        .replace(/:(\w+)/g, (_, key) => {
            keys.push(key);
            return '([^/]+)';
        });
    return { regex: new RegExp(`^${source || ''}/?$`), keys };
}

/**
 * @param {Array<{path:string, view:object, name?:string}>} list
 * @param {{host:HTMLElement, fallback?:string}} options
 */
export function defineRoutes(list, options) {
    host = options.host;
    fallbackPath = options.fallback || fallbackPath;
    for (const route of list) {
        const { regex, keys } = compile(route.path);
        routes.push({ ...route, name: route.name || route.view.id, regex, keys });
    }
}

function parseHash() {
    const rawHash = location.hash.replace(/^#/, '') || '/';
    const [pathPart, queryPart = ''] = rawHash.split('?');
    const path = pathPart.startsWith('/') ? pathPart : `/${pathPart}`;
    const query = Object.fromEntries(new URLSearchParams(queryPart));
    for (const route of routes) {
        const m = route.regex.exec(path);
        if (!m) continue;
        const params = {};
        route.keys.forEach((key, i) => {
            try {
                params[key] = decodeURIComponent(m[i + 1]);
            } catch {
                params[key] = m[i + 1];
            }
        });
        return { route, params, query, path };
    }
    return null;
}

function sameMatch(a, b) {
    return a && b && a.route === b.route
        && JSON.stringify(a.params) === JSON.stringify(b.params)
        && JSON.stringify(a.query) === JSON.stringify(b.query);
}

function ensureMounted(view) {
    let section = mounted.get(view.id);
    if (!section) {
        section = document.createElement('section');
        section.className = `view view-${view.id}`;
        section.dataset.view = view.id;
        section.hidden = true;
        host.append(section);
        mounted.set(view.id, section);
        try {
            view.mount?.(section);
        } catch (err) {
            console.error(`[router] falha ao montar a tela "${view.id}"`, err);
        }
    }
    return section;
}

async function handleChange() {
    const match = parseHash();
    if (!match) {
        navigate(fallbackPath, { replace: true });
        return;
    }
    if (sameMatch(match, current)) return;

    const previous = current;
    const switchingView = !previous || previous.route.view !== match.route.view;

    if (previous && switchingView) {
        try {
            previous.route.view.leave?.();
        } catch (err) {
            console.error(err);
        }
        const prevSection = mounted.get(previous.route.view.id);
        if (prevSection) prevSection.hidden = true;
    }

    const section = ensureMounted(match.route.view);
    section.hidden = false;
    current = match;

    document.title = `${match.route.view.title || 'MecatroniCar'} · MecatroniCar`;
    if (switchingView && host.parentElement) host.parentElement.scrollTop = 0;

    emit('route:changed', { name: match.route.name, viewId: match.route.view.id, params: match.params, query: match.query });

    try {
        await match.route.view.enter?.(match.params, match.query, { previous: previous ? previous.route.name : null });
    } catch (err) {
        console.error(`[router] erro ao abrir a tela "${match.route.view.id}"`, err);
    }
}

/** Monta a URL de hash: href('/veiculo/ABC1D23') → '#/veiculo/ABC1D23' */
export function href(path, query) {
    let out = `#${path.startsWith('/') ? path : `/${path}`}`;
    if (query) {
        const qs = new URLSearchParams();
        for (const [k, v] of Object.entries(query)) {
            if (v !== null && v !== undefined && v !== '') qs.set(k, String(v));
        }
        const s = qs.toString();
        if (s) out += `?${s}`;
    }
    return out;
}

/**
 * Navega para um caminho. `replace: true` não cria entrada no histórico
 * (útil para busca enquanto digita).
 */
export function navigate(path, { query, replace = false } = {}) {
    const target = href(path, query);
    if (location.hash === target) {
        handleChange();
        return;
    }
    if (replace) {
        history.replaceState(history.state, '', target);
        handleChange();
    } else {
        location.hash = target;
    }
}

export function currentRoute() {
    return current ? { name: current.route.name, viewId: current.route.view.id, params: current.params, query: current.query } : null;
}

export function isActive(name) {
    return Boolean(current && current.route.name === name);
}

export function start() {
    if (started) return;
    started = true;
    window.addEventListener('hashchange', handleChange);
    handleChange();
}
