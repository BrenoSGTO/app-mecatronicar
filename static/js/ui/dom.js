/**
 * Helpers de DOM com escape de HTML por padrão.
 *
 * Regra de ouro: dado vindo do usuário/planilha/servidor NUNCA vai cru para
 * innerHTML. Use o template `html` — toda interpolação é escapada, a menos que
 * seja outro `html`...`` (ou `raw()`, só para marcação que VOCÊ escreveu).
 *
 *   import { html, render, $, on } from '../ui/dom.js';
 *   render(lista, html`<li title="${cliente}">${cliente}</li>`);
 */

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '`': '&#96;' };

/** Escapa um valor qualquer para uso seguro em HTML (texto ou atributo). */
export function esc(value) {
    if (value === null || value === undefined) return '';
    return String(value).replace(/[&<>"'`]/g, (ch) => ESCAPES[ch]);
}

/** Marcação já confiável (resultado de `html` ou string escrita no código). */
export class SafeHtml {
    constructor(value) {
        this.value = value;
    }

    toString() {
        return this.value;
    }
}

/** Marca uma string como HTML confiável. NUNCA passe dados do usuário aqui. */
export function raw(markup) {
    if (markup instanceof SafeHtml) return markup;
    return new SafeHtml(markup === null || markup === undefined ? '' : String(markup));
}

function toMarkup(value) {
    if (value === null || value === undefined || value === false || value === true) return '';
    if (value instanceof SafeHtml) return value.value;
    if (Array.isArray(value)) return value.map(toMarkup).join('');
    return esc(value);
}

/**
 * Template literal com escape automático.
 * - `${texto}` → escapado
 * - `${html`...`}` / `${[html`...`, ...]}` → inserido como marcação
 * - `${false}` / `${null}` / `${undefined}` → nada (permite `${cond && html`...`}`)
 */
export function html(strings, ...values) {
    let out = strings[0];
    for (let i = 0; i < values.length; i++) {
        out += toMarkup(values[i]) + strings[i + 1];
    }
    return new SafeHtml(out);
}

/** Junta uma lista em marcação (atalho para listas: join(items.map(fn))). */
export function join(list) {
    return new SafeHtml((list || []).map(toMarkup).join(''));
}

/**
 * Substitui o conteúdo de `el`.
 * - SafeHtml → innerHTML
 * - Node / DocumentFragment → replaceChildren
 * - string/número → textContent (nunca interpreta HTML)
 */
export function render(el, content) {
    if (!el) return el;
    if (content instanceof SafeHtml) {
        el.innerHTML = content.value;
    } else if (content instanceof Node) {
        el.replaceChildren(content);
    } else if (Array.isArray(content)) {
        el.replaceChildren(...content.filter(Boolean));
    } else {
        el.textContent = content === null || content === undefined ? '' : String(content);
    }
    return el;
}

/** Cria um DocumentFragment a partir de SafeHtml. */
export function fragment(content) {
    const tpl = document.createElement('template');
    tpl.innerHTML = content instanceof SafeHtml ? content.value : esc(content);
    return tpl.content;
}

/** Cria UM elemento a partir de SafeHtml (o primeiro elemento do template). */
export function toElement(content) {
    return fragment(content).firstElementChild;
}

/**
 * Cria elemento programaticamente.
 *   h('button', { class: 'btn btn-sm', type: 'button', onclick: fn, dataset: { id: 3 } }, 'Salvar')
 */
export function h(tag, props = {}, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
        if (value === null || value === undefined || value === false) continue;
        if (key === 'class' || key === 'className') {
            el.className = value;
        } else if (key === 'dataset') {
            Object.assign(el.dataset, value);
        } else if (key.startsWith('on') && typeof value === 'function') {
            el.addEventListener(key.slice(2).toLowerCase(), value);
        } else if (key === 'text') {
            el.textContent = value;
        } else if (value === true) {
            el.setAttribute(key, '');
        } else {
            el.setAttribute(key, String(value));
        }
    }
    for (const child of children.flat()) {
        if (child === null || child === undefined || child === false) continue;
        if (child instanceof SafeHtml) {
            el.append(fragment(child));
        } else if (child instanceof Node) {
            el.append(child);
        } else {
            el.append(document.createTextNode(String(child)));
        }
    }
    return el;
}

export function $(selector, root = document) {
    return root.querySelector(selector);
}

export function $$(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
}

/**
 * Delegação de eventos.
 *   on(lista, 'click', '[data-action="abrir"]', (ev, alvo) => ...)
 *   on(botao, 'click', (ev) => ...)            // sem seletor
 * Retorna função que remove o listener.
 */
export function on(root, type, selectorOrHandler, maybeHandler, options) {
    if (typeof selectorOrHandler === 'function') {
        const handler = selectorOrHandler;
        root.addEventListener(type, handler, maybeHandler);
        return () => root.removeEventListener(type, handler, maybeHandler);
    }
    const selector = selectorOrHandler;
    const listener = (event) => {
        const target = event.target instanceof Element ? event.target.closest(selector) : null;
        if (target && root.contains(target)) {
            maybeHandler(event, target);
        }
    };
    root.addEventListener(type, listener, options);
    return () => root.removeEventListener(type, listener, options);
}

/** Mostra/oculta via atributo hidden (forma oficial; nada de style.display). */
export function show(el, visible = true) {
    if (el) el.hidden = !visible;
    return el;
}

export function hide(el) {
    return show(el, false);
}

/** Define texto com segurança. */
export function setText(el, text) {
    if (el) el.textContent = text === null || text === undefined ? '' : String(text);
    return el;
}

/** Valor dinâmico de estilo (larguras de barra etc.) via custom property. */
export function setVar(el, name, value) {
    if (el) el.style.setProperty(name, value);
    return el;
}

/** Debounce simples. */
export function debounce(fn, wait = 200) {
    let timer = null;
    const debounced = (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), wait);
    };
    debounced.cancel = () => clearTimeout(timer);
    return debounced;
}

/** Coloca um botão em estado de carregamento e devolve função para restaurar. */
export function busy(button, label) {
    if (!button) return () => {};
    const previous = button.innerHTML;
    const wasDisabled = button.disabled;
    button.disabled = true;
    button.classList.add('is-loading');
    if (label) {
        button.innerHTML = `<svg class="icon icon-16 icon-spin" aria-hidden="true"><use href="#i-loader-circle"></use></svg><span>${esc(label)}</span>`;
    }
    return () => {
        button.innerHTML = previous;
        button.disabled = wasDisabled;
        button.classList.remove('is-loading');
    };
}

/** Lê os valores de campos [name] de um formulário/contêiner em um objeto (trim). */
export function readFields(root) {
    const out = {};
    for (const el of root.querySelectorAll('[name]')) {
        if (el.type === 'checkbox') out[el.name] = el.checked;
        else if (el.type === 'radio') { if (el.checked) out[el.name] = el.value; }
        else out[el.name] = typeof el.value === 'string' ? el.value.trim() : el.value;
    }
    return out;
}

/** Preenche campos [name] de um contêiner a partir de um objeto. */
export function fillFields(root, values) {
    for (const [name, value] of Object.entries(values || {})) {
        const el = root.querySelector(`[name="${name}"]`);
        if (!el) continue;
        if (el.type === 'checkbox') el.checked = Boolean(value);
        else el.value = value === null || value === undefined ? '' : String(value);
    }
}
