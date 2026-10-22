import os
import io
import uuid
import app

def test_full_pipeline():
    print("Iniciando testes integrados da aplicacao SplitC...")
    client = app.app.test_client()

    # Configura sessao Pro para testes de integracao com arquivos grandes (47 colunas)
    with client.session_transaction() as sess:
        sess['user_id'] = 'mock_pro_test'
        sess['user_email'] = 'pro@validai.app.br'

    # 1. Teste da rota inicial e favicon
    res = client.get('/')
    assert res.status_code == 200, f"Falha GET /: {res.status_code}"
    print("[OK] GET / funcionando perfeitamente (HTTP 200)")

    res_fav = client.get('/favicon.ico')
    assert res_fav.status_code == 200, f"Falha GET /favicon.ico: {res_fav.status_code}"
    assert len(res_fav.data) > 0
    assert 'image/vnd.microsoft.icon' in res_fav.headers.get('Content-Type', '')
    assert 'public' in res_fav.headers.get('Cache-Control', '')

    for size in ['48x48', '96x96', '192x192']:
        res_png = client.get(f'/static/images/favicon-{size}.png')
        assert res_png.status_code == 200, f"Falha GET favicon-{size}.png"
        assert 'image/png' in res_png.headers.get('Content-Type', '')

    print("[OK] GET /favicon.ico e favicons múltiplos de 48px funcionando perfeitamente (HTTP 200)")

    # 2. Teste de Upload dos arquivos de teste
    with open('planilha_antiga.xlsx', 'rb') as fa, open('planilha_nova.xlsx', 'rb') as fb:
        data = {
            'file_a': (io.BytesIO(fa.read()), 'planilha_antiga.xlsx'),
            'file_b': (io.BytesIO(fb.read()), 'planilha_nova.xlsx')
        }
        res = client.post('/api/upload-headers', data=data, content_type='multipart/form-data')
    
    assert res.status_code == 200, f"Falha POST /api/upload-headers: {res.status_code}"
    upload_res = res.get_json()
    assert 'session_id' in upload_res
    session_id = upload_res['session_id']
    print(f"[OK] Upload e leitura de cabecalhos realizado. Sessao: {session_id}")
    print(f"  Colunas detectadas em A: {len(upload_res['cols_a'])}")
    print(f"  Colunas detectadas em B: {len(upload_res['cols_b'])}")
    print(f"  Mapeamento de Data_Fechamento: {upload_res['column_mapping'].get('Data_Fechamento')}")

    # 2.1 Teste de Carregamento de Exemplo de Planilhas (/api/sheets/load-example)
    res_sheets_ex = client.post('/api/sheets/load-example')
    assert res_sheets_ex.status_code == 200, f"Falha POST /api/sheets/load-example: {res_sheets_ex.status_code}"
    sheets_ex_json = res_sheets_ex.get_json()
    assert 'session_id' in sheets_ex_json
    assert sheets_ex_json['rows_a_count'] == 11
    assert sheets_ex_json['rows_b_count'] == 11
    assert 'ID_Pedido' in sheets_ex_json['suggested_keys']
    print("[OK] Carregamento de exemplo demonstrativo de planilhas (/api/sheets/load-example) validado com sucesso!")

    # 3. Teste com seletor único da esquerda (sem colunas complementares)
    compare_payload_single = {
        'session_id': session_id,
        'primary_key_a': 'SEQ_COM_SUM_VND',
        'primary_key_b': 'SEQ_COM_SUM_VND',
        'secondary_keys_a': [],
        'normalize_currency': True,
        'normalize_dates': True,
        'ignore_case': True,
        'trim_spaces': True,
        'column_mapping': upload_res['column_mapping']
    }
    res = client.post('/api/compare', json=compare_payload_single)
    assert res.status_code == 200
    comp_single = res.get_json()
    assert comp_single['summary']['is_identical'] is True
    print("[OK] Teste com apenas a chave principal da esquerda: 100% identico")

    # 4. Teste com 1 coluna complementar na direita (ex: DATA_VENDA)
    compare_payload_one_sec = dict(compare_payload_single)
    compare_payload_one_sec['secondary_keys_a'] = ['DATA_VENDA']
    res = client.post('/api/compare', json=compare_payload_one_sec)
    assert res.status_code == 200
    comp_one = res.get_json()
    assert comp_one['summary']['is_identical'] is True
    print("[OK] Teste com 1 coluna complementar (DATA_VENDA): 100% identico")

    # 5. Teste com 2 ou mais colunas complementares na direita (ex: DATA_VENDA e FILIAL)
    compare_payload_multi_sec = dict(compare_payload_single)
    compare_payload_multi_sec['secondary_keys_a'] = ['DATA_VENDA', 'FILIAL']
    res = client.post('/api/compare', json=compare_payload_multi_sec)
    assert res.status_code == 200
    comp_multi = res.get_json()
    assert comp_multi['summary']['is_identical'] is True
    assert comp_multi['summary']['secondary_keys_a'] == ['DATA_VENDA', 'FILIAL']
    print("[OK] Teste com 2 colunas complementares (DATA_VENDA + FILIAL): 100% identico")

    # 6. Teste com divergencias intencionais (desativando normalizacao de moedas)
    compare_payload_diff = dict(compare_payload_multi_sec)
    compare_payload_diff['normalize_currency'] = False

    res = client.post('/api/compare', json=compare_payload_diff)
    assert res.status_code == 200
    comp_res_diff = res.get_json()
    print("[OK] Comparacao sem normalizacao de moeda (cenario com divergencias):")
    print(f"  Bases identicas? {comp_res_diff['summary']['is_identical']}")
    print(f"  Linhas divergentes: {comp_res_diff['summary']['different_rows_count']}")
    print(f"  Celulas divergentes: {comp_res_diff['summary']['total_cells_diff']}")
    assert comp_res_diff['summary']['is_identical'] is False
    assert len(comp_res_diff['diff_preview']) > 0

    # 7. Teste do download do relatorio Excel gerado com as celulas pintadas
    report_id = comp_res_diff['report_id']
    res_down = client.get(f'/api/download-report/{report_id}')
    assert res_down.status_code == 200
    assert len(res_down.data) > 10000, "Relatorio Excel gerado esta vazio ou corrompido!"

    # Valida que o Excel gerado contém as abas esperadas, incluindo a nova 3ª aba 'Sumarização Financeira'
    import openpyxl
    wb_test = openpyxl.load_workbook(io.BytesIO(res_down.data))
    assert 'Divergências Detalhadas' in wb_test.sheetnames
    assert 'Sumarização Financeira' in wb_test.sheetnames, "Aba 'Sumarização Financeira' deve existir quando houver divergências!"
    
    # Valida presença da logo no Resumo
    ws_resumo = wb_test['Resumo da Validação']
    assert len(ws_resumo._images) > 0, "Logo SplitC deve estar presente lateralmente na aba de resumo!"
    print(f"[OK] Logo da SplitC confirmada no Excel ({len(ws_resumo._images)} imagem inserida).")

    # Valida cabeçalhos e cores (#4FD580)
    ws_test = wb_test['Divergências Detalhadas']
    headers_test = [ws_test.cell(row=1, column=i).value for i in range(1, 6)]
    expected_headers = ["Chave Identificadora", "Linha", "Coluna", "Valor Base Antiga", "Valor Base Nova"]
    assert headers_test == expected_headers, f"Headers incorretos: {headers_test} vs {expected_headers}"
    assert ws_test.cell(row=2, column=2).value is not None, "Coluna Linha vazia na linha 2"
    assert ws_test.cell(row=1, column=1).fill.start_color.rgb == '004FD580', "Cabeçalho deve usar a cor #4FD580!"

    # Valida a 3ª aba 'Sumarização Financeira'
    ws_fin = wb_test['Sumarização Financeira']
    fin_headers = [ws_fin.cell(row=1, column=i).value for i in range(1, 9)]
    expected_fin_headers = [
        "Coluna Base Antiga", "Coluna Base Nova", "Total Base Antiga (R$)", "Total Base Nova (R$)",
        "Diferença (Nova - Antiga)", "% Variação", "Situação", "Qtd. Linhas Divergentes"
    ]
    assert fin_headers == expected_fin_headers, f"Cabeçalhos da aba financeira incorretos: {fin_headers}"
    assert ws_fin.cell(row=1, column=1).fill.start_color.rgb == '004FD580', "Cabeçalhos da aba financeira devem usar #4FD580!"
    assert ws_fin.cell(row=2, column=3).value is not None, "Total da Base Antiga deve estar preenchido!"
    print(f"[OK] 3ª Aba 'Sumarização Financeira' confirmada com cabeçalhos em #4FD580: {fin_headers}")

    # Valida que em bases idênticas a 3ª aba 'Sumarização Financeira' NÃO é criada
    report_id_single = comp_single['report_id']
    res_down_single = client.get(f'/api/download-report/{report_id_single}')
    wb_single = openpyxl.load_workbook(io.BytesIO(res_down_single.data))
    assert 'Sumarização Financeira' not in wb_single.sheetnames, "Aba financeira NÃO deve existir em bases 100% idênticas!"
    print("[OK] Verificado: em bases 100% idênticas, a terceira aba não é criada (mantida estrutura enxuta).")

    # 8. Teste de Mapeamento Manual de Colunas com nomes completamente diferentes (+ Adicionar Coluna)
    # Simula o usuário adicionando manualmente correspondências que o fuzzy matching não detectou
    import pandas as pd
    df_custom_a = pd.DataFrame({
        'MATRICULA_REF': ['M001', 'M002'],
        'SALARIO_BASE': [5000.0, 7500.0],
        'SETOR_ATUACAO': ['Financeiro', 'TI']
    })
    df_custom_b = pd.DataFrame({
        'COD_FUNCIONARIO': ['M001', 'M002'],
        'REMUNERACAO_BRUTA': ['5.000,00', '7.500,00'],
        'DEPARTAMENTO': ['Financeiro', 'TI']
    })
    buf_a = io.BytesIO()
    buf_b = io.BytesIO()
    with pd.ExcelWriter(buf_a, engine='openpyxl') as writer:
        df_custom_a.to_excel(writer, index=False)
    with pd.ExcelWriter(buf_b, engine='openpyxl') as writer:
        df_custom_b.to_excel(writer, index=False)
    buf_a.seek(0)
    buf_b.seek(0)

    data_custom = {
        'file_a': (buf_a, 'base_antiga_custom.xlsx'),
        'file_b': (buf_b, 'base_nova_custom.xlsx')
    }
    res_upload_custom = client.post('/api/upload-headers', data=data_custom, content_type='multipart/form-data')
    assert res_upload_custom.status_code == 200
    custom_session = res_upload_custom.get_json()

    # O fuzzy matching não mapeia porque os nomes são 100% diferentes
    assert len(custom_session['column_mapping']) == 0

    # Simula o mapeamento manual pelo botão '+' do front-end
    manual_custom_mapping = {
        'MATRICULA_REF': 'COD_FUNCIONARIO',
        'SALARIO_BASE': 'REMUNERACAO_BRUTA',
        'SETOR_ATUACAO': 'DEPARTAMENTO'
    }

    res_compare_custom = client.post('/api/compare', json={
        'session_id': custom_session['session_id'],
        'primary_key_a': 'MATRICULA_REF',
        'primary_key_b': 'COD_FUNCIONARIO',
        'secondary_keys_a': [],
        'normalize_currency': True,
        'normalize_dates': True,
        'ignore_case': True,
        'trim_spaces': True,
        'column_mapping': manual_custom_mapping
    })
    assert res_compare_custom.status_code == 200
    custom_result = res_compare_custom.get_json()
    assert custom_result['summary']['is_identical'] is True
    assert custom_result['summary']['total_columns_compared'] == 3
    # 9. Teste da feature de Limpar Mapeamentos e selecionar apenas colunas desejadas
    # Simula o usuário clicando no botão vermelho de Limpar Mapeamentos e escolhendo apenas 1 coluna
    res_compare_cleared = client.post('/api/compare', json={
        'session_id': session_id,
        'primary_key_a': 'SEQ_COM_SUM_VND',
        'primary_key_b': 'SEQ_COM_SUM_VND',
        'secondary_keys_a': [],
        'normalize_currency': True,
        'normalize_dates': True,
        'ignore_case': True,
        'trim_spaces': True,
        'column_mapping': {'Data_Fechamento': 'Data Fechametno'}  # Apenas 1 coluna selecionada pelo usuário
    })
    assert res_compare_cleared.status_code == 200
    cleared_result = res_compare_cleared.get_json()
    assert cleared_result['summary']['total_columns_compared'] == 1, f"Esperado 1 coluna comparada, obtido: {cleared_result['summary']['total_columns_compared']}"
    print("[OK] Teste de Limpar Mapeamento e comparar apenas colunas selecionadas: 1 coluna comparada com sucesso!")

    # 10. Teste da página Validador de Texto (/validador-texto) e rotas de comparação (.txt, .docx, .pdf) + Exportação PDF
    res_txt_page = client.get('/validador-texto')
    assert res_txt_page.status_code == 200, f"Falha GET /validador-texto: {res_txt_page.status_code}"
    html_txt_page = res_txt_page.data.decode('utf-8')
    assert 'Rich text' in html_txt_page
    assert 'Redline' in html_txt_page
    assert 'Plain text' in html_txt_page
    assert 'OCR' not in html_txt_page
    print("[OK] GET /validador-texto renderizado com os 3 modos (Rich text, Redline, Plain text) e sem Imagem/OCR!")

    # Teste 10.1: Upload de arquivos .docx reais
    import docx
    doc_a_buf = io.BytesIO()
    doc_a = docx.Document()
    doc_a.add_paragraph("Contrato de Prestação de Serviços ValidAí")
    doc_a.add_paragraph("Cláusula 1: O valor mensal será de R$ 3.000,00.")
    doc_a.add_paragraph("Cláusula 2: Vigência de 12 meses.")
    doc_a.save(doc_a_buf)
    doc_a_buf.seek(0)

    doc_b_buf = io.BytesIO()
    doc_b = docx.Document()
    doc_b.add_paragraph("Contrato de Prestação de Serviços ValidAí")
    doc_b.add_paragraph("Cláusula 1: O valor mensal será de R$ 4.500,00.")
    doc_b.add_paragraph("Cláusula 3: Foro da comarca de São Paulo.")
    doc_b.save(doc_b_buf)
    doc_b_buf.seek(0)

    res_docx_cmp = client.post(
        '/api/text/compare',
        data={
            'file_a': (doc_a_buf, 'contrato_antigo.docx'),
            'file_b': (doc_b_buf, 'contrato_novo.docx'),
            'trim_spaces': 'true',
            'ignore_case': 'false',
            'diff_granularity': 'word'
        },
        content_type='multipart/form-data'
    )
    assert res_docx_cmp.status_code == 200, f"Falha POST /api/text/compare (.docx): {res_docx_cmp.status_code}"
    docx_json = res_docx_cmp.get_json()
    assert docx_json['summary']['is_identical'] is False
    assert docx_json['summary']['file_type_a'] == 'DOCX'
    assert docx_json['summary']['total_diff_blocks'] >= 2
    assert 'report_id' in docx_json

    # Verifica download do relatório PDF gerado
    pdf_report_id = docx_json['report_id']
    res_pdf_down = client.get(f'/api/text/download-pdf/{pdf_report_id}')
    assert res_pdf_down.status_code == 200, f"Falha download PDF: {res_pdf_down.status_code}"
    assert res_pdf_down.data.startswith(b'%PDF-'), "Arquivo baixado não é um PDF válido!"
    assert len(res_pdf_down.data) > 1500
    print(f"[OK] Comparação de .docx e exportação de relatório PDF validada ({len(res_pdf_down.data)} bytes)!")

    # Teste 10.2: Upload de arquivos .pdf reais (usando o próprio PDF gerado ou criando um PDF de teste)
    pdf_a_buf = io.BytesIO(res_pdf_down.data)
    pdf_b_buf = io.BytesIO(res_pdf_down.data)
    res_pdf_cmp = client.post(
        '/api/text/compare',
        data={
            'file_a': (pdf_a_buf, 'relatorio_v1.pdf'),
            'file_b': (pdf_b_buf, 'relatorio_v2.pdf'),
        },
        content_type='multipart/form-data'
    )
    assert res_pdf_cmp.status_code == 200, f"Falha POST /api/text/compare (.pdf): {res_pdf_cmp.status_code}"
    pdf_cmp_json = res_pdf_cmp.get_json()
    assert pdf_cmp_json['summary']['file_type_a'] == 'PDF'
    assert pdf_cmp_json['summary']['is_identical'] is True
    print("[OK] Leitura e comparação de arquivos .pdf funcionando perfeitamente!")

    # 11. Teste da página "Como usar?" (/como-usar) com Toggle Planilhas / Texto
    res_guide = client.get('/como-usar')
    assert res_guide.status_code == 200, f"Falha GET /como-usar: {res_guide.status_code}"
    html_guide = res_guide.data.decode('utf-8')
    assert 'btn-guide-planilhas' in html_guide
    assert 'btn-guide-texto' in html_guide
    assert 'btn-guide-cadastros' in html_guide
    assert 'btn-guide-xml' in html_guide
    assert 'guide-view-planilhas' in html_guide
    assert 'guide-view-texto' in html_guide
    assert 'guide-view-cadastros' in html_guide
    assert 'guide-view-xml' in html_guide
    print("[OK] GET /como-usar renderizado com seletor das 4 ferramentas (Planilhas, Texto, Cadastros, XML) e todos os guias!")

    # 12. Teste do Dropdown de Idiomas (PT, ES, EN) e Internacionalização (i18n) em todas as páginas
    res_i18n_js = client.get('/static/js/i18n.js')
    assert res_i18n_js.status_code == 200, f"Falha GET /static/js/i18n.js: {res_i18n_js.status_code}"
    i18n_content = res_i18n_js.data.decode('utf-8')
    assert 'pt:' in i18n_content, "Dicionário PT ausente em i18n.js"
    assert 'es:' in i18n_content, "Dicionário ES ausente em i18n.js"
    assert 'en:' in i18n_content, "Dicionário EN ausente em i18n.js"
    print("[OK] Arquivo estático i18n.js carregado com sucesso contendo os 3 idiomas (PT, ES, EN)!")

    # Checar presença do dropdown e scripts em /, /validador-texto e /como-usar
    pages_to_check = [
        ('/', 'Validador Planilhas'),
        ('/validador-texto', 'Validador Texto'),
        ('/validador-cadastros', 'Higienizador de Cadastros'),
        ('/validador-xml', 'Conciliador de XML'),
        ('/como-usar', 'Como Usar')
    ]
    for path, label in pages_to_check:
        res_p = client.get(path)
        assert res_p.status_code == 200, f"Falha GET {path}: {res_p.status_code}"
        html_p = res_p.data.decode('utf-8')
        assert 'lang-dropdown-wrapper' in html_p, f"Dropdown de idiomas ausente na página {label} ({path})"
        assert 'lang-toggle-btn' in html_p, f"Botão de alternância de idioma ausente na página {label} ({path})"
        assert 'data-lang="pt"' in html_p, f"Opção Português ausente na página {label} ({path})"
        assert 'data-lang="es"' in html_p, f"Opção Espanhol ausente na página {label} ({path})"
        assert 'data-lang="en"' in html_p, f"Opção Inglês ausente na página {label} ({path})"
        assert 'i18n.js' in html_p, f"Script i18n.js não importado na página {label} ({path})"
        assert 'data-i18n=' in html_p, f"Atributos data-i18n ausentes na página {label} ({path})"
        assert 'data-i18n="footer_copyright"' in html_p, f"Footer com data-i18n ausente na página {label} ({path})"
        print(f"[OK] Página {label} ({path}) validada com dropdown de idiomas e i18n!")

    # 13. Teste do Menu Dropdown de Soluções ("Mais Validadores")
    for path, label in pages_to_check:
        res_p = client.get(path)
        assert res_p.status_code == 200
        html_p = res_p.data.decode('utf-8')
        assert 'nav-solutions-dropdown' in html_p, f"Dropdown Mais Validadores ausente em {label}"
        assert 'nav-solutions-btn' in html_p, f"Botão Mais Validadores ausente em {label}"
        assert 'nav-solutions-menu' in html_p, f"Menu Mais Validadores ausente em {label}"
        assert '/validador-cadastros' in html_p, f"Item Higienizador de Cadastros ausente em {label}"
        assert '/validador-xml' in html_p, f"Item Conciliador XML ausente em {label}"
        assert '/conciliador-taxas' in html_p, f"Item Conciliação Taxas OFX ausente em {label}"
        assert '/auditoria-rh' in html_p, f"Item Auditoria RH ausente em {label}"
        assert '/validador-json' in html_p, f"Item Comparador JSON ausente em {label}"
        assert 'badge_coming_soon' in html_p, f"Badge 'Em breve' ausente em {label}"
        assert 'Em breve' in html_p, f"Texto da badge 'Em breve' ausente em {label}"
    print("[OK] Menu Dropdown 'Mais Validadores' validado com os 5 novos módulos em todas as páginas!")

    # 14. Teste completo do Higienizador de Cadastros (/validador-cadastros)
    # A. Renderização da página e seus elementos de UI
    res_cad = client.get('/validador-cadastros')
    assert res_cad.status_code == 200, f"Falha GET /validador-cadastros: {res_cad.status_code}"
    html_cad = res_cad.data.decode('utf-8')
    assert 'drop-cadastros' in html_cad, "Área de upload único ausente"
    assert 'step-config-cadastros' in html_cad, "Card de configurações e regras ausente"
    assert 'step-results-cadastros' in html_cad, "Seção de resultados ausente"
    assert 'kpi-total-rows' in html_cad, "KPI total analisado ausente"
    assert 'kpi-valid-rows' in html_cad, "KPI válidos ausente"
    assert 'kpi-invalid-docs' in html_cad, "KPI docs inválidos ausente"
    assert 'kpi-duplicate-rows' in html_cad, "KPI duplicados ausente"
    assert 'kpi-suspicious-contacts' in html_cad, "KPI contatos suspeitos ausente"
    assert 'kpi-auto-corrections' in html_cad, "KPI auto correções ausente"
    assert 'btn-download-clean' in html_cad, "Botão download base limpa ausente"
    assert 'btn-download-audit' in html_cad, "Botão download auditoria ausente"
    print("[OK] Página /validador-cadastros renderizada com todos os elementos de UI!")

    # B. Teste de Upload de Base de Cadastros e Leitura de Cabeçalhos
    import pandas as pd
    test_cadastros_df = pd.DataFrame({
        'CPF_Cliente': [
            '52998224725',        # 1: CPF Válido
            '1234567890',         # 2: 10 dígitos (recupera zero à esquerda para '01234567890')
            '529.982.247-25',     # 3: Duplicado da linha 1
            '111.111.111-11',     # 4: CPF Inválido (dígitos repetidos)
            '00.000.000/0001-91'  # 5: CNPJ Válido (Banco do Brasil)
        ],
        'Nome_Razao': [
            'MARIA DA SILVA',
            'joão  souza 123',
            'Maria da Silva',
            'Cliente Invalido ---',
            'BANCO DO BRASIL S/A'
        ],
        'Email_Contato': [
            'MARIA@GMAIL.COM',
            'joao@gmial.com',     # Domínio com typo conhecido (@gmial.com)
            'maria@gmail.com',
            'carlos_invalido',    # Sem arroba
            'contato@bb.com.br'
        ],
        'Telefone_Celular': [
            '11987654321',        # Celular SP válido
            '1187654321',         # Fixo SP válido (8 dígitos)
            '11 98765-4321',      # Formatado
            '001234',             # DDD inválido
            '61 3493-9000'        # Fixo Brasília válido
        ],
        'Cidade': ['São Paulo', 'Campinas', 'São Paulo', 'Santos', 'Brasília']
    })
    
    excel_buf = io.BytesIO()
    test_cadastros_df.to_excel(excel_buf, index=False)
    excel_buf.seek(0)

    res_upload_cad = client.post(
        '/api/cadastros/upload-headers',
        data={'file': (excel_buf, 'clientes_teste.xlsx')},
        content_type='multipart/form-data'
    )
    assert res_upload_cad.status_code == 200, f"Falha POST /api/cadastros/upload-headers: {res_upload_cad.status_code}"
    cad_upload_json = res_upload_cad.get_json()
    assert 'session_id' in cad_upload_json
    session_id_cad = cad_upload_json['session_id']
    assert cad_upload_json['total_rows'] == 5
    assert len(cad_upload_json['cols']) == 5
    mapping = cad_upload_json['suggested']
    assert mapping['col_doc'] == 'CPF_Cliente'
    assert mapping['col_name'] == 'Nome_Razao'
    assert mapping['col_email'] == 'Email_Contato'
    assert mapping['col_phone'] == 'Telefone_Celular'
    print("[OK] Upload de base de cadastros e detecção automática de colunas realizado com sucesso!")

    # B.1 Teste de Carregamento de Exemplo de Cadastros (/api/cadastros/load-example)
    res_cad_ex = client.post('/api/cadastros/load-example')
    assert res_cad_ex.status_code == 200, f"Falha POST /api/cadastros/load-example: {res_cad_ex.status_code}"
    cad_ex_json = res_cad_ex.get_json()
    assert 'session_id' in cad_ex_json
    assert cad_ex_json['total_rows'] == 11
    assert cad_ex_json['suggested']['col_doc'] == 'CPF_CNPJ'
    assert cad_ex_json['suggested']['col_name'] == 'Nome_Cliente'
    assert cad_ex_json['suggested']['col_email'] == 'Email'
    assert cad_ex_json['suggested']['col_phone'] == 'Telefone_WhatsApp'
    print("[OK] Carregamento de exemplo demonstrativo de cadastros (/api/cadastros/load-example) validado com sucesso!")

    # C. Teste do Processamento e Regras de Higienização
    process_payload = {
        'session_id': session_id_cad,
        'col_doc': 'CPF_Cliente',
        'col_name': 'Nome_Razao',
        'col_email': 'Email_Contato',
        'col_phone': 'Telefone_Celular',
        'duplicate_keys': ['doc'],
        'doc_format': 'mask',
        'auto_recover_zero': True,
        'name_title_case': True,
        'email_lowercase': True,
        'phone_format': 'mask',
        'remove_duplicates': False
    }
    res_proc = client.post('/api/cadastros/process', json=process_payload)
    assert res_proc.status_code == 200, f"Falha POST /api/cadastros/process: {res_proc.status_code}"
    proc_json = res_proc.get_json()
    assert proc_json['success'] is True
    summary = proc_json['summary']
    assert summary['total_rows'] == 5
    assert summary['invalid_docs_count'] >= 1, "Deveria detectar CPF inválido"
    assert summary['duplicates_count'] >= 1, "Deveria detectar CPF duplicado"
    assert summary['suspicious_contacts_count'] >= 1, "Deveria detectar typo no email e telefone com erro"
    assert summary['auto_corrections_count'] >= 1, "Deveria registrar correções automáticas de zeros/nomes/emails"
    print(f"[OK] Processamento de cadastros realizado: {summary['valid_count']} válidos, {summary['invalid_docs_count']} inválidos, {summary['duplicates_count']} duplicados, {summary['auto_corrections_count']} correções automáticas.")

    # D. Teste de Download da Base 100% Higienizada (Excel)
    report_id_cad = proc_json['report_id']
    res_down_clean = client.get(f'/api/cadastros/download-clean/{report_id_cad}')
    assert res_down_clean.status_code == 200, f"Falha GET download-clean: {res_down_clean.status_code}"
    assert len(res_down_clean.data) > 3000, "Base limpa gerada está vazia"
    wb_clean = openpyxl.load_workbook(io.BytesIO(res_down_clean.data))
    assert 'Base Higienizada' in wb_clean.sheetnames
    print("[OK] Download da Base 100% Higienizada gerado e validado com sucesso!")

    # E. Teste de Download do Relatório de Auditoria com Células Pintadas e Logo
    res_down_audit = client.get(f'/api/cadastros/download-audit/{report_id_cad}')
    assert res_down_audit.status_code == 200, f"Falha GET download-audit: {res_down_audit.status_code}"
    assert len(res_down_audit.data) > 5000, "Relatório de auditoria gerado está vazio"
    wb_audit = openpyxl.load_workbook(io.BytesIO(res_down_audit.data))
    assert 'Resumo da Auditoria' in wb_audit.sheetnames
    assert any('Base Auditada' in s for s in wb_audit.sheetnames)
    assert any('Inconsist' in s for s in wb_audit.sheetnames)
    ws_aud_resumo = wb_audit['Resumo da Auditoria']
    assert len(ws_aud_resumo._images) >= 1, "Logo ValidAí ausente no Resumo da Auditoria!"
    print("[OK] Relatório de Auditoria gerado com células pintadas, 3 abas e Logo ValidAí!")

    # F. Teste de Coluna Incompatível (ex: IDCOLABORADOR com números aleatórios curtos como '555722')
    df_incompat = pd.DataFrame({
        'IDCOLABORADOR': [555722, 10293, 88392, 44021, 99120],  # 5-6 dígitos (IDs numéricos com dtype int64)
        'NMCLIENTE': ['MARIA SILVA', 'JOAO SOUZA', 'ANA COSTA', 'PEDRO LIMA', 'LUCAS DIAS'],
        'EMAIL': ['m@test.com', 'j@test.com', 'a@test.com', 'p@test.com', 'l@test.com']
    })
    buf_incompat = io.BytesIO()
    df_incompat.to_csv(buf_incompat, index=False)
    buf_incompat.seek(0)
    res_up_inc = client.post(
        '/api/cadastros/upload-headers',
        data={'file': (buf_incompat, 'base_com_ids.csv')},
        content_type='multipart/form-data'
    )
    assert res_up_inc.status_code == 200
    inc_json = res_up_inc.get_json()
    sess_inc = inc_json['session_id']

    # Tenta processar passando a coluna IDCOLABORADOR como CPF/CNPJ
    res_proc_inc = client.post('/api/cadastros/process', json={
        'session_id': sess_inc,
        'col_doc': 'IDCOLABORADOR',
        'col_name': 'NMCLIENTE',
        'col_email': 'EMAIL',
        'duplicate_keys': ['doc']
    })
    assert res_proc_inc.status_code == 400, f"Deveria rejeitar com 400, mas retornou {res_proc_inc.status_code}"
    err_data = res_proc_inc.get_json()
    assert 'não bate com a referência de CPF / CNPJ' in err_data['error']
    assert 'IDCOLABORADOR' in err_data['error']
    print(f"[OK] Detecção de coluna incompatível ('IDCOLABORADOR' com valores de 6 dígitos) validada: {err_data['error'][:80]}...")

    # 15. Teste completo do Conciliador de XML de Notas Fiscais (/validador-xml)
    # A. Renderização da página e elementos de UI
    res_xml_page = client.get('/validador-xml')
    assert res_xml_page.status_code == 200, f"Falha GET /validador-xml: {res_xml_page.status_code}"
    html_xml = res_xml_page.data.decode('utf-8')
    assert 'drop-xml-pack' in html_xml, "Dropzone do pacote XML ausente"
    assert 'drop-xml-sheet' in html_xml, "Dropzone da planilha financeira ausente"
    assert 'step-config-xml' in html_xml, "Passo 2 de configuração XML ausente"
    assert 'step-results-xml' in html_xml, "Passo 3 de resultados XML ausente"
    assert 'btn-xml-back-step1' in html_xml, "Botão Trocar Arquivo no Passo 2 ausente"
    assert 'btn-xml-download-audit' in html_xml, "Botão download auditoria XML ausente"
    assert 'btn-xml-download-mirror' in html_xml, "Botão download espelho XML ausente"
    print("[OK] Página /validador-xml renderizada com todos os elementos padronizados!")

    # B. Teste de Carregamento de Exemplo (/api/xml/load-example) e Upload Direto (/api/xml/upload)
    res_xml_ex = client.post('/api/xml/load-example')
    assert res_xml_ex.status_code == 200, f"Falha POST /api/xml/load-example: {res_xml_ex.status_code}"
    ex_json = res_xml_ex.get_json()
    assert 'session_id' in ex_json
    assert ex_json['xml_count'] == 6
    assert ex_json['sheet_rows'] == 6
    sess_xml = ex_json['session_id']
    suggested_xml = ex_json['suggested']
    assert suggested_xml['col_nf'] == 'Numero_NF'
    assert suggested_xml['col_val'] == 'Valor_Total_NF'
    assert suggested_xml['col_cnpj'] == 'CNPJ_Fornecedor'
    assert suggested_xml['col_tax'] == 'Total_Impostos'
    print(f"[OK] Pacote de exemplo XML carregado: {ex_json['xml_count']} notas XML extraídas e {ex_json['sheet_rows']} linhas na planilha.")

    # C. Teste de Upload via multipart/form-data (/api/xml/upload) com arquivo .zip e .xlsx
    import tempfile
    import xml_reconciler
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path, zip_name, excel_path, excel_name = xml_reconciler.create_demo_files(tmp_dir)
        with open(zip_path, 'rb') as fz, open(excel_path, 'rb') as fe:
            res_xml_up = client.post(
                '/api/xml/upload',
                data={
                    'xml_files': (io.BytesIO(fz.read()), zip_name),
                    'sheet_file': (io.BytesIO(fe.read()), excel_name)
                },
                content_type='multipart/form-data'
            )
    assert res_xml_up.status_code == 200, f"Falha POST /api/xml/upload: {res_xml_up.status_code}"
    up_xml_json = res_xml_up.get_json()
    assert up_xml_json['xml_count'] == 6
    sess_xml_up = up_xml_json['session_id']
    print("[OK] Upload via multipart/form-data de arquivo .zip + planilha .xlsx validado com sucesso!")

    # D. Teste de Rejeição de Coluna Incompatível no Conciliador de XML
    res_xml_bad_col = client.post('/api/xml/reconcile', json={
        'session_id': sess_xml_up,
        'col_nf': 'Numero_NF',
        'col_val': 'Fornecedor',  # Texto puro no lugar de Valor Total (<vNF>)
        'col_cnpj': 'CNPJ_Fornecedor'
    })
    assert res_xml_bad_col.status_code == 400, f"Deveria rejeitar coluna incompatível com 400, mas retornou {res_xml_bad_col.status_code}"
    bad_col_err = res_xml_bad_col.get_json()
    assert 'Fornecedor' in bad_col_err['error']
    assert 'Valor Monetário (<vNF>)' in bad_col_err['error']
    print(f"[OK] Detecção de coluna incompatível no Conciliador XML validada: {bad_col_err['error'][:80]}...")

    # E. Teste de Conciliação Completa (/api/xml/reconcile)
    res_xml_rec = client.post('/api/xml/reconcile', json={
        'session_id': sess_xml_up,
        'col_nf': 'Numero_NF',
        'col_val': 'Valor_Total_NF',
        'col_cnpj': 'CNPJ_Fornecedor',
        'col_tax': 'Total_Impostos',
        'col_fornecedor': 'Fornecedor',
        'ignore_leading_zeros': True,
        'ignore_cnpj_punct': True,
        'tolerance': 0.05,
        'check_missing_in_excel': True,
        'check_missing_xml': True,
        'check_taxes': True
    })
    assert res_xml_rec.status_code == 200, f"Falha POST /api/xml/reconcile: {res_xml_rec.status_code}"
    rec_json = res_xml_rec.get_json()
    assert rec_json['success'] is True
    xml_sum = rec_json['summary']
    assert xml_sum['total_xmls'] == 6
    assert xml_sum['matched_count'] == 3, f"Esperado 3 conciliadas, obteve {xml_sum['matched_count']}"
    assert xml_sum['divergences_count'] == 2, f"Esperado 2 divergentes, obteve {xml_sum['divergences_count']}"
    assert xml_sum['missing_in_excel_count'] == 1, f"Esperado 1 XML sem lançamento, obteve {xml_sum['missing_in_excel_count']}"
    assert xml_sum['missing_xml_count'] == 1, f"Esperado 1 lançamento sem XML, obteve {xml_sum['missing_xml_count']}"
    print(f"[OK] Conciliação XML executada: {xml_sum['matched_count']} conciliadas, {xml_sum['divergences_count']} divergentes, {xml_sum['missing_in_excel_count']} XML sem Excel, {xml_sum['missing_xml_count']} Excel sem XML.")

    # F. Teste de Download dos 2 Relatórios Excel (Auditoria Pintada + Espelho de XMLs)
    xml_rep_id = rec_json['report_id']
    res_dl_xml_audit = client.get(f'/api/xml/download-audit/{xml_rep_id}')
    assert res_dl_xml_audit.status_code == 200
    assert len(res_dl_xml_audit.data) > 5000
    wb_xml_audit = openpyxl.load_workbook(io.BytesIO(res_dl_xml_audit.data))
    assert 'Resumo da Conciliação' in wb_xml_audit.sheetnames
    assert 'Planilha Auditada' in wb_xml_audit.sheetnames
    assert 'XMLs Sem Lançamento' in wb_xml_audit.sheetnames
    assert 'Divergências de Valor e CNPJ' in wb_xml_audit.sheetnames
    assert len(wb_xml_audit['Resumo da Conciliação']._images) >= 1, "Logo ValidAí ausente no Resumo da Conciliação XML!"
    print("[OK] Relatório Excel de Auditoria Fiscal XML gerado com 4 abas, células pintadas e Logo ValidAí!")

    res_dl_xml_mirror = client.get(f'/api/xml/download-mirror/{xml_rep_id}')
    assert res_dl_xml_mirror.status_code == 200
    assert len(res_dl_xml_mirror.data) > 3000
    wb_xml_mirror = openpyxl.load_workbook(io.BytesIO(res_dl_xml_mirror.data))
    assert 'Espelho Notas Fiscais XML' in wb_xml_mirror.sheetnames
    print("[OK] Planilha Espelho dos XMLs Extraídos gerada e validada com sucesso!")

    # =========================================================================
    # 16. TESTE COMPLETO DO CONCILIADOR DE TAXAS E EXTRATOS (.OFX VS VENDAS ERP)
    # =========================================================================
    print("\n--- Testando Conciliador de Taxas e Extratos (.OFX vs Vendas) ---")

    # A. Carregamento de exemplo demonstrativo (.ofx e .xlsx gerados pelo backend)
    res_ofx_example = client.post('/api/ofx/load-example')
    assert res_ofx_example.status_code == 200, f"Falha POST /api/ofx/load-example: {res_ofx_example.status_code}"
    ofx_ex_data = res_ofx_example.get_json()
    assert 'session_id' in ofx_ex_data
    ofx_sess_id = ofx_ex_data['session_id']
    assert ofx_ex_data['ofx_count'] == 8
    assert ofx_ex_data['sheet_rows'] == 8
    assert ofx_ex_data['suggested']['col_gross_val'] == 'Valor_Bruto'
    assert ofx_ex_data['suggested']['col_id'] == 'ID_Venda_NSU'
    print(f"[OK] Dados de exemplo OFX carregados com sucesso: {ofx_ex_data['ofx_count']} transações bancárias e {ofx_ex_data['sheet_rows']} vendas no PDV.")

    # B. Execução da conciliação com Taxa Esperada de 3.50%
    reconcile_payload = {
        'session_id': ofx_sess_id,
        'col_id': 'ID_Venda_NSU',
        'col_gross_val': 'Valor_Bruto',
        'col_date': 'Data_Venda',
        'col_acquirer': 'Adquirente',
        'expected_rate_pct': 3.5,
        'tolerance_cents': 0.05,
        'date_tolerance_days': 3
    }
    res_ofx_rec = client.post('/api/ofx/reconcile', json=reconcile_payload)
    assert res_ofx_rec.status_code == 200, f"Falha POST /api/ofx/reconcile: {res_ofx_rec.status_code}"
    ofx_rec_data = res_ofx_rec.get_json()
    assert ofx_rec_data['success'] is True
    assert 'report_id' in ofx_rec_data
    ofx_rep_id = ofx_rec_data['report_id']

    kpis = ofx_rec_data['kpis']
    assert kpis['total_sales_count'] == 8
    assert kpis['divergent_fees_count'] == 1, f"Deveria ter 1 venda com taxa a maior (esperado 1, obteve {kpis['divergent_fees_count']})"
    assert kpis['unpaid_sales_count'] == 1, f"Deveria ter 1 venda não repassada (esperado 1, obteve {kpis['unpaid_sales_count']})"
    assert kpis['orphan_credits_count'] == 1, f"Deveria ter 1 crédito avulso no OFX (esperado 1, obteve {kpis['orphan_credits_count']})"
    assert kpis['reconciled_count'] == 6, f"Deveria ter 6 vendas 100% conciliadas (esperado 6, obteve {kpis['reconciled_count']})"
    assert kpis['total_divergence_loss'] == 17.0, f"Prejuízo divergente esperado R$ 17.00, obteve {kpis['total_divergence_loss']}"
    print(f"[OK] Motor de Conciliação validou com precisão: 6 conciliadas, 1 taxa a maior (prejuízo R$ {kpis['total_divergence_loss']}), 1 não repassada e 1 crédito avulso.")

    # C. Download e validação do Relatório de Auditoria Excel (4 abas com células pintadas)
    res_dl_ofx_audit = client.get(f'/api/ofx/download-audit/{ofx_rep_id}')
    assert res_dl_ofx_audit.status_code == 200
    assert len(res_dl_ofx_audit.data) > 5000
    wb_ofx_audit = openpyxl.load_workbook(io.BytesIO(res_dl_ofx_audit.data))
    assert 'Resumo Executivo' in wb_ofx_audit.sheetnames
    assert 'Conciliação Completa' in wb_ofx_audit.sheetnames
    assert 'Divergências e Pendências' in wb_ofx_audit.sheetnames
    assert 'Espelho Extrato OFX' in wb_ofx_audit.sheetnames
    assert len(wb_ofx_audit['Resumo Executivo']._images) >= 1, "Logo ValidAí ausente no Resumo Executivo OFX!"
    print("[OK] Relatório de Auditoria OFX validado com 4 abas, formatação monetária, células pintadas e Logo ValidAí!")

    # D. Download do Espelho Tabulado do Extrato OFX
    res_dl_ofx_mirror = client.get(f'/api/ofx/download-mirror/{ofx_rep_id}')
    assert res_dl_ofx_mirror.status_code == 200
    assert len(res_dl_ofx_mirror.data) > 3000
    wb_ofx_mirror = openpyxl.load_workbook(io.BytesIO(res_dl_ofx_mirror.data))
    assert 'Extrato OFX Tabulado' in wb_ofx_mirror.sheetnames
    print("[OK] Espelho Tabulado do Extrato OFX gerado e validado com sucesso!")

    # =========================================================================
    
    # =========================================================================
    # 16. TESTE COMPLETO DO MÓDULO DE AUDITORIA DE FOLHA E RH (/auditoria-rh)
    # =========================================================================
    print("\n--- Testando Módulo Completo de Auditoria de Folha e RH (/auditoria-rh) ---")
    import rh_auditor

    # A. Renderização da página /auditoria-rh e elementos de UI padronizados
    res_rh_page = client.get('/auditoria-rh')
    assert res_rh_page.status_code == 200, f"Falha GET /auditoria-rh: {res_rh_page.status_code}"
    html_rh = res_rh_page.data.decode('utf-8')
    assert 'drop-ref-file' in html_rh, "Dropzone da Base Referência ausente"
    assert 'drop-audit-file' in html_rh, "Dropzone da Base Auditada ausente"
    assert 'step-config-rh' in html_rh, "Passo 2 de configuração de RH ausente"
    assert 'step-results-rh' in html_rh, "Passo 3 de resultados de RH ausente"
    assert 'btn-rh-upload' in html_rh, "Botão Ler Bases ausente"
    assert 'btn-rh-try-example' in html_rh, "Botão Testar Exemplo ausente"
    assert 'btn-rh-download-audit' in html_rh, "Botão download auditoria RH ausente"
    assert 'v3.3' in html_rh, "Tag de versão v3.3 ausente no rodapé"
    print("[OK] Página /auditoria-rh renderizada com layout de 3 passos, dropzones e v3.3!")

    # B. Teste de Exemplo - Modo Folha (Mês Anterior vs. Atual)
    res_ex_folha = client.post('/api/rh/load-example', json={'mode': 'folha'})
    assert res_ex_folha.status_code == 200, f"Falha POST /api/rh/load-example (folha): {res_ex_folha.status_code}"
    ex_folha_json = res_ex_folha.get_json()
    assert 'session_id' in ex_folha_json
    assert ex_folha_json['rows_ref_count'] == 8
    assert ex_folha_json['rows_audit_count'] == 8
    assert ex_folha_json['suggested_key_ref'] == 'CPF'
    assert ex_folha_json['suggested_key_audit'] == 'CPF'
    sess_folha = ex_folha_json['session_id']
    print(f"[OK] Exemplo de Folha carregado: {ex_folha_json['rows_ref_count']} colaboradores no mês anterior e {ex_folha_json['rows_audit_count']} no mês atual.")

    # C. Execução da Auditoria de Folha
    res_audit_folha = client.post('/api/rh/audit', json={
        'session_id': sess_folha,
        'mode': 'folha',
        'key_ref': 'CPF',
        'key_audit': 'CPF',
        'normalize_cpf': True,
        'ignore_accents': True,
        'variation_threshold': 10.0,
        'column_mapping': ex_folha_json['column_mapping']
    })
    assert res_audit_folha.status_code == 200, f"Falha POST /api/rh/audit (folha): {res_audit_folha.status_code}"
    audit_folha_json = res_audit_folha.get_json()
    assert audit_folha_json['success'] is True
    kpis_f = audit_folha_json['kpis']
    assert kpis_f['total_audited'] == 7, f"Esperado 7 auditados em comum, obteve {kpis_f['total_audited']}"
    assert kpis_f['exclusive_ref_count'] == 1, f"Esperado 1 desligado (Lucas Pereira), obteve {kpis_f['exclusive_ref_count']}"
    assert kpis_f['exclusive_audit_count'] == 1, f"Esperado 1 admitido (Gabriel Mendes), obteve {kpis_f['exclusive_audit_count']}"
    assert kpis_f['critical_variations_count'] >= 1, "Deveria identificar variações atípicas > 10%"
    assert kpis_f['financial_impact'] > 0, "Impacto financeiro deveria refletir aumento líquido da folha"
    assert len(audit_folha_json['financial_summary']) >= 4, "Deveria conter sumarização financeira de todas as colunas monetárias"
    print(f"[OK] Auditoria de Folha executada: {kpis_f['total_audited']} cruzados, {kpis_f['exclusive_ref_count']} desligado, {kpis_f['exclusive_audit_count']} admitido, {kpis_f['critical_variations_count']} variações atípicas.")

    # D. Download do Relatório Excel em 5 Abas Formatadas
    rep_rh_id = audit_folha_json['report_id']
    res_dl_rh = client.get(f'/api/rh/download-report/{rep_rh_id}')
    assert res_dl_rh.status_code == 200, f"Falha GET /api/rh/download-report: {res_dl_rh.status_code}"
    assert len(res_dl_rh.data) > 3000, "Arquivo Excel muito pequeno"
    wb_rh = openpyxl.load_workbook(io.BytesIO(res_dl_rh.data))
    expected_rh_sheets = [
        'Resumo_RH',
        'Divergencias_Detalhadas',
        'Variacoes_Acima_Limite',
        'Desligados_Apenas_Base1',
        'Admitidos_Ou_Indevidos_Base2'
    ]
    for sheet_name in expected_rh_sheets:
        assert sheet_name in wb_rh.sheetnames, f"Aba obrigatória {sheet_name} ausente no Excel de RH!"
    assert len(wb_rh['Resumo_RH']._images) >= 1, "Logo ValidAí ausente no Resumo_RH!"
    print(f"[OK] Relatório Excel de Auditoria de RH validado com 5 abas ({', '.join(expected_rh_sheets)}) e Logo ValidAí!")

    # E. Teste de Exemplo - Modo Benefícios (Ativos RH vs. Fatura Plano de Saúde)
    res_ex_ben = client.post('/api/rh/load-example', json={'mode': 'beneficios'})
    assert res_ex_ben.status_code == 200, f"Falha POST /api/rh/load-example (beneficios): {res_ex_ben.status_code}"
    ex_ben_json = res_ex_ben.get_json()
    assert ex_ben_json['rows_ref_count'] == 8
    assert ex_ben_json['rows_audit_count'] == 8
    sess_ben = ex_ben_json['session_id']

    # F. Execução da Auditoria de Benefícios (Detecção de "Funcionários Fantasmas")
    res_audit_ben = client.post('/api/rh/audit', json={
        'session_id': sess_ben,
        'mode': 'beneficios',
        'key_ref': 'CPF',
        'key_audit': 'CPF_Titular',
        'normalize_cpf': True,
        'ignore_accents': True,
        'variation_threshold': 10.0,
        'column_mapping': {
            'Nome_Colaborador': 'Nome_Segurado',
            'Plano': 'Plano_Saude'
        }
    })
    assert res_audit_ben.status_code == 200, f"Falha POST /api/rh/audit (beneficios): {res_audit_ben.status_code}"
    audit_ben_json = res_audit_ben.get_json()
    kpis_b = audit_ben_json['kpis']
    assert kpis_b['exclusive_audit_count'] == 2, f"Esperado 2 funcionários fantasmas sendo cobrados na fatura, obteve {kpis_b['exclusive_audit_count']}"
    assert kpis_b['exclusive_ref_count'] == 2, f"Esperado 2 ativos no RH sem fatura de benefício, obteve {kpis_b['exclusive_ref_count']}"
    assert kpis_b['total_audited'] == 6, f"Esperado 6 colaboradores auditados em comum, obteve {kpis_b['total_audited']}"
    print(f"[OK] Auditoria de Benefícios validada: {kpis_b['exclusive_audit_count']} funcionários fantasmas identificados e {kpis_b['exclusive_ref_count']} ativos sem benefício!")

    # G. Teste de Upload via multipart/form-data (/api/rh/upload-headers) com normalização inteligente de CPF
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        pref, nref, paud, naud = rh_auditor.create_demo_files(tmp_dir, mode='folha')
        with open(pref, 'rb') as f1, open(paud, 'rb') as f2:
            res_up_rh = client.post(
                '/api/rh/upload-headers',
                data={
                    'file_ref': (io.BytesIO(f1.read()), nref),
                    'file_audit': (io.BytesIO(f2.read()), naud),
                    'mode': 'folha'
                },
                content_type='multipart/form-data'
            )
    assert res_up_rh.status_code == 200, f"Falha POST /api/rh/upload-headers: {res_up_rh.status_code}"
    up_rh_json = res_up_rh.get_json()
    assert up_rh_json['suggested_key_ref'] == 'CPF'
    assert up_rh_json['suggested_key_audit'] == 'CPF'
    assert up_rh_json['is_cpf'] is True
    print("[OK] Upload multipart/form-data de bases de RH validado com sucesso e identificação automática de CPF!")

    # 17. TESTE COMPLETO DE SEO TÉCNICO E SEMÂNTICO (META TAGS, OG, H1, FAQ, JSON-LD, ROBOTS E SITEMAP)
    # =========================================================================
    print("\n--- Testando Otimização de SEO Técnico e Semântico (ValidAí) ---")
    import json as json_mod
    import re

    expected_active_routes = {
        '/': {
            'title': 'ValidAí | Comparador e Validador de Planilhas Excel e CSV Online',
            'description': 'Compare, audite e valide duas planilhas Excel (.xlsx, .xls) ou CSV gratuitamente. Encontre divergências célula por célula e baixe o relatório pintado.',
            'h1': 'Validador e Comparador Inteligente de Planilhas',
        },
        '/validador-texto': {
            'title': 'Comparador e Validador de Textos Online | ValidAí',
            'description': 'Compare dois blocos de texto lado a lado e identifique diferenças, adições e remoções instantaneamente com precisão.',
            'h1': 'Comparador e Validador de Textos e Documentos Online',
        },
        '/validador-cadastros': {
            'title': 'Higienizador de Cadastros: Validar CPF, CNPJ, E-mail e Duplicados | ValidAí',
            'description': 'Limpe e padronize suas bases de dados. Valide CPF/CNPJ, e-mails e remova linhas duplicadas de planilhas automaticamente.',
            'h1': 'Higienizador de Cadastros: Validar CPF, CNPJ, E-mail e Duplicados',
        },
        '/validador-xml': {
            'title': 'Conciliador de Notas Fiscais (XML NFe/NFSe vs Excel) | ValidAí',
            'description': 'Cruze dados de arquivos XML de Notas Fiscais (NFe e NFSe) contra planilhas de controle no Excel de forma automatizada.',
            'h1': 'Conciliador de Notas Fiscais (XML NFe/NFSe vs Excel)',
        },
        '/conciliador-taxas': {
            'title': 'Conciliador de Taxas e Extratos (.OFX vs Vendas) | ValidAí',
            'description': 'Audite taxas de maquininhas (Stone, Cielo, Rede) e repasses de marketplaces contra extratos bancários .OFX.',
            'h1': 'Conciliação de Taxas e Extratos (.OFX vs Vendas)',
        },
                '/auditoria-rh': {
            'title': 'Auditoria de Folha e RH | ValidAí',
            'description': 'Batimento automatizado de folha de pagamento (mês anterior vs. atual) e conciliação de ativos do RH contra faturas de benefícios corporativos.',
            'h1': 'Auditoria de Folha de Pagamento e Benefícios de RH',
        },
        '/como-usar': {
            'title': 'Como Usar o ValidAí | Guia Completo de Validação e Auditoria de Dados',
            'description': 'Aprenda passo a passo como comparar planilhas, higienizar cadastros e conciliar notas fiscais no ValidAí.',
            'h1': 'Como usar o <span class="highlight">ValidAí</span>?',
        },
    }

    for route_path, expected in expected_active_routes.items():
        resp = client.get(route_path)
        assert resp.status_code == 200, f"Rota {route_path} retornou status {resp.status_code}"
        html = resp.data.decode('utf-8')

        # 1. lang="pt-BR"
        assert '<html lang="pt-BR">' in html, f"Falta <html lang=\"pt-BR\"> em {route_path}"

        # 2. Title & Meta Description
        assert f">{expected['title']}</title>" in html, f"Title incorreto em {route_path}"
        assert f'<meta name="description" content="{expected["description"]}">' in html, f"Description incorreta em {route_path}"
        assert '<meta name="robots" content="index, follow">' in html, f"Robots meta ausente em {route_path}"

        # 3. Canonical URL
        expected_canonical = f'<link rel="canonical" href="https://validai.app.br{route_path}">'
        assert expected_canonical in html, f"Canonical ausente ou incorreto em {route_path}"

        # 4. Open Graph & Twitter Cards
        assert f'<meta property="og:title" content="{expected["title"]}">' in html
        assert f'<meta property="og:description" content="{expected["description"]}">' in html
        assert f'<meta property="og:url" content="https://validai.app.br{route_path}">' in html
        assert '<meta property="og:type" content="website">' in html
        assert '<meta property="og:locale" content="pt_BR">' in html
        assert '<meta property="og:image" content="https://validai.app.br/static/images/logo.png">' in html
        assert '<meta name="twitter:card" content="summary_large_image">' in html

        # 5. Unique H1
        h1_matches = re.findall(r'<h1[^>]*>(.*?)</h1>', html, flags=re.DOTALL)
        assert len(h1_matches) == 1, f"A rota {route_path} deve ter exatamente 1 tag <h1>, mas encontrou {len(h1_matches)}"
        assert expected['h1'] in h1_matches[0].strip(), f"H1 inesperado em {route_path}: {h1_matches[0]}"

        # 6. Explicit width and height on all <img> tags (CLS protection)
        img_tags = re.findall(r'<img\b[^>]*>', html)
        assert len(img_tags) >= 2, f"Logo <img> não encontrada em {route_path}"
        for img_tag in img_tags:
            assert 'width="' in img_tag and 'height="' in img_tag, f"Tag <img> sem width/height explícitos em {route_path}: {img_tag}"

        # 7. JSON-LD Schema validation
        ld_scripts = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, flags=re.DOTALL)
        assert len(ld_scripts) >= 1, f"JSON-LD ausente em {route_path}"
        for raw_ld in ld_scripts:
            parsed_ld = json_mod.loads(raw_ld)
            assert parsed_ld['@context'] == 'https://schema.org'

    print("[OK] Todas as 6 rotas ativas possuem Meta Tags dinâmicas, Canonical, Open Graph, Twitter Cards, <h1> único, JSON-LD válido e <img> com width/height!")

    # Verificar FAQ semântico e Schema FAQPage na Home (/)
    home_html = client.get('/').data.decode('utf-8')
    faq_questions = [
        'Como comparar duas planilhas Excel e achar diferenças automaticamente?',
        'Meus dados e planilhas estão seguros durante a validação?',
        'Quais formatos de arquivo o ValidAí aceita (.xlsx, .xls, .csv, .xml)?',
        'Como funciona a normalização automática para evitar falsos positivos?',
    ]
    assert '<details class="seo-faq-item">' in home_html
    assert '<summary class="seo-faq-question">' in home_html
    for q in faq_questions:
        assert q in home_html, f"Pergunta de FAQ ausente na Home: {q}"
    assert '"@type": "FAQPage"' in home_html
    assert '"applicationCategory": "BusinessApplication"' in home_html
    print("[OK] Seção de Perguntas Frequentes (<details>/<summary>) e Schema FAQPage + WebApplication validados na Home!")

    # Verificar rotas "Em Breve" com proteção de Crawl Budget (noindex, follow)
    upcoming_routes = ['/validador-json']
    for up_route in upcoming_routes:
        res_up = client.get(up_route)
        assert res_up.status_code == 200, f"Rota Em Breve {up_route} retornou {res_up.status_code}"
        up_html = res_up.data.decode('utf-8')
        assert '<meta name="robots" content="noindex, follow">' in up_html, f"Falta noindex, follow em {up_route}"
        assert f'<link rel="canonical" href="https://validai.app.br{up_route}">' in up_html
    print("[OK] Proteção de Crawl Budget (<meta name=\"robots\" content=\"noindex, follow\">) validada em /validador-json!")

    # Verificar /robots.txt, /sitemap.xml e /health
    res_robots = client.get('/robots.txt')
    assert res_robots.status_code == 200
    assert 'text/plain' in res_robots.mimetype
    robots_txt = res_robots.data.decode('utf-8')
    assert 'User-agent: *' in robots_txt
    assert 'Disallow: /api/' in robots_txt
    assert 'Disallow: /health' in robots_txt
    assert 'Sitemap: https://validai.app.br/sitemap.xml' in robots_txt
    print("[OK] /robots.txt servido corretamente na raiz do domínio (com Disallow: /health)!")

    res_sitemap = client.get('/sitemap.xml')
    assert res_sitemap.status_code == 200
    assert 'xml' in res_sitemap.mimetype
    sitemap_xml = res_sitemap.data.decode('utf-8')
    for active_url in ['https://validai.app.br/', 'https://validai.app.br/validador-texto', 'https://validai.app.br/validador-cadastros', 'https://validai.app.br/validador-xml', 'https://validai.app.br/conciliador-taxas', 'https://validai.app.br/auditoria-rh', 'https://validai.app.br/como-usar', 'https://validai.app.br/sobre', 'https://validai.app.br/privacidade', 'https://validai.app.br/termos']:
        assert f'<loc>{active_url}</loc>' in sitemap_xml, f"URL {active_url} ausente no sitemap.xml"
    for excluded_url in ['/validador-json', '/health']:
        assert excluded_url not in sitemap_xml, f"Rota {excluded_url} não deveria estar no sitemap.xml"
    print("[OK] /sitemap.xml servido corretamente com todas as 10 URLs canônicas ativas e sem /health!")

    res_health_get = client.get('/health')
    assert res_health_get.status_code == 200
    assert res_health_get.get_json() == {'status': 'ok'}
    assert res_health_get.headers.get('Cache-Control') == 'no-store, no-cache, must-revalidate, max-age=0'
    assert res_health_get.headers.get('X-Robots-Tag') == 'noindex, nofollow'

    res_health_head = client.head('/health')
    assert res_health_head.status_code == 200
    assert res_health_head.headers.get('Cache-Control') == 'no-store, no-cache, must-revalidate, max-age=0'
    assert res_health_head.headers.get('X-Robots-Tag') == 'noindex, nofollow'
    print("[OK] Rota /health (GET e HEAD) ultra-leve validada com status 200, JSON {'status': 'ok'} e headers Cache-Control + X-Robots-Tag!")

    # 13. Teste de Performance Mobile (Compressão Gzip + Cache Estático Imutável + Google Fonts display=swap)
    res_gzip = client.get('/', headers={'Accept-Encoding': 'gzip'})
    assert res_gzip.status_code == 200
    assert res_gzip.headers.get('Content-Encoding') == 'gzip', "Resposta HTML deve ser comprimida com Gzip!"
    assert 'Accept-Encoding' in res_gzip.headers.get('Vary', '')

    res_static_css = client.get('/static/css/style.css', headers={'Accept-Encoding': 'gzip'})
    assert res_static_css.status_code == 200
    assert res_static_css.headers.get('Content-Encoding') == 'gzip', "CSS estático deve ser comprimido com Gzip!"
    assert 'max-age=31536000' in res_static_css.headers.get('Cache-Control', ''), "Cache estático deve ter max-age=31536000!"
    assert 'immutable' in res_static_css.headers.get('Cache-Control', '')
    res_static_css.close()
    print("[OK] Compressão Gzip e Cache-Control estático (max-age=31536000, immutable) validados!")

    # 14. Teste de Acessibilidade (WCAG AA): Hierarquia de Cabeçalhos (sem pulo h2 -> h4) e display=swap
    import re
    all_routes = ['/', '/validador-texto', '/validador-cadastros', '/validador-xml', '/como-usar', '/conciliador-taxas', '/auditoria-rh']
    for r in all_routes:
        resp_r = client.get(r)
        html_r = resp_r.data.decode('utf-8')
        assert '&display=swap' in html_r or 'display=swap' in html_r, f"Falta display=swap em {r}"
        assert 'role="tablist"' not in html_r, f"role='tablist' sem role='tab' encontrado em {r}"
        headings = [int(m.group(1)) for m in re.finditer(r'<h([1-6])\b', html_r, re.I)]
        assert headings and headings[0] == 1, f"Primeiro cabeçalho deve ser <h1> em {r}: {headings}"
        for idx_h in range(1, len(headings)):
            assert headings[idx_h] <= headings[idx_h - 1] + 1, (
                f"Pulo de cabeçalho inválido em {r}: h{headings[idx_h - 1]} -> h{headings[idx_h]}"
            )
    print("[OK] Hierarquia semântica estrita (h1 -> h2 -> h3), ARIA roles e Google Fonts display=swap validados em todas as rotas!")

    # 18. TESTE DE CONFORMIDADE GOOGLE ADSENSE, LGPD E PÁGINAS INSTITUCIONAIS
    # =========================================================================
    print("\n--- Testando Conformidade Google AdSense, LGPD & Institucional (ValidAí) ---")
    
    # 18.1 Rota /privacidade
    res_priv = client.get('/privacidade')
    assert res_priv.status_code == 200, f"Falha GET /privacidade: {res_priv.status_code}"
    priv_html = res_priv.data.decode('utf-8')
    assert "Política de Privacidade" in priv_html
    assert "memória volátil" in priv_html.lower() or "memória efêmera" in priv_html.lower()
    assert "Google AdSense" in priv_html
    assert "DART" in priv_html or "DoubleClick" in priv_html
    assert "adssettings.google.com" in priv_html
    assert "aboutads.info" in priv_html
    assert "LGPD" in priv_html and "13.709" in priv_html
    assert "privacidade@validai.app.br" in priv_html
    print("[OK] /privacidade validada com conformidade LGPD, DPO e cláusulas obrigatórias Google AdSense (cookie DART)!")

    # 18.2 Rota /termos
    res_termos = client.get('/termos')
    assert res_termos.status_code == 200, f"Falha GET /termos: {res_termos.status_code}"
    termos_html = res_termos.data.decode('utf-8')
    assert "Termos e Condições de Uso" in termos_html
    assert "Isenção" in termos_html or "isenção" in termos_html
    assert "v3.3" in termos_html
    print("[OK] /termos validada com regras de uso, isenção fiscal/operacional e versão v3.3!")

    # 18.3 Rota /sobre
    res_sobre = client.get('/sobre')
    assert res_sobre.status_code == 200, f"Falha GET /sobre: {res_sobre.status_code}"
    sobre_html = res_sobre.data.decode('utf-8')
    assert "Sobre o ValidAí" in sobre_html
    assert "PROCV" in sobre_html or "fórmulas" in sobre_html
    print("[OK] /sobre validada com narrativa de missão institucional e soluções!")

    # 18.4 Banner de Consentimento de Cookies (LGPD) no Footer
    for check_route in ['/', '/como-usar', '/auditoria-rh', '/privacidade']:
        res_chk = client.get(check_route)
        chk_html = res_chk.data.decode('utf-8')
        assert 'id="validai-cookie-banner"' in chk_html, f"Cookie banner ausente em {check_route}"
        assert 'id="btn-accept-cookies"' in chk_html, f"Botão aceitar cookies ausente em {check_route}"
        assert 'href="/privacidade"' in chk_html, f"Link /privacidade ausente no banner em {check_route}"
        assert 'href="/termos"' in chk_html, f"Link /termos ausente no footer em {check_route}"
        assert 'href="/sobre"' in chk_html, f"Link /sobre ausente no footer em {check_route}"
    print("[OK] Banner de Cookies LGPD e links institucionais validados no footer de todas as páginas!")

    # 18.5 Conexão, Verificação e Validação do Google AdSense & ads.txt
    prod_pub_id = 'ca-pub-3178662755020611'
    
    # Validação da Rota Pública /ads.txt
    res_ads_txt = client.get('/ads.txt')
    assert res_ads_txt.status_code == 200, f"/ads.txt deve retornar status 200, retornou {res_ads_txt.status_code}"
    assert 'text/plain' in res_ads_txt.content_type, f"Content-Type de /ads.txt deve ser text/plain, retornou {res_ads_txt.content_type}"
    ads_txt_body = res_ads_txt.data.decode('utf-8').strip()
    expected_ads_line = "google.com, pub-3178662755020611, DIRECT, f08c47fec0942fa0"
    assert expected_ads_line in ads_txt_body, f"Linha esperada ausente em /ads.txt: {ads_txt_body}"
    print("[OK] Rota /ads.txt validada (HTTP 200, text/plain e linha oficial do Google AdSense)!")

    # Validação do robots.txt permitindo /ads.txt
    res_robots = client.get('/robots.txt')
    robots_body = res_robots.data.decode('utf-8')
    assert 'Disallow: /ads.txt' not in robots_body, "/ads.txt NÃO pode estar bloqueado no robots.txt!"
    assert 'Allow: /ads.txt' in robots_body, "robots.txt deve permitir explicitamente /ads.txt!"
    print("[OK] robots.txt validado sem bloqueios para /ads.txt!")

    # Validação da Meta Tag e Script Oficial em todas as páginas públicas (Visitante / Standard)
    client.get('/logout')
    public_routes = ['/', '/como-usar', '/privacidade', '/termos', '/sobre', '/auditoria-rh', '/conciliador-taxas']
    for p_route in public_routes:
        res_page = client.get(p_route)
        page_html = res_page.data.decode('utf-8')
        assert f'<meta name="google-adsense-account" content="{prod_pub_id}">' in page_html, f"Meta tag AdSense ausente em {p_route}"
        assert f'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={prod_pub_id}' in page_html, f"Script AdSense ausente em {p_route}"
    print(f"[OK] Meta tag de verificação e script oficial ({prod_pub_id}) validados no <head> de todas as páginas públicas!")

    # Validação da Ocultação de Containers Visuais (ADSENSE_SLOTS_ENABLED = false por padrão)
    # Cenário A: Slots desativados (durante fase de aprovação do AdSense)
    if 'ADSENSE_SLOTS_ENABLED' in os.environ:
        del os.environ['ADSENSE_SLOTS_ENABLED']
    res_home_disabled = client.get('/')
    home_disabled_html = res_home_disabled.data.decode('utf-8')
    assert '<div class="validai-ad-wrapper"' not in home_disabled_html, "Caixa visual de anúncio NÃO deve ser renderizada quando ADSENSE_SLOTS_ENABLED=false!"
    assert '<ins class="adsbygoogle' not in home_disabled_html, "Tag <ins adsbygoogle> NÃO deve ser renderizada quando ADSENSE_SLOTS_ENABLED=false!"
    assert 'class="validai-ad-badge"' not in home_disabled_html, "Badge 'PUBLICIDADE' NÃO deve ser exibida quando ADSENSE_SLOTS_ENABLED=false!"
    print("[OK] Containers visuais 100% ocultos com ADSENSE_SLOTS_ENABLED=false (tela limpa durante aprovação)!")

    # Cenário B: Slots ativados explicitamente (quando o Google aprovar a conta)
    os.environ['ADSENSE_SLOTS_ENABLED'] = 'true'
    try:
        res_home_enabled = client.get('/')
        home_enabled_html = res_home_enabled.data.decode('utf-8')
        assert '<div class="validai-ad-wrapper"' in home_enabled_html, "Container visual deve ser renderizado quando ADSENSE_SLOTS_ENABLED=true!"
        assert '<ins class="adsbygoogle' in home_enabled_html, "Tag <ins adsbygoogle> deve ser renderizada quando ADSENSE_SLOTS_ENABLED=true!"
        assert prod_pub_id in home_enabled_html, f"ID {prod_pub_id} deve constar no bloco de anúncio!"

        res_guide_enabled = client.get('/como-usar')
        guide_enabled_html = res_guide_enabled.data.decode('utf-8')
        assert '<ins class="adsbygoogle' in guide_enabled_html, "Container de anúncio deve constar em /como-usar quando ativo!"
        print(f"[OK] Containers visuais ativados com sucesso quando ADSENSE_SLOTS_ENABLED=true!")
    finally:
        if 'ADSENSE_SLOTS_ENABLED' in os.environ:
            del os.environ['ADSENSE_SLOTS_ENABLED']

    # Validação da Regra CSS para Anúncios Não Preenchidos (unfilled)
    with open('static/css/style.css', 'r', encoding='utf-8') as f_css:
        css_content = f_css.read()
    assert '.adsbygoogle[data-ad-status="unfilled"]' in css_content, "Regra CSS data-ad-status='unfilled' deve constar em style.css!"
    print("[OK] Regra CSS de colapso automático para anúncios 'unfilled' validada com sucesso!")

    # =========================================================================
    # 19. TESTES DO SISTEMA DE PLANOS, MONETIZAÇÃO, AUTENTICAÇÃO E BLINDAGEM RAM
    # =========================================================================
    print("\n--- Testando Sistema de Planos, Monetização, Autenticação e Blindagem RAM ---")
    
    # 19.1 Página /planos
    res_planos = client.get('/planos')
    assert res_planos.status_code == 200, f"Falha GET /planos: {res_planos.status_code}"
    html_planos = res_planos.data.decode('utf-8')
    assert 'Standard' in html_planos
    assert 'Plus' in html_planos
    assert 'Pro' in html_planos
    assert 'R$ 4,99' in html_planos
    assert 'R$ 9,99' in html_planos
    print("[OK] Página /planos renderizada com os 3 cards de planos e preços oficiais!")

    # 19.2 Blindagem de RAM (Limite 12 MB - HTTP 413)
    big_payload = b'0' * (13 * 1024 * 1024)
    res_413 = client.post('/api/single/upload-headers', data={'file': (io.BytesIO(big_payload), 'huge.xlsx')}, content_type='multipart/form-data')
    assert res_413.status_code == 413, f"Upload > 12 MB deveria retornar 413, mas retornou {res_413.status_code}"
    assert 'excede o limite máximo permitido de 12 MB' in res_413.get_json()['error']
    print("[OK] Blindagem de RAM: Upload acima de 12 MB bloqueado com HTTP 413 e mensagem amigável!")

    # 19.3 Plano Standard (Visitante Anônimo)
    client.get('/logout')
    
    # Validador Especial bloqueado para arquivos reais no Standard
    with tempfile.TemporaryDirectory() as tmp_dir:
        cad_csv_path = os.path.join(tmp_dir, 'cad_test.csv')
        with open(cad_csv_path, 'w', encoding='utf-8') as f:
            f.write("CPF,NOME\n11144477735,Cliente Teste\n")
        with open(cad_csv_path, 'rb') as f:
            res_cad_up = client.post('/api/cadastros/upload-headers', data={'file': (f, 'cad_test.csv')}, content_type='multipart/form-data')
    assert res_cad_up.status_code == 200
    cad_sid = res_cad_up.get_json()['session_id']
    
    res_spec_block = client.post('/api/cadastros/process', json={
        'session_id': cad_sid,
        'col_doc': 'CPF',
        'col_name': 'NOME'
    })
    assert res_spec_block.status_code == 403, f"Deveria bloquear ferramenta especial com 403 no Standard, retornou {res_spec_block.status_code}"
    err_spec = res_spec_block.get_json()
    assert err_spec['error'] == 'plan_limit'
    assert err_spec['limit_type'] == 'special_locked'
    assert err_spec['required_plan'] == 'plus'
    print("[OK] Bloqueio de arquivos reais em validadores avançados no plano Standard validado com HTTP 403 (special_locked)!")

    # Exemplo liberado e gratuito em ferramenta especial
    res_cad_ex = client.post('/api/cadastros/load-example')
    assert res_cad_ex.status_code == 200
    ex_sid = res_cad_ex.get_json()['session_id']
    res_spec_free = client.post('/api/cadastros/process', json={
        'session_id': ex_sid,
        'col_doc': 'CPF_Cliente',
        'col_name': 'Nome_Razao'
    })
    assert res_spec_free.status_code == 200
    print("[OK] 'Testar Exemplo' em ferramenta avançada 100% liberado e gratuito no Standard!")

    # Limite de colunas e linhas do Standard dentro de contexto de requisição
    with app.app.test_request_context():
        from services.plan_manager import check_validation_permission
        allowed_cols, err_cols, status_cols = check_validation_permission(tool_type='basic', rows=10, cols=25, is_sample=False)
        assert allowed_cols is False
        assert status_cols == 403
        assert err_cols['limit_type'] == 'columns'
        print("[OK] Trava de segurança de 20 colunas no plano Standard validada com HTTP 403 (columns)!")

        allowed_rows, err_rows, status_rows = check_validation_permission(tool_type='basic', rows=600, cols=10, is_sample=False)
        assert allowed_rows is False
        assert status_rows == 403
        assert err_rows['limit_type'] == 'rows'
        print("[OK] Trava de segurança de 500 linhas no plano Standard validada com HTTP 403 (rows)!")

    # 19.4 Teste de Autenticação e API de Usuário
    res_me_anon = client.get('/api/auth/me')
    assert res_me_anon.status_code == 200
    summary_anon = res_me_anon.get_json()['summary']
    assert summary_anon['is_logged_in'] is False
    assert summary_anon['plan'] == 'standard'
    assert summary_anon['show_ads'] is True
    print("[OK] Endpoint /api/auth/me validado para visitante anônimo (Standard, show_ads=True)!")

    # 19.5 Teste do Plano Pro (Sem anúncios e ilimitado)
    with client.session_transaction() as sess:
        sess['user_id'] = 'mock_pro_test'
        sess['user_email'] = 'pro@validai.app.br'
    
    res_me_pro = client.get('/api/auth/me')
    assert res_me_pro.status_code == 200
    summary_pro = res_me_pro.get_json()['summary']
    assert summary_pro['is_logged_in'] is True
    assert summary_pro['plan'] == 'pro'
    assert summary_pro['show_ads'] is False
    print("[OK] Endpoint /api/auth/me validado para assinante Pro (Ilimitado, show_ads=False)!")

    # 19.6 Teste de Checkout Mercado Pago
    res_chk_plus = client.get('/checkout/plus', follow_redirects=False)
    assert res_chk_plus.status_code == 302
    assert 'mercadopago.com' in res_chk_plus.headers.get('Location', '')
    print(f"[OK] Rota /checkout/plus gera link oficial do Mercado Pago: {res_chk_plus.headers.get('Location')[:55]}...")

    res_chk_pro = client.get('/checkout/pro', follow_redirects=False)
    assert res_chk_pro.status_code == 302
    assert 'mercadopago.com' in res_chk_pro.headers.get('Location', '')
    print(f"[OK] Rota /checkout/pro gera link oficial do Mercado Pago: {res_chk_pro.headers.get('Location')[:55]}...")

    # 19.7 Teste do Modal de Autenticação e OAuth Google / Cadastro / Termos
    res_cb_page = client.get('/auth/callback')
    assert res_cb_page.status_code == 200
    assert 'Conectando com o Google' in res_cb_page.get_data(as_text=True)
    print("[OK] Rota /auth/callback renderizada com ponte do Supabase JS SDK!")

    res_cb_err = client.get('/auth/callback?error=access_denied&error_description=Cancelado+pelo+usuario', follow_redirects=False)
    assert res_cb_err.status_code == 302
    assert '/login?error=' in res_cb_err.headers.get('Location', '')
    print("[OK] Erro de OAuth redireciona adequadamente para a tela de login!")

    # Teste de API OAuth Callback
    test_oauth_id = str(uuid.uuid4())
    test_oauth_email = f"user_oauth_{uuid.uuid4().hex[:8]}@validai.app.br"
    res_oauth_post = client.post('/api/auth/oauth-callback', json={
        'user_id': test_oauth_id,
        'email': test_oauth_email
    })
    assert res_oauth_post.status_code == 200
    oauth_json = res_oauth_post.get_json()
    assert oauth_json['success'] is True
    assert oauth_json['user']['email'] == test_oauth_email
    print("[OK] Endpoint /api/auth/oauth-callback validado (cria sessão e sincroniza perfil)!")

    # Teste de Validação de Cadastro: Senhas divergentes e Termos desmarcados
    res_cad_diff_pwd = client.post('/api/auth/cadastro', json={
        'email': 'novo@validai.app.br',
        'password': 'senhaForte123',
        'password_confirm': 'outraSenhaDiferente',
        'terms': True
    })
    assert res_cad_diff_pwd.status_code == 400
    assert 'não coincidem' in res_cad_diff_pwd.get_json()['error']
    print("[OK] Validação de cadastro: senhas divergentes bloqueadas com sucesso!")

    res_cad_no_terms = client.post('/api/auth/cadastro', json={
        'email': 'novo@validai.app.br',
        'password': 'senhaForte123',
        'password_confirm': 'senhaForte123',
        'terms': False
    })
    assert res_cad_no_terms.status_code == 400
    assert 'Termos de Uso' in res_cad_no_terms.get_json()['error']
    print("[OK] Validação de cadastro: termos desmarcados bloqueados com sucesso!")

    # Teste de Recuperação de Senha
    res_recup = client.post('/api/auth/recuperar-senha', json={'email': 'usuario@validai.app.br'})
    assert res_recup.status_code == 200
    assert res_recup.get_json()['success'] is True
    print("[OK] Endpoint /api/auth/recuperar-senha validado com sucesso!")

    # Desloga para testar a renderização das telas públicas /login e /cadastro
    client.get('/logout')

    # Teste de Renderização dos Botões Google e Termos nas Telas /login e /cadastro
    res_login_page = client.get('/login')
    assert res_login_page.status_code == 200
    login_html = res_login_page.get_data(as_text=True)
    assert 'Continuar com o Google' in login_html
    assert 'ou continue com e-mail' in login_html
    assert 'Esqueci minha senha' in login_html
    print("[OK] Tela /login renderizada com Botão Google, divisor e 'Esqueci minha senha'!")

    res_cad_page = client.get('/cadastro')
    assert res_cad_page.status_code == 200
    cad_html = res_cad_page.get_data(as_text=True)
    assert 'Continuar com o Google' in cad_html
    assert 'ou continue com e-mail' in cad_html
    assert 'Confirme sua senha' in cad_html
    assert 'Li e aceito os' in cad_html
    print("[OK] Tela /cadastro renderizada com Botão Google, 'Confirme sua senha' e Checkbox de Termos!")

    # Teste no Modal Unificado de Autenticação (renderizado em páginas públicas)
    res_home_modal = client.get('/')
    assert res_home_modal.status_code == 200
    home_html = res_home_modal.get_data(as_text=True)
    assert 'validai-auth-modal' in home_html
    assert 'Continuar com o Google' in home_html
    assert 'signup-password-confirm' in home_html
    assert 'signup-terms' in home_html
    print("[OK] Modal Unificado de Autenticação validado com Botão Google, Confirmação e Termos!")

    # -------------------------------------------------------------
    # Testes das Novas Funcionalidades de Planilhas e Mapeamento
    # -------------------------------------------------------------
    print("\n--- Testando Novas Funcionalidades de Leitura de Planilhas e Mapeamento ---")
    import openpyxl
    import pandas as pd
    import numpy as np
    import comparator

    # 1. Teste de Inspeção de Abas (/api/sheets/inspect-file e /inspecionar-arquivo)
    wb_test = openpyxl.Workbook()
    ws1 = wb_test.active
    ws1.title = "Aba_Oculta_1"
    ws1.sheet_state = "hidden"
    ws2 = wb_test.create_sheet("Implementos")
    ws2.sheet_state = "visible"
    ws3 = wb_test.create_sheet("John_Deere")
    ws3.sheet_state = "visible"

    buf_inspect = io.BytesIO()
    wb_test.save(buf_inspect)
    raw_inspect = buf_inspect.getvalue()

    for route in ['/api/sheets/inspect-file', '/inspecionar-arquivo']:
        res_insp = client.post(route, data={'file': (io.BytesIO(raw_inspect), 'maquinas.xlsx')}, content_type='multipart/form-data')
        assert res_insp.status_code == 200, f"Falha POST {route}: {res_insp.status_code}"
        insp_data = res_insp.get_json()
        assert insp_data['is_excel'] is True
        assert len(insp_data['sheets']) == 3
        # Regra Crítica: primeira aba visível deve ser o default, NUNCA a aba oculta!
        assert insp_data['default_sheet'] == "Implementos", f"Aba default incorreta: {insp_data['default_sheet']}"
        assert insp_data['sheets'][0]['name'] == "Aba_Oculta_1" and insp_data['sheets'][0]['visible'] is False
        assert insp_data['sheets'][1]['name'] == "Implementos" and insp_data['sheets'][1]['visible'] is True
        assert insp_data['sheets'][2]['name'] == "John_Deere" and insp_data['sheets'][2]['visible'] is True
    print("[OK] Inspeção de abas e proteção de aba oculta (/inspecionar-arquivo) validadas com sucesso!")

    # 2. Teste de Linha do Cabeçalho deslocada (Ex: cabeçalho na Linha 3)
    df_header_shift = pd.DataFrame([
        ['Relatório Financeiro Corporativo', None, None],
        ['Data de Emissão: 2026-10-22', None, None],
        ['ID_TRANSACAO', 'NOTA_FISCAL', 'TOTAL_BRUTO'],
        [1001, 'NF-8901', 426569.12],
        [1002, 'NF-8902', 15890.00]
    ])
    buf_shift = io.BytesIO()
    df_header_shift.to_excel(buf_shift, index=False, header=False)
    raw_shift = buf_shift.getvalue()

    res_upload_shift = client.post('/api/upload-headers', data={
        'file_a': (io.BytesIO(raw_shift), 'relatorio_a.xlsx'),
        'file_b': (io.BytesIO(raw_shift), 'relatorio_b.xlsx'),
        'header_line_a': '3',
        'header_line_b': '3'
    }, content_type='multipart/form-data')
    assert res_upload_shift.status_code == 200
    shift_data = res_upload_shift.get_json()
    assert shift_data['cols_a'] == ['ID_TRANSACAO', 'NOTA_FISCAL', 'TOTAL_BRUTO'], f"Colunas lidas: {shift_data['cols_a']}"
    assert shift_data['has_unnamed'] is False
    print("[OK] Linha de cabeçalho configurável (header = 3) lida sem erros e sem Unnamed!")

    # 2.1 Teste do Aviso Amarelo quando Linha 1 possui Unnamed
    res_upload_unnamed = client.post('/api/upload-headers', data={
        'file_a': (io.BytesIO(raw_shift), 'relatorio_a.xlsx'),
        'file_b': (io.BytesIO(raw_shift), 'relatorio_b.xlsx'),
        'header_line_a': '1',
        'header_line_b': '1'
    }, content_type='multipart/form-data')
    assert res_upload_unnamed.status_code == 200
    assert res_upload_unnamed.get_json()['has_unnamed'] is True
    print("[OK] Aviso de colunas Unnamed gerado corretamente quando cabeçalho não está na linha 1!")

    # 3. Teste de Concatenação de Múltiplas Abas (pd.concat)
    wb_multi = openpyxl.Workbook()
    ws_imp = wb_multi.active
    ws_imp.title = "Implementos"
    ws_imp.append(['ID', 'PRODUTO', 'VALOR'])
    ws_imp.append([1, 'Trator A', 50000])
    ws_jd = wb_multi.create_sheet("John_Deere")
    ws_jd.append(['ID', 'PRODUTO', 'VALOR'])
    ws_jd.append([2, 'Colheitadeira B', 120000])

    buf_multi = io.BytesIO()
    wb_multi.save(buf_multi)
    buf_multi.seek(0)

    df_multi_read = comparator.read_tabular_file(buf_multi, 'equipamentos.xlsx', header_line=1, sheet_names=['Implementos', 'John_Deere'])
    assert len(df_multi_read) == 2, f"Total de linhas concatenadas incorreto: {len(df_multi_read)}"
    assert list(df_multi_read['ID']) == [1, 2]
    print("[OK] Concatenação de múltiplas abas via pd.concat validada com sucesso!")

    # 4. Teste de Proteção de Colunas Esparsas / Vazias
    df_sparse = pd.DataFrame({
        'ID': [1, 2, 3],
        'DEMITIDO': [np.nan, np.nan, np.nan],
        'OBSERVACOES': [None, None, None],
        'Unnamed: 3': [np.nan, np.nan, np.nan],
        'Unnamed: 4': ['Preenchido', np.nan, 'OK']
    })
    buf_sparse = io.BytesIO()
    df_sparse.to_excel(buf_sparse, index=False)
    buf_sparse.seek(0)

    df_sparse_read = comparator.read_tabular_file(buf_sparse, 'sparse.xlsx')
    cols_kept = list(df_sparse_read.columns)
    assert 'DEMITIDO' in cols_kept, "Coluna DEMITIDO (100% NaN) não pode ser descartada!"
    assert 'OBSERVACOES' in cols_kept, "Coluna OBSERVACOES (100% NaN) não pode ser descartada!"
    assert 'Unnamed: 4' in cols_kept, "Coluna Unnamed com dados deve ser preservada!"
    assert 'Unnamed: 3' not in cols_kept, "Coluna Unnamed 100% nula deve ser descartada!"
    print("[OK] Proteção estrita de colunas esparsas / vazias validada!")

    # 5. Teste de Normalização de Moeda e Decimal com Vírgula Brasileira em CSV vs Excel
    csv_text = "ID;TOTAL_BRUTO\n101;426569,12\n102;1500,50\n"
    buf_csv = io.BytesIO(csv_text.encode('utf-8'))
    df_csv = comparator.read_tabular_file(buf_csv, 'vendas.csv')

    df_excel = pd.DataFrame({
        'ID': [101, 102],
        'TOTAL_BRUTO': [426569.12, 1500.50]
    })

    summary, diff_records, *_ = comparator.compare_datasets(df_excel, df_csv, primary_key_a='ID', primary_key_b='ID')
    assert summary['is_identical'] is True, f"Diferenças encontradas entre CSV e Excel: {summary['different_rows_count']}"
    assert summary['different_rows_count'] == 0
    assert summary['total_cells_diff'] == 0
    print("[OK] Comparação de decimal brasileiro com vírgula (CSV vs Excel float) sem falsos positivos!")

    # 6. Teste de Auto-Mapeamento com os 9 Grupos de Sinônimos de Negócio
    cols_source = [
        'NOTA FISCAL', 'EMPRESA - FILIAL', 'NOME CLIENTE', 'VENDEDOR EQUIPAMENTO',
        'TIPO CLIENTE', 'MODELO', 'DATA DA VENDA', 'TOTAL_BRUTO', 'QUANTIDADE'
    ]
    cols_target = [
        'NUM_NF', 'LOJA', 'RAZAO_SOCIAL', 'VENDEDOR',
        'CLIENTE_GRUPOTRIBUTARIO', 'COD_MODELO', 'DT_VENDA', 'VALOR_VENDA', 'QTD'
    ]
    mapping_result = comparator.suggest_column_mappings(cols_source, cols_target)
    for src, tgt in zip(cols_source, cols_target):
        assert mapping_result.get(src) == tgt, f"Falha mapeando sinônimo: {src} -> {mapping_result.get(src)} (esperado: {tgt})"
    print("[OK] Auto-mapeamento com todos os 9 grupos de sinônimos de negócio validado com sucesso!")

    # 7. Teste de Endpoint /api/excel-sheets diretamente
    res_api_sheets = client.post('/api/excel-sheets', data={'file': (io.BytesIO(raw_inspect), 'maquinas.xlsx')}, content_type='multipart/form-data')
    assert res_api_sheets.status_code == 200
    api_sheets_data = res_api_sheets.get_json()
    assert api_sheets_data['is_excel'] is True
    assert api_sheets_data['default_sheet'] == "Implementos"
    assert len(api_sheets_data['sheets']) == 3
    print("[OK] Endpoint /api/excel-sheets validado com sucesso!")

    # 8. Teste de Normalização de Datas (Evitar Falso Positivo "28/08/2026" vs "2026-08-28 00:00:00")
    val_csv = comparator.parse_cell_value("28/08/2026", normalize_dates=True)
    val_excel_str = comparator.parse_cell_value("2026-08-28 00:00:00", normalize_dates=True)
    val_timestamp = comparator.parse_cell_value(pd.Timestamp("2026-08-28 00:00:00"), normalize_dates=True)
    val_date_iso = comparator.parse_cell_value("2026-08-28", normalize_dates=True)
    val_iso_t = comparator.parse_cell_value("2026-08-28T14:30:00", normalize_dates=True)

    assert val_csv == "2026-08-28", f"Data CSV normalizada incorretamente: {val_csv}"
    assert val_excel_str == "2026-08-28", f"Data Excel normalizada incorretamente: {val_excel_str}"
    assert val_timestamp == "2026-08-28", f"Timestamp normalizado incorretamente: {val_timestamp}"
    assert val_date_iso == "2026-08-28"
    assert val_iso_t == "2026-08-28"

    df_dates_a = pd.DataFrame({
        'ID': [1, 2],
        'DATA_EMISSAO': ['28/08/2026', '01/09/2026']
    })
    df_dates_b = pd.DataFrame({
        'ID': [1, 2],
        'DATA_EMISSAO': ['2026-08-28 00:00:00', pd.Timestamp('2026-09-01 00:00:00')]
    })
    summary_dates, *_ = comparator.compare_datasets(df_dates_a, df_dates_b, primary_key_a='ID', primary_key_b='ID', normalize_dates=True)
    assert summary_dates['is_identical'] is True, f"Falso positivo em datas detectado: {summary_dates['different_rows_count']} linhas divergentes"
    assert summary_dates['different_rows_count'] == 0
    print("[OK] Normalização de datas (CSV 28/08/2026 vs Excel 2026-08-28 00:00:00) 100% idêntica sem falsos positivos!")

    # 9. Teste de Algoritmo de Auto-Sugestão de Chave Primária (CHASSI/NOTA_FISCAL vs MARCA)
    df_key_a = pd.DataFrame({
        'MARCA': ['JOHN DEERE', 'JOHN DEERE', 'CASE', 'NEW HOLLAND', 'MASSEY', 'VALTRA', 'JOHN DEERE', 'CASE', 'VALTRA', 'CASE'],
        'CHASSI': [f'9BR{i:06d}' for i in range(10)],
        'MODELO': ['T100', 'T200', 'T300', 'T400', 'T500', 'T600', 'T700', 'T800', 'T900', 'T1000']
    })
    buf_key_a = io.BytesIO()
    df_key_a.to_excel(buf_key_a, index=False)
    raw_key_a = buf_key_a.getvalue()

    res_upload_keys = client.post('/api/upload-headers', data={
        'file_a': (io.BytesIO(raw_key_a), 'base_a.xlsx'),
        'file_b': (io.BytesIO(raw_key_a), 'base_b.xlsx'),
        'header_line_a': '1',
        'header_line_b': '1'
    }, content_type='multipart/form-data')
    assert res_upload_keys.status_code == 200
    suggested = res_upload_keys.get_json().get('suggested_keys', [])
    assert len(suggested) >= 2
    # CHASSI deve ser a primeira sugestão (#1) e MARCA deve estar depois (penalizada por baixa cardinalidade e categoria)
    assert suggested[0] == 'CHASSI', f"CHASSI não foi a primeira sugestão! Sugestões: {suggested}"
    assert suggested[-1] == 'MARCA', f"MARCA não foi penalizada! Sugestões: {suggested}"
    print("[OK] Algoritmo de auto-sugestão de Chave Primária priorizou CHASSI e penalizou MARCA com perfeição!")

    # 10. Teste de Seleção de Aba e Linha de Cabeçalho no Passo 2 (/api/change-sheet)
    # Cria uma pasta de trabalho com múltiplas abas:
    # Aba 1: 'Resumo' (colunas: Titulo, Data_Criacao)
    # Aba 2: 'Implementos' (linha 1 com texto de lixo, linha 2 com cabeçalho: COD_ITEM, NOME_ITEM, VALOR)
    buf_multi = io.BytesIO()
    with pd.ExcelWriter(buf_multi, engine='openpyxl') as writer:
        df_resumo = pd.DataFrame({'Titulo': ['Relatório Geral'], 'Data_Criacao': ['2026-10-22']})
        df_resumo.to_excel(writer, sheet_name='Resumo', index=False)
        
        df_implementos = pd.DataFrame([
            ['--- TABELA DE IMPLEMENTOS AGRÍCOLAS ---', None, None],
            ['COD_ITEM', 'NOME_ITEM', 'VALOR_UNITARIO'],
            ['IMP001', 'Arado Reversível', 15400.00],
            ['IMP002', 'Grade Aradora', 28900.50]
        ])
        df_implementos.to_excel(writer, sheet_name='Implementos', header=False, index=False)
        
        df_tratores = pd.DataFrame({
            'CHASSI_TRATOR': ['TR01', 'TR02'],
            'POTENCIA_CV': [120, 180]
        })
        df_tratores.to_excel(writer, sheet_name='Tratores', index=False)

    buf_multi.seek(0)
    raw_multi = buf_multi.getvalue()

    res_upload_multi = client.post('/api/upload-headers', data={
        'file_a': (io.BytesIO(raw_multi), 'equipamentos_a.xlsx'),
        'file_b': (io.BytesIO(raw_multi), 'equipamentos_b.xlsx')
    }, content_type='multipart/form-data')
    assert res_upload_multi.status_code == 200
    multi_data = res_upload_multi.get_json()
    assert multi_data['has_multiple_sheets'] is True
    assert len(multi_data['sheets_info_a']) == 3
    assert multi_data['default_sheet_a'] == 'Resumo'
    assert 'Titulo' in multi_data['cols_a']
    session_multi_id = multi_data['session_id']
    print("[OK] Upload de planilha com múltiplas abas detectou has_multiple_sheets=True e listou as 3 abas!")

    # Agora simula o usuário no Passo 2 alternando para a Aba 2 'Implementos' com cabeçalho na linha 2:
    res_change = client.post('/api/change-sheet', json={
        'session_id': session_multi_id,
        'sheet_a': 'Implementos',
        'sheet_b': 'Implementos',
        'header_line_a': 2,
        'header_line_b': 2
    })
    assert res_change.status_code == 200, f"Falha POST /api/change-sheet: {res_change.status_code}"
    change_data = res_change.get_json()
    assert change_data['success'] is True
    assert 'COD_ITEM' in change_data['cols_a']
    assert 'NOME_ITEM' in change_data['cols_a']
    assert 'VALOR_UNITARIO' in change_data['cols_a']
    assert change_data['has_unnamed'] is False
    assert change_data['suggested_keys'][0] == 'COD_ITEM'
    print("[OK] Endpoint /api/change-sheet alternou para a 2ª aba ('Implementos') com cabeçalho na linha 2 com 100% de precisão!")

    # Executa a comparação com a aba e cabeçalho selecionados
    res_compare_multi = client.post('/api/compare', json={
        'session_id': session_multi_id,
        'primary_key_a': 'COD_ITEM',
        'primary_key_b': 'COD_ITEM',
        'secondary_keys_a': [],
        'normalize_currency': True,
        'normalize_dates': True,
        'ignore_case': True,
        'trim_spaces': True,
        'column_mapping': change_data['column_mapping'],
        'header_line_a': 2,
        'header_line_b': 2,
        'sheets_a': 'Implementos',
        'sheets_b': 'Implementos'
    })
    assert res_compare_multi.status_code == 200
    comp_multi_res = res_compare_multi.get_json()
    assert comp_multi_res['summary']['is_identical'] is True
    assert comp_multi_res['summary']['total_rows_a'] == 2
    print("[OK] Comparação final com a aba e cabeçalho escolhidos no Passo 2 realizada com sucesso (100% idêntico)!")

    print("\nTODOS OS TESTES PASSARAM COM 100% DE SUCESSO!")

if __name__ == '__main__':
    test_full_pipeline()


