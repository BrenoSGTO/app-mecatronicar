/**
 * Formatação pt-BR (moeda, km, datas, placas, nomes) e busca textual.
 * Funções puras — sem DOM.
 */

const BRL = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "R$ 1.234,50" a partir de número ou texto ("1.234,50", "R$ 10"). */
export function formatMoney(value) {
    return `R$ ${BRL.format(parseMoney(value))}`;
}

/** Converte "R$ 1.234,56" / "1234,56" / 1234.56 em número. */
export function parseMoney(value) {
    if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
    if (!value) return 0;
    const s = String(value).replace('R$', '').replace(/\s/g, '').replace(/\./g, '').replace(',', '.');
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : 0;
}

/** Número para campo de valor editável: 12.5 → "12,50". Texto passa direto. */
export function moneyInputValue(value) {
    if (value === null || value === undefined || value === '') return '';
    if (typeof value === 'number') return value.toFixed(2).replace('.', ',');
    return String(value);
}

export function formatDecimal(value, decimals = 2) {
    const n = parseFloat(value) || 0;
    return n.toLocaleString('pt-BR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function formatInt(value) {
    const n = parseInt(value, 10);
    return Number.isFinite(n) ? n.toLocaleString('pt-BR') : '0';
}

/** "109622" → "109.622 km" */
export function formatKm(value) {
    if (value === null || value === undefined || value === '') return '';
    const n = parseInt(String(value).replace(/\D/g, ''), 10);
    if (Number.isFinite(n) && n > 0) return `${n.toLocaleString('pt-BR')} km`;
    return `${value} km`;
}

export function pad2(n) {
    return String(n).padStart(2, '0');
}

/** Data local em ISO (AAAA-MM-DD), sem fuso. */
export function toIsoDate(date = new Date()) {
    return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export function todayIso() {
    return toIsoDate(new Date());
}

export function addDays(date, days) {
    const d = new Date(date);
    d.setDate(d.getDate() + days);
    return d;
}

/** Date → "DD/MM/AAAA" */
export function formatDateBr(date = new Date()) {
    const d = date instanceof Date ? date : new Date(date);
    if (Number.isNaN(d.getTime())) return '';
    return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()}`;
}

/** Date → "HH:MM" */
export function formatTimeBr(date = new Date()) {
    const d = date instanceof Date ? date : new Date(date);
    if (Number.isNaN(d.getTime())) return '';
    return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** "2026-11-05" → "05/11/2026" (vazio para "0000-00-00") */
export function isoToBr(iso) {
    if (!iso || iso === '0000-00-00') return '';
    const parts = String(iso).slice(0, 10).split('-');
    return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : String(iso);
}

/** Interpreta "AAAA-MM-DD HH:MM[:SS]", "DD/MM/AAAA" ou ISO. */
export function parseDateTime(value) {
    if (!value) return null;
    const s = String(value).trim();
    let m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(s);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0));
    m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
    m = /^(\d{2})\/(\d{2})\/(\d{4})/.exec(s);
    if (m) return new Date(+m[3], +m[2] - 1, +m[1], 8, 0, 0);
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? null : d;
}

/** Tempo no pátio: "Recém chegado", "35 min", "3h 10m", "2 dias". */
export function formatTimeInYard(value) {
    const start = parseDateTime(value);
    if (!start) return value ? String(value) : 'Recém chegado';
    const minutes = Math.floor(Math.max(0, Date.now() - start.getTime()) / 60000);
    if (minutes < 15) return 'Recém chegado';
    if (minutes < 60) return `${minutes} min no pátio`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
        const rem = minutes % 60;
        return rem > 0 ? `${hours}h ${rem}min no pátio` : `${hours}h no pátio`;
    }
    const days = Math.floor(hours / 24);
    return days === 1 ? '1 dia no pátio' : `${days} dias no pátio`;
}

/** "Entregue hoje às 14:30" / "ontem" / data. */
export function formatDelivered(value) {
    const d = parseDateTime(value);
    if (!d) return value ? `Entregue em ${value}` : 'Entregue recentemente';
    const now = new Date();
    const hm = formatTimeBr(d);
    if (d.toDateString() === now.toDateString()) return `Entregue hoje às ${hm}`;
    if (d.toDateString() === addDays(now, -1).toDateString()) return `Entregue ontem às ${hm}`;
    return `Entregue em ${formatDateBr(d)} às ${hm}`;
}

/** "AAAA-MM-DD" → "Hoje" | "Amanhã" | "DD/MM" */
export function formatRelativeDay(iso) {
    if (!iso) return 'Sem data';
    if (iso === todayIso()) return 'Hoje';
    if (iso === toIsoDate(addDays(new Date(), 1))) return 'Amanhã';
    const parts = String(iso).split('-');
    return parts.length === 3 ? `${parts[2]}/${parts[1]}` : String(iso);
}

/** "Carlos Eduardo da Silva" → "Carlos Eduardo"; "Ana de Souza" → "Ana de Souza" */
export function shortName(fullName) {
    if (!fullName) return 'Cliente';
    const parts = String(fullName).replace(/\(.*?\)/g, '').replace(/[-_]/g, ' ').trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return 'Cliente';
    if (parts.length === 1) return parts[0];
    const connectors = ['de', 'da', 'do', 'dos', 'das', 'e'];
    if (connectors.includes(parts[1].toLowerCase()) && parts.length > 2) return `${parts[0]} ${parts[1]} ${parts[2]}`;
    return `${parts[0]} ${parts[1]}`;
}

/** Só letras e números, maiúsculo: "abc-1d23" → "ABC1D23" */
export function cleanPlate(value) {
    return String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
}

/** Placa para exibição: antiga "ABC-1234", Mercosul "ABC1D23". */
export function formatPlate(value) {
    const rawValue = String(value || '').trim().toUpperCase();
    const clean = cleanPlate(rawValue);
    if (clean.length === 7) {
        return /^[A-Z]{3}[0-9]{4}$/.test(clean) ? `${clean.slice(0, 3)}-${clean.slice(3)}` : clean;
    }
    return rawValue || 'SEM PLACA';
}

export function plural(n, singular, pluralForm = `${singular}s`) {
    return `${n} ${n === 1 ? singular : pluralForm}`;
}

/** Remove acentos, minúsculas. */
export function normalizeText(value) {
    if (!value) return '';
    return String(value).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

const STOP_WORDS = new Set(['de', 'do', 'da', 'dos', 'das', 'e', 'o', 'a', 'os', 'as', 'no', 'na', 'nos', 'nas', 'para', 'por', 'com', 'em']);
const ACTION_WORDS = new Set(['troca', 'trocar', 'substituicao', 'substituir', 'subst', 'reparo', 'conserto', 'servico', 'peca']);

/**
 * Busca por palavras ignorando acentos, preposições e verbos genéricos
 * ("troca de óleo" casa com "Óleo 5W30").
 */
export function matchesSearchTokens(target, query) {
    const normTarget = normalizeText(target);
    const tokens = normalizeText(query).split(/\s+/).filter((t) => t && !STOP_WORDS.has(t));
    if (tokens.length === 0) return normTarget.includes(normalizeText(query));
    const specific = tokens.filter((t) => !ACTION_WORDS.has(t));
    return (specific.length ? specific : tokens).every((t) => normTarget.includes(t));
}
