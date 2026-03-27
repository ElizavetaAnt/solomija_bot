from datetime import date, datetime, timedelta
from typing import Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, and_

from database import get_session
from keyboards import (
    child_main_menu, task_list_keyboard, postpone_time_keyboard,
    reward_list_keyboard, back_keyboard, confirm_keyboard
)
from messages import (
    task_completed, postpone_approved, task_postpone_request_to_parent
)
from models import (
    Task, TaskCompletion, CompletionStatus, Points, PointsHistory,
    RecurType, RecurTime, Reward, RewardRequest, RewardRequestStatus,
    PostponeRequest, PostponeStatus, ScheduleBlock, User, UserRole
)
from config import settings

router = Router()


class HomeworkFSM(StatesGroup):
    title = State()
    subject = State()
    deadline = State()
    add_subtasks = State()
    subtask_text = State()


class PostponeFSM(StatesGroup):
    select_task = State()
    enter_reason = State()
    confirm = State()


async def get_child_user_id(session) -> Optional[int]:
    result = await session.execute(
        select(User).where(User.role == UserRole.child)
    )
    user = result.scalar_one_or_none()
    return user.telegram_id if user else None


async def get_today_completions(session, status_filter=None):
    today = date.today()
    query = (
        select(TaskCompletion)
        .join(Task)
        .where(
            and_(
                TaskCompletion.date == today,
                Task.is_active == True,
            )
        )
    )
    if status_filter:
        query = query.where(TaskCompletion.status == status_filter)
    result = await session.execute(query)
    return result.scalars().all()


async def get_points_balance(session, telegram_id: int) -> int:
    result = await session.execute(
        select(Points).where(Points.telegram_id == telegram_id)
    )
    points = result.scalar_one_or_none()
    return points.balance if points else 0


async def add_points(session, telegram_id: int, amount: int, reason: str, task_id: Optional[int] = None) -> int:
    result = await session.execute(
        select(Points).where(Points.telegram_id == telegram_id)
    )
    points_obj = result.scalar_one_or_none()

    if not points_obj:
        points_obj = Points(telegram_id=telegram_id, balance=0)
        session.add(points_obj)

    points_obj.balance += amount

    history = PointsHistory(
        telegram_id=telegram_id,
        amount=amount,
        reason=reason,
        task_id=task_id,
    )
    session.add(history)
    await session.flush()
    return points_obj.balance


async def get_next_reward(session, balance: int) -> tuple[Optional[str], Optional[int]]:
    result = await session.execute(
        select(Reward)
        .where(Reward.is_active == True)
        .order_by(Reward.cost_points)
    )
    rewards = result.scalars().all()

    for reward in rewards:
        if reward.cost_points > balance:
            return reward.title, reward.cost_points - balance

    if rewards:
        last = rewards[-1]
        return last.title, 0

    return None, None


async def check_week_streak(session, telegram_id: int) -> bool:
    today = date.today()
    week_ago = today - timedelta(days=7)

    for i in range(7):
        check_date = week_ago + timedelta(days=i + 1)
        result = await session.execute(
            select(TaskCompletion).where(
                and_(
                    TaskCompletion.date == check_date,
                    TaskCompletion.status == CompletionStatus.pending,
                )
            )
        )
        if result.scalars().first():
            return False
    return True


