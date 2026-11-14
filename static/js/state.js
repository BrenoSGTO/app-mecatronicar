/**
 * Estado global simples + barramento de eventos.
 *
 * Estado (chave → valor). `state.set` só notifica se o valor MUDOU
 * (comparação por JSON), o que evita re-render quando o polling traz o mesmo dado.
 *
 *   import { state, on, emit } from '../state.js';
 *   state.watch('patio', (patio) => renderPatio(patio));  // chama já e a cada mudança
 *   state.set('patio', data);                              // notifica só se mudou
 *
 * Chaves usadas hoje (documente as novas em docs/FRONTEND.md):
 *   config        { spreadsheet_folder, theme, ui_zoom, ... }  (GET /api/config)
 *   appInfo       { version, local_ip, tv_url, stats }
 *   cars          lista de veículos indexados (GET /api/cars)
 *   patio         { active: [], delivered: [], all: [] }       (GET /api/patio)
 *   agendaEvents  eventos do calendário (GET /api/agenda)
 *   agendamentos  agendamentos da secretária (GET /api/agendamentos)
 *   nfStats       estatísticas fiscais (GET /api/nf/pending)
 *
 * Eventos (on/emit) — convenção "dominio:acao":
 *   route:changed       { name, params, query }
 *   os:saved            { plate }
 *   fiscal:changed      { plate }
 *   vehicle:reload      { plate }
 */

const listeners = new Map();

export function on(event, handler) {
    if (!listeners.has(event)) listeners.set(event, new Set());
    listeners.get(event).add(handler);
    return () => off(event, handler);
}

export function off(event, handler) {
    const set = listeners.get(event);
    if (set) set.delete(handler);
}

export function once(event, handler) {
    const remove = on(event, (payload) => {
        remove();
        handler(payload);
    });
    return remove;
}

export function emit(event, payload) {
    const set = listeners.get(event);
    if (!set) return;
    for (const handler of [...set]) {
        try {
            handler(payload);
        } catch (err) {
            console.error(`[evento ${event}]`, err);
        }
    }
}

const store = new Map();
const signatures = new Map();

function signature(value) {
    try {
        return JSON.stringify(value);
    } catch {
        return `${Date.now()}-${Math.random()}`;
    }
}

export const state = {
    get(key, fallback = undefined) {
        return store.has(key) ? store.get(key) : fallback;
    },

    has(key) {
        return store.has(key);
    },

    /** Define o valor; retorna true se mudou (e notificou). */
    set(key, value, { force = false } = {}) {
        const sig = signature(value);
        if (!force && signatures.get(key) === sig) return false;
        store.set(key, value);
        signatures.set(key, sig);
        emit(`state:${key}`, value);
        return true;
    },

    /** Atualiza a partir do valor atual. */
    update(key, updater) {
        return this.set(key, updater(store.get(key)));
    },

    /** Observa uma chave. Por padrão chama imediatamente se já houver valor. */
    watch(key, handler, { immediate = true } = {}) {
        const remove = on(`state:${key}`, handler);
        if (immediate && store.has(key)) {
            try {
                handler(store.get(key));
            } catch (err) {
                console.error(`[state ${key}]`, err);
            }
        }
        return remove;
    },
};
