from typing import Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def child_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Мой план", callback_data="child_my_plan"))
    builder.row(InlineKeyboardButton(text="📝 Мои задачи", callback_data="child_my_tasks"))
    builder.row(
        InlineKeyboardButton(text="✅ Выполнено", callback_data="child_done"),
        InlineKeyboardButton(text="📅 Перенести", callback_data="child_postpone"),
    )
    builder.row(
        InlineKeyboardButton(text="⏰ Напомнить позже", callback_data="child_remind_later"),
        InlineKeyboardButton(text="📚 Добавить ДЗ", callback_data="child_add_homework"),
    )
    builder.row(InlineKeyboardButton(text="🏆 Моя награда", callback_data="child_my_reward"))
    return builder.as_markup()


def parent_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Отчёт за день", callback_data="parent_daily_report"),
        InlineKeyboardButton(text="📈 Отчёт за неделю", callback_data="parent_weekly_report"),
    )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить задачу", callback_data="parent_add_task"),
        InlineKeyboardButton(text="📋 Задачи дочки", callback_data="parent_tasks"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Невыполненные", callback_data="parent_failed_tasks"),
        InlineKeyboardButton(text="🗓 Расписание", callback_data="parent_schedule"),
    )
    builder.row(InlineKeyboardButton(text="🎁 Награда недели", callback_data="parent_reward"))
    return builder.as_markup()


def task_list_keyboard(tasks: list, action: str = "complete") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for task in tasks:
        task_id = task.id if hasattr(task, "id") else task.get("id")
        title = task.title if hasattr(task, "title") else task.get("title", "")
        display = f"{'✅' if action == 'complete' else '📅'} {title[:40]}"
        builder.row(InlineKeyboardButton(
            text=display,
            callback_data=f"{action}_task_{task_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu"))
    return builder.as_markup()


def postpone_time_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏱ 30 мин", callback_data="remind_30"),
        InlineKeyboardButton(text="⏰ 1 час", callback_data="remind_60"),
    )
    builder.row(
        InlineKeyboardButton(text="⏳ 2 часа", callback_data="remind_120"),
        InlineKeyboardButton(text="📅 Завтра", callback_data="remind_tomorrow"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu"))
    return builder.as_markup()


def confirm_keyboard(
    yes_text: str = "✅ Да",
    no_text: str = "❌ Нет",
    yes_callback: str = "confirm_yes",
    no_callback: str = "confirm_no"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=yes_text, callback_data=yes_callback),
        InlineKeyboardButton(text=no_text, callback_data=no_callback),
    )
    return builder.as_markup()


def postpone_request_parent_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Одобрить",
            callback_data=f"postpone_approve_{request_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"postpone_reject_{request_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="💬 Ответить",
            callback_data=f"postpone_reply_{request_id}"
        )
    )
    return builder.as_markup()


def reward_confirm_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"reward_confirm_{request_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Выбрать другую",
            callback_data=f"reward_change_{request_id}"
        ),
        InlineKeyboardButton(
            text="🚫 Без награды",
            callback_data=f"reward_none_{request_id}"
        ),
    )
    return builder.as_markup()


def reward_list_keyboard(rewards: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for reward in rewards:
        reward_id = reward.id if hasattr(reward, "id") else reward.get("id")
        title = reward.title if hasattr(reward, "title") else reward.get("title", "")
        cost = reward.cost_points if hasattr(reward, "cost_points") else reward.get("cost_points", 0)
        display = f"🏆 {title[:30]} — {cost} очков"
        builder.row(InlineKeyboardButton(
            text=display,
            callback_data=f"select_reward_{reward_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu"))
    return builder.as_markup()


def category_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Дом", callback_data="cat_home"),
        InlineKeyboardButton(text="📚 Школа", callback_data="cat_school"),
    )
    builder.row(
        InlineKeyboardButton(text="🎨 Личное", callback_data="cat_personal"),
        InlineKeyboardButton(text="📅 Еженедельное", callback_data="cat_weekly"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu"))
    return builder.as_markup()


def priority_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🟢 Низкий", callback_data="pri_low"),
        InlineKeyboardButton(text="🟡 Средний", callback_data="pri_medium"),
        InlineKeyboardButton(text="🔴 Высокий", callback_data="pri_high"),
    )
    return builder.as_markup()


def critical_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚠️ Да, критическая", callback_data="critical_yes"),
        InlineKeyboardButton(text="✅ Нет", callback_data="critical_no"),
    )
    return builder.as_markup()


def back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu"))
    return builder.as_markup()


def recur_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Ежедневно", callback_data="recur_daily"),
        InlineKeyboardButton(text="📅 Будни", callback_data="recur_weekday"),
    )
    builder.row(
        InlineKeyboardButton(text="📆 Еженедельно", callback_data="recur_weekly"),
        InlineKeyboardButton(text="1️⃣ Один раз", callback_data="recur_once"),
    )
    return builder.as_markup()


def recur_time_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🌅 Утро", callback_data="rtime_morning"),
        InlineKeyboardButton(text="🌙 Вечер", callback_data="rtime_evening"),
    )
    return builder.as_markup()


def role_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👧 Я Соломия", callback_data="role_child"),
        InlineKeyboardButton(text="👨‍👩‍👧 Я родитель", callback_data="role_parent"),
    )
    return builder.as_markup()


def parent_name_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👩 Мама", callback_data="parent_role_mom"),
        InlineKeyboardButton(text="👨 Папа", callback_data="parent_role_dad"),
    )
    return builder.as_markup()
