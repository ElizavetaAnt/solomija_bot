from typing import Optional


def morning_greeting(
    tasks_morning: list[str],
    has_event_today: bool = False,
    event_name: str = "",
    event_time: str = ""
) -> str:
    tasks_text = "\n".join([f"  • {t}" for t in tasks_morning]) if tasks_morning else "  (нет утренних задач)"
    event_block = ""
    if has_event_today:
        event_block = f"\n\n📅 Сегодня у тебя: *{event_name}* в {event_time}"

    return (
        f"🌅 *Доброе утро, Соломия!* ☀️\n\n"
        f"Новый день — новые возможности! Вот твой утренний список:\n\n"
        f"{tasks_text}"
        f"{event_block}\n\n"
        f"Давай начнём день с хорошего настроения! 💪✨"
    )


def after_school_greeting(
    tasks_evening: list[str],
    has_event_today: bool = False,
    event_name: str = "",
    event_time: str = ""
) -> str:
    tasks_text = "\n".join([f"  • {t}" for t in tasks_evening]) if tasks_evening else "  (нет вечерних задач)"
    event_block = ""
    if has_event_today:
        event_block = f"\n\n📅 Напоминаю: сегодня *{event_name}* в {event_time}"

    return (
        f"🏠 *Привет, ты дома!* 🎒\n\n"
        f"Добро пожаловать домой! Отдохни немного и не забудь про вечерние дела:\n\n"
        f"{tasks_text}"
        f"{event_block}\n\n"
        f"Ты молодец, что пришла! 🌟"
    )


def evening_checkin(pending_tasks: list[str]) -> str:
    if not pending_tasks:
        return (
            f"🌙 *Вечерняя проверка*\n\n"
            f"Ура! 🎉 Все задачи на сегодня выполнены!\n"
            f"Ты просто супер! Скоро пора готовиться ко сну 😴✨"
        )

    tasks_text = "\n".join([f"  • {t}" for t in pending_tasks])
    return (
        f"🌙 *Вечерняя проверка*\n\n"
        f"До сна ещё немного времени. Вот что осталось сделать:\n\n"
        f"{tasks_text}\n\n"
        f"Успевай, ты справишься! 💫"
    )


def sleep_reminder() -> str:
    return (
        f"😴 *Пора готовиться ко сну!*\n\n"
        f"Соломия, уже поздновато 🌙\n"
        f"Умойся, почисти зубки и укладывайся спать.\n"
        f"Хорошего сна, солнышко! 💤🌟"
    )


def task_completed(
    task_title: str,
    points_earned: int,
    new_balance: int,
    next_reward_name: Optional[str] = None,
    points_to_next: Optional[int] = None
) -> str:
    reward_block = ""
    if next_reward_name and points_to_next is not None:
        if points_to_next <= 0:
            reward_block = f"\n\n🎁 *{next_reward_name}* — уже можно попросить!"
        else:
            reward_block = f"\n\n🎯 До *{next_reward_name}*: ещё {points_to_next} очков"

    return (
        f"✅ *Выполнено!*\n\n"
        f"«{task_title}» — отлично сделано! 🌟\n\n"
        f"💫 +{points_earned} очков\n"
        f"💰 Баланс: {new_balance} очков"
        f"{reward_block}"
    )


def task_postpone_request_to_parent(
    task_title: str,
    reason: str,
    proposed_date: str
) -> str:
    return (
        f"📋 *Запрос на перенос задачи*\n\n"
        f"Соломия просит перенести задачу:\n"
        f"📌 *{task_title}*\n\n"
        f"💬 Причина: {reason}\n"
        f"📅 Предлагает перенести на: {proposed_date}"
    )


def postpone_approved(task_title: str) -> str:
    return (
        f"✅ *Задача перенесена*\n\n"
        f"Родители одобрили перенос:\n"
        f"«{task_title}»\n\n"
        f"Не забудь выполнить её в новый день! 📅"
    )


def postpone_rejected(task_title: str) -> str:
    return (
        f"❌ *Перенос не одобрен*\n\n"
        f"Родители попросили выполнить задачу сегодня:\n"
        f"«{task_title}»\n\n"
        f"Ты справишься, давай! 💪"
    )


def critical_task_missed_child(task_title: str) -> str:
    return (
        f"⚠️ *Важная задача не выполнена*\n\n"
        f"Соломия, ты не выполнила важную задачу сегодня:\n"
        f"«{task_title}»\n\n"
        f"Это критически важно для животных / семьи. "
        f"Пожалуйста, сообщи маме или папе 💔\n\n"
        f"С баланса снято 2 очка 😔"
    )


def critical_task_missed_parent(task_title: str, date_str: str) -> str:
    return (
        f"🚨 *Критическая задача не выполнена!*\n\n"
        f"Дата: {date_str}\n"
        f"Задача: *{task_title}*\n\n"
        f"Соломия не выполнила эту задачу. С её счёта снято 2 очка.\n"
        f"Пожалуйста, проверьте ситуацию."
    )


