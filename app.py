import os
import uuid
import json
import gzip
import logging
import gc
import time
import shutil
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

try:
    import brotli
except ImportError:
    brotli = None
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, Response, session, redirect, url_for
import comparator
import single_auditor
import text_comparator
import cadastros_cleaner
import xml_reconciler
import ofx_reconciler
import rh_auditor

# Serviços do Sistema de Planos, Supabase e Pagamentos
from services.supabase_service import SupabaseService
from services.plan_manager import (
    PLANS,
    get_user_summary_for_ui,
    check_validation_permission,
    record_validation_usage
)
from services.mercadopago_service import MercadoPagoService
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'validai_fallback_secret_key_2026')
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024  # Proteção de RAM (Render Free 512MB) - Limite 12MB
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000    # Cache estático de 1 ano (31536000s)


@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def request_entity_too_large(error):
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({
            'error': 'O arquivo enviado excede o limite máximo permitido de 12 MB. '
                     'Para garantir a estabilidade do servidor em nuvem, comprima o arquivo ou divida em lotes menores.'
        }), 413
    return render_template('index.html', upload_error='Arquivo excede o limite de 12 MB.'), 413

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

    # Sinalização explícita de idioma nativo (pt-BR) e HTTP Link hreflang para páginas HTML públicas
    response.headers['Content-Language'] = 'pt-BR'
    if (
        response.status_code == 200
        and response.mimetype == 'text/html'
        and not request.path.startswith(('/login', '/cadastro', '/checkout', '/auth/', '/webhook/', '/api/'))
    ):
        canonical_href = f"{SITE_DOMAIN}{request.path}"
        response.headers['Link'] = (
            f'<{canonical_href}>; rel="alternate"; hreflang="pt-br", '
            f'<{canonical_href}>; rel="alternate"; hreflang="x-default"'
        )

    # Blindagem de indexação em rotas transacionais/privadas (noindex, nofollow)
    if request.path.startswith(('/login', '/cadastro', '/checkout', '/auth/', '/webhook/')):
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'

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


