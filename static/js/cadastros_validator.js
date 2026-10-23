/**
 * ValidAí - Higienizador e Auditor de Cadastros
 * Controlador Frontend Padronizado com o Design System da Plataforma
 */

(function () {
    let currentSessionId = null;
    let currentReportId = null;
    let cadastrosData = null;

    // Elementos do DOM - Passo 1
    const stepUpload = document.getElementById('step-upload-cadastros');
    const dropZone = document.getElementById('drop-cadastros');
    const fileInput = document.getElementById('cadastros-file-input');
    const fileMeta = document.getElementById('cadastros-file-meta');
    const filenameDisplay = document.getElementById('cadastros-filename-display');
    const filesizeDisplay = document.getElementById('cadastros-filesize-display');
    const btnRead = document.getElementById('btn-read-cadastros');
    const btnTryExample = document.getElementById('btn-cadastros-try-example');
    const uploadAlert = document.getElementById('cadastros-upload-alert');
    const uploadAlertMsg = document.getElementById('cadastros-upload-alert-msg');

    // Elementos do DOM - Passo 2
    const stepConfig = document.getElementById('step-config-cadastros');
    const infoFilename = document.getElementById('info-cadastros-filename');
    const infoRows = document.getElementById('info-cadastros-rows');
    const infoCols = document.getElementById('info-cadastros-cols');
    const selectColDoc = document.getElementById('select-col-doc');
    const selectColName = document.getElementById('select-col-name');
    const selectColEmail = document.getElementById('select-col-email');
    const selectColPhone = document.getElementById('select-col-phone');
    const checkDupDoc = document.getElementById('check-dup-doc');
    const checkDupEmail = document.getElementById('check-dup-email');
    const checkDupPhone = document.getElementById('check-dup-phone');
    const checkAutoZeros = document.getElementById('check-auto-zeros');
    const checkNameTitleCase = document.getElementById('check-name-title-case');
    const checkEmailLowercase = document.getElementById('check-email-lowercase');
    const checkRemoveDuplicates = document.getElementById('check-remove-duplicates');
    const btnBackStep1 = document.getElementById('btn-back-step1');
    const btnProcess = document.getElementById('btn-process-cadastros');
    const processAlert = document.getElementById('cadastros-process-alert');
    const processAlertTitle = document.getElementById('cadastros-process-alert-title');
    const processAlertMsg = document.getElementById('cadastros-process-alert-msg');
    const btnCloseProcessAlert = document.getElementById('btn-close-process-alert');

    // Elementos do DOM - Passo 3
    const stepResults = document.getElementById('step-results-cadastros');
    const bannerSuccess = document.getElementById('cadastros-banner-success');
    const bannerDiffs = document.getElementById('cadastros-banner-diffs');
    const kpiTotalRows = document.getElementById('kpi-total-rows');
    const kpiValidRows = document.getElementById('kpi-valid-rows');
    const kpiValidPercent = document.getElementById('kpi-valid-percent');
    const kpiInvalidDocs = document.getElementById('kpi-invalid-docs');
    const kpiDuplicateRows = document.getElementById('kpi-duplicate-rows');
    const kpiSuspiciousContacts = document.getElementById('kpi-suspicious-contacts');
    const kpiAutoCorrections = document.getElementById('kpi-auto-corrections');
    const btnDownloadClean = document.getElementById('btn-download-clean');
    const btnDownloadAudit = document.getElementById('btn-download-audit');
    const badgeTabDocs = document.getElementById('badge-tab-docs');
    const badgeTabDups = document.getElementById('badge-tab-dups');
    const badgeTabContacts = document.getElementById('badge-tab-contacts');
    const tbodyDocs = document.getElementById('tbody-docs');
    const tbodyDups = document.getElementById('tbody-dups');
    const tbodyContacts = document.getElementById('tbody-contacts');
    const theadPreview = document.getElementById('thead-preview');
    const tbodyPreview = document.getElementById('tbody-preview');
    const btnRestart = document.getElementById('btn-restart-cadastros');

    // Tema gerenciado centralmente por header.html

    // =========================================================================
    // PASSO 1: SELEÇÃO E DRAG & DROP DO ARQUIVO
    // =========================================================================

    function showUploadError(msg) {
        if (!uploadAlert || !uploadAlertMsg) return;
        uploadAlertMsg.textContent = msg;
        uploadAlert.style.display = 'flex';
    }

    function clearUploadError() {
        if (uploadAlert) uploadAlert.style.display = 'none';
    }

    if (dropZone && fileInput) {
        dropZone.addEventListener('click', (e) => {
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('drag-over');
            });
        });

        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                fileInput.files = files;
                handleFileSelected(files[0]);
            }
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files && fileInput.files.length > 0) {
                handleFileSelected(fileInput.files[0]);
            }
        });
    }

    function handleFileSelected(file) {
        clearUploadError();
        const validExtensions = ['.xlsx', '.xls', '.csv'];
        const name = file.name.toLowerCase();
        const isValid = validExtensions.some(ext => name.endsWith(ext));

        if (!isValid) {
            showUploadError('Formato de arquivo inválido. Por favor, envie uma planilha .xlsx, .xls ou .csv.');
            btnRead.disabled = true;
            return;
        }

        if (filenameDisplay) filenameDisplay.textContent = file.name;
        if (filesizeDisplay) filesizeDisplay.textContent = (file.size / 1024).toFixed(1) + ' KB';
        if (fileMeta) fileMeta.style.display = 'inline-flex';
        dropZone.classList.add('file-loaded');
        btnRead.disabled = false;
    }

    // Testar Exemplo de Base Cadastral
    if (btnTryExample) {
        btnTryExample.addEventListener('click', async () => {
            clearUploadError();
            btnTryExample.disabled = true;
            const originalHtml = btnTryExample.innerHTML;
            btnTryExample.innerHTML = '<span class="spinner" style="display: inline-block;"></span> Carregando Exemplo...';

            try {
                const res = await fetch('/api/cadastros/load-example', {
                    method: 'POST'
                });
                const data = await res.json();

                if (!res.ok || data.error) {
                    showUploadError(data.error || 'Falha ao carregar base cadastral de exemplo.');
                    return;
                }

                currentSessionId = data.session_id;
                window.cadastrosSampleData = data.sample_data || [];

                // Atualiza dropzone visual com o arquivo de exemplo
                if (filenameDisplay) filenameDisplay.textContent = data.filename || 'Base_Clientes_Para_Higienizar.xlsx';
                if (filesizeDisplay) filesizeDisplay.textContent = '12.8 KB';
                if (fileMeta) fileMeta.style.display = 'inline-flex';
                if (dropZone) dropZone.classList.add('file-loaded');
                if (btnRead) btnRead.disabled = false;

                // Preenche resumo do Passo 2
                infoFilename.textContent = data.filename;
                infoRows.textContent = `${Number(data.total_rows).toLocaleString('pt-BR')} linhas`;
                infoCols.textContent = `${data.total_cols} colunas`;

                // Popula selects de mapeamento
                populateSelect(selectColDoc, data.cols, data.suggested.col_doc);
                populateSelect(selectColName, data.cols, data.suggested.col_name);
                populateSelect(selectColEmail, data.cols, data.suggested.col_email);
                populateSelect(selectColPhone, data.cols, data.suggested.col_phone);

                // Alterna para Passo 2 com rolagem suave
                stepUpload.style.display = 'none';
                stepConfig.style.display = 'block';
                window.scrollTo({ top: stepConfig.offsetTop - 80, behavior: 'smooth' });

            } catch (err) {
                showUploadError('Erro de conexão ao carregar exemplo de cadastros.');
            } finally {
                btnTryExample.disabled = false;
                btnTryExample.innerHTML = originalHtml;
            }
        });
    }

    // Leitura inicial de cabeçalhos
    if (btnRead) {
        btnRead.addEventListener('click', async () => {
            if (!fileInput.files || fileInput.files.length === 0) return;
            clearUploadError();

            const file = fileInput.files[0];
            const formData = new FormData();
            formData.append('file', file);

            const btnText = btnRead.querySelector('.btn-text');
            const spinner = btnRead.querySelector('.spinner');
            const icon = btnRead.querySelector('.btn-circle-icon');

            btnRead.disabled = true;
            if (btnText) btnText.textContent = 'Lendo colunas...';
            if (spinner) spinner.style.display = 'inline-block';
            if (icon) icon.style.display = 'none';

            try {
                const res = await fetch('/api/cadastros/upload-headers', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();

                if (!res.ok || data.error) {
                    showUploadError(data.error || 'Falha ao processar arquivo.');
                    return;
                }

                currentSessionId = data.session_id;
                window.cadastrosSampleData = data.sample_data || [];

                // Preenche resumo
                infoFilename.textContent = data.filename;
                infoRows.textContent = `${Number(data.total_rows).toLocaleString('pt-BR')} linhas`;
                infoCols.textContent = `${data.total_cols} colunas`;

                // Popula selects de mapeamento
                populateSelect(selectColDoc, data.cols, data.suggested.col_doc);
                populateSelect(selectColName, data.cols, data.suggested.col_name);
                populateSelect(selectColEmail, data.cols, data.suggested.col_email);
                populateSelect(selectColPhone, data.cols, data.suggested.col_phone);

                // Alterna para Passo 2
                stepUpload.style.display = 'none';
                stepConfig.style.display = 'block';
                window.scrollTo({ top: stepConfig.offsetTop - 80, behavior: 'smooth' });

            } catch (err) {
                showUploadError('Erro de conexão ao carregar arquivo. Verifique sua rede e tente novamente.');
            } finally {
                btnRead.disabled = false;
                if (btnText) btnText.textContent = 'Ler Cabeçalhos e Continuar';
                if (spinner) spinner.style.display = 'none';
                if (icon) icon.style.display = 'inline-flex';
            }
        });
    }

    function populateSelect(selectEl, cols, suggestedVal) {
        if (!selectEl) return;
        selectEl.innerHTML = '<option value="">-- Não mapear este campo --</option>';
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

    // Botão Voltar ao Passo 1
    if (btnBackStep1) {
        btnBackStep1.addEventListener('click', () => {
            stepConfig.style.display = 'none';
            stepUpload.style.display = 'block';
            window.scrollTo({ top: stepUpload.offsetTop - 80, behavior: 'smooth' });
        });
    }

    // =========================================================================
    // PASSO 2: EXECUÇÃO DA HIGIENIZAÇÃO E AUDITORIA
    // =========================================================================

    function showProcessError(msg, title = 'Inconsistência no Mapeamento de Colunas') {
        if (!processAlert || !processAlertMsg) return;
        if (processAlertTitle) processAlertTitle.textContent = title;
        processAlertMsg.innerHTML = msg;
        processAlert.style.display = 'flex';
        processAlert.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function clearProcessError() {
        if (processAlert) processAlert.style.display = 'none';
        if (selectColDoc) selectColDoc.style.borderColor = '';
        if (selectColEmail) selectColEmail.style.borderColor = '';
    }

    if (btnCloseProcessAlert) {
        btnCloseProcessAlert.addEventListener('click', () => {
            clearProcessError();
        });
    }

    // Validação preventiva do campo de Documento (CPF / CNPJ)
    function validateDocColumn(colName) {
        if (!colName || !window.cadastrosSampleData || window.cadastrosSampleData.length === 0) return true;
        
        const sampleValues = window.cadastrosSampleData
            .map(row => row[colName])
            .filter(v => v !== null && v !== undefined && String(v).trim() !== '');

        if (sampleValues.length === 0) return true;

        let compatibleCount = 0;
        let incompatibleSamples = [];

        sampleValues.forEach(val => {
            const digits = String(val).replace(/\D/g, '');
            if ([9, 10, 11, 12, 13, 14].includes(digits.length)) {
                compatibleCount++;
            } else {
                if (!incompatibleSamples.includes(String(val)) && incompatibleSamples.length < 3) {
                    incompatibleSamples.push(String(val));
                }
            }
        });

        const ratio = compatibleCount / sampleValues.length;
        if (ratio < 0.15 && compatibleCount < 2 && incompatibleSamples.length > 0) {
            const sampleVal = incompatibleSamples[0];
            const nDigits = sampleVal.replace(/\D/g, '').length;
            const detail = nDigits === 0 ? `o valor "<strong>${sampleVal}</strong>" não contém dígitos numéricos` : `o valor "<strong>${sampleVal}</strong>" possui apenas ${nDigits} dígitos`;

            showProcessError(
                `A coluna escolhida "<strong>${colName}</strong>" não bate com a referência de <strong>CPF / CNPJ</strong>.<br>` +
                `Na amostra analisada, ${detail}, enquanto a referência oficial da Receita Federal exige <strong>11 dígitos para CPF</strong> (000.000.000-00) ou <strong>14 dígitos para CNPJ</strong> (00.000.000/0000-00).<br>` +
                `Por favor, selecione a coluna correspondente a Documento da sua base.`,
                'Coluna Incompatível com CPF / CNPJ'
            );
            if (selectColDoc) selectColDoc.style.borderColor = '#ef4444';
            return false;
        }

        if (selectColDoc) selectColDoc.style.borderColor = '';
        return true;
    }

    if (selectColDoc) {
        selectColDoc.addEventListener('change', () => {
            clearProcessError();
            validateDocColumn(selectColDoc.value);
        });
    }

    if (selectColEmail) {
        selectColEmail.addEventListener('change', () => {
            clearProcessError();
        });
    }

    if (btnProcess) {
        btnProcess.addEventListener('click', async () => {
            if (!currentSessionId) return;
            clearProcessError();

            const colDoc = selectColDoc.value || null;
            const colName = selectColName.value || null;
            const colEmail = selectColEmail.value || null;
            const colPhone = selectColPhone.value || null;

            if (!colDoc && !colName && !colEmail && !colPhone) {
                showProcessError('Selecione pelo menos uma coluna para auditar e higienizar.', 'Nenhuma Coluna Selecionada');
                return;
            }

            // Validação de compatibilidade prévia no cliente
            if (colDoc && !validateDocColumn(colDoc)) {
                return;
            }

            // Chaves de duplicidade
            const duplicateKeys = [];
            if (checkDupDoc.checked && colDoc) duplicateKeys.push('doc');
            if (checkDupEmail.checked && colEmail) duplicateKeys.push('email');
            if (checkDupPhone.checked && colPhone) duplicateKeys.push('phone');

            const docFormatEl = document.querySelector('input[name="doc-format-radio"]:checked');
            const docFormat = docFormatEl ? docFormatEl.value : 'mask';

            const phoneFormatEl = document.querySelector('input[name="phone-format-radio"]:checked');
            const phoneFormat = phoneFormatEl ? phoneFormatEl.value : 'mask';

            const payload = {
                session_id: currentSessionId,
                col_doc: colDoc,
                col_name: colName,
                col_email: colEmail,
                col_phone: colPhone,
                duplicate_keys: duplicateKeys,
                doc_format: docFormat,
                auto_recover_zero: checkAutoZeros.checked,
                name_title_case: checkNameTitleCase.checked,
                email_lowercase: checkEmailLowercase.checked,
                phone_format: phoneFormat,
                remove_duplicates: checkRemoveDuplicates.checked
            };

            const btnText = btnProcess.querySelector('.btn-text');
            const spinner = btnProcess.querySelector('.spinner');
            const icon = btnProcess.querySelector('.btn-circle-icon');

            btnProcess.disabled = true;
            if (btnText) btnText.textContent = 'Processando e higienizando...';
            if (spinner) spinner.style.display = 'inline-block';
            if (icon) icon.style.display = 'none';

            try {
                const res = await fetch('/api/cadastros/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (!res.ok || data.error) {
                    showProcessError(data.error || 'Erro ao processar higienização.', data.title || 'Inconsistência no Mapeamento');
                    if (data.field === 'col_doc' && selectColDoc) {
                        selectColDoc.style.borderColor = '#ef4444';
                    }
                    return;
                }

                currentReportId = data.report_id;
                cadastrosData = data;

                // Renderiza Resultados no Passo 3
                renderResults(data);

                stepConfig.style.display = 'none';
                stepResults.style.display = 'block';
                window.scrollTo({ top: stepResults.offsetTop - 80, behavior: 'smooth' });

            } catch (err) {
                showProcessError('Erro de conexão ao processar base. Tente novamente.', 'Falha de Comunicação');
            } finally {
                btnProcess.disabled = false;
                if (btnText) btnText.textContent = 'Processar e Higienizar Base';
                if (spinner) spinner.style.display = 'none';
                if (icon) icon.style.display = 'inline-flex';
            }
        });
    }

    // =========================================================================
    // PASSO 3: RENDERIZAÇÃO DOS RESULTADOS E TABELAS
    // =========================================================================

    function renderResults(data) {
        const s = data.summary;

        // Headline e Banners padronizados
        if (s.invalid_docs_count === 0 && s.duplicates_count === 0 && s.suspicious_contacts_count === 0) {
            if (bannerSuccess) bannerSuccess.style.display = 'flex';
            if (bannerDiffs) bannerDiffs.style.display = 'none';
        } else {
            if (bannerSuccess) bannerSuccess.style.display = 'none';
            if (bannerDiffs) bannerDiffs.style.display = 'flex';
        }

        // KPIs Padronizados
        if (kpiTotalRows) kpiTotalRows.textContent = s.total_rows.toLocaleString('pt-BR');
        if (kpiValidRows) kpiValidRows.textContent = s.valid_count.toLocaleString('pt-BR');
        if (kpiValidPercent) kpiValidPercent.textContent = `${s.valid_percentage}% de conformidade`;
        if (kpiInvalidDocs) kpiInvalidDocs.textContent = s.invalid_docs_count.toLocaleString('pt-BR');
        if (kpiDuplicateRows) kpiDuplicateRows.textContent = s.duplicates_count.toLocaleString('pt-BR');
        if (kpiSuspiciousContacts) kpiSuspiciousContacts.textContent = s.suspicious_contacts_count.toLocaleString('pt-BR');
        if (kpiAutoCorrections) kpiAutoCorrections.textContent = s.auto_corrections_count.toLocaleString('pt-BR');

        // Badges das abas
        if (badgeTabDocs) badgeTabDocs.textContent = s.invalid_docs_count;
        if (badgeTabDups) badgeTabDups.textContent = s.duplicates_count;
        if (badgeTabContacts) badgeTabContacts.textContent = s.suspicious_contacts_count;

        // Links de download
        if (btnDownloadClean) btnDownloadClean.href = `/api/cadastros/download-clean/${currentReportId}`;
        if (btnDownloadAudit) btnDownloadAudit.href = `/api/cadastros/download-audit/${currentReportId}`;

        // Renderiza Tabelas
        renderTableDocs(data.invalid_docs);
        renderTableDups(data.duplicates);
        renderTableContacts(data.suspicious_contacts);
        renderTablePreview(data.clean_columns, data.preview_clean);

        // Renderiza Gráficos Analíticos de Cadastros (Chart.js)
        renderCadastrosCharts(data);
    }

    function renderTableDocs(items) {
        tbodyDocs.innerHTML = '';
        if (!items || items.length === 0) {
            tbodyDocs.innerHTML = '<tr><td colspan="5" class="empty-table-msg" style="text-align: center; padding: 24px; color: var(--text-muted);">Nenhum CPF ou CNPJ inválido encontrado nesta base! ✨</td></tr>';
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="text-align: center; white-space: nowrap;"><span class="badge-line">${item.row}</span></td>
                <td><strong>${escapeHtml(item.name || '-')}</strong></td>
                <td><span class="key-code text-danger" style="background: rgba(239, 68, 68, 0.1);">${escapeHtml(item.original || '(vazio)')}</span></td>
                <td>${item.cleaned ? `<span class="key-code text-success" style="background: rgba(34, 197, 94, 0.1);">${escapeHtml(item.cleaned)}</span>` : '<span style="color:#94a3af;">-</span>'}</td>
                <td><span class="status-badge-diff">${escapeHtml(item.reason)}</span></td>
            `;
            tbodyDocs.appendChild(tr);
        });
    }

    function renderTableDups(items) {
        tbodyDups.innerHTML = '';
        if (!items || items.length === 0) {
            tbodyDups.innerHTML = '<tr><td colspan="5" class="empty-table-msg" style="text-align: center; padding: 24px; color: var(--text-muted);">Nenhum registro duplicado encontrado com os critérios escolhidos! ✨</td></tr>';
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            const linesStr = item.lines.join(', ');
            tr.innerHTML = `
                <td><strong>${escapeHtml(item.column)}</strong></td>
                <td><span class="key-code">${escapeHtml(item.value)}</span></td>
                <td style="text-align: center; white-space: nowrap;"><span class="status-badge-warning">${item.count}x</span></td>
                <td><span style="font-size: 12.5px; font-weight: 600; color: var(--text-muted);">Linhas: ${linesStr}</span></td>
                <td>${escapeHtml(item.sample_name || '-')}</td>
            `;
            tbodyDups.appendChild(tr);
        });
    }

    function renderTableContacts(items) {
        tbodyContacts.innerHTML = '';
        if (!items || items.length === 0) {
            tbodyContacts.innerHTML = '<tr><td colspan="6" class="empty-table-msg" style="text-align: center; padding: 24px; color: var(--text-muted);">Nenhum e-mail ou telefone suspeito identificado! ✨</td></tr>';
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="text-align: center; white-space: nowrap;"><span class="badge-line">${item.row}</span></td>
                <td><strong>${escapeHtml(item.name || '-')}</strong></td>
                <td style="text-align: center; white-space: nowrap;"><span class="status-badge-info">${item.type}</span></td>
                <td><span class="key-code">${escapeHtml(item.original || '(vazio)')}</span></td>
                <td><span class="status-badge-warning">${escapeHtml(item.issue)}</span></td>
                <td>${item.suggestion ? `<span style="font-size: 12.5px; font-weight: 700; color: #16a34a;">💡 ${escapeHtml(item.suggestion)}</span>` : '<span style="color:#94a3af;">-</span>'}</td>
            `;
            tbodyContacts.appendChild(tr);
        });
    }

    function renderTablePreview(cols, rows) {
        theadPreview.innerHTML = '';
        tbodyPreview.innerHTML = '';

        if (!rows || rows.length === 0) {
            tbodyPreview.innerHTML = '<tr><td class="empty-table-msg" style="text-align: center; padding: 24px; color: var(--text-muted);">Nenhum dado para exibir.</td></tr>';
            return;
        }

        // Cabeçalho
        const trHead = document.createElement('tr');
        const thRow = document.createElement('th');
        thRow.style.width = '70px';
        thRow.style.textAlign = 'center';
        thRow.textContent = 'Linha';
        trHead.appendChild(thRow);

        cols.forEach(c => {
            const th = document.createElement('th');
            th.textContent = c;
            trHead.appendChild(th);
        });
        theadPreview.appendChild(trHead);

        // Linhas
        rows.forEach(r => {
            const tr = document.createElement('tr');
            const tdLine = document.createElement('td');
            tdLine.style.textAlign = 'center';
            tdLine.style.whiteSpace = 'nowrap';
            tdLine.innerHTML = `<span class="badge-line">${r._row_num}</span>`;
            tr.appendChild(tdLine);

            cols.forEach(c => {
                const td = document.createElement('td');
                td.textContent = r[c] || '';
                tr.appendChild(td);
            });
            tbodyPreview.appendChild(tr);
        });
    }

    // Navegação de Abas Padronizada (.result-nav-tabs)
    document.querySelectorAll('#cadastros-results-tabs .result-nav-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');

            document.querySelectorAll('#cadastros-results-tabs .result-nav-tab-btn').forEach(b => {
                b.classList.remove('active');
            });
            btn.classList.add('active');

            ['tab-docs', 'tab-dups', 'tab-contacts', 'tab-preview'].forEach(t => {
                const pane = document.getElementById(`pane-${t}`);
                if (pane) pane.style.display = t === target ? 'block' : 'none';
            });
        });
    });

    // Reiniciar / Validar Outra Base
    if (btnRestart) {
        btnRestart.addEventListener('click', () => {
            fileInput.value = '';
            if (fileMeta) fileMeta.style.display = 'none';
            dropZone.classList.remove('file-loaded');
            btnRead.disabled = true;

            stepResults.style.display = 'none';
            stepConfig.style.display = 'none';
            stepUpload.style.display = 'block';

            currentSessionId = null;
            currentReportId = null;
            cadastrosData = null;

            window.scrollTo({ top: stepUpload.offsetTop - 80, behavior: 'smooth' });
        });
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ----------------------------------------------------
    // GRÁFICOS ANALÍTICOS DE CADASTROS (CHART.JS)
    // ----------------------------------------------------
    let chartCadastrosHealthInstance = null;
    let chartCadastrosIssuesInstance = null;
    let lastCadastrosData = null;

    function renderCadastrosCharts(data) {
        lastCadastrosData = data;
        const chartsWrapper = document.getElementById('cadastros-charts-wrapper');
        const chartsContainer = document.getElementById('cadastros-charts-container');
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

            renderCadastrosHealthChart(data);
            renderCadastrosIssuesChart(data);
        } catch (err) {
            console.error('Erro seguro na renderização dos gráficos de cadastros:', err);
        }
    }

    function renderCadastrosHealthChart(data) {
        const canvas = document.getElementById('chart-cadastros-health');
        const badgeCompliance = document.getElementById('cadastros-compliance-badge');
        if (!canvas) return;

        try {
            if (chartCadastrosHealthInstance) {
                chartCadastrosHealthInstance.destroy();
                chartCadastrosHealthInstance = null;
            }

            const s = data.summary || {};
            const totalRows = s.total_rows || 0;
            const validCount = s.valid_count || 0;
            const duplicatesCount = s.duplicates_count || 0;
            const invalidCount = (s.invalid_docs_count || 0) + (s.suspicious_contacts_count || 0);

            const compliancePct = s.valid_percentage != null ? s.valid_percentage : (totalRows > 0 ? ((validCount / totalRows) * 100).toFixed(1) : 100);
            if (badgeCompliance) {
                badgeCompliance.textContent = `Conformidade: ${compliancePct}%`;
            }

            const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
                           document.documentElement.classList.contains('dark-theme') ||
                           (document.body && document.body.classList.contains('dark-theme')) ||
                           (localStorage.getItem('splitc_theme') === 'dark');

            const chartData = (totalRows > 0 || (validCount + invalidCount + duplicatesCount > 0))
                ? [validCount, invalidCount, duplicatesCount]
                : [1, 0, 0];

            chartCadastrosHealthInstance = new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: ['Cadastros Válidos', 'Inválidos / Incompletos', 'Duplicados'],
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
                                    const val = context.parsed || 0;
                                    const sum = validCount + invalidCount + duplicatesCount || totalRows;
                                    const pct = sum > 0 ? ((val / sum) * 100).toFixed(1) : '0.0';
                                    return ` ${context.label}: ${val.toLocaleString("pt-BR")} (${pct}%)`;
                                }
                            }
                        }
                    }
                }
            });
        } catch (e) {
            console.error('Falha segura no gráfico Donut de Cadastros:', e);
        }
    }

    function renderCadastrosIssuesChart(data) {
        const canvas = document.getElementById('chart-cadastros-issues');
        const emptyEl = document.getElementById('chart-cadastros-issues-empty');
        if (!canvas) return;

        try {
            if (chartCadastrosIssuesInstance) {
                chartCadastrosIssuesInstance.destroy();
                chartCadastrosIssuesInstance = null;
            }

            const s = data.summary || {};
            const b = s.inconsistency_breakdown || {};

            const issuesList = [
                { label: 'CPF com Dígito Inválido', count: b.cpf_invalid || 0 },
                { label: 'CNPJ com Dígito Inválido', count: b.cnpj_invalid || 0 },
                { label: 'Zeros à Esquerda Ausentes', count: b.missing_zeros || 0 },
                { label: 'E-mails Inválidos', count: b.invalid_emails || 0 },
                { label: 'Linhas Repetidas', count: b.duplicate_rows != null ? b.duplicate_rows : (s.duplicates_count || 0) }
            ];

            const totalIssues = issuesList.reduce((acc, curr) => acc + curr.count, 0);

            if (totalIssues === 0) {
                canvas.style.display = 'none';
                if (emptyEl) emptyEl.style.display = 'flex';
                return;
            }

            canvas.style.display = 'block';
            if (emptyEl) emptyEl.style.display = 'none';

            const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
                           document.documentElement.classList.contains('dark-theme') ||
                           (document.body && document.body.classList.contains('dark-theme')) ||
                           (localStorage.getItem('splitc_theme') === 'dark');

            chartCadastrosIssuesInstance = new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: issuesList.map(i => i.label),
                    datasets: [{
                        label: 'Ocorrências',
                        data: issuesList.map(i => i.count),
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
                                    return ` ${val.toLocaleString("pt-BR")} ocorrência(s)`;
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
                                font: { size: 12, family: 'Inter, sans-serif', weight: '600' }
                            }
                        }
                    }
                }
            });
        } catch (e) {
            console.error('Falha segura no gráfico de Inconsistências de Cadastros:', e);
        }
    }

    // Exportação do Painel em Imagem PNG (Client-side / 0 MB no Servidor)
    function exportCadastrosChartsToPng() {
        try {
            if (!chartCadastrosHealthInstance && !chartCadastrosIssuesInstance) return;

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

            const scale = 2;
            const outCanvas = document.createElement('canvas');
            outCanvas.width = totalW * scale;
            outCanvas.height = totalH * scale;
            const ctx = outCanvas.getContext('2d');
            ctx.scale(scale, scale);

            ctx.fillStyle = bgPage;
            ctx.fillRect(0, 0, totalW, totalH);

            ctx.fillStyle = accentGreen;
            ctx.font = 'bold 20px Inter, system-ui, sans-serif';
            ctx.fillText('ValidAí', cardPad, cardPad + 24);

            ctx.fillStyle = textTitle;
            ctx.font = '600 15px Inter, system-ui, sans-serif';
            ctx.fillText('•  Higienizador de Cadastros • Saúde da Base & Inconsistências', cardPad + 82, cardPad + 24);

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

            const yCards = cardPad + topHeaderH;
            const x1 = cardPad;
            roundRect(ctx, x1, yCards, cardW, cardH, 10, bgCard, borderCard);

            if (chartCadastrosHealthInstance && chartCadastrosHealthInstance.canvas) {
                const c1 = chartCadastrosHealthInstance.canvas;
                const innerPad = 14;
                ctx.drawImage(c1, x1 + innerPad, yCards + innerPad, cardW - innerPad * 2, cardH - innerPad * 2);
            }

            const x2 = cardPad + cardW + cardGap;
            roundRect(ctx, x2, yCards, cardW, cardH, 10, bgCard, borderCard);

            if (chartCadastrosIssuesInstance && chartCadastrosIssuesInstance.canvas && chartCadastrosIssuesInstance.canvas.style.display !== 'none') {
                const c2 = chartCadastrosIssuesInstance.canvas;
                const innerPad = 14;
                ctx.drawImage(c2, x2 + innerPad, yCards + innerPad, cardW - innerPad * 2, cardH - innerPad * 2);
            } else {
                ctx.fillStyle = accentGreen;
                ctx.font = 'bold 22px Inter, system-ui, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('✓', x2 + cardW / 2, yCards + cardH / 2 - 10);
                ctx.fillStyle = textMuted;
                ctx.font = '13px Inter, system-ui, sans-serif';
                ctx.fillText('100% dos cadastros em conformidade', x2 + cardW / 2, yCards + cardH / 2 + 18);
                ctx.textAlign = 'left';
            }

            const link = document.createElement('a');
            link.download = 'painel-cadastros-validai.png';
            link.href = outCanvas.toDataURL('image/png');
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (e) {
            console.error('Erro seguro na exportação do painel PNG de cadastros:', e);
        }
    }

    const btnExportCadastros = document.getElementById('btn-export-charts-cadastros');
    if (btnExportCadastros) {
        btnExportCadastros.addEventListener('click', exportCadastrosChartsToPng);
    }

    document.addEventListener('click', (e) => {
        if (e.target && (e.target.closest('#theme-toggle-btn') || (e.target.classList && e.target.classList.contains('theme-toggle-btn')))) {
            if (lastCadastrosData && stepResults && stepResults.style.display !== 'none') {
                setTimeout(() => {
                    renderCadastrosCharts(lastCadastrosData);
                }, 120);
            }
        }
    });

})();
