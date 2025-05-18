import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
import sqlite3
import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
API_TOKEN = '7788934089:AAG18zRX9cYwgry8iFGhCzCisbOPL3Blwgc'  # Замените на реальный токен!
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Подключение к SQLite
conn = sqlite3.connect('notes.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблицы для заметок
cursor.execute('''
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    note_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# Определение состояний
class NoteStates(StatesGroup):
    add_note = State()
    delete_note = State()

# Главное меню
def get_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить заметку", callback_data="add_note")],
            [InlineKeyboardButton(text="📝 Просмотреть заметки", callback_data="view_notes")],
            [InlineKeyboardButton(text="❌ Удалить заметку", callback_data="delete_note")]
        ]
    )

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📚 <b>Привет! Это бот для управления заметками.</b>\n"
        "Выбери действие:",
        reply_markup=get_main_menu()
    )

# Обработчик кнопки "Добавить заметку"
@dp.callback_query(lambda c: c.data == 'add_note')
async def add_note_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📝 Введи текст заметки:")
    await state.set_state(NoteStates.add_note)

# Обработчик текста заметки
@dp.message(NoteStates.add_note)
async def process_note_text(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    note_text = message.text
    
    cursor.execute(
        "INSERT INTO notes (user_id, note_text) VALUES (?, ?)",
        (user_id, note_text)
    )
    conn.commit()
    
    await message.answer(
        "✅ <b>Заметка успешно сохранена!</b>",
        reply_markup=get_main_menu()
    )
    await state.clear()

# Обработчик кнопки "Просмотреть заметки"
@dp.callback_query(lambda c: c.data == 'view_notes')
async def view_notes_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    cursor.execute(
        "SELECT note_text, created_at FROM notes "
        "WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    notes = cursor.fetchall()
    
    if not notes:
        await callback.message.answer("📭 У вас пока нет заметок.")
    else:
        response = ["<b>📋 Ваши заметки:</b>", ""]
        for i, (text, created_at) in enumerate(notes, 1):
            response.append(f"{i}. {text}")
            response.append(f"<i>Создано: {created_at}</i>")
            response.append("")
        
        await callback.message.answer("\n".join(response))
    
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=get_main_menu()
    )

# Обработчик кнопки "Удалить заметку"
@dp.callback_query(lambda c: c.data == 'delete_note')
async def delete_note_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    
    cursor.execute(
        "SELECT id, note_text FROM notes "
        "WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    notes = cursor.fetchall()
    
    if not notes:
        await callback.message.answer(
            "❌ Нет заметок для удаления.",
            reply_markup=get_main_menu()
        )
        return
    
    keyboard = []
    for note_id, note_text in notes:
        text = note_text[:25] + "..." if len(note_text) > 25 else note_text
        keyboard.append([InlineKeyboardButton(
            text=f"🗑 {text}",
            callback_data=f"delete_{note_id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="cancel_delete"
    )])
    
    await callback.message.answer(
        "Выберите заметку для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(NoteStates.delete_note)

# Обработчик выбора заметки для удаления
@dp.callback_query(StateFilter(NoteStates.delete_note), lambda c: c.data.startswith('delete_'))
async def delete_selected_note(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    note_id = callback.data.split('_')[1]
    
    cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    
    await callback.message.answer(
        "✅ Заметка успешно удалена!",
        reply_markup=get_main_menu()
    )
    await state.clear()

# Обработчик отмены удаления
@dp.callback_query(StateFilter(NoteStates.delete_note), lambda c: c.data == 'cancel_delete')
async def cancel_delete(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "❌ Удаление отменено.",
        reply_markup=get_main_menu()
    )
    await state.clear()

# Обработчик любых других сообщений
@dp.message()
async def handle_unknown(message: types.Message):
    await message.answer(
        "🤖 Я не понимаю эту команду.\n"
        "Пожалуйста, используйте кнопки меню или команду /start",
        reply_markup=get_main_menu()
    )

# Запуск бота
async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())