def cleanup_old_temp_files(max_age_seconds=3600):
    """
    Remove arquivos e pastas temporárias em UPLOAD_DIR e REPORT_DIR com idade > max_age_seconds (padrão: 1 hora),
    além de purgar sessões e relatórios antigos da memória para preservar o disco efêmero e a RAM no Render.
    """
    now = time.time()

    # 1. Limpeza de subpastas e arquivos em UPLOAD_DIR
    if os.path.exists(UPLOAD_DIR):
        try:
            for item in os.listdir(UPLOAD_DIR):
                item_path = os.path.join(UPLOAD_DIR, item)
                try:
                    mtime = os.path.getmtime(item_path)
                    if (now - mtime) > max_age_seconds:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                        else:
                            os.remove(item_path)
                except Exception as err:
                    logger.warning(f"Erro ao limpar item temporário em UPLOAD_DIR ({item}): {err}")
        except Exception as e:
            logger.warning(f"Erro ao listar UPLOAD_DIR para limpeza: {e}")

    # 2. Limpeza de arquivos em REPORT_DIR
    if os.path.exists(REPORT_DIR):
        try:
            for item in os.listdir(REPORT_DIR):
                item_path = os.path.join(REPORT_DIR, item)
                try:
                    mtime = os.path.getmtime(item_path)
                    if (now - mtime) > max_age_seconds:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                        else:
                            os.remove(item_path)
                except Exception as err:
                    logger.warning(f"Erro ao limpar relatório temporário em REPORT_DIR ({item}): {err}")
        except Exception as e:
            logger.warning(f"Erro ao listar REPORT_DIR para limpeza: {e}")

    # 3. Purga em memória: SESSIONS
    try:
        for sid in list(SESSIONS.keys()):
            sess_info = SESSIONS.get(sid)
            if not sess_info:
                SESSIONS.pop(sid, None)
                continue
            created_at = sess_info.get('created_at')
            if created_at is None:
                folder = os.path.join(UPLOAD_DIR, sid)
                if os.path.exists(folder):
                    try:
                        created_at = os.path.getmtime(folder)
                    except Exception:
                        created_at = 0
                else:
                    created_at = 0
            if (now - created_at) > max_age_seconds:
                SESSIONS.pop(sid, None)
    except Exception as e:
        logger.warning(f"Erro ao purgar SESSIONS antigas: {e}")

    # 4. Purga em memória: REPORTS
    try:
        for rid in list(REPORTS.keys()):
            rep_info = REPORTS.get(rid)
            if not rep_info:
                REPORTS.pop(rid, None)
                continue
            created_at = rep_info.get('created_at')
            if created_at is None:
                rep_path = rep_info.get('path')
                if rep_path and os.path.exists(rep_path):
                    try:
                        created_at = os.path.getmtime(rep_path)
                    except Exception:
                        created_at = 0
                else:
                    created_at = 0
            if (now - created_at) > max_age_seconds:
                REPORTS.pop(rid, None)
    except Exception as e:
        logger.warning(f"Erro ao purgar REPORTS antigos: {e}")


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
    '/auditoria-rh': {
        'title': 'Auditoria de Folha e RH | ValidAí',
        'description': 'Batimento automatizado de folha de pagamento (mês anterior vs. atual) e conciliação de ativos do RH contra faturas de benefícios corporativos.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png',
        'module_name': 'Auditoria de Folha e RH',
        'module_sub': 'Batimento de folha de pagamento, proventos, descontos e benefícios corporativos.'
    },
    '/privacidade': {
        'title': 'Política de Privacidade | ValidAí',
        'description': 'Entenda como o ValidAí trata e protege seus dados conforme a LGPD. Processamento seguro na memória e privacidade total de arquivos.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/termos': {
        'title': 'Termos de Uso | ValidAí',
        'description': 'Termos e condições gerais de uso da plataforma ValidAí para validação de dados, arquivos e cadastros corporativos.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/sobre': {
        'title': 'Sobre o ValidAí | Quem Somos e Nossa Missão',
        'description': 'Conheça a história e a missão do ValidAí: simplificar a validação e higienização de arquivos, planilhas e cadastros corporativos no Brasil.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/planos': {
        'title': 'Planos e Preços | ValidAí - Validador de Arquivos e Dados',
        'description': 'Conheça os planos do ValidAí: Standard (Gratuito) com validações diárias sem cadastro, Plus (R$ 4,99) e Pro (R$ 9,99) com arquivos completos, zero anúncios e sem limites.',
        'robots': 'index, follow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/login': {
        'title': 'Entrar na Conta | ValidAí',
        'description': 'Acesse sua conta no ValidAí para gerenciar seu plano e histórico de validações.',
        'robots': 'noindex, nofollow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    '/cadastro': {
        'title': 'Criar Conta Gratuita | ValidAí',
        'description': 'Crie sua conta no ValidAí para validar planilhas, cadastros e notas fiscais.',
        'robots': 'noindex, nofollow',
        'og_image': f'{SITE_DOMAIN}/static/images/logo.png'
    },
    # Rotas "Em Breve" protegidas contra desperdício de Crawl Budget e Soft 404
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
    user_summary = get_user_summary_for_ui()
    # show_ads: True para visitantes anônimos e plano Standard; False para assinantes Plus e Pro
    show_ads = user_summary.get('show_ads', True)
    return {
        'show_ads': show_ads,
        'adsense_client_id': adsense_id,
        'adsense_slots_enabled': slots_enabled,
        'user_summary': user_summary,
        'plans_config': PLANS,
        'supabase_url': os.environ.get('SUPABASE_URL', '').strip(),
        'supabase_key': os.environ.get('SUPABASE_KEY', '').strip()
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


@app.route('/planos')
def planos():
    return render_template('planos.html', plans=PLANS)


@app.route('/checkout/<plan_name>')
def checkout(plan_name):
    plan_key = (plan_name or '').lower().strip()
    if plan_key not in ['plus', 'pro']:
        return redirect('/planos')

    user_id = session.get('user_id')
    if not user_id:
        return redirect(f"/login?next=/checkout/{plan_key}&info=auth_required")

    user_email = session.get('user_email')
    if not user_email:
        user = SupabaseService.get_user_by_id(user_id)
        if user:
            user_email = user.get('email')
            session['user_email'] = user_email

    init_url, err = MercadoPagoService.create_plan_preference(
        plan_name=plan_key,
        user_email=user_email or 'cliente@validai.app.br',
        user_id=user_id
    )

    if err or not init_url:
        return render_template('planos.html', plans=PLANS, checkout_error=err or "Não foi possível iniciar o checkout.")

    return redirect(init_url)


@app.route('/webhook/mercadopago', methods=['POST', 'GET'])
def webhook_mercadopago():
    try:
        data = request.json or {}
        payment_id = request.args.get('id') or data.get('data', {}).get('id') or data.get('id')

        if not payment_id:
            return jsonify({'status': 'ignored', 'reason': 'no payment id'}), 200

        payment = MercadoPagoService.get_payment_details(payment_id)
        if not payment:
            return jsonify({'status': 'error', 'message': 'Payment details not found'}), 200

        status = payment.get('status')
        external_ref_raw = payment.get('external_reference')

        if status == 'approved' and external_ref_raw:
            try:
                ext_data = json.loads(external_ref_raw)
                user_id = ext_data.get('user_id')
                email = ext_data.get('email')
                plan = ext_data.get('plan')
            except Exception:
                user_id = external_ref_raw
                email = None
                plan = 'pro'

            target = user_id or email
            if target and plan:
                SupabaseService.update_user_plan(
                    user_id_or_email=target,
                    plan=plan,
                    days=30,
                    payment_id=str(payment_id)
                )
                logger.info(f"Plano {plan} aprovado com sucesso para {target} via MP #{payment_id}")

        return jsonify({'status': 'received'}), 200

    except Exception as e:
        logger.error(f"Erro no processamento do webhook Mercado Pago: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 200


# ========================================================
# ROTAS DE AUTENTICAÇÃO (SESSÃO / SUPABASE)
# ========================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        next_url = request.args.get('next') or request.form.get('next') or '/'
        return redirect(next_url)

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = (request.form.get('password') or '').strip()
        next_url = request.form.get('next') or '/'

        if not email or not password:
            return render_template('login.html', error_msg='E-mail e senha são obrigatórios.')

        user, err = SupabaseService.authenticate_user(email, password)
        if err or not user:
            return render_template('login.html', error_msg=err or 'E-mail ou senha inválidos.')

        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session.permanent = True

        return redirect(next_url)

    info_msg = None
    if request.args.get('info') == 'auth_required':
        info_msg = 'Por favor, identifique-se ou crie sua conta para concluir a contratação do plano.'

    return render_template('login.html', info_msg=info_msg)


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if session.get('user_id'):
        next_url = request.args.get('next') or request.form.get('next') or '/'
        return redirect(next_url)

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = (request.form.get('password') or '').strip()
        password_confirm = (request.form.get('password_confirm') or '').strip()
        terms_accepted = bool(request.form.get('terms'))
        next_url = request.form.get('next') or '/'

        if not email or not password:
            return render_template('cadastro.html', error_msg='E-mail e senha são obrigatórios.')
        if len(password) < 6:
            return render_template('cadastro.html', error_msg='A senha deve conter ao menos 6 caracteres.')
        if not password_confirm or password != password_confirm:
            return render_template('cadastro.html', error_msg='As senhas não coincidem. Repita a senha criada com atenção.')
        if not terms_accepted:
            return render_template('cadastro.html', error_msg='Você deve aceitar os Termos de Uso e a Política de Privacidade para criar uma conta.')

        user, err = SupabaseService.create_user(email, password, plan='standard')
        if err or not user:
            return render_template('cadastro.html', error_msg=err or 'Não foi possível criar sua conta.')

        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session.permanent = True

        return redirect(next_url)

    return render_template('cadastro.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_email', None)
    return redirect('/')


@app.route('/auth/callback', methods=['GET'])
def auth_callback():
    error = request.args.get('error')
    error_desc = request.args.get('error_description')
    if error:
        return redirect(f"/login?error={error_desc or error}")

    code = request.args.get('code')
    if code:
        client = SupabaseService.get_client()
        if client:
            try:
                auth_res = client.auth.exchange_code_for_session({'auth_code': code})
                if auth_res and auth_res.user:
                    user_id = auth_res.user.id
                    email = auth_res.user.email
                    profile, err = SupabaseService.get_or_create_oauth_user(user_id=user_id, email=email)
                    if profile:
                        session['user_id'] = profile['id']
                        session['user_email'] = profile['email']
                        session.permanent = True
                        return redirect('/')
            except Exception as e:
                logger.warning(f"Erro ao trocar código OAuth no servidor: {e}")

    return render_template('auth_callback.html',
                           supabase_url=os.environ.get('SUPABASE_URL', '').strip(),
                           supabase_key=os.environ.get('SUPABASE_KEY', '').strip())


@app.route('/api/auth/oauth-callback', methods=['POST'])
def api_auth_oauth_callback():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    user_id = data.get('user_id')
    access_token = data.get('access_token')

    if not email:
        return jsonify({'success': False, 'error': 'E-mail não fornecido pelo provedor OAuth.'}), 400

    client = SupabaseService.get_client()
    if client and access_token:
        try:
            user_check = client.auth.get_user(access_token)
            if user_check and user_check.user:
                email = user_check.user.email or email
                user_id = user_check.user.id or user_id
        except Exception as e:
            logger.warning(f"Aviso ao validar token OAuth no Supabase: {e}")

    profile, err = SupabaseService.get_or_create_oauth_user(user_id=user_id, email=email)
    if err or not profile:
        return jsonify({'success': False, 'error': err or 'Falha ao sincronizar perfil do usuário.'}), 400

    session['user_id'] = profile['id']
    session['user_email'] = profile['email']
    session.permanent = True

    return jsonify({
        'success': True,
        'redirect': '/',
        'user': {
            'id': profile['id'],
            'email': profile['email'],
            'plan': profile.get('plan', 'standard')
        }
    })


@app.route('/api/auth/recuperar-senha', methods=['POST'])
def api_auth_recuperar_senha():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'Informe um e-mail válido.'}), 400

    ok, msg = SupabaseService.reset_password(email, redirect_url=f"{SITE_DOMAIN}/login?info=senha_reset")
    return jsonify({'success': ok, 'message': msg})


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not email or not password:
        return jsonify({'success': False, 'error': 'E-mail e senha são obrigatórios.'}), 400

    user, err = SupabaseService.authenticate_user(email, password)
    if err or not user:
        return jsonify({'success': False, 'error': err or 'Credenciais inválidas.'}), 401

    session['user_id'] = user['id']
    session['user_email'] = user['email']
    session.permanent = True

    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'plan': user.get('plan', 'standard')
        }
    })


@app.route('/api/auth/cadastro', methods=['POST'])
def api_auth_cadastro():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    password_confirm = (data.get('password_confirm') or '').strip()
    terms = data.get('terms')

    if not email or not password:
        return jsonify({'success': False, 'error': 'E-mail e senha são obrigatórios.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'A senha deve ter no mínimo 6 caracteres.'}), 400
    if not password_confirm or password != password_confirm:
        return jsonify({'success': False, 'error': 'As senhas não coincidem. Repita a senha criada com atenção.'}), 400
    if not terms:
        return jsonify({'success': False, 'error': 'Você deve aceitar os Termos de Uso e a Política de Privacidade.'}), 400

    user, err = SupabaseService.create_user(email, password, plan='standard')
    if err or not user:
        return jsonify({'success': False, 'error': err or 'Não foi possível cadastrar usuário.'}), 400

    session['user_id'] = user['id']
    session['user_email'] = user['email']
    session.permanent = True

    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'plan': user.get('plan', 'standard')
        }
    })


