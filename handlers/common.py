from aiogram import Router, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config import settings
from database import get_session
from keyboards import (
    role_keyboard, parent_name_keyboard,
    child_main_menu, parent_main_menu
)
from models import User, UserRole, ParentRole, Points

router = Router()


class RegistrationFSM(StatesGroup):
    choosing_role = State()
    entering_parent_code = State()
    choosing_parent_name = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

    if user and user.is_active:
        if user.role == UserRole.child:
            await message.answer(
                f"👋 Привет, *{user.name}*! Рада тебя видеть! 🌟\n\nВот главное меню:",
                reply_markup=child_main_menu(),
                parse_mode="Markdown"
            )
        else:
            parent_greeting = "Мама" if user.parent_role == ParentRole.mom else "Папа"
            await message.answer(
                f"👋 Привет, *{parent_greeting}*! 😊\n\nВот главное меню:",
                reply_markup=parent_main_menu(),
                parse_mode="Markdown"
            )
        return

    await state.set_state(RegistrationFSM.choosing_role)
    await message.answer(
        "👋 *Привет! Добро пожаловать в семейный бот!* 🏠\n\n"
        "Для начала давай определим, кто ты:",
        reply_markup=role_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(RegistrationFSM.choosing_role, F.data == "role_child")
async def handle_role_child(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name or "Соломия"

    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if not existing:
            new_user = User(
                telegram_id=user_id,
                role=UserRole.child,
                name="Соломия",
            )
            session.add(new_user)

            points = Points(telegram_id=user_id, balance=0)
            session.add(points)

    await state.clear()
    await callback.message.edit_text(
        "🌟 *Привет, Соломия!* 👧\n\n"
        "Отлично, ты зарегистрирована! Теперь ты можешь видеть свои задачи, "
        "зарабатывать очки и получать награды!\n\n"
        "Вот твоё главное меню:",
        reply_markup=child_main_menu(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(RegistrationFSM.choosing_role, F.data == "role_parent")
async def handle_role_parent(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RegistrationFSM.entering_parent_code)
    await callback.message.edit_text(
        "🔐 *Регистрация родителя*\n\n"
        "Введи секретный семейный код для подтверждения:",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(RegistrationFSM.entering_parent_code)
async def handle_parent_code(message: Message, state: FSMContext) -> None:
    if message.text.strip() != settings.PARENT_CODE:
        await message.answer(
            "❌ *Неверный код!*\n\n"
            "Попробуй ещё раз или напиши /start для начала.",
            parse_mode="Markdown"
        )
        return

    await state.set_state(RegistrationFSM.choosing_parent_name)
    await message.answer(
        "✅ *Код верный!*\n\n"
        "Кто ты?",
        reply_markup=parent_name_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(RegistrationFSM.choosing_parent_name)
async def handle_parent_name(callback: CallbackQuery, state: FSMContext) -> None:
    is_mom = callback.data == "parent_role_mom"
    parent_role = ParentRole.mom if is_mom else ParentRole.dad
    name = "Мама" if is_mom else "Папа"
    user_id = callback.from_user.id

    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if not existing:
            new_user = User(
                telegram_id=user_id,
                role=UserRole.parent,
                parent_role=parent_role,
                name=name,
            )
            session.add(new_user)
        else:
            existing.role = UserRole.parent
            existing.parent_role = parent_role
            existing.name = name

    await state.clear()
    await callback.message.edit_text(
        f"✅ *{name}, добро пожаловать!* 👨‍👩‍👧\n\n"
        f"Ты зарегистрирован(а) как родитель. "
        f"Теперь ты будешь получать все уведомления о задачах Соломии.\n\n"
        f"Вот главное меню:",
        reply_markup=parent_main_menu(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await message.answer(
            "❓ *Помощь*\n\n"
            "Сначала используй /start для регистрации.",
            parse_mode="Markdown"
        )
        return

    if user.role == UserRole.child:
        help_text = (
            "❓ *Справка для Соломии*\n\n"
            "🔹 *Мой план* — посмотреть план на день\n"
            "🔹 *Мои задачи* — все задачи на сегодня\n"
            "🔹 *Выполнено* — отметить задачу как выполненную\n"
            "🔹 *Перенести* — попросить родителей перенести задачу\n"
            "🔹 *Напомнить позже* — отложить напоминание\n"
            "🔹 *Добавить ДЗ* — добавить домашнее задание\n"
            "🔹 *Моя награда* — посмотреть баланс и награды\n\n"
            "За выполнение задач ты получаешь очки! 💫"
        )
    else:
        help_text = (
            "❓ *Справка для родителей*\n\n"
            "🔹 *Отчёт за день* — статистика за сегодня\n"
            "🔹 *Отчёт за неделю* — статистика за неделю\n"
            "🔹 *Добавить задачу* — создать новую задачу для Соломии\n"
            "🔹 *Задачи дочки* — все активные задачи\n"
            "🔹 *Невыполненные* — просроченные задачи\n"
            "🔹 *Расписание* — управление расписанием\n"
            "🔹 *Награда недели* — одобрить еженедельную награду"
        )

    await message.answer(help_text, parse_mode="Markdown")


@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery) -> None:
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await callback.message.edit_text("Используй /start для начала.")
        await callback.answer()
        return

    if user.role == UserRole.child:
        await callback.message.edit_text(
            "🏠 *Главное меню*",
            reply_markup=child_main_menu(),
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            "🏠 *Главное меню*",
            reply_markup=parent_main_menu(),
            parse_mode="Markdown"
        )
    await callback.answer()


@router.message(StateFilter(None))
async def handle_unknown(message: Message) -> None:
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await message.answer(
            "👋 Используй /start для начала работы с ботом!",
        )
        return

    if user.role == UserRole.child:
        await message.answer(
            "Используй кнопки меню! 👇",
            reply_markup=child_main_menu(),
        )
    else:
        await message.answer(
            "Используй кнопки меню! 👇",
            reply_markup=parent_main_menu(),
        )