def child_weekly_report_good(
    percent: int,
    completed: int,
    total: int,
    points: int,
    achievements: list[str]
) -> str:
    achievements_text = "\n".join([f"  🏆 {a}" for a in achievements]) if achievements else "  (пока нет)"
    return (
        f"🌟 *Итоги недели — ты супер!*\n\n"
        f"✨ Выполнено: {completed}/{total} задач ({percent}%)\n"
        f"💰 Очков за неделю: +{points}\n\n"
        f"*Твои достижения:*\n{achievements_text}\n\n"
        f"Ты настоящий герой этой недели! 🦸‍♀️\n"
        f"Так держать! Следующая неделя будет ещё лучше 💪🌈"
    )


def child_weekly_report_medium(
    percent: int,
    completed: int,
    total: int,
    points: int,
    failed_tasks: list[str]
) -> str:
    failed_text = "\n".join([f"  • {t}" for t in failed_tasks]) if failed_tasks else ""
    return (
        f"📊 *Итоги недели*\n\n"
        f"Выполнено: {completed}/{total} задач ({percent}%)\n"
        f"💰 Очков: +{points}\n\n"
        f"Неплохо! Но можно ещё лучше 😊\n\n"
        + (f"*Не забытые задачи на следующую неделю:*\n{failed_text}\n\n" if failed_tasks else "")
        + f"В следующей неделе постарайся чуть больше! 🌟"
    )


def child_weekly_report_low(
    percent: int,
    completed: int,
    total: int,
    points: int
) -> str:
    return (
        f"📊 *Итоги недели*\n\n"
        f"Выполнено: {completed}/{total} задач ({percent}%)\n"
        f"💰 Очков: +{points}\n\n"
        f"Эта неделя была сложной 😔\n"
        f"Ничего страшного! Новая неделя — новый шанс.\n"
        f"Давай вместе подумаем, как сделать её лучше? 💭\n\n"
        f"Ты можешь! Верю в тебя 💙"
    )


def daily_report_parent(
    date_str: str,
    completed: int,
    total: int,
    percent: int,
    done_list: list[str],
    failed_list: list[str],
    critical_missed: list[str],
    points_earned: int
) -> str:
    done_text = "\n".join([f"  ✅ {t}" for t in done_list]) if done_list else "  (нет выполненных)"
    failed_text = "\n".join([f"  ❌ {t}" for t in failed_list]) if failed_list else "  (все выполнено)"
    critical_text = ""
    if critical_missed:
        c_items = "\n".join([f"  🚨 {t}" for t in critical_missed])
        critical_text = f"\n\n*КРИТИЧЕСКИЕ (не выполнены):*\n{c_items}"

    return (
        f"📊 *Ежедневный отчёт*\n"
        f"📅 {date_str}\n\n"
        f"Выполнено: {completed}/{total} ({percent}%)\n"
        f"💫 Очков заработано: +{points_earned}\n\n"
        f"*Выполнено:*\n{done_text}\n\n"
        f"*Не выполнено:*\n{failed_text}"
        f"{critical_text}"
    )


def weekly_report_parent(
    week_str: str,
    percent: int,
    by_category: dict[str, tuple[int, int]],
    achievements: list[str],
    failed: list[str],
    points: int,
    reward_level: str
) -> str:
    cat_labels = {
        "home": "🏠 Дом",
        "school": "📚 Школа",
        "personal": "🎨 Личное",
        "weekly": "📅 Еженедельные",
    }
    cat_text = "\n".join([
        f"  {cat_labels.get(cat, cat)}: {done}/{total}"
        for cat, (done, total) in by_category.items()
    ]) or "  (нет данных)"

    ach_text = "\n".join([f"  🏆 {a}" for a in achievements]) if achievements else "  (нет)"
    failed_text = "\n".join([f"  ❌ {t}" for t in failed]) if failed else "  (нет)"

    reward_map = {
        "big": "🏆 Большая награда — заслужила!",
        "medium": "🥈 Средняя награда — молодец!",
        "none": "😔 На этой неделе без награды",
    }

    return (
        f"📈 *Недельный отчёт по Соломии*\n"
        f"📅 {week_str}\n\n"
        f"Общий результат: {percent}%\n"
        f"💰 Очков за неделю: {points}\n\n"
        f"*По категориям:*\n{cat_text}\n\n"
        f"*Достижения:*\n{ach_text}\n\n"
        f"*Пропущено:*\n{failed_text}\n\n"
        f"*Рекомендация по награде:*\n  {reward_map.get(reward_level, '')}"
    )


def reward_suggestion_parent(
    reward_name: str,
    cost_points: int,
    balance: int
) -> str:
    return (
        f"🎁 *Предложение по награде*\n\n"
        f"Соломия набрала достаточно очков!\n\n"
        f"🏆 Рекомендуемая награда: *{reward_name}*\n"
        f"💎 Стоимость: {cost_points} очков\n"
        f"💰 Баланс Соломии: {balance} очков\n\n"
        f"Одобрить награду на этой неделе?"
    )
