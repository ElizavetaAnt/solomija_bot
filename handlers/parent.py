from datetime import date, datetime, timedelta
from typing import Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, and_, func

from config import settings
from database import get_session
from keyboards import (
    parent_main_menu, back_keyboard, category_keyboard, priority_keyboard,
    critical_keyboard, recur_type_keyboard, recur_time_keyboard,
    task_list_keyboard, confirm_keyboard
)
from messages import daily_report_parent, weekly_report_parent
from models import (
    Task, TaskCompletion, CompletionStatus, Points, PointsHistory,
    RecurType, RecurTime, TaskCategory, TaskPriority,
    ScheduleBlock, Reward, RewardRequest, RewardRequestStatus,
    PostponeRequest, PostponeStatus, User, UserRole
)

router = Router()


class AddTaskFSM(StatesGroup):
    title = State()
    category = State()
    priority = State()
    critical = State()
    recur_type = State()
    recur_time_type = State()
    deadline = State()
    points = State()
    confirm = State()


class ScheduleFSM(StatesGroup):
    action = State()
    day = State()
    from_time = State()
    to_time = State()
    event_name = State()


async def get_week_bounds():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


async def calc_week_stats(session, week_start: date, week_end: date) -> dict:
    result = await session.execute(
        select(TaskCompletion)
        .join(Task)
        .where(
            and_(
                TaskCompletion.date >= week_start,
                TaskCompletion.date <= week_end,
                Task.is_active == True,
            )
        )
    )
    completions = result.scalars().all()

    if not completions:
        return {
            "total": 0, "done": 0, "percent": 0,
            "by_category": {}, "done_list": [], "failed_list": [],
            "critical_missed": [], "points_earned": 0
        }

    task_ids = [c.task_id for c in completions]
    task_result = await session.execute(
        select(Task).where(Task.id.in_(task_ids))
    )
    tasks_map = {t.id: t for t in task_result.scalars().all()}

    total = len(completions)
    done_comps = [c for c in completions if c.status == CompletionStatus.done]
    done = len(done_comps)
    percent = int(done / total * 100) if total > 0 else 0

    by_category: dict[str, list] = {}
    done_list = []
    failed_list = []
    critical_missed = []
    points_earned = 0

    for comp in completions:
        task = tasks_map.get(comp.task_id)
        if not task:
            continue
        cat = task.category.value if hasattr(task.category, 'value') else str(task.category)
        if cat not in by_category:
            by_category[cat] = [0, 0]
        by_category[cat][1] += 1

        if comp.status == CompletionStatus.done:
            by_category[cat][0] += 1
            done_list.append(task.title)
            points_earned += task.points
        elif comp.status in (CompletionStatus.pending, CompletionStatus.skipped):
            failed_list.append(task.title)
            if task.is_critical:
                critical_missed.append(task.title)

    return {
        "total": total,
        "done": done,
        "percent": percent,
        "by_category": {k: tuple(v) for k, v in by_category.items()},
        "done_list": done_list,
        "failed_list": failed_list,
        "critical_missed": critical_missed,
        "points_earned": points_earned,
    }


