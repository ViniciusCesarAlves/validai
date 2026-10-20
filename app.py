import os
import uuid
import json
import gzip
try:
    import brotli
except ImportError:
    brotli = None
from flask import Flask, render_template, request, jsonify, send_file, Response
import comparator
import single_auditor
import text_comparator
import cadastros_cleaner
import xml_reconciler
import ofx_reconciler
import rh_auditor

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Suporta até 100MB de arquivo
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000    # Cache estático de 1 ano (31536000s)

COMPRESSIBLE_MIMETYPES = {
    'text/html',
    'text/css',
    'text/plain',
    'text/javascript',
    'application/javascript',
    'application/x-javascript',
    'application/json',
    'application/xml',
    'text/xml',
    'image/svg+xml',
}


@app.after_request
def add_cache_and_compression(response):
    # Preserva cabeçalhos restritos da rota de monitoramento /health
    if request.path == '/health':
        return response

    # Cache estático de longa duração (1 ano) para /static/ e /favicon.ico (Core Web Vitals / PageSpeed Mobile)
    if request.path.startswith('/static/') or request.path == '/favicon.ico':
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'

    # Compressão Gzip / Brotli para respostas HTML, CSS, JS, JSON e XML
    if (
        response.status_code == 200
        and request.method != 'HEAD'
        and 'Content-Encoding' not in response.headers
        and (response.mimetype in COMPRESSIBLE_MIMETYPES)
    ):
        accept_encoding = request.headers.get('Accept-Encoding', '').lower()
        if 'br' in accept_encoding or 'gzip' in accept_encoding:
            if response.direct_passthrough:
                response.direct_passthrough = False
            raw_data = response.get_data()
            if len(raw_data) >= 400:
                if brotli is not None and 'br' in accept_encoding:
                    compressed_data = brotli.compress(raw_data, quality=4)
                    response.set_data(compressed_data)
                    response.headers['Content-Encoding'] = 'br'
                    response.headers['Content-Length'] = str(len(compressed_data))
                elif 'gzip' in accept_encoding:
                    compressed_data = gzip.compress(raw_data, compresslevel=6)
                    response.set_data(compressed_data)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Length'] = str(len(compressed_data))
                vary = response.headers.get('Vary', '')
                if 'Accept-Encoding' not in vary:
                    response.headers['Vary'] = f"{vary}, Accept-Encoding".strip(', ')

    return response


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
REPORT_DIR = os.path.join(BASE_DIR, 'reports')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# Armazenamento em memória para sessões ativas
SESSIONS = {}
REPORTS = {}

SITE_DOMAIN = "https://validai.app.br"

