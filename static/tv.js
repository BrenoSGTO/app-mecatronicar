/**
 * MecatroniCar v2.0 - tv.js
 * Painel de TV / Monitoramento do Pátio ao Vivo (CP-06)
 */

document.addEventListener("DOMContentLoaded", () => {
    // Estado da TV
    let patioData = { total: 0, by_status: {}, cars: [] };
    let previousCarStatuses = {};
    let soundEnabled = false;
    let pollInterval = null;

    // Elementos DOM
    const clockTimeEl = document.getElementById("tv-clock-time");
    const clockDateEl = document.getElementById("tv-clock-date");
    const totalCarsEl = document.getElementById("tv-total-cars");
    const btnToggleSound = document.getElementById("btn-toggle-sound");
    const soundIcon = document.getElementById("sound-icon");
    const btnFullscreen = document.getElementById("btn-fullscreen");
    const btnOpenManageModal = document.getElementById("btn-open-manage-modal");
    
    // Modal Elements
    const modalBackdrop = document.getElementById("tv-manage-modal");
    const modalCloseBtn = document.getElementById("tv-modal-close-btn");
    const btnCancelModal = document.getElementById("btn-cancel-modal");
    const modalForm = document.getElementById("tv-manage-form");
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

    // Áudio com Web Audio API para alertas na oficina
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
            console.warn("Audio Context blocked or not allowed:", e);
        }
    }

    // Toggle de Som
    if (btnToggleSound) {
        btnToggleSound.addEventListener("click", () => {
            soundEnabled = !soundEnabled;
            if (soundEnabled) {
                soundIcon.textContent = "🔊";
                btnToggleSound.classList.add("tv-btn-primary");
                showToast("🔔 Aviso sonoro ativado!");
                playStatusChangeChime();
            } else {
                soundIcon.textContent = "🔔";
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

    // Carregar e Atualizar Pátio (Polling)
    async function fetchPatioData() {
        try {
            const res = await fetch("/api/patio");
            if (!res.ok) throw new Error("Erro na requisição /api/patio");
            const data = await res.json();
            if (data.success) {
                checkStatusChanges(data.cars);
                patioData = data;
                renderBoard(data);
            }
        } catch (err) {
            console.error("Erro atualizando pátio da TV:", err);
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
        }
        previousCarStatuses = currentMap;
    }

    // Renderizar Colunas e Cards
    function renderBoard(data) {
        if (totalCarsEl) totalCarsEl.textContent = data.total || 0;

        const statuses = [
            "Em Diagnóstico",
            "Esperando Orçamento",
            "Esperando Aprovação",
            "Esperando Peças",
            "Em Execução",
            "Esperando Cliente Buscar",
            "Liberado p/ Retirada por Terceiro"
        ];

        // Limpa todas as colunas
        statuses.forEach(st => {
            const container = document.getElementById(`cards-${st}`);
            const badge = document.getElementById(`badge-${st}`);
            if (container) container.innerHTML = "";
            if (badge) badge.textContent = (data.by_status && data.by_status[st]) || 0;
        });

        // Preenche com os carros
        (data.cars || []).forEach(car => {
            const container = document.getElementById(`cards-${car.status}`);
            if (container) {
                const cardEl = createCarCard(car);
                container.appendChild(cardEl);
            }
        });
    }

    function createCarCard(car) {
        const card = document.createElement("div");
        card.className = "tv-card";
        card.dataset.carId = car.id;

        const plateFmt = car.plate_display || car.plate || "SEM PLACA";
        const boxBadge = car.box_mecanico ? `<span class="tv-card-box-badge">${escapeHtml(car.box_mecanico)}</span>` : "";
        const notesHtml = car.notes ? `<div class="tv-card-notes">${escapeHtml(car.notes)}</div>` : "";

        let thirdPartyHtml = "";
        if (car.status === "Liberado p/ Retirada por Terceiro" && car.authorized_name) {
            thirdPartyHtml = `
                <div class="tv-third-party-alert">
                    <span class="tv-third-party-label">🔑 AUTORIZADO A RETIRAR</span>
                    <span class="tv-third-party-name">${escapeHtml(car.authorized_name)}</span>
                    ${car.authorized_doc ? `<span class="tv-third-party-doc">Doc: ${escapeHtml(car.authorized_doc)}</span>` : ""}
                </div>
            `;
        }

        card.innerHTML = `
            <div class="tv-card-header">
                <span class="tv-plate-tag">${escapeHtml(plateFmt)}</span>
                ${boxBadge}
            </div>
            <div class="tv-card-car-model">${escapeHtml(car.car_model || "Veículo")}</div>
            <div class="tv-card-meta">
                <span>${escapeHtml(car.car_color || "")}</span>
                <span>${escapeHtml(car.car_year || "")}</span>
            </div>
            <div class="tv-card-client">👤 ${escapeHtml(car.client_name || "Cliente")}</div>
            ${notesHtml}
            ${thirdPartyHtml}
        `;

        card.addEventListener("click", () => openEditModal(car));
        return card;
    }

    // Modal de Adicionar / Editar Carro no Pátio
    if (btnOpenManageModal) {
        btnOpenManageModal.addEventListener("click", () => {
            openNewModal();
        });
    }

    function openNewModal() {
        modalForm.reset();
        document.getElementById("tv-modal-title").textContent = "Adicionar Veículo ao Pátio";
        document.getElementById("form-car-id").value = "";
        btnDeleteCar.style.display = "none";
        toggleThirdPartyFields();
        modalBackdrop.style.display = "flex";
        document.getElementById("form-plate").focus();
    }

    function openEditModal(car) {
        modalForm.reset();
        document.getElementById("tv-modal-title").textContent = `Gerenciar: ${car.plate_display || car.plate}`;
        document.getElementById("form-car-id").value = car.id;
        document.getElementById("form-plate").value = car.plate_display || car.plate;
        document.getElementById("form-client").value = car.client_name || "";
        document.getElementById("form-model").value = car.car_model || "";
        document.getElementById("form-color").value = car.car_color || "";
        document.getElementById("form-status").value = car.status;
        document.getElementById("form-box").value = car.box_mecanico || "";
        document.getElementById("form-notes").value = car.notes || "";
        document.getElementById("form-auth-name").value = car.authorized_name || "";
        document.getElementById("form-auth-doc").value = car.authorized_doc || "";
        document.getElementById("form-auth-phone").value = car.authorized_phone || "";

        btnDeleteCar.style.display = "block";
        toggleThirdPartyFields();
        modalBackdrop.style.display = "flex";
    }

    function closeModal() {
        modalBackdrop.style.display = "none";
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeModal);
    if (btnCancelModal) btnCancelModal.addEventListener("click", closeModal);

    // Alternar campos de terceiro
    function toggleThirdPartyFields() {
        if (selectStatus && thirdPartySection) {
            if (selectStatus.value === "Liberado p/ Retirada por Terceiro") {
                thirdPartySection.style.display = "flex";
            } else {
                thirdPartySection.style.display = "none";
            }
        }
    }
    if (selectStatus) {
        selectStatus.addEventListener("change", toggleThirdPartyFields);
    }

    // Submissão do Formulário
    if (modalForm) {
        modalForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const carId = document.getElementById("form-car-id").value;
            const payload = {
                id: carId ? parseInt(carId) : null,
                plate: document.getElementById("form-plate").value.trim().toUpperCase(),
                client_name: document.getElementById("form-client").value.trim(),
                car_model: document.getElementById("form-model").value.trim(),
                car_color: document.getElementById("form-color").value.trim(),
                status: document.getElementById("form-status").value,
                box_mecanico: document.getElementById("form-box").value.trim(),
                notes: document.getElementById("form-notes").value.trim(),
                authorized_name: document.getElementById("form-auth-name").value.trim(),
                authorized_doc: document.getElementById("form-auth-doc").value.trim(),
                authorized_phone: document.getElementById("form-auth-phone").value.trim()
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

    // Exclusão / Baixa
    if (btnDeleteCar) {
        btnDeleteCar.addEventListener("click", async () => {
            const carId = document.getElementById("form-car-id").value;
            if (!carId) return;
            if (confirm("Confirmar a saída / baixa deste veículo do pátio?")) {
                try {
                    const res = await fetch(`/api/patio/${carId}`, { method: "DELETE" });
                    const resData = await res.json();
                    if (resData.success) {
                        showToast("🚗 Veículo removido do pátio!");
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

    // Inicialização do Polling (a cada 5 segundos)
    fetchPatioData();
    pollInterval = setInterval(fetchPatioData, 5000);
});
