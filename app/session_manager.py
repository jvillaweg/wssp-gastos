from app.models import User, Consent, Session, UserRole, RoleEnum
from sqlalchemy.orm import Session as DBSession
from datetime import datetime

ONBOARDING_GREETING = "Soy tu registro de gastos por WhatsApp. ¿Aceptas que guarde tus mensajes para calcular resúmenes? Responde sí para continuar."
ONBOARDING_DECLINE = "No puedo continuar sin tu consentimiento. Si cambias de opinión, vuelve a escribir cualquier mensaje."
ONBOARDING_NAME_PROMPT = "Nombre para tus reportes? (o escribe omitir)"
ONBOARDING_TZ_PROMPT = "Zona horaria (ej: America/Santiago) o escribe omitir."
ONBOARDING_CUR_PROMPT = "Moneda (ej: CLP, USD) o escribe omitir."
ONBOARDING_TUTORIAL = "Ejemplo: 'gasto 3500 supermercado', 'set presupuesto 50000', 'export me'. Escribe 'help' para ver comandos."

class SessionManager:
    def __init__(self, db: DBSession):
        self.db = db

    def start_onboarding(self, user: User):
        # Send greeting/consent
        self.send_message(user.phone_e164, ONBOARDING_GREETING)
        self.set_session_state(user, "ONBOARDING")

    def handle_onboarding(self, user: User, session: Session, message: str):
        if not self.has_consent(user):
            if message.strip().lower() == "sí":
                self.grant_consent(user)
                self.send_message(user.phone_e164, ONBOARDING_NAME_PROMPT)
                session.state = "ONBOARDING_NAME"
            else:
                self.send_message(user.phone_e164, ONBOARDING_DECLINE)
                user.is_active = False
        elif session.state == "ONBOARDING_NAME":
            # Save name or skip
            if message.strip().lower() != "omitir":
                user.display_name = message.strip()
            self.send_message(user.phone_e164, ONBOARDING_TZ_PROMPT)
            session.state = "ONBOARDING_TZ"
        elif session.state == "ONBOARDING_TZ":
            # Validate/set timezone or skip
            if message.strip().lower() != "omitir":
                user.timezone = message.strip()
            self.send_message(user.phone_e164, ONBOARDING_CUR_PROMPT)
            session.state = "ONBOARDING_CUR"
        elif session.state == "ONBOARDING_CUR":
            # Validate/set currency or skip
            if message.strip().lower() != "omitir":
                user.currency = message.strip().upper()
            self.send_message(user.phone_e164, ONBOARDING_TUTORIAL)
            session.state = "ACTIVE"
            user.is_active = True
        self.db.commit()

    def has_consent(self, user: User):
        consent = self.db.query(Consent).filter_by(user_id=user.user_id, type='data_processing', revoked_at=None).first()
        return bool(consent)

    def grant_consent(self, user: User):
        consent = Consent(user_id=user.user_id, type='data_processing', granted_at=datetime.utcnow())
        self.db.add(consent)
        self.db.commit()

    def set_session_state(self, user: User, state: str):
        session = self.db.query(Session).filter_by(user_id=user.user_id).first()
        if not session:
            session = Session(user_id=user.user_id, state=state, started_at=datetime.utcnow(), updated_at=datetime.utcnow())
            self.db.add(session)
        else:
            session.state = state
            session.updated_at = datetime.utcnow()
        self.db.commit()

    def send_message(self, phone_e164: str, text: str):
        from app.wa_sender import WhatsAppSender
        WhatsAppSender.send_message(phone_e164, text)