@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    summary = get_user_summary_for_ui()
    return jsonify({'success': True, 'summary': summary})



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
        "Allow: /llms.txt\n"
        "Disallow: /api/\n"
        "Disallow: /health\n"
        "Disallow: /checkout/\n"
        "Disallow: /webhook/\n"
        "Disallow: /auth/\n"
        "Disallow: /login\n"
        "Disallow: /cadastro\n"
        "Disallow: /logout\n"
        "\n"
        f"Sitemap: {SITE_DOMAIN}/sitemap.xml\n"
    )
    return Response(content, mimetype='text/plain; charset=utf-8')


@app.route('/manifest.json')
def pwa_manifest():
    manifest_path = os.path.join(app.root_path, 'static', 'manifest.json')
    response = send_file(manifest_path, mimetype='application/manifest+json')
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


@app.route('/sw.js')
def pwa_service_worker():
    sw_path = os.path.join(app.root_path, 'static', 'sw.js')
    response = send_file(sw_path, mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response


@app.route('/llms.txt')
def llms_txt():
    content = (
        "# ValidAí — Plataforma Brasileira de Auditoria, Conciliação e Validação Inteligente de Dados\n\n"
        "> O ValidAí (https://validai.app.br) é a plataforma SaaS brasileira de referência para auditoria de planilhas, "
        "conciliação financeira, conferência fiscal de NF-e, auditoria de folha de pagamento de RH, higienização de cadastros "
        "(CPF/CNPJ) e comparação textual de contratos (PDF/Word). Fundado e arquitetado por Vinícius Alves.\n\n"
        "## Módulos e Ferramentas Oficiais (6 Validadores Especializados)\n\n"
        "1. **[Comparador e Validador de Planilhas Excel e CSV](https://validai.app.br/)**\n"
        "   - Compara duas bases (.xlsx, .xls, .csv) célula por célula ou audita uma base única.\n"
        "   - Suporta chaves compostas, união de múltiplas abas, tolerância financeira de centavos e normalização textual.\n"
        "   - Exporta relatório Excel (.xlsx) com células pintadas (verde/amarelo/vermelho) e autofiltro ativo.\n\n"
        "2. **[Auditoria de Folha de Pagamento e Benefícios de RH](https://validai.app.br/auditoria-rh)**\n"
        "   - Cruza folha anterior vs. folha atual ou base de ativos do RH contra faturas de planos de saúde, VR e benefícios.\n"
        "   - Identifica cobranças indevidas de desligados (fantasmas na fatura), variações salariais acima do limite e divergências de encargos (INSS/FGTS/IRRF).\n\n"
        "3. **[Conciliador de Extratos Bancários (.OFX) e Taxas de Cartão](https://validai.app.br/conciliador-taxas)**\n"
        "   - Concilia arquivos bancários .OFX e borderôs de adquirentes (Stone, Cielo, Rede, PagBank, Getnet, Mercado Pago) contra controles internos.\n"
        "   - Audita taxas MDR contratadas vs. cobradas efetivamente e aponta perdas financeiras por transação.\n\n"
        "4. **[Conciliador de Notas Fiscais Eletrônicas (XML NF-e vs. Planilha)](https://validai.app.br/validador-xml)**\n"
        "   - Extrai dados fiscais de múltiplos XMLs de NF-e (modelo 55/65, chaves de 44 dígitos, CNPJ, CFOP, NCM, ICMS, IPI, PIS, COFINS) em lote (.xml ou .zip).\n"
        "   - Cruza automaticamente contra o relatório do ERP ou SPED e permite consulta instantânea de CNPJ.\n\n"
        "5. **[Validador e Higienizador de Cadastros em Lote (CPF, CNPJ, CEP, Contatos)](https://validai.app.br/validador-cadastros)**\n"
        "   - Valida dígitos verificadores oficiais (Módulo 11) de CPF e CNPJ, padroniza telefones celulares para WhatsApp (E.164), limpa e-mails e formata CEPs.\n"
        "   - Gera base higienizada pronta para importação em ERP/CRM e laudo de registros inválidos.\n\n"
        "6. **[Comparador e Validador de Textos e Documentos (PDF, DOCX, TXT)](https://validai.app.br/validador-texto)**\n"
        "   - Compara duas versões de contratos, minutas jurídicas ou relatórios com visualização Side-by-Side (Rich Text) e Redline Unificado.\n"
        "   - Calcula índice de similaridade e gera laudo em PDF colorido com alterações destacadas.\n\n"
        "## Segurança, Privacidade (LGPD) e Arquitetura\n\n"
        "- **Conformidade LGPD (Lei nº 13.709/2018):** Processamento volátil em memória temporária com limpeza automática periódica e descarte imediato.\n"
        "- **Planos e Acesso:** Plano Standard gratuito para uso diário; Passes Plus (R$ 4,99) e Pro (R$ 9,99) com liberação imediata via PIX ou Cartão por 30 dias sem renovação surpresa.\n"
        "- **Documentação e Guias:**\n"
        "  - Guia Passo a Passo: https://validai.app.br/como-usar\n"
        "  - Planos e Preços: https://validai.app.br/planos\n"
        "  - Sobre o ValidAí e Fundador (Vinícius Alves): https://validai.app.br/sobre\n"
        "  - Política de Privacidade: https://validai.app.br/privacidade\n"
        "  - Termos de Uso: https://validai.app.br/termos\n"
    )
    response = Response(content, mimetype='text/plain; charset=utf-8')
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


@app.route('/ads.txt')
def ads_txt():
    response = send_from_directory(
        BASE_DIR,
        'ads.txt',
        mimetype='text/plain'
    )
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    response.headers['Cache-Control'] = 'public, max-age=86400'
    response.headers['X-Robots-Tag'] = 'all'
    return response


@app.route('/sitemap.xml')
def sitemap_xml():
    lastmod_date = "2026-10-24"
    urls = [
        ('/', '1.0', 'weekly'),
        ('/validador-texto', '0.9', 'weekly'),
        ('/validador-cadastros', '0.9', 'weekly'),
        ('/validador-xml', '0.9', 'weekly'),
        ('/conciliador-taxas', '0.8', 'weekly'),
        ('/auditoria-rh', '0.8', 'weekly'),
        ('/como-usar', '0.8', 'monthly'),
        ('/planos', '0.8', 'monthly'),
        ('/sobre', '0.6', 'monthly'),
        ('/privacidade', '0.4', 'monthly'),
        ('/termos', '0.4', 'monthly'),
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


@app.route('/api/excel-sheets', methods=['POST'])
@app.route('/inspecionar-arquivo', methods=['POST'])
@app.route('/api/sheets/inspect-file', methods=['POST'])
def inspect_spreadsheet_route():
    try:
        file = request.files.get('file') or request.files.get('file_a') or request.files.get('file_b')
        if not file:
            return jsonify({'error': 'Nenhum arquivo enviado.'}), 400
        filename = file.filename or 'arquivo.xlsx'
        info = comparator.inspect_spreadsheet_file(file, filename)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e), 'is_excel': False, 'sheets': [], 'default_sheet': None}), 500


