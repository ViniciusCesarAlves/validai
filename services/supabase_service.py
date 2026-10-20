import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class SupabaseService:
    _client: Client = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._client is None:
            url = os.environ.get('SUPABASE_URL', '').strip()
            key = os.environ.get('SUPABASE_KEY', '').strip()
            if not url or not key:
                logger.warning("SUPABASE_URL ou SUPABASE_KEY não configurados!")
                return None
            try:
                cls._client = create_client(url, key)
            except Exception as e:
                logger.error(f"Erro ao inicializar cliente Supabase: {e}")
                return None
        return cls._client

    @classmethod
    def get_user_by_email(cls, email: str):
        if not email:
            return None
        client = cls.get_client()
        if not client:
            return None
        try:
            res = client.table('users_profiles').select('*').eq('email', email.strip().lower()).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar usuário por email ({email}): {e}")
            return None

    @classmethod
    def get_user_by_id(cls, user_id: str):
        if not user_id:
            return None
        user_id_str = str(user_id)
        if user_id_str.startswith('mock_pro_'):
            return {
                'id': user_id_str,
                'email': 'pro@validai.app.br',
                'plan': 'pro',
                'daily_basic_count': 0,
                'daily_special_count': 0,
                'plan_expires_at': '2099-01-01T00:00:00+00:00'
            }
        if user_id_str.startswith('mock_plus_'):
            return {
                'id': user_id_str,
                'email': 'plus@validai.app.br',
                'plan': 'plus',
                'daily_basic_count': 0,
                'daily_special_count': 0,
                'plan_expires_at': '2099-01-01T00:00:00+00:00'
            }
        if user_id_str.startswith('mock_std_'):
            return {
                'id': user_id_str,
                'email': 'std@validai.app.br',
                'plan': 'standard',
                'daily_basic_count': 0,
                'daily_special_count': 0,
                'plan_expires_at': None
            }

        client = cls.get_client()
        if not client:
            return None
        try:
            res = client.table('users_profiles').select('*').eq('id', str(user_id)).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar usuário por ID ({user_id}): {e}")
            return None

    @classmethod
    def create_user(cls, email: str, password: str, plan: str = 'standard'):
        client = cls.get_client()
        if not client:
            return None, "Serviço de banco de dados indisponível no momento."

        email_clean = email.strip().lower()
        if '@' not in email_clean or '.' not in email_clean:
            return None, "E-mail inválido."

        if not password or len(password) < 6:
            return None, "A senha deve conter no mínimo 6 caracteres."

        existing = cls.get_user_by_email(email_clean)
        if existing:
            return None, "Já existe uma conta cadastrada com este e-mail."

        hashed_pwd = generate_password_hash(password)
        today_str = str(datetime.now(timezone.utc).date())
        new_id = str(uuid.uuid4())

        user_data = {
            'id': new_id,
            'email': email_clean,
            'password_hash': hashed_pwd,
            'plan': plan.lower(),
            'daily_basic_count': 0,
            'daily_special_count': 0,
            'last_usage_date': today_str
        }

        try:
            res = client.table('users_profiles').insert(user_data).execute()
            if res.data and len(res.data) > 0:
                created = res.data[0]
                created.pop('password_hash', None)
                return created, None
            return None, "Não foi possível criar o usuário."
        except Exception as e:
            logger.error(f"Erro ao criar usuário: {e}")
            return None, f"Erro interno ao criar conta: {str(e)}"

    @classmethod
    def get_or_create_oauth_user(cls, user_id: str, email: str, plan: str = 'standard'):
        if not email:
            return None, "E-mail inválido."
        email_clean = email.strip().lower()

        existing = cls.get_user_by_email(email_clean)
        if existing:
            return existing, None

        client = cls.get_client()
        today_str = str(datetime.now(timezone.utc).date())
        # Garante que o ID gravado no banco seja um UUID vlido
        new_id = None
        if user_id:
            try:
                new_id = str(uuid.UUID(str(user_id)))
            except Exception:
                new_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(user_id)))
        else:
            new_id = str(uuid.uuid4())

        user_data = {
            'id': new_id,
            'email': email_clean,
            'password_hash': 'oauth:google',
            'plan': plan.lower(),
            'daily_basic_count': 0,
            'daily_special_count': 0,
            'last_usage_date': today_str
        }

        if not client:
            return user_data, None

        try:
            res = client.table('users_profiles').insert(user_data).execute()
            if res.data and len(res.data) > 0:
                created = res.data[0]
                created.pop('password_hash', None)
                return created, None
            return user_data, None
        except Exception as e:
            logger.error(f"Erro ao inserir perfil OAuth ({email_clean}): {e}")
            existing_retry = cls.get_user_by_email(email_clean)
            if existing_retry:
                return existing_retry, None
            return None, str(e)

    @classmethod
    def reset_password(cls, email: str, redirect_url: str = None):
        if not email:
            return False, "Informe o e-mail."
        email_clean = email.strip().lower()
        client = cls.get_client()
        if not client:
            return True, "Se o e-mail estiver cadastrado, as instruções serão enviadas."

        try:
            opts = {'redirect_to': redirect_url} if redirect_url else {}
            client.auth.reset_password_for_email(email_clean, opts)
            return True, "Instruções de redefinição de senha enviadas para o seu e-mail."
        except Exception as e:
            logger.warning(f"Aviso ao enviar redefinição de senha para {email_clean}: {e}")
            return True, "Se o e-mail estiver cadastrado, as instruções serão enviadas."

    @classmethod
    def authenticate_user(cls, email: str, password: str):
        if not email or not password:
            return None, "Informe e-mail e senha."

        user = cls.get_user_by_email(email)
        if not user:
            return None, "E-mail ou senha incorretos."

        stored_hash = user.get('password_hash')
        if not stored_hash or not check_password_hash(stored_hash, password):
            return None, "E-mail ou senha incorretos."

        user_clean = dict(user)
        user_clean.pop('password_hash', None)
        return user_clean, None

    @classmethod
    def get_or_sync_user_usage(cls, user_id: str):
        user = cls.get_user_by_id(user_id)
        if not user:
            return None
        if str(user_id).startswith('mock_'):
            return dict(user)

        client = cls.get_client()
        today_str = str(datetime.now(timezone.utc).date())
        needs_update = False
        updates = {}

        # 1. Verifica expiração do plano (Plus / Pro)
        current_plan = (user.get('plan') or 'standard').lower()
        expires_at_str = user.get('plan_expires_at')
        if current_plan in ('plus', 'pro') and expires_at_str:
            try:
                # Tratamento robusto de timezone ISO format
                exp_date = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                if exp_date < datetime.now(timezone.utc):
                    # Plano expirou -> retorna para standard
                    current_plan = 'standard'
                    updates['plan'] = 'standard'
                    updates['plan_expires_at'] = None
                    needs_update = True
            except Exception as exp_err:
                logger.warning(f"Erro ao analisar data de expiração ({expires_at_str}): {exp_err}")

        # 2. Reseta cotas diárias se a data do último uso for anterior a hoje
        last_date = user.get('last_usage_date')
        if last_date != today_str:
            updates['daily_basic_count'] = 0
            updates['daily_special_count'] = 0
            updates['last_usage_date'] = today_str
            needs_update = True
            user['daily_basic_count'] = 0
            user['daily_special_count'] = 0
            user['last_usage_date'] = today_str

        if needs_update and client:
            try:
                client.table('users_profiles').update(updates).eq('id', str(user_id)).execute()
                user.update(updates)
            except Exception as e:
                logger.error(f"Erro ao sincronizar uso do usuário ({user_id}): {e}")

        user['plan'] = current_plan
        user.pop('password_hash', None)
        return user

    @classmethod
    def increment_user_usage(cls, user_id: str, usage_type: str = 'basic'):
        if not user_id or str(user_id).startswith('mock_'):
            return
        client = cls.get_client()
        if not client:
            return

        today_str = str(datetime.now(timezone.utc).date())
        user = cls.get_or_sync_user_usage(user_id)
        if not user:
            return

        col = 'daily_special_count' if usage_type == 'special' else 'daily_basic_count'
        new_count = int(user.get(col, 0) or 0) + 1

        try:
            client.table('users_profiles').update({
                col: new_count,
                'last_usage_date': today_str
            }).eq('id', str(user_id)).execute()
        except Exception as e:
            logger.error(f"Erro ao incrementar cota ({col}) para usuário {user_id}: {e}")

    @classmethod
    def update_user_plan(cls, user_id_or_email: str, plan: str, days: int = 30, payment_id: str = None):
        client = cls.get_client()
        if not client or not user_id_or_email:
            return False, "Cliente de banco indisponível."

        plan_clean = plan.strip().lower()
        if plan_clean not in ('standard', 'plus', 'pro'):
            return False, f"Plano inválido: {plan}"

        # Localiza por ID ou email
        user = cls.get_user_by_id(user_id_or_email) or cls.get_user_by_email(user_id_or_email)
        if not user:
            return False, f"Usuário não encontrado: {user_id_or_email}"

        expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        updates = {
            'plan': plan_clean,
            'plan_expires_at': expires_at.isoformat() if plan_clean != 'standard' else None
        }
        if payment_id:
            updates['mp_payment_id'] = str(payment_id)

        try:
            res = client.table('users_profiles').update(updates).eq('id', user['id']).execute()
            logger.info(f"Plano atualizado com sucesso para {user['email']}: {plan_clean} (expira em {expires_at})")
            return True, None
        except Exception as e:
            logger.error(f"Erro ao atualizar plano do usuário ({user_id_or_email}): {e}")
            return False, str(e)