@router.callback_query(F.data == "parent_daily_report")
async def handle_daily_report(callback: CallbackQuery) -> None:
    today = date.today()

    async with get_session() as session:
        stats = await calc_week_stats(session, today, today)

    text = daily_report_parent(
        date_str=today.strftime("%d.%m.%Y (%A)"),
        completed=stats["done"],
        total=stats["total"],
        percent=stats["percent"],
        done_list=stats["done_list"],
        failed_list=stats["failed_list"],
        critical_missed=stats["critical_missed"],
        points_earned=stats["points_earned"],
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "parent_weekly_report")
async def handle_weekly_report(callback: CallbackQuery) -> None:
    week_start, week_end = await get_week_bounds()

    async with get_session() as session:
        stats = await calc_week_stats(session, week_start, week_end)

        points_result = await session.execute(
            select(Points).where(Points.telegram_id != 0)
        )
        child_points = points_result.scalar_one_or_none()
        balance = child_points.balance if child_points else 0

        reward_result = await session.execute(
            select(Reward)
            .where(Reward.is_active == True)
            .order_by(Reward.cost_points)
        )
        rewards = reward_result.scalars().all()

    percent = stats["percent"]
    if percent >= 85:
        reward_level = "big"
    elif percent >= 60:
        reward_level = "medium"
    else:
        reward_level = "none"

    achievements = []
    if percent == 100:
        achievements.append("Все задачи выполнены! 🌟")
    if not stats["critical_missed"]:
        achievements.append("Ни одной критической задачи не пропущено 💪")

    week_str = f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}"

    text = weekly_report_parent(
        week_str=week_str,
        percent=percent,
        by_category=stats["by_category"],
        achievements=achievements,
        failed=stats["failed_list"][:5],
        points=stats["points_earned"],
        reward_level=reward_level,
    )

    from keyboards import reward_confirm_keyboard
    from messages import reward_suggestion_parent

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "parent_add_task")
async def handle_add_task_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddTaskFSM.title)
    await callback.message.edit_text(
        "➕ *Новая задача для Соломии*\n\nВведи название задачи:",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(AddTaskFSM.title)
async def add_task_title(message: Message, state: FSMContext) -> None:
    await state.update_data(task_title=message.text.strip())
    await state.set_state(AddTaskFSM.category)
    await message.answer(
        "📁 *Выбери категорию:*",
        reply_markup=category_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(AddTaskFSM.category, F.data.startswith("cat_"))
async def add_task_category(callback: CallbackQuery, state: FSMContext) -> None:
    cat_map = {
        "cat_home": "home",
        "cat_school": "school",
        "cat_personal": "personal",
        "cat_weekly": "weekly",
    }
    await state.update_data(task_category=cat_map.get(callback.data, "personal"))
    await state.set_state(AddTaskFSM.priority)
    await callback.message.edit_text(
        "⚡ *Выбери приоритет:*",
        reply_markup=priority_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(AddTaskFSM.priority, F.data.startswith("pri_"))
async def add_task_priority(callback: CallbackQuery, state: FSMContext) -> None:
    pri_map = {"pri_low": "low", "pri_medium": "medium", "pri_high": "high"}
    await state.update_data(task_priority=pri_map.get(callback.data, "medium"))
    await state.set_state(AddTaskFSM.critical)
    await callback.message.edit_text(
        "⚠️ *Критическая задача?*\n\n(за невыполнение снимаются очки)",
        reply_markup=critical_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(AddTaskFSM.critical, F.data.in_({"critical_yes", "critical_no"}))
async def add_task_critical(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(task_critical=callback.data == "critical_yes")
    await state.set_state(AddTaskFSM.recur_type)
    await callback.message.edit_text(
        "🔄 *Повторение:*",
        reply_markup=recur_type_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(AddTaskFSM.recur_type, F.data.startswith("recur_"))
async def add_task_recur_type(callback: CallbackQuery, state: FSMContext) -> None:
    recur_map = {
        "recur_daily": "daily",
        "recur_weekday": "weekday",
        "recur_weekly": "weekly",
        "recur_once": "once",
    }
    recur = recur_map.get(callback.data, "once")
    await state.update_data(task_recur=recur)

    if recur in ("daily", "weekday", "weekly"):
        await state.set_state(AddTaskFSM.recur_time_type)
        await callback.message.edit_text(
            "🌅 *Когда выполнять?*",
            reply_markup=recur_time_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await state.set_state(AddTaskFSM.deadline)
        await callback.message.edit_text(
            "📅 *Введи дату* (ДД.ММ.ГГГГ):",
            parse_mode="Markdown"
        )
    await callback.answer()


@router.callback_query(AddTaskFSM.recur_time_type, F.data.startswith("rtime_"))
async def add_task_recur_time(callback: CallbackQuery, state: FSMContext) -> None:
    rtime_map = {"rtime_morning": "morning", "rtime_evening": "evening"}
    await state.update_data(task_recur_time=rtime_map.get(callback.data, "evening"))
    await state.set_state(AddTaskFSM.points)
    await callback.message.edit_text(
        "💫 *Сколько очков за выполнение?* (введи число от 1 до 10):",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(AddTaskFSM.deadline)
async def add_task_deadline(message: Message, state: FSMContext) -> None:
    try:
        deadline = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("❌ Неверный формат! Введи дату как ДД.ММ.ГГГГ:")
        return

    await state.update_data(task_deadline=deadline.isoformat())
    await state.set_state(AddTaskFSM.points)
    await message.answer(
        "💫 *Сколько очков за выполнение?* (введи число от 1 до 10):",
        parse_mode="Markdown"
    )


@router.message(AddTaskFSM.points)
async def add_task_points(message: Message, state: FSMContext) -> None:
    try:
        pts = int(message.text.strip())
        if pts < 1 or pts > 10:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 1 до 10:")
        return

    data = await state.get_data()

    async with get_session() as session:
        recur_type_val = data.get("task_recur", "once")
        recur_time_val = data.get("task_recur_time", "evening")
        deadline_str = data.get("task_deadline")
        deadline = date.fromisoformat(deadline_str) if deadline_str else None

        is_critical = data.get("task_critical", False)
        penalty = 2 if is_critical else 0

        task = Task(
            title=data["task_title"],
            category=data.get("task_category", "personal"),
            priority=data.get("task_priority", "medium"),
            is_critical=is_critical,
            is_recurring=recur_type_val in ("daily", "weekday", "weekly"),
            recur_type=recur_type_val,
            recur_time=recur_time_val,
            deadline=deadline,
            points=pts,
            penalty_points=penalty,
            created_by=message.from_user.id,
        )
        session.add(task)
        await session.flush()

        if recur_type_val == "once" and deadline:
            completion = TaskCompletion(
                task_id=task.id,
                date=deadline,
                status=CompletionStatus.pending,
            )
            session.add(completion)

    await state.clear()

    recur_labels = {
        "daily": "Ежедневно",
        "weekday": "По будням",
        "weekly": "Еженедельно",
        "once": "Один раз",
    }

    await message.answer(
        f"✅ *Задача создана!*\n\n"
        f"📌 {data['task_title']}\n"
        f"🔄 {recur_labels.get(recur_type_val, recur_type_val)}\n"
        f"💫 {pts} очков",
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "parent_tasks")
async def handle_parent_tasks(callback: CallbackQuery) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(Task).where(Task.is_active == True).order_by(Task.category, Task.title)
        )
        tasks = result.scalars().all()

    if not tasks:
        await callback.message.edit_text(
            "📋 Нет активных задач.",
            reply_markup=back_keyboard(),
        )
        await callback.answer()
        return

    cat_labels = {
        "home": "🏠 Дом",
        "school": "📚 Школа",
        "personal": "🎨 Личное",
        "weekly": "📅 Еженедельные",
    }
    by_cat: dict[str, list] = {}
    for task in tasks:
        cat = task.category.value if hasattr(task.category, 'value') else str(task.category)
        if cat not in by_cat:
            by_cat[cat] = []
        recur_icon = "🔄" if task.is_recurring else "1️⃣"
        critical_icon = "⚠️" if task.is_critical else ""
        by_cat[cat].append(f"{recur_icon}{critical_icon} {task.title} (+{task.points}⭐)")

    text = "📋 *Все задачи Соломии:*\n\n"
    for cat, items in by_cat.items():
        text += f"*{cat_labels.get(cat, cat)}:*\n"
        text += "\n".join([f"  • {i}" for i in items])
        text += "\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "parent_failed_tasks")
async def handle_failed_tasks(callback: CallbackQuery) -> None:
    today = date.today()

    async with get_session() as session:
        result = await session.execute(
            select(TaskCompletion)
            .join(Task)
            .where(
                and_(
                    TaskCompletion.date == today,
                    TaskCompletion.status == CompletionStatus.pending,
                    Task.is_active == True,
                )
            )
        )
        completions = result.scalars().all()

        task_ids = [c.task_id for c in completions]
        if task_ids:
            task_result = await session.execute(
                select(Task).where(Task.id.in_(task_ids))
            )
            tasks = task_result.scalars().all()
        else:
            tasks = []

    if not tasks:
        await callback.message.edit_text(
            "✅ *Отлично!* Все задачи сегодня выполнены!",
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    text = f"❌ *Невыполненные задачи на {today.strftime('%d.%m.%Y')}:*\n\n"
    for task in tasks:
        critical = "⚠️ КРИТИЧНО! " if task.is_critical else ""
        text += f"• {critical}{task.title} (+{task.points}⭐)\n"

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "parent_schedule")
async def handle_schedule(callback: CallbackQuery) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(ScheduleBlock)
            .where(ScheduleBlock.is_active == True)
            .order_by(ScheduleBlock.day_of_week, ScheduleBlock.blocked_from)
        )
        blocks = result.scalars().all()

    day_names = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}

    if not blocks:
        text = "🗓 *Расписание*\n\n(нет блоков)"
    else:
        text = "🗓 *Текущее расписание:*\n\n"
        for block in blocks:
            day = day_names.get(block.day_of_week, "Все дни") if block.day_of_week is not None else "Все дни"
            text += f"• *{day}* {block.blocked_from}–{block.blocked_to} — {block.event_name}\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить блок", callback_data="schedule_add"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "schedule_add")
async def handle_schedule_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ScheduleFSM.event_name)
    await callback.message.edit_text(
        "📅 *Добавить событие в расписание*\n\nНазвание события:",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(ScheduleFSM.event_name)
async def schedule_event_name(message: Message, state: FSMContext) -> None:
    await state.update_data(event_name=message.text.strip())
    await state.set_state(ScheduleFSM.day)
    await message.answer(
        "📅 День недели (0=Пн, 1=Вт, 2=Ср, 3=Чт, 4=Пт, 5=Сб, 6=Вс, или 'все'):"
    )


@router.message(ScheduleFSM.day)
async def schedule_day(message: Message, state: FSMContext) -> None:
    text = message.text.strip().lower()
    if text == "все":
        day = None
    else:
        try:
            day = int(text)
            if day < 0 or day > 6:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введи число от 0 до 6 или 'все':")
            return

    await state.update_data(event_day=day)
    await state.set_state(ScheduleFSM.from_time)
    await message.answer("🕐 Время начала (ЧЧ:ММ):")


@router.message(ScheduleFSM.from_time)
async def schedule_from_time(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат! Введи время как ЧЧ:ММ:")
        return

    await state.update_data(event_from=message.text.strip())
    await state.set_state(ScheduleFSM.to_time)
    await message.answer("🕐 Время окончания (ЧЧ:ММ):")


@router.message(ScheduleFSM.to_time)
async def schedule_to_time(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат! Введи время как ЧЧ:ММ:")
        return

    data = await state.get_data()

    async with get_session() as session:
        block = ScheduleBlock(
            day_of_week=data.get("event_day"),
            blocked_from=data["event_from"],
            blocked_to=message.text.strip(),
            event_name=data["event_name"],
        )
        session.add(block)

    await state.clear()
    await message.answer(
        f"✅ *Добавлено в расписание:*\n\n"
        f"📅 {data['event_name']}: {data['event_from']}–{message.text.strip()}",
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "parent_reward")
async def handle_parent_reward(callback: CallbackQuery) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(RewardRequest)
            .where(RewardRequest.status == RewardRequestStatus.pending)
            .order_by(RewardRequest.requested_at.desc())
        )
        requests = result.scalars().all()

        if not requests:
            await callback.message.edit_text(
                "🎁 *Награда недели*\n\nНет ожидающих запросов.",
                reply_markup=back_keyboard(),
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        req = requests[0]
        reward_result = await session.execute(
            select(Reward).where(Reward.id == req.reward_id)
        )
        reward = reward_result.scalar_one_or_none()

        child_result = await session.execute(
            select(Points)
        )
        child_points = child_result.scalars().first()
        balance = child_points.balance if child_points else 0

    from keyboards import reward_confirm_keyboard
    from messages import reward_suggestion_parent

    text = reward_suggestion_parent(
        reward.title if reward else "Неизвестно",
        reward.cost_points if reward else 0,
        balance
    )

    await callback.message.edit_text(
        text,
        reply_markup=reward_confirm_keyboard(req.id),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("postpone_approve_"))
async def handle_postpone_approve(callback: CallbackQuery) -> None:
    req_id = int(callback.data.split("_")[-1])

    async with get_session() as session:
        result = await session.execute(
            select(PostponeRequest).where(PostponeRequest.id == req_id)
        )
        req = result.scalar_one_or_none()

        if not req:
            await callback.answer("Запрос не найден!", show_alert=True)
            return

        req.status = PostponeStatus.approved
        req.resolved_at = datetime.utcnow()

        if req.completion_id:
            comp_result = await session.execute(
                select(TaskCompletion).where(TaskCompletion.id == req.completion_id)
            )
            completion = comp_result.scalar_one_or_none()
            if completion:
                tomorrow = date.today() + timedelta(days=1)
                completion.status = CompletionStatus.postponed
                completion.postponed_to = tomorrow

                new_comp = TaskCompletion(
                    task_id=completion.task_id,
                    date=tomorrow,
                    status=CompletionStatus.pending,
                )
                session.add(new_comp)

        task_result = await session.execute(
            select(Task).where(Task.id == req.task_id)
        )
        task = task_result.scalar_one_or_none()
        task_title = task.title if task else "Задача"

    from messages import postpone_approved

    try:
        from main import bot_instance
        child_users = await _get_child_ids()
        for child_id in child_users:
            await bot_instance.send_message(
                child_id,
                postpone_approved(task_title),
                parse_mode="Markdown"
            )
    except Exception:
        pass

    await callback.message.edit_text(
        f"✅ Перенос задачи «{task_title}» одобрен!",
        parse_mode="Markdown"
    )
    await callback.answer("Одобрено!")


@router.callback_query(F.data.startswith("postpone_reject_"))
async def handle_postpone_reject(callback: CallbackQuery) -> None:
    req_id = int(callback.data.split("_")[-1])

    async with get_session() as session:
        result = await session.execute(
            select(PostponeRequest).where(PostponeRequest.id == req_id)
        )
        req = result.scalar_one_or_none()

        if not req:
            await callback.answer("Запрос не найден!", show_alert=True)
            return

        req.status = PostponeStatus.rejected
        req.resolved_at = datetime.utcnow()

        task_result = await session.execute(
            select(Task).where(Task.id == req.task_id)
        )
        task = task_result.scalar_one_or_none()
        task_title = task.title if task else "Задача"

    from messages import postpone_rejected

    try:
        from main import bot_instance
        child_ids = await _get_child_ids()
        for child_id in child_ids:
            await bot_instance.send_message(
                child_id,
                postpone_rejected(task_title),
                parse_mode="Markdown"
            )
    except Exception:
        pass

    await callback.message.edit_text(
        f"❌ Перенос задачи «{task_title}» отклонён.",
        parse_mode="Markdown"
    )
    await callback.answer("Отклонено!")


@router.callback_query(F.data.startswith("reward_confirm_"))
async def handle_reward_confirm(callback: CallbackQuery) -> None:
    req_id = int(callback.data.split("_")[-1])

    async with get_session() as session:
        result = await session.execute(
            select(RewardRequest).where(RewardRequest.id == req_id)
        )
        req = result.scalar_one_or_none()

        if not req:
            await callback.answer("Запрос не найден!", show_alert=True)
            return

        req.status = RewardRequestStatus.approved
        req.resolved_at = datetime.utcnow()

        reward_result = await session.execute(
            select(Reward).where(Reward.id == req.reward_id)
        )
        reward = reward_result.scalar_one_or_none()

        if reward:
            points_result = await session.execute(
                select(Points).where(Points.telegram_id == req.telegram_id)
            )
            points_obj = points_result.scalar_one_or_none()
            if points_obj:
                points_obj.balance -= reward.cost_points

                from models import PointsHistory
                history = PointsHistory(
                    telegram_id=req.telegram_id,
                    amount=-reward.cost_points,
                    reason=f"Награда: {reward.title}",
                )
                session.add(history)

        reward_title = reward.title if reward else "Награда"

    try:
        from main import bot_instance
        await bot_instance.send_message(
            req.telegram_id,
            f"🎉 *Ура! Награда одобрена!*\n\n"
            f"🏆 *{reward_title}*\n\n"
            f"Беги к маме или папе за своей наградой! 🎁",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"✅ Награда «{reward_title}» подтверждена! Очки списаны.",
        parse_mode="Markdown"
    )
    await callback.answer("Награда выдана!")


@router.callback_query(F.data.startswith("reward_none_"))
async def handle_reward_none(callback: CallbackQuery) -> None:
    req_id = int(callback.data.split("_")[-1])

    async with get_session() as session:
        result = await session.execute(
            select(RewardRequest).where(RewardRequest.id == req_id)
        )
        req = result.scalar_one_or_none()
        if req:
            req.status = RewardRequestStatus.rejected
            req.resolved_at = datetime.utcnow()

    try:
        from main import bot_instance
        if req:
            await bot_instance.send_message(
                req.telegram_id,
                "😔 *На этой неделе без награды*\n\n"
                "Родители решили не выдавать награду на этой неделе.\n"
                "Старайся больше в следующий раз! 💪",
                parse_mode="Markdown"
            )
    except Exception:
        pass

    await callback.message.edit_text(
        "Награда за эту неделю не выдана.",
        parse_mode="Markdown"
    )
    await callback.answer()


async def _get_child_ids() -> list[int]:
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.child)
        )
        users = result.scalars().all()
        return [u.telegram_id for u in users]