@app.route('/api/upload-headers', methods=['POST'])
def upload_headers():
    cleanup_old_temp_files()
    try:
        file_a = request.files.get('file_a')
        file_b = request.files.get('file_b')

        if not file_a or not file_b:
            return jsonify({'error': 'Envie ambos os arquivos (Base Antiga e Base Nova).'}), 400

        header_line_a = request.form.get('header_line_a', 1)
        header_line_b = request.form.get('header_line_b', 1)
        sheets_a = request.form.get('sheets_a')
        sheets_b = request.form.get('sheets_b')

        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        filename_a = file_a.filename
        filename_b = file_b.filename

        path_a = os.path.join(session_folder, 'base_a_' + filename_a)
        path_b = os.path.join(session_folder, 'base_b_' + filename_b)

        file_a.save(path_a)
        file_b.save(path_b)

        info_a = comparator.inspect_spreadsheet_file(path_a, filename_a)
        info_b = comparator.inspect_spreadsheet_file(path_b, filename_b)
        sheets_info_a = info_a.get('sheets', [])
        sheets_info_b = info_b.get('sheets', [])

        # Garante que a aba padrão seja a primeira aba VISÍVEL do arquivo
        first_vis_a = next((s['name'] for s in sheets_info_a if s.get('visible') is not False), None)
        default_sheet_a = (sheets_a if sheets_a else None) or first_vis_a or info_a.get('default_sheet') or (sheets_info_a[0]['name'] if sheets_info_a else None)

        first_vis_b = next((s['name'] for s in sheets_info_b if s.get('visible') is not False), None)
        default_sheet_b = (sheets_b if sheets_b else None) or first_vis_b or info_b.get('default_sheet') or (sheets_info_b[0]['name'] if sheets_info_b else None)

        has_multiple_sheets = len(sheets_info_a) > 1 or len(sheets_info_b) > 1

        # Ler colunas dos arquivos com suporte a linha de cabeçalho e abas
        df_a = comparator.read_tabular_file(path_a, filename_a, header_line=header_line_a, sheet_names=default_sheet_a)
        df_b = comparator.read_tabular_file(path_b, filename_b, header_line=header_line_b, sheet_names=default_sheet_b)

        cols_a = list(df_a.columns)
        cols_b = list(df_b.columns)

        has_unnamed = any(str(c).upper().startswith('UNNAMED:') for c in cols_a + cols_b)

        mapping = comparator.suggest_column_mappings(cols_a, cols_b)

        # Sugestões de chaves primárias inteligentes com prioridade semântica e análise de cardinalidade
        suggested_keys = comparator.suggest_primary_keys(df_a, df_b, mapping, cols_a)

        SESSIONS[session_id] = {
            'path_a': path_a,
            'path_b': path_b,
            'filename_a': filename_a,
            'filename_b': filename_b,
            'header_line_a': header_line_a,
            'header_line_b': header_line_b,
            'sheets_a': default_sheet_a,
            'sheets_b': default_sheet_b,
            'sheets_info_a': sheets_info_a,
            'sheets_info_b': sheets_info_b,
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
            'has_unnamed': has_unnamed,
            'suggested_keys': suggested_keys,
            'column_mapping': mapping,
            'sheets_info_a': sheets_info_a,
            'sheets_info_b': sheets_info_b,
            'default_sheet_a': default_sheet_a,
            'default_sheet_b': default_sheet_b,
            'header_line_a': int(header_line_a) if str(header_line_a).isdigit() else 1,
            'header_line_b': int(header_line_b) if str(header_line_b).isdigit() else 1,
            'has_multiple_sheets': has_multiple_sheets
        })

    except HTTPException:
        raise
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
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

        suggested_keys = comparator.suggest_primary_keys(df_a, df_b, mapping, cols_a)

        SESSIONS[session_id] = {
            'is_sample': True,
            'path_a': path_a,
            'path_b': path_b,
            'filename_a': filename_a,
            'filename_b': filename_b,
            'cols_a': cols_a,
            'cols_b': cols_b,
            'sheets_a': 'Vendas_ERP',
            'sheets_b': 'Vendas_ERP',
            'header_line_a': 1,
            'header_line_b': 1
        }

        return jsonify({
            'session_id': session_id,
            'filename_a': filename_a,
            'filename_b': filename_b,
            'rows_a_count': len(df_a),
            'rows_b_count': len(df_b),
            'cols_a': cols_a,
            'cols_b': cols_b,
            'suggested_keys': suggested_keys,
            'column_mapping': mapping,
            'sheets_info_a': [{'name': 'Vendas_ERP', 'visible': True}],
            'sheets_info_b': [{'name': 'Vendas_ERP', 'visible': True}],
            'default_sheet_a': 'Vendas_ERP',
            'default_sheet_b': 'Vendas_ERP',
            'header_line_a': 1,
            'header_line_b': 1,
            'has_multiple_sheets': False
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao carregar exemplo de planilhas: {str(e)}'}), 500


@app.route('/api/change-sheet', methods=['POST'])
def change_sheet():
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        if not session_id or session_id not in SESSIONS:
            return jsonify({'error': 'Sessão não encontrada ou expirada. Recarregue os arquivos.'}), 404

        sess = SESSIONS[session_id]
        if sess.get('is_sample'):
            return jsonify({'error': 'A alteração de abas não se aplica a planilhas de exemplo fixas.'}), 400

        raw_a = data.get('sheets_a') if 'sheets_a' in data else data.get('sheet_a')
        raw_b = data.get('sheets_b') if 'sheets_b' in data else data.get('sheet_b')
        sheet_a = raw_a if raw_a else sess.get('sheets_a')
        sheet_b = raw_b if raw_b else sess.get('sheets_b')
        header_line_a = data.get('header_line_a', sess.get('header_line_a', 1))
        header_line_b = data.get('header_line_b', sess.get('header_line_b', 1))

        df_a = comparator.read_tabular_file(sess['path_a'], sess['filename_a'], header_line=header_line_a, sheet_names=sheet_a)
        df_b = comparator.read_tabular_file(sess['path_b'], sess['filename_b'], header_line=header_line_b, sheet_names=sheet_b)

        cols_a = list(df_a.columns)
        cols_b = list(df_b.columns)
        has_unnamed = any(str(c).upper().startswith('UNNAMED:') for c in cols_a + cols_b)

        mapping = comparator.suggest_column_mappings(cols_a, cols_b)
        suggested_keys = comparator.suggest_primary_keys(df_a, df_b, mapping, cols_a)

        # Atualiza a sessão
        sess['header_line_a'] = header_line_a
        sess['header_line_b'] = header_line_b
        sess['sheets_a'] = sheet_a
        sess['sheets_b'] = sheet_b
        sess['cols_a'] = cols_a
        sess['cols_b'] = cols_b
        sess['mapping'] = mapping
        sess['rows_a_count'] = len(df_a)
        sess['rows_b_count'] = len(df_b)

        return jsonify({
            'success': True,
            'rows_a_count': len(df_a),
            'rows_b_count': len(df_b),
            'cols_a': cols_a,
            'cols_b': cols_b,
            'has_unnamed': has_unnamed,
            'suggested_keys': suggested_keys,
            'column_mapping': mapping,
            'active_sheet_a': sheet_a,
            'active_sheet_b': sheet_b,
            'header_line_a': int(header_line_a) if str(header_line_a).isdigit() else 1,
            'header_line_b': int(header_line_b) if str(header_line_b).isdigit() else 1
        })
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Falha ao alternar aba/cabeçalho: {str(e)}'}), 500


@app.route('/favicon.ico')
def favicon():
    fav_dir = BASE_DIR if os.path.exists(os.path.join(BASE_DIR, 'favicon.ico')) else os.path.join(BASE_DIR, 'static')
    response = send_from_directory(
        fav_dir,
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response

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

        header_line_a = data.get('header_line_a', sess.get('header_line_a', 1))
        header_line_b = data.get('header_line_b', sess.get('header_line_b', 1))
        raw_sheets_a = data.get('sheets_a')
        raw_sheets_b = data.get('sheets_b')
        sheets_a = raw_sheets_a if raw_sheets_a else sess.get('sheets_a')
        sheets_b = raw_sheets_b if raw_sheets_b else sess.get('sheets_b')

        df_a = comparator.read_tabular_file(sess['path_a'], sess['filename_a'], header_line=header_line_a, sheet_names=sheets_a)
        df_b = comparator.read_tabular_file(sess['path_b'], sess['filename_b'], header_line=header_line_b, sheet_names=sheets_b)

        # Validação de planos, cotas e limites de volume (com suporte a Teaser / Degustação)
        is_sample = bool(sess.get('is_sample') or data.get('is_sample'))
        row_count = max(len(df_a), len(df_b))
        col_count = max(len(df_a.columns), len(df_b.columns))
        allowed, err_resp, status_code = check_validation_permission(
            tool_type='basic',
            row_count=row_count,
            col_count=col_count,
            is_sample=is_sample
        )
        is_teaser = False
        if not allowed:
            if row_count > 30000 or col_count > 100:
                del df_a, df_b
                gc.collect()
                return jsonify(err_resp), status_code
            is_teaser = True

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
            'filename': report_filename,
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }

        # Registra consumo de cota e coleta de lixo
        if not is_teaser:
            record_validation_usage(tool_type='basic', is_sample=is_sample)
        del df_a, df_b
        gc.collect()

        diff_preview = summary['sample_diff_records'][:3] if is_teaser else summary['sample_diff_records']
        only_in_a_preview = summary.get('sample_only_in_a', [])[:3] if is_teaser else summary.get('sample_only_in_a', [])
        only_in_b_preview = summary.get('sample_only_in_b', [])[:3] if is_teaser else summary.get('sample_only_in_b', [])
        total_issues = summary.get('total_diff_records', 0) + summary.get('rows_only_in_a', 0) + summary.get('rows_only_in_b', 0)
        total_hidden = max(0, total_issues - len(diff_preview)) if is_teaser else 0

        # Formata resposta com resumo e amostra de diferenças para tabela dinâmica
        return jsonify({
            'success': True,
            'report_id': report_id,
            'is_teaser': is_teaser,
            'teaser_info': err_resp if is_teaser else None,
            'total_hidden_divergences': total_hidden,
            'summary': summary,
            'has_differences': not summary['is_identical'],
            'diff_preview': diff_preview,
            'only_in_a_preview': only_in_a_preview,
            'only_in_b_preview': only_in_b_preview,
            'cols_display_a': summary.get('cols_display_a', []),
            'cols_display_b': summary.get('cols_display_b', []),
            'columns_with_differences': summary['columns_with_differences']
        })

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Erro na comparação: {str(e)}'}), 500


def check_report_download_allowed(rep):
    """Verifica se o download de um relatório gerado em modo Teaser está liberado."""
    if not rep or not rep.get('is_teaser'):
        return True, None, 200
    user_summary = get_user_summary_for_ui()
    current_plan = user_summary.get('plan', 'standard')
    plan_err = rep.get('plan_error') or {}
    req_plan = plan_err.get('required_plan', 'plus')
    if current_plan == 'pro' or (current_plan == 'plus' and req_plan == 'plus'):
        return True, None, 200
    err_payload = dict(plan_err) if plan_err else {
        'error': 'plan_limit',
        'limit_type': 'teaser_locked',
        'message': 'Desbloqueie o relatório completo e baixe a planilha pintada por apenas R$ 4,99 no PIX.',
        'required_plan': req_plan
    }
    err_payload['error'] = 'plan_limit'
    return False, err_payload, 403


@app.route('/api/download-report/<report_id>', methods=['GET'])
def download_report(report_id):
    if report_id not in REPORTS:
        return jsonify({'error': 'Relatório não encontrado.'}), 404

    rep = REPORTS[report_id]
    dl_ok, dl_err, dl_status = check_report_download_allowed(rep)
    if not dl_ok:
        return jsonify(dl_err), dl_status

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
    cleanup_old_temp_files()
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

        header_line = request.form.get('header_line', 1)
        sheets = request.form.get('sheets')

        df = comparator.read_tabular_file(filepath, filename, header_line=header_line, sheet_names=sheets)
        cols = list(df.columns)
        has_unnamed = any(str(c).upper().startswith('UNNAMED:') for c in cols)

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
            'header_line': header_line,
            'sheets': sheets,
            'cols': cols,
            'total_rows': len(df)
        }

        return jsonify({
            'session_id': session_id,
            'filename': filename,
            'total_rows': len(df),
            'total_cols': len(cols),
            'cols': cols,
            'has_unnamed': has_unnamed,
            'sample_data': sample_rows
        })

    except HTTPException:
        raise
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
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
        header_line = data.get('header_line', sess.get('header_line', 1))
        sheets = data.get('sheets', sess.get('sheets'))
        df = comparator.read_tabular_file(sess['path'], sess['filename'], header_line=header_line, sheet_names=sheets)

        is_sample = bool(sess.get('is_sample') or data.get('is_sample'))
        row_count = len(df)
        col_count = len(df.columns)
        allowed, err_resp, status_code = check_validation_permission(
            tool_type='basic',
            row_count=row_count,
            col_count=col_count,
            is_sample=is_sample
        )
        is_teaser = False
        if not allowed:
            if row_count > 30000 or col_count > 100:
                del df
                gc.collect()
                return jsonify(err_resp), status_code
            is_teaser = True

        summary, preview_rows, invalid_cells_by_row, cols = single_auditor.audit_single_dataset(
            df, rules, max_preview_rows=300
        )

        # Gera o relatório Excel estilizado ValidAí
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
            'filename': report_filename,
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }

        if not is_teaser:
            record_validation_usage(tool_type='basic', is_sample=is_sample)
        del df
        gc.collect()

        out_preview = preview_rows[:3] if is_teaser else preview_rows
        total_hidden = max(0, summary.get('invalid_rows', 0) - len(out_preview)) if is_teaser else 0

        return jsonify({
            'success': True,
            'report_id': report_id,
            'is_teaser': is_teaser,
            'teaser_info': err_resp if is_teaser else None,
            'total_hidden_divergences': total_hidden,
            'summary': summary,
            'preview_rows': out_preview,
            'cols': cols
        })

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
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

        # Validação de planos para textos/documentos (com suporte a Teaser)
        is_sample = bool(data.get('is_sample') if request.is_json else request.form.get('is_sample', 'false').lower() == 'true')
        lines_count = max(len(text_a.splitlines()), len(text_b.splitlines()))
        allowed, err_resp, status_code = check_validation_permission(
            tool_type='basic',
            row_count=lines_count,
            col_count=1,
            is_sample=is_sample
        )
        is_teaser = False
        if not allowed:
            if lines_count > 30000:
                gc.collect()
                return jsonify(err_resp), status_code
            is_teaser = True

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
            'mimetype': 'application/pdf',
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }

        if not is_teaser:
            record_validation_usage(tool_type='basic', is_sample=is_sample)
        gc.collect()

        out_diff_rows = result['diff_table_rows'][:3] if is_teaser else result['diff_table_rows']
        total_hidden = max(0, len(result['diff_table_rows']) - len(out_diff_rows)) if is_teaser else 0

        return jsonify({
            'success': True,
            'report_id': report_id,
            'is_teaser': is_teaser,
            'teaser_info': err_resp if is_teaser else None,
            'total_hidden_divergences': total_hidden,
            'summary': result['summary'],
            'side_by_side_blocks': result['side_by_side_blocks'][:3] if is_teaser else result['side_by_side_blocks'],
            'redline_blocks': result['redline_blocks'][:3] if is_teaser else result['redline_blocks'],
            'diff_table_rows': out_diff_rows,
            'stats_comparison': result['stats_comparison']
        })

    except HTTPException:
        raise
    except Exception as e:
        return jsonify({'error': f'Erro ao comparar documentos: {str(e)}'}), 500

