import os
import json
import logging
import mercadopago

logger = logging.getLogger(__name__)

SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'https://validai.app.br').rstrip('/')

class MercadoPagoService:
    _sdk = None

    @classmethod
    def get_sdk(cls):
        if cls._sdk is None:
            token = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '').strip()
            if not token:
                logger.warning("MERCADOPAGO_ACCESS_TOKEN não configurado!")
                return None
            try:
                cls._sdk = mercadopago.SDK(token)
            except Exception as e:
                logger.error(f"Erro ao inicializar SDK Mercado Pago: {e}")
                return None
        return cls._sdk

    @classmethod
    def create_checkout_preference(cls, user_id: str, user_email: str, plan_name: str):
        sdk = cls.get_sdk()
        if not sdk:
            return None, "Serviço de pagamentos indisponível no momento."

        plan_key = plan_name.strip().lower()
        if plan_key == 'plus':
            title = "ValidAí - Plano Plus (30 dias)"
            price = 4.99
        elif plan_key == 'pro':
            title = "ValidAí - Plano Pro (30 dias)"
            price = 9.99
        else:
            return None, f"Plano desconhecido: {plan_name}"

        # Monta referência externa para o Webhook identificar o usuário e o plano
        ext_ref = json.dumps({
            'user_id': str(user_id),
            'email': str(user_email),
            'plan': plan_key
        })

        base_url = os.environ.get('SITE_DOMAIN', 'https://validai.app.br').rstrip('/')

        preference_data = {
            "items": [
                {
                    "title": title,
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": float(price),
                    "description": f"Assinatura mensal de 30 dias do {title}"
                }
            ],
            "payer": {
                "email": user_email
            },
            "back_urls": {
                "success": f"{base_url}/?pagamento=sucesso&plano={plan_key}",
                "pending": f"{base_url}/?pagamento=pendente&plano={plan_key}",
                "failure": f"{base_url}/?pagamento=falha&plano={plan_key}"
            },
            "auto_return": "approved",
            "external_reference": ext_ref,
            "notification_url": f"{base_url}/webhook/mercadopago",
            "statement_descriptor": "VALIDAI APP"
        }

        try:
            preference_response = sdk.preference().create(preference_data)
            pref = preference_response.get("response", {})
            
            # Garante o redirecionamento para a URL oficial de produção (init_point)
            init_url = pref.get("init_point")
            if not init_url:
                init_url = pref.get("sandbox_init_point")

            if init_url:
                return init_url, None
            else:
                logger.error(f"Resposta inválida do Mercado Pago: {preference_response}")
                return None, "Não foi possível gerar o link de pagamento."

        except Exception as e:
            logger.error(f"Erro ao criar preferência no Mercado Pago: {e}")
            return None, str(e)

    @classmethod
    def get_payment_details(cls, payment_id: str):
        sdk = cls.get_sdk()
        if not sdk:
            return None
        try:
            payment_info = sdk.payment().get(str(payment_id))
            return payment_info.get("response")
        except Exception as e:
            logger.error(f"Erro ao consultar pagamento {payment_id}: {e}")
            return None

    @classmethod
    def create_plan_preference(cls, plan_name: str, user_email: str, user_id: str = None):
        """Criação conveniente de preferência de planos."""
        return cls.create_checkout_preference(user_id=str(user_id or ''), user_email=str(user_email or ''), plan_name=plan_name)

