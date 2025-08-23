from app.models import User, Consent, Session, UserRole, RoleEnum
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
import re

VALID_CURRENCIES = {"CLP": 0, "USD": 2, "EUR": 2}
VALID_TIMEZONES = ["America/Santiago", "UTC", "America/New_York"]

class CommandRouter:
    def __init__(self, db: DBSession):
        self.db = db

    def handle_command(self, user: User, session: Session, message: str):
        msg = message.strip().lower()
        if msg == "help":
            self.send_message(user.phone_e164, self.help_text())
        elif msg == "profile":
            self.send_message(user.phone_e164, self.profile_text(user))
        elif msg.startswith("set name "):
            user.display_name = message[9:].strip()
            self.db.commit()
            self.send_message(user.phone_e164, f"Nombre actualizado: {user.display_name}")
        elif msg.startswith("set currency "):
            cur = message[13:].strip().upper()
            if cur in VALID_CURRENCIES:
                user.currency = cur
                self.db.commit()
                self.send_message(user.phone_e164, f"Moneda actualizada: {cur}")
            else:
                self.send_message(user.phone_e164, f"Moneda inválida. Ejemplo: CLP, USD.")
        elif msg.startswith("set timezone "):
            tz = message[13:].strip()
            if tz in VALID_TIMEZONES:
                user.timezone = tz
                self.db.commit()
                self.send_message(user.phone_e164, f"Zona horaria actualizada: {tz}")
            else:
                user.timezone = "America/Santiago"
                self.db.commit()
                self.send_message(user.phone_e164, f"Zona horaria inválida. Usando America/Santiago.")
        elif msg == "erase me":
            # Mark for deletion, send confirmation
            from app.privacy_manager import PrivacyManager
            PrivacyManager(self.db).schedule_deletion(user)
            self.send_message(user.phone_e164, "Tu cuenta será eliminada en 48h. Escribe 'cancel erase' para cancelar.")
        elif msg == "export me":
            # Generate CSV, send signed URL
            from app.privacy_manager import PrivacyManager
            url = PrivacyManager(self.db).export_user(user)
            self.send_message(user.phone_e164, f"Descarga tus datos: {url}")
        elif msg == "stop":
            user.is_active = False
            self.db.commit()
            self.send_message(user.phone_e164, "Perfil desactivado. Escribe 'start' para reactivar.")
        elif msg == "start":
            user.is_active = True
            self.db.commit()
            self.send_message(user.phone_e164, "Perfil reactivado.")
        # Admin commands
        elif msg.startswith("block "):
            # Only if user is admin
            if self.is_admin(user):
                phone = message.split(" ", 1)[1].strip()
                target = self.db.query(User).filter_by(phone_e164=phone).first()
                if target:
                    target.is_blocked = True
                    self.db.commit()
                    self.send_message(user.phone_e164, f"Usuario {phone} bloqueado.")
                else:
                    self.send_message(user.phone_e164, "Usuario no encontrado.")
            else:
                self.send_message(user.phone_e164, "Solo administradores pueden bloquear.")
        elif msg.startswith("unblock "):
            if self.is_admin(user):
                phone = message.split(" ", 1)[1].strip()
                target = self.db.query(User).filter_by(phone_e164=phone).first()
                if target:
                    target.is_blocked = False
                    self.db.commit()
                    self.send_message(user.phone_e164, f"Usuario {phone} desbloqueado.")
                else:
                    self.send_message(user.phone_e164, "Usuario no encontrado.")
            else:
                self.send_message(user.phone_e164, "Solo administradores pueden desbloquear.")
        elif msg == "stats users":
            if self.is_admin(user):
                active = self.db.query(User).filter_by(is_active=True).count()
                blocked = self.db.query(User).filter_by(is_blocked=True).count()
                self.send_message(user.phone_e164, f"Activos: {active}, Bloqueados: {blocked}")
            else:
                self.send_message(user.phone_e164, "Solo administradores pueden ver estadísticas.")
        else:
            self.send_message(user.phone_e164, "Comando no reconocido. Escribe 'help'.")

    def help_text(self):
        return "Comandos: profile, set name <nombre>, set currency <ISO>, set timezone <IANA>, erase me, export me, stop, start."
    def profile_text(self, user: User):
        return f"Nombre: {user.display_name or 'Sin nombre'}\nMoneda: {user.currency}\nZona horaria: {user.timezone}"
    def send_message(self, phone_e164: str, text: str):
        from app.wa_sender import WhatsAppSender
        WhatsAppSender.send_message(phone_e164, text)

    def is_admin(self, user: User):
        role = self.db.query(UserRole).filter_by(user_id=user.user_id).first()
        return role and role.role == RoleEnum.admin
