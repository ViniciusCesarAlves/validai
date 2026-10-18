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

    // Alternador de Tema Local
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const target = current === 'dark' ? 'light' : 'dark';
            if (target === 'dark') {
                html.setAttribute('data-theme', 'dark');
                html.classList.add('dark-theme');
                if (document.body) document.body.classList.add('dark-theme');
                localStorage.setItem('splitc_theme', 'dark');
            } else {
                html.removeAttribute('data-theme');
                html.classList.remove('dark-theme');
                if (document.body) document.body.classList.remove('dark-theme');
                localStorage.setItem('splitc_theme', 'light');
            }
        });
    }

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
                <td style="text-align: center; font-weight: 600;">${item.row}</td>
                <td><strong>${escapeHtml(item.name || '-')}</strong></td>
                <td><code class="code-pill code-danger">${escapeHtml(item.original || '(vazio)')}</code></td>
                <td>${item.cleaned ? `<code class="code-pill">${escapeHtml(item.cleaned)}</code>` : '<span style="color:#94a3af;">-</span>'}</td>
                <td><span class="badge-audit" style="color: var(--danger);">${escapeHtml(item.reason)}</span></td>
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
                <td><code class="code-pill code-warning">${escapeHtml(item.value)}</code></td>
                <td style="text-align: center;"><span class="tab-btn-badge" style="background: rgba(245, 158, 11, 0.15); color: #d97706;">${item.count}x</span></td>
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
                <td style="text-align: center; font-weight: 600;">${item.row}</td>
                <td><strong>${escapeHtml(item.name || '-')}</strong></td>
                <td><span class="badge-ready" style="font-size: 11px;">${item.type}</span></td>
                <td><code class="code-pill" style="color: #ea580c; background: rgba(234, 88, 12, 0.1);">${escapeHtml(item.original || '(vazio)')}</code></td>
                <td><span style="font-size: 12.5px; font-weight: 600; color: #ea580c;">${escapeHtml(item.issue)}</span></td>
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
            tdLine.style.fontWeight = '600';
            tdLine.textContent = r._row_num;
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
})();
