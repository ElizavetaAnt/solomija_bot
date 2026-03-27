from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import (
    Task, TaskCategory, TaskPriority, RecurType, RecurTime,
    ScheduleBlock, Reward, RewardType, BotSettings
)


async def is_initialized(session: AsyncSession) -> bool:
    result = await session.execute(
        select(BotSettings).where(BotSettings.key == "initialized")
    )
    setting = result.scalar_one_or_none()
    return setting is not None


async def populate_initial_data(session: AsyncSession) -> None:
    if await is_initialized(session):
        return

    # ===== RECURRING TASKS =====

    daily_tasks = [
        Task(
            title="Корм Марсу и Масяне (утро)",
            category=TaskCategory.home,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.morning,
            points=2,
            penalty_points=0,
        ),
        Task(
            title="Вода Марсу и Масяне (утро)",
            category=TaskCategory.home,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.morning,
            points=2,
            penalty_points=0,
        ),
        Task(
            title="Смена пелёнки Соле (утро)",
            category=TaskCategory.home,
            priority=TaskPriority.high,
            is_critical=True,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.morning,
            points=3,
            penalty_points=2,
        ),
        Task(
            title="Корм Марсу и Масяне (вечер)",
            category=TaskCategory.home,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.evening,
            points=2,
            penalty_points=0,
        ),
        Task(
            title="Вода Марсу и Масяне (вечер)",
            category=TaskCategory.home,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.evening,
            points=2,
            penalty_points=0,
        ),
        Task(
            title="Смена пелёнки Соле (вечер)",
            category=TaskCategory.home,
            priority=TaskPriority.high,
            is_critical=True,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.evening,
            points=3,
            penalty_points=2,
        ),
        Task(
            title="Чтение (30 мин)",
            category=TaskCategory.personal,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.evening,
            points=5,
            penalty_points=0,
        ),
        Task(
            title="Рисование (1 час)",
            category=TaskCategory.personal,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.evening,
            points=2,
            penalty_points=0,
        ),
        Task(
            title="Подготовить одежду на завтра",
            category=TaskCategory.home,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.evening,
            specific_time="21:00",
            points=2,
            penalty_points=0,
        ),
        Task(
            title="Проверить ланч-бокс и посуду",
            category=TaskCategory.home,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.daily,
            recur_time=RecurTime.evening,
            specific_time="21:00",
            points=5,
            penalty_points=0,
        ),
    ]

    weekday_tasks = [
        Task(
            title="Чтение перед сном",
            category=TaskCategory.personal,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.weekday,
            recur_time=RecurTime.evening,
            points=5,
            penalty_points=0,
        ),
    ]

    weekly_tasks = [
        Task(
            title="Навестить прабабушку",
            category=TaskCategory.personal,
            priority=TaskPriority.high,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.weekly,
            recur_time=RecurTime.specific,
            points=5,
            penalty_points=0,
        ),
        Task(
            title="Купить сладость для прабабушки",
            category=TaskCategory.home,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.weekly,
            recur_time=RecurTime.specific,
            points=2,
            penalty_points=0,
        ),
        Task(
            title="Написать бабушке Лене и дедушке Коле",
            category=TaskCategory.personal,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.weekly,
            recur_time=RecurTime.specific,
            points=3,
            penalty_points=0,
        ),
        Task(
            title="Написать бабушке Марине и дедушке Анатолию",
            category=TaskCategory.personal,
            priority=TaskPriority.medium,
            is_critical=False,
            is_recurring=True,
            recur_type=RecurType.weekly,
            recur_time=RecurTime.specific,
            points=3,
            penalty_points=0,
        ),
    ]

    for task in daily_tasks + weekday_tasks + weekly_tasks:
        session.add(task)

    # ===== SCHEDULE BLOCKS =====

    schedule_blocks = [
        ScheduleBlock(day_of_week=0, blocked_from="09:00", blocked_to="17:00", event_name="Школа"),
        ScheduleBlock(day_of_week=1, blocked_from="09:00", blocked_to="17:00", event_name="Школа"),
        ScheduleBlock(day_of_week=2, blocked_from="09:00", blocked_to="17:00", event_name="Школа"),
        ScheduleBlock(day_of_week=3, blocked_from="09:00", blocked_to="17:00", event_name="Школа"),
        ScheduleBlock(day_of_week=4, blocked_from="09:00", blocked_to="17:00", event_name="Школа"),
        ScheduleBlock(day_of_week=0, blocked_from="19:30", blocked_to="21:00", event_name="Танцы"),
        ScheduleBlock(day_of_week=2, blocked_from="19:30", blocked_to="21:00", event_name="Танцы"),
        ScheduleBlock(day_of_week=5, blocked_from="12:00", blocked_to="14:00", event_name="Цирк"),
        ScheduleBlock(day_of_week=3, blocked_from="19:30", blocked_to="21:00", event_name="Лекция"),
        ScheduleBlock(day_of_week=6, blocked_from="11:00", blocked_to="13:00", event_name="Лекция"),
    ]

    for block in schedule_blocks:
        session.add(block)

    # ===== REWARDS =====

    rewards = [
        Reward(
            title="Вкусняшки на выбор",
            description="Выбираешь любую вкусняшку на свой вкус",
            cost_points=15,
            reward_type=RewardType.real,
        ),
        Reward(
            title="Выбирает фильм для семьи",
            description="Ты выбираешь фильм, который смотрим всей семьёй",
            cost_points=20,
            reward_type=RewardType.real,
        ),
        Reward(
            title="Заказ на Wildberries/Ozon до 500₽",
            description="Можешь заказать любую вещь на Wildberries или Ozon",
            cost_points=40,
            reward_type=RewardType.real,
            max_price=500,
        ),
        Reward(
            title="Дополнительный час телефона",
            description="+1 час экранного времени в любой день",
            cost_points=10,
            reward_type=RewardType.virtual,
        ),
        Reward(
            title="Стикер Супергерой недели",
            description="Получаешь титул Супергероя недели!",
            cost_points=5,
            reward_type=RewardType.virtual,
        ),
    ]

    for reward in rewards:
        session.add(reward)

    # ===== BOT SETTINGS =====

    default_settings = [
        BotSettings(key="morning_time", value="07:30"),
        BotSettings(key="after_school_time", value="17:15"),
        BotSettings(key="evening_checkin_time", value="21:30"),
        BotSettings(key="sleep_reminder_time", value="22:30"),
        BotSettings(key="weekly_reminder_day", value="4"),
        BotSettings(key="weekly_reminder_time", value="17:30"),
        BotSettings(key="daily_report_time", value="22:00"),
        BotSettings(key="child_weekly_report_time", value="20:00"),
        BotSettings(key="parent_weekly_report_time", value="21:00"),
        BotSettings(key="initialized", value="true"),
    ]

    for setting in default_settings:
        session.add(setting)

    await session.flush()
