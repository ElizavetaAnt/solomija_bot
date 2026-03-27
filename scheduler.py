import asyncio
import logging
import random
from datetime import date, datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select, and_

from config import settings
from database import get_session
from models import (
    Task, TaskCompletion, CompletionStatus, Points, PointsHistory,
    RecurType, ScheduleBlock, BotSettings, User, UserRole,
    Reward, RewardRequest, RewardRequestStatus
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
_bot = None


def set_bot(bot_instance):
    global _bot
    _bot = bot_instance


async def get_setting(session, key: str, default: str = "") -> str:
    result = await session.execute(
        select(BotSettings).where(BotSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else default


async def get_child_telegram_ids(session) -> list[int]:
    result = await session.execute(
        select(User).where(User.role == UserRole.child, User.is_active == True)
    )
    users = result.scalars().all()
    return [u.telegram_id for u in users]


async def get_parent_telegram_ids(session) -> list[int]:
    result = await session.execute(
        select(User).where(User.role == UserRole.parent, User.is_active == True)
    )
    users = result.scalars().all()
    return [u.telegram_id for u in users]


def get_today_weekday() -> int:
    return date.today().weekday()


async def get_today_tasks(session, recur_type_filter: Optional[str] = None) -> list[Task]:
    today = date.today()
    weekday = today.weekday()

    query = select(Task).where(Task.is_active == True)
    result = await session.execute(query)
    all_tasks = result.scalars().all()

    today_tasks = []
    for task in all_tasks:
        if not task.is_recurring:
            if task.deadline == today:
                today_tasks.append(task)
            continue

        recur = task.recur_type.value if hasattr(task.recur_type, 'value') else str(task.recur_type)

        if recur == RecurType.daily.value:
            today_tasks.append(task)
        elif recur == RecurType.weekday.value:
            if weekday < 5:
                today_tasks.append(task)
        elif recur == RecurType.weekly.value:
            if weekday == 4:  # Only Fridays
                today_tasks.append(task)
        elif recur == RecurType.once.value:
            if task.deadline == today:
                today_tasks.append(task)

    if recur_type_filter:
        today_tasks = [
            t for t in today_tasks
            if (t.recur_time.value if hasattr(t.recur_time, 'value') else str(t.recur_time)) == recur_type_filter
        ]

    return today_tasks


async def get_week_stats(session, week_start: date, week_end: date) -> dict:
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
        return {"total": 0, "done": 0, "percent": 0, "points": 0,
                "by_category": {}, "done_list": [], "failed_list": [],
                "critical_missed": [], "achievements": []}

    task_ids = [c.task_id for c in completions]
    task_result = await session.execute(select(Task).where(Task.id.in_(task_ids)))
    tasks_map = {t.id: t for t in task_result.scalars().all()}

    total = len(completions)
    done = sum(1 for c in completions if c.status == CompletionStatus.done)
    percent = int(done / total * 100) if total > 0 else 0
    points_earned = sum(
        tasks_map[c.task_id].points
        for c in completions
        if c.status == CompletionStatus.done and c.task_id in tasks_map
    )

    by_category: dict[str, list] = {}
    done_list, failed_list, critical_missed = [], [], []

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
        else:
            failed_list.append(task.title)
            if task.is_critical:
                critical_missed.append(task.title)

    achievements = []
    if percent == 100:
        achievements.append("Все задачи выполнены! 🌟")
    if not critical_missed:
        achievements.append("Ни одной критической задачи не пропущено 💪")

    return {
        "total": total, "done": done, "percent": percent, "points": points_earned,
        "by_category": {k: tuple(v) for k, v in by_category.items()},
        "done_list": done_list, "failed_list": failed_list,
        "critical_missed": critical_missed, "achievements": achievements,
    }


def calculate_reward_level(percent: int) -> str:
    if percent >= 85:
        return "big"
    elif percent >= 60:
        return "medium"
    return "none"


async def is_blocked_time(session, now: datetime) -> bool:
    weekday = now.weekday()
    time_str = now.strftime("%H:%M")

    result = await session.execute(
        select(ScheduleBlock).where(
            and_(
                ScheduleBlock.is_active == True,
                ScheduleBlock.day_of_week == weekday,
            )
        )
    )
    blocks = result.scalars().all()

    for block in blocks:
        if block.blocked_from <= time_str <= block.blocked_to:
            return True
    return False


async def create_day_completions(session, target_date: date) -> int:
    weekday = target_date.weekday()
    result = await session.execute(select(Task).where(Task.is_active == True))
    all_tasks = result.scalars().all()

    created = 0
    for task in all_tasks:
        if not task.is_recurring:
            if task.deadline == target_date:
                existing = await session.execute(
                    select(TaskCompletion).where(
                        and_(TaskCompletion.task_id == task.id, TaskCompletion.date == target_date)
                    )
                )
                if not existing.scalar_one_or_none():
                    session.add(TaskCompletion(
                        task_id=task.id, date=target_date, status=CompletionStatus.pending
                    ))
                    created += 1
            continue

        recur = task.recur_type.value if hasattr(task.recur_type, 'value') else str(task.recur_type)
        should_create = False

        if recur == RecurType.daily.value:
            should_create = True
        elif recur == RecurType.weekday.value:
            should_create = weekday < 5
        elif recur == RecurType.weekly.value:
            # Grandma tasks are handled separately by plan_grandma_visits()
            if task.title in ("Навестить прабабушку", "Купить сладость для прабабушки"):
                continue

        # School prep tasks only Mon-Thu (no point preparing for weekend)
        if task.title in ("Подготовить одежду на завтра", "Проверить ланч-бокс и посуду") and weekday >= 4:
            continue
            # Other weekly tasks only on Fridays, once per week
            if weekday == 4:
                week_start = target_date - timedelta(days=target_date.weekday())
                week_end = week_start + timedelta(days=6)
                existing_week = await session.execute(
                    select(TaskCompletion).where(
                        and_(
                            TaskCompletion.task_id == task.id,
                            TaskCompletion.date >= week_start,
                            TaskCompletion.date <= week_end,
                        )
                    )
                )
                if not existing_week.scalar_one_or_none():
                    should_create = True
        elif recur == RecurType.once.value:
            should_create = task.deadline == target_date

        if should_create:
            existing = await session.execute(
                select(TaskCompletion).where(
                    and_(TaskCompletion.task_id == task.id, TaskCompletion.date == target_date)
                )
            )
            if not existing.scalar_one_or_none():
                session.add(TaskCompletion(
                    task_id=task.id, date=target_date, status=CompletionStatus.pending
                ))
                created += 1

    return created


GRANDMA_TASKS = ["Навестить прабабушку", "Купить сладость для прабабушки"]


async def plan_grandma_visits(session, week_monday: date):
    """Randomly picks Tuesday or Sunday for grandma visit this week."""
    offset = random.choice([1, 6])  # 1=Tuesday, 6=Sunday
    visit_date = week_monday + timedelta(days=offset)
    week_end = week_monday + timedelta(days=6)

    result = await session.execute(
        select(Task).where(and_(Task.is_active == True, Task.title.in_(GRANDMA_TASKS)))
    )
    tasks = result.scalars().all()

    for task in tasks:
        existing = await session.execute(
            select(TaskCompletion).where(
                and_(
                    TaskCompletion.task_id == task.id,
                    TaskCompletion.date >= week_monday,
                    TaskCompletion.date <= week_end,
                )
            )
        )
        if not existing.scalar_one_or_none():
            session.add(TaskCompletion(
                task_id=task.id,
                date=visit_date,
                status=CompletionStatus.pending,
            ))

    logger.info(f"Grandma visit planned for {visit_date} ({'Tuesday' if offset == 1 else 'Sunday'})")
    return visit_date


async def grandma_reminder_job():
    """Sends morning reminder on grandma visit day."""
    if not _bot:
        return
    try:
        today = date.today()
        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)
            parent_ids = await get_parent_telegram_ids(session)

            result = await session.execute(
                select(Task).where(and_(Task.is_active == True, Task.title.in_(GRANDMA_TASKS)))
            )
            tasks = result.scalars().all()

            has_visit_today = False
            for task in tasks:
                comp = await session.execute(
                    select(TaskCompletion).where(
                        and_(TaskCompletion.task_id == task.id, TaskCompletion.date == today)
                    )
                )
                if comp.scalar_one_or_none():
                    has_visit_today = True
                    break

        if not has_visit_today:
            return

        child_text = (
            "👵 *Сегодня день Вали!*\n\n"
            "Не забудь навестить прабабушку и взять ей сладость! 🍬\n\n"
            "Она всегда так рада тебя видеть! ❤️"
        )
        parent_text = "📣 Напоминание: сегодня Соломия должна навестить прабабушку Валю 👵"

        for child_id in child_ids:
            try:
                await _bot.send_message(child_id, child_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send grandma reminder to child: {e}")

        for parent_id in parent_ids:
            try:
                await _bot.send_message(parent_id, parent_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send grandma reminder to parent: {e}")

    except Exception as e:
        logger.error(f"grandma_reminder_job error: {e}")


async def midnight_job():
    logger.info("Running midnight_job")
    try:
        tomorrow = date.today() + timedelta(days=1)
        async with get_session() as session:
            count = await create_day_completions(session, tomorrow)
            logger.info(f"Created {count} completions for {tomorrow}")

            # Every Monday — plan grandma visit for the week (Tue or Sun randomly)
            if tomorrow.weekday() == 0:  # tomorrow is Monday
                week_monday = tomorrow
                await plan_grandma_visits(session, week_monday)
    except Exception as e:
        logger.error(f"midnight_job error: {e}")


async def morning_notification_job():
    logger.info("Running morning_notification_job")
    if not _bot:
        return
    try:
        today = date.today()
        weekday = today.weekday()

        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)
            morning_tasks = await get_today_tasks(session, "morning")

            schedule_result = await session.execute(
                select(ScheduleBlock).where(
                    and_(ScheduleBlock.is_active == True, ScheduleBlock.day_of_week == weekday)
                )
            )
            blocks = schedule_result.scalars().all()

        from messages import morning_greeting
        has_event = len(blocks) > 0
        event_name = blocks[0].event_name if has_event else ""
        event_time = blocks[0].blocked_from if has_event else ""
        task_titles = [t.title for t in morning_tasks]
        text = morning_greeting(task_titles, has_event, event_name, event_time)

        for child_id in child_ids:
            try:
                await _bot.send_message(child_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send morning msg to {child_id}: {e}")
    except Exception as e:
        logger.error(f"morning_notification_job error: {e}")


async def after_school_job():
    logger.info("Running after_school_job")
    if not _bot:
        return
    today = date.today()
    if today.weekday() >= 5:
        return
    try:
        weekday = today.weekday()
        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)
            evening_tasks = await get_today_tasks(session, "evening")

            schedule_result = await session.execute(
                select(ScheduleBlock).where(
                    and_(ScheduleBlock.is_active == True, ScheduleBlock.day_of_week == weekday)
                )
            )
            blocks = schedule_result.scalars().all()

        evening_blocks = [b for b in blocks if b.blocked_from >= "17:00"]
        from messages import after_school_greeting
        has_event = len(evening_blocks) > 0
        event_name = evening_blocks[0].event_name if has_event else ""
        event_time = evening_blocks[0].blocked_from if has_event else ""
        task_titles = [t.title for t in evening_tasks]
        text = after_school_greeting(task_titles, has_event, event_name, event_time)

        for child_id in child_ids:
            try:
                await _bot.send_message(child_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send after-school msg to {child_id}: {e}")
    except Exception as e:
        logger.error(f"after_school_job error: {e}")


async def evening_checkin_job():
    logger.info("Running evening_checkin_job")
    if not _bot:
        return
    try:
        today = date.today()
        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)

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
                task_result = await session.execute(select(Task).where(Task.id.in_(task_ids)))
                tasks = task_result.scalars().all()
                pending = [t.title for t in tasks]
            else:
                pending = []

        from messages import evening_checkin
        text = evening_checkin(pending)

        for child_id in child_ids:
            try:
                await _bot.send_message(child_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send evening checkin to {child_id}: {e}")
    except Exception as e:
        logger.error(f"evening_checkin_job error: {e}")


async def sleep_reminder_job():
    logger.info("Running sleep_reminder_job")
    if not _bot:
        return
    try:
        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)

        from messages import sleep_reminder
        text = sleep_reminder()

        for child_id in child_ids:
            try:
                await _bot.send_message(child_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send sleep reminder to {child_id}: {e}")
    except Exception as e:
        logger.error(f"sleep_reminder_job error: {e}")


async def critical_task_check_job():
    logger.info("Running critical_task_check_job")
    if not _bot:
        return
    try:
        today = date.today()
        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)
            parent_ids = await get_parent_telegram_ids(session)

            result = await session.execute(
                select(TaskCompletion)
                .join(Task)
                .where(
                    and_(
                        TaskCompletion.date == today,
                        TaskCompletion.status == CompletionStatus.pending,
                        Task.is_active == True,
                        Task.is_critical == True,
                    )
                )
            )
            completions = result.scalars().all()

            if not completions:
                return

            task_ids = [c.task_id for c in completions]
            task_result = await session.execute(select(Task).where(Task.id.in_(task_ids)))
            tasks = task_result.scalars().all()

            for task in tasks:
                comp = next((c for c in completions if c.task_id == task.id), None)
                if comp:
                    comp.status = CompletionStatus.skipped

                for child_id in child_ids:
                    pts_result = await session.execute(
                        select(Points).where(Points.telegram_id == child_id)
                    )
                    pts = pts_result.scalar_one_or_none()
                    if pts:
                        pts.balance -= task.penalty_points
                        history = PointsHistory(
                            telegram_id=child_id,
                            amount=-task.penalty_points,
                            reason=f"Критическая задача не выполнена: {task.title}",
                            task_id=task.id,
                        )
                        session.add(history)

        from messages import critical_task_missed_child, critical_task_missed_parent

        for task in tasks:
            child_text = critical_task_missed_child(task.title)
            parent_text = critical_task_missed_parent(task.title, today.strftime("%d.%m.%Y"))

            for child_id in child_ids:
                try:
                    await _bot.send_message(child_id, child_text, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Failed to notify child {child_id}: {e}")

            for parent_id in parent_ids:
                try:
                    await _bot.send_message(parent_id, parent_text, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Failed to notify parent {parent_id}: {e}")

    except Exception as e:
        logger.error(f"critical_task_check_job error: {e}")


async def daily_report_job():
    logger.info("Running daily_report_job")
    if not _bot:
        return
    try:
        today = date.today()
        async with get_session() as session:
            parent_ids = await get_parent_telegram_ids(session)

            result = await session.execute(
                select(TaskCompletion)
                .join(Task)
                .where(
                    and_(TaskCompletion.date == today, Task.is_active == True)
                )
            )
            completions = result.scalars().all()

            task_ids = [c.task_id for c in completions]
            tasks_map = {}
            if task_ids:
                task_result = await session.execute(select(Task).where(Task.id.in_(task_ids)))
                tasks_map = {t.id: t for t in task_result.scalars().all()}

        total = len(completions)
        done = sum(1 for c in completions if c.status == CompletionStatus.done)
        percent = int(done / total * 100) if total > 0 else 0
        done_list = [tasks_map[c.task_id].title for c in completions
                     if c.status == CompletionStatus.done and c.task_id in tasks_map]
        failed_list = [tasks_map[c.task_id].title for c in completions
                       if c.status != CompletionStatus.done and c.task_id in tasks_map]
        critical_missed = [tasks_map[c.task_id].title for c in completions
                           if c.status != CompletionStatus.done
                           and c.task_id in tasks_map
                           and tasks_map[c.task_id].is_critical]
        points_earned = sum(
            tasks_map[c.task_id].points for c in completions
            if c.status == CompletionStatus.done and c.task_id in tasks_map
        )

        from messages import daily_report_parent
        text = daily_report_parent(
            date_str=today.strftime("%d.%m.%Y"),
            completed=done,
            total=total,
            percent=percent,
            done_list=done_list,
            failed_list=failed_list,
            critical_missed=critical_missed,
            points_earned=points_earned,
        )

        for parent_id in parent_ids:
            try:
                await _bot.send_message(parent_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send daily report to {parent_id}: {e}")
    except Exception as e:
        logger.error(f"daily_report_job error: {e}")


async def weekly_tasks_reminder_job():
    logger.info("Running weekly_tasks_reminder_job")
    if not _bot:
        return
    try:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)

            result = await session.execute(
                select(TaskCompletion)
                .join(Task)
                .where(
                    and_(
                        TaskCompletion.date.between(week_start, week_end),
                        TaskCompletion.status == CompletionStatus.pending,
                        Task.recur_type == RecurType.weekly,
                        Task.is_active == True,
                    )
                )
            )
            completions = result.scalars().all()
            task_ids = [c.task_id for c in completions]

            if task_ids:
                task_result = await session.execute(select(Task).where(Task.id.in_(task_ids)))
                tasks = task_result.scalars().all()
                task_titles = [t.title for t in tasks]
            else:
                task_titles = []

        if not task_titles:
            return

        text = (
            "📅 *Напоминание о еженедельных задачах!*\n\n"
            "Эту неделю ещё не выполнены:\n\n"
            + "\n".join([f"  • {t}" for t in task_titles])
            + "\n\nОсталось до воскресенья! Успевай! 💪"
        )

        for child_id in child_ids:
            try:
                await _bot.send_message(child_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send weekly reminder to {child_id}: {e}")
    except Exception as e:
        logger.error(f"weekly_tasks_reminder_job error: {e}")


async def child_weekly_report_job():
    logger.info("Running child_weekly_report_job")
    if not _bot:
        return
    try:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = today

        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)
            stats = await get_week_stats(session, week_start, week_end)

        percent = stats["percent"]
        from messages import (
            child_weekly_report_good,
            child_weekly_report_medium,
            child_weekly_report_low
        )

        if percent >= 85:
            text = child_weekly_report_good(
                percent, stats["done"], stats["total"],
                stats["points"], stats["achievements"]
            )
        elif percent >= 60:
            text = child_weekly_report_medium(
                percent, stats["done"], stats["total"],
                stats["points"], stats["failed_list"][:3]
            )
        else:
            text = child_weekly_report_low(
                percent, stats["done"], stats["total"], stats["points"]
            )

        for child_id in child_ids:
            try:
                await _bot.send_message(child_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send child weekly report to {child_id}: {e}")
    except Exception as e:
        logger.error(f"child_weekly_report_job error: {e}")


async def parent_weekly_report_job():
    logger.info("Running parent_weekly_report_job")
    if not _bot:
        return
    try:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = today

        async with get_session() as session:
            parent_ids = await get_parent_telegram_ids(session)
            stats = await get_week_stats(session, week_start, week_end)

            child_points_result = await session.execute(select(Points))
            child_pts = child_points_result.scalars().first()
            balance = child_pts.balance if child_pts else 0

            reward_result = await session.execute(
                select(Reward)
                .where(and_(Reward.is_active == True, Reward.cost_points <= balance))
                .order_by(Reward.cost_points.desc())
            )
            top_reward = reward_result.scalars().first()

        percent = stats["percent"]
        reward_level = calculate_reward_level(percent)
        week_str = f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}"

        from messages import weekly_report_parent, reward_suggestion_parent
        from keyboards import reward_confirm_keyboard

        report_text = weekly_report_parent(
            week_str=week_str,
            percent=percent,
            by_category=stats["by_category"],
            achievements=stats["achievements"],
            failed=stats["failed_list"][:5],
            points=stats["points"],
            reward_level=reward_level,
        )

        for parent_id in parent_ids:
            try:
                await _bot.send_message(parent_id, report_text, parse_mode="Markdown")

                if top_reward and reward_level != "none":
                    suggestion = reward_suggestion_parent(
                        top_reward.title, top_reward.cost_points, balance
                    )
                    async with get_session() as session2:
                        req_result = await session2.execute(
                            select(RewardRequest)
                            .where(RewardRequest.status == RewardRequestStatus.pending)
                            .order_by(RewardRequest.requested_at.desc())
                        )
                        pending_req = req_result.scalars().first()

                    if pending_req:
                        await _bot.send_message(
                            parent_id, suggestion,
                            reply_markup=reward_confirm_keyboard(pending_req.id),
                            parse_mode="Markdown"
                        )
                    else:
                        await _bot.send_message(parent_id, suggestion, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send parent weekly report to {parent_id}: {e}")
    except Exception as e:
        logger.error(f"parent_weekly_report_job error: {e}")


async def tomorrow_plan_job():
    """Evening notification: tomorrow's plan for child and parents."""
    logger.info("Running tomorrow_plan_job")
    if not _bot:
        return
    try:
        tomorrow = date.today() + timedelta(days=1)
        weekday = tomorrow.weekday()
        days_ru = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]

        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)
            parent_ids = await get_parent_telegram_ids(session)

            result = await session.execute(
                select(TaskCompletion)
                .join(Task)
                .where(
                    and_(
                        TaskCompletion.date == tomorrow,
                        Task.is_active == True,
                    )
                )
            )
            completions = result.scalars().all()
            task_ids = [c.task_id for c in completions]

            tasks_map = {}
            if task_ids:
                task_result = await session.execute(select(Task).where(Task.id.in_(task_ids)))
                tasks_map = {t.id: t for t in task_result.scalars().all()}

            schedule_result = await session.execute(
                select(ScheduleBlock).where(
                    and_(ScheduleBlock.is_active == True, ScheduleBlock.day_of_week == weekday)
                )
            )
            blocks = schedule_result.scalars().all()

        task_lines = []
        for comp in completions:
            task = tasks_map.get(comp.task_id)
            if task:
                time_str = f" в {task.specific_time}" if task.specific_time else ""
                task_lines.append(f"• {task.title}{time_str} (+{task.points}⭐)")

        child_text = (
            f"🌙 *План на завтра — {days_ru[weekday]}:*\n\n"
            + ("\n".join(task_lines) if task_lines else "(задач нет)")
        )
        if blocks:
            child_text += "\n\n*Расписание:*\n"
            child_text += "\n".join([f"📅 {b.event_name}: {b.blocked_from}–{b.blocked_to}" for b in blocks])
        child_text += "\n\nГотовься заранее! 💪"

        parent_text = (
            f"📋 *План Соломии на завтра — {days_ru[weekday]}:*\n\n"
            + ("\n".join(task_lines) if task_lines else "(задач нет)")
        )
        if blocks:
            parent_text += "\n\n*Расписание:*\n"
            parent_text += "\n".join([f"📅 {b.event_name}: {b.blocked_from}–{b.blocked_to}" for b in blocks])

        for child_id in child_ids:
            try:
                await _bot.send_message(child_id, child_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send tomorrow plan to child {child_id}: {e}")

        for parent_id in parent_ids:
            try:
                await _bot.send_message(parent_id, parent_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send tomorrow plan to parent {parent_id}: {e}")

    except Exception as e:
        logger.error(f"tomorrow_plan_job error: {e}")


async def event_reminder_job():
    logger.info("Running event_reminder_job")
    if not _bot:
        return
    try:
        now = datetime.now(tz=scheduler.timezone)
        in_15 = (now + timedelta(minutes=30)).strftime("%H:%M")
        weekday = now.weekday()

        async with get_session() as session:
            child_ids = await get_child_telegram_ids(session)
            parent_ids = await get_parent_telegram_ids(session)

            result = await session.execute(
                select(ScheduleBlock).where(
                    and_(
                        ScheduleBlock.is_active == True,
                        ScheduleBlock.day_of_week == weekday,
                        ScheduleBlock.blocked_from == in_15,
                    )
                )
            )
            upcoming = result.scalars().all()

        for block in upcoming:
            child_text = (
                f"⏰ *Через 30 минут — {block.event_name}!*\n\n"
                f"🕐 Начало в {block.blocked_from}\n\n"
                f"Пора готовиться! 💪"
            )
            parent_text = (
                f"📣 Соломия получила напоминание:\n\n"
                f"*{block.event_name}* начинается в {block.blocked_from} (через 30 минут)"
            )

            for child_id in child_ids:
                try:
                    await _bot.send_message(child_id, child_text, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Failed to send event reminder to child {child_id}: {e}")

            for parent_id in parent_ids:
                try:
                    await _bot.send_message(parent_id, parent_text, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Failed to send event notify to parent {parent_id}: {e}")

    except Exception as e:
        logger.error(f"event_reminder_job error: {e}")


async def schedule_one_time_reminder(user_id: int, task_id: int, task_title: str, remind_at: datetime):
    if not _bot:
        return

    async def _send_reminder():
        try:
            from keyboards import back_keyboard
            await _bot.send_message(
                user_id,
                f"⏰ *Напоминание!*\n\n«{task_title}» — пора выполнить! 💪",
                reply_markup=back_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send one-time reminder: {e}")

    scheduler.add_job(
        _send_reminder,
        trigger=DateTrigger(run_date=remind_at),
        id=f"reminder_{user_id}_{task_id}_{remind_at.timestamp()}",
        replace_existing=False,
    )


def setup_scheduler(morning_hour: int = 7, morning_minute: int = 30):
    scheduler.add_job(
        midnight_job,
        CronTrigger(hour=0, minute=1),
        id="midnight_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        morning_notification_job,
        CronTrigger(hour=morning_hour, minute=morning_minute),
        id="morning_notification_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        after_school_job,
        CronTrigger(hour=17, minute=15, day_of_week="mon-fri"),
        id="after_school_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        evening_checkin_job,
        CronTrigger(hour=21, minute=30),
        id="evening_checkin_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        critical_task_check_job,
        CronTrigger(hour=21, minute=30),
        id="critical_task_check_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        sleep_reminder_job,
        CronTrigger(hour=22, minute=30),
        id="sleep_reminder_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        daily_report_job,
        CronTrigger(hour=22, minute=0),
        id="daily_report_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        weekly_tasks_reminder_job,
        CronTrigger(hour=17, minute=30, day_of_week="fri"),
        id="weekly_tasks_reminder_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        child_weekly_report_job,
        CronTrigger(hour=20, minute=0, day_of_week="sun"),
        id="child_weekly_report_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        parent_weekly_report_job,
        CronTrigger(hour=21, minute=0, day_of_week="sun"),
        id="parent_weekly_report_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        event_reminder_job,
        CronTrigger(minute="*/15"),
        id="event_reminder_job",
        replace_existing=True,
        misfire_grace_time=60,
    )

    scheduler.add_job(
        tomorrow_plan_job,
        CronTrigger(hour=20, minute=0),
        id="tomorrow_plan_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        grandma_reminder_job,
        CronTrigger(hour=10, minute=0, day_of_week="tue,sun"),
        id="grandma_reminder_job",
        replace_existing=True,
        misfire_grace_time=300,
    )

    logger.info("Scheduler jobs configured.")