@router.callback_query(F.data == "child_my_plan")
async def handle_my_plan(callback: CallbackQuery) -> None:
    today = date.today()
    weekday = today.weekday()

    async with get_session() as session:
        result = await session.execute(
            select(TaskCompletion)
            .join(Task)
            .where(
                and_(
                    TaskCompletion.date == today,
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
            tasks_map = {t.id: t for t in task_result.scalars().all()}
        else:
            tasks_map = {}

        schedule_result = await session.execute(
            select(ScheduleBlock).where(
                and_(
                    ScheduleBlock.is_active == True,
                    ScheduleBlock.day_of_week == weekday,
                )
            )
        )
        schedule_blocks = schedule_result.scalars().all()

    morning_tasks = []
    evening_tasks = []
    presleep_tasks = []

    for comp in completions:
        task = tasks_map.get(comp.task_id)
        if not task:
            continue
        status_icon = "✅" if comp.status == CompletionStatus.done else "⬜"
        label = f"{status_icon} {task.title}"

        if task.recur_time == RecurTime.morning:
            morning_tasks.append(label)
        elif task.specific_time in ("21:00",):
            presleep_tasks.append(label)
        else:
            evening_tasks.append(label)

    events_text = ""
    if schedule_blocks:
        events = [f"  📅 {b.event_name}: {b.blocked_from}–{b.blocked_to}" for b in schedule_blocks]
        events_text = "\n\n*Сегодня в расписании:*\n" + "\n".join(events)

    morning_text = "\n".join(morning_tasks) if morning_tasks else "  (нет утренних задач)"
    evening_text = "\n".join(evening_tasks) if evening_tasks else "  (нет вечерних задач)"
    presleep_text = "\n".join(presleep_tasks) if presleep_tasks else ""

    text = (
        f"📋 *Мой план на сегодня*\n\n"
        f"🌅 *Утро:*\n{morning_text}\n\n"
        f"🌙 *Вечер:*\n{evening_text}"
    )
    if presleep_text:
        text += f"\n\n😴 *Перед сном:*\n{presleep_text}"
    if events_text:
        text += events_text

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "child_my_tasks")
async def handle_my_tasks(callback: CallbackQuery) -> None:
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
            "✅ *Отлично!* Все задачи на сегодня выполнены! 🎉",
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    text = f"📝 *Задачи на сегодня* ({len(tasks)} осталось):\n\n"
    for task in tasks:
        pts = f"+{task.points}⭐" if task.points else ""
        critical = "⚠️ " if task.is_critical else ""
        text += f"{critical}• {task.title} {pts}\n"

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "child_done")
async def handle_done_list(callback: CallbackQuery) -> None:
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
            "✅ Все задачи уже выполнены! 🎉",
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "✅ *Что выполнила?*\n\nВыбери задачу:",
        reply_markup=task_list_keyboard(tasks, action="complete"),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("complete_task_"))
async def handle_complete_task(callback: CallbackQuery) -> None:
    task_id = int(callback.data.split("_")[-1])
    today = date.today()
    user_id = callback.from_user.id

    async with get_session() as session:
        result = await session.execute(
            select(TaskCompletion).where(
                and_(
                    TaskCompletion.task_id == task_id,
                    TaskCompletion.date == today,
                )
            )
        )
        completion = result.scalar_one_or_none()

        if not completion:
            await callback.answer("Задача не найдена!", show_alert=True)
            return

        if completion.status == CompletionStatus.done:
            await callback.answer("Задача уже выполнена!", show_alert=True)
            return

        completion.status = CompletionStatus.done
        completion.completed_at = datetime.utcnow()

        task_result = await session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = task_result.scalar_one_or_none()

        if not task:
            await callback.answer("Задача не найдена!", show_alert=True)
            return

        new_balance = await add_points(
            session, user_id, task.points,
            f"Выполнена задача: {task.title}", task_id
        )

        next_reward_name, points_to_next = await get_next_reward(session, new_balance)

        has_streak = await check_week_streak(session, user_id)
        streak_bonus = 0
        if has_streak:
            new_balance = await add_points(
                session, user_id, 5,
                "Бонус за 7 дней подряд! 🔥", None
            )
            streak_bonus = 5

    text = task_completed(task.title, task.points, new_balance, next_reward_name, points_to_next)
    if streak_bonus:
        text += f"\n\n🔥 *Бонус за серию 7 дней:* +5 очков!"

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer("Отлично! ✅")