@app.route('/api/text/download-pdf/<report_id>', methods=['GET'])
def download_text_pdf_report(report_id):
    if report_id not in REPORTS:
        return jsonify({'error': 'Relatório PDF não encontrado.'}), 404

    rep = REPORTS[report_id]
    dl_ok, dl_err, dl_status = check_report_download_allowed(rep)
    if not dl_ok:
        return jsonify(dl_err), dl_status

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
    cleanup_old_temp_files()
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

    except HTTPException:
        raise
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
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
            'is_sample': True,
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
        header_line = data.get('header_line', sess.get('header_line', 1))
        sheets = data.get('sheets', sess.get('sheets'))
        df = comparator.read_tabular_file(sess['path'], sess['filename'], header_line=header_line, sheet_names=sheets)

        is_sample = bool(sess.get('is_sample') or data.get('is_sample'))
        row_count = len(df)
        col_count = len(df.columns)
        allowed, err_resp, status_code = check_validation_permission(
            tool_type='special',
            row_count=row_count,
            col_count=col_count,
            is_sample=is_sample
        )
        is_teaser = False
        if not allowed:
            if row_count > 30000 or col_count > 100:
                del df
                gc.collect()
                return jsonify(err_resp), status_code
            is_teaser = True

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
            'filename': clean_filename,
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }
        REPORTS[f"cadastros_audit_{report_id}"] = {
            'path': audit_path,
            'filename': audit_filename,
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }

        if not is_teaser:
            record_validation_usage(tool_type='special', is_sample=is_sample)
        del df
        gc.collect()

        inv_docs = results['invalid_docs'][:3] if is_teaser else results['invalid_docs']
        dups = results['duplicates'][:3] if is_teaser else results['duplicates']
        susp = results['suspicious_contacts'][:3] if is_teaser else results['suspicious_contacts']
        prev_clean = results['preview_clean'][:3] if is_teaser else results['preview_clean']
        total_issues = len(results['invalid_docs']) + len(results['duplicates']) + len(results['suspicious_contacts'])
        total_hidden = max(0, total_issues - 3) if is_teaser else 0

        return jsonify({
            'success': True,
            'report_id': report_id,
            'is_teaser': is_teaser,
            'teaser_info': err_resp if is_teaser else None,
            'total_hidden_divergences': total_hidden,
            'summary': results['summary'],
            'invalid_docs': inv_docs,
            'duplicates': dups,
            'suspicious_contacts': susp,
            'preview_clean': prev_clean,
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
        dl_ok, dl_err, dl_status = check_report_download_allowed(REPORTS[key])
        if not dl_ok:
            return jsonify(dl_err), dl_status
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
        dl_ok, dl_err, dl_status = check_report_download_allowed(REPORTS[key])
        if not dl_ok:
            return jsonify(dl_err), dl_status
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
    cleanup_old_temp_files()
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

    except HTTPException:
        raise
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
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
            'is_sample': True,
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

        # Validação de planos para conciliação XML (Especial com suporte a Teaser)
        is_sample = bool(sess.get('is_sample') or data.get('is_sample'))
        row_count = max(len(df_sheet), len(invoices))
        col_count = len(df_sheet.columns)
        allowed, err_resp, status_code = check_validation_permission(
            tool_type='special',
            row_count=row_count,
            col_count=col_count,
            is_sample=is_sample
        )
        is_teaser = False
        if not allowed:
            if row_count > 30000 or col_count > 100:
                del df_sheet
                gc.collect()
                return jsonify(err_resp), status_code
            is_teaser = True

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
            'filename': audit_filename,
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }
        REPORTS[f"xml_mirror_{report_id}"] = {
            'path': mirror_path,
            'filename': mirror_filename,
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }

        if not is_teaser:
            record_validation_usage(tool_type='special', is_sample=is_sample)
        del df_sheet
        gc.collect()

        divs = res['divergences'][:3] if is_teaser else res['divergences']
        miss_excel = res['missing_in_excel'][:3] if is_teaser else res['missing_in_excel']
        miss_xml = res['missing_xml'][:3] if is_teaser else res['missing_xml']
        mirror_list = res['all_xml_mirror'][:3] if is_teaser else res['all_xml_mirror']
        total_issues = len(res['divergences']) + len(res['missing_in_excel']) + len(res['missing_xml'])
        total_hidden = max(0, total_issues - 3) if is_teaser else 0

        return jsonify({
            'success': True,
            'report_id': report_id,
            'is_teaser': is_teaser,
            'teaser_info': err_resp if is_teaser else None,
            'total_hidden_divergences': total_hidden,
            'summary': res['summary'],
            'divergences': divs,
            'missing_in_excel': miss_excel,
            'missing_xml': miss_xml,
            'all_xml_mirror': mirror_list
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
        dl_ok, dl_err, dl_status = check_report_download_allowed(REPORTS[key])
        if not dl_ok:
            return jsonify(dl_err), dl_status
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
        dl_ok, dl_err, dl_status = check_report_download_allowed(REPORTS[key])
        if not dl_ok:
            return jsonify(dl_err), dl_status
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
    cleanup_old_temp_files()
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

    except HTTPException:
        raise
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
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
            'is_sample': True,
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

        # Validação de planos para conciliação bancária OFX (Especial com suporte a Teaser)
        is_sample = bool(sess.get('is_sample') or data.get('is_sample'))
        row_count = max(len(df_sales), len(transactions))
        col_count = len(df_sales.columns)
        allowed, err_resp, status_code = check_validation_permission(
            tool_type='special',
            row_count=row_count,
            col_count=col_count,
            is_sample=is_sample
        )
        is_teaser = False
        if not allowed:
            if row_count > 30000 or col_count > 100:
                del df_sales
                gc.collect()
                return jsonify(err_resp), status_code
            is_teaser = True

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
            'filename': audit_filename,
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }
        REPORTS[f"ofx_mirror_{report_id}"] = {
            'path': mirror_path,
            'filename': mirror_filename,
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }

        sess['last_result'] = res
        sess['last_report_id'] = report_id

        if not is_teaser:
            record_validation_usage(tool_type='special', is_sample=is_sample)
        del df_sales
        gc.collect()

        out_items = res['items'][:3] if is_teaser else res['items']
        total_hidden = max(0, len(res['items']) - len(out_items)) if is_teaser else 0

        return jsonify({
            'success': True,
            'report_id': report_id,
            'is_teaser': is_teaser,
            'teaser_info': err_resp if is_teaser else None,
            'total_hidden_divergences': total_hidden,
            'kpis': res['kpis'],
            'items': out_items
        })

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao executar conciliação de taxas: {str(e)}'}), 500


@app.route('/api/ofx/download-audit/<report_id>', methods=['GET'])
def ofx_download_audit(report_id):
    key = f"ofx_audit_{report_id}"
    if key in REPORTS and os.path.exists(REPORTS[key]['path']):
        dl_ok, dl_err, dl_status = check_report_download_allowed(REPORTS[key])
        if not dl_ok:
            return jsonify(dl_err), dl_status
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
        dl_ok, dl_err, dl_status = check_report_download_allowed(REPORTS[key])
        if not dl_ok:
            return jsonify(dl_err), dl_status
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
    cleanup_old_temp_files()
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

    except HTTPException:
        raise
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
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
            'is_sample': True,
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

        # Validação de planos para auditoria de RH (Especial com suporte a Teaser)
        is_sample = bool(sess.get('is_sample') or data.get('is_sample'))
        row_count = max(len(df_ref), len(df_audit))
        col_count = max(len(df_ref.columns), len(df_audit.columns))
        allowed, err_resp, status_code = check_validation_permission(
            tool_type='special',
            row_count=row_count,
            col_count=col_count,
            is_sample=is_sample
        )
        is_teaser = False
        if not allowed:
            if row_count > 30000 or col_count > 100:
                del df_ref, df_audit
                gc.collect()
                return jsonify(err_resp), status_code
            is_teaser = True

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
            'filename': audit_filename,
            'is_teaser': is_teaser,
            'plan_error': err_resp if is_teaser else None
        }

        sess['last_result'] = res
        sess['last_report_id'] = report_id

        if not is_teaser:
            record_validation_usage(tool_type='special', is_sample=is_sample)
        del df_ref, df_audit
        gc.collect()

        out_div = res['divergences'][:3] if is_teaser else res['divergences']
        out_crit = res['critical_variations'][:3] if is_teaser else res['critical_variations']
        out_ex1 = res['exclusive_ref'][:3] if is_teaser else res['exclusive_ref']
        out_ex2 = res['exclusive_audit'][:3] if is_teaser else res['exclusive_audit']
        total_issues = len(res['divergences']) + len(res['exclusive_ref']) + len(res['exclusive_audit'])
        total_hidden = max(0, total_issues - 3) if is_teaser else 0

        return jsonify({
            'success': True,
            'report_id': report_id,
            'is_teaser': is_teaser,
            'teaser_info': err_resp if is_teaser else None,
            'total_hidden_divergences': total_hidden,
            'kpis': res['kpis'],
            'financial_summary': res['financial_summary'],
            'divergences': out_div,
            'critical_variations': out_crit,
            'exclusive_ref': out_ex1,
            'exclusive_audit': out_ex2
        })

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao executar auditoria de RH: {str(e)}'}), 500


@app.route('/api/rh/download-report/<report_id>', methods=['GET'])
def rh_download_report(report_id):
    key = f"rh_audit_{report_id}"
    if key in REPORTS and os.path.exists(REPORTS[key]['path']):
        dl_ok, dl_err, dl_status = check_report_download_allowed(REPORTS[key])
        if not dl_ok:
            return jsonify(dl_err), dl_status
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


