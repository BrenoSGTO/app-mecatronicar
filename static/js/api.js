/**
 * Wrapper de fetch para as rotas /api/* do servidor Flask.
 *
 * - Sempre JSON (envio e resposta), com mensagens de erro em português.
 * - Timeout (padrão 20s) via AbortController; aceita `signal` externo para
 *   cancelar requisições obsoletas (ex.: busca enquanto digita).
 * - Lança ApiError quando: rede falhou, timeout, HTTP != 2xx, resposta não-JSON
 *   ou `{ success: false }` (a menos que `allowFailure: true`).
 *
 *   import { api } from '../api.js';
 *   const { cars } = await api.get('/api/cars');
 *   await api.post('/api/patio/status', { id, status });
 */

export class ApiError extends Error {
    constructor(message, { status = 0, data = null, kind = 'http' } = {}) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
        this.kind = kind; // 'http' | 'network' | 'timeout' | 'parse' | 'failure'
    }
}

const DEFAULT_TIMEOUT = 20000;

/** Monta URL com querystring, ignorando valores vazios. */
export function apiUrl(path, params) {
    if (!params) return path;
    const qs = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value === null || value === undefined || value === '') continue;
        qs.set(key, String(value));
    }
    const str = qs.toString();
    return str ? `${path}${path.includes('?') ? '&' : '?'}${str}` : path;
}

async function parseResponse(res, fallbackMessage) {
    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
        const text = await res.text().catch(() => '');
        const clean = text.replace(/<[^>]*>?/gm, ' ').replace(/\s+/g, ' ').trim();
        const snippet = clean ? `: ${clean.length > 90 ? `${clean.slice(0, 90)}…` : clean}` : '.';
        if (!res.ok) {
            throw new ApiError(`O servidor retornou erro ${res.status}${snippet}`, { status: res.status, kind: 'http' });
        }
        throw new ApiError(`Resposta inesperada do servidor${snippet}`, { status: res.status, kind: 'parse' });
    }

    let data;
    try {
        data = await res.json();
    } catch {
        throw new ApiError('Não foi possível interpretar a resposta do servidor (JSON inválido).', { status: res.status, kind: 'parse' });
    }

    if (!res.ok) {
        const msg = (data && (data.error || data.message)) || `${fallbackMessage} (HTTP ${res.status})`;
        throw new ApiError(msg, { status: res.status, data, kind: 'http' });
    }
    return data;
}

/**
 * Requisição genérica.
 * @param {string} method
 * @param {string} path
 * @param {{params?:object, body?:any, timeout?:number, signal?:AbortSignal, allowFailure?:boolean, errorMessage?:string}} [options]
 */
export async function request(method, path, options = {}) {
    const {
        params,
        body,
        timeout = DEFAULT_TIMEOUT,
        signal,
        allowFailure = false,
        errorMessage = 'Falha na comunicação com o servidor',
    } = options;

    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
    }, timeout);

    const onExternalAbort = () => controller.abort();
    if (signal) {
        if (signal.aborted) controller.abort();
        else signal.addEventListener('abort', onExternalAbort, { once: true });
    }

    const init = {
        method,
        cache: 'no-store',
        signal: controller.signal,
        headers: { Accept: 'application/json' },
    };
    if (body !== undefined) {
        init.headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(body);
    }

    let res;
    try {
        res = await fetch(apiUrl(path, params), init);
    } catch (err) {
        if (timedOut) {
            throw new ApiError('O servidor demorou demais para responder. Tente novamente.', { kind: 'timeout' });
        }
        if (signal && signal.aborted) {
            throw err; // cancelado por quem chamou (AbortError) — ignore no chamador
        }
        throw new ApiError('Não foi possível conectar ao servidor local do MecatroniCar.', { kind: 'network' });
    } finally {
        clearTimeout(timer);
        if (signal) signal.removeEventListener('abort', onExternalAbort);
    }

    const data = await parseResponse(res, errorMessage);
    if (!allowFailure && data && data.success === false) {
        throw new ApiError(data.error || data.message || 'A operação não foi concluída.', { status: res.status, data, kind: 'failure' });
    }
    return data;
}

export const api = {
    get: (path, options) => request('GET', path, options),
    post: (path, body = {}, options) => request('POST', path, { ...options, body }),
    put: (path, body = {}, options) => request('PUT', path, { ...options, body }),
    del: (path, options) => request('DELETE', path, options),
};

/** true se o erro foi um cancelamento intencional (AbortController do chamador). */
export function isAbort(err) {
    return err && err.name === 'AbortError';
}

/** Abre uma rota GET (ex.: PDF) em nova aba/janela. */
export function openInNewTab(path, params) {
    window.open(apiUrl(path, params), '_blank');
}

/**
 * Envia um POST de formulário para nova aba (usado pelos geradores de PDF que
 * recebem `config_json`). Não usa fetch porque o resultado é uma página.
 */
export function postToNewTab(path, fields) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = path;
    form.target = '_blank';
    form.hidden = true;
    for (const [name, value] of Object.entries(fields)) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = name;
        input.value = typeof value === 'string' ? value : JSON.stringify(value);
        form.append(input);
    }
    document.body.append(form);
    form.submit();
    form.remove();
}
