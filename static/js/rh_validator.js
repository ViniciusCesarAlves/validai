/**
 * ValidAí - Auditoria de Folha e RH
 * Controlador Frontend Especializado em Recursos Humanos, Folha e Benefícios Corporativos
 */

(function () {
    let currentSessionId = null;
    let currentReportId = null;
    let currentMode = 'folha'; // 'folha' ou 'beneficios'
    let selectedRefFile = null;
    let selectedAuditFile = null;
    let auditResults = null;

    let activeTab = 'summary';
    let searchQuery = '';

    // Tema gerenciado centralmente por header.html

    // Elementos do DOM - Passo 1
    const stepUpload = document.getElementById('step-upload-rh');
    const btnModeFolha = document.getElementById('btn-mode-folha');
    const btnModeBeneficios = document.getElementById('btn-mode-beneficios');
    const labelRefTitle = document.getElementById('label-ref-title');
    const labelRefDesc = document.getElementById('label-ref-desc');
    const labelAuditTitle = document.getElementById('label-audit-title');
    const labelAuditDesc = document.getElementById('label-audit-desc');

    const dropRefFile = document.getElementById('drop-ref-file');
    const fileRefInput = document.getElementById('file-ref-input');
    const fileMetaRef = document.getElementById('file-meta-ref');
    const filenameRef = document.getElementById('filename-ref');
    const filesizeRef = document.getElementById('filesize-ref');

    const dropAuditFile = document.getElementById('drop-audit-file');
    const fileAuditInput = document.getElementById('file-audit-input');
    const fileMetaAudit = document.getElementById('file-meta-audit');
    const filenameAudit = document.getElementById('filename-audit');
    const filesizeAudit = document.getElementById('filesize-audit');

    const btnTryExample = document.getElementById('btn-rh-try-example');
    const btnUpload = document.getElementById('btn-rh-upload');
    const uploadAlert = document.getElementById('rh-upload-alert');
    const uploadAlertMsg = document.getElementById('rh-upload-alert-msg');
    const btnCloseUploadAlert = document.getElementById('btn-close-rh-upload-alert');

    // Elementos do DOM - Passo 2
    const stepConfig = document.getElementById('step-config-rh');
    const infoRefName = document.getElementById('info-ref-name');
    const infoRefRows = document.getElementById('info-ref-rows');
    const infoAuditName = document.getElementById('info-audit-name');
    const infoAuditRows = document.getElementById('info-audit-rows');

    const selectKeyRef = document.getElementById('select-rh-key-ref');
    const selectKeyAudit = document.getElementById('select-rh-key-audit');
    const selectSecRef = document.getElementById('select-rh-sec-ref');
    const selectSecAudit = document.getElementById('select-rh-sec-audit');

    const chkNormCpf = document.getElementById('chk-norm-cpf');
    const chkIgnoreAccents = document.getElementById('chk-ignore-accents');
    const inputVariationThreshold = document.getElementById('input-variation-threshold');
    const presetVarButtons = document.querySelectorAll('.btn-preset-var');

    const tbodyMapping = document.getElementById('tbody-mapping-rh');
    const mappingSummaryCount = document.getElementById('mapping-summary-count');

    const btnBackStep1 = document.getElementById('btn-rh-back-step1');
    const btnProcess = document.getElementById('btn-process-rh');

    // Elementos do DOM - Passo 3
    const stepResults = document.getElementById('step-results-rh');
    const bannerSuccess = document.getElementById('rh-banner-success');
    const bannerDiffs = document.getElementById('rh-banner-diffs');
    const bannerDiffsTitle = document.getElementById('rh-banner-diffs-title');
    const bannerDiffsMsg = document.getElementById('rh-banner-diffs-msg');

    const kpiAuditedCount = document.getElementById('rh-kpi-audited-count');
    const kpiDivergenceVal = document.getElementById('rh-kpi-divergence-val');
    const kpiCriticalCount = document.getElementById('rh-kpi-critical-count');
    const kpiCriticalLabel = document.getElementById('rh-kpi-critical-label');
    const kpiExclusiveRef = document.getElementById('rh-kpi-exclusive-ref');
    const kpiEx1Label = document.getElementById('rh-kpi-ex1-label');
    const kpiExclusiveAudit = document.getElementById('rh-kpi-exclusive-audit');
    const kpiEx2Label = document.getElementById('rh-kpi-ex2-label');
    const kpiFinancialImpact = document.getElementById('rh-kpi-financial-impact');

    const btnDownloadAudit = document.getElementById('btn-rh-download-audit');

    const badgeSummary = document.getElementById('badge-rh-summary');
    const badgeDivergences = document.getElementById('badge-rh-divergences');
    const badgeEx1 = document.getElementById('badge-rh-ex1');
    const badgeEx2 = document.getElementById('badge-rh-ex2');
    const tabLabelEx1 = document.getElementById('tab-label-ex1');
    const tabLabelEx2 = document.getElementById('tab-label-ex2');

    const resultTabs = document.querySelectorAll('#rh-results-tabs .result-nav-tab-btn');
    const rhTableSearch = document.getElementById('rh-table-search');
    const rhTableTitle = document.getElementById('rh-table-title');

    const panelSummary = document.getElementById('panel-tab-summary');
    const panelDivergences = document.getElementById('panel-tab-divergences');
    const panelExRef = document.getElementById('panel-tab-exclusive_ref');
    const panelExAudit = document.getElementById('panel-tab-exclusive_audit');

    const tbodySummary = document.getElementById('tbody-rh-summary');
    const tbodyDivergences = document.getElementById('tbody-rh-divergences');
    const tbodyExRef = document.getElementById('tbody-rh-exclusive_ref');
    const tbodyExAudit = document.getElementById('tbody-rh-exclusive_audit');

    const hintDivergences = document.getElementById('hint-rh-divergences');
    const hintExRef = document.getElementById('hint-rh-exclusive_ref');
    const hintExAudit = document.getElementById('hint-rh-exclusive_audit');

    // Utilitário de escape de HTML
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function showUploadAlert(msg) {
        uploadAlertMsg.textContent = msg;
        uploadAlert.style.display = 'flex';
    }

    function hideUploadAlert() {
        uploadAlert.style.display = 'none';
        uploadAlertMsg.textContent = '';
    }

    if (btnCloseUploadAlert) {
        btnCloseUploadAlert.addEventListener('click', hideUploadAlert);
    }

    // -------------------------------------------------------------------------
    // 1. GESTÃO DE MODOS DE AUDITORIA (FOLHA vs BENEFÍCIOS)
    // -------------------------------------------------------------------------
    function updateModeUI(mode) {
        currentMode = mode;
        if (mode === 'beneficios') {
            btnModeBeneficios.classList.add('active');
            btnModeFolha.classList.remove('active');

            labelRefTitle.textContent = "Base de Ativos no RH";
            labelRefDesc.textContent = "Planilha oficial com lista de funcionários ativos (.xlsx, .xls ou .csv)";
            labelAuditTitle.textContent = "Fatura da Operadora de Benefícios";
            labelAuditDesc.textContent = "Relatório de cobrança (Plano de Saúde, VR/VA, Seguros) para auditar";

            if (kpiEx1Label) kpiEx1Label.textContent = "Ativos sem Fatura";
            if (kpiEx2Label) kpiEx2Label.textContent = "Cobrança Indevida (Fantasmas)";
            if (tabLabelEx1) tabLabelEx1.textContent = "Ativos sem Fatura no RH";
            if (tabLabelEx2) tabLabelEx2.textContent = "Cobrança Indevida / Fantasmas";
        } else {
            btnModeFolha.classList.add('active');
            btnModeBeneficios.classList.remove('active');

            labelRefTitle.textContent = "Base Referência (Folha Mês Anterior)";
            labelRefDesc.textContent = "Planilha da folha de pagamento do mês anterior (.xlsx, .xls ou .csv)";
            labelAuditTitle.textContent = "Base Auditada (Folha Mês Atual)";
            labelAuditDesc.textContent = "Planilha da folha de pagamento do mês atual para cruzamento";

            if (kpiEx1Label) kpiEx1Label.textContent = "Exclusivos Base 1 (Desligados)";
            if (kpiEx2Label) kpiEx2Label.textContent = "Exclusivos Base 2 (Admitidos)";
            if (tabLabelEx1) tabLabelEx1.textContent = "Exclusivos Base 1 (Desligados)";
            if (tabLabelEx2) tabLabelEx2.textContent = "Exclusivos Base 2 (Admitidos)";
        }
    }

    if (btnModeFolha) {
        btnModeFolha.addEventListener('click', () => updateModeUI('folha'));
    }
    if (btnModeBeneficios) {
        btnModeBeneficios.addEventListener('click', () => updateModeUI('beneficios'));
    }

    // -------------------------------------------------------------------------
    // 2. GESTÃO DE DRAG & DROP E UPLOAD
    // -------------------------------------------------------------------------
    function setupDropzone(dropEl, inputEl, onFileSelect) {
        ['dragenter', 'dragover'].forEach(evt => {
            dropEl.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropEl.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(evt => {
            dropEl.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropEl.classList.remove('drag-over');
            });
        });

        dropEl.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                onFileSelect(files[0]);
            }
        });

        dropEl.addEventListener('click', (e) => {
            if (e.target.tagName !== 'INPUT') {
                inputEl.click();
            }
        });

        inputEl.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                onFileSelect(e.target.files[0]);
            }
        });
    }

    function checkCanUpload() {
        btnUpload.disabled = !(selectedRefFile && selectedAuditFile);
    }

    setupDropzone(dropRefFile, fileRefInput, (file) => {
        selectedRefFile = file;
        filenameRef.textContent = file.name;
        filesizeRef.textContent = formatBytes(file.size);
        fileMetaRef.style.display = 'flex';
        hideUploadAlert();
        checkCanUpload();
    });

    setupDropzone(dropAuditFile, fileAuditInput, (file) => {
        selectedAuditFile = file;
        filenameAudit.textContent = file.name;
        filesizeAudit.textContent = formatBytes(file.size);
        fileMetaAudit.style.display = 'flex';
        hideUploadAlert();
        checkCanUpload();
    });

    // -------------------------------------------------------------------------
    // 3. CARREGAR TESTAR EXEMPLO
    // -------------------------------------------------------------------------
    if (btnTryExample) {
        btnTryExample.addEventListener('click', async () => {
            try {
                btnTryExample.disabled = true;
                const origText = btnTryExample.innerHTML;
                btnTryExample.innerHTML = `<span class="spinner" style="display:inline-block; margin-right:6px;"></span> Carregando exemplo...`;

                const resp = await fetch('/api/rh/load-example', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: currentMode })
                });

                const data = await resp.json();
                if (!resp.ok) {
                    throw new Error(data.error || 'Erro ao carregar bases demonstrativas.');
                }

                currentSessionId = data.session_id;
                renderConfigStep(data);
            } catch (err) {
                showUploadAlert(err.message);
            } finally {
                btnTryExample.disabled = false;
                btnTryExample.innerHTML = `<span class="btn-text">Testar Exemplo</span>`;
            }
        });
    }

    // -------------------------------------------------------------------------
    // 4. SUBMETER ARQUIVOS DO USUÁRIO PARA LEITURA DE CABEÇALHOS
    // -------------------------------------------------------------------------
    if (btnUpload) {
        btnUpload.addEventListener('click', async () => {
            if (!selectedRefFile || !selectedAuditFile) return;

            try {
                btnUpload.disabled = true;
                const spinner = btnUpload.querySelector('.spinner');
                const btnText = btnUpload.querySelector('.btn-text');
                if (spinner) spinner.style.display = 'inline-block';
                if (btnText) btnText.textContent = "Processando arquivos...";

                const fd = new FormData();
                fd.append('file_ref', selectedRefFile);
                fd.append('file_audit', selectedAuditFile);
                fd.append('mode', currentMode);

                const resp = await fetch('/api/rh/upload-headers', {
                    method: 'POST',
                    body: fd
                });

                const data = await resp.json();
                if (!resp.ok) {
                    throw new Error(data.error || 'Falha ao processar arquivos de RH.');
                }

                currentSessionId = data.session_id;
                renderConfigStep(data);
            } catch (err) {
                showUploadAlert(err.message);
            } finally {
                btnUpload.disabled = false;
                const spinner = btnUpload.querySelector('.spinner');
                const btnText = btnUpload.querySelector('.btn-text');
                if (spinner) spinner.style.display = 'none';
                if (btnText) btnText.textContent = "Ler Bases e Configurar Auditoria";
            }
        });
    }

    // -------------------------------------------------------------------------
    // ESTADO E CONTROLES DO MAPEAMENTO DE COLUNAS (IDÊNTICO AO VALIDADOR DE PLANILHAS)
    // -------------------------------------------------------------------------
    const mappingState = {
        columnsA: [],
        columnsB: [],
        initialMapping: {},
        mappingList: [],
        isManualMapping: false
    };
    let activeDropdownState = null;
    function normalizeSearch(str) {
        return (str || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .trim();
    }
    function updateMappingCounter() {
        const validCount = mappingState.mappingList.filter(it => it.colA && it.colB).length;
        if (mappingSummaryCount) {
            mappingSummaryCount.textContent = validCount;
        }

        // Alerta informativo sobre colunas não mapeadas (idêntico ao Validador de Planilhas)
        const unmappedHint = document.getElementById('unmapped-hint-rh');
        if (!unmappedHint) return;
        const mappedA = new Set(mappingState.mappingList.map(it => it.colA).filter(Boolean));
        const unmappedA = (mappingState.columnsA || []).filter(c => !mappedA.has(c));
        const mappedB = new Set(mappingState.mappingList.map(it => it.colB).filter(Boolean));
        const unmappedB = (mappingState.columnsB || []).filter(c => !mappedB.has(c));

        if (unmappedA.length === 0 && unmappedB.length === 0) {
            unmappedHint.style.display = 'none';
            unmappedHint.innerHTML = '';
            return;
        }

        const maxShow = 8;
        let msg = '';
        if (unmappedA.length > 0) {
            const previewA = unmappedA.slice(0, maxShow).map(c => escapeHtml(c)).join(', ');
            const extraA = unmappedA.length > maxShow ? ` e mais ${unmappedA.length - maxShow} coluna(s)...` : '';
            msg += `<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                <svg class="splitc-icon splitc-icon-sm" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                <strong>Colunas da Base Antiga ainda não mapeadas (${unmappedA.length}):</strong> <span style="color: #475569; font-weight: 500;">${previewA}${extraA}</span>
            </div>`;
        }
        if (unmappedB.length > 0) {
            const previewB = unmappedB.slice(0, maxShow).map(c => escapeHtml(c)).join(', ');
            const extraB = unmappedB.length > maxShow ? ` e mais ${unmappedB.length - maxShow} coluna(s)...` : '';
            msg += `<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                <svg class="splitc-icon splitc-icon-sm" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="16" x2="12" y2="12"/>
                    <line x1="12" y1="8" x2="12.01" y2="8"/>
                </svg>
                <strong>Colunas da Base Nova ainda não mapeadas (${unmappedB.length}):</strong> <span style="color: #475569; font-weight: 500;">${previewB}${extraB}</span>
            </div>`;
        }
        msg += `<div style="margin-top: 6px; font-weight: 600; color: #b45309; display: flex; align-items: center; gap: 6px;">
            <svg class="splitc-icon splitc-icon-sm" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 16 16 12 12 8"/>
                <line x1="8" y1="12" x2="16" y2="12"/>
            </svg>
            <span>Se alguma dessas colunas corresponde a uma coluna na outra base com nome diferente, clique em <strong>"+ Adicionar Coluna"</strong> acima para associá-las manualmente.</span>
        </div>`;
        unmappedHint.innerHTML = msg;
        unmappedHint.style.display = 'block';
    }
    function renderMappingTable() {
        if (!tbodyMapping) return;
        tbodyMapping.innerHTML = '';
        if (!mappingState.mappingList || mappingState.mappingList.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td colspan="4" style="text-align: center; color: #64748b; padding: 24px;">
                    Nenhuma coluna associada ainda. Clique no botão <strong>"+ Adicionar Coluna"</strong> acima para mapear.
                </td>
            `;
            tbodyMapping.appendChild(tr);
            updateMappingCounter();
            return;
        }
        mappingState.mappingList.forEach((item) => {
            const tr = document.createElement('tr');
            tr.dataset.id = item.id;
            tr.innerHTML = `
                <td>
                    <div class="searchable-select-trigger mapping-col-a ${item.colA ? 'has-value' : 'is-placeholder'}" data-id="${item.id}" data-type="colA" tabindex="0" title="${escapeHtml(item.colA || 'Clique para pesquisar e selecionar coluna')}">
                        <span class="trigger-text">${escapeHtml(item.colA || 'Selecione a coluna (Base Antiga)...')}</span>
                        <span class="trigger-arrow">▾</span>
                    </div>
                </td>
                <td style="color: #4FD580; text-align: center; font-weight: 800; font-size: 15px;">➔</td>
                <td>
                    <div class="searchable-select-trigger mapping-col-b ${item.colB ? 'has-value' : 'is-placeholder'}" data-id="${item.id}" data-type="colB" tabindex="0" title="${escapeHtml(item.colB || 'Clique para pesquisar e selecionar coluna')}">
                        <span class="trigger-text">${escapeHtml(item.colB || 'Selecione a coluna (Base Nova)...')}</span>
                        <span class="trigger-arrow">▾</span>
                    </div>
                </td>
                <td style="text-align: center;">
                    <button type="button" class="btn-remove-row" data-id="${item.id}" title="Remover mapeamento desta coluna">✕</button>
                </td>
            `;
            tbodyMapping.appendChild(tr);
        });
        // Eventos nos triggers de seleção
        tbodyMapping.querySelectorAll('.mapping-col-a').forEach(trigger => {
            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                openMappingDropdown(trigger.dataset.id, 'colA', trigger);
            });
            trigger.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
                    e.preventDefault();
                    trigger.click();
                }
            });
        });
        tbodyMapping.querySelectorAll('.mapping-col-b').forEach(trigger => {
            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                openMappingDropdown(trigger.dataset.id, 'colB', trigger);
            });
            trigger.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
                    e.preventDefault();
                    trigger.click();
                }
            });
        });
        // Eventos do botão remover linha
        tbodyMapping.querySelectorAll('.btn-remove-row').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.dataset.id;
                mappingState.mappingList = mappingState.mappingList.filter(it => it.id !== id);
                renderMappingTable();
            });
        });
        updateMappingCounter();
    }
    // Portal Flutuante de Dropdown Pesquisável
    const mappingPortal = document.getElementById('mapping-dropdown-portal');
    const mappingSearchInput = document.getElementById('mapping-dropdown-search');
    const mappingClearBtn = document.getElementById('mapping-dropdown-clear-btn');
    const mappingOptionsList = document.getElementById('mapping-dropdown-options');
    function openMappingDropdown(itemId, colType, triggerEl) {
        if (activeDropdownState && activeDropdownState.triggerEl === triggerEl) {
            closeMappingDropdown();
            return;
        }
        closeMappingDropdown();
        activeDropdownState = { itemId, colType, triggerEl };
        triggerEl.classList.add('active');
        if (mappingSearchInput) mappingSearchInput.value = '';
        if (mappingClearBtn) mappingClearBtn.style.display = 'none';
        renderMappingDropdownOptions('');
        if (mappingPortal) {
            mappingPortal.style.display = 'flex';
            positionMappingDropdown(triggerEl, mappingPortal);
        }
        setTimeout(() => {
            if (mappingSearchInput) mappingSearchInput.focus();
        }, 30);
    }
    function positionMappingDropdown(triggerEl, portal) {
        if (!triggerEl || !portal) return;
        const rect = triggerEl.getBoundingClientRect();
        const dropdownWidth = Math.max(rect.width, 280);
        const dropdownHeight = 310;
        const windowHeight = window.innerHeight;
        const windowWidth = window.innerWidth;
        let left = rect.left;
        if (left + dropdownWidth > windowWidth - 16) {
            left = windowWidth - dropdownWidth - 16;
        }
        if (left < 16) left = 16;
        let top = rect.bottom + 4;
        if (rect.bottom + dropdownHeight > windowHeight - 16 && rect.top > dropdownHeight + 16) {
            top = rect.top - dropdownHeight - 4;
        }
        portal.style.top = `${top}px`;
        portal.style.left = `${left}px`;
        portal.style.width = `${dropdownWidth}px`;
    }
    function renderMappingDropdownOptions(filterText = '') {
        if (!activeDropdownState || !mappingOptionsList) return;
        const { itemId, colType } = activeDropdownState;
        const item = mappingState.mappingList.find(it => it.id === itemId);
        if (!item) return;
        const allCols = colType === 'colA' ? mappingState.columnsA : mappingState.columnsB;
        const currentVal = colType === 'colA' ? item.colA : item.colB;
        const normFilter = normalizeSearch(filterText);
        const filteredCols = allCols.filter(c => normalizeSearch(c).includes(normFilter));
        mappingOptionsList.innerHTML = '';
        // Opção vazia
        const emptyOpt = document.createElement('div');
        emptyOpt.className = 'dropdown-option is-empty-option' + (!currentVal ? ' selected' : '');
        emptyOpt.innerHTML = `<span>(Nenhuma coluna selecionada)</span>`;
        emptyOpt.addEventListener('click', () => {
            selectMappingDropdownOption('');
        });
        mappingOptionsList.appendChild(emptyOpt);
        if (filteredCols.length === 0) {
            const noRes = document.createElement('div');
            noRes.className = 'dropdown-no-results';
            noRes.textContent = 'Nenhuma coluna encontrada.';
            mappingOptionsList.appendChild(noRes);
            return;
        }
        filteredCols.forEach(col => {
            const isSelected = col === currentVal;
            const opt = document.createElement('div');
            opt.className = 'dropdown-option' + (isSelected ? ' selected' : '');
            opt.innerHTML = `
                <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(col)}</span>
                ${isSelected ? '<span style="color: #4FD580; font-weight: 800; margin-left: 8px;">✓</span>' : ''}
            `;
            opt.addEventListener('click', () => {
                selectMappingDropdownOption(col);
            });
            mappingOptionsList.appendChild(opt);
        });
    }
    function selectMappingDropdownOption(colValue) {
        if (!activeDropdownState) return;
        const { itemId, colType } = activeDropdownState;
        const item = mappingState.mappingList.find(it => it.id === itemId);
        if (item) {
            if (colType === 'colA') {
                item.colA = colValue;
            } else {
                item.colB = colValue;
            }
            renderMappingTable();
        }
        closeMappingDropdown();
    }
    function closeMappingDropdown() {
        if (mappingPortal) mappingPortal.style.display = 'none';
        if (activeDropdownState && activeDropdownState.triggerEl) {
            activeDropdownState.triggerEl.classList.remove('active');
        }
        activeDropdownState = null;
    }
    if (mappingSearchInput) {
        mappingSearchInput.addEventListener('input', (e) => {
            const val = e.target.value;
            if (mappingClearBtn) mappingClearBtn.style.display = val ? 'block' : 'none';
            renderMappingDropdownOptions(val);
        });
        mappingSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const firstOption = document.querySelector('#mapping-dropdown-options .dropdown-option:not(.is-empty-option)');
                if (firstOption) firstOption.click();
            } else if (e.key === 'Escape') {
                closeMappingDropdown();
            }
        });
    }
    if (mappingClearBtn) {
        mappingClearBtn.addEventListener('click', () => {
            if (mappingSearchInput) {
                mappingSearchInput.value = '';
                mappingClearBtn.style.display = 'none';
                renderMappingDropdownOptions('');
                mappingSearchInput.focus();
            }
        });
    }
    document.addEventListener('click', (e) => {
        if (!activeDropdownState) return;
        if (mappingPortal && (mappingPortal.contains(e.target) || activeDropdownState.triggerEl.contains(e.target))) {
            return;
        }
        closeMappingDropdown();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && activeDropdownState) {
            closeMappingDropdown();
        }
    });
    window.addEventListener('scroll', () => {
        if (activeDropdownState && mappingPortal && mappingPortal.style.display === 'flex') {
            positionMappingDropdown(activeDropdownState.triggerEl, mappingPortal);
        }
    }, true);
    window.addEventListener('resize', () => {
        if (activeDropdownState && mappingPortal && mappingPortal.style.display === 'flex') {
            positionMappingDropdown(activeDropdownState.triggerEl, mappingPortal);
        }
    });
    // Botão "+ Adicionar Coluna"
    const btnAddMapping = document.getElementById('btn-add-mapping-rh');
    if (btnAddMapping) {
        btnAddMapping.addEventListener('click', () => {
            let nextA = '';
            let nextB = '';
            if (!mappingState.isManualMapping) {
                const usedA = new Set(mappingState.mappingList.map(it => it.colA).filter(Boolean));
                const unusedA = (mappingState.columnsA || []).filter(c => !usedA.has(c));
                nextA = unusedA.length > 0 ? unusedA[0] : '';
                const usedB = new Set(mappingState.mappingList.map(it => it.colB).filter(Boolean));
                const unusedB = (mappingState.columnsB || []).filter(c => !usedB.has(c));
                if (nextA && mappingState.initialMapping && mappingState.initialMapping[nextA] && unusedB.includes(mappingState.initialMapping[nextA])) {
                    nextB = mappingState.initialMapping[nextA];
                } else {
                    nextB = unusedB.length > 0 ? unusedB[0] : '';
                }
            }
            const newItem = {
                id: 'rh_map_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
                colA: nextA,
                colB: nextB
            };
            mappingState.mappingList.push(newItem);
            renderMappingTable();
            const wrapper = document.querySelector('.mapping-table-wrapper');
            if (wrapper) {
                wrapper.scrollTop = wrapper.scrollHeight;
            }
            if (mappingState.isManualMapping) {
                setTimeout(() => {
                    const newRowTrigger = document.querySelector(`.mapping-col-a[data-id="${newItem.id}"]`);
                    if (newRowTrigger) newRowTrigger.focus();
                }, 60);
            }
        });
    }
    // Botão "Restaurar Mapeamento"
    const btnRestoreMapping = document.getElementById('btn-restore-mapping-rh');
    if (btnRestoreMapping) {
        btnRestoreMapping.addEventListener('click', () => {
            mappingState.isManualMapping = false;
            const sourceMap = mappingState.initialMapping || {};
            mappingState.mappingList = Object.entries(sourceMap).map(([colA, colB], idx) => ({
                id: 'rh_map_' + idx + '_' + Math.random().toString(36).substring(2, 7),
                colA: colA,
                colB: colB
            }));
            renderMappingTable();
        });
    }
    // -------------------------------------------------------------------------
    // MODAL DE LIMPEZA E SELEÇÃO DE MAPEAMENTO
    // -------------------------------------------------------------------------
    const btnClearMapping = document.getElementById('btn-clear-mapping-rh');
    const modalClearMapping = document.getElementById('modal-clear-mapping');
    const btnModalClose = document.getElementById('btn-modal-close');
    const btnModalCancel = document.getElementById('btn-modal-cancel');
    const btnModalClearAll = document.getElementById('btn-modal-clear-all');
    const btnModalApply = document.getElementById('btn-modal-apply');
    const modalSearchInput = document.getElementById('modal-search-input');
    const modalSearchClear = document.getElementById('modal-search-clear');
    const btnModalSelectAll = document.getElementById('btn-modal-select-all');
    const btnModalDeselectAll = document.getElementById('btn-modal-deselect-all');
    const modalSelectedCount = document.getElementById('modal-selected-count');
    const modalTotalCount = document.getElementById('modal-total-count');
    const modalBtnApplyCount = document.getElementById('modal-btn-apply-count');
    const modalColumnsList = document.getElementById('modal-columns-list');
    let modalSelectedCols = new Set();
    let modalAutoPairs = [];
    function openClearMappingModal() {
        if (!modalClearMapping) return;
        closeMappingDropdown();
        const sourceMap = mappingState.initialMapping || {};
        modalAutoPairs = Object.entries(sourceMap).map(([colA, colB]) => ({ colA, colB }));
        modalSelectedCols.clear();
        const currentlyMappedA = new Set(mappingState.mappingList.map(it => it.colA).filter(Boolean));
        if (currentlyMappedA.size > 0 && currentlyMappedA.size < modalAutoPairs.length) {
            modalAutoPairs.forEach(p => {
                if (currentlyMappedA.has(p.colA)) {
                    modalSelectedCols.add(p.colA);
                }
            });
        }
        if (modalSearchInput) modalSearchInput.value = '';
        if (modalSearchClear) modalSearchClear.style.display = 'none';
        renderModalColumnsList('');
        updateModalCounters();
        modalClearMapping.style.display = 'flex';
        requestAnimationFrame(() => {
            modalClearMapping.classList.add('is-open');
        });
        setTimeout(() => {
            if (modalSearchInput) modalSearchInput.focus();
        }, 60);
    }
    function closeClearMappingModal() {
        if (!modalClearMapping) return;
        modalClearMapping.classList.remove('is-open');
        setTimeout(() => {
            modalClearMapping.style.display = 'none';
        }, 200);
    }
    function updateModalCounters() {
        const count = modalSelectedCols.size;
        const total = modalAutoPairs.length;
        if (modalSelectedCount) modalSelectedCount.textContent = count;
        if (modalTotalCount) modalTotalCount.textContent = total;
        if (modalBtnApplyCount) modalBtnApplyCount.textContent = count;
    }
    function renderModalColumnsList(filterText = '') {
        if (!modalColumnsList) return;
        modalColumnsList.innerHTML = '';
        const normFilter = normalizeSearch(filterText);
        const filtered = normFilter
            ? modalAutoPairs.filter(p =>
                normalizeSearch(p.colA).includes(normFilter) ||
                normalizeSearch(p.colB).includes(normFilter)
              )
            : modalAutoPairs;
        if (filtered.length === 0) {
            modalColumnsList.innerHTML = '<div style="padding: 20px; text-align: center; color: #64748b; font-size: 13px;">Nenhuma coluna encontrada para esta pesquisa.</div>';
            return;
        }
        filtered.forEach(pair => {
            const isChecked = modalSelectedCols.has(pair.colA);
            const row = document.createElement('label');
            row.className = 'modal-col-row' + (isChecked ? ' is-checked' : '');
            row.innerHTML = `
                <input type="checkbox" class="modal-col-checkbox" value="${escapeHtml(pair.colA)}" ${isChecked ? 'checked' : ''}>
                <div class="modal-col-pair">
                    <span class="modal-col-a" title="${escapeHtml(pair.colA)}">${escapeHtml(pair.colA)}</span>
                    <span class="modal-col-arrow">➔</span>
                    <span class="modal-col-b" title="${escapeHtml(pair.colB)}">${escapeHtml(pair.colB)}</span>
                </div>
            `;
            const chk = row.querySelector('.modal-col-checkbox');
            chk.addEventListener('change', (e) => {
                if (e.target.checked) {
                    modalSelectedCols.add(pair.colA);
                    row.classList.add('is-checked');
                } else {
                    modalSelectedCols.delete(pair.colA);
                    row.classList.remove('is-checked');
                }
                updateModalCounters();
            });
            modalColumnsList.appendChild(row);
        });
    }
    if (btnClearMapping) {
        btnClearMapping.addEventListener('click', openClearMappingModal);
    }
    if (btnModalClose) btnModalClose.addEventListener('click', closeClearMappingModal);
    if (btnModalCancel) btnModalCancel.addEventListener('click', closeClearMappingModal);
    if (modalClearMapping) {
        modalClearMapping.addEventListener('click', (e) => {
            if (e.target === modalClearMapping) closeClearMappingModal();
        });
    }
    // Modal Opção 1: Limpar Tudo
    if (btnModalClearAll) {
        btnModalClearAll.addEventListener('click', () => {
            closeClearMappingModal();
            mappingState.isManualMapping = true;
            mappingState.mappingList = [
                {
                    id: 'rh_map_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
                    colA: '',
                    colB: ''
                }
            ];
            renderMappingTable();
            const wrapper = document.querySelector('.mapping-table-wrapper');
            if (wrapper) wrapper.scrollTop = 0;
            setTimeout(() => {
                const firstTrigger = tbodyMapping.querySelector('.mapping-col-a');
                if (firstTrigger) firstTrigger.focus();
            }, 60);
        });
    }
    // Modal Opção 2: Aplicar Seleção
    if (btnModalApply) {
        btnModalApply.addEventListener('click', () => {
            if (modalSelectedCols.size === 0) {
                alert('Marque pelo menos uma coluna na lista para manter no mapeamento, ou clique em "Limpar Tudo" acima para esvaziar a tabela.');
                return;
            }
            mappingState.isManualMapping = false;
            mappingState.mappingList = modalAutoPairs
                .filter(p => modalSelectedCols.has(p.colA))
                .map((p, idx) => ({
                    id: 'rh_map_' + idx + '_' + Math.random().toString(36).substring(2, 7),
                    colA: p.colA,
                    colB: p.colB
                }));
            renderMappingTable();
            closeClearMappingModal();
            const wrapper = document.querySelector('.mapping-table-wrapper');
            if (wrapper) wrapper.scrollTop = 0;
        });
    }
    if (btnModalSelectAll) {
        btnModalSelectAll.addEventListener('click', () => {
            const currentFilter = modalSearchInput ? modalSearchInput.value : '';
            const normFilter = normalizeSearch(currentFilter);
            modalAutoPairs.forEach(p => {
                if (!normFilter || normalizeSearch(p.colA).includes(normFilter) || normalizeSearch(p.colB).includes(normFilter)) {
                    modalSelectedCols.add(p.colA);
                }
            });
            renderModalColumnsList(currentFilter);
            updateModalCounters();
        });
    }
    if (btnModalDeselectAll) {
        btnModalDeselectAll.addEventListener('click', () => {
            const currentFilter = modalSearchInput ? modalSearchInput.value : '';
            const normFilter = normalizeSearch(currentFilter);
            if (!normFilter) {
                modalSelectedCols.clear();
            } else {
                modalAutoPairs.forEach(p => {
                    if (normalizeSearch(p.colA).includes(normFilter) || normalizeSearch(p.colB).includes(normFilter)) {
                        modalSelectedCols.delete(p.colA);
                    }
                });
            }
            renderModalColumnsList(currentFilter);
            updateModalCounters();
        });
    }
    if (modalSearchInput) {
        modalSearchInput.addEventListener('input', (e) => {
            const val = e.target.value;
            if (modalSearchClear) modalSearchClear.style.display = val ? 'block' : 'none';
            renderModalColumnsList(val);
        });
    }
    if (modalSearchClear) {
        modalSearchClear.addEventListener('click', () => {
            if (modalSearchInput) {
                modalSearchInput.value = '';
                modalSearchClear.style.display = 'none';
                renderModalColumnsList('');
                modalSearchInput.focus();
            }
        });
    }
    // -------------------------------------------------------------------------
    // 5. TRANSIÇÃO E MONTAGEM DO PASSO 2 (CONFIGURAÇÃO)
    // -------------------------------------------------------------------------
    function renderConfigStep(data) {
        stepUpload.style.display = 'none';
        stepConfig.style.display = 'block';
        stepResults.style.display = 'none';

        infoRefName.textContent = data.filename_ref || 'Base Referência';
        infoRefRows.textContent = `(${data.rows_ref_count || 0} linhas)`;
        infoAuditName.textContent = data.filename_audit || 'Base Auditada';
        infoAuditRows.textContent = `(${data.rows_audit_count || 0} linhas)`;

        // 1. Popula Selects de Chave Principal
        selectKeyRef.innerHTML = '';
        data.cols_ref.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            if (c === data.suggested_key_ref) opt.selected = true;
            selectKeyRef.appendChild(opt);
        });

        selectKeyAudit.innerHTML = '';
        data.cols_audit.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            if (c === data.suggested_key_audit) opt.selected = true;
            selectKeyAudit.appendChild(opt);
        });

        // 2. Popula Selects de Chave Complementar
        selectSecRef.innerHTML = '<option value="">(Nenhuma chave complementar)</option>';
        data.cols_ref.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            selectSecRef.appendChild(opt);
        });

        selectSecAudit.innerHTML = '<option value="">(Nenhuma chave complementar)</option>';
        data.cols_audit.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            selectSecAudit.appendChild(opt);
        });

        // 3. Inicializa Mapeamento de Colunas no padrão do Validador de Planilhas
        mappingState.columnsA = data.cols_ref || [];
        mappingState.columnsB = data.cols_audit || [];
        mappingState.initialMapping = { ...(data.column_mapping || {}) };
        mappingState.isManualMapping = false;

        // Converte o mapeamento inicial em lista de pares
        mappingState.mappingList = Object.entries(mappingState.initialMapping).map(([colA, colB], idx) => ({
            id: 'rh_map_' + idx + '_' + Math.random().toString(36).substring(2, 7),
            colA: colA,
            colB: colB
        }));

        renderMappingTable();

        stepConfig.scrollIntoView({ behavior: 'smooth' });
    }

    // Botão Voltar ao Passo 1
    if (btnBackStep1) {
        btnBackStep1.addEventListener('click', () => {
            stepConfig.style.display = 'none';
            stepUpload.style.display = 'block';
            stepResults.style.display = 'none';
            stepUpload.scrollIntoView({ behavior: 'smooth' });
        });
    }

    // Atalhos Rápidos de Variação (%)
    presetVarButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            presetVarButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            inputVariationThreshold.value = btn.getAttribute('data-var');
        });
    });

    if (inputVariationThreshold) {
        inputVariationThreshold.addEventListener('input', () => {
            const val = parseFloat(inputVariationThreshold.value);
            presetVarButtons.forEach(btn => {
                if (parseFloat(btn.getAttribute('data-var')) === val) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        });
    }

    // -------------------------------------------------------------------------
    // 6. EXECUTAR AUDITORIA DE FOLHA E RH
    // -------------------------------------------------------------------------
    if (btnProcess) {
        btnProcess.addEventListener('click', async () => {
            if (!currentSessionId) return;

            try {
                btnProcess.disabled = true;
                const spinner = btnProcess.querySelector('.spinner');
                const btnText = btnProcess.querySelector('.btn-text');
                if (spinner) spinner.style.display = 'inline-block';
                if (btnText) btnText.textContent = "Auditando colaboradores...";

                // Coletar mapeamento atualizado no padrão do Validador de Planilhas
                const customMapping = {};
                mappingState.mappingList.forEach(item => {
                    if (item.colA && item.colB) {
                        customMapping[item.colA] = item.colB;
                    }
                });

                const payload = {
                    session_id: currentSessionId,
                    mode: currentMode,
                    key_ref: selectKeyRef.value,
                    key_audit: selectKeyAudit.value,
                    sec_key_ref: selectSecRef.value || null,
                    sec_key_audit: selectSecAudit.value || null,
                    normalize_cpf: chkNormCpf ? chkNormCpf.checked : true,
                    ignore_accents: chkIgnoreAccents ? chkIgnoreAccents.checked : true,
                    variation_threshold: parseFloat(inputVariationThreshold.value) || 10.0,
                    column_mapping: customMapping
                };

                const resp = await fetch('/api/rh/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await resp.json();
                if (!resp.ok) {
                    throw new Error(data.error || 'Erro ao processar auditoria de RH.');
                }

                currentReportId = data.report_id;
                auditResults = data;
                renderResultsStep(data);
            } catch (err) {
                alert(`Erro na Auditoria: ${err.message}`);
            } finally {
                btnProcess.disabled = false;
                const spinner = btnProcess.querySelector('.spinner');
                const btnText = btnProcess.querySelector('.btn-text');
                if (spinner) spinner.style.display = 'none';
                if (btnText) btnText.textContent = "Executar Auditoria de RH";
            }
        });
    }

    // -------------------------------------------------------------------------
    // 7. TRANSIÇÃO E RENDERIZAÇÃO DO PASSO 3 (RESULTADOS)
    // -------------------------------------------------------------------------
    function renderResultsStep(data) {
        stepConfig.style.display = 'none';
        stepResults.style.display = 'block';

        const k = data.kpis;
        const isPerfect = (k.divergence_count === 0 && k.exclusive_ref_count === 0 && k.exclusive_audit_count === 0 && k.critical_variations_count === 0);

        if (isPerfect) {
            bannerSuccess.style.display = 'flex';
            bannerDiffs.style.display = 'none';
        } else {
            bannerSuccess.style.display = 'none';
            bannerDiffs.style.display = 'flex';
            if (bannerDiffsTitle) {
                if (currentMode === 'beneficios') {
                    bannerDiffsTitle.textContent = `Atenção: Identificadas ${k.exclusive_audit_count} cobranças indevidas ou funcionários sem benefício!`;
                } else {
                    bannerDiffsTitle.textContent = `Atenção: Identificadas ${k.critical_variations_count} variações salariais atípicas e ${k.divergence_count} cadastros divergentes!`;
                }
            }
        }

        // 1. Atualizar KPIs
        kpiAuditedCount.textContent = k.total_audited;
        kpiDivergenceVal.textContent = `${k.divergence_count} (${k.divergence_pct}%)`;
        kpiCriticalCount.textContent = k.critical_variations_count;
        if (kpiCriticalLabel) {
            kpiCriticalLabel.textContent = `Alertas de Variação (> ${k.variation_threshold_pct}%)`;
        }
        kpiExclusiveRef.textContent = k.exclusive_ref_count;
        kpiExclusiveAudit.textContent = k.exclusive_audit_count;
        kpiFinancialImpact.textContent = k.financial_impact_fmt;
        if (k.financial_impact > 0) {
            kpiFinancialImpact.className = "kpi-val text-danger";
        } else if (k.financial_impact < 0) {
            kpiFinancialImpact.className = "kpi-val text-info";
        } else {
            kpiFinancialImpact.className = "kpi-val text-success";
        }

        // 2. Botão de Download
        btnDownloadAudit.href = `/api/rh/download-report/${data.report_id}`;

        // 3. Atualizar Badges das Abas
        badgeSummary.textContent = data.financial_summary.length;
        badgeDivergences.textContent = data.divergences.length;
        badgeEx1.textContent = data.exclusive_ref.length;
        badgeEx2.textContent = data.exclusive_audit.length;

        // 4. Renderizar Tabelas
        renderTables();

        stepResults.scrollIntoView({ behavior: 'smooth' });
    }

    // -------------------------------------------------------------------------
    // 8. RENDERIZAÇÃO DAS 4 TABELAS DE DETALHAMENTO
    // -------------------------------------------------------------------------
    function renderTables() {
        if (!auditResults) return;

        const q = searchQuery.toLowerCase().trim();

        // Tabela 1: Sumarização Financeira
        tbodySummary.innerHTML = '';
        const finList = auditResults.financial_summary.filter(item => {
            if (!q) return true;
            return item.col_ref.toLowerCase().includes(q) ||
                   item.col_audit.toLowerCase().includes(q) ||
                   item.situacao.toLowerCase().includes(q);
        });

        if (finList.length === 0) {
            tbodySummary.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-muted);">Nenhuma coluna financeira identificada ou correspondente à busca.</td></tr>`;
        } else {
            finList.forEach(item => {
                const tr = document.createElement('tr');
                const diffClass = item.diff > 0 ? 'text-warning font-bold' : (item.diff < 0 ? 'text-info font-bold' : 'text-success');
                const badgeClass = item.diff > 0 ? 'status-badge-warning' : (item.diff < 0 ? 'status-badge-diff' : 'status-badge-ok');

                tr.innerHTML = `
                    <td style="font-weight: 600;">${escapeHtml(item.col_ref)}</td>
                    <td style="font-weight: 600;">${escapeHtml(item.col_audit)}</td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${escapeHtml(item.total_ref_fmt)}</td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${escapeHtml(item.total_audit_fmt)}</td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 13px;" class="${diffClass}">${escapeHtml(item.diff_fmt)}</td>
                    <td style="text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 13px;"><span class="badge-pct ${item.diff !== 0 ? 'pct-alert' : ''}">${escapeHtml(item.var_pct_fmt)}</span></td>
                    <td style="text-align: center;"><span class="${badgeClass}">${escapeHtml(item.situacao)}</span></td>
                `;
                tbodySummary.appendChild(tr);
            });
        }

        // Tabela 2: Alertas e Divergências por Colaborador
        tbodyDivergences.innerHTML = '';
        const divList = auditResults.divergences.filter(item => {
            if (!q) return true;
            return item.employee_key.toLowerCase().includes(q) ||
                   item.employee_name.toLowerCase().includes(q) ||
                   item.col_display.toLowerCase().includes(q) ||
                   item.status.toLowerCase().includes(q);
        });

        if (divList.length === 0) {
            tbodyDivergences.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:24px; color:var(--text-muted);">Nenhuma divergência ou alerta localizado entre os colaboradores.</td></tr>`;
            hintDivergences.textContent = '';
        } else {
            divList.slice(0, 50).forEach(item => {
                const tr = document.createElement('tr');
                const badgeClass = item.is_critical ? 'status-badge-danger' : (item.is_numeric ? 'status-badge-warning' : 'status-badge-diff');
                const diffClass = item.diff > 0 ? 'text-danger font-bold' : (item.diff < 0 ? 'text-info font-bold' : '');

                tr.innerHTML = `
                    <td style="text-align: center;"><span class="key-code">${escapeHtml(item.employee_key)}</span></td>
                    <td><strong>${escapeHtml(item.employee_name || '-')}</strong></td>
                    <td style="font-size: 13px;">${escapeHtml(item.col_display)}</td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--text-muted);">${escapeHtml(item.val_ref_fmt)}</td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;">${escapeHtml(item.val_audit_fmt)}</td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 13px;" class="${diffClass}">${escapeHtml(item.diff_fmt)}</td>
                    <td style="text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 13px;"><span class="badge-pct ${item.is_critical ? 'pct-alert' : ''}">${escapeHtml(item.var_pct_fmt)}</span></td>
                    <td style="text-align: center;"><span class="${badgeClass}">${escapeHtml(item.status)}</span></td>
                `;
                tbodyDivergences.appendChild(tr);
            });
            hintDivergences.textContent = `Exibindo ${Math.min(50, divList.length)} de ${divList.length} ocorrências encontradas. O arquivo Excel completo contém todas as linhas.`;
        }

        // Tabela 3: Exclusivos Base 1 (Desligados)
        tbodyExRef.innerHTML = '';
        const exRefList = auditResults.exclusive_ref.filter(item => {
            if (!q) return true;
            return item.employee_key.toLowerCase().includes(q) ||
                   item.employee_name.toLowerCase().includes(q) ||
                   item.cargo.toLowerCase().includes(q) ||
                   item.departamento.toLowerCase().includes(q);
        });

        if (exRefList.length === 0) {
            tbodyExRef.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:24px; color:var(--text-muted);">Nenhum colaborador exclusivo na Base de Referência.</td></tr>`;
            hintExRef.textContent = '';
        } else {
            exRefList.slice(0, 50).forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="text-align: center;"><span class="key-code">${escapeHtml(item.employee_key)}</span></td>
                    <td><strong>${escapeHtml(item.employee_name || '-')}</strong></td>
                    <td>${escapeHtml(item.cargo)}</td>
                    <td>${escapeHtml(item.departamento)}</td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 600;">${escapeHtml(item.valor_referencia_fmt)}</td>
                    <td style="text-align: center;"><span class="status-badge-warning">${escapeHtml(item.status)}</span></td>
                `;
                tbodyExRef.appendChild(tr);
            });
            hintExRef.textContent = `Exibindo ${Math.min(50, exRefList.length)} de ${exRefList.length} colaboradores exclusivos na Base 1.`;
        }

        // Tabela 4: Exclusivos Base 2 (Admitidos / Cobrança Indevida)
        tbodyExAudit.innerHTML = '';
        const exAuditList = auditResults.exclusive_audit.filter(item => {
            if (!q) return true;
            return item.employee_key.toLowerCase().includes(q) ||
                   item.employee_name.toLowerCase().includes(q) ||
                   item.cargo.toLowerCase().includes(q) ||
                   item.departamento.toLowerCase().includes(q);
        });

        if (exAuditList.length === 0) {
            tbodyExAudit.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:24px; color:var(--text-muted);">Nenhum colaborador exclusivo na Base Auditada.</td></tr>`;
            hintExAudit.textContent = '';
        } else {
            exAuditList.slice(0, 50).forEach(item => {
                const tr = document.createElement('tr');
                const badgeClass = currentMode === 'beneficios' ? 'status-badge-danger' : 'status-badge-ok';

                tr.innerHTML = `
                    <td style="text-align: center;"><span class="key-code">${escapeHtml(item.employee_key)}</span></td>
                    <td><strong>${escapeHtml(item.employee_name || '-')}</strong></td>
                    <td>${escapeHtml(item.cargo)}</td>
                    <td>${escapeHtml(item.departamento)}</td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;">${escapeHtml(item.valor_auditado_fmt)}</td>
                    <td style="text-align: center;"><span class="${badgeClass}">${escapeHtml(item.status)}</span></td>
                `;
                tbodyExAudit.appendChild(tr);
            });
            hintExAudit.textContent = `Exibindo ${Math.min(50, exAuditList.length)} de ${exAuditList.length} colaboradores na Base 2.`;
        }
    }

    // -------------------------------------------------------------------------
    // 9. NAVEGAÇÃO DE ABAS E BARRA DE BUSCA EM TEMPO REAL
    // -------------------------------------------------------------------------
    resultTabs.forEach(tabBtn => {
        tabBtn.addEventListener('click', () => {
            resultTabs.forEach(b => b.classList.remove('active'));
            tabBtn.classList.add('active');

            activeTab = tabBtn.getAttribute('data-tab');

            panelSummary.style.display = (activeTab === 'summary') ? 'block' : 'none';
            panelDivergences.style.display = (activeTab === 'divergences') ? 'block' : 'none';
            panelExRef.style.display = (activeTab === 'exclusive_ref') ? 'block' : 'none';
            panelExAudit.style.display = (activeTab === 'exclusive_audit') ? 'block' : 'none';

            if (activeTab === 'summary') {
                rhTableTitle.textContent = "Sumarização Financeira da Folha / Benefícios";
            } else if (activeTab === 'divergences') {
                rhTableTitle.textContent = "Alertas e Divergências por Colaborador";
            } else if (activeTab === 'exclusive_ref') {
                rhTableTitle.textContent = currentMode === 'beneficios' ? "Colaboradores Ativos no RH sem Fatura no Benefício" : "Colaboradores Desligados (Apenas Base 1)";
            } else if (activeTab === 'exclusive_audit') {
                rhTableTitle.textContent = currentMode === 'beneficios' ? "Cobranças Indevidas em Benefícios (Funcionários Fantasmas)" : "Novos Admitidos na Folha (Apenas Base 2)";
            }
        });
    });

    if (rhTableSearch) {
        rhTableSearch.addEventListener('input', (e) => {
            searchQuery = e.target.value;
            renderTables();
        });
    }

    // Inicialização do Modo Padrão
    updateModeUI('folha');

})();

