/**
 * Agendador único de tarefas periódicas (polling).
 *
 * - Pausa tudo quando a janela fica oculta (visibilitychange) e retoma ao voltar,
 *   rodando na hora as tarefas que ficaram "vencidas".
 * - Nunca roda a mesma tarefa em paralelo; chamadas durante a execução são
 *   agrupadas em uma única nova execução.
 * - `when()` opcional: a tarefa só roda se retornar true (ex.: só na tela X).
 *
 *   import { every, runNow } from '../scheduler.js';
 *   every('patio', 15000, loadPatio);     // roda já e depois a cada 15s
 *   await runNow('patio');                // força atualização após uma ação
 *
 * Para "só re-renderizar quando mudou", grave o resultado com state.set()
 * (que compara o valor) e renderize em state.watch().
 */

const tasks = new Map();
let paused = typeof document !== 'undefined' ? document.hidden : false;

function schedule(task, delay = task.interval) {
    clearTimeout(task.timer);
    task.timer = null;
    if (paused || !tasks.has(task.name)) return;
    task.timer = setTimeout(() => execute(task), Math.max(0, delay));
}

async function execute(task) {
    if (tasks.get(task.name) !== task) return undefined;
    clearTimeout(task.timer);
    task.timer = null;
    if (paused) return undefined;

    if (task.running) {
        task.rerun = true;
        return task.running;
    }
    if (task.when && !task.when()) {
        schedule(task);
        return undefined;
    }

    task.running = (async () => {
        try {
            await task.fn();
        } catch (err) {
            console.warn(`[agendador] tarefa "${task.name}" falhou:`, err);
        } finally {
            task.lastRun = Date.now();
            task.running = null;
            if (task.rerun) {
                task.rerun = false;
                execute(task);
            } else {
                schedule(task);
            }
        }
    })();
    return task.running;
}

/**
 * Registra (ou substitui) uma tarefa periódica.
 * @returns {() => void} função que cancela a tarefa
 */
export function every(name, interval, fn, { immediate = true, when = null } = {}) {
    stop(name);
    const task = { name, interval, fn, when, timer: null, running: null, rerun: false, lastRun: 0 };
    tasks.set(name, task);
    if (immediate) execute(task);
    else schedule(task);
    return () => stop(name);
}

/** Executa a tarefa agora (ignora `when`) e reinicia o intervalo. */
export function runNow(name) {
    const task = tasks.get(name);
    if (!task) return Promise.resolve();
    if (task.running) {
        task.rerun = true;
        return task.running;
    }
    const savedWhen = task.when;
    task.when = null;
    const p = execute(task);
    task.when = savedWhen;
    return p || Promise.resolve();
}

export function stop(name) {
    const task = tasks.get(name);
    if (!task) return;
    clearTimeout(task.timer);
    tasks.delete(name);
}

export function isPaused() {
    return paused;
}

if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', () => {
        paused = document.hidden;
        for (const task of tasks.values()) {
            if (paused) {
                clearTimeout(task.timer);
                task.timer = null;
            } else {
                const elapsed = Date.now() - task.lastRun;
                schedule(task, elapsed >= task.interval ? 0 : task.interval - elapsed);
            }
        }
    });
}
