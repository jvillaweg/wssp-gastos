import re
import datetime
from datetime import timedelta
from typing import List, Optional, Tuple
from app.models import Category, Expense, Tag, User
from app.core.tag_manager import TagManager
from app.services.whatsapp_service import WhatsAppService
from app.webhooks.models import Interactive


class ExpenseManager:
    """Handles expense-related operations and business logic."""
    
    def __init__(self, db, user: User):
        self.db = db
        self.user = user
        self.tag_manager = TagManager(db, user)
    
    def list_categories(self) -> str:
        """List all available categories."""
        categories = self.db.query(Category).all()
        category_names = [
            f"{category.name} codigo {category.short_name}" for category in categories
        ]
        return (
            "Categorías existentes:\n" + ",\n".join(category_names)
            if category_names
            else "No hay categorías existentes."
        )
    
    def handle_interactive_response(self, interactive: Interactive) -> None:
        """Handle interactive button responses for expense confirmation/rejection."""
        if interactive.type == "button_reply" and interactive.button_reply:
            button_id: str = interactive.button_reply.id
            instruction, id_str = button_id.split("_", 1)
            expense_id = int(id_str)
            expense: Expense = (
                self.db.query(Expense)
                .filter_by(id=expense_id, user_id=self.user.id)
                .first()
            )

            if not expense:
                WhatsAppService.send_message(
                    self.user.phone, "❌ No se encontró el gasto solicitado."
                )
                return

            if instruction == "confirm":
                expense.status = "confirmed"
                self.db.commit()
                message = f"✅ *¡Gasto confirmado exitosamente!*\n{expense}\n\n¡Tu gasto ha sido registrado correctamente! 💫"

            elif instruction == "decline":
                expense.status = "rejected"
                self.db.commit()
                message = f"❌ *Gasto rechazado:*\n{expense}\n\nEl gasto ha sido rechazado y no se guardará en tus registros."
            else:
                message = f"⚠️ Acción no reconocida: {instruction}"

            WhatsAppService.send_message(self.user.phone, message)
    
    def create_expense_from_text(self, text: str) -> None:
        """Process expense creation from text message."""
        parsed_text = text.strip().lower()
        cuerpo: str
        cuerpo, tags = self._split_text_and_tag(parsed_text)
        cuerpo, date_str = self._extract_date(cuerpo)
        
        # Handle tags
        tag_objs = []
        if tags:
            tag_objs = self.tag_manager.get_or_create_tags(tags)

        # Parse expense details
        items = cuerpo.split()
        price = items[0]
        currency = "CLP"
        
        if ("," in price) or ("." in price):
            price = price.replace(",", ".")
            price = float(price + "0")
            currency = "USD"
        else:
            price = int(price)
            
        category = items[1] if len(items) > 1 else "x"
        description = " ".join(items[2:]) if len(items) > 2 else "No description"

        category_obj = self.db.query(Category).filter(
            (Category.short_name.ilike(category)) | (Category.name.ilike(category))
        ).first()

        # Create expense
        expense = Expense(
            user_id=self.user.id,
            amount=price,
            category=category_obj,
            description=description,
            currency=currency,
            raw_text=text,
            chat_id=self.user.phone,
            expense_date=date_str,
        )
        self.db.add(expense)
        
        # Add tags
        if tags:
            for tag in tag_objs:
                expense.tags.append(tag)
        self.db.commit()
        
        # Send confirmation message with buttons
        confirmation_text = f"💰 *Gasto en proceso:* \n{expense}"
        WhatsAppService.send_confirm_interaction(self.user.phone, confirmation_text, expense.id)
    
    def _split_text_and_tag(self, texto: str) -> Tuple[str, Optional[List[str]]]:
        """
        Separa el texto de una o más etiquetas con @ al final.
        Retorna (texto_sin_tags, tags) como tupla.
        Si no hay etiquetas, tags será None.
        """
        # Busca todas las etiquetas @tag al final del texto
        tags = re.findall(r"@([^\s]+)", texto)
        # Elimina las etiquetas del texto
        cuerpo = re.sub(r"\s*@([^\s]+)", "", texto).strip()
        return cuerpo, tags if tags else None
    
    def _extract_date(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Extracts a date from the text in formats:
        dd/mm/yyyy, dd-mm-yyyy, dd/mm/yy, dd-mm-yy, dd/mm, dd-mm
        If only day and month, assumes current year.
        Returns a tuple (text_without_date, date_in_YYYY-MM-DD format or None).
        """
        date_patterns = [
            r"(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b)",  # dd/mm/yyyy or dd-mm-yyyy or dd/mm/yy or dd-mm-yy
            r"(\b\d{1,2}[/-]\d{1,2}\b)",              # dd/mm or dd-mm
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                try:
                    if re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", date_str):
                        # Handle full date with year
                        parts = re.split(r"[/-]", date_str)
                        day = int(parts[0])
                        month = int(parts[1])
                        year = int(parts[2])
                        if year < 100:  # Handle two-digit year
                            year += 2000
                    elif re.match(r"\d{1,2}[/-]\d{1,2}", date_str):
                        # Handle date without year, assume current year
                        parts = re.split(r"[/-]", date_str)
                        day = int(parts[0])
                        month = int(parts[1])
                        year = datetime.datetime.now().year
                    else:
                        continue
                    
                    extracted_date = datetime.datetime(year, month, day, 12, 0)
                    text_without_date = text.replace(date_str, "").strip()
                    return text_without_date, extracted_date.isoformat()
                except ValueError:
                    continue
        return text, datetime.datetime.now().isoformat()

    def list_expenses(self, text: str) -> str:
        """List expenses for the user based on the provided text."""
        text = text.strip().lower()
        text, tags = self._split_text_and_tag(text)

        if tags:
            return self._list_expenses_by_tags(tags)
        else:
            return self._list_expenses_by_month(text)

    def _list_expenses_by_tags(self, tags: List[str]) -> str:
        """List expenses filtered by tags."""
        expenses_query = self.db.query(Expense).filter(Expense.user_id == self.user.id)
        expenses_query = expenses_query.join(Expense.tags).filter(Tag.name.in_(tags))
        expenses = expenses_query.order_by(Expense.expense_date.desc()).all()
        
        if not expenses:
            return "No se encontraron gastos con las etiquetas especificadas."
        
        total_clp, total_usd = self._calculate_totals(expenses)
        header = f"📋 *Gastos con etiquetas {', '.join(tags)}:* {total_clp} CLP / {total_usd} USD\n\n"
        
        expenses_list = ""
        for expense in expenses:
            expenses_list += expense.custom_str(include_category=False, include_tags=True) + "\n\n"
        
        return header + expenses_list

    def _list_expenses_by_month(self, text: str) -> str:
        """List expenses filtered by month and display options."""
        items = text.split()
        month_input = items[1] if len(items) > 1 else None
        display_options = self._parse_display_options(items)
        
        month = self._parse_month(month_input) if month_input else None
        if month_input and month is None:
            return "❌ Mes no válido. Usa número (1-12) o nombre del mes en español."
        
        expenses = self._get_expenses_by_month(month)
        if not expenses:
            return "No se encontraron gastos para el período especificado."
        
        total_clp, total_usd = self._calculate_totals(expenses)
        header = self._build_month_header(month, total_clp, total_usd)
        
        expenses_list = ""
        for expense in expenses:
            expenses_list += expense.custom_str(display_options["cat"], display_options["tags"]) + "\n\n"
        
        return header + expenses_list

    def _parse_display_options(self, items: List[str]) -> dict:
        """Parse display options from command items."""
        return {
            "cat": "cat" in items,
            "tags": "tags" in items
        }

    def _parse_month(self, month_input: str) -> Optional[int]:
        """Parse month from string input (number or Spanish name)."""
        meses = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
            "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
            "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
        }
        
        try:
            month = int(month_input)
            if 1 <= month <= 12:
                return month
            return None
        except ValueError:
            return meses.get(month_input.lower())

    def _get_expenses_by_month(self, month: Optional[int]) -> List[Expense]:
        """Get expenses filtered by month."""
        expenses_query = self.db.query(Expense).filter(Expense.user_id == self.user.id)
        
        if month:
            current_year = datetime.datetime.now().year
            start_date = datetime.datetime(current_year, month, 1)
            if month == 12:
                end_date = datetime.datetime(current_year + 1, 1, 1)
            else:
                end_date = datetime.datetime(current_year, month + 1, 1)
            
            expenses_query = expenses_query.filter(
                Expense.expense_date >= start_date,
                Expense.expense_date < end_date
            )
        
        return expenses_query.order_by(Expense.expense_date.desc()).all()

    def _calculate_totals(self, expenses: List[Expense]) -> Tuple[str, str]:
        """Calculate and format total amounts for CLP and USD."""
        total_clp = sum(exp.amount for exp in expenses if exp.currency == "CLP")
        total_usd = sum(exp.amount for exp in expenses if exp.currency == "USD")
        
        formatted_clp = self.parse_money_text(total_clp, "CLP")
        formatted_usd = self.parse_money_text(total_usd, "USD")
        
        return formatted_clp, formatted_usd

    def _build_month_header(self, month: Optional[int], total_clp: str, total_usd: str) -> str:
        """Build header for month-based expense listing."""
        if month:
            meses = {
                1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
                5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
                9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
            }
            month_name = meses[month]
            return f"📋 *Gastos {month_name}:* {total_clp} CLP / {total_usd} USD\n\n"
        else:
            return f"📋 *Gastos:* {total_clp} CLP / {total_usd} USD\n\n"

    def get_summary(self, text: str = "day") -> str:
        """Get summary of expenses for different periods (day, week, month)."""
        now = datetime.datetime.now()
        items = text.strip().lower().split()
        period = items[1] if items else "day"
        
        if period in ["day", "hoy", "today", "diario"]:
            return self._get_daily_summary(now)
        elif period in ["week", "semana", "semanal"]:
            return self._get_weekly_summary(now)
        elif period in ["month", "mes", "mensual"]:
            # Check if a specific month is provided
            month_input = items[2] if len(items) > 2 else None
            target_month = self._parse_month(month_input) if month_input else now.month
            target_year = now.year
            
            if month_input and target_month is None:
                return "❌ Mes no válido. Usa número (1-12) o nombre del mes en español."
            
            return self._get_monthly_summary(now, target_month, target_year)
        else:
            return "❌ Período no válido. Usa: 'hoy', 'semana' o 'mes [mes_opcional]'"

    def _get_daily_summary(self, date: datetime.datetime) -> str:
        """Get summary for a specific day."""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        expenses = self._get_expenses_by_date_range(start_date, end_date)
        
        if not expenses:
            return "📅 *Resumen del día:*\nNo tienes gastos registrados hoy."
        
        total_clp, total_usd = self._calculate_totals(expenses)
        expense_count = len(expenses)
        
        # Get top category
        categories = {}
        for expense in expenses:
            cat_name = expense.category.name if expense.category else "Sin categoría"
            categories[cat_name] = categories.get(cat_name, 0) + expense.amount
        
        top_category = max(categories.items(), key=lambda x: x[1]) if categories else ("N/A", 0)
        
        summary = f"📅 *Resumen del día - {date.strftime('%d/%m/%Y')}:*\n\n"
        summary += f"💰 Total: {total_clp} CLP / {total_usd} USD\n"
        summary += f"📊 Cantidad de gastos: {expense_count}\n"
        summary += f"🏆 Categoría principal: {top_category[0]}\n\n"
        
        # Show last 3 expenses
        summary += "*Últimos gastos:*\n"
        for expense in expenses[:3]:
            summary += f"• {expense.custom_str(include_category=True, include_tags=False)}\n"
        
        if len(expenses) > 3:
            summary += f"\n_...y {len(expenses) - 3} gastos más_"
        
        return summary

    def _get_weekly_summary(self, date: datetime.datetime) -> str:
        """Get summary for the current week."""
        # Get Monday of current week
        monday = date - timedelta(days=date.weekday())
        start_date = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
        
        expenses = self._get_expenses_by_date_range(start_date, end_date)
        
        if not expenses:
            return "📅 *Resumen semanal:*\nNo tienes gastos registrados esta semana."
        
        total_clp, total_usd = self._calculate_totals(expenses)
        expense_count = len(expenses)
        
        # Calculate daily average
        daily_avg_clp = sum(exp.amount for exp in expenses if exp.currency == "CLP") / 7
        daily_avg_usd = sum(exp.amount for exp in expenses if exp.currency == "USD") / 7
        
        # Get category breakdown
        categories = {}
        for expense in expenses:
            cat_name = expense.category.name if expense.category else "Sin categoría"
            if cat_name not in categories:
                categories[cat_name] = {"clp": 0, "usd": 0, "count": 0}
            categories[cat_name][expense.currency.lower()] += expense.amount
            categories[cat_name]["count"] += 1
        
        summary = f"📅 *Resumen semanal - {start_date.strftime('%d/%m')} al {end_date.strftime('%d/%m')}:*\n\n"
        summary += f"💰 Total: {total_clp} CLP / {total_usd} USD\n"
        summary += f"📊 Cantidad de gastos: {expense_count}\n"
        summary += f"📈 Promedio diario: {self.parse_money_text(daily_avg_clp, 'CLP')} CLP / {self.parse_money_text(daily_avg_usd, 'USD')} USD\n\n"
        
        summary += "*Gastos por categoría:*\n"
        for cat_name, amounts in sorted(categories.items(), key=lambda x: x[1]["clp"] + x[1]["usd"], reverse=True):
            cat_clp = self.parse_money_text(amounts["clp"], "CLP")
            cat_usd = self.parse_money_text(amounts["usd"], "USD")
            summary += f"• {cat_name}: {cat_clp} CLP / {cat_usd} USD ({amounts['count']} gastos)\n"
        
        return summary

    def _get_monthly_summary(self, date: datetime.datetime, target_month: int = None, target_year: int = None) -> str:
        """Get summary for a specific month."""
        if target_month is None:
            target_month = date.month
        if target_year is None:
            target_year = date.year
            
        start_date = datetime.datetime(target_year, target_month, 1, 0, 0, 0, 0)
        if target_month == 12:
            end_date = datetime.datetime(target_year + 1, 1, 1, 0, 0, 0, 0)
        else:
            end_date = datetime.datetime(target_year, target_month + 1, 1, 0, 0, 0, 0)
        
        expenses = self._get_expenses_by_date_range(start_date, end_date)
        
        month_name = self._get_month_name(target_month)
        
        if not expenses:
            return f"📅 *Resumen mensual:*\nNo tienes gastos registrados en {month_name} {target_year}."
        
        total_clp, total_usd = self._calculate_totals(expenses)
        expense_count = len(expenses)
        
        # Calculate daily average
        days_in_month = (end_date - start_date).days
        daily_avg_clp = sum(exp.amount for exp in expenses if exp.currency == "CLP") / days_in_month
        daily_avg_usd = sum(exp.amount for exp in expenses if exp.currency == "USD") / days_in_month
        
        # Get category breakdown
        categories = {}
        for expense in expenses:
            cat_name = expense.category.name if expense.category else "Sin categoría"
            if cat_name not in categories:
                categories[cat_name] = {"clp": 0, "usd": 0, "count": 0}
            categories[cat_name][expense.currency.lower()] += expense.amount
            categories[cat_name]["count"] += 1
        
        summary = f"📅 *Resumen mensual - {month_name} {target_year}:*\n\n"
        summary += f"💰 Total: {total_clp} CLP / {total_usd} USD\n"
        summary += f"📊 Cantidad de gastos: {expense_count}\n"
        summary += f"📈 Promedio diario: {self.parse_money_text(daily_avg_clp, 'CLP')} CLP / {self.parse_money_text(daily_avg_usd, 'USD')} USD\n\n"
        
        summary += "*Categorías:*\n"
        for cat_name, amounts in categories.items():
            cat_clp = self.parse_money_text(amounts["clp"], "CLP")
            cat_usd = self.parse_money_text(amounts["usd"], "USD")
            summary += f"• {cat_name}: "
            if amounts["clp"] > 0:
                summary += f"{cat_clp} CLP"
            if amounts["usd"] > 0:
                summary += f"| {cat_usd} USD"
            summary += f" ({amounts['count']} gastos)\n"

        return summary

    def delete_last_expense(self) -> str:
        """Delete the most recent expense for the user."""
        last_expense = (
            self.db.query(Expense)
            .filter(Expense.user_id == self.user.id)
            .order_by(Expense.created_at.desc())
            .first()
        )
        
        if not last_expense:
            return "❌ No tienes gastos para eliminar."
        
        expense_info = str(last_expense)
        expense_status = last_expense.status
        
        self.db.delete(last_expense)
        self.db.commit()
        
        return f"🗑️ *Último gasto eliminado:*\n{expense_info}\n\n✅ El gasto ha sido eliminado de tus registros."

    def search_expenses(self, search_term: str) -> str:
        """Search expenses by description, category, or amount."""
        if not search_term or len(search_term.strip()) < 2:
            return "❌ El término de búsqueda debe tener al menos 2 caracteres."
        
        search_term = search_term.strip().lower()
        
        # Search in multiple fields
        expenses_query = self.db.query(Expense).filter(Expense.user_id == self.user.id)
        
        # Search by description
        description_results = expenses_query.filter(
            Expense.description.ilike(f"%{search_term}%")
        )
        
        # Search by category name
        category_results = expenses_query.join(Category, Expense.category_id == Category.id).filter(
            Category.name.ilike(f"%{search_term}%")
        )
        
        # Search by amount (if search term is numeric)
        amount_results = []
        try:
            search_amount = float(search_term.replace(",", "."))
            amount_results = expenses_query.filter(Expense.amount == search_amount)
        except ValueError:
            pass
        
        # Combine all results and remove duplicates
        all_results = set()
        for result_set in [description_results, category_results, amount_results]:
            if result_set:
                all_results.update(result_set.all())
        
        expenses = list(all_results)
        expenses.sort(key=lambda x: x.expense_date, reverse=True)
        
        if not expenses:
            return f"❌ No se encontraron gastos que contengan '{search_term}'."
        
        total_clp, total_usd = self._calculate_totals(expenses)
        result_count = len(expenses)
        
        header = f"🔍 *Resultados para '{search_term}':*\n"
        header += f"📊 {result_count} gasto{'s' if result_count != 1 else ''} encontrado{'s' if result_count != 1 else ''}\n"
        header += f"💰 Total: {total_clp} CLP / {total_usd} USD\n\n"
        
        expenses_list = ""
        # Show maximum 10 results
        for expense in expenses[:10]:
            expenses_list += expense.custom_str(include_category=True, include_tags=True) + "\n\n"
        
        if len(expenses) > 10:
            expenses_list += f"_...y {len(expenses) - 10} resultados más_\n"
            expenses_list += "💡 *Tip:* Usa un término más específico para refinar la búsqueda."
        
        return header + expenses_list

    def _get_expenses_by_date_range(self, start_date: datetime.datetime, end_date: datetime.datetime) -> List[Expense]:
        """Get expenses within a date range."""
        return (
            self.db.query(Expense)
            .filter(
                Expense.user_id == self.user.id,
                Expense.expense_date >= start_date,
                Expense.expense_date < end_date
            )
            .order_by(Expense.expense_date.desc())
            .all()
        )

    def _get_month_name(self, month_number: int) -> str:
        """Get Spanish month name from month number."""
        meses = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        return meses.get(month_number, "mes desconocido")

    def parse_money_text(self, number: float, currency: str) -> str:
        """Parse and return a human-readable monetary $1,200.50 for usd or $1.200 for clp"""
        if currency == "USD":
            return f"${number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif currency == "CLP":
            return f"${int(number):,}".replace(",", ".")
        else:
            return f"{number} {currency}"