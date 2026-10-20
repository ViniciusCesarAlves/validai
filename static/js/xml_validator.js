/**
 * ValidAí - Conciliador de XML de Notas Fiscais (NFe / NFSe / CTe)
 * Controlador Frontend Padronizado com o Design System da Plataforma
 */

(function () {
    let currentSessionId = null;
    let currentReportId = null;
    let selectedXmlFiles = [];
    let selectedSheetFile = null;

    // Elementos do DOM - Passo 1
    const stepUpload = document.getElementById('step-upload-xml');
    const dropXmlPack = document.getElementById('drop-xml-pack');
    const fileXmlPackInput = document.getElementById('file-xml-pack');
    const fileMetaXmlPack = document.getElementById('file-meta-xml-pack');
    const filenameXmlPack = document.getElementById('filename-xml-pack');
    const filesizeXmlPack = document.getElementById('filesize-xml-pack');

    const dropXmlSheet = document.getElementById('drop-xml-sheet');
    const fileXmlSheetInput = document.getElementById('file-xml-sheet');
    const fileMetaXmlSheet = document.getElementById('file-meta-xml-sheet');
    const filenameXmlSheet = document.getElementById('filename-xml-sheet');
    const filesizeXmlSheet = document.getElementById('filesize-xml-sheet');

    const btnTryExample = document.getElementById('btn-xml-try-example');
    const btnUpload = document.getElementById('btn-xml-upload');
    const uploadAlert = document.getElementById('xml-upload-alert');
    const uploadAlertMsg = document.getElementById('xml-upload-alert-msg');
    const btnCloseUploadAlert = document.getElementById('btn-close-upload-alert');

    // Elementos do DOM - Passo 2
    const stepConfig = document.getElementById('step-config-xml');
    const infoPackName = document.getElementById('info-xml-pack-name');
    const infoCountBadge = document.getElementById('info-xml-count-badge');
    const infoTotalVal = document.getElementById('info-xml-total-val');
    const infoSheetName = document.getElementById('info-xml-sheet-name');
    const infoSheetRows = document.getElementById('info-xml-sheet-rows');

    const selectColNf = document.getElementById('select-xml-col-nf');
    const selectColVal = document.getElementById('select-xml-col-val');
    const selectColCnpj = document.getElementById('select-xml-col-cnpj');
    const selectColTax = document.getElementById('select-xml-col-tax');
    const selectColFornecedor = document.getElementById('select-xml-col-fornecedor');

    const checkMissingExcel = document.getElementById('check-xml-missing-excel');
    const checkMissingFile = document.getElementById('check-xml-missing-file');
    const checkTaxes = document.getElementById('check-xml-taxes');
    const checkLeadingZeros = document.getElementById('check-xml-leading-zeros');
    const checkCnpjPunct = document.getElementById('check-xml-cnpj-punct');

    const processAlert = document.getElementById('xml-process-alert');
    const processAlertTitle = document.getElementById('xml-process-alert-title');
    const processAlertMsg = document.getElementById('xml-process-alert-msg');
    const btnCloseProcessAlert = document.getElementById('btn-close-xml-process-alert');

    const btnBackStep1 = document.getElementById('btn-xml-back-step1');
    const btnProcess = document.getElementById('btn-process-xml');

    // Elementos do DOM - Passo 3
    const stepResults = document.getElementById('step-results-xml');
    const bannerSuccess = document.getElementById('xml-banner-success');
    const bannerDiffs = document.getElementById('xml-banner-diffs');

    const kpiTotalXml = document.getElementById('xml-kpi-total-xml');
    const kpiTotalXmlVal = document.getElementById('xml-kpi-total-xml-val');
    const kpiMatched = document.getElementById('xml-kpi-matched');
    const kpiMatchedPct = document.getElementById('xml-kpi-matched-pct');
    const kpiDivergences = document.getElementById('xml-kpi-divergences');
    const kpiMissingExcel = document.getElementById('xml-kpi-missing-excel');
    const kpiMissingXml = document.getElementById('xml-kpi-missing-xml');
    const kpiNetDiff = document.getElementById('xml-kpi-net-diff');
    const kpiSheetTotal = document.getElementById('xml-kpi-sheet-total');

    const btnDownloadAudit = document.getElementById('btn-xml-download-audit');
    const btnDownloadMirror = document.getElementById('btn-xml-download-mirror');

    const badgeDivs = document.getElementById('badge-xml-divs');
    const badgeMissingExcel = document.getElementById('badge-xml-missing-excel');
    const badgeMissingFile = document.getElementById('badge-xml-missing-file');
    const badgeMirror = document.getElementById('badge-xml-mirror');

    const tbodyDivs = document.getElementById('tbody-xml-divs');
    const tbodyMissingExcel = document.getElementById('tbody-xml-missing-excel');
    const tbodyMissingFile = document.getElementById('tbody-xml-missing-file');
    const tbodyMirror = document.getElementById('tbody-xml-mirror');

    const btnRestart = document.getElementById('btn-restart-xml');

    // Tema gerenciado centralmente por header.html

    // =========================================================================
    // PASSO 1: UPLOAD DE ARQUIVOS (.ZIP / .XML E PLANILHA FINANCEIRA)
    // =========================================================================

    function showUploadError(msg) {
        if (!uploadAlert || !uploadAlertMsg) return;
        uploadAlertMsg.textContent = msg;
        uploadAlert.style.display = 'flex';
    }

    function clearUploadError() {
        if (uploadAlert) uploadAlert.style.display = 'none';
    }

    if (btnCloseUploadAlert) {
        btnCloseUploadAlert.addEventListener('click', clearUploadError);
    }

    function checkReadyToUpload() {
        if (btnUpload) {
            btnUpload.disabled = !(selectedXmlFiles.length > 0 && selectedSheetFile !== null);
        }
    }

    // Dropzone 1: Pacote XML (.zip ou .xml)
    if (dropXmlPack && fileXmlPackInput) {
        dropXmlPack.addEventListener('click', (e) => {
            if (e.target !== fileXmlPackInput) {
                fileXmlPackInput.click();
            }
        });

        ['dragenter', 'dragover'].forEach(ev => {
            dropXmlPack.addEventListener(ev, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropXmlPack.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(ev => {
            dropXmlPack.addEventListener(ev, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropXmlPack.classList.remove('drag-over');
            });
        });

        dropXmlPack.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                handleXmlPackSelected(Array.from(files));
            }
        });

        fileXmlPackInput.addEventListener('change', () => {
            if (fileXmlPackInput.files && fileXmlPackInput.files.length > 0) {
                handleXmlPackSelected(Array.from(fileXmlPackInput.files));
            }
        });
    }

    function handleXmlPackSelected(files) {
        clearUploadError();
        const valid = files.filter(f => {
            const n = f.name.toLowerCase();
            return n.endsWith('.zip') || n.endsWith('.xml');
        });

        if (valid.length === 0) {
            showUploadError('Formato inválido no Lado A. Envie um arquivo .zip contendo os XMLs ou selecione arquivos .xml diretamente.');
            return;
        }

        selectedXmlFiles = valid;
        const totalSizeKB = (valid.reduce((acc, f) => acc + f.size, 0) / 1024).toFixed(1);

        if (filenameXmlPack) {
            filenameXmlPack.textContent = valid.length === 1 ? valid[0].name : `${valid.length} arquivos XML selecionados`;
        }
        if (filesizeXmlPack) {
            filesizeXmlPack.textContent = `${totalSizeKB} KB`;
        }
        if (fileMetaXmlPack) fileMetaXmlPack.style.display = 'inline-flex';
        dropXmlPack.classList.add('file-loaded');
        checkReadyToUpload();
    }

    // Dropzone 2: Planilha Financeira
    if (dropXmlSheet && fileXmlSheetInput) {
        dropXmlSheet.addEventListener('click', (e) => {
            if (e.target !== fileXmlSheetInput) {
                fileXmlSheetInput.click();
            }
        });

        ['dragenter', 'dragover'].forEach(ev => {
            dropXmlSheet.addEventListener(ev, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropXmlSheet.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(ev => {
            dropXmlSheet.addEventListener(ev, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropXmlSheet.classList.remove('drag-over');
            });
        });

        dropXmlSheet.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                handleSheetSelected(files[0]);
            }
        });

        fileXmlSheetInput.addEventListener('change', () => {
            if (fileXmlSheetInput.files && fileXmlSheetInput.files.length > 0) {
                handleSheetSelected(fileXmlSheetInput.files[0]);
            }
        });
    }

    function handleSheetSelected(file) {
        clearUploadError();
        const name = file.name.toLowerCase();
        const isValid = ['.xlsx', '.xls', '.csv'].some(ext => name.endsWith(ext));

        if (!isValid) {
            showUploadError('Formato inválido na Planilha. Envie um arquivo .xlsx, .xls ou .csv.');
            return;
        }

        selectedSheetFile = file;
        if (filenameXmlSheet) filenameXmlSheet.textContent = file.name;
        if (filesizeXmlSheet) filesizeXmlSheet.textContent = (file.size / 1024).toFixed(1) + ' KB';
        if (fileMetaXmlSheet) fileMetaXmlSheet.style.display = 'inline-flex';
        dropXmlSheet.classList.add('file-loaded');
        checkReadyToUpload();
    }

    // Popular tela de configuração (Passo 2) após leitura de arquivos ou exemplo
    function applyUploadResponseToStep2(data) {
        currentSessionId = data.session_id;

        if (infoPackName) infoPackName.textContent = data.package_label;
        if (infoCountBadge) infoCountBadge.textContent = `${data.xml_count} XMLs`;
        if (infoTotalVal) infoTotalVal.textContent = data.xml_total_value_fmt;
        if (infoSheetName) infoSheetName.textContent = data.sheet_filename;
        if (infoSheetRows) infoSheetRows.textContent = `(${data.sheet_rows} linhas)`;

        populateSelect(selectColNf, data.cols, data.suggested.col_nf, '-- Selecione a coluna do Nº da NF --');
        populateSelect(selectColVal, data.cols, data.suggested.col_val, '-- Selecione a coluna de Valor --');
        populateSelect(selectColCnpj, data.cols, data.suggested.col_cnpj, '-- Não mapear este campo --');
        populateSelect(selectColTax, data.cols, data.suggested.col_tax, '-- Não mapear este campo --');
        populateSelect(selectColFornecedor, data.cols, data.suggested.col_fornecedor, '-- Não mapear (Usar <xNome> do XML) --');

        clearProcessError();
        stepUpload.style.display = 'none';
        stepResults.style.display = 'none';
        stepConfig.style.display = 'block';
        window.scrollTo({ top: stepConfig.offsetTop - 80, behavior: 'smooth' });
    }

    function populateSelect(selectEl, cols, suggestedVal, placeholder) {
        if (!selectEl) return;
        selectEl.innerHTML = `<option value="">${placeholder}</option>`;
        cols.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.textContent = col;
            if (suggestedVal && col === suggestedVal) {
                opt.selected = true;
            }
            selectEl.appendChild(opt);
        });
    }

    // Enviar arquivos reais
    if (btnUpload) {
        btnUpload.addEventListener('click', async () => {
            if (selectedXmlFiles.length === 0 || !selectedSheetFile) return;
            clearUploadError();

            const formData = new FormData();
            selectedXmlFiles.forEach(f => formData.append('xml_files', f));
            formData.append('sheet_file', selectedSheetFile);

            const btnText = btnUpload.querySelector('.btn-text');
            const spinner = btnUpload.querySelector('.spinner');
            const icon = btnUpload.querySelector('.btn-circle-icon');

            btnUpload.disabled = true;
            if (btnText) btnText.textContent = 'Extraindo XMLs e Colunas...';
            if (spinner) spinner.style.display = 'inline-block';
            if (icon) icon.style.display = 'none';

            try {
                const res = await fetch('/api/xml/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();

                if (!res.ok || data.error) {
                    showUploadError(data.error || 'Falha ao ler arquivos.');
                    return;
                }

                applyUploadResponseToStep2(data);
            } catch (err) {
                showUploadError('Erro de comunicação com o servidor. Tente novamente.');
            } finally {
                checkReadyToUpload();
                if (btnText) btnText.textContent = 'Ler XMLs e Mapear Planilha';
                if (spinner) spinner.style.display = 'none';
                if (icon) icon.style.display = 'inline-flex';
            }
        });
    }

    // Botão Testar Exemplo
    if (btnTryExample) {
        btnTryExample.addEventListener('click', async () => {
            clearUploadError();
            const origHtml = btnTryExample.innerHTML;
            btnTryExample.disabled = true;
            btnTryExample.innerHTML = '<span class="btn-text">Carregando Lote de Exemplo...</span>';

            try {
                const res = await fetch('/api/xml/load-example', {
                    method: 'POST'
                });
                const data = await res.json();

                if (!res.ok || data.error) {
                    showUploadError(data.error || 'Não foi possível carregar o lote de exemplo.');
                    return;
                }

                applyUploadResponseToStep2(data);
            } catch (err) {
                showUploadError('Falha ao carregar exemplo de demonstração.');
            } finally {
                btnTryExample.disabled = false;
                btnTryExample.innerHTML = origHtml;
            }
        });
    }

    // =========================================================================
    // PASSO 2: CONFIGURAÇÃO E EXECUÇÃO DA CONCILIAÇÃO FISCAL
    // =========================================================================

    function showProcessError(msg, title = 'Coluna Incompatível com a Referência Fiscal') {
        if (!processAlert || !processAlertMsg) return;
        if (processAlertTitle) processAlertTitle.textContent = title;
        processAlertMsg.textContent = msg;
        processAlert.style.display = 'flex';
        processAlert.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function clearProcessError() {
        if (processAlert) processAlert.style.display = 'none';
    }

    if (btnCloseProcessAlert) {
        btnCloseProcessAlert.addEventListener('click', clearProcessError);
    }

    [selectColNf, selectColVal, selectColCnpj, selectColTax, selectColFornecedor].forEach(sel => {
        if (sel) sel.addEventListener('change', clearProcessError);
    });

    if (btnBackStep1) {
        btnBackStep1.addEventListener('click', () => {
            stepConfig.style.display = 'none';
            stepResults.style.display = 'none';
            stepUpload.style.display = 'block';
            window.scrollTo({ top: stepUpload.offsetTop - 80, behavior: 'smooth' });
        });
    }

    if (btnProcess) {
        btnProcess.addEventListener('click', async () => {
            clearProcessError();

            const colNf = selectColNf ? selectColNf.value : '';
            const colVal = selectColVal ? selectColVal.value : '';

            if (!colNf) {
                showProcessError(
                    'A coluna de Número da Nota Fiscal (<nNF>) é obrigatória para cruzar os arquivos XML com a planilha.',
                    'Mapeamento Obrigatório Pendente'
                );
                return;
            }

            if (!colVal) {
                showProcessError(
                    'A coluna de Valor Total da Nota (<vNF>) é obrigatória para conferir os valores lançados no financeiro.',
                    'Mapeamento Obrigatório Pendente'
                );
                return;
            }

            const tolRadio = document.querySelector('input[name="xml-tolerance-radio"]:checked');
            const tolerance = tolRadio ? parseFloat(tolRadio.value) : 0.05;

            const payload = {
                session_id: currentSessionId,
                col_nf: colNf,
                col_val: colVal,
                col_cnpj: selectColCnpj ? selectColCnpj.value : '',
                col_tax: selectColTax ? selectColTax.value : '',
                col_fornecedor: selectColFornecedor ? selectColFornecedor.value : '',
                tolerance: tolerance,
                ignore_leading_zeros: checkLeadingZeros ? checkLeadingZeros.checked : true,
                ignore_cnpj_punct: checkCnpjPunct ? checkCnpjPunct.checked : true,
                check_missing_in_excel: checkMissingExcel ? checkMissingExcel.checked : true,
                check_missing_xml: checkMissingFile ? checkMissingFile.checked : true,
                check_taxes: checkTaxes ? checkTaxes.checked : true
            };

            const btnText = btnProcess.querySelector('.btn-text');
            const spinner = btnProcess.querySelector('.spinner');
            const icon = btnProcess.querySelector('.btn-circle-icon');

            btnProcess.disabled = true;
            if (btnText) btnText.textContent = 'Cruzando XMLs vs. Planilha...';
            if (spinner) spinner.style.display = 'inline-block';
            if (icon) icon.style.display = 'none';

            try {
                const res = await fetch('/api/xml/reconcile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (!res.ok || data.error) {
                    showProcessError(
                        data.error || 'Ocorreu um erro durante a conciliação.',
                        data.title || 'Coluna Incompatível com a Referência Fiscal'
                    );
                    return;
                }

                currentReportId = data.report_id;
                renderResults(data);

                stepConfig.style.display = 'none';
                stepResults.style.display = 'block';
                window.scrollTo({ top: stepResults.offsetTop - 80, behavior: 'smooth' });

            } catch (err) {
                showProcessError('Erro de conexão ao processar conciliação fiscal. Tente novamente.');
            } finally {
                btnProcess.disabled = false;
                if (btnText) btnText.textContent = 'Executar Conciliação Fiscal';
                if (spinner) spinner.style.display = 'none';
                if (icon) icon.style.display = 'inline-flex';
            }
        });
    }

    // =========================================================================
    // PASSO 3: RENDERIZAÇÃO DO DASHBOARD, KPIS E TABELAS DE AUDITORIA
    // =========================================================================

    function renderResults(data) {
        const s = data.summary;

        // KPIs
        if (kpiTotalXml) kpiTotalXml.textContent = s.total_xmls;
        if (kpiTotalXmlVal) kpiTotalXmlVal.textContent = `Soma XMLs: ${s.total_xml_value_fmt}`;
        if (kpiMatched) kpiMatched.textContent = s.matched_count;
        if (kpiMatchedPct) kpiMatchedPct.textContent = `${s.matched_percentage}% de conformidade`;
        if (kpiDivergences) kpiDivergences.textContent = s.divergences_count;
        if (kpiMissingExcel) kpiMissingExcel.textContent = s.missing_in_excel_count;
        if (kpiMissingXml) kpiMissingXml.textContent = s.missing_xml_count;
        if (kpiNetDiff) kpiNetDiff.textContent = s.net_difference_fmt;
        if (kpiSheetTotal) kpiSheetTotal.textContent = `Planilha: ${s.total_sheet_value_fmt}`;

        const totalIssues = s.divergences_count + s.missing_in_excel_count + s.missing_xml_count;
        if (totalIssues === 0) {
            if (bannerSuccess) bannerSuccess.style.display = 'flex';
            if (bannerDiffs) bannerDiffs.style.display = 'none';
        } else {
            if (bannerSuccess) bannerSuccess.style.display = 'none';
            if (bannerDiffs) bannerDiffs.style.display = 'flex';
        }

        // Links de Download
        if (btnDownloadAudit) btnDownloadAudit.href = `/api/xml/download-audit/${currentReportId}`;
        if (btnDownloadMirror) btnDownloadMirror.href = `/api/xml/download-mirror/${currentReportId}`;

        // Badges das Abas
        if (badgeDivs) badgeDivs.textContent = data.divergences.length;
        if (badgeMissingExcel) badgeMissingExcel.textContent = data.missing_in_excel.length;
        if (badgeMissingFile) badgeMissingFile.textContent = data.missing_xml.length;
        if (badgeMirror) badgeMirror.textContent = data.all_xml_mirror.length;

        renderTableDivergences(data.divergences);
        renderTableMissingExcel(data.missing_in_excel);
        renderTableMissingFile(data.missing_xml);
        renderTableMirror(data.all_xml_mirror);

        // Ativa a primeira aba relevante
        if (data.divergences.length > 0) {
            activateTab('tab-xml-divs');
        } else if (data.missing_in_excel.length > 0) {
            activateTab('tab-xml-missing-excel');
        } else if (data.missing_xml.length > 0) {
            activateTab('tab-xml-missing-file');
        } else {
            activateTab('tab-xml-mirror');
        }
    }

    function renderTableDivergences(items) {
        if (!tbodyDivs) return;
        tbodyDivs.innerHTML = '';

        if (!items || items.length === 0) {
            tbodyDivs.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 28px; color: var(--text-muted); font-weight: 600;">✅ Nenhuma divergência de valor, imposto ou CNPJ encontrada nas notas conciliadas!</td></tr>';
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="text-align: center;"><span class="badge-line">${escapeHtml(item.excel_line)}</span></td>
                <td><span class="key-code">NF ${escapeHtml(item.nNF)}</span></td>
                <td>
                    <strong>${escapeHtml(item.emit_nome)}</strong>
                    <div style="font-size: 11px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; margin-top: 2px;">CNPJ XML: ${escapeHtml(item.emit_cnpj_xml)}</div>
                </td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; color: #16a34a; white-space: nowrap;">${escapeHtml(item.vNF_xml_fmt)}</td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; color: #dc2626; white-space: nowrap;">${escapeHtml(item.val_planilha_fmt)}</td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; white-space: nowrap;"><span class="tag-pill tag-error" style="font-weight: 700;">${escapeHtml(item.diff_val_fmt)}</span></td>
                <td><span style="color: #dc2626; font-weight: 600; font-size: 12.5px;">${escapeHtml(item.motivo)}</span></td>
            `;
            tbodyDivs.appendChild(tr);
        });
    }

    function renderTableMissingExcel(items) {
        if (!tbodyMissingExcel) return;
        tbodyMissingExcel.innerHTML = '';

        if (!items || items.length === 0) {
            tbodyMissingExcel.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 28px; color: var(--text-muted); font-weight: 600;">✅ Todos os XMLs da pasta foram devidamente localizados na planilha financeira!</td></tr>';
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span class="status-badge status-badge-info">${escapeHtml(item.tipo_doc)}</span></td>
                <td><span class="key-code" style="color: #d97706; border-color: rgba(245, 158, 11, 0.4);">NF ${escapeHtml(item.nNF)}</span></td>
                <td style="white-space: nowrap;">${escapeHtml(item.data_emissao)}</td>
                <td><span class="key-code">${escapeHtml(item.emit_cnpj)}</span></td>
                <td><strong>${escapeHtml(item.emit_nome)}</strong></td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; color: #d97706; white-space: nowrap;">${escapeHtml(item.vNF_fmt)}</td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 13px; white-space: nowrap;">${escapeHtml(item.total_impostos_fmt)}</td>
                <td style="font-size: 12px; color: var(--text-muted);">${escapeHtml(item.filename)}</td>
            `;
            tbodyMissingExcel.appendChild(tr);
        });
    }

    function renderTableMissingFile(items) {
        if (!tbodyMissingFile) return;
        tbodyMissingFile.innerHTML = '';

        if (!items || items.length === 0) {
            tbodyMissingFile.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 28px; color: var(--text-muted); font-weight: 600;">✅ Todos os lançamentos da planilha possuem arquivo .XML correspondente!</td></tr>';
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="text-align: center;"><span class="badge-line">${escapeHtml(item.excel_line)}</span></td>
                <td><span class="key-code" style="color: #ea580c; border-color: rgba(234, 88, 12, 0.4);">NF ${escapeHtml(item.nNF_planilha)}</span></td>
                <td><strong>${escapeHtml(item.fornecedor)}</strong></td>
                <td><span class="key-code">${escapeHtml(item.cnpj_planilha)}</span></td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; white-space: nowrap;">${escapeHtml(item.val_planilha_fmt)}</td>
                <td><span style="color: #ea580c; font-weight: 600; font-size: 12.5px;">${escapeHtml(item.motivo)}</span></td>
            `;
            tbodyMissingFile.appendChild(tr);
        });
    }

    function renderTableMirror(items) {
        if (!tbodyMirror) return;
        tbodyMirror.innerHTML = '';

        if (!items || items.length === 0) {
            tbodyMirror.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 28px; color: var(--text-muted);">Nenhum XML processado.</td></tr>';
            return;
        }

        items.forEach(item => {
            const st = item.status_conciliacao || '';
            let statusBadge = `<span class="status-badge status-badge-ok">${escapeHtml(st)}</span>`;
            if (st.includes('DIVERGÊNCIA')) {
                statusBadge = `<span class="status-badge status-badge-diff">${escapeHtml(st)}</span>`;
            } else if (st.includes('SEM LANÇAMENTO') || st.includes('NÃO ENCONTRADO')) {
                statusBadge = `<span class="status-badge status-badge-warning">${escapeHtml(st)}</span>`;
            }

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${statusBadge}</td>
                <td><strong>${escapeHtml(item.tipo_doc)}</strong></td>
                <td><span class="key-code">NF ${escapeHtml(item.nNF)}</span></td>
                <td style="white-space: nowrap;">${escapeHtml(item.data_emissao)}</td>
                <td><span class="key-code">${escapeHtml(item.emit_cnpj_fmt || item.emit_cnpj)}</span></td>
                <td><strong>${escapeHtml(item.emit_nome)}</strong></td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; white-space: nowrap;">${escapeHtml(item.vNF_fmt)}</td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 13px; white-space: nowrap;">${escapeHtml(item.total_impostos_fmt)}</td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted);">${escapeHtml(item.chave_acesso)}</td>
            `;
            tbodyMirror.appendChild(tr);
        });
    }

    function activateTab(tabId) {
        document.querySelectorAll('#xml-results-tabs .result-nav-tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
        });

        ['tab-xml-divs', 'tab-xml-missing-excel', 'tab-xml-missing-file', 'tab-xml-mirror'].forEach(t => {
            const pane = document.getElementById(`pane-${t}`);
            if (pane) pane.style.display = t === tabId ? 'block' : 'none';
        });
    }

    document.querySelectorAll('#xml-results-tabs .result-nav-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            activateTab(btn.getAttribute('data-tab'));
        });
    });

    if (btnRestart) {
        btnRestart.addEventListener('click', () => {
            selectedXmlFiles = [];
            selectedSheetFile = null;
            if (fileXmlPackInput) fileXmlPackInput.value = '';
            if (fileXmlSheetInput) fileXmlSheetInput.value = '';
            if (fileMetaXmlPack) fileMetaXmlPack.style.display = 'none';
            if (fileMetaXmlSheet) fileMetaXmlSheet.style.display = 'none';
            if (dropXmlPack) dropXmlPack.classList.remove('file-loaded');
            if (dropXmlSheet) dropXmlSheet.classList.remove('file-loaded');
            if (btnUpload) btnUpload.disabled = true;

            stepResults.style.display = 'none';
            stepConfig.style.display = 'none';
            stepUpload.style.display = 'block';
            currentSessionId = null;
            currentReportId = null;

            window.scrollTo({ top: stepUpload.offsetTop - 80, behavior: 'smooth' });
        });
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
})();

