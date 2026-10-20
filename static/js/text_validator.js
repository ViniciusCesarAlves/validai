/**
 * ValidAí - Validador de Documentos e Textos (.pdf, .docx, .txt)
 * Controlador Frontend (Upload, Modos Rich Text / Redline / Plain Text, Analytics e PDF)
 */

document.addEventListener('DOMContentLoaded', () => {
    // Tema gerenciado centralmente por header.html

    // --- 2. Estado da Aplicação ---
    let inputMode = 'files'; // 'files' | 'paste'
    let currentViewMode = 'rich_text'; // 'rich_text' | 'redline' | 'plain_text'
    let fileDocA = null;
    let fileDocB = null;
    let comparisonData = null;

    // --- 3. Referências DOM ---
    const btnInputFiles = document.getElementById('btn-input-files');
    const btnInputPaste = document.getElementById('btn-input-paste');
    const docUploadGrid = document.getElementById('doc-upload-grid');
    const docPasteGrid = document.getElementById('doc-paste-grid');

    const dropzoneA = document.getElementById('dropzone-doc-a');
    const dropzoneB = document.getElementById('dropzone-doc-b');
    const inputA = document.getElementById('file-doc-a');
    const inputB = document.getElementById('file-doc-b');
    const metaA = document.getElementById('meta-doc-a');
    const metaB = document.getElementById('meta-doc-b');
    const filenameA = document.getElementById('filename-doc-a');
    const filenameB = document.getElementById('filename-doc-b');
    const filesizeA = document.getElementById('filesize-doc-a');
    const filesizeB = document.getElementById('filesize-doc-b');

    const textareaA = document.getElementById('textarea-doc-a');
    const textareaB = document.getElementById('textarea-doc-b');
    const counterA = document.getElementById('counter-doc-a');
    const counterB = document.getElementById('counter-doc-b');

    const modeCards = document.querySelectorAll('.doc-mode-card');
    const viewerModeBtns = document.querySelectorAll('.viewer-mode-btn');

    const btnTryExample = document.getElementById('btn-text-try-example');
    const btnFindDiff = document.getElementById('btn-text-find-diff');
    const btnReset = document.getElementById('btn-text-reset');

    const stepResults = document.getElementById('text-step-results');
    const viewerContainer = document.getElementById('text-diff-viewer-container');
    const chkOnlyDiffs = document.getElementById('chk-only-diffs');
    const visualSearchInput = document.getElementById('text-visual-search');
    const tableSearchInput = document.getElementById('text-table-search');

    const toastError = document.getElementById('text-toast-error');
    const toastMessage = document.getElementById('text-toast-message');
    const btnCloseToast = document.getElementById('btn-close-text-toast');

    // --- 4. Funções Utilitárias ---
    function showError(msg) {
        if (!toastError || !toastMessage) return;
        toastMessage.textContent = msg;
        toastError.style.display = 'flex';
        setTimeout(() => {
            toastError.style.display = 'none';
        }, 6500);
    }

    if (btnCloseToast) {
        btnCloseToast.addEventListener('click', () => {
            toastError.style.display = 'none';
        });
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 KB';
        const kb = bytes / 1024;
        if (kb < 1024) return `${kb.toFixed(1)} KB`;
        return `${(kb / 1024).toFixed(2)} MB`;
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function updateActionButtonState() {
        if (inputMode === 'files') {
            btnFindDiff.disabled = !(fileDocA && fileDocB);
        } else {
            const hasA = textareaA.value.trim().length > 0;
            const hasB = textareaB.value.trim().length > 0;
            btnFindDiff.disabled = !(hasA || hasB);
        }
    }

    // --- 5. Alternância entre Upload de Arquivos e Colar Texto ---
    btnInputFiles.addEventListener('click', () => {
        inputMode = 'files';
        btnInputFiles.classList.add('active');
        btnInputPaste.classList.remove('active');
        docUploadGrid.style.display = 'grid';
        docPasteGrid.style.display = 'none';
        updateActionButtonState();
    });

    btnInputPaste.addEventListener('click', () => {
        inputMode = 'paste';
        btnInputPaste.classList.add('active');
        btnInputFiles.classList.remove('active');
        docUploadGrid.style.display = 'none';
        docPasteGrid.style.display = 'grid';
        updateActionButtonState();
    });

    // Contadores de caracteres nas textareas
    function updateCharCounter(textarea, counterEl) {
        const len = textarea.value.length;
        const words = textarea.value.trim() ? textarea.value.trim().split(/\s+/).length : 0;
        counterEl.textContent = `${len.toLocaleString('pt-BR')} caract. • ${words} palav.`;
        updateActionButtonState();
    }

    textareaA.addEventListener('input', () => updateCharCounter(textareaA, counterA));
    textareaB.addEventListener('input', () => updateCharCounter(textareaB, counterB));

    // --- 6. Upload e Drag & Drop de Documentos (.pdf, .docx, .txt) ---
    function isValidDocFile(file) {
        if (!file) return false;
        const validExts = ['.pdf', '.docx', '.txt'];
        const lower = file.name.toLowerCase();
        return validExts.some(ext => lower.endsWith(ext));
    }

    function handleFileSelect(side, file) {
        if (!file) return;
        if (!isValidDocFile(file)) {
            showError('Formato inválido. Por favor, selecione um arquivo .pdf, .docx ou .txt.');
            return;
        }
        if (side === 'a') {
            fileDocA = file;
            filenameA.textContent = file.name;
            filesizeA.textContent = formatBytes(file.size);
            metaA.style.display = 'inline-flex';
            dropzoneA.classList.add('has-file', 'file-loaded');
        } else {
            fileDocB = file;
            filenameB.textContent = file.name;
            filesizeB.textContent = formatBytes(file.size);
            metaB.style.display = 'inline-flex';
            dropzoneB.classList.add('has-file', 'file-loaded');
        }
        updateActionButtonState();
    }

    function setupDropzone(dropzone, inputEl, side) {
        dropzone.addEventListener('click', (e) => {
            if (e.target !== inputEl) {
                inputEl.click();
            }
        });

        inputEl.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                handleFileSelect(side, e.target.files[0]);
            }
        });

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover', 'drag-over');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover', 'drag-over');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover', 'drag-over');
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleFileSelect(side, e.dataTransfer.files[0]);
            }
        });
    }

    setupDropzone(dropzoneA, inputA, 'a');
    setupDropzone(dropzoneB, inputB, 'b');

    // --- 7. Seleção dos Cartões de Modo (Rich Text / Redline / Plain Text) ---
    function setViewMode(mode) {
        currentViewMode = mode;

        modeCards.forEach(card => {
            const isMatch = card.getAttribute('data-view-mode') === mode;
            card.classList.toggle('active', isMatch);
            card.setAttribute('aria-checked', isMatch ? 'true' : 'false');
        });

        viewerModeBtns.forEach(btn => {
            const isMatch = btn.getAttribute('data-mode') === mode;
            btn.classList.toggle('active', isMatch);
        });

        if (comparisonData) {
            renderVisualComparison();
        }
    }

    modeCards.forEach(card => {
        card.addEventListener('click', () => {
            setViewMode(card.getAttribute('data-view-mode'));
        });
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setViewMode(card.getAttribute('data-view-mode'));
            }
        });
    });

    viewerModeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            setViewMode(btn.getAttribute('data-mode'));
        });
    });

    // --- 8. Botão "Testar Exemplo" ---
    btnTryExample.addEventListener('click', () => {
        const sampleOriginal = [
            "CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE TECNOLOGIA - VALIDAÍ",
            "Cláusula 1ª - Do Objeto do Contrato",
            "O presente instrumento tem como objeto o licenciamento da plataforma de auditoria de dados.",
            "Cláusula 2ª - Do Prazo de Vigência e Renovação",
            "O contrato terá vigência de 12 (doze) meses, iniciando-se em 01 de janeiro de 2026.",
            "Cláusula 3ª - Dos Valores e Condições de Pagamento",
            "Pelos serviços prestados, a CONTRATANTE pagará o valor mensal de R$ 4.500,00 até o dia 10.",
            "Em caso de atraso, incidirá multa moratória de 2% e juros de 1% ao mês.",
            "Cláusula 4ª - Do Acordo de Nível de Serviço (SLA)",
            "O suporte técnico funcionará em horário comercial (09h às 18h), com tempo de resposta de 4 horas.",
            "Cláusula 5ª - Da Confidencialidade e LGPD",
            "Ambas as partes comprometem-se a manter sigilo absoluto sobre as bases de dados processadas."
        ].join("\n");

        const sampleNew = [
            "CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE TECNOLOGIA - VALIDAÍ",
            "Cláusula 1ª - Do Objeto do Contrato",
            "O presente instrumento tem como objeto o licenciamento da plataforma de auditoria de dados e documentos.",
            "Cláusula 2ª - Do Prazo de Vigência e Renovação",
            "O contrato terá vigência de 24 (vinte e quatro) meses, iniciando-se em 15 de fevereiro de 2026.",
            "Cláusula 3ª - Dos Valores e Condições de Pagamento",
            "Pelos serviços prestados, a CONTRATANTE pagará o valor mensal de R$ 5.200,00 até o dia 15.",
            "Cláusula 4ª - Do Acordo de Nível de Serviço (SLA)",
            "O suporte técnico funcionará em regime 24x7, com tempo de resposta máximo de 1 hora.",
            "Cláusula 5ª - Da Confidencialidade e LGPD",
            "Ambas as partes comprometem-se a manter sigilo absoluto sobre as bases de dados processadas.",
            "Cláusula 6ª - Da Assinatura Digital",
            "As partes reconhecem a validade jurídica da assinatura eletrônica deste instrumento."
        ].join("\n");

        btnInputPaste.click();
        textareaA.value = sampleOriginal;
        textareaB.value = sampleNew;
        updateCharCounter(textareaA, counterA);
        updateCharCounter(textareaB, counterB);
        runTextComparison('Minuta_Contrato_v1.docx', 'Minuta_Contrato_v2_Revisado.docx');
    });

    // --- 9. Execução da Comparação via API ---
    async function runTextComparison(customNameA = null, customNameB = null) {
        const spinner = btnFindDiff.querySelector('.spinner');
        const btnText = btnFindDiff.querySelector('.btn-text');

        btnFindDiff.disabled = true;
        if (spinner) spinner.style.display = 'inline-block';
        if (btnText) btnText.textContent = 'Processando Documentos...';

        try {
            const formData = new FormData();
            formData.append('trim_spaces', document.getElementById('opt-text-trim-spaces').checked ? 'true' : 'false');
            formData.append('ignore_case', document.getElementById('opt-text-ignore-case').checked ? 'true' : 'false');
            formData.append('ignore_empty_lines', document.getElementById('opt-text-ignore-empty').checked ? 'true' : 'false');
            formData.append('diff_granularity', document.getElementById('opt-text-word-level').checked ? 'word' : 'char');

            if (inputMode === 'files' && fileDocA && fileDocB) {
                formData.append('file_a', fileDocA);
                formData.append('file_b', fileDocB);
            } else {
                formData.append('text_a', textareaA.value);
                formData.append('text_b', textareaB.value);
                formData.append('filename_a', customNameA || 'Texto Original');
                formData.append('filename_b', customNameB || 'Texto Novo');
            }

            const resp = await fetch('/api/text/compare', {
                method: 'POST',
                body: formData
            });

            const data = await resp.json();
            if (!resp.ok || data.error) {
                throw new Error(data.error || 'Erro ao comparar os documentos.');
            }

            comparisonData = data;
            renderAllResults(data);

            stepResults.style.display = 'block';
            stepResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (err) {
            showError(err.message || 'Falha inesperada na comparação.');
        } finally {
            if (spinner) spinner.style.display = 'none';
            if (btnText) btnText.textContent = 'Encontrar Diferenças';
            updateActionButtonState();
        }
    }

    btnFindDiff.addEventListener('click', () => runTextComparison());

    // --- 10. Renderização de KPIs, Banners Padronizados, PDF e Tabelas ---
    function renderAllResults(data) {
        const s = data.summary;

        // Banners Padronizados (Idêntico ao Validador de Planilhas)
        const bannerIdentical = document.getElementById('text-banner-identical');
        const bannerDiffs = document.getElementById('text-banner-diffs');

        const lang = (window.ValidAiI18n && window.ValidAiI18n.getCurrentLanguage) ? window.ValidAiI18n.getCurrentLanguage() : 'pt';
        const numLocale = lang === 'en' ? 'en-US' : (lang === 'es' ? 'es-ES' : 'pt-BR');

        if (s.is_identical) {
            bannerIdentical.style.display = 'flex';
            bannerDiffs.style.display = 'none';
            if (lang === 'es') {
                document.getElementById('text-identical-title').textContent = '¡Excelente! ¡Los documentos son 100% IDÉNTICOS!';
                document.getElementById('text-identical-desc').textContent =
                    `Todas las líneas y palabras coincidieron perfectamente entre "${s.filename_a}" (${s.file_type_a}) y "${s.filename_b}" (${s.file_type_b}).`;
            } else if (lang === 'en') {
                document.getElementById('text-identical-title').textContent = 'Great! The documents are 100% IDENTICAL!';
                document.getElementById('text-identical-desc').textContent =
                    `All lines and words matched perfectly between "${s.filename_a}" (${s.file_type_a}) and "${s.filename_b}" (${s.file_type_b}).`;
            } else {
                document.getElementById('text-identical-title').textContent = 'Excelente! Os documentos estão 100% IDÊNTICOS!';
                document.getElementById('text-identical-desc').textContent =
                    `Todas as linhas e palavras coincidiram perfeitamente entre "${s.filename_a}" (${s.file_type_a}) e "${s.filename_b}" (${s.file_type_b}).`;
            }
        } else {
            bannerIdentical.style.display = 'none';
            bannerDiffs.style.display = 'flex';
            if (lang === 'es') {
                document.getElementById('text-diffs-title').textContent =
                    `¡Atención: Se encontraron ${s.total_diff_blocks} líneas con alteraciones (${s.similarity_pct}% de similitud)!`;
                document.getElementById('text-diffs-desc').textContent =
                    `Comparando "${s.filename_a}" (${s.file_type_a}) y "${s.filename_b}" (${s.file_type_b}) — ${s.modified_lines_count} modificadas, ${s.added_lines_count} añadidas y ${s.removed_lines_count} eliminadas.`;
            } else if (lang === 'en') {
                document.getElementById('text-diffs-title').textContent =
                    `Notice: ${s.total_diff_blocks} lines with changes found (${s.similarity_pct}% similarity)!`;
                document.getElementById('text-diffs-desc').textContent =
                    `Comparing "${s.filename_a}" (${s.file_type_a}) and "${s.filename_b}" (${s.file_type_b}) — ${s.modified_lines_count} modified, ${s.added_lines_count} added, and ${s.removed_lines_count} removed.`;
            } else {
                document.getElementById('text-diffs-title').textContent =
                    `Atenção: Foram encontradas ${s.total_diff_blocks} linhas com alterações (${s.similarity_pct}% de similaridade)!`;
                document.getElementById('text-diffs-desc').textContent =
                    `Comparando "${s.filename_a}" (${s.file_type_a}) e "${s.filename_b}" (${s.file_type_b}) — ${s.modified_lines_count} modificadas, ${s.added_lines_count} adicionadas e ${s.removed_lines_count} removidas.`;
            }
        }

        // KPIs (Grid 2x3 padronizado)
        document.getElementById('text-kpi-similarity').textContent = `${s.similarity_pct}%`;
        document.getElementById('text-kpi-lines').textContent = `${s.total_lines_a} / ${s.total_lines_b}`;
        const pageLabel = lang === 'en' ? 'pg.' : (lang === 'es' ? 'pág.' : 'pág.');
        document.getElementById('text-kpi-pages-sub').textContent = `${s.pages_a} ${pageLabel} vs ${s.pages_b} ${pageLabel}`;
        document.getElementById('text-kpi-identical').textContent = s.identical_lines_count.toLocaleString(numLocale);
        document.getElementById('text-kpi-diff-lines').textContent = s.total_diff_blocks.toLocaleString(numLocale);
        if (lang === 'en') {
            document.getElementById('text-kpi-diff-breakdown').textContent =
                `${s.modified_lines_count} mod. | ${s.added_lines_count} added | ${s.removed_lines_count} rem.`;
        } else if (lang === 'es') {
            document.getElementById('text-kpi-diff-breakdown').textContent =
                `${s.modified_lines_count} mod. | ${s.added_lines_count} añad. | ${s.removed_lines_count} elim.`;
        } else {
            document.getElementById('text-kpi-diff-breakdown').textContent =
                `${s.modified_lines_count} mod. | ${s.added_lines_count} adic. | ${s.removed_lines_count} rem.`;
        }
        document.getElementById('text-kpi-words-added').textContent = `+${s.words_added.toLocaleString(numLocale)}`;
        document.getElementById('text-kpi-words-removed').textContent = `-${s.words_removed.toLocaleString(numLocale)}`;

        // Badge da aba de divergências
        document.getElementById('badge-text-diffs').textContent = s.total_diff_blocks;

        // Botão de Download PDF
        const btnPdf = document.getElementById('btn-download-text-pdf');
        if (data.report_id) {
            btnPdf.href = `/api/text/download-pdf/${data.report_id}`;
            btnPdf.style.display = 'inline-flex';
        } else {
            btnPdf.style.display = 'none';
        }

        // Renderiza as 3 visões das abas
        renderVisualComparison();
        renderDiffTable(data.diff_table_rows || []);
        renderStatsTable(data.stats_comparison || [], s);
    }

    // Helper para converter lista de segmentos [{text, type}] em HTML com <del> e <ins>
    function renderSegmentsHtml(segments) {
        if (!segments || segments.length === 0) return '';
        return segments.map(seg => {
            const escaped = escapeHtml(seg.text);
            if (seg.type === 'delete') {
                return `<del class="diff-tok-del">${escaped}</del>`;
            }
            if (seg.type === 'insert') {
                return `<ins class="diff-tok-ins">${escaped}</ins>`;
            }
            return `<span>${escaped}</span>`;
        }).join('');
    }

    // --- 11. Renderizador dos 3 Modos Visuais (Rich Text | Redline | Plain Text) ---
    function renderVisualComparison() {
        if (!comparisonData) return;
        const s = comparisonData.summary;
        const onlyDiffs = chkOnlyDiffs.checked;
        const query = (visualSearchInput.value || '').trim().toLowerCase();

        if (currentViewMode === 'rich_text') {
            const blocks = (comparisonData.side_by_side_blocks || []).filter(b => {
                if (onlyDiffs && b.type === 'equal') return false;
                if (query) {
                    const hayA = (b.text_a || '').toLowerCase();
                    const hayB = (b.text_b || '').toLowerCase();
                    return hayA.includes(query) || hayB.includes(query);
                }
                return true;
            });

            if (blocks.length === 0) {
                viewerContainer.innerHTML = `<div style="padding: 36px; text-align: center; color: var(--text-muted);">Nenhum trecho encontrado para os filtros selecionados.</div>`;
                return;
            }

            let leftRowsHtml = '';
            let rightRowsHtml = '';

            blocks.forEach(b => {
                if (b.type === 'equal') {
                    leftRowsHtml += `
                        <div class="rich-line-row">
                            <span class="rich-line-num">${b.line_a ?? ''}</span>
                            <div class="rich-line-text">${escapeHtml(b.text_a) || '&nbsp;'}</div>
                        </div>`;
                    rightRowsHtml += `
                        <div class="rich-line-row">
                            <span class="rich-line-num">${b.line_b ?? ''}</span>
                            <div class="rich-line-text">${escapeHtml(b.text_b) || '&nbsp;'}</div>
                        </div>`;
                } else if (b.type === 'delete') {
                    leftRowsHtml += `
                        <div class="rich-line-row line-delete">
                            <span class="rich-line-num">${b.line_a ?? ''}</span>
                            <div class="rich-line-text">${renderSegmentsHtml(b.segments_a) || '&nbsp;'}</div>
                        </div>`;
                    rightRowsHtml += `
                        <div class="rich-line-row line-empty-slot">
                            <span class="rich-line-num"></span>
                            <div class="rich-line-text">&nbsp;</div>
                        </div>`;
                } else if (b.type === 'insert') {
                    leftRowsHtml += `
                        <div class="rich-line-row line-empty-slot">
                            <span class="rich-line-num"></span>
                            <div class="rich-line-text">&nbsp;</div>
                        </div>`;
                    rightRowsHtml += `
                        <div class="rich-line-row line-insert">
                            <span class="rich-line-num">${b.line_b ?? ''}</span>
                            <div class="rich-line-text">${renderSegmentsHtml(b.segments_b) || '&nbsp;'}</div>
                        </div>`;
                } else if (b.type === 'replace') {
                    leftRowsHtml += `
                        <div class="rich-line-row line-replace-a">
                            <span class="rich-line-num">${b.line_a ?? ''}</span>
                            <div class="rich-line-text">${renderSegmentsHtml(b.segments_a) || '&nbsp;'}</div>
                        </div>`;
                    rightRowsHtml += `
                        <div class="rich-line-row line-replace-b">
                            <span class="rich-line-num">${b.line_b ?? ''}</span>
                            <div class="rich-line-text">${renderSegmentsHtml(b.segments_b) || '&nbsp;'}</div>
                        </div>`;
                }
            });

            viewerContainer.innerHTML = `
                <div class="rich-doc-grid">
                    <div class="rich-doc-pane">
                        <div class="rich-doc-header">
                            <span>${escapeHtml(s.filename_a)}</span>
                            <span class="rich-doc-badge">Original (${s.total_lines_a} linhas)</span>
                        </div>
                        <div class="rich-doc-body" id="rich-scroll-a">${leftRowsHtml}</div>
                    </div>
                    <div class="rich-doc-pane">
                        <div class="rich-doc-header">
                            <span>${escapeHtml(s.filename_b)}</span>
                            <span class="rich-doc-badge">Novo (${s.total_lines_b} linhas)</span>
                        </div>
                        <div class="rich-doc-body" id="rich-scroll-b">${rightRowsHtml}</div>
                    </div>
                </div>
            `;

            // Sincroniza rolagem vertical entre os dois documentos
            const scrollA = document.getElementById('rich-scroll-a');
            const scrollB = document.getElementById('rich-scroll-b');
            if (scrollA && scrollB) {
                let isSyncingLeft = false;
                let isSyncingRight = false;
                scrollA.addEventListener('scroll', () => {
                    if (!isSyncingLeft) {
                        isSyncingRight = true;
                        scrollB.scrollTop = scrollA.scrollTop;
                    }
                    isSyncingLeft = false;
                });
                scrollB.addEventListener('scroll', () => {
                    if (!isSyncingRight) {
                        isSyncingLeft = true;
                        scrollA.scrollTop = scrollB.scrollTop;
                    }
                    isSyncingRight = false;
                });
            }

        } else if (currentViewMode === 'redline') {
            const blocks = (comparisonData.redline_blocks || []).filter(b => {
                if (onlyDiffs && b.type === 'equal') return false;
                if (query) {
                    const combined = (b.segments || []).map(x => x.text).join('').toLowerCase();
                    return combined.includes(query);
                }
                return true;
            });

            if (blocks.length === 0) {
                viewerContainer.innerHTML = `<div style="padding: 36px; text-align: center; color: var(--text-muted);">Nenhum trecho encontrado para os filtros selecionados.</div>`;
                return;
            }

            const linesHtml = blocks.map(b => {
                let rowClass = '';
                if (b.type === 'delete') rowClass = 'line-delete';
                else if (b.type === 'insert') rowClass = 'line-insert';
                else if (b.type === 'replace') rowClass = 'line-replace';

                const numLabel = `${b.line_a ?? '-'} → ${b.line_b ?? '-'}`;
                return `
                    <div class="redline-line-row ${rowClass}">
                        <span class="redline-line-nums">${numLabel}</span>
                        <div class="redline-line-text">${renderSegmentsHtml(b.segments) || '&nbsp;'}</div>
                    </div>
                `;
            }).join('');

            viewerContainer.innerHTML = `
                <div class="redline-doc-wrapper">
                    <div class="redline-doc-sheet">
                        <div class="redline-doc-header">
                            <span>Documento Unificado (Redline): ${escapeHtml(s.filename_a)} → ${escapeHtml(s.filename_b)}</span>
                            <span class="rich-doc-badge">Inserções em verde • Exclusões tachadas em vermelho</span>
                        </div>
                        <div class="redline-doc-body">${linesHtml}</div>
                    </div>
                </div>
            `;

        } else {
            // Modo Plain Text (Linha a linha)
            const blocks = (comparisonData.side_by_side_blocks || []).filter(b => {
                if (onlyDiffs && b.type === 'equal') return false;
                if (query) {
                    const hayA = (b.text_a || '').toLowerCase();
                    const hayB = (b.text_b || '').toLowerCase();
                    return hayA.includes(query) || hayB.includes(query);
                }
                return true;
            });

            if (blocks.length === 0) {
                viewerContainer.innerHTML = `<div style="padding: 36px; text-align: center; color: var(--text-muted);">Nenhum trecho encontrado para os filtros selecionados.</div>`;
                return;
            }

            const rowsHtml = blocks.map(b => {
                if (b.type === 'equal') {
                    return `
                        <tr>
                            <td class="plain-col-num">${b.line_a ?? ''}</td>
                            <td class="plain-col-sign"></td>
                            <td class="plain-col-text">${escapeHtml(b.text_a)}</td>
                            <td class="plain-col-num">${b.line_b ?? ''}</td>
                            <td class="plain-col-sign"></td>
                            <td class="plain-col-text">${escapeHtml(b.text_b)}</td>
                        </tr>`;
                } else if (b.type === 'delete') {
                    return `
                        <tr>
                            <td class="plain-col-num">${b.line_a ?? ''}</td>
                            <td class="plain-col-sign" style="color:#DC2626;">-</td>
                            <td class="plain-col-text plain-cell-delete">${renderSegmentsHtml(b.segments_a)}</td>
                            <td class="plain-col-num"></td>
                            <td class="plain-col-sign"></td>
                            <td class="plain-col-text plain-cell-empty"></td>
                        </tr>`;
                } else if (b.type === 'insert') {
                    return `
                        <tr>
                            <td class="plain-col-num"></td>
                            <td class="plain-col-sign"></td>
                            <td class="plain-col-text plain-cell-empty"></td>
                            <td class="plain-col-num">${b.line_b ?? ''}</td>
                            <td class="plain-col-sign" style="color:#16A34A;">+</td>
                            <td class="plain-col-text plain-cell-insert">${renderSegmentsHtml(b.segments_b)}</td>
                        </tr>`;
                } else {
                    return `
                        <tr>
                            <td class="plain-col-num">${b.line_a ?? ''}</td>
                            <td class="plain-col-sign" style="color:#D97706;">~</td>
                            <td class="plain-col-text plain-cell-delete">${renderSegmentsHtml(b.segments_a)}</td>
                            <td class="plain-col-num">${b.line_b ?? ''}</td>
                            <td class="plain-col-sign" style="color:#16A34A;">~</td>
                            <td class="plain-col-text plain-cell-insert">${renderSegmentsHtml(b.segments_b)}</td>
                        </tr>`;
                }
            }).join('');

            viewerContainer.innerHTML = `
                <div class="plain-diff-wrapper">
                    <table class="plain-diff-table">
                        <thead>
                            <tr>
                                <th style="width:44px;text-align:right;">#</th>
                                <th style="width:26px;"></th>
                                <th>${escapeHtml(s.filename_a)} (Texto Puro)</th>
                                <th style="width:44px;text-align:right;">#</th>
                                <th style="width:26px;"></th>
                                <th>${escapeHtml(s.filename_b)} (Texto Puro)</th>
                            </tr>
                        </thead>
                        <tbody>${rowsHtml}</tbody>
                    </table>
                </div>
            `;
        }
    }

    chkOnlyDiffs.addEventListener('change', renderVisualComparison);
    visualSearchInput.addEventListener('input', renderVisualComparison);

    // --- 12. Renderização da Tabela Analítica de Divergências ---
    function renderDiffTable(rows) {
        const tbody = document.getElementById('text-diff-table-tbody');
        const query = (tableSearchInput.value || '').trim().toLowerCase();

        const filtered = rows.filter(r => {
            if (!query) return true;
            return (
                (r.change_type || '').toLowerCase().includes(query) ||
                (r.text_a || '').toLowerCase().includes(query) ||
                (r.text_b || '').toLowerCase().includes(query) ||
                String(r.line_a).includes(query) ||
                String(r.line_b).includes(query)
            );
        });

        if (filtered.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align: center; padding: 28px; color: var(--text-muted);">
                        ${rows.length === 0 ? 'Nenhuma divergência encontrada — os documentos são idênticos!' : 'Nenhuma divergência corresponde ao filtro digitado.'}
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = filtered.map(r => {
            const contentA = r.segments_a && r.segments_a.length
                ? renderSegmentsHtml(r.segments_a)
                : `<span style="color:var(--text-muted);font-style:italic;">${escapeHtml(r.text_a)}</span>`;
            const contentB = r.segments_b && r.segments_b.length
                ? renderSegmentsHtml(r.segments_b)
                : `<span style="color:var(--text-muted);font-style:italic;">${escapeHtml(r.text_b)}</span>`;

            const badgeClass = r.badge_class === 'success' ? 'status-badge-ok' : 'status-badge-diff';

            return `
                <tr>
                    <td><span class="key-code">#${r.diff_id}</span></td>
                    <td style="text-align:center;"><span class="${badgeClass}">${escapeHtml(r.change_type)}</span></td>
                    <td style="text-align:center;"><span class="badge-line">${r.line_a} → ${r.line_b}</span></td>
                    <td style="white-space:pre-wrap;word-break:break-word;">${contentA}</td>
                    <td style="white-space:pre-wrap;word-break:break-word;">${contentB}</td>
                </tr>
            `;
        }).join('');
    }

    tableSearchInput.addEventListener('input', () => {
        if (comparisonData) {
            renderDiffTable(comparisonData.diff_table_rows || []);
        }
    });

    // --- 13. Renderização da Tabela de Analytics e Estatísticas ---
    function renderStatsTable(stats, summary) {
        document.getElementById('th-stat-doc-a').textContent = summary.filename_a || 'Documento Original';
        document.getElementById('th-stat-doc-b').textContent = summary.filename_b || 'Documento Novo';

        const tbody = document.getElementById('text-stats-tbody');
        tbody.innerHTML = stats.map(st => {
            let diffBadge = '<span class="badge-line">Sem variação (0)</span>';
            if (st.diff > 0) {
                diffBadge = `<span class="status-badge-ok">+${st.diff.toLocaleString('pt-BR')} ${escapeHtml(st.unit)}</span>`;
            } else if (st.diff < 0) {
                diffBadge = `<span class="status-badge-diff">${st.diff.toLocaleString('pt-BR')} ${escapeHtml(st.unit)}</span>`;
            }

            const valA = typeof st.val_a === 'number' ? st.val_a.toLocaleString('pt-BR') : escapeHtml(st.val_a);
            const valB = typeof st.val_b === 'number' ? st.val_b.toLocaleString('pt-BR') : escapeHtml(st.val_b);

            return `
                <tr>
                    <td><strong>${escapeHtml(st.metric)}</strong></td>
                    <td style="text-align:center;font-weight:600;">${valA}</td>
                    <td style="text-align:center;font-weight:600;">${valB}</td>
                    <td style="text-align:center;">${diffBadge}</td>
                </tr>
            `;
        }).join('');
    }

    // --- 14. Controle de Abas na Seção de Resultados ---
    const tabBtns = document.querySelectorAll('#text-results-tabs .result-nav-tab-btn');
    const paneVisual = document.getElementById('text-pane-visual');
    const paneTable = document.getElementById('text-pane-table');
    const paneStats = document.getElementById('text-pane-stats');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            paneVisual.style.display = target === 'visual' ? 'block' : 'none';
            paneTable.style.display = target === 'table' ? 'block' : 'none';
            paneStats.style.display = target === 'stats' ? 'block' : 'none';
        });
    });

    // --- 15. Botão de Reset ("Comparar Novos Documentos") ---
    btnReset.addEventListener('click', () => {
        stepResults.style.display = 'none';
        document.getElementById('text-step-upload').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    // --- 16. Reagir a mudanças de idioma ---
    window.addEventListener('validaiLanguageChanged', () => {
        if (comparisonData) {
            renderAllResults(comparisonData);
        }
    });
});

