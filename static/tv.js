/**
 * MecatroniCar v2.0 - tv.js
 * Painel de TV / Monitoramento do Pátio ao Vivo em Grade Dinâmica Auto-Fit
 * Issue #14: Grade Sem Colunas Rígidas, Ordenação Operacional por Fase e Ajuste de Tela Cheia
 */

document.addEventListener("DOMContentLoaded", () => {
    // Estado da TV
    let patioData = { total: 0, by_status: {}, cars: [] };
    let previousCarStatuses = {};
    let soundEnabled = false;
    let pollInterval = null;

    // Configuração das 7 Fases Operacionais Oficiais da MecatroniCar
    const PHASE_CONFIG = {
        diagnostico: {
            order: 1,
            key: "diagnostico",
            label: "Em Diagnóstico",
            icon: "🔍",
            cssClass: "phase-diagnostico",
            badgeClass: "tv-phase-badge-diagnostico",
            matcher: (s) => /diagn[oó]st/i.test(s)
        },
        orcamento: {
            order: 2,
            key: "orcamento",
            label: "Esperando Orçamento",
            icon: "📝",
            cssClass: "phase-orcamento",
            badgeClass: "tv-phase-badge-orcamento",
            matcher: (s) => /or[cç]am/i.test(s)
        },
        aprovacao: {
            order: 3,
            key: "aprovacao",
            label: "Esperando Aprovação",
            icon: "⏳",
            cssClass: "phase-aprovacao",
            badgeClass: "tv-phase-badge-aprovacao",
            matcher: (s) => /aprov/i.test(s)
        },
        pecas: {
            order: 4,
            key: "pecas",
            label: "Esperando Peças",
            icon: "📦",
            cssClass: "phase-pecas",
            badgeClass: "tv-phase-badge-pecas",
            matcher: (s) => /pe[cç]a/i.test(s)
        },
        execucao: {
            order: 5,
            key: "execucao",
            label: "Em Execução",
            icon: "🔧",
            cssClass: "phase-execucao",
            badgeClass: "tv-phase-badge-execucao",
            matcher: (s) => /execu/i.test(s)
        },
        pronto: {
            order: 6,
            key: "pronto",
            label: "Aguardando Retirada",
            icon: "✅",
            cssClass: "phase-pronto",
            badgeClass: "tv-phase-badge-pronto",
            matcher: (s) => !/terceir/i.test(s) && (/client/i.test(s) || /retir/i.test(s) || /pronto/i.test(s))
        },
        terceiro: {
            order: 7,
            key: "terceiro",
            label: "Retirada p/ Terceiro",
            icon: "🔑",
            cssClass: "phase-terceiro",
            badgeClass: "tv-phase-badge-terceiro",
            matcher: (s) => /terceir/i.test(s)
        }
    };

    function resolvePhase(statusStr) {
        if (!statusStr) return PHASE_CONFIG.diagnostico;
        const s = String(statusStr).trim();
        for (const phase of Object.values(PHASE_CONFIG)) {
            if (phase.matcher(s)) {
                return phase;
            }
        }
        return PHASE_CONFIG.diagnostico;
    }

    // Elementos DOM Principais
    const clockTimeEl = document.getElementById("tv-clock-time");
    const clockDateEl = document.getElementById("tv-clock-date");
    const totalCarsEl = document.getElementById("tv-total-cars");
    const btnToggleSound = document.getElementById("btn-toggle-sound");
    const soundIcon = document.getElementById("sound-icon");
    const btnFullscreen = document.getElementById("btn-fullscreen");
    const btnOpenManageModal = document.getElementById("btn-open-manage-modal");
    const btnEmptyAddCar = document.getElementById("btn-empty-add-car");

    // Elementos do Grid e Fases
    const gridWrapper = document.getElementById("tv-grid-wrapper");
    const carsGrid = document.getElementById("tv-cars-grid");
    const emptyState = document.getElementById("tv-empty-state");
    const connDot = document.getElementById("tv-conn-dot");
    const connStatus = document.getElementById("tv-conn-status");
    const lastSyncEl = document.getElementById("tv-last-sync");
    const tvLanUrlEl = document.getElementById("tv-lan-url");

    // Elementos do Modal
    const modalBackdrop = document.getElementById("tv-manage-modal");
    const modalCloseBtn = document.getElementById("btn-close-modal");
    const btnCancelModal = document.getElementById("btn-cancel-modal");
    const modalForm = document.getElementById("tv-car-form") || document.getElementById("tv-manage-form");
    const btnDeleteCar = document.getElementById("btn-delete-car");
    const selectStatus = document.getElementById("form-status");
    const thirdPartySection = document.getElementById("third-party-section");

    // Relógio Digital
    function updateClock() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString("pt-BR", { hour12: false });
        const dateStr = now.toLocaleDateString("pt-BR", {
            weekday: "long",
            day: "2-digit",
            month: "long",
            year: "numeric"
        });
        if (clockTimeEl) clockTimeEl.textContent = timeStr;
        if (clockDateEl) clockDateEl.textContent = dateStr;
    }
    updateClock();
    setInterval(updateClock, 1000);

    // Alerta Sonoro com Web Audio API
    function playStatusChangeChime() {
        if (!soundEnabled) return;
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
            osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
            gain.gain.setValueAtTime(0.3, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.35);
        } catch (e) {
            console.warn("Audio Context blocked:", e);
        }
    }

    // Toggle de Som
    if (btnToggleSound) {
        btnToggleSound.addEventListener("click", () => {
            soundEnabled = !soundEnabled;
            if (soundEnabled) {
                if (soundIcon) soundIcon.textContent = "🔊";
                btnToggleSound.classList.add("tv-btn-primary");
                showToast("🔔 Aviso sonoro ativado!");
                playStatusChangeChime();
            } else {
                if (soundIcon) soundIcon.textContent = "🔔";
                btnToggleSound.classList.remove("tv-btn-primary");
                showToast("🔕 Aviso sonoro desativado.");
            }
        });
    }

    // Toggle Tela Cheia
    if (btnFullscreen) {
        btnFullscreen.addEventListener("click", () => {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => {
                    console.warn(`Erro tentando tela cheia: ${err.message}`);
                });
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                }
            }
        });
    }

    // Algoritmo de Ajuste Automático de Tamanho (Auto-Fit Grade Dinâmica)
    function calculateOptimalGrid(n, containerWidth, containerHeight) {
        if (n <= 0) return { cols: 1, rows: 1, density: "large" };
        if (n === 1) return { cols: 1, rows: 1, density: "xlarge" };

        const isLandscape = (containerWidth || window.innerWidth) >= (containerHeight || window.innerHeight);

        let cols, rows;

        if (n === 2) {
            cols = isLandscape ? 2 : 1;
            rows = isLandscape ? 1 : 2;
        } else if (n === 3) {
            cols = isLandscape ? 3 : 1;
            rows = isLandscape ? 1 : 3;
        } else if (n === 4) {
            cols = 2;
            rows = 2;
        } else if (n <= 6) {
            cols = isLandscape ? 3 : 2;
            rows = isLandscape ? 2 : 3;
        } else if (n <= 8) {
            cols = isLandscape ? 4 : 2;
            rows = isLandscape ? 2 : 4;
        } else if (n === 9) {
            cols = 3;
            rows = 3;
        } else if (n <= 12) {
            cols = isLandscape ? 4 : 3;
            rows = isLandscape ? 3 : 4;
        } else if (n <= 15) {
            cols = isLandscape ? 5 : 3;
            rows = isLandscape ? 3 : 5;
        } else if (n <= 16) {
            cols = 4;
            rows = 4;
        } else if (n <= 20) {
            cols = isLandscape ? 5 : 4;
            rows = isLandscape ? 4 : 5;
        } else if (n <= 24) {
            cols = isLandscape ? 6 : 4;
            rows = isLandscape ? 4 : 6;
        } else {
            // Mais de 24 veículos
            cols = isLandscape ? Math.min(8, Math.ceil(Math.sqrt(n * 1.6))) : Math.min(5, Math.ceil(Math.sqrt(n * 0.7)));
            rows = Math.ceil(n / cols);
        }

        let density = "medium";
        if (rows <= 1) {
            density = "xlarge";
        } else if (rows === 2) {
            density = "large";
        } else if (rows === 3) {
            density = "medium";
        } else {
            density = "compact";
        }

        return { cols, rows, density };
    }

    // Carregar e Atualizar Pátio (Polling)
    async function fetchPatioData() {
        try {
            const res = await fetch("/api/patio");
            if (!res.ok) throw new Error("Erro na requisição /api/patio");
            const data = await res.json();
            if (data.success) {
                checkStatusChanges(data.cars || []);
                patioData = data;
                renderBoard(data);

                if (connDot) connDot.style.backgroundColor = "var(--phase-exec)";
                if (connStatus) connStatus.textContent = "Conectado ao vivo";
                if (lastSyncEl) {
                    const now = new Date();
                    lastSyncEl.textContent = `Última checagem: ${now.toLocaleTimeString("pt-BR")}`;
                }
                if (tvLanUrlEl && data.tv_url) {
                    tvLanUrlEl.textContent = data.tv_url;
                }
            }
        } catch (err) {
            console.error("Erro atualizando pátio da TV:", err);
            if (connDot) connDot.style.backgroundColor = "var(--mec-danger)";
            if (connStatus) connStatus.textContent = "Reconectando...";
        }
    }

    function checkStatusChanges(newCars) {
        let hasChanges = false;
        const currentMap = {};
        newCars.forEach(c => {
            currentMap[c.id] = c.status;
            if (previousCarStatuses[c.id] && previousCarStatuses[c.id] !== c.status) {
                hasChanges = true;
            }
        });
        if (hasChanges && Object.keys(previousCarStatuses).length > 0) {
            playStatusChangeChime();
            showToast("🔔 Status de veículo atualizado no pátio!");
        }
        previousCarStatuses = currentMap;
    }

    // Renderizar Painel da TV em Grade Dinâmica
    function renderBoard(data) {
        const cars = Array.isArray(data.cars) ? data.cars : [];
        const total = cars.length;

        // Atualiza contador total no header
        if (totalCarsEl) totalCarsEl.textContent = total;

        // Contagem por fase operacional
        const phaseCounts = {
            diagnostico: 0,
            orcamento: 0,
            aprovacao: 0,
            pecas: 0,
            execucao: 0,
            pronto: 0,
            terceiro: 0
        };

        cars.forEach(car => {
            const phase = resolvePhase(car.status_display || car.status);
            if (phaseCounts[phase.key] !== undefined) {
                phaseCounts[phase.key]++;
            }
        });

        // Atualiza pílulas da barra de fases (macro pipeline)
        Object.entries(phaseCounts).forEach(([key, count]) => {
            const countEl = document.getElementById(`count-${key}`);
            const pillEl = document.querySelector(`.tv-phase-pill[data-phase="${key}"]`);
            if (countEl) countEl.textContent = count;
            if (pillEl) {
                if (count > 0) {
                    pillEl.classList.add("has-cars");
                } else {
                    pillEl.classList.remove("has-cars");
                }
            }
        });

        // Ordenação dos cards pela fase operacional (Diagnóstico -> ... -> Retirada)
        const sortedCars = [...cars].sort((a, b) => {
            const phaseA = resolvePhase(a.status_display || a.status);
            const phaseB = resolvePhase(b.status_display || b.status);
            if (phaseA.order !== phaseB.order) {
                return phaseA.order - phaseB.order;
            }
            // Secundário: por ID para estabilidade visual
            return (a.id || 0) - (b.id || 0);
        });

        // Se pátio vazio, exibe empty state elegante
        if (total === 0) {
            if (carsGrid) {
                carsGrid.innerHTML = "";
                carsGrid.style.display = "none";
            }
            if (emptyState) emptyState.style.display = "flex";
            return;
        }

        if (emptyState) emptyState.style.display = "none";
        if (carsGrid) carsGrid.style.display = "grid";

        // Aplica o Auto-Fit calculando cols, rows e density
        applyGridAutoFit(total);

        // Preenche os cards na grade
        if (carsGrid) {
            carsGrid.innerHTML = "";
            sortedCars.forEach(car => {
                const cardEl = createCarCard(car);
                carsGrid.appendChild(cardEl);
            });
        }
    }

    function applyGridAutoFit(total) {
        if (!carsGrid || !gridWrapper) return;
        const w = gridWrapper.clientWidth || window.innerWidth;
        const h = gridWrapper.clientHeight || (window.innerHeight - 150);

        const { cols, rows, density } = calculateOptimalGrid(total, w, h);

        carsGrid.style.setProperty("--grid-cols", cols);
        carsGrid.style.setProperty("--grid-rows", rows);
        carsGrid.setAttribute("data-density", density);
    }

    // Criar Card do Veículo em Destaque
    function createCarCard(car) {
        const card = document.createElement("article");
        const phase = resolvePhase(car.status_display || car.status);

        card.className = `tv-card ${phase.cssClass}`;
        card.dataset.carId = car.id;
        card.dataset.phase = phase.key;

        const plateFmt = car.plate_display || car.plate || "SEM PLACA";
        const boxBadge = car.box_mecanico || car.mechanic_name
            ? `<span class="tv-card-box-badge">📍 ${escapeHtml(car.box_mecanico || car.mechanic_name)}</span>`
            : "";

        const notesHtml = car.notes
            ? `<div class="tv-card-notes" title="${escapeHtml(car.notes)}">📋 ${escapeHtml(car.notes)}</div>`
            : "";

        let thirdPartyHtml = "";
        const isThirdParty = phase.key === "terceiro" || /terceir/i.test(car.status || "");
        if (isThirdParty) {
            const authName = car.authorized_name || car.third_party_name || "Pessoa Autorizada";
            const authDoc = car.authorized_doc || car.third_party_doc || "";
            thirdPartyHtml = `
                <div class="tv-third-party-alert">
                    <div class="tv-third-party-header">
                        <span class="pulse-gold">🔑</span>
                        <span>RETIRADA AUTORIZADA P/ TERCEIRO</span>
                    </div>
                    <div class="tv-third-party-name">${escapeHtml(authName)}</div>
                    ${authDoc ? `<div class="tv-third-party-doc">Doc / CPF: <strong>${escapeHtml(authDoc)}</strong></div>` : ""}
                </div>
            `;
        }

        const modelText = car.car_model || "Veículo";
        const colorText = car.car_color ? `<span>• ${escapeHtml(car.car_color)}</span>` : "";
        const yearText = car.car_year ? `<span>• ${escapeHtml(car.car_year)}</span>` : "";
        const clientText = car.client_name ? `👤 ${escapeHtml(car.client_name)}` : "👤 Cliente da Oficina";

        // Exibição do horário da última atualização
        let timeFormatted = "";
        if (car.updated_at || car.updated_time) {
            const rawTime = car.updated_at || car.updated_time;
            try {
                const parts = rawTime.split(" ");
                timeFormatted = parts.length > 1 ? parts[1].substring(0, 5) : rawTime;
            } catch (e) {
                timeFormatted = "";
            }
        }

        card.innerHTML = `
            <div class="tv-card-top-row">
                <span class="tv-phase-badge ${phase.badgeClass}">
                    <span>${phase.icon}</span>
                    <span>${escapeHtml(car.status_display || phase.label)}</span>
                </span>
                ${boxBadge}
            </div>

            <div class="tv-card-vehicle-row">
                <span class="tv-plate-tag">${escapeHtml(plateFmt)}</span>
                <div class="tv-vehicle-info">
                    <div class="tv-card-model" title="${escapeHtml(modelText)}">${escapeHtml(modelText)}</div>
                    <div class="tv-card-meta">
                        ${colorText}
                        ${yearText}
                    </div>
                </div>
            </div>

            <div class="tv-card-body">
                <div class="tv-card-client" title="${escapeHtml(clientText)}">${clientText}</div>
                ${notesHtml}
                ${thirdPartyHtml}
            </div>

            <div class="tv-card-footer">
                <span>${timeFormatted ? `Atualizado às ${timeFormatted}` : "No pátio"}</span>
                <span class="tv-card-edit-hint">✎ Editar</span>
            </div>
        `;

        card.addEventListener("click", () => openEditModal(car));
        return card;
    }

    // Modal de Adicionar / Editar Carro no Pátio
    if (btnOpenManageModal) {
        btnOpenManageModal.addEventListener("click", openNewModal);
    }
    if (btnEmptyAddCar) {
        btnEmptyAddCar.addEventListener("click", openNewModal);
    }

    function openNewModal() {
        if (modalForm) modalForm.reset();
        const titleEl = document.getElementById("tv-modal-title");
        if (titleEl) titleEl.textContent = "🚗 Adicionar Carro ao Pátio";
        const carIdInput = document.getElementById("form-car-id");
        if (carIdInput) carIdInput.value = "";
        if (btnDeleteCar) btnDeleteCar.style.display = "none";
        toggleThirdPartyFields();
        if (modalBackdrop) modalBackdrop.style.display = "flex";
        const plateInput = document.getElementById("form-plate");
        if (plateInput) plateInput.focus();
    }

    function openEditModal(car) {
        if (modalForm) modalForm.reset();
        const titleEl = document.getElementById("tv-modal-title");
        if (titleEl) titleEl.textContent = `🚗 Gerenciar: ${car.plate_display || car.plate}`;

        setVal("form-car-id", car.id);
        setVal("form-plate", car.plate_display || car.plate);
        setVal("form-client", car.client_name || "");
        setVal("form-model", car.car_model || "");
        setVal("form-color", car.car_color || "");
        setVal("form-box", car.box_mecanico || car.mechanic_name || "");
        setVal("form-notes", car.notes || "");
        setVal("form-auth-name", car.authorized_name || car.third_party_name || "");
        setVal("form-auth-doc", car.authorized_doc || car.third_party_doc || "");
        setVal("form-auth-phone", car.authorized_phone || car.third_party_phone || "");

        // Selecionar status compatível no select
        if (selectStatus) {
            const rawStatus = car.status_display || car.status || "";
            let matched = false;
            for (let i = 0; i < selectStatus.options.length; i++) {
                if (selectStatus.options[i].value === rawStatus || selectStatus.options[i].value === car.status) {
                    selectStatus.selectedIndex = i;
                    matched = true;
                    break;
                }
            }
            if (!matched) {
                // Tenta resolver por fase
                const phase = resolvePhase(rawStatus);
                for (let i = 0; i < selectStatus.options.length; i++) {
                    if (phase.matcher(selectStatus.options[i].value)) {
                        selectStatus.selectedIndex = i;
                        break;
                    }
                }
            }
        }

        if (btnDeleteCar) btnDeleteCar.style.display = "block";
        toggleThirdPartyFields();
        if (modalBackdrop) modalBackdrop.style.display = "flex";
    }

    function setVal(id, val) {
        const el = document.getElementById(id);
        if (el) el.value = val !== undefined && val !== null ? val : "";
    }

    function closeModal() {
        if (modalBackdrop) modalBackdrop.style.display = "none";
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeModal);
    if (btnCancelModal) btnCancelModal.addEventListener("click", closeModal);

    // Fechar ao clicar fora do diálogo
    if (modalBackdrop) {
        modalBackdrop.addEventListener("click", (e) => {
            if (e.target === modalBackdrop) {
                closeModal();
            }
        });
    }

    // Alternar campos de terceiro
    function toggleThirdPartyFields() {
        if (selectStatus && thirdPartySection) {
            const isThird = /terceir/i.test(selectStatus.value);
            thirdPartySection.style.display = isThird ? "flex" : "none";
        }
    }
    if (selectStatus) {
        selectStatus.addEventListener("change", toggleThirdPartyFields);
    }

    // Submissão do Formulário de Carro
    if (modalForm) {
        modalForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const carId = (document.getElementById("form-car-id") || {}).value;
            const payload = {
                id: carId ? parseInt(carId, 10) : null,
                plate: ((document.getElementById("form-plate") || {}).value || "").trim().toUpperCase(),
                client_name: ((document.getElementById("form-client") || {}).value || "").trim(),
                car_model: ((document.getElementById("form-model") || {}).value || "").trim(),
                car_color: ((document.getElementById("form-color") || {}).value || "").trim(),
                status: (document.getElementById("form-status") || {}).value,
                box_mecanico: ((document.getElementById("form-box") || {}).value || "").trim(),
                notes: ((document.getElementById("form-notes") || {}).value || "").trim(),
                authorized_name: ((document.getElementById("form-auth-name") || {}).value || "").trim(),
                authorized_doc: ((document.getElementById("form-auth-doc") || {}).value || "").trim(),
                authorized_phone: ((document.getElementById("form-auth-phone") || {}).value || "").trim()
            };

            try {
                const res = await fetch("/api/patio", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const resData = await res.json();
                if (resData.success) {
                    showToast("✅ Veículo salvo no pátio com sucesso!");
                    closeModal();
                    fetchPatioData();
                } else {
                    alert("Erro ao salvar: " + (resData.error || "Tente novamente"));
                }
            } catch (err) {
                alert("Erro ao conectar com o servidor: " + err.message);
            }
        });
    }

    // Exclusão / Baixa do Carro
    if (btnDeleteCar) {
        btnDeleteCar.addEventListener("click", async () => {
            const carIdInput = document.getElementById("form-car-id");
            const carId = carIdInput ? carIdInput.value : null;
            if (!carId) return;
            if (confirm("Confirmar a saída / baixa deste veículo do pátio?")) {
                try {
                    const res = await fetch(`/api/patio/${carId}`, { method: "DELETE" });
                    const resData = await res.json();
                    if (resData.success) {
                        showToast("🚗 Veículo removido do pátio com sucesso!");
                        closeModal();
                        fetchPatioData();
                    }
                } catch (err) {
                    alert("Erro ao remover: " + err.message);
                }
            }
        });
    }

    // Toast de Notificação
    function showToast(msg) {
        const toast = document.getElementById("tv-toast");
        if (toast) {
            toast.textContent = msg;
            toast.style.display = "block";
            setTimeout(() => {
                toast.style.display = "none";
            }, 3000);
        }
    }

    function escapeHtml(text) {
        if (!text) return "";
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Recalcular layout ao redimensionar a tela
    window.addEventListener("resize", () => {
        if (patioData && patioData.cars && patioData.cars.length > 0) {
            applyGridAutoFit(patioData.cars.length);
        }
    });

    // Inicialização do Polling (a cada 5 segundos)
    fetchPatioData();
    pollInterval = setInterval(fetchPatioData, 5000);
});
