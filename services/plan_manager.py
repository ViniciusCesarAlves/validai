import os
import logging
from datetime import datetime, timezone
from flask import session, request
from services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)

PLANS = {
    'standard': {
        'id': 'standard',
        'name': 'Standard',
        'price': 0.0,
        'price_display': 'Grátis',
        'daily_basic_limit': 3,
        'daily_special_limit': 0,
        'max_rows': 500,
        'max_cols': 20,
        'show_ads': True,
        'badge_label': 'Standard',
        'features': [
            '3 validações básicas de planilhas/texto por dia',
            'Arquivos com até 500 linhas e 20 colunas',
            'Relatórios com células divergentes pintadas',
            'Amostras e exemplos liberados em todos os validadores'
        ]
    },
    'plus': {
        'id': 'plus',
        'name': 'Plus',
        'price': 4.99,
        'price_display': 'R$ 4,99 / mês',
        'daily_basic_limit': None,  # Ilimitado
        'daily_special_limit': 1,   # 1 validação real por dia
        'max_rows': 5000,
        'max_cols': 30,
        'show_ads': False,
        'badge_label': 'Plus',
        'features': [
            'Validações básicas de planilhas e texto ILIMITADAS',
            '1 validação de Cadastros/XML/OFX/RH por dia',
            'Arquivos com até 5.000 linhas e 30 colunas',
            '100% Livre de anúncios publicitários',
            'Suporte prioritário por e-mail'
        ]
    },
    'pro': {
        'id': 'pro',
        'name': 'Pro',
        'price': 9.99,
        'price_display': 'R$ 9,99 / mês',
        'daily_basic_limit': None,  # Ilimitado
        'daily_special_limit': None, # Ilimitado
        'max_rows': 30000,           # Trava de segurança do servidor
        'max_cols': None,            # Sem limite de colunas
        'show_ads': False,
        'badge_label': 'Pro',
        'features': [
            'TODAS as ferramentas 100% ILIMITADAS',
            'Higienizador, XML, Conciliador OFX e Auditoria RH sem travas',
            'Grandes arquivos até 30.000 linhas',
            '100% Livre de anúncios publicitários',
            'Exportação e relatórios avançados em 5 abas'
        ]
    }
}

# Cache em memória para visitantes anônimos (chave: "IP_YYYY-MM-DD")
_ANONYMOUS_CACHE = {}

def get_client_ip() -> str:
    """Extrai o IP real do cliente considerando proxies e Cloudflare."""
    try:
        cf_ip = request.headers.get('CF-Connecting-IP')
        if cf_ip:
            return cf_ip.strip()
        xf_ip = request.headers.get('X-Forwarded-For')
        if xf_ip:
            return xf_ip.split(',')[0].strip()
        return (request.remote_addr or '127.0.0.1').strip()
    except Exception:
        return '127.0.0.1'

def _cleanup_anonymous_cache(current_today: str):
    """Limpa chaves antigas do cache em memória para proteger a RAM."""
    keys_to_delete = [k for k in _ANONYMOUS_CACHE if not k.endswith(f"_{current_today}")]
    for k in keys_to_delete:
        _ANONYMOUS_CACHE.pop(k, None)

def get_anonymous_usage() -> dict:
    """Obtém contagem combinada de IP e cookie de sessão para visitantes anônimos."""
    today_str = str(datetime.now(timezone.utc).date())
    _cleanup_anonymous_cache(today_str)
    
    ip = get_client_ip()
    cache_key = f"{ip}_{today_str}"
    mem_usage = _ANONYMOUS_CACHE.get(cache_key, {'basic': 0, 'special': 0})

    # Consulta também a session cookie
    sess_usage = session.get('anon_usage', {})
    if sess_usage.get('date') != today_str:
        sess_usage = {'date': today_str, 'basic': 0, 'special': 0}
        session['anon_usage'] = sess_usage

    basic_cnt = max(int(mem_usage.get('basic', 0)), int(sess_usage.get('basic', 0)))
    special_cnt = max(int(mem_usage.get('special', 0)), int(sess_usage.get('special', 0)))

    return {
        'basic': basic_cnt,
        'special': special_cnt,
        'date': today_str
    }

def get_current_user_and_usage():
    """
    Retorna (user, plan_id, plan_config, current_usage, is_logged_in)
    current_usage: {'basic': int, 'special': int}
    """
    user_id = session.get('user_id')
    if user_id:
        user = SupabaseService.get_or_sync_user_usage(user_id)
        if user:
            plan_id = (user.get('plan') or 'standard').lower()
            if plan_id not in PLANS:
                plan_id = 'standard'
            plan_config = PLANS[plan_id]
            usage = {
                'basic': int(user.get('daily_basic_count') or 0),
                'special': int(user.get('daily_special_count') or 0)
            }
            return user, plan_id, plan_config, usage, True
        else:
            # Sessão com user_id inválido ou deletado
            session.pop('user_id', None)
            session.pop('user_email', None)

    # Visitante anônimo
    anon_usage = get_anonymous_usage()
    return None, 'standard', PLANS['standard'], anon_usage, False

