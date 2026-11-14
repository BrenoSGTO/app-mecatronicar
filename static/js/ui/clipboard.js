/**
 * Copiar para a área de transferência com fallback e aviso.
 *   copyText(texto, 'Discriminação copiada!');
 */
import { toast } from './toast.js';

export async function copyText(text, successMessage = 'Copiado!') {
    if (text === null || text === undefined || String(text).trim() === '') {
        toast('Nada para copiar.', 'error');
        return false;
    }
    const value = String(text);
    try {
        await navigator.clipboard.writeText(value);
    } catch {
        const area = document.createElement('textarea');
        area.value = value;
        area.setAttribute('readonly', '');
        area.className = 'sr-only';
        document.body.append(area);
        area.select();
        document.execCommand('copy');
        area.remove();
    }
    toast(successMessage, 'success');
    return true;
}