# Sistema Centralizado de Metadados SEO por Rota
SEO_METADATA = {
    '/': {
        'title': 'ValidAí | Comparador e Validador de Planilhas Excel e CSV Online',
        'description': 'Compare, audite e valide duas planilhas Excel (.xlsx, .xls) ou CSV gratuitamente. Encontre divergências célula por célula e baixe o relatório pintado.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/validador-texto': {
        'title': 'Comparador e Validador de Textos Online | ValidAí',
        'description': 'Compare dois blocos de texto lado a lado e identifique diferenças, adições e remoções instantaneamente com precisão.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/validador-cadastros': {
        'title': 'Higienizador de Cadastros: Validar CPF, CNPJ, E-mail e Duplicados | ValidAí',
        'description': 'Limpe e padronize suas bases de dados. Valide CPF/CNPJ, e-mails e remova linhas duplicadas de planilhas automaticamente.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/validador-xml': {
        'title': 'Conciliador de Notas Fiscais (XML NFe/NFSe vs Excel) | ValidAí',
        'description': 'Cruze dados de arquivos XML de Notas Fiscais (NFe e NFSe) contra planilhas de controle no Excel de forma automatizada.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/como-usar': {
        'title': 'Como Usar o ValidAí | Guia Completo de Validação e Auditoria de Dados',
        'description': 'Aprenda passo a passo como comparar planilhas, higienizar cadastros e conciliar notas fiscais no ValidAí.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/conciliador-taxas': {
        'title': 'Conciliador de Taxas e Extratos (.OFX vs Vendas) | ValidAí',
        'description': 'Audite taxas de maquininhas (Stone, Cielo, Rede) e repasses de marketplaces contra extratos bancários .OFX.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    # Rotas "Em Breve" protegidas contra desperdício de Crawl Budget e Soft 404
    '/auditoria-rh': {
        'title': 'Auditoria de Folha e RH | ValidAí',
        'description': 'Batimento automatizado de folha de pagamento (mês anterior vs. atual) e conciliação de ativos do RH contra faturas de benefícios corporativos.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png',
        'module_name': 'Auditoria de Folha e RH',
        'module_sub': 'Batimento de folha de pagamento, proventos, descontos e benefícios corporativos.'
    },
    '/privacidade': {
        'title': 'Política de Privacidade e Proteção de Dados (LGPD) | ValidAí',
        'description': 'Conheça nossa Política de Privacidade em conformidade com a LGPD (Lei 13.709/2018). Processamento volátil em memória, sem armazenamento permanente e transparência com cookies e Google AdSense.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/termos': {
        'title': 'Termos e Condições de Uso | ValidAí',
        'description': 'Termos de Uso do ValidAí. Regras de utilização, isenção de responsabilidade sobre análises tributárias e contábeis, propriedade intelectual e uso justo.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/sobre': {
        'title': 'Sobre o ValidAí | Soluções em Auditoria e Conciliação de Dados',
        'description': 'Conheça a missão do ValidAí: automatizar a validação e conciliação de planilhas, notas fiscais e folhas de pagamento sem fórmulas complexas.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/validador-json': {
        'title': 'Comparador de JSON / APIs - Em Breve | ValidAí',
        'description': 'Identifique diferenças estruturais, chaves ausentes e divergências de tipagem entre payloads JSON e retornos de APIs.',
        'robots': 'noindex, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png',
        'module_name': 'Comparador de JSON / APIs',
        'module_sub': 'Análise de diferenças estruturais entre payloads JSON, webhooks e objetos aninhados.'
    }
}


@app.context_processor
def inject_seo_metadata():
    path = request.path if request else '/'
    meta = SEO_METADATA.get(path, SEO_METADATA['/'])
    canonical = f"{SITE_DOMAIN}{path}"
    return {
        'seo': {
            'title': meta['title'],
            'description': meta['description'],
            'robots': meta.get('robots', 'index, follow'),
            'canonical_url': canonical,
            'og_image': meta.get('og_image', f'{SITE_DOMAIN}/static/images/logo.png'),
            'module_name': meta.get('module_name', ''),
            'module_sub': meta.get('module_sub', '')
        }
    }

ADSENSE_SLOTS_ENABLED = os.environ.get('ADSENSE_SLOTS_ENABLED', 'false').lower() == 'true'

@app.context_processor
def inject_ads_context():
    adsense_id = os.environ.get('ADSENSE_CLIENT_ID', 'ca-pub-3178662755020611').strip()
    slots_enabled = os.environ.get('ADSENSE_SLOTS_ENABLED', 'false').lower() == 'true'
    # show_ads: True por padrão para visitantes e plano Standard; False no futuro para assinantes Plus/Pro
    show_ads = True
    return {
        'show_ads': show_ads,
        'adsense_client_id': adsense_id,
        'adsense_slots_enabled': slots_enabled
    }


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/validador-texto')
def validador_texto():
    return render_template('validador_texto.html')

@app.route('/validador-cadastros')
def validador_cadastros():
    return render_template('validador_cadastros.html')

@app.route('/validador-xml')
def validador_xml():
    return render_template('validador_xml.html')

@app.route('/como-usar')
def como_usar():
    return render_template('como_usar.html')

@app.route('/conciliador-taxas')
def conciliador_taxas():
    return render_template('validador_ofx.html')

@app.route('/auditoria-rh')
def auditoria_rh():
    return render_template('validador_rh.html')

@app.route('/validador-json')
def upcoming_module():
    return render_template('em_breve.html')

@app.route('/privacidade')
def privacidade():
    return render_template('privacidade.html')


@app.route('/termos')
def termos():
    return render_template('termos.html')


@app.route('/sobre')
def sobre():
    return render_template('sobre.html')



@app.route('/health', methods=['GET', 'HEAD'])
def health_check():
    response = Response('{"status": "ok"}', status=200, mimetype='application/json')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@app.route('/robots.txt')
def robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /ads.txt\n"
        "Disallow: /api/\n"
        "Disallow: /health\n"
        "\n"
        f"Sitemap: {SITE_DOMAIN}/sitemap.xml\n"
    )
    return Response(content, mimetype='text/plain; charset=utf-8')


@app.route('/ads.txt')
def ads_txt():
    content = "google.com, pub-3178662755020611, DIRECT, f08c47fec0942fa0\n"
    response = Response(content, mimetype='text/plain; charset=utf-8')
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


@app.route('/sitemap.xml')
def sitemap_xml():
    lastmod_date = "2026-10-18"
    urls = [
        ('/', '1.0', 'weekly'),
        ('/validador-texto', '0.9', 'weekly'),
        ('/validador-cadastros', '0.9', 'weekly'),
        ('/validador-xml', '0.9', 'weekly'),
        ('/conciliador-taxas', '0.9', 'weekly'),
        ('/auditoria-rh', '0.9', 'weekly'),
        ('/como-usar', '0.8', 'monthly'),
        ('/sobre', '0.7', 'monthly'),
        ('/privacidade', '0.6', 'monthly'),
        ('/termos', '0.6', 'monthly'),
    ]
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for route_path, priority, changefreq in urls:
        xml_lines.append('  <url>')
        xml_lines.append(f'    <loc>{SITE_DOMAIN}{route_path}</loc>')
        xml_lines.append(f'    <lastmod>{lastmod_date}</lastmod>')
        xml_lines.append(f'    <changefreq>{changefreq}</changefreq>')
        xml_lines.append(f'    <priority>{priority}</priority>')
        xml_lines.append('  </url>')
    xml_lines.append('</urlset>')
    return Response("\n".join(xml_lines), mimetype='application/xml; charset=utf-8')


@app.route('/api/upload-headers', methods=['POST'])
def upload_headers():
    try:
        file_a = request.files.get('file_a')
        file_b = request.files.get('file_b')

        if not file_a or not file_b:
            return jsonify({'error': 'Envie ambos os arquivos (Base Antiga e Base Nova).'}), 400

        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        filename_a = file_a.filename
        filename_b = file_b.filename

        path_a = os.path.join(session_folder, 'base_a_' + filename_a)
        path_b = os.path.join(session_folder, 'base_b_' + filename_b)

        file_a.save(path_a)
        file_b.save(path_b)

        # Ler colunas dos arquivos
        df_a = comparator.read_tabular_file(path_a, filename_a)
        df_b = comparator.read_tabular_file(path_b, filename_b)

        cols_a = list(df_a.columns)
        cols_b = list(df_b.columns)

        mapping = comparator.suggest_column_mappings(cols_a, cols_b)

        # Sugestões de chaves primárias inteligentes
        key_keywords = ['ID', 'SEQ', 'TICKET', 'MATRICULA', 'CODIGO', 'CHAVE', 'CPF', 'NUMERO', 'REGISTRO']
        suggested_keys = []
        
        # Colunas que mapeiam entre si e possuem palavras-chave de identificador
        for col_a, col_b in mapping.items():
            col_norm = comparator.normalize_column_name(col_a)
            if any(k in col_norm for k in key_keywords):
                suggested_keys.append({
                    'col_a': col_a,
                    'col_b': col_b,
                    'score': 10
                })

        # Adiciona outras colunas comuns se não houver muitas
        for col_a, col_b in mapping.items():
            if not any(s['col_a'] == col_a for s in suggested_keys):
                suggested_keys.append({
                    'col_a': col_a,
                    'col_b': col_b,
                    'score': 1
                })

        suggested_keys.sort(key=lambda x: x['score'], reverse=True)

        SESSIONS[session_id] = {
            'path_a': path_a,
            'path_b': path_b,
            'filename_a': filename_a,
            'filename_b': filename_b,
            'cols_a': cols_a,
            'cols_b': cols_b,
            'mapping': mapping,
            'rows_a_count': len(df_a),
            'rows_b_count': len(df_b)
        }

        return jsonify({
            'session_id': session_id,
            'filename_a': filename_a,
            'filename_b': filename_b,
            'rows_a_count': len(df_a),
            'rows_b_count': len(df_b),
            'cols_a': cols_a,
            'cols_b': cols_b,
            'suggested_keys': [s['col_a'] for s in suggested_keys],
            'column_mapping': mapping
        })

    except Exception as e:
        return jsonify({'error': f'Falha ao processar arquivos: {str(e)}'}), 500


@app.route('/api/sheets/load-example', methods=['POST'])
def sheets_load_example():
    try:
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        path_a, filename_a, path_b, filename_b = comparator.create_demo_files(session_folder)

        df_a = comparator.read_tabular_file(path_a, filename_a)
        df_b = comparator.read_tabular_file(path_b, filename_b)

        cols_a = list(df_a.columns)
        cols_b = list(df_b.columns)

        mapping = comparator.suggest_column_mappings(cols_a, cols_b)

        key_keywords = ['ID', 'SEQ', 'TICKET', 'MATRICULA', 'CODIGO', 'CHAVE', 'CPF', 'NUMERO', 'REGISTRO']
        suggested_keys = []
        for col_a, col_b in mapping.items():
            col_norm = comparator.normalize_column_name(col_a)
            if any(k in col_norm for k in key_keywords):
                suggested_keys.append({'col_a': col_a, 'score': 10})

        if not suggested_keys and 'ID_Pedido' in cols_a:
            suggested_keys.append({'col_a': 'ID_Pedido', 'score': 10})

        SESSIONS[session_id] = {
            'path_a': path_a,
            'path_b': path_b,
            'filename_a': filename_a,
            'filename_b': filename_b,
            'cols_a': cols_a,
            'cols_b': cols_b
        }

        return jsonify({
            'session_id': session_id,
            'filename_a': filename_a,
            'filename_b': filename_b,
            'rows_a_count': len(df_a),
            'rows_b_count': len(df_b),
            'cols_a': cols_a,
            'cols_b': cols_b,
            'suggested_keys': [s['col_a'] for s in suggested_keys],
            'column_mapping': mapping
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao carregar exemplo de planilhas: {str(e)}'}), 500


@app.route('/favicon.ico')
def favicon():
    ico_path = os.path.join(BASE_DIR, 'static', 'favicon.ico')
    if os.path.exists(ico_path):
        return send_file(ico_path, mimetype='image/x-icon')
    return send_file(os.path.join(BASE_DIR, 'static', 'images', 'favicon.png'), mimetype='image/png')

@app.route('/api/compare', methods=['POST'])
def compare():
    try:
        data = request.json or {}
        session_id = data.get('session_id')

        if not session_id or session_id not in SESSIONS:
            return jsonify({'error': 'Sessão inválida ou expirada. Faça o upload novamente.'}), 400

        sess = SESSIONS[session_id]
        if 'column_mapping' in data and isinstance(data['column_mapping'], dict):
            custom_mapping = data['column_mapping']
        else:
            custom_mapping = sess.get('mapping', {})
        primary_key_a = data.get('primary_key_a')
        primary_key_b = data.get('primary_key_b')
        if not primary_key_b or primary_key_b not in sess['cols_b']:
            primary_key_b = custom_mapping.get(primary_key_a) or sess.get('mapping', {}).get(primary_key_a, primary_key_a)
        
        # Suporta lista de colunas complementares ou coluna única
        secondary_keys_a = data.get('secondary_keys_a')
        if not secondary_keys_a and data.get('secondary_key_a'):
            secondary_keys_a = [data.get('secondary_key_a')]
        elif not secondary_keys_a:
            secondary_keys_a = []

        normalize_currency = bool(data.get('normalize_currency', True))
        normalize_dates = bool(data.get('normalize_dates', True))
        ignore_case = bool(data.get('ignore_case', True))
        trim_spaces = bool(data.get('trim_spaces', True))

        df_a = comparator.read_tabular_file(sess['path_a'], sess['filename_a'])
        df_b = comparator.read_tabular_file(sess['path_b'], sess['filename_b'])

        summary, diff_records, df_a_idx, df_b_idx, valid_cols_a, final_mapping, only_a, only_b = comparator.compare_datasets(
            df_a, df_b,
            primary_key_a=primary_key_a,
            primary_key_b=primary_key_b,
            secondary_keys_a=secondary_keys_a,
            column_mapping=custom_mapping,
            normalize_currency=normalize_currency,
            normalize_dates=normalize_dates,
            ignore_case=ignore_case,
            trim_spaces=trim_spaces,
            max_sample_rows=300
        )

        # Gera o relatório Excel em background
        report_id = str(uuid.uuid4())
        report_filename = f"Relatorio_Validacao_{report_id[:8]}.xlsx"
        report_path = os.path.join(REPORT_DIR, report_filename)

        comparator.generate_excel_diff_report(
            summary=summary,
            diff_records=diff_records,
            df_a_indexed=df_a_idx,
            df_b_indexed=df_b_idx,
            valid_cols_a=valid_cols_a,
            column_mapping=final_mapping,
            only_in_a=only_a,
            only_in_b=only_b,
            output_path=report_path
        )

        REPORTS[report_id] = {
            'path': report_path,
            'filename': report_filename
        }

        # Formata resposta com resumo e amostra de diferenças para tabela dinâmica
        return jsonify({
            'success': True,
            'report_id': report_id,
            'summary': summary,
            'has_differences': not summary['is_identical'],
            'diff_preview': summary['sample_diff_records'],
            'only_in_a_preview': summary.get('sample_only_in_a', []),
            'only_in_b_preview': summary.get('sample_only_in_b', []),
            'cols_display_a': summary.get('cols_display_a', []),
            'cols_display_b': summary.get('cols_display_b', []),
            'columns_with_differences': summary['columns_with_differences']
        })

    except Exception as e:
        return jsonify({'error': f'Erro na comparação: {str(e)}'}), 500

@app.route('/api/download-report/<report_id>', methods=['GET'])
def download_report(report_id):
    if report_id not in REPORTS:
        return jsonify({'error': 'Relatório não encontrado.'}), 404

    rep = REPORTS[report_id]
    return send_file(
        rep['path'],
        as_attachment=True,
        download_name=rep['filename'],
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ========================================================
# ROTAS DO VALIDADOR / AUDITORIA DE ARQUIVO ÚNICO
# ========================================================

@app.route('/api/single/upload-headers', methods=['POST'])
def single_upload_headers():
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'Nenhum arquivo enviado. Selecione uma planilha (.xlsx, .xls ou .csv).'}), 400

        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        filename = file.filename
        filepath = os.path.join(session_folder, filename)
        file.save(filepath)

        df = comparator.read_tabular_file(filepath, filename)
        cols = list(df.columns)

        # Amostra das primeiras 5 linhas para preview
        sample_rows = []
        for _, row in df.head(5).iterrows():
            row_dict = {}
            for c in cols:
                val = row[c]
                row_dict[c] = "" if (val is None or (hasattr(val, '__iter__') and False) or str(val) == 'nan') else str(val)
            sample_rows.append(row_dict)

        SESSIONS[session_id] = {
            'mode': 'single',
            'path': filepath,
            'filename': filename,
            'cols': cols,
            'total_rows': len(df)
        }

        return jsonify({
            'session_id': session_id,
            'filename': filename,
            'total_rows': len(df),
            'total_cols': len(cols),
            'cols': cols,
            'sample_data': sample_rows
        })

    except Exception as e:
        return jsonify({'error': f'Falha ao carregar arquivo: {str(e)}'}), 500

@app.route('/api/single/audit', methods=['POST'])
def single_audit():
    try:
        data = request.json or {}
        session_id = data.get('session_id')
        rules = data.get('rules', [])

        if not session_id or session_id not in SESSIONS:
            return jsonify({'error': 'Sessão inválida ou expirada. Faça o upload novamente.'}), 400

        if not rules or not isinstance(rules, list):
            return jsonify({'error': 'Configure ao menos uma regra de auditoria antes de continuar.'}), 400

        sess = SESSIONS[session_id]
        df = comparator.read_tabular_file(sess['path'], sess['filename'])

        summary, preview_rows, invalid_cells_by_row, cols = single_auditor.audit_single_dataset(
            df, rules, max_preview_rows=300
        )

        # Gera o relatório Excel estilizado SplitC
        report_id = str(uuid.uuid4())
        report_filename = f"Relatorio_Auditoria_{report_id[:8]}.xlsx"
        report_path = os.path.join(REPORT_DIR, report_filename)

        single_auditor.generate_single_audit_excel(
            df=df,
            summary=summary,
            invalid_cells_by_row=invalid_cells_by_row,
            cols=cols,
            output_path=report_path
        )

        REPORTS[report_id] = {
            'path': report_path,
            'filename': report_filename
        }

        return jsonify({
            'success': True,
            'report_id': report_id,
            'summary': summary,
            'preview_rows': preview_rows,
            'cols': cols
        })

    except Exception as e:
        return jsonify({'error': f'Erro ao executar auditoria: {str(e)}'}), 500

@app.route('/api/single/download-report/<report_id>', methods=['GET'])
def single_download_report(report_id):
    return download_report(report_id)

# ========================================================
# ROTAS DO VALIDADOR DE TEXTO E DOCUMENTOS (PDF/DOCX/TXT)
# ========================================================

@app.route('/api/text/compare', methods=['POST'])
def text_compare():
    try:
        if request.is_json:
            data = request.json or {}
            text_a = data.get('text_a', '')
            text_b = data.get('text_b', '')
            filename_a = data.get('filename_a', 'Documento Original.txt')
            filename_b = data.get('filename_b', 'Documento Novo.txt')
            pages_a = int(data.get('pages_a', 1))
            pages_b = int(data.get('pages_b', 1))
            file_type_a = data.get('file_type_a', 'TXT')
            file_type_b = data.get('file_type_b', 'TXT')
            ignore_case = bool(data.get('ignore_case', False))
            trim_spaces = bool(data.get('trim_spaces', True))
            ignore_empty_lines = bool(data.get('ignore_empty_lines', False))
            diff_granularity = data.get('diff_granularity', 'word')
        else:
            file_a = request.files.get('file_a')
            file_b = request.files.get('file_b')
            text_a_raw = request.form.get('text_a')
            text_b_raw = request.form.get('text_b')

            session_id = str(uuid.uuid4())
            session_folder = os.path.join(UPLOAD_DIR, session_id)
            os.makedirs(session_folder, exist_ok=True)

            if file_a and file_a.filename:
                filename_a = file_a.filename
                path_a = os.path.join(session_folder, 'doc_a_' + filename_a)
                file_a.save(path_a)
                extracted_a = text_comparator.extract_text_from_file(path_a, filename_a)
                text_a = extracted_a['text']
                pages_a = extracted_a['pages_count']
                file_type_a = extracted_a['file_type']
            elif text_a_raw is not None:
                text_a = text_a_raw
                filename_a = request.form.get('filename_a', 'Texto Original')
                pages_a = 1
                file_type_a = 'TXT'
            else:
                return jsonify({'error': 'Envie o Documento Original (.pdf, .docx ou .txt).'}), 400

            if file_b and file_b.filename:
                filename_b = file_b.filename
                path_b = os.path.join(session_folder, 'doc_b_' + filename_b)
                file_b.save(path_b)
                extracted_b = text_comparator.extract_text_from_file(path_b, filename_b)
                text_b = extracted_b['text']
                pages_b = extracted_b['pages_count']
                file_type_b = extracted_b['file_type']
            elif text_b_raw is not None:
                text_b = text_b_raw
                filename_b = request.form.get('filename_b', 'Texto Novo')
                pages_b = 1
                file_type_b = 'TXT'
            else:
                return jsonify({'error': 'Envie o Documento Novo (.pdf, .docx ou .txt).'}), 400

            ignore_case = request.form.get('ignore_case', 'false').lower() == 'true'
            trim_spaces = request.form.get('trim_spaces', 'true').lower() == 'true'
            ignore_empty_lines = request.form.get('ignore_empty_lines', 'false').lower() == 'true'
            diff_granularity = request.form.get('diff_granularity', 'word')

        result = text_comparator.compare_texts(
            text_a=text_a,
            text_b=text_b,
            filename_a=filename_a,
            filename_b=filename_b,
            pages_a=pages_a,
            pages_b=pages_b,
            file_type_a=file_type_a,
            file_type_b=file_type_b,
            ignore_case=ignore_case,
            trim_spaces=trim_spaces,
            ignore_empty_lines=ignore_empty_lines,
            diff_granularity=diff_granularity
        )

        report_id = str(uuid.uuid4())
        report_filename = f"Relatorio_Diferencas_Texto_{report_id[:8]}.pdf"
        report_path = os.path.join(REPORT_DIR, report_filename)

        text_comparator.generate_pdf_diff_report(result, report_path)

        REPORTS[report_id] = {
            'path': report_path,
            'filename': report_filename,
            'mimetype': 'application/pdf'
        }

        return jsonify({
            'success': True,
            'report_id': report_id,
            'summary': result['summary'],
            'side_by_side_blocks': result['side_by_side_blocks'],
            'redline_blocks': result['redline_blocks'],
            'diff_table_rows': result['diff_table_rows'],
            'stats_comparison': result['stats_comparison']
        })

    except Exception as e:
        return jsonify({'error': f'Erro ao comparar documentos: {str(e)}'}), 500

@app.route('/api/text/download-pdf/<report_id>', methods=['GET'])
def download_text_pdf_report(report_id):
    if report_id not in REPORTS:
        return jsonify({'error': 'Relatório PDF não encontrado.'}), 404

    rep = REPORTS[report_id]
    return send_file(
        rep['path'],
        as_attachment=True,
        download_name=rep['filename'],
        mimetype=rep.get('mimetype', 'application/pdf')
    )

# ========================================================
# ROTAS DO HIGIENIZADOR DE CADASTROS (CPF, CNPJ, E-MAIL, ETC.)
# ========================================================

@app.route('/api/cadastros/upload-headers', methods=['POST'])
def cadastros_upload_headers():
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'Nenhum arquivo enviado. Selecione uma planilha de cadastros (.xlsx, .xls ou .csv).'}), 400

        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        filename = file.filename
        filepath = os.path.join(session_folder, filename)
        file.save(filepath)

        df = comparator.read_tabular_file(filepath, filename)
        cols = list(df.columns)

        # Sugestão automática e inteligente de colunas
        def find_col(keywords, exclude=None, avoid_keywords=None):
            if exclude is None:
                exclude = set()
            if avoid_keywords is None:
                avoid_keywords = set()
            for c in cols:
                if c in exclude:
                    continue
                c_norm = comparator.normalize_column_name(c)
                if any(k in c_norm for k in keywords) and not any(ak in c_norm for ak in avoid_keywords):
                    return c
            for c in cols:
                if c in exclude:
                    continue
                c_norm = comparator.normalize_column_name(c)
                if any(k in c_norm for k in keywords):
                    return c
            return ""

        col_doc = find_col(['CPF', 'CNPJ', 'DOC', 'DOCUMENTO', 'RUT', 'IDENTIFICACAO'])
        col_email = find_col(['EMAIL', 'E-MAIL', 'CORREIO', 'MAIL'], exclude={col_doc})
        col_phone = find_col(['TELEFONE', 'CELULAR', 'TEL', 'CEL', 'FONE', 'WHATSAPP'], exclude={col_doc, col_email})
        col_name = find_col(['NOME', 'RAZAO', 'CLIENTE', 'FORNECEDOR', 'FUNCIONARIO', 'LEAD', 'TITULAR', 'CONTATO'], exclude={col_doc, col_email, col_phone}, avoid_keywords=['ID', 'COD', 'MATRICULA'])

        suggested = {
            'col_doc': col_doc,
            'col_name': col_name,
            'col_email': col_email,
            'col_phone': col_phone
        }

        # Amostra das primeiras 5 linhas
        sample_rows = []
        for _, row in df.head(5).iterrows():
            row_dict = {}
            for c in cols:
                val = row[c]
                row_dict[c] = "" if (val is None or str(val) == 'nan') else str(val)
            sample_rows.append(row_dict)

        SESSIONS[session_id] = {
            'mode': 'cadastros',
            'path': filepath,
            'filename': filename,
            'cols': cols,
            'total_rows': len(df)
        }

        return jsonify({
            'session_id': session_id,
            'filename': filename,
            'total_rows': len(df),
            'total_cols': len(cols),
            'cols': cols,
            'suggested': suggested,
            'sample_data': sample_rows
        })

    except Exception as e:
        return jsonify({'error': f'Falha ao carregar base de cadastros: {str(e)}'}), 500


@app.route('/api/cadastros/load-example', methods=['POST'])
def cadastros_load_example():
    try:
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        filepath, filename = cadastros_cleaner.create_demo_file(session_folder)
        df = comparator.read_tabular_file(filepath, filename)
        cols = list(df.columns)

        def find_col(keywords, exclude=None, avoid_keywords=None):
            if exclude is None:
                exclude = set()
            if avoid_keywords is None:
                avoid_keywords = set()
            for c in cols:
                if c in exclude:
                    continue
                c_norm = comparator.normalize_column_name(c)
                if any(k in c_norm for k in keywords) and not any(ak in c_norm for ak in avoid_keywords):
                    return c
            for c in cols:
                if c in exclude:
                    continue
                c_norm = comparator.normalize_column_name(c)
                if any(k in c_norm for k in keywords):
                    return c
            return ""

        col_doc = find_col(['CPF', 'CNPJ', 'DOC', 'DOCUMENTO', 'RUT', 'IDENTIFICACAO'])
        col_email = find_col(['EMAIL', 'E-MAIL', 'CORREIO', 'MAIL'], exclude={col_doc})
        col_phone = find_col(['TELEFONE', 'CELULAR', 'TEL', 'CEL', 'FONE', 'WHATSAPP'], exclude={col_doc, col_email})
        col_name = find_col(['NOME', 'RAZAO', 'CLIENTE', 'FORNECEDOR', 'FUNCIONARIO', 'LEAD', 'TITULAR', 'CONTATO'], exclude={col_doc, col_email, col_phone}, avoid_keywords=['ID', 'COD', 'MATRICULA'])

        suggested = {
            'col_doc': col_doc,
            'col_name': col_name,
            'col_email': col_email,
            'col_phone': col_phone
        }

        sample_rows = []
        for _, row in df.head(5).iterrows():
            row_dict = {}
            for c in cols:
                val = row[c]
                row_dict[c] = "" if (val is None or str(val) == 'nan') else str(val)
            sample_rows.append(row_dict)

        SESSIONS[session_id] = {
            'mode': 'cadastros',
            'path': filepath,
            'filename': filename,
            'cols': cols,
            'total_rows': len(df)
        }

        return jsonify({
            'session_id': session_id,
            'filename': filename,
            'total_rows': len(df),
            'total_cols': len(cols),
            'cols': cols,
            'suggested': suggested,
            'sample_data': sample_rows
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao carregar exemplo de cadastros: {str(e)}'}), 500


@app.route('/api/cadastros/process', methods=['POST'])
def cadastros_process():
    try:
        data = request.json or {}
        session_id = data.get('session_id')

        if not session_id or session_id not in SESSIONS:
            return jsonify({'error': 'Sessão inválida ou expirada. Faça o upload novamente.'}), 400

        sess = SESSIONS[session_id]
        df = comparator.read_tabular_file(sess['path'], sess['filename'])

        options = {
            'col_doc': data.get('col_doc'),
            'col_name': data.get('col_name'),
            'col_email': data.get('col_email'),
            'col_phone': data.get('col_phone'),
            'duplicate_keys': data.get('duplicate_keys', ['doc']),
            'doc_format': data.get('doc_format', 'mask'),
            'auto_recover_zero': bool(data.get('auto_recover_zero', True)),
            'name_title_case': bool(data.get('name_title_case', True)),
            'email_lowercase': bool(data.get('email_lowercase', True)),
            'phone_format': data.get('phone_format', 'mask'),
            'remove_duplicates': bool(data.get('remove_duplicates', False))
        }

        results = cadastros_cleaner.process_cadastros(df, options)

        # Gera os 2 arquivos Excel (Base Higienizada e Relatório de Auditoria Pintado)
        report_id = str(uuid.uuid4())
        clean_filename = f"Base_Higienizada_{report_id[:8]}.xlsx"
        clean_path = os.path.join(REPORT_DIR, clean_filename)
        cadastros_cleaner.generate_clean_excel(results['df_clean'], clean_path)

        audit_filename = f"Relatorio_Auditoria_Cadastros_{report_id[:8]}.xlsx"
        audit_path = os.path.join(REPORT_DIR, audit_filename)
        cadastros_cleaner.generate_audit_excel(
            df_audit=results['df_audit'],
            summary=results['summary'],
            invalid_docs=results['invalid_docs'],
            duplicates=results['duplicates'],
            suspicious_contacts=results['suspicious_contacts'],
            row_cell_errors=results['row_cell_errors'],
            output_path=audit_path
        )

        REPORTS[f"cadastros_clean_{report_id}"] = {
            'path': clean_path,
            'filename': clean_filename
        }
        REPORTS[f"cadastros_audit_{report_id}"] = {
            'path': audit_path,
            'filename': audit_filename
        }

        return jsonify({
            'success': True,
            'report_id': report_id,
            'summary': results['summary'],
            'invalid_docs': results['invalid_docs'],
            'duplicates': results['duplicates'],
            'suspicious_contacts': results['suspicious_contacts'],
            'preview_clean': results['preview_clean'],
            'clean_columns': results['clean_columns']
        })

    except ValueError as ve:
        return jsonify({
            'error': str(ve),
            'title': 'Coluna Incompatível com a Referência'
        }), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar higienização: {str(e)}'}), 500

@app.route('/api/cadastros/download-clean/<report_id>', methods=['GET'])
def cadastros_download_clean(report_id):
    key = f"cadastros_clean_{report_id}"
    if key in REPORTS and os.path.exists(REPORTS[key]['path']):
        return send_file(
            REPORTS[key]['path'],
            as_attachment=True,
            download_name=REPORTS[key]['filename'],
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    return jsonify({'error': 'Arquivo limpo expirado ou não encontrado.'}), 404

@app.route('/api/cadastros/download-audit/<report_id>', methods=['GET'])
def cadastros_download_audit(report_id):
    key = f"cadastros_audit_{report_id}"
    if key in REPORTS and os.path.exists(REPORTS[key]['path']):
        return send_file(
            REPORTS[key]['path'],
            as_attachment=True,
            download_name=REPORTS[key]['filename'],
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    return jsonify({'error': 'Relatório de auditoria expirado ou não encontrado.'}), 404


# ========================================================
# ROTAS DO CONCILIADOR DE XML DE NOTAS FISCAIS (NFe / NFSe)
# ========================================================

@app.route('/api/xml/upload', methods=['POST'])
def xml_upload():
    try:
        xml_files = request.files.getlist('xml_files')
        sheet_file = request.files.get('sheet_file')

        if not xml_files or len(xml_files) == 0 or not xml_files[0].filename:
            return jsonify({'error': 'Envie um arquivo .zip contendo os XMLs ou arquivos .xml de Notas Fiscais.'}), 400
        if not sheet_file or not sheet_file.filename:
            return jsonify({'error': 'Envie a planilha financeira (.xlsx, .xls ou .csv) para conciliação.'}), 400

        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        saved_xml_files = []
        for idx, xf in enumerate(xml_files):
            if not xf.filename:
                continue
            safe_name = os.path.basename(xf.filename)
            x_path = os.path.join(session_folder, f"xml_{idx}_{safe_name}")
            xf.save(x_path)
            saved_xml_files.append((x_path, safe_name))

        invoices, parse_errors = xml_reconciler.extract_xmls_from_files(saved_xml_files)
        if len(invoices) == 0:
            err_detail = parse_errors[0]['error'] if parse_errors else "Nenhum arquivo .xml de Nota Fiscal válido foi localizado no envio."
            return jsonify({'error': f'Falha ao ler XMLs: {err_detail}'}), 400

        sheet_filename = os.path.basename(sheet_file.filename)
        sheet_path = os.path.join(session_folder, f"sheet_{sheet_filename}")
        sheet_file.save(sheet_path)

        df_sheet = comparator.read_tabular_file(sheet_path, sheet_filename)
        cols = list(df_sheet.columns)
        suggested = xml_reconciler.suggest_sheet_columns(cols)

        xml_total_val = round(sum(inv['vNF'] for inv in invoices), 2)
        package_label = saved_xml_files[0][1] if len(saved_xml_files) == 1 else f"{len(saved_xml_files)} arquivos enviados"

        SESSIONS[session_id] = {
            'mode': 'xml',
            'invoices': invoices,
            'parse_errors': parse_errors,
            'sheet_path': sheet_path,
            'sheet_filename': sheet_filename,
            'package_label': package_label,
            'cols': cols
        }

        return jsonify({
            'session_id': session_id,
            'package_label': package_label,
            'xml_count': len(invoices),
            'xml_total_value': xml_total_val,
            'xml_total_value_fmt': xml_reconciler.format_brl(xml_total_val),
            'parse_errors': parse_errors,
            'sheet_filename': sheet_filename,
            'sheet_rows': len(df_sheet),
            'sheet_cols': len(cols),
            'cols': cols,
            'suggested': suggested
        })

    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivos: {str(e)}'}), 500


@app.route('/api/xml/load-example', methods=['POST'])
def xml_load_example():
    try:
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        zip_path, zip_name, excel_path, excel_name = xml_reconciler.create_demo_files(session_folder)
        invoices, parse_errors = xml_reconciler.extract_xmls_from_files([(zip_path, zip_name)])
        df_sheet = comparator.read_tabular_file(excel_path, excel_name)
        cols = list(df_sheet.columns)
        suggested = xml_reconciler.suggest_sheet_columns(cols)
        xml_total_val = round(sum(inv['vNF'] for inv in invoices), 2)

        SESSIONS[session_id] = {
            'mode': 'xml',
            'invoices': invoices,
            'parse_errors': parse_errors,
            'sheet_path': excel_path,
            'sheet_filename': excel_name,
            'package_label': zip_name,
            'cols': cols
        }

        return jsonify({
            'session_id': session_id,
            'package_label': zip_name,
            'xml_count': len(invoices),
            'xml_total_value': xml_total_val,
            'xml_total_value_fmt': xml_reconciler.format_brl(xml_total_val),
            'parse_errors': parse_errors,
            'sheet_filename': excel_name,
            'sheet_rows': len(df_sheet),
            'sheet_cols': len(cols),
            'cols': cols,
            'suggested': suggested
        })

    except Exception as e:
        return jsonify({'error': f'Erro ao gerar lote de exemplo: {str(e)}'}), 500


@app.route('/api/xml/reconcile', methods=['POST'])
def xml_reconcile():
    try:
        data = request.json or {}
        session_id = data.get('session_id')

        if not session_id or session_id not in SESSIONS:
            return jsonify({'error': 'Sessão inválida ou expirada. Faça o upload novamente.'}), 400

        sess = SESSIONS[session_id]
        df_sheet = comparator.read_tabular_file(sess['sheet_path'], sess['sheet_filename'])
        invoices = sess['invoices']

        options = {
            'col_nf': data.get('col_nf'),
            'col_val': data.get('col_val'),
            'col_cnpj': data.get('col_cnpj'),
            'col_tax': data.get('col_tax'),
            'col_fornecedor': data.get('col_fornecedor'),
            'tolerance': data.get('tolerance', 0.05),
            'ignore_leading_zeros': bool(data.get('ignore_leading_zeros', True)),
            'ignore_cnpj_punct': bool(data.get('ignore_cnpj_punct', True)),
            'check_missing_in_excel': bool(data.get('check_missing_in_excel', True)),
            'check_missing_xml': bool(data.get('check_missing_xml', True)),
            'check_taxes': bool(data.get('check_taxes', True))
        }

        res = xml_reconciler.reconcile_xml_vs_sheet(invoices, df_sheet, options)

        report_id = str(uuid.uuid4())
        audit_filename = f"Relatorio_Conciliacao_XML_{report_id[:8]}.xlsx"
        audit_path = os.path.join(REPORT_DIR, audit_filename)
        xml_reconciler.generate_xml_audit_excel(df_sheet, res, audit_path)

        mirror_filename = f"Espelho_Notas_Fiscais_XML_{report_id[:8]}.xlsx"
        mirror_path = os.path.join(REPORT_DIR, mirror_filename)
        xml_reconciler.generate_xml_mirror_excel(res['all_xml_mirror'], mirror_path)

        REPORTS[f"xml_audit_{report_id}"] = {
            'path': audit_path,
            'filename': audit_filename
        }
        REPORTS[f"xml_mirror_{report_id}"] = {
            'path': mirror_path,
            'filename': mirror_filename
        }

        return jsonify({
            'success': True,
            'report_id': report_id,
            'summary': res['summary'],
            'divergences': res['divergences'],
            'missing_in_excel': res['missing_in_excel'],
            'missing_xml': res['missing_xml'],
            'all_xml_mirror': res['all_xml_mirror']
        })

    except ValueError as ve:
        return jsonify({
            'error': str(ve),
            'title': 'Coluna Incompatível com a Referência Fiscal'
        }), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao executar conciliação de XML: {str(e)}'}), 500


@app.route('/api/xml/download-audit/<report_id>', methods=['GET'])
def xml_download_audit(report_id):
    key = f"xml_audit_{report_id}"
    if key in REPORTS and os.path.exists(REPORTS[key]['path']):
        return send_file(
            REPORTS[key]['path'],
            as_attachment=True,
            download_name=REPORTS[key]['filename'],
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    return jsonify({'error': 'Relatório de auditoria expirado ou não encontrado.'}), 404


@app.route('/api/xml/download-mirror/<report_id>', methods=['GET'])
def xml_download_mirror(report_id):
    key = f"xml_mirror_{report_id}"
    if key in REPORTS and os.path.exists(REPORTS[key]['path']):
        return send_file(
            REPORTS[key]['path'],
            as_attachment=True,
            download_name=REPORTS[key]['filename'],
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    return jsonify({'error': 'Planilha espelho expirada ou não encontrada.'}), 404


# ========================================================
# ROTAS DO CONCILIADOR DE TAXAS E EXTRATOS (.OFX)
# ========================================================

@app.route('/api/ofx/upload', methods=['POST'])
def ofx_upload():
    try:
        ofx_files = request.files.getlist('ofx_files')
        sheet_file = request.files.get('sheet_file')

        if not ofx_files or not ofx_files[0].filename:
            return jsonify({'error': 'Envie ao menos um extrato bancário no formato .OFX ou .ZIP.'}), 400

        if not sheet_file or not sheet_file.filename:
            return jsonify({'error': 'Envie o relatório de vendas do PDV/ERP (.xlsx, .xls ou .csv).'}), 400

        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        saved_ofx_files = []
        for f in ofx_files:
            if f.filename:
                safe_name = os.path.basename(f.filename)
                f_path = os.path.join(session_folder, safe_name)
                f.save(f_path)
                saved_ofx_files.append((f_path, safe_name))

        sheet_filename = os.path.basename(sheet_file.filename)
        sheet_path = os.path.join(session_folder, sheet_filename)
        sheet_file.save(sheet_path)

        transactions, parse_errors = ofx_reconciler.extract_ofx_from_uploaded_files(saved_ofx_files)
        if not transactions and parse_errors:
            return jsonify({'error': f"Falha ao ler transações do arquivo OFX: {parse_errors[0]['error']}"}), 400
        elif not transactions:
            return jsonify({'error': 'Nenhuma transação válida encontrada no(s) arquivo(s) OFX enviado(s).'}), 400

        df_sheet = comparator.read_tabular_file(sheet_path, sheet_filename)
        cols = list(df_sheet.columns)
        suggested = ofx_reconciler.suggest_sheet_columns(cols)

        ofx_label = saved_ofx_files[0][1] if len(saved_ofx_files) == 1 else f"{len(saved_ofx_files)} arquivos OFX"

        SESSIONS[session_id] = {
            'mode': 'ofx',
            'transactions': transactions,
            'parse_errors': parse_errors,
            'sheet_path': sheet_path,
            'sheet_filename': sheet_filename,
            'ofx_label': ofx_label,
            'cols': cols
        }

        return jsonify({
            'session_id': session_id,
            'ofx_label': ofx_label,
            'ofx_count': len(transactions),
            'parse_errors': parse_errors,
            'sheet_filename': sheet_filename,
            'sheet_rows': len(df_sheet),
            'sheet_cols': len(cols),
            'cols': cols,
            'suggested': suggested
        })

    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivos OFX e planilha: {str(e)}'}), 500


@app.route('/api/ofx/load-example', methods=['POST'])
def ofx_load_example():
    try:
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        ofx_path, ofx_name, excel_path, excel_name = ofx_reconciler.create_demo_files(session_folder)
        transactions, parse_errors = ofx_reconciler.extract_ofx_from_uploaded_files([(ofx_path, ofx_name)])
        df_sheet = comparator.read_tabular_file(excel_path, excel_name)
        cols = list(df_sheet.columns)
        suggested = ofx_reconciler.suggest_sheet_columns(cols)

        SESSIONS[session_id] = {
            'mode': 'ofx',
            'transactions': transactions,
            'parse_errors': parse_errors,
            'sheet_path': excel_path,
            'sheet_filename': excel_name,
            'ofx_label': ofx_name,
            'cols': cols
        }

        return jsonify({
            'session_id': session_id,
            'ofx_label': ofx_name,
            'ofx_count': len(transactions),
            'parse_errors': parse_errors,
            'sheet_filename': excel_name,
            'sheet_rows': len(df_sheet),
            'sheet_cols': len(cols),
            'cols': cols,
            'suggested': suggested
        })

    except Exception as e:
        return jsonify({'error': f'Erro ao gerar dados de exemplo OFX: {str(e)}'}), 500


@app.route('/api/ofx/reconcile', methods=['POST'])
def ofx_reconcile():
    try:
        data = request.json or {}
        session_id = data.get('session_id')

        if not session_id or session_id not in SESSIONS:
            return jsonify({'error': 'Sessão inválida ou expirada. Faça o upload novamente.'}), 400

        sess = SESSIONS[session_id]
        df_sales = comparator.read_tabular_file(sess['sheet_path'], sess['sheet_filename'])
        transactions = sess['transactions']

        col_id = data.get('col_id')
        col_gross_val = data.get('col_gross_val')
        col_date = data.get('col_date')
        col_acquirer = data.get('col_acquirer')
        expected_rate_pct = float(data.get('expected_rate_pct', 3.5))
        tolerance_cents = float(data.get('tolerance_cents', 0.05))
        date_tolerance_days = int(data.get('date_tolerance_days', 3))

        res = ofx_reconciler.reconcile_ofx_vs_sales(
            df_sales=df_sales,
            ofx_transactions=transactions,
            col_id=col_id,
            col_gross_val=col_gross_val,
            col_date=col_date,
            col_acquirer=col_acquirer,
            expected_rate_pct=expected_rate_pct,
            tolerance_cents=tolerance_cents,
            date_tolerance_days=date_tolerance_days
        )

        report_id = str(uuid.uuid4())
        logo_path = os.path.join(app.root_path, 'static', 'images', 'logo.png')
        if not os.path.exists(logo_path):
            logo_path = None

        audit_filename = f"Relatorio_Auditoria_Taxas_OFX_{report_id[:8]}.xlsx"
        audit_path = os.path.join(REPORT_DIR, audit_filename)
        ofx_reconciler.generate_audit_report(res, audit_path, logo_path=logo_path)

        mirror_filename = f"Espelho_Extrato_OFX_{report_id[:8]}.xlsx"
        mirror_path = os.path.join(REPORT_DIR, mirror_filename)
        ofx_reconciler.generate_ofx_mirror_report(transactions, mirror_path, logo_path=logo_path)

        REPORTS[f"ofx_audit_{report_id}"] = {
            'path': audit_path,
            'filename': audit_filename
        }
        REPORTS[f"ofx_mirror_{report_id}"] = {
            'path': mirror_path,
            'filename': mirror_filename
        }

        sess['last_result'] = res
        sess['last_report_id'] = report_id

        return jsonify({
            'success': True,
            'report_id': report_id,
            'kpis': res['kpis'],
            'items': res['items']
        })

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao executar conciliação de taxas: {str(e)}'}), 500


@app.route('/api/ofx/download-audit/<report_id>', methods=['GET'])
def ofx_download_audit(report_id):
    key = f"ofx_audit_{report_id}"
    if key in REPORTS and os.path.exists(REPORTS[key]['path']):
        return send_file(
            REPORTS[key]['path'],
            as_attachment=True,
            download_name=REPORTS[key]['filename'],
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    return jsonify({'error': 'Relatório de auditoria de taxas expirado ou não encontrado.'}), 404


@app.route('/api/ofx/download-mirror/<report_id>', methods=['GET'])
def ofx_download_mirror(report_id):
    key = f"ofx_mirror_{report_id}"
    if key in REPORTS and os.path.exists(REPORTS[key]['path']):
        return send_file(
            REPORTS[key]['path'],
            as_attachment=True,
            download_name=REPORTS[key]['filename'],
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    return jsonify({'error': 'Espelho do extrato OFX expirado ou não encontrado.'}), 404



# ========================================================
# ROTAS DA AUDITORIA DE FOLHA E RH (/auditoria-rh)
# ========================================================

@app.route('/api/rh/upload-headers', methods=['POST'])
def rh_upload_headers():
    try:
        file_ref = request.files.get('file_ref')
        file_audit = request.files.get('file_audit')
        mode = request.form.get('mode', 'folha')

        if not file_ref or not file_audit:
            return jsonify({'error': 'Envie ambos os arquivos (Base de Referência e Base Auditada).'}), 400

        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        filename_ref = file_ref.filename
        filename_audit = file_audit.filename

        path_ref = os.path.join(session_folder, 'ref_' + filename_ref)
        path_audit = os.path.join(session_folder, 'audit_' + filename_audit)

        file_ref.save(path_ref)
        file_audit.save(path_audit)

        df_ref = comparator.read_tabular_file(path_ref, filename_ref)
        df_audit = comparator.read_tabular_file(path_audit, filename_audit)

        cols_ref = list(df_ref.columns)
        cols_audit = list(df_audit.columns)

        mapping = comparator.suggest_column_mappings(cols_ref, cols_audit)
        key_suggestion = rh_auditor.suggest_employee_keys(cols_ref, cols_audit)

        name_ref = rh_auditor.find_name_column(cols_ref)
        name_audit = rh_auditor.find_name_column(cols_audit)

        SESSIONS[session_id] = {
            'mode': mode,
            'path_ref': path_ref,
            'path_audit': path_audit,
            'filename_ref': filename_ref,
            'filename_audit': filename_audit,
            'cols_ref': cols_ref,
            'cols_audit': cols_audit,
            'mapping': mapping,
            'rows_ref_count': len(df_ref),
            'rows_audit_count': len(df_audit)
        }

        return jsonify({
            'session_id': session_id,
            'mode': mode,
            'filename_ref': filename_ref,
            'filename_audit': filename_audit,
            'rows_ref_count': len(df_ref),
            'rows_audit_count': len(df_audit),
            'cols_ref': cols_ref,
            'cols_audit': cols_audit,
            'column_mapping': mapping,
            'suggested_key_ref': key_suggestion['primary_ref'],
            'suggested_key_audit': key_suggestion['primary_audit'],
            'is_cpf': key_suggestion['is_cpf'],
            'name_col_ref': name_ref,
            'name_col_audit': name_audit
        })

    except Exception as e:
        return jsonify({'error': f'Falha ao ler arquivos de RH: {str(e)}'}), 500


@app.route('/api/rh/load-example', methods=['POST'])
def rh_load_example():
    try:
        data = request.json or {}
        mode = data.get('mode', 'folha')

        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        path_ref, filename_ref, path_audit, filename_audit = rh_auditor.create_demo_files(session_folder, mode=mode)

        df_ref = comparator.read_tabular_file(path_ref, filename_ref)
        df_audit = comparator.read_tabular_file(path_audit, filename_audit)

        cols_ref = list(df_ref.columns)
        cols_audit = list(df_audit.columns)

        mapping = comparator.suggest_column_mappings(cols_ref, cols_audit)
        key_suggestion = rh_auditor.suggest_employee_keys(cols_ref, cols_audit)

        name_ref = rh_auditor.find_name_column(cols_ref)
        name_audit = rh_auditor.find_name_column(cols_audit)

        SESSIONS[session_id] = {
            'mode': mode,
            'path_ref': path_ref,
            'path_audit': path_audit,
            'filename_ref': filename_ref,
            'filename_audit': filename_audit,
            'cols_ref': cols_ref,
            'cols_audit': cols_audit,
            'mapping': mapping,
            'rows_ref_count': len(df_ref),
            'rows_audit_count': len(df_audit)
        }

        return jsonify({
            'session_id': session_id,
            'mode': mode,
            'filename_ref': filename_ref,
            'filename_audit': filename_audit,
            'rows_ref_count': len(df_ref),
            'rows_audit_count': len(df_audit),
            'cols_ref': cols_ref,
            'cols_audit': cols_audit,
            'column_mapping': mapping,
            'suggested_key_ref': key_suggestion['primary_ref'],
            'suggested_key_audit': key_suggestion['primary_audit'],
            'is_cpf': key_suggestion['is_cpf'],
            'name_col_ref': name_ref,
            'name_col_audit': name_audit
        })

    except Exception as e:
        return jsonify({'error': f'Falha ao carregar bases demonstrativas de RH: {str(e)}'}), 500


@app.route('/api/rh/audit', methods=['POST'])
def rh_execute_audit():
    try:
        data = request.json or {}
        session_id = data.get('session_id')

        if not session_id or session_id not in SESSIONS:
            return jsonify({'error': 'Sessão inválida ou expirada. Faça o envio das bases novamente.'}), 400

        sess = SESSIONS[session_id]
        df_ref = comparator.read_tabular_file(sess['path_ref'], sess['filename_ref'])
        df_audit = comparator.read_tabular_file(sess['path_audit'], sess['filename_audit'])

        options = {
            'mode': data.get('mode', sess.get('mode', 'folha')),
            'key_ref': data.get('key_ref'),
            'key_audit': data.get('key_audit'),
            'sec_key_ref': data.get('sec_key_ref'),
            'sec_key_audit': data.get('sec_key_audit'),
            'name_col_ref': data.get('name_col_ref'),
            'name_col_audit': data.get('name_col_audit'),
            'normalize_cpf': bool(data.get('normalize_cpf', True)),
            'ignore_accents': bool(data.get('ignore_accents', True)),
            'variation_threshold': float(data.get('variation_threshold', 10.0)),
            'column_mapping': data.get('column_mapping', {})
        }

        res = rh_auditor.audit_rh_bases(df_ref, df_audit, options)

        report_id = str(uuid.uuid4())
        audit_filename = f"Relatorio_Auditoria_RH_{report_id[:8]}.xlsx"
        audit_path = os.path.join(REPORT_DIR, audit_filename)

        logo_path = os.path.join(app.root_path, 'static', 'images', 'logo.png')
        if not os.path.exists(logo_path):
            logo_path = None

        rh_auditor.generate_rh_audit_excel(res, audit_path, logo_path=logo_path)

        REPORTS[f"rh_audit_{report_id}"] = {
            'path': audit_path,
            'filename': audit_filename
        }

        sess['last_result'] = res
        sess['last_report_id'] = report_id

        return jsonify({
            'success': True,
            'report_id': report_id,
            'kpis': res['kpis'],
            'financial_summary': res['financial_summary'],
            'divergences': res['divergences'],
            'critical_variations': res['critical_variations'],
            'exclusive_ref': res['exclusive_ref'],
            'exclusive_audit': res['exclusive_audit']
        })

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao executar auditoria de RH: {str(e)}'}), 500


@app.route('/api/rh/download-report/<report_id>', methods=['GET'])
def rh_download_report(report_id):
    key = f"rh_audit_{report_id}"
    if key in REPORTS and os.path.exists(REPORTS[key]['path']):
        return send_file(
            REPORTS[key]['path'],
            as_attachment=True,
            download_name=REPORTS[key]['filename'],
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    return jsonify({'error': 'Relatório de auditoria de RH expirado ou não encontrado.'}), 404


if __name__ == '__main__':
    print("Iniciando Validador de Dados em http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)