def check_validation_permission(tool_type: str = 'basic', rows: int = None, cols: int = None, is_sample: bool = False, row_count: int = None, col_count: int = None):
    """
    Valida permissões de plano para uma execução.
    Retorna (allowed: bool, error_data: dict, http_status: int)
    """
    if rows is None and row_count is not None:
        rows = row_count
    if cols is None and col_count is not None:
        cols = col_count

    if is_sample:
        return True, None, 200

    user, plan_id, plan_config, usage, is_logged_in = get_current_user_and_usage()

    # 1. Checagem de Limite de Linhas
    if rows is not None and plan_config.get('max_rows') is not None:
        max_r = plan_config['max_rows']
        if rows > max_r:
            req_plan = 'plus' if rows <= 5000 else 'pro'
            return False, {
                'error': 'plan_limit',
                'limit_type': 'rows',
                'message': f"Seu arquivo possui {rows} linhas, excedendo o limite de {max_r} linhas do plano {plan_config['name']}.",
                'current_plan': plan_id,
                'required_plan': req_plan,
                'current_val': rows,
                'limit_val': max_r
            }, 403

    # 2. Checagem de Limite de Colunas
    if cols is not None and plan_config.get('max_cols') is not None:
        max_c = plan_config['max_cols']
        if cols > max_c:
            req_plan = 'plus' if cols <= 30 else 'pro'
            return False, {
                'error': 'plan_limit',
                'limit_type': 'columns',
                'message': f"Seu arquivo possui {cols} colunas, excedendo o limite de {max_c} colunas do plano {plan_config['name']}.",
                'current_plan': plan_id,
                'required_plan': req_plan,
                'current_val': cols,
                'limit_val': max_c
            }, 403

    # 3. Checagem de Cota Diária por Tipo de Ferramenta
    if tool_type == 'special':
        # Validadores Especiais (Cadastros, XML, OFX, RH)
        if plan_id == 'standard':
            return False, {
                'error': 'plan_limit',
                'limit_type': 'special_locked',
                'message': "Este validador avançado está disponível a partir do plano Plus (R$ 4,99/mês). No plano Standard, você pode usar o botão 'Testar Exemplo' para ver o funcionamento completo gratuitamente.",
                'current_plan': plan_id,
                'required_plan': 'plus'
            }, 403
        elif plan_id == 'plus':
            if usage['special'] >= 1:
                return False, {
                    'error': 'plan_limit',
                    'limit_type': 'daily_quota',
                    'message': "Você atingiu sua cota de 1 validação especial diária do plano Plus. Faça upgrade para o plano Pro para ter validações especiais ilimitadas.",
                    'current_plan': plan_id,
                    'required_plan': 'pro'
                }, 403

    elif tool_type == 'basic':
        # Validadores Básicos (Planilhas e Textos)
        if plan_id == 'standard':
            if usage['basic'] >= 3:
                return False, {
                    'error': 'plan_limit',
                    'limit_type': 'daily_quota',
                    'message': "Você atingiu o limite de 3 validações gratuitas hoje. Assine o plano Plus (apenas R$ 4,99/mês) para validações ilimitadas de planilhas e textos.",
                    'current_plan': plan_id,
                    'required_plan': 'plus'
                }, 403

    return True, None, 200

def record_validation_usage(tool_type: str = 'basic', is_sample: bool = False):
    """Incrementa a cota consumida após processamento bem-sucedido."""
    if is_sample:
        return

    user_id = session.get('user_id')
    today_str = str(datetime.now(timezone.utc).date())

    if user_id:
        SupabaseService.increment_user_usage(user_id, tool_type)
    else:
        ip = get_client_ip()
        cache_key = f"{ip}_{today_str}"
        entry = _ANONYMOUS_CACHE.get(cache_key, {'basic': 0, 'special': 0})
        key_name = 'special' if tool_type == 'special' else 'basic'
        entry[key_name] = int(entry.get(key_name, 0)) + 1
        _ANONYMOUS_CACHE[cache_key] = entry

        sess_usage = session.get('anon_usage', {'date': today_str, 'basic': 0, 'special': 0})
        if sess_usage.get('date') != today_str:
            sess_usage = {'date': today_str, 'basic': 0, 'special': 0}
        sess_usage[key_name] = int(sess_usage.get(key_name, 0)) + 1
        session['anon_usage'] = sess_usage

def get_user_summary_for_ui() -> dict:
    """Retorna dados consolidados para exibição no Header e Navbar."""
    user, plan_id, plan_config, usage, is_logged_in = get_current_user_and_usage()

    # Formata texto do badge da navbar
    if plan_id == 'standard':
        used = usage['basic']
        badge_text = f"Standard • {used}/3 hoje"
    elif plan_id == 'plus':
        spec_used = usage['special']
        badge_text = f"Plus • Básicos ∞ • Esp. {spec_used}/1"
    else:
        badge_text = "Pro • Ilimitado"

    return {
        'is_logged_in': is_logged_in,
        'user_id': user['id'] if user else None,
        'email': user['email'] if user else None,
        'plan': plan_id,
        'plan_name': plan_config['name'],
        'badge_text': badge_text,
        'daily_basic': usage['basic'],
        'daily_special': usage['special'],
        'basic_limit': plan_config['daily_basic_limit'],
        'special_limit': plan_config['daily_special_limit'],
        'show_ads': plan_config['show_ads'],
        'plans_catalog': PLANS
    }
