/**
 * Ícones Lucide (licença ISC) vendorizados em /vendor/icons.svg.
 * O sprite é injetado uma vez no <body> (loadIconSprite) e cada ícone vira
 * <svg class="icon icon-16"><use href="#i-nome"></use></svg>.
 *
 *   import { icon } from '../ui/icon.js';
 *   html`<button class="btn btn-sm">${icon('printer')} Imprimir</button>`
 *
 * Tamanhos suportados: 12, 14, 16 (padrão), 18, 20, 24, 32, 40.
 * Lista de nomes disponíveis: docs/FRONTEND.md (ou ids "i-*" em icons.svg).
 */
import { raw } from './dom.js';

const SIZES = new Set([12, 14, 16, 18, 20, 24, 32, 40]);
const NAME_RE = /^[a-z0-9-]+$/;

export function iconMarkup(name, size = 16, extraClass = '') {
    const safeName = NAME_RE.test(name) ? name : 'circle-help';
    const px = SIZES.has(size) ? size : 16;
    const cls = extraClass && /^[\w\s-]+$/.test(extraClass) ? ` ${extraClass}` : '';
    return `<svg class="icon icon-${px}${cls}" aria-hidden="true" focusable="false"><use href="#i-${safeName}"></use></svg>`;
}

/** Ícone como SafeHtml (para usar dentro de templates `html`). */
export function icon(name, size = 16, extraClass = '') {
    return raw(iconMarkup(name, size, extraClass));
}

/** Ícone como elemento DOM. */
export function iconEl(name, size = 16, extraClass = '') {
    const tpl = document.createElement('template');
    tpl.innerHTML = iconMarkup(name, size, extraClass);
    return tpl.content.firstElementChild;
}

/** Busca o sprite e o insere no início do <body>. Chamado uma vez pelo main.js. */
export async function loadIconSprite(url = '/vendor/icons.svg') {
    if (document.getElementById('mc-icon-sprite')) return;
    try {
        const res = await fetch(url);
        const text = await res.text();
        const holder = document.createElement('div');
        holder.id = 'mc-icon-sprite';
        holder.hidden = true;
        holder.setAttribute('aria-hidden', 'true');
        holder.innerHTML = text; // arquivo estático do próprio app (confiável)
        document.body.prepend(holder);
    } catch (err) {
        console.warn('Não foi possível carregar os ícones:', err);
    }
}
