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
    
    // Tabs Navigation Elements (Issue #15)
    const tabBtnPatio = document.getElementById("tab-btn-patio");
    const tabBtnCalendar = document.getElementById("tab-btn-calendar");
    const tvPatioView = document.getElementById("tv-patio-view");
    const tvCalendarView = document.getElementById("tv-calendar-view");
    const tabPatioCount = document.getElementById("tab-patio-count");
    const tabCalendarCount = document.getElementById("tab-calendar-count");
    const btnOpenAgendamentoModal = document.getElementById("btn-open-agendamento-modal");
    const btnCalNewAppointment = document.getElementById("btn-cal-new-appointment");
    const tvCounterIcon = document.getElementById("tv-counter-icon");
    const tvCounterLabel = document.getElementById("tv-counter-label");

    // Modal Agendamento Elements
    const agendamentoModal = document.getElementById("tv-agendamento-modal");
    const btnCloseAgendamentoModal = document.getElementById("btn-close-agendamento-modal");
    const btnCancelAgendaModal = document.getElementById("btn-cancel-agenda-modal");
    const formAgendamento = document.getElementById("tv-agendamento-form");
    const btnDeleteAgendamento = document.getElementById("btn-delete-agendamento");
    const formAgendaId = document.getElementById("form-agenda-id");
    const formAgendaClient = document.getElementById("form-agenda-client");
    const formAgendaPhone = document.getElementById("form-agenda-phone");
    const formAgendaPlate = document.getElementById("form-agenda-plate");
    const formAgendaModel = document.getElementById("form-agenda-model");
    const formAgendaDate = document.getElementById("form-agenda-date");
    const formAgendaTime = document.getElementById("form-agenda-time");
    const formAgendaStatus = document.getElementById("form-agenda-status");
    const formAgendaTitle = document.getElementById("form-agenda-title");
    const formAgendaDesc = document.getElementById("form-agenda-desc");
    const formAgendaNotes = document.getElementById("form-agenda-notes");
    const tvAgendamentoModalTitle = document.getElementById("tv-agendamento-modal-title");

    // Calendar Navigation & Filters
    const btnCalPrev = document.getElementById("btn-cal-prev");
    const btnCalToday = document.getElementById("btn-cal-today");
    const btnCalNext = document.getElementById("btn-cal-next");
    const tvCalCurrentLabel = document.getElementById("tv-cal-current-label");
    const filterBtnToday = document.getElementById("filter-btn-today");
    const filterBtnWeek = document.getElementById("filter-btn-week");
    const filterBtnAll = document.getElementById("filter-btn-all");
    const badgeCalToday = document.getElementById("badge-cal-today");
    const badgeCalWeek = document.getElementById("badge-cal-week");
    const badgeCalAll = document.getElementById("badge-cal-all");
    const tvCalGrid = document.getElementById("tv-cal-grid");
    const tvCalEmpty = document.getElementById("tv-cal-empty");

    // Estado do Calendário
    let activeTab = "patio"; // "patio" ou "calendar"
    let agendamentosData = [];
    let calendarFilter = "today"; // "today", "week", "all"
    let calendarCurrentDate = new Date();

    // Modal Elements Patio
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
        if (totalCarsEl && activeTab === "patio") totalCarsEl.textContent = data.total || 0;
        if (tabPatioCount) tabPatioCount.textContent = data.total || 0;

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
            const stName = car.status_display || car.status;
            let container = document.getElementById(`cards-${stName}`);
            if (!container) {
                container = document.getElementById(`cards-${car.status}`);
            }
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

    // =========================================================================
    // NAVEGAÇÃO DE ABAS DA TV (Issue #15)
    // =========================================================================
    function switchTab(tabName) {
        activeTab = tabName;
        if (tabName === "calendar") {
            if (tabBtnCalendar) tabBtnCalendar.classList.add("active");
            if (tabBtnPatio) tabBtnPatio.classList.remove("active");
            if (tvCalendarView) tvCalendarView.style.display = "flex";
            if (tvPatioView) tvPatioView.style.display = "none";
            if (btnOpenManageModal) btnOpenManageModal.style.display = "none";
            if (btnOpenAgendamentoModal) btnOpenAgendamentoModal.style.display = "inline-flex";
            if (tvCounterIcon) tvCounterIcon.textContent = "📅";
            if (tvCounterLabel) tvCounterLabel.textContent = "agendados";
            renderCalendar();
            if (totalCarsEl) totalCarsEl.textContent = agendamentosData.length;
        } else {
            if (tabBtnPatio) tabBtnPatio.classList.add("active");
            if (tabBtnCalendar) tabBtnCalendar.classList.remove("active");
            if (tvPatioView) tvPatioView.style.display = "flex";
            if (tvCalendarView) tvCalendarView.style.display = "none";
            if (btnOpenManageModal) btnOpenManageModal.style.display = "inline-flex";
            if (btnOpenAgendamentoModal) btnOpenAgendamentoModal.style.display = "none";
            if (tvCounterIcon) tvCounterIcon.textContent = "🚗";
            if (tvCounterLabel) tvCounterLabel.textContent = "no pátio";
            if (totalCarsEl) totalCarsEl.textContent = patioData.total || 0;
        }
    }

    if (tabBtnPatio) {
        tabBtnPatio.addEventListener("click", () => switchTab("patio"));
    }
    if (tabBtnCalendar) {
        tabBtnCalendar.addEventListener("click", () => switchTab("calendar"));
    }

    // =========================================================================
    // CALENDÁRIO DE AGENDAMENTOS (Issue #15)
    // =========================================================================
    function formatLocalDateIso(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    }

    async function fetchAgendamentosData() {
        try {
            const res = await fetch("/api/agendamentos");
            if (!res.ok) throw new Error("Erro na requisição /api/agendamentos");
            const data = await res.json();
            if (data.success) {
                agendamentosData = data.agendamentos || [];
                if (tabCalendarCount) tabCalendarCount.textContent = data.today_count || 0;
                renderCalendar();
                if (activeTab === "calendar" && totalCarsEl) {
                    totalCarsEl.textContent = agendamentosData.length;
                }
            }
        } catch (err) {
            console.error("Erro atualizando agendamentos da TV:", err);
        }
    }

    function renderCalendar() {
        const today = new Date();
        const todayIso = formatLocalDateIso(today);

        const next7 = new Date();
        next7.setDate(today.getDate() + 7);
        const next7Iso = formatLocalDateIso(next7);

        // Contadores
        const todayCount = agendamentosData.filter(a => a.scheduled_date_iso === todayIso).length;
        const weekCount = agendamentosData.filter(a => {
            const d = a.scheduled_date_iso;
            return d >= todayIso && d <= next7Iso;
        }).length;

        if (badgeCalToday) badgeCalToday.textContent = todayCount;
        if (badgeCalWeek) badgeCalWeek.textContent = weekCount;
        if (badgeCalAll) badgeCalAll.textContent = agendamentosData.length;

        // Label do período
        if (tvCalCurrentLabel) {
            if (calendarFilter === "today") {
                const isRealToday = formatLocalDateIso(calendarCurrentDate) === todayIso;
                const dateStr = calendarCurrentDate.toLocaleDateString("pt-BR", {
                    weekday: "long",
                    day: "2-digit",
                    month: "long",
                    year: "numeric"
                });
                tvCalCurrentLabel.textContent = (isRealToday ? "Hoje • " : "") + dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
            } else if (calendarFilter === "week") {
                tvCalCurrentLabel.textContent = `Próximos 7 Dias (até ${next7.toLocaleDateString("pt-BR")})`;
            } else {
                tvCalCurrentLabel.textContent = `Todos os Agendamentos (${agendamentosData.length})`;
            }
        }

        // Filtra os itens
        let filtered = [];
        if (calendarFilter === "today") {
            const targetIso = formatLocalDateIso(calendarCurrentDate);
            filtered = agendamentosData.filter(a => a.scheduled_date_iso === targetIso);
        } else if (calendarFilter === "week") {
            filtered = agendamentosData.filter(a => {
                const d = a.scheduled_date_iso;
                return d >= todayIso && d <= next7Iso;
            });
        } else {
            filtered = [...agendamentosData];
        }

        if (tvCalGrid && tvCalEmpty) {
            tvCalGrid.innerHTML = "";
            if (filtered.length === 0) {
                tvCalEmpty.style.display = "flex";
            } else {
                tvCalEmpty.style.display = "none";
                filtered.forEach(ag => {
                    const card = createAgendamentoCard(ag);
                    tvCalGrid.appendChild(card);
                });
            }
        }
    }

    function createAgendamentoCard(ag) {
        const card = document.createElement("div");
        const statusClass = `status-${ag.status || 'agendado'}`;
        card.className = `tv-agenda-card ${statusClass}`;

        const statusLabels = {
            agendado: "🕒 Agendado",
            confirmado: "👍 Confirmado",
            concluido: "✅ Atendido",
            cancelado: "❌ Cancelado"
        };
        const statusBadgeClass = `tv-badge-${ag.status || 'agendado'}`;
        const statusLabel = statusLabels[ag.status] || ag.status;
        const plateDisp = ag.car_plate_display || ag.car_plate || "SEM PLACA";

        card.innerHTML = `
            <div class="tv-card-top-row">
                <div class="tv-card-time-box">
                    <span class="tv-card-time">${escapeHtml(ag.scheduled_time || '08:00')}</span>
                    <span class="tv-card-date-badge">${escapeHtml(ag.scheduled_date_display || ag.scheduled_date)}</span>
                </div>
                <span class="tv-card-status-badge ${statusBadgeClass}">${statusLabel}</span>
            </div>

            <div class="tv-card-vehicle-row">
                <span class="tv-card-plate-badge">${escapeHtml(plateDisp)}</span>
                <span class="tv-card-model">${escapeHtml(ag.car_model || 'Veículo')}</span>
            </div>

            <div class="tv-card-client-row">
                <span class="tv-card-client-name">👤 ${escapeHtml(ag.client_name)}</span>
                <span class="tv-card-client-phone">📞 ${escapeHtml(ag.phone || 'S/ Tel')}</span>
            </div>

            <div class="tv-card-issue-box">
                <div class="tv-card-issue-title">🔧 ${escapeHtml(ag.title)}</div>
                ${ag.description ? `<div class="tv-card-issue-desc">${escapeHtml(ag.description)}</div>` : ''}
            </div>

            ${ag.notes ? `<div style="font-size: 11px; color: #cbd5e1; font-style: italic;">📝 ${escapeHtml(ag.notes)}</div>` : ''}

            <div class="tv-card-actions">
                ${ag.status !== 'confirmado' && ag.status !== 'concluido' ? `
                    <button type="button" class="tv-card-btn tv-card-btn-confirm" data-id="${ag.id}" title="Confirmar Agendamento">
                        👍 Confirmar
                    </button>
                ` : ''}
                <button type="button" class="tv-card-btn tv-card-btn-edit" data-id="${ag.id}" title="Editar Detalhes">
                    ✏️ Detalhes / Editar
                </button>
            </div>
        `;

        const btnConfirm = card.querySelector(".tv-card-btn-confirm");
        if (btnConfirm) {
            btnConfirm.addEventListener("click", async (e) => {
                e.stopPropagation();
                await updateAgendamentoStatus(ag.id, "confirmado");
            });
        }

        const btnEdit = card.querySelector(".tv-card-btn-edit");
        if (btnEdit) {
            btnEdit.addEventListener("click", (e) => {
                e.stopPropagation();
                openAgendamentoModal(ag);
            });
        }

        card.addEventListener("click", () => {
            openAgendamentoModal(ag);
        });

        return card;
    }

    async function updateAgendamentoStatus(id, newStatus) {
        try {
            const res = await fetch(`/api/agendamentos/${id}/status`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: newStatus })
            });
            const data = await res.json();
            if (data.success) {
                showToast(`Agendamento atualizado para ${newStatus}!`);
                fetchAgendamentosData();
            }
        } catch (err) {
            console.error("Erro alterando status:", err);
        }
    }

    // Navegação de Datas no Calendário
    if (btnCalPrev) {
        btnCalPrev.addEventListener("click", () => {
            calendarCurrentDate.setDate(calendarCurrentDate.getDate() - 1);
            calendarFilter = "today";
            updateFilterButtons();
            renderCalendar();
        });
    }

    if (btnCalToday) {
        btnCalToday.addEventListener("click", () => {
            calendarCurrentDate = new Date();
            calendarFilter = "today";
            updateFilterButtons();
            renderCalendar();
        });
    }

    if (btnCalNext) {
        btnCalNext.addEventListener("click", () => {
            calendarCurrentDate.setDate(calendarCurrentDate.getDate() + 1);
            calendarFilter = "today";
            updateFilterButtons();
            renderCalendar();
        });
    }

    function updateFilterButtons() {
        [filterBtnToday, filterBtnWeek, filterBtnAll].forEach(btn => {
            if (btn) {
                if (btn.dataset.filter === calendarFilter) {
                    btn.classList.add("active");
                } else {
                    btn.classList.remove("active");
                }
            }
        });
    }

    if (filterBtnToday) {
        filterBtnToday.addEventListener("click", () => {
            calendarFilter = "today";
            updateFilterButtons();
            renderCalendar();
        });
    }
    if (filterBtnWeek) {
        filterBtnWeek.addEventListener("click", () => {
            calendarFilter = "week";
            updateFilterButtons();
            renderCalendar();
        });
    }
    if (filterBtnAll) {
        filterBtnAll.addEventListener("click", () => {
            calendarFilter = "all";
            updateFilterButtons();
            renderCalendar();
        });
    }

    // Modal de Agendamento
    function openAgendamentoModal(ag = null) {
        if (!agendamentoModal) return;
        if (formAgendamento) formAgendamento.reset();

        const todayIso = formatLocalDateIso(new Date());

        if (ag) {
            if (tvAgendamentoModalTitle) tvAgendamentoModalTitle.textContent = "✏️ Editar Agendamento na TV";
            if (formAgendaId) formAgendaId.value = ag.id;
            if (formAgendaClient) formAgendaClient.value = ag.client_name || "";
            if (formAgendaPhone) formAgendaPhone.value = ag.phone || "";
            if (formAgendaPlate) formAgendaPlate.value = ag.car_plate || "";
            if (formAgendaModel) formAgendaModel.value = ag.car_model || "";
            if (formAgendaDate) formAgendaDate.value = ag.scheduled_date_iso || ag.scheduled_date || todayIso;
            if (formAgendaTime) formAgendaTime.value = ag.scheduled_time || "08:30";
            if (formAgendaStatus) formAgendaStatus.value = ag.status || "agendado";
            if (formAgendaTitle) formAgendaTitle.value = ag.title || "";
            if (formAgendaDesc) formAgendaDesc.value = ag.description || "";
            if (formAgendaNotes) formAgendaNotes.value = ag.notes || "";
            if (btnDeleteAgendamento) btnDeleteAgendamento.style.display = "inline-flex";
        } else {
            if (tvAgendamentoModalTitle) tvAgendamentoModalTitle.textContent = "📅 Agendar Atendimento na Oficina";
            if (formAgendaId) formAgendaId.value = "";
            if (formAgendaDate) formAgendaDate.value = formatLocalDateIso(calendarCurrentDate);
            if (formAgendaTime) formAgendaTime.value = "08:30";
            if (formAgendaStatus) formAgendaStatus.value = "agendado";
            if (btnDeleteAgendamento) btnDeleteAgendamento.style.display = "none";
        }

        agendamentoModal.style.display = "flex";
        setTimeout(() => {
            if (formAgendaClient) formAgendaClient.focus();
        }, 100);
    }

    function closeAgendamentoModal() {
        if (agendamentoModal) agendamentoModal.style.display = "none";
    }

    if (btnOpenAgendamentoModal) {
        btnOpenAgendamentoModal.addEventListener("click", () => openAgendamentoModal());
    }
    if (btnCalNewAppointment) {
        btnCalNewAppointment.addEventListener("click", () => openAgendamentoModal());
    }
    if (btnCloseAgendamentoModal) {
        btnCloseAgendamentoModal.addEventListener("click", closeAgendamentoModal);
    }
    if (btnCancelAgendaModal) {
        btnCancelAgendaModal.addEventListener("click", closeAgendamentoModal);
    }

    // Form Submit Agendamento
    if (formAgendamento) {
        formAgendamento.addEventListener("submit", async (e) => {
            e.preventDefault();
            const agId = formAgendaId.value;
            const payload = {
                client_name: formAgendaClient.value.trim(),
                phone: formAgendaPhone.value.trim(),
                car_plate: formAgendaPlate.value.trim().toUpperCase(),
                car_model: formAgendaModel.value.trim(),
                scheduled_date: formAgendaDate.value,
                scheduled_time: formAgendaTime.value,
                status: formAgendaStatus.value,
                title: formAgendaTitle.value.trim(),
                description: formAgendaDesc.value.trim(),
                notes: formAgendaNotes.value.trim()
            };

            try {
                let url = "/api/agendamentos";
                let method = "POST";
                if (agId) {
                    url = `/api/agendamentos/${agId}`;
                    method = "PUT";
                }

                const res = await fetch(url, {
                    method: method,
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    showToast(agId ? "✅ Agendamento atualizado!" : "📅 Agendamento salvo com sucesso!");
                    closeAgendamentoModal();
                    fetchAgendamentosData();
                } else {
                    alert("Erro ao salvar agendamento: " + (data.error || "Erro desconhecido"));
                }
            } catch (err) {
                alert("Erro ao conectar com servidor: " + err.message);
            }
        });
    }

    // Excluir Agendamento
    if (btnDeleteAgendamento) {
        btnDeleteAgendamento.addEventListener("click", async () => {
            const agId = formAgendaId.value;
            if (!agId) return;
            if (confirm("Deseja realmente excluir este agendamento?")) {
                try {
                    const res = await fetch(`/api/agendamentos/${agId}`, { method: "DELETE" });
                    const data = await res.json();
                    if (data.success) {
                        showToast("🗑️ Agendamento excluído.");
                        closeAgendamentoModal();
                        fetchAgendamentosData();
                    } else {
                        alert("Erro: " + (data.error || "Não foi possível excluir"));
                    }
                } catch (err) {
                    alert("Erro ao excluir: " + err.message);
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
    fetchAgendamentosData();
    pollInterval = setInterval(() => {
        fetchPatioData();
        fetchAgendamentosData();
    }, 5000);
});

