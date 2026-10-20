/**
 * ValidAí - Conciliador de Taxas e Extratos (.OFX vs Vendas)
 * Controlador Frontend Padronizado com o Design System da Plataforma
 */

(function () {
    let currentSessionId = null;
    let currentReportId = null;
    let selectedOfxFiles = [];
    let selectedSalesFile = null;
    let reconciliationData = null;

    let currentFilter = 'all';
    let searchQuery = '';
    let currentPage = 1;
    const pageSize = 20;

    // Elementos do DOM - Passo 1
    const stepUpload = document.getElementById('step-upload-ofx');
    const dropOfxFile = document.getElementById('drop-ofx-file');
    const fileOfxInput = document.getElementById('file-ofx-input');
    const fileMetaOfx = document.getElementById('file-meta-ofx');
    const filenameOfx = document.getElementById('filename-ofx');
    const filesizeOfx = document.getElementById('filesize-ofx');

    const dropSalesSheet = document.getElementById('drop-sales-sheet');
    const fileSalesInput = document.getElementById('file-sales-input');
    const fileMetaSales = document.getElementById('file-meta-sales');
    const filenameSales = document.getElementById('filename-sales');
    const filesizeSales = document.getElementById('filesize-sales');

    const btnTryExample = document.getElementById('btn-ofx-try-example');
    const btnUpload = document.getElementById('btn-ofx-upload');
    const uploadAlert = document.getElementById('ofx-upload-alert');
    const uploadAlertMsg = document.getElementById('ofx-upload-alert-msg');
    const btnCloseUploadAlert = document.getElementById('btn-close-ofx-upload-alert');

    // Elementos do DOM - Passo 2
    const stepConfig = document.getElementById('step-config-ofx');
    const infoOfxName = document.getElementById('info-ofx-name');
    const infoOfxCountBadge = document.getElementById('info-ofx-count-badge');
    const infoSalesName = document.getElementById('info-sales-name');
    const infoSalesRows = document.getElementById('info-sales-rows');

    const selectColId = document.getElementById('select-ofx-col-id');
    const selectColGross = document.getElementById('select-ofx-col-gross');
    const selectColDate = document.getElementById('select-ofx-col-date');
    const selectColAcquirer = document.getElementById('select-ofx-col-acquirer');

    const inputExpectedRate = document.getElementById('input-expected-rate');
    const presetRateButtons = document.querySelectorAll('.btn-preset-rate');
    const selectTolerance = document.getElementById('select-ofx-tolerance');
    const selectDateTol = document.getElementById('select-ofx-date-tol');

    const processAlert = document.getElementById('ofx-process-alert');
    const processAlertMsg = document.getElementById('ofx-process-alert-msg');
    const btnCloseProcessAlert = document.getElementById('btn-close-ofx-process-alert');

    const btnBackStep1 = document.getElementById('btn-ofx-back-step1');
    const btnProcess = document.getElementById('btn-process-ofx');

    // Elementos do DOM - Passo 3
    const stepResults = document.getElementById('step-results-ofx');
    const bannerSuccess = document.getElementById('ofx-banner-success');
    const bannerDiffs = document.getElementById('ofx-banner-diffs');
    const bannerDiffsMsg = document.getElementById('ofx-banner-diffs-msg');

    const kpiReconciledPct = document.getElementById('ofx-kpi-reconciled-pct');
    const kpiReconciledCount = document.getElementById('ofx-kpi-reconciled-count');
    const kpiGrossVal = document.getElementById('ofx-kpi-gross-val');
    const kpiSalesCount = document.getElementById('ofx-kpi-sales-count');
    const kpiCreditedVal = document.getElementById('ofx-kpi-credited-val');
    const kpiExpNetVal = document.getElementById('ofx-kpi-exp-net-val');
    const kpiLossVal = document.getElementById('ofx-kpi-loss-val');
    const kpiDivergentCount = document.getElementById('ofx-kpi-divergent-count');
    const kpiUnpaidCount = document.getElementById('ofx-kpi-unpaid-count');
    const kpiOrphanCount = document.getElementById('ofx-kpi-orphan-count');
    const kpiOrphanSub = document.getElementById('ofx-kpi-orphan-sub');

    const btnDownloadAudit = document.getElementById('btn-ofx-download-audit');
    const btnDownloadMirror = document.getElementById('btn-ofx-download-mirror');

    const badgeAll = document.getElementById('badge-ofx-all');
    const badgeDivergent = document.getElementById('badge-ofx-divergent');
    const badgeReconciled = document.getElementById('badge-ofx-reconciled');
    const badgeUnpaid = document.getElementById('badge-ofx-unpaid');
    const badgeOrphan = document.getElementById('badge-ofx-orphan');

    const filterTabs = document.querySelectorAll('.result-nav-tabs .result-nav-tab-btn');
    const tableSearchInput = document.getElementById('ofx-table-search');
    const tbodyReconciliation = document.getElementById('tbody-ofx-reconciliation');
    const paginationInfo = document.getElementById('ofx-pagination-info');
    const btnPrevPage = document.getElementById('btn-prev-page');
    const btnNextPage = document.getElementById('btn-next-page');

    const btnRestart = document.getElementById('btn-restart-ofx');

    // Tema gerenciado centralmente por header.html

    // Dropdown de Soluções
    const navDropdownBtn = document.getElementById('nav-solutions-btn');
    const navDropdownMenu = document.getElementById('nav-solutions-menu');
    if (navDropdownBtn && navDropdownMenu) {
        navDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = navDropdownMenu.classList.contains('show');
            navDropdownMenu.classList.toggle('show', !isOpen);
            navDropdownBtn.setAttribute('aria-expanded', !isOpen);
        });
        document.addEventListener('click', (e) => {
            if (!navDropdownBtn.contains(e.target) && !navDropdownMenu.contains(e.target)) {
                navDropdownMenu.classList.remove('show');
                navDropdownBtn.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // Dropdown de Idiomas
    const langToggleBtn = document.getElementById('lang-toggle-btn');
    const langDropdownMenu = document.getElementById('lang-dropdown-menu');
    if (langToggleBtn && langDropdownMenu) {
        langToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = langDropdownMenu.classList.contains('show');
            langDropdownMenu.classList.toggle('show', !isOpen);
            langToggleBtn.setAttribute('aria-expanded', !isOpen);
        });
        document.addEventListener('click', (e) => {
            if (!langToggleBtn.contains(e.target) && !langDropdownMenu.contains(e.target)) {
                langDropdownMenu.classList.remove('show');
                langToggleBtn.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // Formatador amigável de tamanho de arquivo
    function formatFileSize(bytes) {
        if (!bytes || bytes <= 0) return '0 KB';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function checkReadyForUpload() {
        const canUpload = (selectedOfxFiles.length > 0 && selectedSalesFile !== null);
        btnUpload.disabled = !canUpload;
    }

    function hideAlerts() {
        if (uploadAlert) uploadAlert.style.display = 'none';
        if (processAlert) processAlert.style.display = 'none';
    }

    if (btnCloseUploadAlert) {
        btnCloseUploadAlert.addEventListener('click', () => {
            uploadAlert.style.display = 'none';
        });
    }

    if (btnCloseProcessAlert) {
        btnCloseProcessAlert.addEventListener('click', () => {
            processAlert.style.display = 'none';
        });
    }

    // =========================================================================
    // 1. EVENTOS DE DRAG & DROP E SELEÇÃO DE ARQUIVOS (PASSO 1)
    // =========================================================================

    // Dropzone OFX
    ['dragenter', 'dragover'].forEach(eventName => {
        dropOfxFile.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropOfxFile.classList.add('drag-active');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropOfxFile.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropOfxFile.classList.remove('drag-active');
        });
    });

    dropOfxFile.addEventListener('drop', (e) => {
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleOfxFilesSelected(Array.from(e.dataTransfer.files));
        }
    });

    dropOfxFile.addEventListener('click', (e) => {
        if (e.target !== fileOfxInput) {
            fileOfxInput.click();
        }
    });

    fileOfxInput.addEventListener('change', () => {
        if (fileOfxInput.files && fileOfxInput.files.length > 0) {
            handleOfxFilesSelected(Array.from(fileOfxInput.files));
        }
    });

    function handleOfxFilesSelected(files) {
        hideAlerts();
        selectedOfxFiles = files;
        if (selectedOfxFiles.length === 1) {
            filenameOfx.textContent = selectedOfxFiles[0].name;
            filesizeOfx.textContent = formatFileSize(selectedOfxFiles[0].size);
        } else {
            filenameOfx.textContent = `${selectedOfxFiles.length} arquivos selecionados`;
            const totalBytes = selectedOfxFiles.reduce((acc, f) => acc + f.size, 0);
            filesizeOfx.textContent = formatFileSize(totalBytes);
        }
        fileMetaOfx.style.display = 'flex';
        dropOfxFile.classList.add('file-loaded');
        checkReadyForUpload();
    }

    // Dropzone Planilha de Vendas
    ['dragenter', 'dragover'].forEach(eventName => {
        dropSalesSheet.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropSalesSheet.classList.add('drag-active');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropSalesSheet.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropSalesSheet.classList.remove('drag-active');
        });
    });

    dropSalesSheet.addEventListener('drop', (e) => {
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleSalesFileSelected(e.dataTransfer.files[0]);
        }
    });

    dropSalesSheet.addEventListener('click', (e) => {
        if (e.target !== fileSalesInput) {
            fileSalesInput.click();
        }
    });

    fileSalesInput.addEventListener('change', () => {
        if (fileSalesInput.files && fileSalesInput.files.length > 0) {
            handleSalesFileSelected(fileSalesInput.files[0]);
        }
    });

    function handleSalesFileSelected(file) {
        hideAlerts();
        selectedSalesFile = file;
        filenameSales.textContent = selectedSalesFile.name;
        filesizeSales.textContent = formatFileSize(selectedSalesFile.size);
        fileMetaSales.style.display = 'flex';
        dropSalesSheet.classList.add('file-loaded');
        checkReadyForUpload();
    }

    // =========================================================================
    // 2. ENVIO DOS ARQUIVOS E TESTAR EXEMPLO
    // =========================================================================

    btnTryExample.addEventListener('click', async () => {
        hideAlerts();
        btnTryExample.disabled = true;
        btnTryExample.innerHTML = '<span class="spinner"></span> Carregando Exemplo...';

        try {
            const resp = await fetch('/api/ofx/load-example', {
                method: 'POST'
            });
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.error || 'Erro ao carregar exemplo de conciliação OFX.');
            }
            setupStep2(data);
        } catch (err) {
            uploadAlertMsg.textContent = err.message;
            uploadAlert.style.display = 'flex';
        } finally {
            btnTryExample.disabled = false;
            btnTryExample.innerHTML = '<span class="btn-text">Testar Exemplo</span>';
        }
    });

    btnUpload.addEventListener('click', async () => {
        if (selectedOfxFiles.length === 0 || !selectedSalesFile) return;

        hideAlerts();
        btnUpload.disabled = true;
        const spinner = btnUpload.querySelector('.spinner');
        const btnText = btnUpload.querySelector('.btn-text');
        if (spinner) spinner.style.display = 'inline-block';
        if (btnText) btnText.textContent = 'Lendo OFX e Planilha...';

        try {
            const formData = new FormData();
            selectedOfxFiles.forEach((file) => {
                formData.append('ofx_files', file);
            });
            formData.append('sheet_file', selectedSalesFile);

            const resp = await fetch('/api/ofx/upload', {
                method: 'POST',
                body: formData
            });

            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.error || 'Falha ao processar arquivos.');
            }
            setupStep2(data);
        } catch (err) {
            uploadAlertMsg.textContent = err.message;
            uploadAlert.style.display = 'flex';
        } finally {
            btnUpload.disabled = false;
            if (spinner) spinner.style.display = 'none';
            if (btnText) btnText.textContent = 'Ler Arquivos e Mapear Colunas';
        }
    });

    // =========================================================================
    // 3. PASSO 2: CONFIGURAÇÃO DE MAPEAMENTO E TAXA ESPERADA (%)
    // =========================================================================

    function setupStep2(data) {
        currentSessionId = data.session_id;

        infoOfxName.textContent = data.ofx_label || 'Extrato OFX';
        infoOfxCountBadge.textContent = `${data.ofx_count} transações`;
        infoSalesName.textContent = data.sheet_filename || 'Vendas';
        infoSalesRows.textContent = `(${data.sheet_rows} vendas)`;

        // Popula selects de colunas
        populateSelect(selectColId, data.cols, data.suggested.col_id, 'Selecione o NSU / ID Venda...');
        populateSelect(selectColGross, data.cols, data.suggested.col_gross_val, 'Selecione o Valor Bruto...');
        populateSelect(selectColDate, data.cols, data.suggested.col_date, 'Selecione a Data da Venda...');
        populateSelect(selectColAcquirer, data.cols, data.suggested.col_acquirer, '-- Não mapear (Opcional) --', true);

        // Transição de telas
        stepUpload.style.display = 'none';
        stepConfig.style.display = 'block';
        stepResults.style.display = 'none';

        window.scrollTo({ top: stepConfig.offsetTop - 80, behavior: 'smooth' });
    }

    function populateSelect(selectEl, cols, suggestedVal, defaultText, allowEmpty = false) {
        selectEl.innerHTML = '';
        if (allowEmpty || !suggestedVal) {
            const optDefault = document.createElement('option');
            optDefault.value = '';
            optDefault.textContent = defaultText;
            selectEl.appendChild(optDefault);
        }

        cols.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.textContent = col;
            if (suggestedVal && col === suggestedVal) {
                opt.selected = true;
            }
            selectEl.appendChild(opt);
        });

        if (!allowEmpty && !suggestedVal && cols.length > 0) {
            selectEl.selectedIndex = 0;
        }
    }

    // Botões de Presets da Taxa Esperada (%)
    presetRateButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            presetRateButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const rate = btn.getAttribute('data-rate');
            if (rate) {
                inputExpectedRate.value = rate;
            }
        });
    });

    inputExpectedRate.addEventListener('input', () => {
        const val = parseFloat(inputExpectedRate.value);
        presetRateButtons.forEach(b => {
            const r = parseFloat(b.getAttribute('data-rate'));
            b.classList.toggle('active', Math.abs(r - val) < 0.01);
        });
    });

    btnBackStep1.addEventListener('click', () => {
        hideAlerts();
        stepConfig.style.display = 'none';
        stepUpload.style.display = 'block';
        window.scrollTo({ top: stepUpload.offsetTop - 80, behavior: 'smooth' });
    });

    // =========================================================================
    // 4. EXECUÇÃO DA CONCILIAÇÃO
    // =========================================================================

    btnProcess.addEventListener('click', async () => {
        hideAlerts();

        const colGross = selectColGross.value;
        if (!colGross) {
            processAlertMsg.textContent = 'Por favor, selecione qual coluna da planilha corresponde ao Valor Bruto da Venda.';
            processAlert.style.display = 'flex';
            selectColGross.focus();
            return;
        }

        const rateVal = parseFloat(inputExpectedRate.value);
        if (isNaN(rateVal) || rateVal < 0 || rateVal > 100) {
            processAlertMsg.textContent = 'Por favor, informe uma Taxa Esperada válida entre 0,00% e 100,00%.';
            processAlert.style.display = 'flex';
            inputExpectedRate.focus();
            return;
        }

        btnProcess.disabled = true;
        const spinner = btnProcess.querySelector('.spinner');
        const btnText = btnProcess.querySelector('.btn-text');
        if (spinner) spinner.style.display = 'inline-block';
        if (btnText) btnText.textContent = 'Auditando Taxas e Extrato...';

        try {
            const payload = {
                session_id: currentSessionId,
                col_id: selectColId.value || '',
                col_gross_val: colGross,
                col_date: selectColDate.value || '',
                col_acquirer: selectColAcquirer.value || '',
                expected_rate_pct: rateVal,
                tolerance_cents: parseFloat(selectTolerance.value) || 0.05,
                date_tolerance_days: parseInt(selectDateTol.value) || 3
            };

            const resp = await fetch('/api/ofx/reconcile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.error || 'Erro ao realizar conciliação.');
            }

            renderDashboard(data);
        } catch (err) {
            processAlertMsg.textContent = err.message;
            processAlert.style.display = 'flex';
        } finally {
            btnProcess.disabled = false;
            if (spinner) spinner.style.display = 'none';
            if (btnText) btnText.textContent = 'Conciliar Taxas e Extrato';
        }
    });

    // =========================================================================
    // 5. PASSO 3: RENDERIZAÇÃO DO DASHBOARD E RESULTADOS
    // =========================================================================

    function renderDashboard(data) {
        reconciliationData = data;
        currentReportId = data.report_id;
        const kpis = data.kpis;

        // Banners
        if (kpis.divergent_fees_count === 0 && kpis.unpaid_sales_count === 0) {
            bannerSuccess.style.display = 'flex';
            bannerDiffs.style.display = 'none';
        } else {
            bannerSuccess.style.display = 'none';
            bannerDiffs.style.display = 'flex';
            let msg = '';
            if (kpis.divergent_fees_count > 0 && kpis.unpaid_sales_count > 0) {
                msg = `Foram identificadas ${kpis.divergent_fees_count} vendas com taxa cobrada a maior (totalizando ${kpis.total_divergence_loss_fmt} em prejuízo a recuperar) e ${kpis.unpaid_sales_count} vendas registradas que não caíram no extrato bancário.`;
            } else if (kpis.divergent_fees_count > 0) {
                msg = `Foram identificadas ${kpis.divergent_fees_count} vendas com taxa superior à acordada. Prejuízo estimado para solicitação de estorno: ${kpis.total_divergence_loss_fmt}.`;
            } else {
                msg = `Identificadas ${kpis.unpaid_sales_count} vendas no PDV sem repasse correspondente no extrato bancário.`;
            }
            bannerDiffsMsg.textContent = msg;
        }

        // KPIs
        if (kpiReconciledPct) kpiReconciledPct.textContent = `${kpis.reconciled_pct}%`;
        if (kpiReconciledCount) kpiReconciledCount.textContent = `${kpis.reconciled_count} de ${kpis.total_sales_count} vendas`;
        if (kpiGrossVal) kpiGrossVal.textContent = kpis.total_gross_fmt;
        if (kpiSalesCount) kpiSalesCount.textContent = `${kpis.total_sales_count} vendas analisadas`;
        if (kpiCreditedVal) kpiCreditedVal.textContent = kpis.total_credited_ofx_fmt;
        if (kpiExpNetVal) kpiExpNetVal.textContent = `Líquido Esperado: ${kpis.total_expected_net_fmt}`;
        if (kpiLossVal) kpiLossVal.textContent = kpis.total_divergence_loss_fmt;
        if (kpiDivergentCount) kpiDivergentCount.textContent = `${kpis.divergent_fees_count} com taxa a maior`;
        if (kpiUnpaidCount) kpiUnpaidCount.textContent = `${kpis.unpaid_sales_count}`;
        if (kpiOrphanCount) kpiOrphanCount.textContent = `${kpis.orphan_credits_count}`;
        if (kpiOrphanSub) {
            kpiOrphanSub.textContent = kpis.orphan_credits_count > 0 ? `${kpis.total_orphan_amount_fmt} em créditos avulsos` : 'créditos sem venda no PDV';
        }

        // Links de download direto
        if (btnDownloadAudit) btnDownloadAudit.href = `/api/ofx/download-audit/${currentReportId}`;
        if (btnDownloadMirror) btnDownloadMirror.href = `/api/ofx/download-mirror/${currentReportId}`;

        // Badges das abas de filtro
        const items = data.items;
        const countAll = items.length;
        const countDivergent = items.filter(i => i.status === 'TAXA_A_MAIOR').length;
        const countReconciled = items.filter(i => i.status === 'CONCILIADO').length;
        const countUnpaid = items.filter(i => i.status === 'NAO_REPASSADO').length;
        const countOrphan = items.filter(i => i.status === 'CREDITO_SEM_VENDA').length;

        badgeAll.textContent = countAll;
        badgeDivergent.textContent = countDivergent;
        badgeReconciled.textContent = countReconciled;
        badgeUnpaid.textContent = countUnpaid;
        badgeOrphan.textContent = countOrphan;

        // Se houver divergências, abre direto na aba de divergências
        if (countDivergent > 0) {
            setFilterTab('TAXA_A_MAIOR');
        } else {
            setFilterTab('all');
        }

        // Transição de telas
        stepConfig.style.display = 'none';
        stepResults.style.display = 'block';

        window.scrollTo({ top: stepResults.offsetTop - 80, behavior: 'smooth' });
    }

    function setFilterTab(filter) {
        currentFilter = filter;
        currentPage = 1;
        filterTabs.forEach(tab => {
            tab.classList.toggle('active', tab.getAttribute('data-filter') === filter);
        });
        renderTable();
    }

    filterTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const f = tab.getAttribute('data-filter');
            setFilterTab(f);
        });
    });

    tableSearchInput.addEventListener('input', () => {
        searchQuery = tableSearchInput.value.toLowerCase().trim();
        currentPage = 1;
        renderTable();
    });

    btnPrevPage.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderTable();
        }
    });

    btnNextPage.addEventListener('click', () => {
        currentPage++;
        renderTable();
    });

    function renderTable() {
        if (!reconciliationData) return;
        const items = reconciliationData.items;

        // Filtro por Status
        let filtered = items;
        if (currentFilter !== 'all') {
            filtered = filtered.filter(i => i.status === currentFilter);
        }

        // Filtro de Busca
        if (searchQuery) {
            filtered = filtered.filter(i => {
                const s = `${i.sale_id} ${i.acquirer} ${i.gross_val_fmt} ${i.credited_ofx_fmt} ${i.sale_date_display} ${i.ofx_memo}`.toLowerCase();
                return s.includes(searchQuery);
            });
        }

        const totalFiltered = filtered.length;
        const totalPages = Math.ceil(totalFiltered / pageSize) || 1;
        if (currentPage > totalPages) currentPage = totalPages;
        if (currentPage < 1) currentPage = 1;

        const startIdx = (currentPage - 1) * pageSize;
        const pageItems = filtered.slice(startIdx, startIdx + pageSize);

        tbodyReconciliation.innerHTML = '';

        if (pageItems.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td colspan="12" style="text-align: center; padding: 32px; color: var(--text-muted);">Nenhum registro encontrado com os filtros atuais.</td>`;
            tbodyReconciliation.appendChild(tr);
        } else {
            pageItems.forEach(item => {
                const tr = document.createElement('tr');

                let badgeHtml = '';
                if (item.status === 'CONCILIADO') {
                    badgeHtml = `<span class="status-badge-ok">✔ Conciliado</span>`;
                } else if (item.status === 'TAXA_A_MAIOR') {
                    badgeHtml = `<span class="status-badge-diff">✘ Taxa a Maior</span>`;
                } else if (item.status === 'NAO_REPASSADO') {
                    badgeHtml = `<span class="status-badge-warning">⚠ Não Repassado</span>`;
                } else if (item.status === 'CREDITO_SEM_VENDA') {
                    badgeHtml = `<span class="status-badge-info">ℹ Crédito Avulso</span>`;
                } else {
                    badgeHtml = `<span class="status-badge-diff">${escapeHtml(item.status_label)}</span>`;
                }

                const diffClass = item.diff_val > 0.05 ? 'text-danger font-bold' : (item.diff_val < -0.05 ? 'text-info font-bold' : 'text-success font-bold');

                tr.innerHTML = `
                    <td style="text-align: center; white-space: nowrap;">${badgeHtml}</td>
                    <td style="text-align: center; white-space: nowrap;"><span class="key-code">${escapeHtml(item.sale_id)}</span></td>
                    <td style="white-space: nowrap;"><strong>${escapeHtml(item.acquirer)}</strong></td>
                    <td style="text-align: center; white-space: nowrap; font-family: 'JetBrains Mono', monospace; font-size: 12px;">${escapeHtml(item.sale_date_display)}</td>
                    <td style="text-align: center; white-space: nowrap; font-family: 'JetBrains Mono', monospace; font-size: 12px;">${escapeHtml(item.credit_date_display)}</td>
                    <td style="text-align: right; white-space: nowrap; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 600;">${escapeHtml(item.gross_val_fmt)}</td>
                    <td style="text-align: center; white-space: nowrap;"><span class="badge-pct">${escapeHtml(item.expected_rate_fmt)}</span></td>
                    <td style="text-align: right; white-space: nowrap; font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--text-muted);">${escapeHtml(item.expected_net_fmt)}</td>
                    <td style="text-align: right; white-space: nowrap; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;">${escapeHtml(item.credited_ofx_fmt)}</td>
                    <td style="text-align: center; white-space: nowrap;"><span class="badge-pct ${item.status === 'TAXA_A_MAIOR' ? 'pct-alert' : ''}">${escapeHtml(item.effective_rate_fmt)}</span></td>
                    <td style="text-align: right; white-space: nowrap; font-family: 'JetBrains Mono', monospace; font-size: 13px;" class="${diffClass}">${escapeHtml(item.diff_val_fmt)}</td>
                    <td style="font-size: 12.5px; color: var(--text-muted); line-height: 1.4; min-width: 250px;">${escapeHtml(item.recommendation)}</td>
                `;
                tbodyReconciliation.appendChild(tr);
            });
        }

        // Atualiza controles de paginação
        const startRecord = totalFiltered === 0 ? 0 : startIdx + 1;
        const endRecord = Math.min(startIdx + pageSize, totalFiltered);
        paginationInfo.textContent = `Mostrando ${startRecord} a ${endRecord} de ${totalFiltered} registros (Página ${currentPage} de ${totalPages})`;

        btnPrevPage.disabled = (currentPage <= 1);
        btnNextPage.disabled = (currentPage >= totalPages);
    }

    // =========================================================================
    // 6. DOWNLOADS DE RELATÓRIOS EXCEL
    // =========================================================================

    if (btnDownloadAudit) {
        btnDownloadAudit.addEventListener('click', (e) => {
            if (!currentReportId) {
                e.preventDefault();
                return;
            }
        });
    }

    if (btnDownloadMirror) {
        btnDownloadMirror.addEventListener('click', (e) => {
            if (!currentReportId) {
                e.preventDefault();
                return;
            }
        });
    }

    btnRestart.addEventListener('click', () => {
        hideAlerts();
        selectedOfxFiles = [];
        selectedSalesFile = null;
        currentSessionId = null;
        currentReportId = null;
        reconciliationData = null;

        fileMetaOfx.style.display = 'none';
        fileMetaSales.style.display = 'none';
        dropOfxFile.classList.remove('file-loaded');
        dropSalesSheet.classList.remove('file-loaded');
        btnUpload.disabled = true;

        stepResults.style.display = 'none';
        stepConfig.style.display = 'none';
        stepUpload.style.display = 'block';

        window.scrollTo({ top: stepUpload.offsetTop - 80, behavior: 'smooth' });
    });

})();

