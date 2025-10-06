from __future__ import annotations

import shlex
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Category, Expense, User


_CLEAR_TOKENS = {'', '-', 'none', 'null', 'ninguno'}


class CategoryManager:
    '''Handles category-related operations and command parsing.'''

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def handle(self, command_text: str) -> str:
        '''Dispatch cat-prefixed commands (list/create/update/delete/info/help).'''
        command_text = (command_text or '').strip()
        if not command_text:
            return self.list_categories()

        tokens = self._tokenize(command_text)
        if not tokens:
            return self.list_categories()

        action = tokens[0].lower()
        remainder = command_text[len(tokens[0]):].strip() if len(command_text) > len(tokens[0]) else ''

        if action in ('list', 'l', 'ls', 'show'):
            return self.list_categories()
        if action in ('create', 'c', 'add', '+'):
            return self.create_category(remainder)
        if action in ('update', 'u', 'edit', 'rename'):
            return self.update_category(remainder)
        if action in ('delete', 'd', 'remove', 'rm', 'del'):
            return self.delete_category(remainder)
        if action in ('info', 'i', 'details'):
            return self.show_info(remainder)
        if action in ('help', 'h', '?'):
            return self.show_help()

        return "❌ Acción de categoría no reconocida. Usa 'cat help' para ver opciones."

    def list_categories(self) -> str:
        '''Return a formatted list of available categories.'''
        categories = (
            self.db.query(Category)
            .order_by(Category.is_system.desc(), func.lower(Category.name))
            .all()
        )
        if not categories:
            return 'No hay categorías registradas.'

        system_lines: List[str] = []
        custom_lines: List[str] = []
        for category in categories:
            parts: List[str] = []
            if category.emoji:
                parts.append(category.emoji)
            parts.append(category.name)
            if category.short_name:
                parts.append(f"[{category.short_name}]")
            if category.parent:
                reference = category.parent.short_name or category.parent.name
                parts.append(f"↳ {reference}")

            formatted = ' '.join(parts)
            if category.is_system:
                system_lines.append(formatted)
            else:
                custom_lines.append(formatted)

        sections: List[str] = ['📂 *Categorías disponibles:*']
        if system_lines:
            sections.append('🔒 *Sistema:*\n' + '\n'.join(system_lines))
        if custom_lines:
            sections.append('🧩 *Personalizadas:*\n' + '\n'.join(custom_lines))

        return '\n\n'.join(sections)

    def create_category(self, args_text: str) -> str:
        '''Create a new custom category.'''
        tokens = self._tokenize(args_text)
        if not tokens:
            return '❌ Debes indicar un nombre. Ejemplo: cat c Transporte urbano code=trans'

        name_tokens, options = self._split_name_and_options(tokens)
        if not name_tokens:
            return '❌ Debes indicar un nombre.'

        name = ' '.join(name_tokens).strip()
        if not name:
            return '❌ Debes indicar un nombre.'

        code_option = self._pick_option(options, ('code', 'short', 'alias'))
        desired_code = None if self._should_clear(code_option) else self._normalize_code(code_option)
        emoji = None if self._should_clear(options.get('emoji')) else options.get('emoji')
        parent_option = options.get('parent')
        parent = None
        if parent_option and not self._should_clear(parent_option):
            parent = self._get_category_by_identifier(parent_option)
            if not parent:
                return f"❌ No se encontró la categoría padre '{parent_option}'."

        if self._category_exists(name, parent):
            return '❌ Ya existe una categoría con ese nombre.'

        if desired_code and self._get_category_by_short(desired_code):
            return f"❌ El código '{desired_code}' ya está en uso."

        short_name = desired_code or self._generate_short_name(name)

        category = Category(
            name=name,
            short_name=short_name,
            emoji=emoji,
            parent=parent,
            is_system=False,
        )
        self.db.add(category)
        self.db.commit()

        parent_text = f" (hija de {parent.name})" if parent else ''
        return f"✅ Categoría creada: *{name}* [{short_name}]{parent_text}."

    def update_category(self, args_text: str) -> str:
        '''Update name, short code, emoji or parent of a custom category.'''
        tokens = self._tokenize(args_text)
        if not tokens:
            return '❌ Debes indicar la categoría a actualizar. Ejemplo: cat u comida name=Comidas code=food'

        identifier = tokens[0]
        target = self._get_category_by_identifier(identifier)
        if not target:
            return f"❌ No se encontró la categoría '{identifier}'."
        if target.is_system:
            return '❌ No puedes editar categorías del sistema.'

        name_tokens, options = self._split_name_and_options(tokens[1:])
        updates: List[str] = []

        if name_tokens:
            new_name = ' '.join(name_tokens).strip()
            if new_name and new_name != target.name:
                if self._category_exists(new_name, target.parent, exclude_id=target.id):
                    return '❌ Ya existe otra categoría con ese nombre.'
                target.name = new_name
                updates.append(f"nombre='{new_name}'")

        code_option = self._pick_option(options, ('code', 'short', 'alias'))
        if code_option is not None:
            if self._should_clear(code_option):
                target.short_name = None
                updates.append('código eliminado')
            else:
                new_code = self._normalize_code(code_option)
                if new_code:
                    existing = self._get_category_by_short(new_code)
                    if existing and existing.id != target.id:
                        return f"❌ El código '{new_code}' ya está en uso."
                    target.short_name = new_code
                    updates.append(f"código='{new_code}'")

        if 'emoji' in options:
            emoji_option = options['emoji']
            if self._should_clear(emoji_option):
                target.emoji = None
                updates.append('emoji eliminado')
            else:
                target.emoji = emoji_option
                updates.append(f"emoji='{emoji_option}'")

        if 'parent' in options:
            parent_option = options['parent']
            if self._should_clear(parent_option):
                target.parent = None
                updates.append('sin categoría padre')
            else:
                parent = self._get_category_by_identifier(parent_option)
                if not parent:
                    return f"❌ No se encontró la categoría padre '{parent_option}'."
                if parent.id == target.id:
                    return '❌ Una categoría no puede ser su propia padre.'
                if self._is_descendant(parent, target):
                    return '❌ Se detectó un ciclo en la jerarquía de categorías.'
                target.parent = parent
                updates.append(f"padre='{parent.name}'")

        if not updates:
            return 'ℹ️ No se detectaron cambios.'

        self.db.commit()
        return f"✅ Categoría actualizada ({', '.join(updates)})."

    def delete_category(self, args_text: str) -> str:
        '''Delete a custom category if it has no expenses.'''
        tokens = self._tokenize(args_text)
        if not tokens:
            return '❌ Debes indicar la categoría a eliminar. Ejemplo: cat d comida'

        identifier = tokens[0]
        category = self._get_category_by_identifier(identifier)
        if not category:
            return f"❌ No se encontró la categoría '{identifier}'."
        if category.is_system:
            return '❌ No puedes eliminar categorías del sistema.'
        if category.children:
            return '❌ Esta categoría tiene subcategorías. Elimínalas o muévelas primero.'
        if self._has_expenses(category):
            return '❌ No puedes eliminar una categoría con gastos asociados.'

        name, code = category.name, category.short_name
        self.db.delete(category)
        self.db.commit()
        code_text = f" [{code}]" if code else ''
        return f"🗑️ Categoría eliminada: *{name}*{code_text}."

    def show_info(self, args_text: str) -> str:
        '''Show detailed information about a category.'''
        tokens = self._tokenize(args_text)
        if not tokens:
            return '❌ Debes indicar la categoría. Ejemplo: cat info comida'

        identifier = tokens[0]
        category = self._get_category_by_identifier(identifier)
        if not category:
            return f"❌ No se encontró la categoría '{identifier}'."

        parent_name = category.parent.name if category.parent else 'Sin padre'
        scope = 'Sistema' if category.is_system else 'Personal'
        short_text = category.short_name or 'Sin código'
        emoji_text = category.emoji or 'Sin emoji'
        expense_count = (
            self.db.query(Expense.id)
            .filter(Expense.category_id == category.id)
            .count()
        )

        lines = [
            '📘 *Detalle de categoría*',
            f'Nombre: {category.name}',
            f'Código: {short_text}',
            f'Emoji: {emoji_text}',
            f'Padre: {parent_name}',
            f'Ámbito: {scope}',
            f'Gastos asociados: {expense_count}',
        ]
        return '\n'.join(lines)

    def show_help(self) -> str:
        '''Return help text for category commands.'''
        return (
            '📚 *Comandos de categorías:*'
            '\n• `cat` o `cat list` — listar categorías'
            '\n• `cat c <nombre> [code=alias] [emoji=📁] [parent=codigo]` — crear'
            '\n• `cat u <id> [name=Nuevo nombre] [code=nuevo] [emoji=📁] [parent=codigo|-]` — actualizar'
            '\n• `cat d <id>` — eliminar (sin gastos ni subcategorías)'
            '\n• `cat info <id>` — detalle de una categoría'
        )

    def _tokenize(self, text: str) -> List[str]:
        text = (text or '').strip()
        if not text:
            return []
        try:
            return shlex.split(text)
        except ValueError:
            return text.split()

    def _split_name_and_options(self, tokens: List[str]) -> Tuple[List[str], Dict[str, str]]:
        name_tokens: List[str] = []
        options: Dict[str, str] = {}
        for token in tokens:
            if '=' in token:
                key, value = token.split('=', 1)
                options[key.lower().strip()] = value.strip()
            else:
                name_tokens.append(token)
        return name_tokens, options

    def _pick_option(self, options: Dict[str, str], keys: Tuple[str, ...]) -> Optional[str]:
        for key in keys:
            if key in options:
                return options[key]
        return None

    def _get_category_by_identifier(self, identifier: str) -> Optional[Category]:
        if not identifier:
            return None
        ident = identifier.strip().lower()
        if not ident:
            return None
        category = (
            self.db.query(Category)
            .filter(func.lower(Category.short_name) == ident)
            .first()
        )
        if category:
            return category
        return (
            self.db.query(Category)
            .filter(func.lower(Category.name) == ident)
            .first()
        )

    def _get_category_by_short(self, short_name: Optional[str]) -> Optional[Category]:
        if not short_name:
            return None
        return (
            self.db.query(Category)
            .filter(func.lower(Category.short_name) == short_name.lower())
            .first()
        )

    def _category_exists(self, name: str, parent: Optional[Category], exclude_id: Optional[int] = None) -> bool:
        if not name:
            return False
        query = (
            self.db.query(Category.id)
            .filter(func.lower(Category.name) == name.lower())
        )
        if parent:
            query = query.filter(Category.parent_id == parent.id)
        else:
            query = query.filter(Category.parent_id.is_(None))
        if exclude_id:
            query = query.filter(Category.id != exclude_id)
        return query.limit(1).first() is not None

    def _generate_short_name(self, name: str) -> str:
        base = ''.join(char for char in name.lower() if char.isalnum()) or 'cat'
        candidate = base[:6]
        if not candidate:
            candidate = 'cat'
        suffix = 1
        while self._get_category_by_short(candidate):
            candidate = f"{base[:4]}{suffix}" if base[:4] else f'cat{suffix}'
            suffix += 1
        return candidate

    def _normalize_code(self, code: Optional[str]) -> Optional[str]:
        if code is None:
            return None
        cleaned = code.strip().lower()
        return cleaned or None

    def _should_clear(self, value: Optional[str]) -> bool:
        if value is None:
            return False
        return value.strip().lower() in _CLEAR_TOKENS

    def _has_expenses(self, category: Category) -> bool:
        return (
            self.db.query(Expense.id)
            .filter(Expense.category_id == category.id)
            .limit(1)
            .first()
            is not None
        )

    def _is_descendant(self, parent: Category, target: Category) -> bool:
        current = parent
        while current:
            if current.id == target.id:
                return True
            current = current.parent
        return False