@router.callback_query(F.data == "child_postpone")
async def handle_postpone_list(callback: CallbackQuery, state: FSMContext) -> None:
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
            "✅ Нет задач для переноса!",
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    await state.set_state(PostponeFSM.select_task)
    await callback.message.edit_text(
        "📅 *Перенос задачи*\n\nКакую задачу хочешь перенести?",
        reply_markup=task_list_keyboard(tasks, action="postpone_select"),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(PostponeFSM.select_task, F.data.startswith("postpone_select_task_"))
async def handle_postpone_select(callback: CallbackQuery, state: FSMContext) -> None:
    task_id = int(callback.data.split("_")[-1])
    await state.update_data(postpone_task_id=task_id)
    await state.set_state(PostponeFSM.enter_reason)

    await callback.message.edit_text(
        "💬 *Почему хочешь перенести?*\n\n"
        "Напиши причину (например: много домашки, устала, болею):",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(PostponeFSM.enter_reason)
async def handle_postpone_reason(message: Message, state: FSMContext) -> None:
    reason = message.text.strip()
    data = await state.get_data()
    task_id = data.get("postpone_task_id")
    today = date.today()
    tomorrow = today + timedelta(days=1)

    async with get_session() as session:
        task_result = await session.execute(select(Task).where(Task.id == task_id))
        task = task_result.scalar_one_or_none()

        comp_result = await session.execute(
            select(TaskCompletion).where(
                and_(
                    TaskCompletion.task_id == task_id,
                    TaskCompletion.date == today,
                )
            )
        )
        completion = comp_result.scalar_one_or_none()

        if not task or not completion:
            await message.answer("Задача не найдена!")
            await state.clear()
            return

        postpone_req = PostponeRequest(
            task_id=task_id,
            completion_id=completion.id,
            reason=reason,
            status=PostponeStatus.pending,
        )
        session.add(postpone_req)
        await session.flush()
        req_id = postpone_req.id

        task_title = task.title

    from keyboards import postpone_request_parent_keyboard

    parent_msg = task_postpone_request_to_parent(
        task_title,
        reason,
        tomorrow.strftime("%d.%m.%Y")
    )

    try:
        from main import bot_instance
        for parent_id in settings.parent_ids:
            if parent_id:
                await bot_instance.send_message(
                    parent_id,
                    parent_msg,
                    reply_markup=postpone_request_parent_keyboard(req_id),
                    parse_mode="Markdown"
                )
    except Exception as e:
        pass

    await state.clear()
    await message.answer(
        "📤 *Запрос отправлен родителям!*\n\n"
        "Жди ответа. Как только они решат — ты получишь уведомление 😊",
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "child_remind_later")
async def handle_remind_later_list(callback: CallbackQuery, state: FSMContext) -> None:
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
            "✅ Нет задач!",
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    await state.update_data(remind_tasks=[t.id for t in tasks])
    await callback.message.edit_text(
        "⏰ *Напомнить позже*\n\nВыбери задачу:",
        reply_markup=task_list_keyboard(tasks, action="remind_task"),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("remind_task_"))
async def handle_remind_task_select(callback: CallbackQuery, state: FSMContext) -> None:
    task_id = int(callback.data.split("_")[-1])
    await state.update_data(remind_task_id=task_id)

    await callback.message.edit_text(
        "⏰ *Через сколько напомнить?*",
        reply_markup=postpone_time_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.in_({"remind_30", "remind_60", "remind_120", "remind_tomorrow"}))
async def handle_remind_time(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    task_id = data.get("remind_task_id")

    delay_map = {
        "remind_30": (30, "30 минут"),
        "remind_60": (60, "1 час"),
        "remind_120": (120, "2 часа"),
        "remind_tomorrow": (None, "завтра"),
    }
    minutes, label = delay_map.get(callback.data, (30, "30 минут"))

    async with get_session() as session:
        task_result = await session.execute(select(Task).where(Task.id == task_id))
        task = task_result.scalar_one_or_none()
        task_title = task.title if task else "Задача"

    if minutes:
        remind_time = datetime.now() + timedelta(minutes=minutes)
        try:
            from scheduler import schedule_one_time_reminder
            await schedule_one_time_reminder(
                callback.from_user.id,
                task_id,
                task_title,
                remind_time
            )
        except Exception:
            pass

    await state.clear()
    await callback.message.edit_text(
        f"⏰ *Напомню через {label}!*\n\n«{task_title}»",
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


class HomeworkFSMState(StatesGroup):
    title = State()
    subject = State()
    deadline = State()
    confirm = State()


@router.callback_query(F.data == "child_add_homework")
async def handle_add_homework(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(HomeworkFSMState.title)
    await callback.message.edit_text(
        "📚 *Добавить домашнее задание*\n\n"
        "Напиши название задания:",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(HomeworkFSMState.title)
async def hw_title(message: Message, state: FSMContext) -> None:
    await state.update_data(hw_title=message.text.strip())
    await state.set_state(HomeworkFSMState.subject)
    await message.answer("📖 Какой предмет?")


@router.message(HomeworkFSMState.subject)
async def hw_subject(message: Message, state: FSMContext) -> None:
    await state.update_data(hw_subject=message.text.strip())
    await state.set_state(HomeworkFSMState.deadline)
    await message.answer(
        "📅 К какому числу сдать? (формат: ДД.ММ.ГГГГ или 'завтра')"
    )


@router.message(HomeworkFSMState.deadline)
async def hw_deadline(message: Message, state: FSMContext) -> None:
    text = message.text.strip().lower()
    deadline_date = None

    if text == "завтра":
        deadline_date = date.today() + timedelta(days=1)
    else:
        try:
            deadline_date = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await message.answer("❌ Неверный формат! Введи дату как ДД.ММ.ГГГГ или 'завтра':")
            return

    data = await state.get_data()
    title = f"ДЗ: {data['hw_subject']} — {data['hw_title']}"

    async with get_session() as session:
        task = Task(
            title=title,
            category="school",
            priority="medium",
            is_critical=False,
            is_recurring=False,
            recur_type="once",
            recur_time="evening",
            deadline=deadline_date,
            points=2,
            penalty_points=0,
            created_by=message.from_user.id,
        )
        session.add(task)
        await session.flush()

        completion = TaskCompletion(
            task_id=task.id,
            date=deadline_date,
            status=CompletionStatus.pending,
        )
        session.add(completion)

    await state.clear()
    await message.answer(
        f"✅ *Домашнее задание добавлено!*\n\n"
        f"📚 {title}\n"
        f"📅 Срок: {deadline_date.strftime('%d.%m.%Y')}\n\n"
        f"Не забудь выполнить! 💪",
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )


class ChildAddTaskFSM(StatesGroup):
    title = State()
    category = State()
    deadline = State()
    task_time = State()


@router.callback_query(F.data == "child_add_task")
async def handle_child_add_task(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ChildAddTaskFSM.title)
    await callback.message.edit_text(
        "➕ *Добавить задачу*\n\nНапиши название задачи:",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(ChildAddTaskFSM.title)
async def child_task_title(message: Message, state: FSMContext) -> None:
    await state.update_data(task_title=message.text.strip())
    await state.set_state(ChildAddTaskFSM.category)
    from keyboards import category_keyboard
    await message.answer(
        "📁 *Выбери категорию:*",
        reply_markup=category_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(ChildAddTaskFSM.category, F.data.startswith("cat_"))
async def child_task_category(callback: CallbackQuery, state: FSMContext) -> None:
    cat_map = {
        "cat_home": "home",
        "cat_school": "school",
        "cat_personal": "personal",
        "cat_weekly": "weekly",
    }
    await state.update_data(task_category=cat_map.get(callback.data, "personal"))
    await state.set_state(ChildAddTaskFSM.deadline)
    from keyboards import day_picker_keyboard
    await callback.message.edit_text(
        "📅 *Выбери день:*",
        reply_markup=day_picker_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(ChildAddTaskFSM.deadline, F.data.startswith("day_"))
async def child_task_deadline(callback: CallbackQuery, state: FSMContext) -> None:
    day_str = callback.data.replace("day_", "")
    await state.update_data(task_deadline=day_str)
    await state.set_state(ChildAddTaskFSM.task_time)
    from keyboards import time_picker_keyboard
    await callback.message.edit_text(
        "🕐 *Выбери время:*",
        reply_markup=time_picker_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(ChildAddTaskFSM.task_time, F.data.startswith("time_"))
async def child_task_time(callback: CallbackQuery, state: FSMContext) -> None:
    time_str = callback.data.replace("time_", "")
    data = await state.get_data()
    deadline_date = date.fromisoformat(data["task_deadline"])

    async with get_session() as session:
        task = Task(
            title=data["task_title"],
            category=data.get("task_category", "personal"),
            priority="medium",
            is_critical=False,
            is_recurring=False,
            recur_type="once",
            recur_time="evening",
            deadline=deadline_date,
            specific_time=time_str,
            points=2,
            penalty_points=0,
            created_by=callback.from_user.id,
        )
        session.add(task)
        await session.flush()

        completion = TaskCompletion(
            task_id=task.id,
            date=deadline_date,
            status=CompletionStatus.pending,
        )
        session.add(completion)

    await state.clear()
    await callback.message.edit_text(
        f"✅ *Задача добавлена!*\n\n"
        f"📌 {data['task_title']}\n"
        f"📅 {deadline_date.strftime('%d.%m.%Y')} в {time_str}\n\n"
        f"Удачи! 💪",
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "child_my_reward")
async def handle_my_reward(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id

    async with get_session() as session:
        balance = await get_points_balance(session, user_id)

        result = await session.execute(
            select(Reward)
            .where(Reward.is_active == True)
            .order_by(Reward.cost_points)
        )
        rewards = result.scalars().all()

    text = f"🏆 *Моя награда*\n\n💰 Баланс: *{balance} очков*\n\n*Доступные награды:*\n"

    available = []
    not_yet = []

    for reward in rewards:
        icon = "✅" if reward.cost_points <= balance else "🔒"
        line = f"{icon} *{reward.title}* — {reward.cost_points} очков"
        if reward.max_price:
            line += f" (до {reward.max_price}₽)"
        if reward.cost_points <= balance:
            available.append(line)
        else:
            not_yet.append(f"{line} (ещё {reward.cost_points - balance} очков)")

    if available:
        text += "\n*Можно получить уже сейчас:*\n"
        text += "\n".join(available) + "\n"

    if not_yet:
        text += "\n*Накопи ещё:*\n"
        text += "\n".join(not_yet[:3])

    if available:
        text += "\n\n💌 Покажи маме или папе, чтобы получить награду!"

    await callback.message.edit_text(
        text,
        reply_markup=reward_list_keyboard([r for r in rewards if r.cost_points <= balance]) if available else back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("select_reward_"))
async def handle_select_reward(callback: CallbackQuery) -> None:
    reward_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    async with get_session() as session:
        balance = await get_points_balance(session, user_id)

        reward_result = await session.execute(
            select(Reward).where(Reward.id == reward_id)
        )
        reward = reward_result.scalar_one_or_none()

        if not reward:
            await callback.answer("Награда не найдена!", show_alert=True)
            return

        if reward.cost_points > balance:
            await callback.answer(
                f"Не хватает {reward.cost_points - balance} очков!",
                show_alert=True
            )
            return

        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        existing = await session.execute(
            select(RewardRequest).where(
                and_(
                    RewardRequest.telegram_id == user_id,
                    RewardRequest.status == RewardRequestStatus.pending,
                    RewardRequest.week_start == week_start,
                )
            )
        )
        if existing.scalar_one_or_none():
            await callback.answer(
                "Запрос на эту неделю уже отправлен!",
                show_alert=True
            )
            return

        req = RewardRequest(
            reward_id=reward_id,
            telegram_id=user_id,
            status=RewardRequestStatus.pending,
            week_start=week_start,
        )
        session.add(req)
        await session.flush()
        req_id = req.id

    from messages import reward_suggestion_parent
    from keyboards import reward_confirm_keyboard

    parent_msg = reward_suggestion_parent(reward.title, reward.cost_points, balance)

    try:
        from main import bot_instance
        for parent_id in settings.parent_ids:
            if parent_id:
                await bot_instance.send_message(
                    parent_id,
                    parent_msg,
                    reply_markup=reward_confirm_keyboard(req_id),
                    parse_mode="Markdown"
                )
    except Exception:
        pass

    await callback.message.edit_text(
        f"🎁 *Запрос на награду отправлен!*\n\n"
        f"«{reward.title}» — запрос ушёл родителям.\n"
        f"Жди подтверждения! 🤞",
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()
