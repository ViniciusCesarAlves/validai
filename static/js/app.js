document.addEventListener('DOMContentLoaded', () => {
    // Verificação Pós-Checkout do Mercado Pago na URL
    try {
        const urlParams = new URLSearchParams(window.location.search || '');
        const mpStatus = (urlParams.get('status') || '').toLowerCase();
        const mpCollectionStatus = (urlParams.get('collection_status') || '').toLowerCase();
        const mpFeedback = (urlParams.get('feedback') || '').toLowerCase();
        const mpPagamento = (urlParams.get('pagamento') || '').toLowerCase();

        if (
            mpStatus === 'approved' ||
            mpCollectionStatus === 'approved' ||
            mpFeedback === 'success' ||
            (mpPagamento === 'sucesso' && mpStatus !== 'rejected' && mpStatus !== 'null')
        ) {
            const mpBanner = document.getElementById('mp-checkout-success-banner');
            if (mpBanner) {
                mpBanner.style.display = 'flex';
            }
            const btnCloseMp = document.getElementById('btn-close-mp-success');
            if (btnCloseMp && mpBanner) {
                btnCloseMp.addEventListener('click', () => {
                    try {
                        mpBanner.style.display = 'none';
                    } catch (_) {}
                });
            }
            if (window.history && typeof window.history.replaceState === 'function') {
                window.history.replaceState({}, document.title, window.location.pathname);
            }
        }
    } catch (mpErr) {
        console.warn('Aviso ao verificar retorno de checkout:', mpErr);
    }

    // Estado da Aplicação
    const state = {
        sessionId: null,
        reportId: null,
        fileA: null,
        fileB: null,
        columnsA: [],
        columnsB: [],
        initialMapping: {},
        mappingList: [],
        mapping: {},
        isManualMapping: false,
        selectedSecondaryKeys: [],
        diffRecords: [],
        allDiffRows: [],
        onlyInAPreview: [],
        onlyInBPreview: [],
        colsDisplayA: [],
        colsDisplayB: [],
        selectedSheetsA: [],
        selectedSheetsB: [],
        userHeaderLineA: null,
        userHeaderLineB: null
    };

    // Tema gerenciado centralmente por header.html

    // Elementos DOM - Passo 1
    const fileInputA = document.getElementById('file-a');
    const fileInputB = document.getElementById('file-b');
    const dropzoneA = document.getElementById('dropzone-a');
    const dropzoneB = document.getElementById('dropzone-b');
    const fileMetaA = document.getElementById('file-meta-a');
    const fileMetaB = document.getElementById('file-meta-b');
    const filenameA = document.getElementById('filename-a');
    const filenameB = document.getElementById('filename-b');
    const filesizeA = document.getElementById('filesize-a');
    const filesizeB = document.getElementById('filesize-b');
    const btnReadHeaders = document.getElementById('btn-read-headers');
    const btnSheetsTryExample = document.getElementById('btn-sheets-try-example');

    // Elementos DOM - Passo 2
    const stepConfig = document.getElementById('step-config');
    const selectPrimaryKey = document.getElementById('primary-key');
    const secKeysTrigger = document.getElementById('sec-keys-trigger');
    const secKeysDropdown = document.getElementById('sec-keys-dropdown');
    const secKeysLabel = document.getElementById('sec-keys-label');
    const secKeysSearch = document.getElementById('sec-keys-search');
    const secKeysOptionsList = document.getElementById('sec-keys-options-list');
    const selectedSecKeysTags = document.getElementById('selected-sec-keys-tags');
    const btnClearSecKeys = document.getElementById('btn-clear-sec-keys');
    const btnCloseSecKeys = document.getElementById('btn-close-sec-keys');

    const normCurrency = document.getElementById('norm-currency');
    const normDates = document.getElementById('norm-dates');
    const normCase = document.getElementById('norm-case');
    const normTrim = document.getElementById('norm-trim');
    const mappedColsCount = document.getElementById('mapped-cols-count');
    const mappingTableBody = document.getElementById('mapping-table-body');
    const btnAddMapping = document.getElementById('btn-add-mapping');
    const btnRestoreMapping = document.getElementById('btn-restore-mapping');
    const btnClearMapping = document.getElementById('btn-clear-mapping');
    const unmappedHint = document.getElementById('unmapped-hint');
    const btnRunCompare = document.getElementById('btn-run-compare');

    // Elementos DOM - Seletor de Aba e Cabeçalho no Passo 2 (Múltiplas Abas)
    const step2SheetsConfig = document.getElementById('step2-sheets-config');
    const step2CardA = document.getElementById('step2-card-a');
    const step2CardB = document.getElementById('step2-card-b');
    const step2FilenameA = document.getElementById('step2-filename-a');
    const step2FilenameB = document.getElementById('step2-filename-b');
    const step2MultiselectA = document.getElementById('step2-multiselect-a');
    const step2MultiselectB = document.getElementById('step2-multiselect-b');
    const step2SheetTriggerA = document.getElementById('step2-sheet-trigger-a');
    const step2SheetTriggerB = document.getElementById('step2-sheet-trigger-b');
    const step2SheetLabelA = document.getElementById('step2-sheet-label-a');
    const step2SheetLabelB = document.getElementById('step2-sheet-label-b');
    const step2SheetDropdownA = document.getElementById('step2-sheet-dropdown-a');
    const step2SheetDropdownB = document.getElementById('step2-sheet-dropdown-b');
    const step2SelectAllVisA = document.getElementById('step2-select-all-vis-a');
    const step2SelectAllVisB = document.getElementById('step2-select-all-vis-b');
    const step2DeselectAllA = document.getElementById('step2-deselect-all-a');
    const step2DeselectAllB = document.getElementById('step2-deselect-all-b');
    const step2SheetOptionsA = document.getElementById('step2-sheet-options-a');
    const step2SheetOptionsB = document.getElementById('step2-sheet-options-b');
    const step2HeaderLineA = document.getElementById('step2-header-line-a');
    const step2HeaderLineB = document.getElementById('step2-header-line-b');
    const step2SheetLoading = document.getElementById('step2-sheet-loading');

    // Elementos DOM - Modal de Limpeza / Seleção de Mapeamento
    const modalClearMapping = document.getElementById('modal-clear-mapping');
    const btnModalClose = document.getElementById('btn-modal-close');
    const btnModalClearAll = document.getElementById('btn-modal-clear-all');
    const btnModalCancel = document.getElementById('btn-modal-cancel');
    const btnModalApply = document.getElementById('btn-modal-apply');
    const btnModalSelectAll = document.getElementById('btn-modal-select-all');
    const btnModalDeselectAll = document.getElementById('btn-modal-deselect-all');
    const modalSearchInput = document.getElementById('modal-search-input');
    const modalSearchClear = document.getElementById('modal-search-clear');
    const modalColumnsList = document.getElementById('modal-columns-list');
    const modalSelectedCount = document.getElementById('modal-selected-count');
    const modalTotalCount = document.getElementById('modal-total-count');
    const modalBtnApplyCount = document.getElementById('modal-btn-apply-count');

    // Elementos DOM - Passo 3
    const stepResults = document.getElementById('step-results');
    const bannerIdentical = document.getElementById('banner-identical');
    const bannerDiffs = document.getElementById('banner-diffs');
    const kpiRowsMatched = document.getElementById('kpi-rows-matched');
    const kpiRowsTotal = document.getElementById('kpi-rows-total');
    const kpiRowsDiff = document.getElementById('kpi-rows-diff');
    const kpiPctDiff = document.getElementById('kpi-pct-diff');
    const kpiCellsDiff = document.getElementById('kpi-cells-diff');
    const kpiColsDiff = document.getElementById('kpi-cols-diff');
    const kpiColsTotal = document.getElementById('kpi-cols-total');
    const kpiRowsOnlyA = document.getElementById('kpi-rows-only-a');
    const kpiRowsOnlyB = document.getElementById('kpi-rows-only-b');
    const btnDownloadExcel = document.getElementById('btn-download-excel');
    const diffColsSection = document.getElementById('diff-cols-section');
    const diffTagsContainer = document.getElementById('diff-tags-container');
    const diffTableSection = document.getElementById('diff-table-section');
    const diffTableBody = document.getElementById('diff-table-body');
    const diffSearch = document.getElementById('diff-search');
    const btnRestart = document.getElementById('btn-restart');

    // Elementos de Navegação, Sumarização Financeira e Registros Exclusivos
    const resultNavTabs = document.getElementById('result-nav-tabs');
    const tabBtnDiffs = document.getElementById('tab-btn-diffs');
    const tabBtnOnlyA = document.getElementById('tab-btn-only-a');
    const tabBtnOnlyB = document.getElementById('tab-btn-only-b');
    const tabBtnFinancial = document.getElementById('tab-btn-financial');
    const onlyATableSection = document.getElementById('only-a-table-section');
    const onlyBTableSection = document.getElementById('only-b-table-section');
    const onlyATableHead = document.getElementById('only-a-table-head');
    const onlyATableBody = document.getElementById('only-a-table-body');
    const onlyBTableHead = document.getElementById('only-b-table-head');
    const onlyBTableBody = document.getElementById('only-b-table-body');
    const onlyASearch = document.getElementById('only-a-search');
    const onlyBSearch = document.getElementById('only-b-search');
    const financialTableSection = document.getElementById('financial-table-section');
    const financialTableBody = document.getElementById('financial-table-body');
    const financialTableFooter = document.getElementById('financial-table-footer');
    const badgeDiffCount = document.getElementById('badge-diff-count');
    const badgeOnlyACount = document.getElementById('badge-only-a-count');
    const badgeOnlyBCount = document.getElementById('badge-only-b-count');
    const badgeFinCount = document.getElementById('badge-fin-count');

    // ----------------------------------------------------
    // FUNÇÕES UTILITÁRIAS
    // ----------------------------------------------------
    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function setBtnLoading(button, isLoading, originalText = '') {
        const textSpan = button.querySelector('.btn-text');
        const spinner = button.querySelector('.spinner');
        const icon = button.querySelector('.btn-circle-icon');
        if (isLoading) {
            button.disabled = true;
            if (textSpan) textSpan.dataset.original = textSpan.textContent;
            if (textSpan && originalText) textSpan.textContent = originalText;
            if (spinner) spinner.style.display = 'inline-block';
            if (icon) icon.style.display = 'none';
        } else {
            button.disabled = false;
            if (textSpan && textSpan.dataset.original) textSpan.textContent = textSpan.dataset.original;
            if (spinner) spinner.style.display = 'none';
            if (icon) icon.style.display = 'inline-flex';
        }
    }

    const BTN_STEPPER_STAGES = [
        '⏳ Lendo e normalizando células...',
        '🔍 Cruzando chaves e identificadores...',
        '📊 Consolidando divergências e KPIs...',
        '✨ Finalizando relatório...'
    ];

    function startBtnStepperLoading(button, fallbackDefaultText = '') {
        try {
            if (!button) return;
            if (button._stepperIntervalId) {
                clearInterval(button._stepperIntervalId);
                button._stepperIntervalId = null;
            }
            const textSpan = button.querySelector('.btn-text');
            const spinner = button.querySelector('.spinner');
            const icon = button.querySelector('.btn-circle-icon');

            if (textSpan && !textSpan.dataset.stepperOriginal) {
                textSpan.dataset.stepperOriginal = textSpan.textContent || fallbackDefaultText;
            }
            button.disabled = true;
            if (spinner) spinner.style.display = 'inline-block';
            if (icon) icon.style.display = 'none';

            let stepIndex = 0;
            if (textSpan) {
                textSpan.style.transition = 'opacity 0.18s ease';
                textSpan.textContent = BTN_STEPPER_STAGES[0];
            }

            button._stepperIntervalId = setInterval(() => {
                try {
                    if (!textSpan || !button.disabled) return;
                    stepIndex = Math.min(stepIndex + 1, BTN_STEPPER_STAGES.length - 1);
                    textSpan.style.opacity = '0.65';
                    setTimeout(() => {
                        try {
                            if (button.disabled && textSpan) {
                                textSpan.textContent = BTN_STEPPER_STAGES[stepIndex];
                                textSpan.style.opacity = '1';
                            }
                        } catch (_) {}
                    }, 90);
                } catch (stepErr) {
                    console.warn('Erro ao avançar stepper do botão:', stepErr);
                }
            }, 900);
        } catch (err) {
            console.warn('Erro ao iniciar stepper do botão:', err);
        }
    }

    function stopBtnStepperLoading(button, fallbackDefaultText = '') {
        try {
            if (!button) return;
            if (button._stepperIntervalId) {
                clearInterval(button._stepperIntervalId);
                button._stepperIntervalId = null;
            }
            const textSpan = button.querySelector('.btn-text');
            const spinner = button.querySelector('.spinner');
            const icon = button.querySelector('.btn-circle-icon');

            button.disabled = false;
            if (textSpan) {
                textSpan.style.opacity = '1';
                textSpan.textContent = textSpan.dataset.stepperOriginal || fallbackDefaultText || textSpan.textContent;
                delete textSpan.dataset.stepperOriginal;
            }
            if (spinner) spinner.style.display = 'none';
            if (icon) icon.style.display = 'inline-flex';
        } catch (err) {
            console.warn('Erro ao restaurar estado do botão:', err);
        }
    }

    function showValidaiToast(message, type = 'success') {
        try {
            if (!message) return;
            let toastEl = document.getElementById('validai-quick-toast');
            if (!toastEl) {
                toastEl = document.createElement('div');
                toastEl.id = 'validai-quick-toast';
                toastEl.className = 'validai-quick-toast';
                toastEl.setAttribute('role', 'status');
                toastEl.setAttribute('aria-live', 'polite');
                document.body.appendChild(toastEl);
            }
            toastEl.classList.remove('toast-info', 'show');
            if (type === 'info') {
                toastEl.classList.add('toast-info');
            }
            const cleanMsg = String(message).replace(/^[\u{1F300}-\u{1FAFF}\u2600-\u27BF\uFE0F]+\s*/u, '');
            const iconSvg = type === 'info'
                ? '<svg class="splitc-icon splitc-icon-sm" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4FD580" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:8px;vertical-align:-3px;" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
                : '<svg class="splitc-icon splitc-icon-sm" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4FD580" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:8px;vertical-align:-3px;" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>';
            toastEl.innerHTML = `${iconSvg}<span>${escapeHtml(cleanMsg)}</span>`;

            if (toastEl._hideTimer) {
                clearTimeout(toastEl._hideTimer);
            }
            requestAnimationFrame(() => {
                toastEl.classList.add('show');
            });
            toastEl._hideTimer = setTimeout(() => {
                try {
                    toastEl.classList.remove('show');
                } catch (_) {}
            }, 3400);
        } catch (err) {
            console.warn('Erro ao exibir toast:', err);
        }
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // ----------------------------------------------------

    // ----------------------------------------------------
    // INSPEÇÃO DE PLANILHAS E SELETOR DE ABAS (EXCEL)
    // ----------------------------------------------------
    async function inspectAndRenderSheets(file, suffix) {
        const isSingle = (suffix === 'single');
        const configPanel = document.getElementById(isSingle ? 'single-file-config' : ('file-config-' + suffix));
        const sheetsPanel = document.getElementById(isSingle ? 'single-sheets-panel' : ('sheets-panel-' + suffix));
        const sheetsHint = document.getElementById(isSingle ? 'single-sheets-hint' : ('sheets-hint-' + suffix));
        const chipsContainer = document.getElementById(isSingle ? 'single-sheets-chips' : ('sheets-chips-' + suffix));
        const hiddenArea = document.getElementById(isSingle ? 'single-hidden-area' : ('hidden-area-' + suffix));
        const btnToggleHidden = document.getElementById(isSingle ? 'single-btn-toggle-hidden' : ('btn-toggle-hidden-' + suffix));
        const hiddenCount = document.getElementById(isSingle ? 'single-hidden-count' : ('hidden-count-' + suffix));
        const hiddenChips = document.getElementById(isSingle ? 'single-hidden-chips' : ('hidden-chips-' + suffix));
        const headerLineInput = document.getElementById(isSingle ? 'single-header-line' : ('header-line-' + suffix));

        if (configPanel) {
            configPanel.style.display = 'block';
        }
        const savedHeaderLine = isSingle ? singleState.userHeaderLine : (suffix === 'a' ? state.userHeaderLineA : state.userHeaderLineB);
        if (headerLineInput) {
            if (savedHeaderLine !== null && savedHeaderLine !== undefined) {
                headerLineInput.value = savedHeaderLine;
            } else {
                headerLineInput.value = 1;
            }
            if (!headerLineInput.hasAttribute('data-has-listener')) {
                headerLineInput.setAttribute('data-has-listener', 'true');
                headerLineInput.addEventListener('input', (e) => {
                    const val = parseInt(e.target.value, 10);
                    if (!isNaN(val) && val >= 1) {
                        if (isSingle) singleState.userHeaderLine = val;
                        else if (suffix === 'a') state.userHeaderLineA = val;
                        else if (suffix === 'b') state.userHeaderLineB = val;
                    }
                });
            }
        }

        const ext = file.name.split('.').pop().toLowerCase();
        const isExcel = ['xlsx', 'xls', 'xlsm'].includes(ext);

        if (!isExcel) {
            if (sheetsPanel) sheetsPanel.style.display = 'none';
            if (suffix === 'a') state.selectedSheetsA = [];
            else if (suffix === 'b') state.selectedSheetsB = [];
            else if (isSingle) singleState.selectedSheets = [];
            return;
        }

        if (sheetsPanel) sheetsPanel.style.display = 'block';
        if (chipsContainer) {
            chipsContainer.innerHTML = '<span style="font-size:11px; color:#64748b; padding:4px 0;">Carregando abas...</span>';
        }
        if (hiddenArea) hiddenArea.style.display = 'none';

        try {
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/api/excel-sheets', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            const sheets = data.sheets || [];
            const defaultSheet = data.default_sheet || (sheets.find(s => s.visible !== false)?.name || (sheets[0] ? sheets[0].name : null));

            let selectedList = defaultSheet ? [defaultSheet] : (sheets.length > 0 ? [sheets[0].name] : []);
            if (suffix === 'a') state.selectedSheetsA = [...selectedList];
            else if (suffix === 'b') state.selectedSheetsB = [...selectedList];
            else if (isSingle) singleState.selectedSheets = [...selectedList];

            renderSheetsChipsUI(sheets, selectedList, suffix, {
                sheetsHint,
                chipsContainer,
                hiddenArea,
                btnToggleHidden,
                hiddenCount,
                hiddenChips
            });
        } catch (err) {
            console.error('Erro ao inspecionar abas:', err);
            if (chipsContainer) {
                chipsContainer.innerHTML = '<span style="font-size:11px; color:#ef4444;">Não foi possível listar as abas</span>';
            }
        }
    }

    function renderSheetsChipsUI(sheets, initialSelected, suffix, elements) {
        const { sheetsHint, chipsContainer, hiddenArea, btnToggleHidden, hiddenCount, hiddenChips } = elements;

        function getSelected() {
            if (suffix === 'a') return state.selectedSheetsA || [];
            if (suffix === 'b') return state.selectedSheetsB || [];
            return singleState.selectedSheets || [];
        }

        function setSelected(list) {
            if (suffix === 'a') state.selectedSheetsA = list;
            else if (suffix === 'b') state.selectedSheetsB = list;
            else singleState.selectedSheets = list;
        }

        function updateHint() {
            if (!sheetsHint) return;
            const cur = getSelected();
            const count = cur.length;
            if (count === 0) {
                sheetsHint.textContent = 'Nenhuma aba selecionada';
            } else if (count === 1) {
                sheetsHint.textContent = cur[0];
            } else {
                sheetsHint.textContent = count + ' abas selecionadas';
            }
        }

        function createChipElement(sheet, isHidden) {
            const label = document.createElement('label');
            label.className = 'sheet-chip' + (isHidden ? ' hidden-sheet' : '');

            const isChecked = getSelected().includes(sheet.name);
            if (isChecked) {
                label.classList.add('active');
            }

            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.value = sheet.name;
            chk.checked = isChecked;

            chk.addEventListener('change', (e) => {
                e.stopPropagation();
                let cur = [...getSelected()];
                if (chk.checked) {
                    if (!cur.includes(sheet.name)) {
                        cur.push(sheet.name);
                    }
                    label.classList.add('active');
                } else {
                    cur = cur.filter(s => s !== sheet.name);
                    label.classList.remove('active');
                }
                setSelected(cur);
                updateHint();
            });

            const textSpan = document.createElement('span');
            textSpan.textContent = sheet.name;

            label.appendChild(chk);
            label.appendChild(textSpan);

            if (isHidden) {
                const badge = document.createElement('span');
                badge.className = 'sheet-badge-oculta';
                badge.textContent = 'Oculta';
                label.appendChild(badge);
            }

            label.addEventListener('click', (e) => {
                e.stopPropagation();
            });

            return label;
        }

        if (chipsContainer) {
            chipsContainer.innerHTML = '';
        }
        if (hiddenChips) {
            hiddenChips.innerHTML = '';
        }

        const visibleSheets = sheets.filter(s => s.visible !== false);
        const hiddenSheetsList = sheets.filter(s => s.visible === false);

        const toRenderVisible = visibleSheets.length > 0 ? visibleSheets : sheets;
        const toRenderHidden = visibleSheets.length > 0 ? hiddenSheetsList : [];

        toRenderVisible.forEach(sheet => {
            if (chipsContainer) {
                chipsContainer.appendChild(createChipElement(sheet, false));
            }
        });

        // Atalho "Selecionar Todas as Visíveis" / "Desmarcar Todas" (Passo 1)
        const isSingle = (suffix === 'single');
        const bulkContainer = document.getElementById(isSingle ? 'single-sheets-bulk' : ('sheets-bulk-' + suffix));
        const btnSelectAll = document.getElementById(isSingle ? 'single-btn-select-all' : ('btn-select-all-' + suffix));
        const btnDeselectAll = document.getElementById(isSingle ? 'single-btn-deselect-all' : ('btn-deselect-all-' + suffix));

        if (bulkContainer) {
            if (toRenderVisible.length >= 2) {
                bulkContainer.style.display = 'inline-flex';

                if (btnSelectAll) {
                    btnSelectAll.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const visNames = toRenderVisible.map(s => s.name);
                        let cur = [...getSelected()];
                        visNames.forEach(name => {
                            if (!cur.includes(name)) cur.push(name);
                        });
                        setSelected(cur);

                        if (chipsContainer) {
                            chipsContainer.querySelectorAll('.sheet-chip').forEach(lbl => {
                                const inp = lbl.querySelector('input[type="checkbox"]');
                                if (inp && visNames.includes(inp.value)) {
                                    inp.checked = true;
                                    lbl.classList.add('active');
                                }
                            });
                        }
                        updateHint();
                    };
                }

                if (btnDeselectAll) {
                    btnDeselectAll.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const visNames = toRenderVisible.map(s => s.name);
                        let cur = getSelected().filter(name => !visNames.includes(name));
                        setSelected(cur);

                        if (chipsContainer) {
                            chipsContainer.querySelectorAll('.sheet-chip').forEach(lbl => {
                                const inp = lbl.querySelector('input[type="checkbox"]');
                                if (inp && visNames.includes(inp.value)) {
                                    inp.checked = false;
                                    lbl.classList.remove('active');
                                }
                            });
                        }
                        updateHint();
                    };
                }
            } else {
                bulkContainer.style.display = 'none';
            }
        }

        if (hiddenArea && btnToggleHidden && hiddenCount && hiddenChips) {
            if (toRenderHidden.length > 0) {
                hiddenArea.style.display = 'block';
                hiddenCount.textContent = toRenderHidden.length;
                hiddenChips.style.display = 'none';

                toRenderHidden.forEach(sheet => {
                    hiddenChips.appendChild(createChipElement(sheet, true));
                });

                btnToggleHidden.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const isShowing = (hiddenChips.style.display !== 'none');
                    hiddenChips.style.display = isShowing ? 'none' : 'flex';
                    const eyeSvg = '<svg class="step2-eye-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> ';
                    btnToggleHidden.innerHTML = isShowing
                        ? eyeSvg + 'Mostrar abas ocultas (' + toRenderHidden.length + ')'
                        : eyeSvg + 'Ocultar abas ocultas (' + toRenderHidden.length + ')';
                };
            } else {
                hiddenArea.style.display = 'none';
            }
        }

        updateHint();
    }

    // PASSO 1: UPLOAD & DRAG AND DROP
    // ----------------------------------------------------
    function setupDropzone(dropzone, input, metaBox, nameSpan, sizeSpan, fileKey) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('drag-over');
            });
        });

        dropzone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect(files[0], dropzone, metaBox, nameSpan, sizeSpan, fileKey);
            }
        });

        dropzone.addEventListener('click', (e) => {
            if (e.target.closest('.file-config-panel')) {
                return;
            }
            if (e.target !== input) {
                input.click();
            }
        });

        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileSelect(e.target.files[0], dropzone, metaBox, nameSpan, sizeSpan, fileKey);
            }
        });
    }

    function handleFileSelect(file, dropzone, metaBox, nameSpan, sizeSpan, fileKey) {
        state[fileKey] = file;
        nameSpan.textContent = file.name;
        sizeSpan.textContent = formatBytes(file.size);
        metaBox.style.display = 'inline-flex';
        dropzone.classList.add('file-loaded');

        if (fileKey === 'fileA') {
            state.userHeaderLineA = null;
            state.selectedSheetsA = [];
            if (step2HeaderLineA) step2HeaderLineA.value = 1;
        } else if (fileKey === 'fileB') {
            state.userHeaderLineB = null;
            state.selectedSheetsB = [];
            if (step2HeaderLineB) step2HeaderLineB.value = 1;
        }

        const paywallNotice = document.getElementById('step1-paywall-notice');
        if (paywallNotice) paywallNotice.style.display = 'none';

        // Se ambos os arquivos foram selecionados, habilita o botão
        if (state.fileA && state.fileB) {
            btnReadHeaders.disabled = false;
        }
    }

    setupDropzone(dropzoneA, fileInputA, fileMetaA, filenameA, filesizeA, 'fileA');
    setupDropzone(dropzoneB, fileInputB, fileMetaB, filenameB, filesizeB, 'fileB');

    // ----------------------------------------------------
    // PASSO 1: TESTAR EXEMPLO DE PLANILHAS
    // ----------------------------------------------------
    if (btnSheetsTryExample) {
        btnSheetsTryExample.addEventListener('click', async () => {
            const paywallNotice = document.getElementById('step1-paywall-notice');
            if (paywallNotice) paywallNotice.style.display = 'none';

            btnSheetsTryExample.disabled = true;
            const originalHtml = btnSheetsTryExample.innerHTML;
            btnSheetsTryExample.innerHTML = '<span class="spinner" style="display: inline-block;"></span> Carregando Exemplo...';

            try {
                const response = await fetch('/api/sheets/load-example', {
                    method: 'POST'
                });

                const data = await response.json();

                if (!response.ok) {
                    alert(data.error || 'Erro ao carregar exemplo de planilhas.');
                    return;
                }

                // Atualizar dropzones com os arquivos de demonstração (limpos e simétricos no Passo 1)
                filenameA.textContent = data.filename_a || 'Base_Vendas_ERP_Anterior.xlsx';
                filesizeA.textContent = '14.2 KB';
                fileMetaA.style.display = 'inline-flex';
                dropzoneA.classList.add('file-loaded');

                filenameB.textContent = data.filename_b || 'Base_Vendas_ERP_Atualizada.xlsx';
                filesizeB.textContent = '14.5 KB';
                fileMetaB.style.display = 'inline-flex';
                dropzoneB.classList.add('file-loaded');

                state.userHeaderLineA = null;
                state.userHeaderLineB = null;
                if (step2HeaderLineA) step2HeaderLineA.value = 1;
                if (step2HeaderLineB) step2HeaderLineB.value = 1;
                state.selectedSheetsA = ['Vendas_ERP'];
                state.selectedSheetsB = ['Vendas_ERP'];

                btnReadHeaders.disabled = !(state.fileA && state.fileB);

                state.sessionId = data.session_id;
                state.columnsA = data.cols_a;
                state.columnsB = data.cols_b;
                state.initialMapping = { ...(data.column_mapping || {}) };
                state.mapping = data.column_mapping || {};
                state.selectedSecondaryKeys = [];
                state.isManualMapping = false;

                state.mappingList = Object.entries(state.mapping).map(([colA, colB], idx) => ({
                    id: 'map_' + idx + '_' + Math.random().toString(36).substring(2, 7),
                    colA: colA,
                    colB: colB
                }));

                selectPrimaryKey.innerHTML = '<option value="">Selecione a chave primária...</option>';
                state.columnsA.forEach(col => {
                    const opt = document.createElement('option');
                    opt.value = col;
                    opt.textContent = col;
                    selectPrimaryKey.appendChild(opt);
                });

                if (data.suggested_keys && data.suggested_keys.length > 0) {
                    const foundKey = data.suggested_keys.find(k => state.columnsA.includes(k));
                    if (foundKey) {
                        selectPrimaryKey.value = foundKey;
                    }
                }

                if (!selectPrimaryKey.value && state.columnsA.length > 0) {
                    const idKeywords = ['CHASSI', 'VIN', 'NOTAFISCAL', 'NUMNF', 'NF', 'NUMERONOTA', 'ID', 'CPF', 'CNPJ', 'MATRICULA', 'CODIGO', 'COD', 'PEDIDO', 'TICKET', 'SERIAL', 'PROTOCOLO'];
                    const lowKeywords = ['MARCA', 'STATUS', 'SITUACAO', 'UF', 'TIPO', 'CATEGORIA', 'ESTADO', 'CIDADE', 'ATIVO', 'SEXO'];
                    const candidate = state.columnsA.find(col => {
                        const clean = col.toUpperCase().replace(/[^A-Z0-9]/g, '');
                        return idKeywords.some(k => clean.includes(k)) && !lowKeywords.some(k => clean.includes(k));
                    });
                    if (candidate) {
                        selectPrimaryKey.value = candidate;
                    }
                }

                renderSecondaryKeysOptions();
                updateSecondaryKeysUI();
                renderMappingTable();
                setupStep2Sheets(data);

                stepConfig.style.display = 'block';
                stepConfig.scrollIntoView({ behavior: 'smooth', block: 'start' });

            } catch (err) {
                console.error(err);
                alert('Falha na comunicação com o servidor: ' + err.message);
            } finally {
                btnSheetsTryExample.disabled = false;
                btnSheetsTryExample.innerHTML = originalHtml;
            }
        });
    }

    // ----------------------------------------------------
    // PASSO 1 -> PASSO 2: LER CABEÇALHOS
    // ----------------------------------------------------
    btnReadHeaders.addEventListener('click', async () => {
        if (!state.fileA || !state.fileB) return;

        setBtnLoading(btnReadHeaders, true, 'Lendo cabeçalhos e analisando...');

        const formData = new FormData();
        formData.append('file_a', state.fileA);
        formData.append('file_b', state.fileB);
        const hlA = (state.userHeaderLineA !== null && state.userHeaderLineA !== undefined)
            ? state.userHeaderLineA
            : 1;
        const hlB = (state.userHeaderLineB !== null && state.userHeaderLineB !== undefined)
            ? state.userHeaderLineB
            : 1;
        formData.append('header_line_a', hlA);
        formData.append('header_line_b', hlB);
        if (state.selectedSheetsA && state.selectedSheetsA.length > 0) {
            formData.append('sheets_a', JSON.stringify(state.selectedSheetsA));
        }
        if (state.selectedSheetsB && state.selectedSheetsB.length > 0) {
            formData.append('sheets_b', JSON.stringify(state.selectedSheetsB));
        }

        try {
            const response = await fetch('/api/upload-headers', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                alert(data.error || 'Erro ao processar planilhas.');
                setBtnLoading(btnReadHeaders, false);
                return;
            }

            // Paywall Proativo e Transparente no Passo 1 (Limite de 500 linhas no plano Standard)
            const rowsA = Number(data.rows_a_count) || 0;
            const rowsB = Number(data.rows_b_count) || 0;
            const maxRows = Math.max(rowsA, rowsB);
            const userPlan = window.VALIDAI_USER_PLAN || (document.body && document.body.getAttribute('data-user-plan')) || 'standard';
            const paywallNotice = document.getElementById('step1-paywall-notice');
            const paywallCount = document.getElementById('step1-paywall-rows-count');

            if (userPlan === 'standard' && maxRows > 500) {
                if (paywallCount) {
                    paywallCount.textContent = maxRows.toLocaleString('pt-BR');
                }
                if (paywallNotice) {
                    paywallNotice.style.display = 'flex';
                }
            } else if (paywallNotice) {
                paywallNotice.style.display = 'none';
            }

            const alertUnnamed = document.getElementById('alert-unnamed-cols');
            if (alertUnnamed) {
                alertUnnamed.style.display = data.has_unnamed ? 'flex' : 'none';
            }

            state.sessionId = data.session_id;
            state.columnsA = data.cols_a;
            state.columnsB = data.cols_b;
            state.initialMapping = { ...(data.column_mapping || {}) };
            state.mapping = data.column_mapping || {};
            state.selectedSecondaryKeys = [];
            state.isManualMapping = false;

            // Inicializar lista de mapeamentos editáveis
            state.mappingList = Object.entries(state.mapping).map(([colA, colB], idx) => ({
                id: 'map_' + idx + '_' + Math.random().toString(36).substring(2, 7),
                colA: colA,
                colB: colB
            }));

            // Popular Dropdown de Chave Primária (Coluna da Esquerda)
            selectPrimaryKey.innerHTML = '<option value="">Selecione a chave primária...</option>';

            state.columnsA.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.textContent = col;
                selectPrimaryKey.appendChild(opt);
            });

            // Selecionar sugestão inteligente automaticamente se houver
            if (data.suggested_keys && data.suggested_keys.length > 0) {
                const foundKey = data.suggested_keys.find(k => state.columnsA.includes(k));
                if (foundKey) {
                    selectPrimaryKey.value = foundKey;
                }
            }

            // Fallback de segurança no frontend: prioriza identificadores e nunca seleciona MARCA/categórica
            if (!selectPrimaryKey.value && state.columnsA.length > 0) {
                const idKeywords = ['CHASSI', 'VIN', 'NOTAFISCAL', 'NUMNF', 'NF', 'NUMERONOTA', 'ID', 'CPF', 'CNPJ', 'MATRICULA', 'CODIGO', 'COD', 'PEDIDO', 'TICKET', 'SERIAL', 'PROTOCOLO'];
                const lowKeywords = ['MARCA', 'STATUS', 'SITUACAO', 'UF', 'TIPO', 'CATEGORIA', 'ESTADO', 'CIDADE', 'ATIVO', 'SEXO'];
                const candidate = state.columnsA.find(col => {
                    const clean = col.toUpperCase().replace(/[^A-Z0-9]/g, '');
                    return idKeywords.some(k => clean.includes(k)) && !lowKeywords.some(k => clean.includes(k));
                });
                if (candidate) {
                    selectPrimaryKey.value = candidate;
                }
            }

            // Inicializar o seletor múltiplo da coluna da direita
            renderSecondaryKeysOptions();
            updateSecondaryKeysUI();

            // Renderizar tabela de mapeamento de colunas
            renderMappingTable();
            setupStep2Sheets(data);

            // Exibir Passo 2 com transição suave
            stepConfig.style.display = 'block';
            stepConfig.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (err) {
            console.error(err);
            alert('Falha na comunicação com o servidor: ' + err.message);
        } finally {
            setBtnLoading(btnReadHeaders, false);
        }
    });

    // ----------------------------------------------------
    // GERENCIAMENTO DO SELETOR MÚLTIPLO (COLUNA DA DIREITA)
    // ----------------------------------------------------
    function renderSecondaryKeysOptions(filterText = '') {
        secKeysOptionsList.innerHTML = '';
        const currentPk = selectPrimaryKey.value;
        const query = (filterText || '').toLowerCase().trim();

        // Lista de colunas disponíveis excluindo a chave primária
        const availableCols = state.columnsA.filter(c => c !== currentPk);

        const filteredCols = query 
            ? availableCols.filter(c => c.toLowerCase().includes(query))
            : availableCols;

        if (filteredCols.length === 0) {
            secKeysOptionsList.innerHTML = '<div style="padding: 12px; text-align: center; color: #64748b; font-size: 13px;">Nenhuma coluna encontrada</div>';
            return;
        }

        filteredCols.forEach(col => {
            const isChecked = state.selectedSecondaryKeys.includes(col);
            const label = document.createElement('label');
            label.className = 'multiselect-option' + (isChecked ? ' selected' : '');
            label.innerHTML = `
                <input type="checkbox" value="${escapeHtml(col)}" ${isChecked ? 'checked' : ''}>
                <span>${escapeHtml(col)}</span>
            `;

            const chk = label.querySelector('input');
            chk.addEventListener('change', (e) => {
                const val = e.target.value;
                if (e.target.checked) {
                    if (!state.selectedSecondaryKeys.includes(val)) {
                        state.selectedSecondaryKeys.push(val);
                    }
                    label.classList.add('selected');
                } else {
                    state.selectedSecondaryKeys = state.selectedSecondaryKeys.filter(k => k !== val);
                    label.classList.remove('selected');
                }
                updateSecondaryKeysUI();
            });

            secKeysOptionsList.appendChild(label);
        });
    }

    function updateSecondaryKeysUI() {
        const count = state.selectedSecondaryKeys.length;
        if (count === 0) {
            secKeysLabel.textContent = 'Nenhuma coluna complementar selecionada';
            secKeysLabel.style.color = 'var(--text-muted)';
        } else if (count === 1) {
            secKeysLabel.textContent = `1 coluna: ${state.selectedSecondaryKeys[0]}`;
            secKeysLabel.style.color = 'var(--text-main)';
        } else {
            secKeysLabel.textContent = `${count} colunas selecionadas para validação`;
            secKeysLabel.style.color = 'var(--text-main)';
        }

        // Renderizar tags/chips das colunas selecionadas
        selectedSecKeysTags.innerHTML = '';
        state.selectedSecondaryKeys.forEach(col => {
            const chip = document.createElement('span');
            chip.className = 'tag-chip';
            chip.innerHTML = `
                <span>${escapeHtml(col)}</span>
                <span class="tag-remove" data-col="${escapeHtml(col)}" title="Remover coluna">×</span>
            `;
            chip.querySelector('.tag-remove').addEventListener('click', (e) => {
                e.stopPropagation();
                const removeCol = e.target.dataset.col;
                state.selectedSecondaryKeys = state.selectedSecondaryKeys.filter(k => k !== removeCol);
                updateSecondaryKeysUI();
                renderSecondaryKeysOptions(secKeysSearch.value);
            });
            selectedSecKeysTags.appendChild(chip);
        });
    }

    // Abertura e fechamento do dropdown multiselect
    secKeysTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = secKeysDropdown.style.display === 'flex';
        secKeysDropdown.style.display = isOpen ? 'none' : 'flex';
        secKeysTrigger.classList.toggle('active', !isOpen);
        if (!isOpen) {
            secKeysSearch.value = '';
            renderSecondaryKeysOptions();
            secKeysSearch.focus();
        }
    });

    secKeysSearch.addEventListener('input', (e) => {
        renderSecondaryKeysOptions(e.target.value);
    });

    btnClearSecKeys.addEventListener('click', (e) => {
        e.stopPropagation();
        state.selectedSecondaryKeys = [];
        updateSecondaryKeysUI();
        renderSecondaryKeysOptions(secKeysSearch.value);
    });

    btnCloseSecKeys.addEventListener('click', (e) => {
        e.stopPropagation();
        secKeysDropdown.style.display = 'none';
        secKeysTrigger.classList.remove('active');
    });

    // Fechar ao clicar fora
    document.addEventListener('click', (e) => {
        const container = document.getElementById('multiselect-container');
        if (container && !container.contains(e.target)) {
            secKeysDropdown.style.display = 'none';
            secKeysTrigger.classList.remove('active');
        }
    });

    // Se a chave primária for alterada, atualiza o seletor múltiplo para não conter a mesma chave
    selectPrimaryKey.addEventListener('change', () => {
        const pk = selectPrimaryKey.value;
        if (state.selectedSecondaryKeys.includes(pk)) {
            state.selectedSecondaryKeys = state.selectedSecondaryKeys.filter(k => k !== pk);
            updateSecondaryKeysUI();
        }
        renderSecondaryKeysOptions(secKeysSearch.value);
    });

    function updateMappingStateAndHints() {
        const newMapping = {};
        state.mappingList.forEach(item => {
            if (item.colA && item.colB) {
                newMapping[item.colA] = item.colB;
            }
        });
        state.mapping = newMapping;
        mappedColsCount.textContent = Object.keys(newMapping).length;

        // Alerta informativo sobre colunas não mapeadas
        if (unmappedHint) {
            const mappedA = new Set(state.mappingList.map(it => it.colA).filter(Boolean));
            const unmappedA = state.columnsA.filter(c => !mappedA.has(c));

            const mappedB = new Set(state.mappingList.map(it => it.colB).filter(Boolean));
            const unmappedB = state.columnsB.filter(c => !mappedB.has(c));

            if (unmappedA.length > 0 || unmappedB.length > 0) {
                let msg = '';
                if (unmappedA.length > 0) {
                    const maxShow = 8;
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
                    const maxShow = 8;
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
            } else {
                unmappedHint.style.display = 'none';
                unmappedHint.innerHTML = '';
            }
        }
    }

    // ----------------------------------------------------
    // CONTROLE DO DROPDOWN PESQUISÁVEL DE MAPEAMENTO
    // ----------------------------------------------------
    let activeDropdownState = null; // { itemId, colType: 'colA'|'colB', triggerEl }

    function normalizeSearch(str) {
        return (str || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .trim();
    }

    function openMappingDropdown(itemId, colType, triggerEl) {
        if (activeDropdownState && activeDropdownState.triggerEl === triggerEl) {
            closeMappingDropdown();
            return;
        }

        closeMappingDropdown();

        activeDropdownState = { itemId, colType, triggerEl };
        triggerEl.classList.add('active');

        const portal = document.getElementById('mapping-dropdown-portal');
        const searchInput = document.getElementById('mapping-dropdown-search');
        const clearBtn = document.getElementById('mapping-dropdown-clear-btn');
        if (searchInput) searchInput.value = '';
        if (clearBtn) clearBtn.style.display = 'none';

        renderMappingDropdownOptions('');

        if (portal) {
            portal.style.display = 'flex';
            positionMappingDropdown(triggerEl, portal);
        }

        setTimeout(() => {
            if (searchInput) searchInput.focus();
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
        if (!activeDropdownState) return;
        const { itemId, colType } = activeDropdownState;
        const item = state.mappingList.find(it => it.id === itemId);
        if (!item) return;

        const allCols = colType === 'colA' ? state.columnsA : state.columnsB;
        const currentVal = colType === 'colA' ? item.colA : item.colB;

        const normFilter = normalizeSearch(filterText);
        const filteredCols = allCols.filter(c => normalizeSearch(c).includes(normFilter));

        const listEl = document.getElementById('mapping-dropdown-options');
        if (!listEl) return;
        listEl.innerHTML = '';

        // Opção para desmarcar / selecionar vazio
        const emptyOpt = document.createElement('div');
        emptyOpt.className = 'dropdown-option is-empty-option' + (!currentVal ? ' selected' : '');
        emptyOpt.innerHTML = `<span>(Nenhuma coluna selecionada)</span>`;
        emptyOpt.addEventListener('click', () => {
            selectMappingDropdownOption('');
        });
        listEl.appendChild(emptyOpt);

        if (filteredCols.length === 0) {
            const noRes = document.createElement('div');
            noRes.className = 'dropdown-no-results';
            noRes.textContent = 'Nenhuma coluna encontrada.';
            listEl.appendChild(noRes);
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
            listEl.appendChild(opt);
        });
    }

    function selectMappingDropdownOption(colValue) {
        if (!activeDropdownState) return;
        const { itemId, colType } = activeDropdownState;
        const item = state.mappingList.find(it => it.id === itemId);
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
        const portal = document.getElementById('mapping-dropdown-portal');
        if (portal) portal.style.display = 'none';
        if (activeDropdownState && activeDropdownState.triggerEl) {
            activeDropdownState.triggerEl.classList.remove('active');
        }
        activeDropdownState = null;
    }

    // Eventos do campo de busca do dropdown de mapeamento
    const mappingSearchInput = document.getElementById('mapping-dropdown-search');
    const mappingClearBtn = document.getElementById('mapping-dropdown-clear-btn');
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
                if (firstOption) {
                    firstOption.click();
                }
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

    // Fechar dropdown de mapeamento ao clicar fora ou pressionar Escape
    document.addEventListener('click', (e) => {
        if (!activeDropdownState) return;
        const portal = document.getElementById('mapping-dropdown-portal');
        if (portal && (portal.contains(e.target) || activeDropdownState.triggerEl.contains(e.target))) {
            return;
        }
        closeMappingDropdown();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && activeDropdownState) {
            closeMappingDropdown();
        }
    });

    // Manter o dropdown ancorado ao rolar a página ou redimensionar a janela
    window.addEventListener('scroll', () => {
        if (activeDropdownState) {
            const portal = document.getElementById('mapping-dropdown-portal');
            if (portal && portal.style.display === 'flex') {
                positionMappingDropdown(activeDropdownState.triggerEl, portal);
            }
        }
    }, true);

    window.addEventListener('resize', () => {
        if (activeDropdownState) {
            const portal = document.getElementById('mapping-dropdown-portal');
            if (portal && portal.style.display === 'flex') {
                positionMappingDropdown(activeDropdownState.triggerEl, portal);
            }
        }
    });

    function renderMappingTable() {
        mappingTableBody.innerHTML = '';

        if (!state.mappingList || state.mappingList.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td colspan="4" style="text-align: center; color: #64748b; padding: 24px;">
                    Nenhuma coluna associada ainda. Clique no botão <strong>"+ Adicionar Coluna"</strong> acima para mapear.
                </td>
            `;
            mappingTableBody.appendChild(tr);
            updateMappingStateAndHints();
            return;
        }

        state.mappingList.forEach((item) => {
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
            mappingTableBody.appendChild(tr);
        });

        // Eventos de clique nos triggers da coluna da esquerda e direita
        mappingTableBody.querySelectorAll('.mapping-col-a').forEach(trigger => {
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

        mappingTableBody.querySelectorAll('.mapping-col-b').forEach(trigger => {
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
        mappingTableBody.querySelectorAll('.btn-remove-row').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.dataset.id;
                state.mappingList = state.mappingList.filter(it => it.id !== id);
                renderMappingTable();
            });
        });

        updateMappingStateAndHints();
    }

    // Botão "+ Adicionar Coluna"
    if (btnAddMapping) {
        btnAddMapping.addEventListener('click', () => {
            let nextA = '';
            let nextB = '';

            // Se NÃO estiver em modo de seleção manual (pós-clique em Limpar Mapeamentos),
            // puxa automaticamente as colunas que estão faltando (igual funcionava antes)
            if (!state.isManualMapping) {
                const usedA = new Set(state.mappingList.map(it => it.colA).filter(Boolean));
                const unusedA = state.columnsA.filter(c => !usedA.has(c));
                nextA = unusedA.length > 0 ? unusedA[0] : '';

                const usedB = new Set(state.mappingList.map(it => it.colB).filter(Boolean));
                const unusedB = state.columnsB.filter(c => !usedB.has(c));
                if (nextA && state.initialMapping && state.initialMapping[nextA] && unusedB.includes(state.initialMapping[nextA])) {
                    nextB = state.initialMapping[nextA];
                } else {
                    nextB = unusedB.length > 0 ? unusedB[0] : '';
                }
            }

            const newItem = {
                id: 'map_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
                colA: nextA,
                colB: nextB
            };

            state.mappingList.push(newItem);
            renderMappingTable();

            // Rolar a tabela para a nova linha criada
            const wrapper = document.querySelector('.mapping-table-wrapper');
            if (wrapper) {
                wrapper.scrollTop = wrapper.scrollHeight;
            }

            // Se estiver em modo manual, foca no seletor da nova linha
            if (state.isManualMapping) {
                setTimeout(() => {
                    const newRowTrigger = document.querySelector(`.mapping-col-a[data-id="${newItem.id}"]`);
                    if (newRowTrigger) {
                        newRowTrigger.focus();
                    }
                }, 60);
            }
        });
    }

    // Botão "Restaurar Mapeamento" (fundo verde com ícone de planilha)
    if (btnRestoreMapping) {
        btnRestoreMapping.addEventListener('click', () => {
            // Desativa modo manual para que a adição volte a auto-completar colunas faltantes
            state.isManualMapping = false;

            const sourceMap = (state.initialMapping && Object.keys(state.initialMapping).length > 0)
                ? state.initialMapping
                : (state.mapping || {});

            state.mappingList = Object.entries(sourceMap).map(([colA, colB], idx) => ({
                id: 'map_' + idx + '_' + Math.random().toString(36).substring(2, 7),
                colA: colA,
                colB: colB
            }));

            renderMappingTable();

            // Rolar a tabela para o topo
            const wrapper = document.querySelector('.mapping-table-wrapper');
            if (wrapper) {
                wrapper.scrollTop = 0;
            }
        });
    }

    // ----------------------------------------------------
    // MODAL DE LIMPEZA E SELEÇÃO DE MAPEAMENTOS POR CHECKBOX
    // ----------------------------------------------------
    let modalSelectedCols = new Set();
    let modalAutoPairs = [];

    function openClearMappingModal() {
        if (!modalClearMapping) return;

        // Fecha dropdown de coluna caso esteja aberto
        closeMappingDropdown();

        const sourceMap = (state.initialMapping && Object.keys(state.initialMapping).length > 0)
            ? state.initialMapping
            : (state.mapping || {});

        modalAutoPairs = Object.entries(sourceMap).map(([colA, colB]) => ({ colA, colB }));

        modalSelectedCols.clear();
        const currentlyMappedA = new Set(state.mappingList.map(it => it.colA).filter(Boolean));
        // Se apenas um subconjunto estava selecionado, mantém pré-marcado para facilitar ajustes;
        // se todas estavam mapeadas (estado inicial), inicia desmarcado para o usuário escolher as desejadas.
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

    // Botão "Limpar Mapeamentos" (fundo vermelho com lixeira) -> abre popup
    if (btnClearMapping) {
        btnClearMapping.addEventListener('click', () => {
            openClearMappingModal();
        });
    }

    // Opção 1 do Popup: "Limpar Tudo" (mantém exatamente como funcionava antes ao limpar)
    if (btnModalClearAll) {
        btnModalClearAll.addEventListener('click', () => {
            closeClearMappingModal();

            // Ativa o modo de seleção manual para que as colunas sejam escolhidas na mão
            state.isManualMapping = true;

            state.mappingList = [
                {
                    id: 'map_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
                    colA: '',
                    colB: ''
                }
            ];
            renderMappingTable();

            // Rolar a tabela para o topo
            const wrapper = document.querySelector('.mapping-table-wrapper');
            if (wrapper) {
                wrapper.scrollTop = 0;
            }

            // Focar o seletor da primeira linha
            setTimeout(() => {
                const firstTrigger = mappingTableBody.querySelector('.mapping-col-a');
                if (firstTrigger) {
                    firstTrigger.focus();
                }
            }, 60);
        });
    }

    // Opção 2 do Popup: "Aplicar Mapeamento Selecionado" (traz direto o mapeamento automático das colunas marcadas)
    if (btnModalApply) {
        btnModalApply.addEventListener('click', () => {
            if (modalSelectedCols.size === 0) {
                alert('Marque pelo menos uma coluna na lista para manter no mapeamento, ou clique em "Limpar Tudo" acima para esvaziar a tabela.');
                return;
            }

            // Mantém o modo inteligente ativo (se deletar ou adicionar depois, puxa as colunas que faltam)
            state.isManualMapping = false;

            state.mappingList = modalAutoPairs
                .filter(p => modalSelectedCols.has(p.colA))
                .map((p, idx) => ({
                    id: 'map_' + idx + '_' + Math.random().toString(36).substring(2, 7),
                    colA: p.colA,
                    colB: p.colB
                }));

            renderMappingTable();
            closeClearMappingModal();

            const wrapper = document.querySelector('.mapping-table-wrapper');
            if (wrapper) {
                wrapper.scrollTop = 0;
            }
        });
    }

    // Botões Marcar Todas / Desmarcar Todas no Modal
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

    // Busca no Modal
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

    // Fechar Modal (botão X, botão Cancelar, clique no backdrop, tecla Escape)
    if (btnModalClose) {
        btnModalClose.addEventListener('click', closeClearMappingModal);
    }
    if (btnModalCancel) {
        btnModalCancel.addEventListener('click', closeClearMappingModal);
    }
    if (modalClearMapping) {
        modalClearMapping.addEventListener('click', (e) => {
            if (e.target === modalClearMapping) {
                closeClearMappingModal();
            }
        });
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalClearMapping && modalClearMapping.classList.contains('is-open')) {
            closeClearMappingModal();
        }
    });

    // ----------------------------------------------------
    // SELETOR MULTI-SELECT DE ABAS E CABEÇALHO NO PASSO 2
    // ----------------------------------------------------
    let step2ShowHiddenA = false;
    let step2ShowHiddenB = false;
    let step2SheetsDataA = [];
    let step2SheetsDataB = [];
    let step2DefaultSheetA = null;
    let step2DefaultSheetB = null;
    let step2ReloadTimer = null;
    let isReloadingStep2 = false;
    let pendingReloadStep2 = false;

    function normalizeStep2SheetSelection(val, sheetsInfo) {
        try {
            if (!Array.isArray(sheetsInfo) || sheetsInfo.length === 0) {
                return [];
            }
            const validNames = sheetsInfo.map(s => s.name);
            if (Array.isArray(val) && val.length > 0) {
                const filtered = val.filter(n => validNames.includes(n));
                if (filtered.length > 0) return filtered;
            } else if (typeof val === 'string' && val.trim() !== '') {
                if (validNames.includes(val)) return [val];
            }
            const firstVis = sheetsInfo.find(s => s.visible !== false);
            return firstVis ? [firstVis.name] : [sheetsInfo[0].name];
        } catch (err) {
            console.warn('Erro ao normalizar abas selecionadas:', err);
            return [];
        }
    }

    function getStep2SelectedSheets(suffix) {
        return suffix === 'a' ? (state.selectedSheetsA || []) : (state.selectedSheetsB || []);
    }

    function setStep2SelectedSheets(suffix, list, sheetsInfo) {
        const orderMap = new Map((sheetsInfo || []).map((s, idx) => [s.name, idx]));
        const uniqueOrdered = Array.from(new Set(list || [])).sort((x, y) => {
            const ix = orderMap.has(x) ? orderMap.get(x) : 9999;
            const iy = orderMap.has(y) ? orderMap.get(y) : 9999;
            return ix - iy;
        });
        if (suffix === 'a') {
            state.selectedSheetsA = uniqueOrdered;
        } else {
            state.selectedSheetsB = uniqueOrdered;
        }
    }

    function closeStep2Dropdown(suffix) {
        try {
            const isA = (suffix === 'a');
            const trigger = isA ? step2SheetTriggerA : step2SheetTriggerB;
            const dropdown = isA ? step2SheetDropdownA : step2SheetDropdownB;
            const card = isA ? step2CardA : step2CardB;
            if (dropdown) dropdown.style.display = 'none';
            if (trigger) {
                trigger.classList.remove('active');
                trigger.setAttribute('aria-expanded', 'false');
            }
            if (card) card.classList.remove('has-open-dropdown');
        } catch (err) {
            console.warn('Erro ao fechar dropdown de abas:', err);
        }
    }

    function closeAllStep2Dropdowns() {
        closeStep2Dropdown('a');
        closeStep2Dropdown('b');
    }

    function toggleStep2Dropdown(suffix) {
        try {
            const isA = (suffix === 'a');
            const trigger = isA ? step2SheetTriggerA : step2SheetTriggerB;
            const dropdown = isA ? step2SheetDropdownA : step2SheetDropdownB;
            const card = isA ? step2CardA : step2CardB;
            if (!trigger || !dropdown || trigger.disabled || trigger.classList.contains('is-disabled')) {
                return;
            }
            const isOpen = dropdown.style.display !== 'none';
            closeStep2Dropdown(isA ? 'b' : 'a');
            if (isOpen) {
                closeStep2Dropdown(suffix);
            } else {
                dropdown.style.display = 'flex';
                trigger.classList.add('active');
                trigger.setAttribute('aria-expanded', 'true');
                if (card) card.classList.add('has-open-dropdown');
            }
        } catch (err) {
            console.warn('Erro ao alternar dropdown de abas:', err);
        }
    }

    function updateStep2TriggerLabel(suffix) {
        try {
            const isA = (suffix === 'a');
            const trigger = isA ? step2SheetTriggerA : step2SheetTriggerB;
            const labelEl = isA ? step2SheetLabelA : step2SheetLabelB;
            const sheets = isA ? step2SheetsDataA : step2SheetsDataB;
            if (!trigger || !labelEl) return;

            if (!sheets || sheets.length <= 1) {
                labelEl.textContent = 'Arquivo único / CSV';
                trigger.title = 'Arquivo único / CSV';
                trigger.classList.remove('is-placeholder');
                return;
            }

            const selected = getStep2SelectedSheets(suffix);
            if (selected.length === 0) {
                labelEl.textContent = 'Nenhuma aba selecionada';
                trigger.title = 'Selecione ao menos uma aba para validar';
                trigger.classList.add('is-placeholder');
            } else if (selected.length === 1) {
                labelEl.textContent = selected[0];
                trigger.title = selected[0];
                trigger.classList.remove('is-placeholder');
            } else if (selected.length === 2) {
                const summary = `${selected[0]}, ${selected[1]} (2 selecionadas)`;
                labelEl.textContent = summary;
                trigger.title = selected.join(', ');
                trigger.classList.remove('is-placeholder');
            } else {
                const summary = `${selected[0]}, ${selected[1]}... (${selected.length} selecionadas)`;
                labelEl.textContent = summary;
                trigger.title = selected.join(', ');
                trigger.classList.remove('is-placeholder');
            }
        } catch (err) {
            console.warn('Erro ao atualizar resumo de abas:', err);
        }
    }

    function renderStep2SheetOptions(suffix) {
        try {
            const isA = (suffix === 'a');
            const trigger = isA ? step2SheetTriggerA : step2SheetTriggerB;
            const optionsContainer = isA ? step2SheetOptionsA : step2SheetOptionsB;
            const btnToggle = document.getElementById(isA ? 'btn-toggle-hidden-step2-a' : 'btn-toggle-hidden-step2-b');
            const countSpan = document.getElementById(isA ? 'step2-hidden-count-a' : 'step2-hidden-count-b');
            const sheets = isA ? step2SheetsDataA : step2SheetsDataB;
            const showHidden = isA ? step2ShowHiddenA : step2ShowHiddenB;

            if (!trigger || !optionsContainer) return;

            // Arquivo CSV ou Excel de aba única -> indicador fixo e desabilitado
            if (!sheets || sheets.length <= 1) {
                closeStep2Dropdown(suffix);
                optionsContainer.innerHTML = '';
                trigger.disabled = true;
                trigger.classList.add('is-disabled');
                trigger.setAttribute('aria-disabled', 'true');
                if (sheets && sheets.length === 1) {
                    setStep2SelectedSheets(suffix, [sheets[0].name], sheets);
                } else {
                    setStep2SelectedSheets(suffix, [], []);
                }
                if (btnToggle) {
                    btnToggle.style.display = 'none';
                    btnToggle.classList.remove('is-active');
                }
                updateStep2TriggerLabel(suffix);
                return;
            }

            trigger.disabled = false;
            trigger.classList.remove('is-disabled');
            trigger.removeAttribute('aria-disabled');

            const visibleSheets = sheets.filter(s => s.visible !== false);
            const hiddenSheets = sheets.filter(s => s.visible === false);

            // Configuração do botão toggle de abas ocultas
            if (btnToggle) {
                if (hiddenSheets.length > 0) {
                    btnToggle.style.display = 'inline-flex';
                    if (countSpan) countSpan.textContent = hiddenSheets.length;
                    btnToggle.classList.toggle('is-active', !!showHidden);
                    btnToggle.setAttribute('aria-pressed', showHidden ? 'true' : 'false');
                    btnToggle.setAttribute('title', showHidden ? 'Ocultar abas ocultas' : 'Mostrar abas ocultas');
                } else {
                    btnToggle.style.display = 'none';
                    btnToggle.classList.remove('is-active');
                }
            }

            optionsContainer.innerHTML = '';

            function appendSheetCheckboxItem(sheetObj) {
                const isHidden = sheetObj.visible === false;
                const isChecked = getStep2SelectedSheets(suffix).includes(sheetObj.name);

                const lbl = document.createElement('label');
                lbl.className = 'step2-sheet-option' + (isChecked ? ' selected' : '');
                lbl.setAttribute('role', 'option');
                lbl.setAttribute('aria-selected', isChecked ? 'true' : 'false');

                const chk = document.createElement('input');
                chk.type = 'checkbox';
                chk.value = sheetObj.name;
                chk.checked = isChecked;

                chk.addEventListener('change', (e) => {
                    e.stopPropagation();
                    try {
                        let cur = [...getStep2SelectedSheets(suffix)];
                        if (chk.checked) {
                            if (!cur.includes(sheetObj.name)) cur.push(sheetObj.name);
                            lbl.classList.add('selected');
                            lbl.setAttribute('aria-selected', 'true');
                        } else {
                            cur = cur.filter(n => n !== sheetObj.name);
                            lbl.classList.remove('selected');
                            lbl.setAttribute('aria-selected', 'false');
                        }
                        setStep2SelectedSheets(suffix, cur, sheets);
                        updateStep2TriggerLabel(suffix);
                        if (cur.length > 0) {
                            scheduleReloadHeadersStep2();
                        }
                    } catch (innerErr) {
                        console.warn('Erro ao selecionar aba:', innerErr);
                    }
                });

                const nameSpan = document.createElement('span');
                nameSpan.className = 'step2-sheet-option-name';
                nameSpan.textContent = sheetObj.name;
                nameSpan.title = sheetObj.name;

                lbl.appendChild(chk);
                lbl.appendChild(nameSpan);

                if (isHidden) {
                    const badge = document.createElement('span');
                    badge.className = 'sheet-badge-oculta';
                    badge.textContent = 'Oculta';
                    lbl.appendChild(badge);
                }

                lbl.addEventListener('click', (e) => {
                    e.stopPropagation();
                });

                optionsContainer.appendChild(lbl);
            }

            if (showHidden && hiddenSheets.length > 0 && visibleSheets.length > 0) {
                const visHeader = document.createElement('div');
                visHeader.className = 'step2-sheet-group-label';
                visHeader.textContent = 'Abas Visíveis';
                optionsContainer.appendChild(visHeader);
                visibleSheets.forEach(s => appendSheetCheckboxItem(s));

                const hidHeader = document.createElement('div');
                hidHeader.className = 'step2-sheet-group-label';
                hidHeader.textContent = 'Abas Ocultas no Excel';
                optionsContainer.appendChild(hidHeader);
                hiddenSheets.forEach(s => appendSheetCheckboxItem(s));
            } else {
                const listToRender = showHidden
                    ? [...visibleSheets, ...hiddenSheets]
                    : (visibleSheets.length > 0 ? visibleSheets : sheets);
                listToRender.forEach(s => appendSheetCheckboxItem(s));
            }

            updateStep2TriggerLabel(suffix);
        } catch (err) {
            console.error('Erro ao renderizar opções de abas no Passo 2:', err);
        }
    }

    function setupStep2Sheets(data) {
        try {
            if (!step2SheetsConfig) return;
            closeAllStep2Dropdowns();

            step2SheetsDataA = (data && data.sheets_info_a) ? data.sheets_info_a : [];
            step2SheetsDataB = (data && data.sheets_info_b) ? data.sheets_info_b : [];
            step2DefaultSheetA = data ? data.default_sheet_a : null;
            step2DefaultSheetB = data ? data.default_sheet_b : null;

            setStep2SelectedSheets('a', normalizeStep2SheetSelection(step2DefaultSheetA, step2SheetsDataA), step2SheetsDataA);
            setStep2SelectedSheets('b', normalizeStep2SheetSelection(step2DefaultSheetB, step2SheetsDataB), step2SheetsDataB);

            if (!data || !data.has_multiple_sheets) {
                step2SheetsConfig.style.display = 'none';
                return;
            }

            step2SheetsConfig.style.display = 'block';

            if (step2FilenameA) {
                step2FilenameA.textContent = data.filename_a || 'Base Antiga';
                step2FilenameA.title = data.filename_a || 'Base Antiga';
            }
            if (step2FilenameB) {
                step2FilenameB.textContent = data.filename_b || 'Base Nova';
                step2FilenameB.title = data.filename_b || 'Base Nova';
            }

            // Oculta abas ocultas por padrão ao abrir nova sessão
            step2ShowHiddenA = false;
            step2ShowHiddenB = false;

            renderStep2SheetOptions('a');
            renderStep2SheetOptions('b');

            if (step2HeaderLineA) {
                step2HeaderLineA.value = (state.userHeaderLineA !== null && state.userHeaderLineA !== undefined)
                    ? state.userHeaderLineA
                    : (data.header_line_a || 1);
            }
            if (step2HeaderLineB) {
                step2HeaderLineB.value = (state.userHeaderLineB !== null && state.userHeaderLineB !== undefined)
                    ? state.userHeaderLineB
                    : (data.header_line_b || 1);
            }
        } catch (err) {
            console.error('Erro ao configurar abas no Passo 2:', err);
        }
    }

    function scheduleReloadHeadersStep2(delayMs = 200) {
        if (step2ReloadTimer) {
            clearTimeout(step2ReloadTimer);
        }
        step2ReloadTimer = setTimeout(() => {
            step2ReloadTimer = null;
            reloadHeadersStep2();
        }, delayMs);
    }

    async function reloadHeadersStep2() {
        if (!state.sessionId) return;

        // Se algum arquivo possui múltiplas abas e está temporariamente com 0 marcadas, aguarda o usuário marcar ao menos 1 aba
        if (step2SheetsDataA.length > 1 && getStep2SelectedSheets('a').length === 0) return;
        if (step2SheetsDataB.length > 1 && getStep2SelectedSheets('b').length === 0) return;

        if (isReloadingStep2) {
            pendingReloadStep2 = true;
            return;
        }

        const sheetsA = getStep2SelectedSheets('a');
        const sheetsB = getStep2SelectedSheets('b');
        const headerLineA = step2HeaderLineA ? (parseInt(step2HeaderLineA.value, 10) || 1) : 1;
        const headerLineB = step2HeaderLineB ? (parseInt(step2HeaderLineB.value, 10) || 1) : 1;

        isReloadingStep2 = true;
        pendingReloadStep2 = false;
        if (step2SheetLoading) step2SheetLoading.style.display = 'inline-flex';

        try {
            const resp = await fetch('/api/change-sheet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: state.sessionId,
                    sheets_a: sheetsA,
                    sheets_b: sheetsB,
                    header_line_a: headerLineA,
                    header_line_b: headerLineB
                })
            });

            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.error || 'Erro ao alternar aba ou cabeçalho.');
            }

            // Atualiza aviso proativo de limite de 500 linhas (ex: após concatenação de múltiplas abas)
            const rowsA = Number(data.rows_a_count) || 0;
            const rowsB = Number(data.rows_b_count) || 0;
            const maxRows = Math.max(rowsA, rowsB);
            const userPlan = window.VALIDAI_USER_PLAN || (document.body && document.body.getAttribute('data-user-plan')) || 'standard';
            const paywallNotice = document.getElementById('step1-paywall-notice');
            const paywallCount = document.getElementById('step1-paywall-rows-count');
            if (userPlan === 'standard' && maxRows > 500) {
                if (paywallCount) paywallCount.textContent = maxRows.toLocaleString('pt-BR');
                if (paywallNotice) paywallNotice.style.display = 'flex';
            } else if (paywallNotice) {
                paywallNotice.style.display = 'none';
            }

            // Atualiza colunas e mapeamento no estado
            state.columnsA = data.cols_a || [];
            state.columnsB = data.cols_b || [];
            state.initialMapping = { ...(data.column_mapping || {}) };
            state.mapping = data.column_mapping || {};
            state.selectedSecondaryKeys = [];
            state.isManualMapping = false;

            // Atualiza aviso de colunas Unnamed
            const alertUnnamed = document.getElementById('alert-unnamed-cols');
            if (alertUnnamed) {
                alertUnnamed.style.display = data.has_unnamed ? 'flex' : 'none';
            }

            // Recriar lista de mapeamento
            state.mappingList = Object.entries(state.mapping).map(([colA, colB], idx) => ({
                id: 'map_' + idx + '_' + Math.random().toString(36).substring(2, 7),
                colA: colA,
                colB: colB
            }));

            // Repopular Chave Primária
            if (selectPrimaryKey) {
                selectPrimaryKey.innerHTML = '<option value="">Selecione a chave primária...</option>';
                state.columnsA.forEach(col => {
                    const opt = document.createElement('option');
                    opt.value = col;
                    opt.textContent = col;
                    selectPrimaryKey.appendChild(opt);
                });

                if (data.suggested_keys && data.suggested_keys.length > 0) {
                    const foundKey = data.suggested_keys.find(k => state.columnsA.includes(k));
                    if (foundKey) {
                        selectPrimaryKey.value = foundKey;
                    }
                }

                if (!selectPrimaryKey.value && state.columnsA.length > 0) {
                    const idKeywords = ['CHASSI', 'VIN', 'NOTAFISCAL', 'NUMNF', 'NF', 'NUMERONOTA', 'ID', 'CPF', 'CNPJ', 'MATRICULA', 'CODIGO', 'COD', 'PEDIDO', 'TICKET', 'SERIAL', 'PROTOCOLO'];
                    const lowKeywords = ['MARCA', 'STATUS', 'SITUACAO', 'UF', 'TIPO', 'CATEGORIA', 'ESTADO', 'CIDADE', 'ATIVO', 'SEXO'];
                    const candidate = state.columnsA.find(col => {
                        const clean = col.toUpperCase().replace(/[^A-Z0-9]/g, '');
                        return idKeywords.some(k => clean.includes(k)) && !lowKeywords.some(k => clean.includes(k));
                    });
                    if (candidate) {
                        selectPrimaryKey.value = candidate;
                    }
                }
            }

            // Atualizar Colunas Complementares
            renderSecondaryKeysOptions();
            updateSecondaryKeysUI();

            // Atualizar Tabela de Mapeamento
            renderMappingTable();

        } catch (err) {
            console.error(err);
            alert('Falha ao atualizar colunas das abas selecionadas: ' + err.message);
        } finally {
            isReloadingStep2 = false;
            if (step2SheetLoading) step2SheetLoading.style.display = 'none';
            if (pendingReloadStep2) {
                pendingReloadStep2 = false;
                reloadHeadersStep2();
            }
        }
    }

    function bindStep2MultiselectEvents(suffix) {
        try {
            const isA = (suffix === 'a');
            const trigger = isA ? step2SheetTriggerA : step2SheetTriggerB;
            const dropdown = isA ? step2SheetDropdownA : step2SheetDropdownB;
            const btnSelectAllVis = isA ? step2SelectAllVisA : step2SelectAllVisB;
            const btnDeselectAll = isA ? step2DeselectAllA : step2DeselectAllB;
            const optionsContainer = isA ? step2SheetOptionsA : step2SheetOptionsB;
            const btnToggleHidden = document.getElementById(isA ? 'btn-toggle-hidden-step2-a' : 'btn-toggle-hidden-step2-b');

            if (trigger) {
                trigger.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    toggleStep2Dropdown(suffix);
                });
            }

            if (dropdown) {
                dropdown.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
            }

            if (btnSelectAllVis) {
                btnSelectAllVis.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    try {
                        const sheets = isA ? step2SheetsDataA : step2SheetsDataB;
                        const visList = sheets.filter(s => s.visible !== false);
                        const targetVis = (visList.length > 0 ? visList : sheets).map(s => s.name);
                        const prev = getStep2SelectedSheets(suffix);
                        const merged = [...prev];
                        targetVis.forEach(n => {
                            if (!merged.includes(n)) merged.push(n);
                        });
                        setStep2SelectedSheets(suffix, merged, sheets);

                        if (optionsContainer) {
                            optionsContainer.querySelectorAll('.step2-sheet-option').forEach(lbl => {
                                const inp = lbl.querySelector('input[type="checkbox"]');
                                if (inp && getStep2SelectedSheets(suffix).includes(inp.value)) {
                                    inp.checked = true;
                                    lbl.classList.add('selected');
                                    lbl.setAttribute('aria-selected', 'true');
                                }
                            });
                        }
                        updateStep2TriggerLabel(suffix);
                        const next = getStep2SelectedSheets(suffix);
                        if (next.length > 0 && JSON.stringify(prev) !== JSON.stringify(next)) {
                            scheduleReloadHeadersStep2();
                        }
                    } catch (err) {
                        console.warn('Erro ao marcar todas as abas visíveis:', err);
                    }
                });
            }

            if (btnDeselectAll) {
                btnDeselectAll.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    try {
                        const sheets = isA ? step2SheetsDataA : step2SheetsDataB;
                        setStep2SelectedSheets(suffix, [], sheets);
                        if (optionsContainer) {
                            optionsContainer.querySelectorAll('.step2-sheet-option').forEach(lbl => {
                                const inp = lbl.querySelector('input[type="checkbox"]');
                                if (inp) inp.checked = false;
                                lbl.classList.remove('selected');
                                lbl.setAttribute('aria-selected', 'false');
                            });
                        }
                        updateStep2TriggerLabel(suffix);
                    } catch (err) {
                        console.warn('Erro ao desmarcar abas:', err);
                    }
                });
            }

            if (btnToggleHidden) {
                btnToggleHidden.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    try {
                        if (isA) {
                            step2ShowHiddenA = !step2ShowHiddenA;
                        } else {
                            step2ShowHiddenB = !step2ShowHiddenB;
                        }
                        const nowShowing = isA ? step2ShowHiddenA : step2ShowHiddenB;
                        const sheets = isA ? step2SheetsDataA : step2SheetsDataB;
                        const prev = [...getStep2SelectedSheets(suffix)];

                        // Se ocultou as abas ocultas, remove eventuais abas ocultas da seleção ativa
                        if (!nowShowing && sheets.length > 1) {
                            const hiddenNames = sheets.filter(s => s.visible === false).map(s => s.name);
                            let filtered = prev.filter(n => !hiddenNames.includes(n));
                            if (filtered.length === 0) {
                                const defName = isA ? step2DefaultSheetA : step2DefaultSheetB;
                                filtered = normalizeStep2SheetSelection(defName, sheets);
                            }
                            setStep2SelectedSheets(suffix, filtered, sheets);
                        }

                        renderStep2SheetOptions(suffix);
                        const next = getStep2SelectedSheets(suffix);
                        if (next.length > 0 && JSON.stringify(prev) !== JSON.stringify(next)) {
                            scheduleReloadHeadersStep2();
                        }
                    } catch (err) {
                        console.warn('Erro ao alternar visibilidade de abas ocultas:', err);
                    }
                });
            }
        } catch (err) {
            console.error('Erro ao inicializar eventos do multi-select no Passo 2:', err);
        }
    }

    bindStep2MultiselectEvents('a');
    bindStep2MultiselectEvents('b');

    // Fechar dropdowns do Passo 2 ao clicar fora ou pressionar Escape
    document.addEventListener('click', (e) => {
        try {
            if (step2MultiselectA && !step2MultiselectA.contains(e.target)) {
                closeStep2Dropdown('a');
            }
            if (step2MultiselectB && !step2MultiselectB.contains(e.target)) {
                closeStep2Dropdown('b');
            }
        } catch (err) {
            console.warn('Erro ao processar clique externo do dropdown:', err);
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeAllStep2Dropdowns();
        }
    });

    if (step2HeaderLineA) {
        step2HeaderLineA.addEventListener('input', (e) => {
            const v = parseInt(e.target.value, 10);
            if (!isNaN(v) && v >= 1) {
                state.userHeaderLineA = v;
            }
        });
        step2HeaderLineA.addEventListener('change', () => {
            const v = parseInt(step2HeaderLineA.value, 10);
            if (!isNaN(v) && v >= 1) {
                state.userHeaderLineA = v;
            }
            scheduleReloadHeadersStep2(50);
        });
    }
    if (step2HeaderLineB) {
        step2HeaderLineB.addEventListener('input', (e) => {
            const v = parseInt(e.target.value, 10);
            if (!isNaN(v) && v >= 1) {
                state.userHeaderLineB = v;
            }
        });
        step2HeaderLineB.addEventListener('change', () => {
            const v = parseInt(step2HeaderLineB.value, 10);
            if (!isNaN(v) && v >= 1) {
                state.userHeaderLineB = v;
            }
            scheduleReloadHeadersStep2(50);
        });
    }

    // PASSO 2 -> PASSO 3: RODAR VALIDAÇÃO
    // ----------------------------------------------------
    btnRunCompare.addEventListener('click', async () => {
        if (step2SheetsDataA.length > 1 && getStep2SelectedSheets('a').length === 0) {
            alert('Por favor, selecione ao menos uma aba na Base Antiga para validar.');
            if (step2SheetTriggerA) step2SheetTriggerA.focus();
            return;
        }
        if (step2SheetsDataB.length > 1 && getStep2SelectedSheets('b').length === 0) {
            alert('Por favor, selecione ao menos uma aba na Base Nova para validar.');
            if (step2SheetTriggerB) step2SheetTriggerB.focus();
            return;
        }

        // Assegurar sincronização do mapeamento
        const finalMapping = {};
        state.mappingList.forEach(item => {
            if (item.colA && item.colB) {
                finalMapping[item.colA] = item.colB;
            }
        });
        state.mapping = finalMapping;

        const mappedPairsCount = Object.keys(finalMapping).length;
        if (mappedPairsCount === 0) {
            alert('Por favor, selecione e mapeie ao menos um par de colunas (Base Antiga e Base Nova) na tabela para realizar a validação.');
            return;
        }

        const pk = selectPrimaryKey.value;
        if (!pk) {
            alert('Por favor, selecione uma Chave Identificadora Principal na coluna da esquerda.');
            selectPrimaryKey.focus();
            return;
        }

        const pkB = state.mapping[pk] || pk;

        closeAllStep2Dropdowns();
        startBtnStepperLoading(btnRunCompare, 'Rodar Validação Completa');

        const payload = {
            session_id: state.sessionId,
            primary_key_a: pk,
            primary_key_b: pkB,
            secondary_keys_a: state.selectedSecondaryKeys,
            normalize_currency: normCurrency.checked,
            normalize_dates: normDates.checked,
            ignore_case: normCase.checked,
            trim_spaces: normTrim.checked,
            column_mapping: state.mapping,
            header_line_a: (step2HeaderLineA && step2HeaderLineA.value) ? (parseInt(step2HeaderLineA.value, 10) || 1) : (state.userHeaderLineA || 1),
            header_line_b: (step2HeaderLineB && step2HeaderLineB.value) ? (parseInt(step2HeaderLineB.value, 10) || 1) : (state.userHeaderLineB || 1),
            sheets_a: getStep2SelectedSheets('a'),
            sheets_b: getStep2SelectedSheets('b')
        };

        try {
            const response = await fetch('/api/compare', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                alert(data.error || 'Erro durante a validação.');
                stopBtnStepperLoading(btnRunCompare, 'Rodar Validação Completa');
                return;
            }

            state.reportId = data.report_id;
            state.diffRecords = data.diff_preview || [];
            state.onlyInAPreview = data.only_in_a_preview || [];
            state.onlyInBPreview = data.only_in_b_preview || [];
            state.colsDisplayA = data.cols_display_a || [];
            state.colsDisplayB = data.cols_display_b || [];
            
            // Exibir Resultados
            renderResults(data);

            stepResults.style.display = 'block';
            stepResults.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (err) {
            console.error(err);
            alert('Erro ao executar a validação: ' + err.message);
        } finally {
            stopBtnStepperLoading(btnRunCompare, 'Rodar Validação Completa');
        }
    });

    // ----------------------------------------------------
    // PASSO 3: RENDERIZAR RESULTADOS
    // ----------------------------------------------------
    function renderResults(data) {
        state.lastCompareData = data;
        const s = data.summary;
        const lang = (window.ValidAiI18n && window.ValidAiI18n.getCurrentLanguage) ? window.ValidAiI18n.getCurrentLanguage() : 'pt';
        const numLocale = lang === 'en' ? 'en-US' : (lang === 'es' ? 'es-ES' : 'pt-BR');
        const rowsLabel = lang === 'en' ? 'rows in A' : (lang === 'es' ? 'filas en A' : 'linhas em A');
        const ofLabel = lang === 'en' ? 'of' : (lang === 'es' ? 'de' : 'de');
        const colsLabel = lang === 'en' ? 'columns' : (lang === 'es' ? 'columnas' : 'colunas');
        const ofTotal = lang === 'en' ? 'of total' : (lang === 'es' ? 'del total' : 'do total');

        // Atualizar KPIs
        kpiRowsMatched.textContent = s.matched_keys_count.toLocaleString(numLocale);
        kpiRowsTotal.textContent = `${ofLabel} ${s.total_rows_a.toLocaleString(numLocale)} ${rowsLabel}`;

        kpiRowsDiff.textContent = s.different_rows_count.toLocaleString(numLocale);
        const pctDiff = s.matched_keys_count > 0 ? ((s.different_rows_count / s.matched_keys_count) * 100).toFixed(1) : 0;
        kpiPctDiff.textContent = `${pctDiff}% ${ofTotal}`;

        kpiCellsDiff.textContent = s.total_cells_diff.toLocaleString(numLocale);
        kpiColsDiff.textContent = s.columns_with_differences_count.toLocaleString(numLocale);
        kpiColsTotal.textContent = `${ofLabel} ${s.total_columns_compared} ${colsLabel}`;

        if (kpiRowsOnlyA) kpiRowsOnlyA.textContent = (s.only_in_a_count || 0).toLocaleString(numLocale);
        if (kpiRowsOnlyB) kpiRowsOnlyB.textContent = (s.only_in_b_count || 0).toLocaleString(numLocale);

        // Card de Destaque Executivo: Tempo Estimado Economizado (Passo 3)
        const timeSavedCard = document.getElementById('step3-time-saved-card');
        const timeSavedVal = document.getElementById('step3-time-saved-val');
        if (timeSavedCard && timeSavedVal) {
            try {
                const rowsCompared = Number(s.matched_keys_count || s.total_rows_a || 0);
                const colsCompared = Number(s.total_columns_compared || (state.columnsA ? state.columnsA.length : 0) || 1);
                const totalCells = rowsCompared * colsCompared;
                const savedMinutes = Math.max(15, Math.round(totalCells / 20));

                let timeDisplay = '';
                if (savedMinutes < 60) {
                    timeDisplay = `~${savedMinutes} minutos`;
                } else {
                    const hours = Math.floor(savedMinutes / 60);
                    const mins = savedMinutes % 60;
                    timeDisplay = mins > 0 ? `~${hours}h ${mins < 10 ? '0' : ''}${mins}min` : `~${hours}h`;
                }

                timeSavedVal.textContent = timeDisplay;
                timeSavedCard.style.display = 'flex';
            } catch (tErr) {
                console.warn('Erro ao calcular tempo economizado:', tErr);
                timeSavedCard.style.display = 'none';
            }
        }

        if (s.is_identical) {
            // Sucesso Total
            bannerIdentical.style.display = 'flex';
            bannerDiffs.style.display = 'none';
            diffColsSection.style.display = 'none';
            diffTableSection.style.display = 'none';
            if (resultNavTabs) resultNavTabs.style.display = 'none';
            if (onlyATableSection) onlyATableSection.style.display = 'none';
            if (onlyBTableSection) onlyBTableSection.style.display = 'none';
            if (financialTableSection) financialTableSection.style.display = 'none';
            btnDownloadExcel.classList.remove('btn-excel');
            btnDownloadExcel.classList.add('btn-success');
        } else {
            // Divergências ou Chaves Exclusivas
            bannerIdentical.style.display = 'none';
            bannerDiffs.style.display = 'flex';
            btnDownloadExcel.classList.add('btn-excel');

            const bannerTitle = bannerDiffs.querySelector('h3');
            const bannerDesc = bannerDiffs.querySelector('p');

            if (s.matched_keys_count === 0 && ((s.only_in_a_count || 0) > 0 || (s.only_in_b_count || 0) > 0)) {
                if (bannerTitle) bannerTitle.textContent = lang === 'en'
                    ? 'Notice: No matching rows found between the two spreadsheets!'
                    : (lang === 'es' ? '¡Atención: Ninguna fila coincidió entre ambas hojas de cálculo!' : 'Atenção: Nenhuma linha coincidiu entre as duas planilhas!');
                if (bannerDesc) {
                    if (lang === 'en') {
                        bannerDesc.innerHTML = `With the selected identifiers, no records from the Old Sheet were matched in the New Sheet. All records are exclusive to each file (<strong>${(s.only_in_a_count || 0).toLocaleString(numLocale)}</strong> in Old Sheet only and <strong>${(s.only_in_b_count || 0).toLocaleString(numLocale)}</strong> in New Sheet only). Check the detailed tabs below or verify your identifier keys.`;
                    } else if (lang === 'es') {
                        bannerDesc.innerHTML = `Con los identificadores seleccionados, no se encontraron registros de la Base Antigua en la Base Nueva. Todos los registros son exclusivos de cada archivo (<strong>${(s.only_in_a_count || 0).toLocaleString(numLocale)}</strong> solo en Base Antigua y <strong>${(s.only_in_b_count || 0).toLocaleString(numLocale)}</strong> solo en Base Nueva). Vea las pestañas abajo o revise los identificadores elegidos.`;
                    } else {
                        bannerDesc.innerHTML = `Com os identificadores selecionados, nenhum registro da Base Antiga foi encontrado na Base Nova. Todos os registros são exclusivos de cada arquivo (<strong>${(s.only_in_a_count || 0).toLocaleString('pt-BR')}</strong> apenas na Base Antiga e <strong>${(s.only_in_b_count || 0).toLocaleString('pt-BR')}</strong> apenas na Base Nova). Veja os dados completos nas abas <strong>"Apenas na Base Antiga"</strong> e <strong>"Apenas na Base Nova"</strong> abaixo ou verifique os identificadores escolhidos.`;
                    }
                }
            } else {
                if (bannerTitle) bannerTitle.textContent = lang === 'en'
                    ? 'Notice: Discrepancies were found between the spreadsheets!'
                    : (lang === 'es' ? '¡Atención: Se encontraron discrepancias entre las hojas de cálculo!' : 'Atenção: Foram encontradas divergências entre as planilhas!');
                if (bannerDesc) {
                    bannerDesc.textContent = lang === 'en'
                        ? 'Review the discrepancy summary below or download the full Excel report with highlighted cells.'
                        : (lang === 'es' ? 'Consulte el resumen de discrepancias abajo o descargue la hoja Excel completa con las celdas resaltadas.' : 'Confira o resumo das divergências abaixo ou baixe a planilha Excel completa com as células pintadas.');
                }
            }

            // Renderizar Tags de Colunas Divergentes
            diffTagsContainer.innerHTML = '';
            if (data.columns_with_differences && Object.keys(data.columns_with_differences).length > 0) {
                diffColsSection.style.display = 'block';
                for (const [col, count] of Object.entries(data.columns_with_differences)) {
                    const tag = document.createElement('span');
                    tag.className = 'diff-tag';
                    tag.textContent = `${col} (${count.toLocaleString('pt-BR')} linhas)`;
                    diffTagsContainer.appendChild(tag);
                }
            } else {
                diffColsSection.style.display = 'none';
            }

            // Preparar dados para a tabela de diferenças
            flattenDiffRows(data.diff_preview);
            renderDiffTable(state.allDiffRows);

            // Renderizar tabelas de registros exclusivos
            renderOnlyTable(onlyATableHead, onlyATableBody, state.colsDisplayA, state.onlyInAPreview);
            renderOnlyTable(onlyBTableHead, onlyBTableBody, state.colsDisplayB, state.onlyInBPreview);

            // Configurar Abas e Sumarização Financeira
            const fin = s.financial_summary;
            const hasFinancial = fin && fin.items && fin.items.length > 0;
            const hasDiffs = s.different_rows_count > 0;
            const hasOnlyA = (s.only_in_a_count || 0) > 0;
            const hasOnlyB = (s.only_in_b_count || 0) > 0;

            if (resultNavTabs) {
                resultNavTabs.style.display = 'flex';
                if (badgeDiffCount) badgeDiffCount.textContent = s.different_rows_count.toLocaleString('pt-BR');
                if (badgeOnlyACount) badgeOnlyACount.textContent = (s.only_in_a_count || 0).toLocaleString('pt-BR');
                if (badgeOnlyBCount) badgeOnlyBCount.textContent = (s.only_in_b_count || 0).toLocaleString('pt-BR');

                if (tabBtnDiffs) tabBtnDiffs.style.display = hasDiffs || s.matched_keys_count > 0 ? 'inline-flex' : 'none';
                if (tabBtnOnlyA) tabBtnOnlyA.style.display = hasOnlyA ? 'inline-flex' : 'none';
                if (tabBtnOnlyB) tabBtnOnlyB.style.display = hasOnlyB ? 'inline-flex' : 'none';

                if (tabBtnFinancial) {
                    if (hasFinancial) {
                        tabBtnFinancial.style.display = 'inline-flex';
                        if (badgeFinCount) badgeFinCount.textContent = fin.items.length;
                        renderFinancialTable(fin);
                    } else {
                        tabBtnFinancial.style.display = 'none';
                    }
                }

                // Escolhe a aba ativa inicial mais relevante
                if (hasDiffs) {
                    switchResultTab('diffs');
                } else if (hasOnlyA) {
                    switchResultTab('only-a');
                } else if (hasOnlyB) {
                    switchResultTab('only-b');
                } else if (hasFinancial) {
                    switchResultTab('financial');
                } else {
                    switchResultTab('diffs');
                }
            }
        }

        // Renderizar Gráficos Analíticos do Passo 3 (Donut e Top Colunas)
        renderChartsStep3(data);
    }
    // ----------------------------------------------------
    // GRÁFICOS ANALÍTICOS DO PASSO 3 (CHART.JS)
    // ----------------------------------------------------
    let chartRecordsProportionInstance = null;
    let chartDiffColsInstance = null;

    function renderChartsStep3(data) {
        const chartsWrapper = document.getElementById('step3-charts-wrapper');
        const chartsContainer = document.getElementById('step3-charts-container');
        if (!chartsContainer) return;

        try {
            if (typeof Chart === 'undefined') {
                console.warn('Chart.js não carregado. Exibição dos gráficos ignorada com segurança.');
                if (chartsWrapper) chartsWrapper.style.display = 'none';
                chartsContainer.style.display = 'none';
                return;
            }

            if (chartsWrapper) chartsWrapper.style.display = 'block';
            chartsContainer.style.display = 'grid';
            renderDonutChart(data);
            renderBarChart(data);
        } catch (err) {
            console.error('Erro seguro na renderização dos gráficos do Passo 3:', err);
        }
    }

    function renderDonutChart(data) {
        const canvas = document.getElementById('chart-records-proportion');
        if (!canvas) return;

        try {
            if (chartRecordsProportionInstance) {
                chartRecordsProportionInstance.destroy();
                chartRecordsProportionInstance = null;
            }

            const s = data.summary || {};
            const matchedCount = s.matched_keys_count || 0;
            const diffCount = s.different_rows_count || 0;
            const identicalCount = Math.max(0, matchedCount - diffCount);
            const exclusiveCount = (s.only_in_a_count || 0) + (s.only_in_b_count || 0);

            const lang = (window.ValidAiI18n && window.ValidAiI18n.getCurrentLanguage) ? window.ValidAiI18n.getCurrentLanguage() : 'pt';
            const numLocale = lang === 'en' ? 'en-US' : (lang === 'es' ? 'es-ES' : 'pt-BR');
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
                           document.documentElement.classList.contains('dark-theme') ||
                           (document.body && document.body.classList.contains('dark-theme')) ||
                           (localStorage.getItem('splitc_theme') === 'dark');

            const labelIdentical = lang === 'en' ? '100% Identical' : (lang === 'es' ? '100% Idénticas' : '100% Iguais');
            const labelDiff = lang === 'en' ? 'With Differences' : (lang === 'es' ? 'Con Diferencias' : 'Com Diferenças');
            const labelExclusive = lang === 'en' ? 'Exclusive' : (lang === 'es' ? 'Exclusivas' : 'Exclusivas');

            const totalRecords = identicalCount + diffCount + exclusiveCount;
            const chartData = totalRecords > 0 
                ? [identicalCount, diffCount, exclusiveCount] 
                : [1, 0, 0];

            chartRecordsProportionInstance = new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: [labelIdentical, labelDiff, labelExclusive],
                    datasets: [{
                        data: chartData,
                        backgroundColor: ['#10b981', '#ef4444', '#f59e0b'],
                        hoverBackgroundColor: ['#059669', '#dc2626', '#d97706'],
                        borderWidth: 2,
                        borderColor: isDark ? '#17181f' : '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '66%',
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                padding: 10,
                                color: isDark ? '#cbd5e1' : '#475569',
                                font: { size: 11, family: 'Inter, sans-serif', weight: '500' }
                            }
                        },
                        tooltip: {
                            backgroundColor: isDark ? '#1e293b' : '#0f172a',
                            titleColor: '#ffffff',
                            bodyColor: '#ffffff',
                            padding: 9,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(context) {
                                    if (totalRecords === 0) return ` 0 registros`;
                                    const val = context.parsed || 0;
                                    const pct = totalRecords > 0 ? ((val / totalRecords) * 100).toFixed(1) : '0.0';
                                    return ` ${context.label}: ${val.toLocaleString(numLocale)} (${pct}%)`;
                                }
                            }
                        }
                    }
                }
            });
        } catch (e) {
            console.error('Falha segura no gráfico Donut:', e);
        }
    }

    function renderBarChart(data) {
        const canvas = document.getElementById('chart-diff-cols');
        const emptyEl = document.getElementById('chart-diff-cols-empty');
        if (!canvas) return;

        try {
            if (chartDiffColsInstance) {
                chartDiffColsInstance.destroy();
                chartDiffColsInstance = null;
            }

            const diffMap = data.columns_with_differences || (data.summary && data.summary.columns_with_differences) || {};
            const sortedCols = Object.entries(diffMap).sort((a, b) => b[1] - a[1]).slice(0, 5);

            if (sortedCols.length === 0) {
                canvas.style.display = 'none';
                if (emptyEl) emptyEl.style.display = 'flex';
                return;
            }

            canvas.style.display = 'block';
            if (emptyEl) emptyEl.style.display = 'none';

            const lang = (window.ValidAiI18n && window.ValidAiI18n.getCurrentLanguage) ? window.ValidAiI18n.getCurrentLanguage() : 'pt';
            const numLocale = lang === 'en' ? 'en-US' : (lang === 'es' ? 'es-ES' : 'pt-BR');
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
                           document.documentElement.classList.contains('dark-theme') ||
                           (document.body && document.body.classList.contains('dark-theme')) ||
                           (localStorage.getItem('splitc_theme') === 'dark');

            const datasetLabel = lang === 'en' ? 'Discrepancies' : (lang === 'es' ? 'Discrepancias' : 'Divergências');

            chartDiffColsInstance = new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: sortedCols.map(c => c[0]),
                    datasets: [{
                        label: datasetLabel,
                        data: sortedCols.map(c => c[1]),
                        backgroundColor: 'rgba(239, 68, 68, 0.85)',
                        hoverBackgroundColor: '#dc2626',
                        borderRadius: 4,
                        barThickness: 16,
                        maxBarThickness: 20
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    layout: {
                        padding: {
                            left: 15,
                            right: 15
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: isDark ? '#1e293b' : '#0f172a',
                            titleColor: '#ffffff',
                            bodyColor: '#ffffff',
                            padding: 9,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(context) {
                                    const val = context.parsed.x || 0;
                                    const errLabel = lang === 'en' ? 'divergent rows' : (lang === 'es' ? 'filas con error' : 'linhas com divergência');
                                    return ` ${val.toLocaleString(numLocale)} ${errLabel}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            grid: {
                                color: isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)',
                                drawBorder: false
                            },
                            ticks: {
                                precision: 0,
                                color: isDark ? '#94a3b8' : '#64748b',
                                font: { size: 10, family: 'Inter, sans-serif' }
                            }
                        },
                        y: {
                            grid: { display: false, drawBorder: false },
                            ticks: {
                                autoSkip: false,
                                color: isDark ? '#e2e8f0' : '#1e293b',
                                font: { size: 12, family: 'JetBrains Mono, monospace', weight: '600' }
                            }
                        }
                    }
                }
            });
        } catch (e) {
            console.error('Falha segura no gráfico de Barras:', e);
        }
    }

    // Exportação do Painel Analítico em Imagem PNG (Client-side / 0 MB no Servidor)
    function exportChartsDashboardToPng({ title, filename, chart1, chart2, empty2Text }) {
        try {
            if (!chart1 && !chart2) return;

            const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
                           document.documentElement.classList.contains('dark-theme') ||
                           (document.body && document.body.classList.contains('dark-theme')) ||
                           (localStorage.getItem('splitc_theme') === 'dark');

            const bgPage = isDark ? '#0f1117' : '#f8fafc';
            const bgCard = isDark ? '#17181f' : '#ffffff';
            const borderCard = isDark ? '#272a36' : '#e2e8f0';
            const textTitle = isDark ? '#f1f5f9' : '#0f172a';
            const textMuted = isDark ? '#94a3b8' : '#64748b';
            const accentGreen = '#10b981';

            const cardPad = 24;
            const cardGap = 20;
            const topHeaderH = 70;
            const cardW = 540;
            const cardH = 280;
            const totalW = cardPad * 2 + cardW * 2 + cardGap;
            const totalH = cardPad * 2 + topHeaderH + cardH;

            const scale = 2; // Alta resolução (retina 2x)
            const outCanvas = document.createElement('canvas');
            outCanvas.width = totalW * scale;
            outCanvas.height = totalH * scale;
            const ctx = outCanvas.getContext('2d');
            ctx.scale(scale, scale);

            // Fundo
            ctx.fillStyle = bgPage;
            ctx.fillRect(0, 0, totalW, totalH);

            // Cabeçalho da Imagem
            ctx.fillStyle = accentGreen;
            ctx.font = 'bold 20px Inter, system-ui, sans-serif';
            ctx.fillText('ValidAí', cardPad, cardPad + 24);

            ctx.fillStyle = textTitle;
            ctx.font = '600 15px Inter, system-ui, sans-serif';
            ctx.fillText('•  ' + (title || 'Painel Analítico'), cardPad + 82, cardPad + 24);

            ctx.fillStyle = textMuted;
            ctx.font = '12px Inter, system-ui, sans-serif';
            const dateStr = new Date().toLocaleString('pt-BR');
            ctx.fillText('Gerado via ValidAí em ' + dateStr, cardPad, cardPad + 48);

            function roundRect(ctx, x, y, width, height, radius, fill, stroke) {
                ctx.beginPath();
                ctx.moveTo(x + radius, y);
                ctx.lineTo(x + width - radius, y);
                ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
                ctx.lineTo(x + width, y + height - radius);
                ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
                ctx.lineTo(x + radius, y + height);
                ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
                ctx.lineTo(x, y + radius);
                ctx.quadraticCurveTo(x, y, x + radius, y);
                ctx.closePath();
                if (fill) { ctx.fillStyle = fill; ctx.fill(); }
                if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
            }

            // Card 1
            const yCards = cardPad + topHeaderH;
            const x1 = cardPad;
            roundRect(ctx, x1, yCards, cardW, cardH, 10, bgCard, borderCard);

            if (chart1 && chart1.canvas) {
                const c1 = chart1.canvas;
                const innerPad = 14;
                ctx.drawImage(c1, x1 + innerPad, yCards + innerPad, cardW - innerPad * 2, cardH - innerPad * 2);
            }

            // Card 2
            const x2 = cardPad + cardW + cardGap;
            roundRect(ctx, x2, yCards, cardW, cardH, 10, bgCard, borderCard);

            if (chart2 && chart2.canvas && chart2.canvas.style.display !== 'none') {
                const c2 = chart2.canvas;
                const innerPad = 14;
                ctx.drawImage(c2, x2 + innerPad, yCards + innerPad, cardW - innerPad * 2, cardH - innerPad * 2);
            } else {
                ctx.fillStyle = accentGreen;
                ctx.font = 'bold 22px Inter, system-ui, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('✓', x2 + cardW / 2, yCards + cardH / 2 - 10);
                ctx.fillStyle = textMuted;
                ctx.font = '13px Inter, system-ui, sans-serif';
                ctx.fillText(empty2Text || 'Nenhuma divergência encontrada', x2 + cardW / 2, yCards + cardH / 2 + 18);
                ctx.textAlign = 'left';
            }

            // Dispara download
            const link = document.createElement('a');
            link.download = filename || 'Relatorio_ValidAi_Graficos.png';
            link.href = outCanvas.toDataURL('image/png');
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (e) {
            console.error('Erro seguro na exportação do painel PNG:', e);
        }
    }

    const btnExportSheets = document.getElementById('btn-export-charts-sheets');
    if (btnExportSheets) {
        btnExportSheets.addEventListener('click', () => {
            exportChartsDashboardToPng({
                title: 'Validador de Planilhas • Proporção & Colunas Divergentes',
                filename: 'Relatorio_ValidAi_Graficos.png',
                chart1: chartRecordsProportionInstance,
                chart2: chartDiffColsInstance,
                empty2Text: '100% de conformidade nas colunas analisadas'
            });
        });
    }

    // Re-renderizar gráficos ao alternar tema (claro/escuro)
    document.addEventListener('click', (e) => {
        if (e.target && (e.target.closest('#theme-toggle-btn') || (e.target.classList && e.target.classList.contains('theme-toggle-btn')))) {
            if (state.lastCompareData && stepResults && stepResults.style.display !== 'none') {
                setTimeout(() => {
                    renderChartsStep3(state.lastCompareData);
                }, 120);
            }
        }
    });


    function flattenDiffRows(diffPreview) {
        state.allDiffRows = [];
        diffPreview.forEach(rec => {
            const keyStr = rec.secondary_key_val 
                ? `${rec.primary_key_val} [${rec.secondary_key_val}]` 
                : rec.primary_key_val;

            const lineVal = rec.line_display || rec.row_num_a || '-';

            for (const [colA, cDiff] of Object.entries(rec.cell_diffs)) {
                state.allDiffRows.push({
                    key: keyStr,
                    line: lineVal,
                    col: colA,
                    valA: cDiff.val_a_raw,
                    valB: cDiff.val_b_raw
                });
            }
        });
    }

    function renderDiffTable(rows) {
        diffTableBody.innerHTML = '';
        if (rows.length === 0) {
            diffTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #64748b; padding: 24px;">Nenhum registro encontrado para este filtro.</td></tr>`;
            return;
        }

        const maxDisplay = 200;
        const displayRows = rows.slice(0, maxDisplay);

        displayRows.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span class="key-code">${escapeHtml(item.key)}</span></td>
                <td style="text-align: center;"><span class="badge-line">${escapeHtml(String(item.line))}</span></td>
                <td><strong>${escapeHtml(item.col)}</strong></td>
                <td><span class="cell-diff-old">${escapeHtml(item.valA || '(Vazio)')}</span></td>
                <td class="diff-arrow">➔</td>
                <td><span class="cell-diff-new">${escapeHtml(item.valB || '(Vazio)')}</span></td>
            `;
            diffTableBody.appendChild(tr);
        });
    }

    // Busca rápida na tabela de diferenças
    diffSearch.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        if (!query) {
            renderDiffTable(state.allDiffRows);
            return;
        }

        const filtered = state.allDiffRows.filter(r => 
            r.key.toLowerCase().includes(query) ||
            String(r.line).toLowerCase().includes(query) ||
            r.col.toLowerCase().includes(query) ||
            String(r.valA).toLowerCase().includes(query) ||
            String(r.valB).toLowerCase().includes(query)
        );

        renderDiffTable(filtered);
    });

    // ----------------------------------------------------
    // SUMARIZAÇÃO FINANCEIRA E ALTERNÂNCIA DE ABAS
    // ----------------------------------------------------
    function formatMoneyBR(val) {
        if (val === null || val === undefined || isNaN(val)) return 'R$ 0,00';
        return Number(val).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function renderFinancialTable(fin) {
        if (!financialTableBody || !fin || !fin.items) return;

        financialTableBody.innerHTML = '';
        fin.items.forEach(item => {
            const tr = document.createElement('tr');
            const isOk = item.status === 'OK';
            const diffClass = isOk ? 'text-success font-bold' : 'text-danger font-bold';
            const statusBadge = isOk 
                ? '<span class="status-badge-ok">OK / Conciliado</span>' 
                : '<span class="status-badge-diff">Divergente</span>';
            const pctText = (item.pct_diff > 0 ? '+' : '') + item.pct_diff.toFixed(2) + '%';

            tr.innerHTML = `
                <td><strong>${escapeHtml(item.col_a)}</strong></td>
                <td><strong>${escapeHtml(item.col_b)}</strong></td>
                <td style="text-align: right; font-family: monospace;">${formatMoneyBR(item.sum_a)}</td>
                <td style="text-align: right; font-family: monospace;">${formatMoneyBR(item.sum_b)}</td>
                <td style="text-align: right; font-family: monospace;" class="${diffClass}">${formatMoneyBR(item.diff)}</td>
                <td style="text-align: center;"><span class="badge-pct ${item.pct_diff !== 0 ? 'pct-alert' : ''}">${pctText}</span></td>
                <td style="text-align: center;">${statusBadge}</td>
                <td style="text-align: center;"><span class="badge-line">${item.diff_count}</span></td>
            `;
            financialTableBody.appendChild(tr);
        });

        if (financialTableFooter) {
            const totalOk = fin.divergent_pairs_count === 0;
            const diffClass = totalOk ? 'text-success font-bold' : 'text-danger font-bold';
            const totalPct = (fin.total_pct_diff > 0 ? '+' : '') + fin.total_pct_diff.toFixed(2) + '%';
            financialTableFooter.innerHTML = `
                <tr class="tfoot-total-row">
                    <td colspan="2"><strong>TOTAL GERAL CONSOLIDADO</strong></td>
                    <td style="text-align: right; font-family: monospace; font-weight: bold;">${formatMoneyBR(fin.total_sum_a)}</td>
                    <td style="text-align: right; font-family: monospace; font-weight: bold;">${formatMoneyBR(fin.total_sum_b)}</td>
                    <td style="text-align: right; font-family: monospace; font-weight: bold;" class="${diffClass}">${formatMoneyBR(fin.total_diff)}</td>
                    <td style="text-align: center; font-weight: bold;">${totalPct}</td>
                    <td style="text-align: center;"><strong>${totalOk ? '100% CONCILIADO' : fin.divergent_pairs_count + ' PAR(ES) COM ERRO'}</strong></td>
                    <td style="text-align: center;">-</td>
                </tr>
            `;
        }
    }

    function switchResultTab(tabName) {
        [tabBtnDiffs, tabBtnOnlyA, tabBtnOnlyB, tabBtnFinancial].forEach(btn => {
            if (btn) btn.classList.remove('active');
        });
        if (diffTableSection) diffTableSection.style.display = 'none';
        if (onlyATableSection) onlyATableSection.style.display = 'none';
        if (onlyBTableSection) onlyBTableSection.style.display = 'none';
        if (financialTableSection) financialTableSection.style.display = 'none';

        if (tabName === 'diffs') {
            if (tabBtnDiffs) tabBtnDiffs.classList.add('active');
            if (diffTableSection) diffTableSection.style.display = 'block';
        } else if (tabName === 'only-a') {
            if (tabBtnOnlyA) tabBtnOnlyA.classList.add('active');
            if (onlyATableSection) onlyATableSection.style.display = 'block';
        } else if (tabName === 'only-b') {
            if (tabBtnOnlyB) tabBtnOnlyB.classList.add('active');
            if (onlyBTableSection) onlyBTableSection.style.display = 'block';
        } else if (tabName === 'financial') {
            if (tabBtnFinancial) tabBtnFinancial.classList.add('active');
            if (financialTableSection) financialTableSection.style.display = 'block';
        }
    }

    function renderOnlyTable(thead, tbody, cols, rows, filterText = '') {
        if (!thead || !tbody) return;
        thead.innerHTML = '';
        tbody.innerHTML = '';

        if (!cols || cols.length === 0) return;

        // Cabeçalhos (Linha, Chave, + colunas)
        const trHead = document.createElement('tr');
        trHead.innerHTML = `
            <th style="text-align: center; width: 80px;">Linha</th>
            <th style="min-width: 200px;">Chave Identificadora</th>
        ` + cols.map(c => `<th>${escapeHtml(c)}</th>`).join('');
        thead.appendChild(trHead);

        const normFilter = normalizeSearch(filterText);
        const filtered = normFilter 
            ? rows.filter(r => 
                normalizeSearch(r.key).includes(normFilter) ||
                String(r.line).includes(normFilter) ||
                Object.values(r.values || {}).some(v => normalizeSearch(v).includes(normFilter))
              )
            : rows;

        if (filtered.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td colspan="${cols.length + 2}" style="text-align: center; color: #64748b; padding: 24px;">Nenhum registro encontrado.</td>`;
            tbody.appendChild(tr);
            return;
        }

        const maxDisplay = 200;
        const displayRows = filtered.slice(0, maxDisplay);

        displayRows.forEach(item => {
            const tr = document.createElement('tr');
            const lineVal = item.line !== null ? item.line : '-';
            const cellsHtml = cols.map(c => {
                const val = (item.values && item.values[c]) || '';
                return `<td>${escapeHtml(val)}</td>`;
            }).join('');

            tr.innerHTML = `
                <td style="text-align: center;"><span class="badge-line">${escapeHtml(String(lineVal))}</span></td>
                <td><span class="key-code">${escapeHtml(item.key)}</span></td>
                ${cellsHtml}
            `;
            tbody.appendChild(tr);
        });
    }

    if (tabBtnDiffs) tabBtnDiffs.addEventListener('click', () => switchResultTab('diffs'));
    if (tabBtnOnlyA) tabBtnOnlyA.addEventListener('click', () => switchResultTab('only-a'));
    if (tabBtnOnlyB) tabBtnOnlyB.addEventListener('click', () => switchResultTab('only-b'));
    if (tabBtnFinancial) tabBtnFinancial.addEventListener('click', () => switchResultTab('financial'));

    if (onlyASearch) {
        onlyASearch.addEventListener('input', (e) => {
            renderOnlyTable(onlyATableHead, onlyATableBody, state.colsDisplayA, state.onlyInAPreview, e.target.value);
        });
    }

    if (onlyBSearch) {
        onlyBSearch.addEventListener('input', (e) => {
            renderOnlyTable(onlyBTableHead, onlyBTableBody, state.colsDisplayB, state.onlyInBPreview, e.target.value);
        });
    }

    // ----------------------------------------------------
    // DOWNLOAD DO RELATÓRIO EXCEL
    // ----------------------------------------------------
    btnDownloadExcel.addEventListener('click', () => {
        if (!state.reportId) {
            alert('Nenhum relatório disponível para download.');
            return;
        }
        window.location.href = `/api/download-report/${state.reportId}`;
    });

    // ----------------------------------------------------
    // REINICIAR VALIDAÇÃO
    // ----------------------------------------------------
    btnRestart.addEventListener('click', () => {
        window.location.reload();
    });

    // ========================================================
    // CONTROLADOR DO TOGGLE SWITCH DE MODO (DUAL VS SINGLE)
    // ========================================================
    const modeDualContainer = document.getElementById('mode-dual-container');
    const modeSingleContainer = document.getElementById('mode-single-container');
    const allModeBtns = document.querySelectorAll('.mode-btn');

    function setAppMode(targetMode) {
        if (targetMode === 'single') {
            if (modeDualContainer) modeDualContainer.style.display = 'none';
            if (modeSingleContainer) modeSingleContainer.style.display = 'block';
            allModeBtns.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.mode === 'single');
            });
            localStorage.setItem('splitc_validador_mode', 'single');
        } else {
            if (modeDualContainer) modeDualContainer.style.display = 'block';
            if (modeSingleContainer) modeSingleContainer.style.display = 'none';
            allModeBtns.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.mode === 'dual');
            });
            localStorage.setItem('splitc_validador_mode', 'dual');
        }
    }

    allModeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.dataset.mode;
            setAppMode(mode);
        });
    });

    // Se o usuário já tinha selecionado modo single antes, restaura
    const savedMode = localStorage.getItem('splitc_validador_mode');
    if (savedMode === 'single') {
        setAppMode('single');
    }

    // ========================================================
    // MÓDULO DE VALIDAÇÃO / AUDITORIA DE ARQUIVO ÚNICO
    // ========================================================
    const singleDropzone = document.getElementById('single-dropzone');
    const singleFileInput = document.getElementById('single-file-input');
    const singleFileMeta = document.getElementById('single-file-meta');
    const singleFilename = document.getElementById('single-filename');
    const singleFilesize = document.getElementById('single-filesize');
    const btnSingleReadFile = document.getElementById('btn-single-read-file');

    const singleStepUpload = document.getElementById('single-step-upload');
    const singleStepConfig = document.getElementById('single-step-config');
    const singleStepResults = document.getElementById('single-step-results');

    const singleInfoName = document.getElementById('single-info-name');
    const singleInfoRows = document.getElementById('single-info-rows');
    const singleInfoCols = document.getElementById('single-info-cols');
    const btnSingleChangeFile = document.getElementById('btn-single-change-file');

    const singleRuleCol = document.getElementById('single-rule-col');
    const singleRuleType = document.getElementById('single-rule-type');
    const singleParamContainer = document.getElementById('single-param-container');
    const singleParamLabel = document.getElementById('single-param-label');
    const singleParamHelp = document.getElementById('single-param-help');

    const paramCompareCols = document.getElementById('param-compare-cols');
    const singleRuleOp = document.getElementById('single-rule-op');
    const singleRuleTargetCol = document.getElementById('single-rule-target-col');

    const paramThreshold = document.getElementById('param-threshold');
    const singleRuleThreshold = document.getElementById('single-rule-threshold');

    const paramCount = document.getElementById('param-count');
    const singleRuleCount = document.getElementById('single-rule-count');

    const paramLength = document.getElementById('param-length');
    const singleRuleLenOp = document.getElementById('single-rule-len-op');
    const singleRuleLenVal = document.getElementById('single-rule-len-val');

    const btnSingleAddRule = document.getElementById('btn-single-add-rule');
    const singleRulesContainer = document.getElementById('single-rules-container');
    const singleEmptyRulesMsg = document.getElementById('single-empty-rules-msg');
    const singleRulesCountBadge = document.getElementById('single-rules-count-badge');
    const btnSingleClearRules = document.getElementById('btn-single-clear-rules');
    const btnSingleRunAudit = document.getElementById('btn-single-run-audit');

    const presetIdDuplicates = document.getElementById('preset-id-duplicates');
    const presetAllNotEmpty = document.getElementById('preset-all-not-empty');

    const singleAlertBanner = document.getElementById('single-alert-banner');
    const singleAlertIcon = document.getElementById('single-alert-icon');
    const singleAlertTitle = document.getElementById('single-alert-title');
    const singleAlertDesc = document.getElementById('single-alert-desc');
    const singleKpiTotalRows = document.getElementById('single-kpi-total-rows');
    const singleKpiValidRows = document.getElementById('single-kpi-valid-rows');
    const singleKpiValidPct = document.getElementById('single-kpi-valid-pct');
    const singleKpiInvalidRows = document.getElementById('single-kpi-invalid-rows');
    const singleKpiInvalidPct = document.getElementById('single-kpi-invalid-pct');
    const singleKpiCellsErrors = document.getElementById('single-kpi-cells-errors');
    const singleKpiRulesCount = document.getElementById('single-kpi-rules-count');
    const singleKpiConformityRate = document.getElementById('single-kpi-conformity-rate');

    const btnSingleDownloadExcel = document.getElementById('btn-single-download-excel');
    const btnSingleRestart = document.getElementById('btn-single-restart');

    const singleTabBtnIssues = document.getElementById('single-tab-btn-issues');
    const singleTabBtnRules = document.getElementById('single-tab-btn-rules');
    const singleTabBtnFreq = document.getElementById('single-tab-btn-freq');
    const singleBadgeIssues = document.getElementById('single-badge-issues');
    const singleBadgeRules = document.getElementById('single-badge-rules');

    const singlePaneIssues = document.getElementById('single-pane-issues');
    const singlePaneRules = document.getElementById('single-pane-rules');
    const singlePaneFreq = document.getElementById('single-pane-freq');

    const singleIssuesSearch = document.getElementById('single-issues-search');
    const singleIssuesTheadTr = document.getElementById('single-issues-thead-tr');
    const singleIssuesTbody = document.getElementById('single-issues-tbody');
    const singleRulesTbody = document.getElementById('single-rules-tbody');
    const singleFreqContainer = document.getElementById('single-freq-container');

    // Estado interno do modo único
    const singleState = {
        file: null,
        sessionId: null,
        filename: '',
        cols: [],
        totalRows: 0,
        totalCols: 0,
        rules: [],
        reportId: null,
        summary: null,
        previewRows: [],
        selectedSheets: [],
        userHeaderLine: null
    };

    // Upload & Drag-and-drop
    if (singleDropzone && singleFileInput) {
        ['dragenter', 'dragover'].forEach(evt => {
            singleDropzone.addEventListener(evt, (e) => {
                e.preventDefault();
                singleDropzone.classList.add('drag-over');
            });
        });
        ['dragleave', 'drop'].forEach(evt => {
            singleDropzone.addEventListener(evt, (e) => {
                e.preventDefault();
                singleDropzone.classList.remove('drag-over');
            });
        });

        singleDropzone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files && files[0]) {
                handleSingleFileSelect(files[0]);
            }
        });

        singleDropzone.addEventListener('click', (e) => {
            if (e.target.closest('.file-config-panel')) {
                return;
            }
            if (e.target !== singleFileInput) {
                singleFileInput.click();
            }
        });

        singleFileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                handleSingleFileSelect(e.target.files[0]);
            }
        });
    }

    function handleSingleFileSelect(file) {
        const validExts = ['.xlsx', '.xls', '.csv'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!validExts.includes(ext)) {
            alert('Formato de arquivo não suportado. Por favor, envie um arquivo .xlsx, .xls ou .csv.');
            return;
        }

        singleState.file = file;
        singleState.userHeaderLine = null;
        const sLine = document.getElementById('single-header-line');
        if (sLine) sLine.value = 1;

        singleFilename.textContent = file.name;
        singleFilesize.textContent = (file.size / 1024).toFixed(1) + ' KB';
        singleFileMeta.style.display = 'inline-flex';
        singleDropzone.classList.add('file-loaded');
        btnSingleReadFile.disabled = false;

        inspectAndRenderSheets(file, 'single');
    }

    // Leitura das colunas do arquivo
    if (btnSingleReadFile) {
        btnSingleReadFile.addEventListener('click', async () => {
            if (!singleState.file) return;

            const btnText = btnSingleReadFile.querySelector('.btn-text');
            const spinner = btnSingleReadFile.querySelector('.spinner');
            btnSingleReadFile.disabled = true;
            btnText.textContent = 'Lendo colunas...';
            spinner.style.display = 'inline-block';

            const singleHeaderLine = parseInt(document.getElementById('single-header-line')?.value || '1', 10) || 1;
            const formData = new FormData();
            formData.append('file', singleState.file);
            formData.append('header_line', singleHeaderLine);
            if (singleState.selectedSheets && singleState.selectedSheets.length > 0) {
                formData.append('sheets', JSON.stringify(singleState.selectedSheets));
            }

            try {
                const res = await fetch('/api/single/upload-headers', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.error || 'Erro ao carregar arquivo.');
                }

                singleState.sessionId = data.session_id;
                singleState.filename = data.filename;
                singleState.cols = data.cols;
                singleState.totalRows = data.total_rows;
                singleState.totalCols = data.total_cols;
                singleState.rules = [];

                // Atualiza painel do Passo 2
                singleInfoName.textContent = singleState.filename;
                singleInfoRows.textContent = Number(singleState.totalRows).toLocaleString('pt-BR');
                singleInfoCols.textContent = Number(singleState.totalCols).toLocaleString('pt-BR');

                // Popula selects de colunas
                populateSingleColSelects(singleState.cols);
                renderSingleRulesList();

                // Transição de tela
                singleStepUpload.style.display = 'none';
                singleStepConfig.style.display = 'block';
                singleStepResults.style.display = 'none';
                singleStepConfig.scrollIntoView({ behavior: 'smooth' });

            } catch (err) {
                alert(err.message);
            } finally {
                btnSingleReadFile.disabled = false;
                btnText.textContent = 'Ler Colunas e Configurar Regras';
                spinner.style.display = 'none';
            }
        });
    }

    function populateSingleColSelects(cols) {
        if (!singleRuleCol || !singleRuleTargetCol) return;
        singleRuleCol.innerHTML = '<option value="">Selecione uma coluna...</option>';
        singleRuleTargetCol.innerHTML = '<option value="">Selecione a 2ª coluna...</option>';

        cols.forEach(c => {
            const opt1 = document.createElement('option');
            opt1.value = c;
            opt1.textContent = c;
            singleRuleCol.appendChild(opt1);

            const opt2 = document.createElement('option');
            opt2.value = c;
            opt2.textContent = c;
            singleRuleTargetCol.appendChild(opt2);
        });
    }

    // Componente de Dropdown Customizado com Ícones SVG SplitC
    const customRuleTrigger = document.getElementById('custom-rule-trigger');
    const customRuleDropdown = document.getElementById('custom-rule-dropdown');
    const customRuleTriggerIcon = document.getElementById('custom-rule-trigger-icon');
    const customRuleTriggerLabel = document.getElementById('custom-rule-trigger-label');

    function selectCustomRule(val) {
        if (!customRuleDropdown || !singleRuleType) return;
        const options = customRuleDropdown.querySelectorAll('.custom-select-option');
        options.forEach(opt => {
            const isMatch = opt.getAttribute('data-value') === val;
            opt.classList.toggle('selected', isMatch);
            opt.setAttribute('aria-selected', isMatch ? 'true' : 'false');
            if (isMatch) {
                const iconHtml = opt.querySelector('.option-icon').innerHTML;
                const title = opt.querySelector('.option-title').textContent.trim();
                const desc = opt.querySelector('.option-desc').textContent.trim();
                if (customRuleTriggerIcon) customRuleTriggerIcon.innerHTML = iconHtml;
                if (customRuleTriggerLabel) customRuleTriggerLabel.textContent = `${title} ${desc}`;
            }
        });

        if (singleRuleType.value !== val) {
            singleRuleType.value = val;
            singleRuleType.dispatchEvent(new Event('change'));
        }
    }

    if (customRuleTrigger && customRuleDropdown && singleRuleType) {
        customRuleTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = customRuleDropdown.style.display === 'block';
            if (isOpen) {
                closeCustomRuleDropdown();
            } else {
                openCustomRuleDropdown();
            }
        });

        customRuleTrigger.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
                e.preventDefault();
                openCustomRuleDropdown();
            } else if (e.key === 'Escape') {
                closeCustomRuleDropdown();
            }
        });

        function openCustomRuleDropdown() {
            customRuleDropdown.style.display = 'block';
            customRuleTrigger.classList.add('active');
            customRuleTrigger.setAttribute('aria-expanded', 'true');
        }

        function closeCustomRuleDropdown() {
            customRuleDropdown.style.display = 'none';
            customRuleTrigger.classList.remove('active');
            customRuleTrigger.setAttribute('aria-expanded', 'false');
        }

        document.addEventListener('click', (e) => {
            if (!customRuleTrigger.contains(e.target) && !customRuleDropdown.contains(e.target)) {
                closeCustomRuleDropdown();
            }
        });

        const customOptions = customRuleDropdown.querySelectorAll('.custom-select-option');
        customOptions.forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                const val = opt.getAttribute('data-value');
                selectCustomRule(val);
                closeCustomRuleDropdown();
                customRuleTrigger.focus();
            });
        });
    }

    // Dinâmica de parâmetros do tipo de regra
    if (singleRuleType) {
        singleRuleType.addEventListener('change', () => {
            const rType = singleRuleType.value;
            singleParamContainer.style.display = 'none';
            paramCompareCols.style.display = 'none';
            paramThreshold.style.display = 'none';
            paramCount.style.display = 'none';
            paramLength.style.display = 'none';

            if (rType === 'compare_cols') {
                singleParamContainer.style.display = 'block';
                paramCompareCols.style.display = 'grid';
                if (singleParamLabel) singleParamLabel.textContent = 'Comparar com outra Coluna *';
                if (singleParamHelp) singleParamHelp.textContent = 'Escolha o operador e a coluna de destino';
            } else if (['greater_than', 'less_than', 'equals', 'not_equals'].includes(rType)) {
                singleParamContainer.style.display = 'block';
                paramThreshold.style.display = 'block';
                if (singleParamLabel) singleParamLabel.textContent = 'Valor de Referência *';
                if (singleParamHelp) singleParamHelp.textContent = 'Digite o valor fixo (numérico, data ou texto)';
            } else if (rType === 'count_equals') {
                singleParamContainer.style.display = 'block';
                paramCount.style.display = 'block';
                if (singleParamLabel) singleParamLabel.textContent = 'Limite Mínimo de Repetições *';
                if (singleParamHelp) singleParamHelp.textContent = 'Alerta se o valor se repetir X ou mais vezes';
            } else if (rType === 'text_length') {
                singleParamContainer.style.display = 'block';
                paramLength.style.display = 'grid';
                if (singleParamLabel) singleParamLabel.textContent = 'Comprimento do Texto *';
                if (singleParamHelp) singleParamHelp.textContent = 'Ex: 11 para CPF, 14 para CNPJ';
            }
        });
    }

    // Adicionar regra
    if (btnSingleAddRule) {
        btnSingleAddRule.addEventListener('click', () => {
            const col = singleRuleCol.value;
            if (!col) {
                alert('Por favor, selecione uma coluna para validar.');
                singleRuleCol.focus();
                return;
            }

            const ruleType = singleRuleType.value;
            let targetCol = '';
            let op = '==';
            let threshold = '';
            let countVal = 2;
            let lenOp = '==';
            let lenVal = 0;

            if (ruleType === 'compare_cols') {
                targetCol = singleRuleTargetCol.value;
                if (!targetCol) {
                    alert('Selecione a segunda coluna para a comparação.');
                    singleRuleTargetCol.focus();
                    return;
                }
                if (targetCol === col) {
                    alert('Selecione uma coluna diferente da primeira para comparar.');
                    return;
                }
                op = singleRuleOp.value;
            } else if (['greater_than', 'less_than', 'equals', 'not_equals'].includes(ruleType)) {
                threshold = singleRuleThreshold.value.trim();
                if (!threshold) {
                    alert('Informe o valor de referência para a comparação.');
                    singleRuleThreshold.focus();
                    return;
                }
            } else if (ruleType === 'count_equals') {
                countVal = parseInt(singleRuleCount.value) || 2;
            } else if (ruleType === 'text_length') {
                lenOp = singleRuleLenOp.value;
                lenVal = parseInt(singleRuleLenVal.value) || 0;
                if (lenVal <= 0) {
                    alert('Informe a quantidade de caracteres esperada.');
                    singleRuleLenVal.focus();
                    return;
                }
            }

            // Descrição amigável
            let desc = '';
            const typeLabels = {
                'duplicate': 'Verificar Duplicatas',
                'only_letters': 'Apenas Letras',
                'only_numbers': 'Apenas Números',
                'alphanumeric': 'Alfanumérico (Letras e Números)',
                'not_empty': 'Campo Obrigatório (Não Vazio)',
                'compare_cols': `Comparar: [${col}] ${op} [${targetCol}]`,
                'greater_than': `Maior que (>) ${threshold}`,
                'less_than': `Menor que (<) ${threshold}`,
                'equals': `Igual a (==) ${threshold}`,
                'not_equals': `Diferente de (!=) ${threshold}`,
                'count_equals': `Contar Repetições (limite: >= ${countVal})`,
                'text_length': `Tamanho ${lenOp} ${lenVal} caracteres`
            };
            desc = typeLabels[ruleType] || ruleType;

            // Evita regra idêntica duplicada
            const exists = singleState.rules.some(r => 
                r.col === col && r.rule_type === ruleType && r.target_col === targetCol && r.threshold === threshold && r.op === op
            );
            if (exists) {
                alert('Essa mesma regra já foi adicionada para esta coluna.');
                return;
            }

            singleState.rules.push({
                id: Date.now() + Math.random().toString(36).substr(2, 4),
                col: col,
                rule_type: ruleType,
                target_col: targetCol,
                op: op,
                threshold: threshold,
                count: countVal,
                length_op: lenOp,
                length_val: lenVal,
                desc: desc
            });

            renderSingleRulesList();
            if (singleRuleThreshold) singleRuleThreshold.value = '';
            if (singleRuleLenVal) singleRuleLenVal.value = '';
        });
    }

    function renderSingleRulesList() {
        if (!singleRulesContainer) return;
        singleRulesContainer.innerHTML = '';

        if (singleState.rules.length === 0) {
            singleRulesContainer.appendChild(singleEmptyRulesMsg);
            singleRulesCountBadge.textContent = '0 regras';
            btnSingleRunAudit.disabled = true;
            return;
        }

        singleRulesCountBadge.textContent = `${singleState.rules.length} regra${singleState.rules.length > 1 ? 's' : ''}`;
        btnSingleRunAudit.disabled = false;

        singleState.rules.forEach((rule, idx) => {
            const item = document.createElement('div');
            item.className = 'single-rule-item';
            item.innerHTML = `
                <div class="rule-item-content">
                    <span class="rule-col-badge">${escapeHtml(rule.col)}</span>
                    <span class="rule-type-tag">${escapeHtml(rule.desc)}</span>
                </div>
                <button type="button" class="btn-remove-rule" title="Remover Regra" data-idx="${idx}">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            `;
            item.querySelector('.btn-remove-rule').addEventListener('click', () => {
                singleState.rules.splice(idx, 1);
                renderSingleRulesList();
            });
            singleRulesContainer.appendChild(item);
        });
    }

    // Pacotes Inteligentes de 1 Clique (Auditar 1 Base)
    const presetPackCadastral = document.getElementById('preset-pack-cadastral');
    const presetPackFinanceiro = document.getElementById('preset-pack-financeiro');

    function normalizeAuditColName(colName) {
        try {
            return String(colName || '')
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toUpperCase()
                .trim();
        } catch (_) {
            return String(colName || '').toUpperCase().trim();
        }
    }

    function addSinglePresetRuleSafe(col, ruleType, descText) {
        try {
            if (!col || !ruleType || !Array.isArray(singleState.rules)) return false;
            const already = singleState.rules.some(r => r.col === col && r.rule_type === ruleType);
            if (already) return false;
            singleState.rules.push({
                id: Date.now() + Math.random().toString(36).substr(2, 5),
                col: col,
                rule_type: ruleType,
                desc: descText
            });
            return true;
        } catch (err) {
            console.warn('Erro ao adicionar regra de preset:', err);
            return false;
        }
    }

    if (presetPackCadastral) {
        presetPackCadastral.addEventListener('click', () => {
            try {
                const cols = Array.isArray(singleState.cols) ? singleState.cols : [];
                let addedCount = 0;
                let matchedAnyCol = false;

                cols.forEach(col => {
                    const norm = normalizeAuditColName(col);
                    const tokens = norm.split(/[^A-Z0-9]+/).filter(Boolean);

                    const isDocOrId = (
                        tokens.includes('ID') ||
                        tokens.includes('DOC') ||
                        norm.includes('CPF') ||
                        norm.includes('CNPJ') ||
                        norm.includes('DOCUMENTO') ||
                        norm.includes('MATRICULA') ||
                        norm.includes('CODIGO')
                    );

                    const isCpfCnpjNomeEmail = (
                        norm.includes('CPF') ||
                        norm.includes('CNPJ') ||
                        norm.includes('NOME') ||
                        norm.includes('RAZAO') ||
                        norm.includes('EMAIL') ||
                        norm.includes('E-MAIL')
                    );

                    if (isDocOrId) {
                        matchedAnyCol = true;
                        if (addSinglePresetRuleSafe(col, 'duplicate', `Verificar Duplicatas na coluna '${col}'`)) {
                            addedCount++;
                        }
                    }

                    if (isCpfCnpjNomeEmail) {
                        matchedAnyCol = true;
                        if (addSinglePresetRuleSafe(col, 'not_empty', `Campo Obrigatório em '${col}'`)) {
                            addedCount++;
                        }
                    }
                });

                if (addedCount > 0) {
                    renderSingleRulesList();
                    showValidaiToast(`⚡ Pacote Cadastral aplicado! ${addedCount} regra(s) adicionada(s).`, 'success');
                } else if (matchedAnyCol) {
                    showValidaiToast('✅ As regras do Pacote Cadastral já estão ativas na auditoria.', 'info');
                } else {
                    showValidaiToast('⚠️ Nenhuma coluna cadastral (ID, CPF, CNPJ, Nome ou E-mail) detectada automaticamente.', 'info');
                }
            } catch (err) {
                console.error('Erro ao aplicar Pacote Cadastral:', err);
            }
        });
    }

    if (presetPackFinanceiro) {
        presetPackFinanceiro.addEventListener('click', () => {
            try {
                const cols = Array.isArray(singleState.cols) ? singleState.cols : [];
                const finTerms = ['VALOR', 'PRECO', 'TOTAL', 'SALDO', 'VLR', 'MONTANTE', 'LIQUIDO', 'BRUTO'];
                let addedCount = 0;
                let matchedAnyCol = false;

                cols.forEach(col => {
                    const norm = normalizeAuditColName(col);
                    if (finTerms.some(term => norm.includes(term))) {
                        matchedAnyCol = true;
                        if (addSinglePresetRuleSafe(col, 'not_empty', `Campo Obrigatório em '${col}'`)) {
                            addedCount++;
                        }
                        if (addSinglePresetRuleSafe(col, 'only_numbers', `Apenas Números em '${col}'`)) {
                            addedCount++;
                        }
                    }
                });

                if (addedCount > 0) {
                    renderSingleRulesList();
                    showValidaiToast(`💰 Pacote Financeiro aplicado! ${addedCount} regra(s) adicionada(s).`, 'success');
                } else if (matchedAnyCol) {
                    showValidaiToast('✅ As regras do Pacote Financeiro já estão ativas na auditoria.', 'info');
                } else {
                    showValidaiToast('⚠️ Nenhuma coluna financeira (Valor, Preço, Total ou Saldo) detectada automaticamente.', 'info');
                }
            } catch (err) {
                console.error('Erro ao aplicar Pacote Financeiro:', err);
            }
        });
    }

    // Presets rápidos
    if (presetIdDuplicates) {
        presetIdDuplicates.addEventListener('click', () => {
            const keywords = ['id', 'codigo', 'código', 'ticket', 'cpf', 'matricula', 'documento', 'doc', 'chave', 'num'];
            let addedCount = 0;
            singleState.cols.forEach(col => {
                const norm = col.toLowerCase();
                if (keywords.some(k => norm.includes(k))) {
                    if (!singleState.rules.some(r => r.col === col && r.rule_type === 'duplicate')) {
                        singleState.rules.push({
                            id: Date.now() + Math.random().toString(36).substr(2, 4),
                            col: col,
                            rule_type: 'duplicate',
                            desc: `Verificar Duplicatas na coluna '${col}'`
                        });
                        addedCount++;
                    }
                }
            });
            if (addedCount > 0) {
                renderSingleRulesList();
            } else {
                alert('Nenhuma coluna com nome de identificador (ID, CÓDIGO, TICKET, CPF, etc.) foi identificada.');
            }
        });
    }

    if (presetAllNotEmpty) {
        presetAllNotEmpty.addEventListener('click', () => {
            let addedCount = 0;
            singleState.cols.forEach(col => {
                if (!singleState.rules.some(r => r.col === col && r.rule_type === 'not_empty')) {
                    singleState.rules.push({
                        id: Date.now() + Math.random().toString(36).substr(2, 4),
                        col: col,
                        rule_type: 'not_empty',
                        desc: `Campo Obrigatório em '${col}'`
                    });
                    addedCount++;
                }
            });
            if (addedCount > 0) {
                renderSingleRulesList();
            } else {
                alert('Todas as colunas já possuem a regra de campo obrigatório adicionada.');
            }
        });
    }

    if (btnSingleClearRules) {
        btnSingleClearRules.addEventListener('click', () => {
            if (singleState.rules.length > 0 && confirm('Deseja realmente limpar todas as regras adicionadas?')) {
                singleState.rules = [];
                renderSingleRulesList();
            }
        });
    }

    if (btnSingleChangeFile) {
        btnSingleChangeFile.addEventListener('click', () => {
            singleStepUpload.style.display = 'block';
            singleStepConfig.style.display = 'none';
            singleStepResults.style.display = 'none';
        });
    }

    // Executar auditoria
    if (btnSingleRunAudit) {
        btnSingleRunAudit.addEventListener('click', async () => {
            if (singleState.rules.length === 0) {
                alert('Adicione ao menos uma regra de validação antes de continuar.');
                return;
            }

            startBtnStepperLoading(btnSingleRunAudit, 'Executar Auditoria de Dados');

            try {
                const res = await fetch('/api/single/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: singleState.sessionId,
                        rules: singleState.rules,
                        header_line: parseInt(document.getElementById('single-header-line')?.value || '1', 10) || 1,
                        sheets: singleState.selectedSheets
                    })
                });
                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.error || 'Erro na auditoria.');
                }

                singleState.reportId = data.report_id;
                singleState.summary = data.summary;
                singleState.previewRows = data.preview_rows;

                renderSingleResults(data);

                singleStepConfig.style.display = 'none';
                singleStepResults.style.display = 'block';
                singleStepResults.scrollIntoView({ behavior: 'smooth' });

            } catch (err) {
                alert(err.message);
            } finally {
                stopBtnStepperLoading(btnSingleRunAudit, 'Executar Auditoria de Dados');
                if (!singleState.rules || singleState.rules.length === 0) {
                    btnSingleRunAudit.disabled = true;
                }
            }
        });
    }

    function renderSingleResults(data) {
        const s = data.summary;

        // Banner
        if (s.is_perfect) {
            singleAlertBanner.className = 'result-banner banner-success';
            singleAlertTitle.textContent = 'Excelente! Planilha 100% Conforme!';
            singleAlertDesc.textContent = 'Todas as regras aplicadas foram validadas com sucesso. Nenhuma inconsistência foi encontrada.';
            if (singleAlertIcon) {
                singleAlertIcon.innerHTML = `<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;
            }
        } else {
            singleAlertBanner.className = 'result-banner banner-alert';
            singleAlertTitle.textContent = 'Atenção: Foram encontradas inconsistências na planilha!';
            singleAlertDesc.textContent = `Foram detectadas ${s.total_errors.toLocaleString('pt-BR')} divergências distribuídas em ${s.invalid_rows.toLocaleString('pt-BR')} linhas. Veja os detalhes abaixo ou baixe o Excel com as células destacadas.`;
            if (singleAlertIcon) {
                singleAlertIcon.innerHTML = `<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
            }
        }

        // KPIs
        singleKpiTotalRows.textContent = s.total_rows.toLocaleString('pt-BR');
        singleKpiValidRows.textContent = s.valid_rows.toLocaleString('pt-BR');
        singleKpiValidPct.textContent = `${((s.valid_rows / s.total_rows) * 100 || 0).toFixed(1)}% do total`;
        singleKpiInvalidRows.textContent = s.invalid_rows.toLocaleString('pt-BR');
        singleKpiInvalidPct.textContent = `${((s.invalid_rows / s.total_rows) * 100 || 0).toFixed(1)}% com falhas`;
        singleKpiCellsErrors.textContent = s.total_errors.toLocaleString('pt-BR');
        singleKpiRulesCount.textContent = s.rules_count;
        singleKpiConformityRate.textContent = `${s.conformity_rate}%`;

        // Card de Destaque Executivo: Tempo Estimado Economizado (Single)
        const singleTimeSavedCard = document.getElementById('single-time-saved-card');
        const singleTimeSavedVal = document.getElementById('single-time-saved-val');
        if (singleTimeSavedCard && singleTimeSavedVal) {
            try {
                const totalRows = Number(s.total_rows || 0);
                const totalCols = Number(s.total_columns || (singleState.cols ? singleState.cols.length : 0) || 1);
                const totalCells = totalRows * totalCols;
                const savedMinutes = Math.max(15, Math.round(totalCells / 20));

                let timeDisplay = '';
                if (savedMinutes < 60) {
                    timeDisplay = `~${savedMinutes} minutos`;
                } else {
                    const hours = Math.floor(savedMinutes / 60);
                    const mins = savedMinutes % 60;
                    timeDisplay = mins > 0 ? `~${hours}h ${mins < 10 ? '0' : ''}${mins}min` : `~${hours}h`;
                }

                singleTimeSavedVal.textContent = timeDisplay;
                singleTimeSavedCard.style.display = 'flex';
            } catch (tErr) {
                console.warn('Erro ao calcular tempo economizado (single):', tErr);
                singleTimeSavedCard.style.display = 'none';
            }
        }

        // Badges nas abas
        singleBadgeIssues.textContent = s.invalid_rows.toLocaleString('pt-BR');
        singleBadgeRules.textContent = s.rules_count;

        // Frequência de repetições (Aba 3)
        if (s.frequency_breakdown && Object.keys(s.frequency_breakdown).length > 0) {
            singleTabBtnFreq.style.display = 'inline-flex';
            renderSingleFrequency(s.frequency_breakdown);
        } else {
            singleTabBtnFreq.style.display = 'none';
        }

        // Renderiza tabelas
        renderSingleIssuesTable(singleIssuesSearch ? singleIssuesSearch.value : '');
        renderSingleRulesTable(s.rules_stats);

        // Aba padrão ativa
        switchSingleTab('issues');
    }

    function renderSingleIssuesTable(query = '') {
        if (!singleIssuesTheadTr || !singleIssuesTbody) return;
        singleIssuesTheadTr.innerHTML = `
            <th style="width: 70px; text-align: center;">Linha</th>
            <th style="width: 120px; text-align: center;">Situação</th>
            <th style="min-width: 200px;">Inconsistências Detectadas</th>
        `;

        singleState.cols.forEach(c => {
            const th = document.createElement('th');
            th.textContent = c;
            singleIssuesTheadTr.appendChild(th);
        });

        singleIssuesTbody.innerHTML = '';
        const q = query.toLowerCase().trim();

        const filtered = singleState.previewRows.filter(row => {
            if (!q) return true;
            return Object.values(row).some(v => String(v).toLowerCase().includes(q));
        });

        if (filtered.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td colspan="${singleState.cols.length + 3}" style="text-align: center; padding: 32px; color: var(--text-muted);">Nenhum registro encontrado para este filtro.</td>`;
            singleIssuesTbody.appendChild(tr);
            return;
        }

        filtered.forEach(row => {
            const tr = document.createElement('tr');
            const errors = row._errors || {};
            const hasError = Object.keys(errors).length > 0;

            let reasonsHtml = '';
            if (hasError) {
                const tags = [];
                for (const [colName, msgList] of Object.entries(errors)) {
                    tags.push(`<span class="invalid-reason-badge"><strong>${escapeHtml(colName)}:</strong> ${escapeHtml(msgList.join(', '))}</span>`);
                }
                reasonsHtml = `<div class="invalid-cell-wrap">${tags.join('')}</div>`;
            } else {
                reasonsHtml = '<span class="status-badge-ok">Conforme</span>';
            }

            const statusBadge = hasError 
                ? '<span class="status-badge-diff">Inconsistente</span>'
                : '<span class="status-badge-ok">OK</span>';

            let cellsHtml = '';
            singleState.cols.forEach(c => {
                const val = row[c] !== undefined ? row[c] : '';
                const isCellError = errors[c] !== undefined;
                if (isCellError) {
                    cellsHtml += `<td class="cell-invalid" title="${escapeHtml(errors[c].join(', '))}">${escapeHtml(val)}</td>`;
                } else {
                    cellsHtml += `<td>${escapeHtml(val)}</td>`;
                }
            });

            tr.innerHTML = `
                <td style="text-align: center;"><span class="badge-line">${row._row_idx}</span></td>
                <td style="text-align: center;">${statusBadge}</td>
                <td>${reasonsHtml}</td>
                ${cellsHtml}
            `;
            singleIssuesTbody.appendChild(tr);
        });
    }

    function renderSingleRulesTable(rulesStats) {
        if (!singleRulesTbody) return;
        singleRulesTbody.innerHTML = '';

        rulesStats.forEach(r => {
            const tr = document.createElement('tr');
            const isOk = r.passed;
            const statusBadge = isOk 
                ? '<span class="status-badge-ok">100% Conforme</span>'
                : `<span class="status-badge-diff">${r.violations_count} Inconsistência(s)</span>`;

            tr.innerHTML = `
                <td style="text-align: center;"><strong>#${r.rule_id}</strong></td>
                <td><span class="rule-col-badge">${escapeHtml(r.col)}</span></td>
                <td><strong>${escapeHtml(r.rule_type)}</strong></td>
                <td>${escapeHtml(r.description)}</td>
                <td style="text-align: right; font-weight: bold; color: ${isOk ? 'var(--success)' : 'var(--danger)'};">${r.violations_count.toLocaleString('pt-BR')}</td>
                <td style="text-align: center;">${statusBadge}</td>
            `;
            singleRulesTbody.appendChild(tr);
        });
    }

    function renderSingleFrequency(breakdown) {
        if (!singleFreqContainer) return;
        singleFreqContainer.innerHTML = '';

        for (const [col, items] of Object.entries(breakdown)) {
            const card = document.createElement('div');
            card.className = 'freq-card';
            let rowsHtml = items.map(it => `
                <tr>
                    <td>${escapeHtml(it.value)}</td>
                    <td style="text-align: center;"><span class="badge-line text-danger font-bold">${it.count.toLocaleString('pt-BR')}x</span></td>
                </tr>
            `).join('');

            card.innerHTML = `
                <h4>Repetições na Coluna: ${escapeHtml(col)}</h4>
                <table class="freq-table">
                    <thead>
                        <tr>
                            <th>Valor</th>
                            <th style="text-align: center;">Ocorrências</th>
                        </tr>
                    </thead>
                    <tbody>${rowsHtml}</tbody>
                </table>
            `;
            singleFreqContainer.appendChild(card);
        }
    }

    function switchSingleTab(tab) {
        [singleTabBtnIssues, singleTabBtnRules, singleTabBtnFreq].forEach(b => {
            if (b) b.classList.remove('active');
        });
        if (singlePaneIssues) singlePaneIssues.style.display = 'none';
        if (singlePaneRules) singlePaneRules.style.display = 'none';
        if (singlePaneFreq) singlePaneFreq.style.display = 'none';

        if (tab === 'issues') {
            if (singleTabBtnIssues) singleTabBtnIssues.classList.add('active');
            if (singlePaneIssues) singlePaneIssues.style.display = 'block';
        } else if (tab === 'rules') {
            if (singleTabBtnRules) singleTabBtnRules.classList.add('active');
            if (singlePaneRules) singlePaneRules.style.display = 'block';
        } else if (tab === 'freq') {
            if (singleTabBtnFreq) singleTabBtnFreq.classList.add('active');
            if (singlePaneFreq) singlePaneFreq.style.display = 'block';
        }
    }

    if (singleTabBtnIssues) singleTabBtnIssues.addEventListener('click', () => switchSingleTab('issues'));
    if (singleTabBtnRules) singleTabBtnRules.addEventListener('click', () => switchSingleTab('rules'));
    if (singleTabBtnFreq) singleTabBtnFreq.addEventListener('click', () => switchSingleTab('freq'));

    if (singleIssuesSearch) {
        singleIssuesSearch.addEventListener('input', (e) => {
            renderSingleIssuesTable(e.target.value);
        });
    }

    // Download do Excel de Auditoria Única
    if (btnSingleDownloadExcel) {
        btnSingleDownloadExcel.addEventListener('click', () => {
            if (!singleState.reportId) {
                alert('Nenhum relatório disponível para download.');
                return;
            }
            window.location.href = `/api/single/download-report/${singleState.reportId}`;
        });
    }

    // Nova Auditoria
    if (btnSingleRestart) {
        btnSingleRestart.addEventListener('click', () => {
            singleState.file = null;
            singleState.rules = [];
            singleState.reportId = null;
            if (singleFileInput) singleFileInput.value = '';
            if (singleFileMeta) singleFileMeta.style.display = 'none';
            if (singleDropzone) singleDropzone.classList.remove('file-loaded');
            if (btnSingleReadFile) btnSingleReadFile.disabled = true;

            singleStepUpload.style.display = 'block';
            singleStepConfig.style.display = 'none';
            singleStepResults.style.display = 'none';
            singleStepUpload.scrollIntoView({ behavior: 'smooth' });
        });
    }

    // Reagir a mudanças de idioma
    window.addEventListener('validaiLanguageChanged', () => {
        if (state.lastCompareData) {
            renderResults(state.lastCompareData);
        }
    });
});
