import json
from datetime import date, datetime, timedelta


def _parse_date(value: str) -> date:
    return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()


def _parse_holidays(value: str) -> set[date]:
    if not value:
        return set()
    holidays = set()
    for raw_item in str(value).replace("，", ",").replace("；", ",").replace(";", ",").split(","):
        item = raw_item.strip()
        if item:
            holidays.add(_parse_date(item))
    return holidays


def calculate_business_deadline(start_date: str, business_days: int, holidays: str = "") -> str:
    """根据起始日期和工作日数量计算截止日期。"""
    current = _parse_date(start_date)
    total_days = int(business_days)
    holiday_set = _parse_holidays(holidays)

    if total_days < 0:
        raise ValueError("工作日数量不能为负数")

    counted = 0
    timeline = []
    while counted < total_days:
        current += timedelta(days=1)
        is_weekend = current.weekday() >= 5
        is_holiday = current in holiday_set
        if not is_weekend and not is_holiday:
            counted += 1
            timeline.append(current.isoformat())

    reminder_offsets = [10, 5, 3, 1]
    reminders = []
    for offset in reminder_offsets:
        reminder = current - timedelta(days=offset)
        if reminder >= _parse_date(start_date):
            reminders.append({"提前天数": offset, "提醒日期": reminder.isoformat()})

    result = {
        "起始日期": start_date,
        "工作日数量": total_days,
        "截止日期": current.isoformat(),
        "排除节假日": [item.isoformat() for item in sorted(holiday_set)],
        "提醒节点": reminders,
        "计算说明": "默认排除周六、周日；如传入 holidays，则同时排除指定日期。",
        "计入工作日": timeline,
    }
    return json.dumps(result, ensure_ascii=False)


SKILL_TOOLS = [
    {
        "name": "calculate_business_deadline",
        "description": "根据起始日期、工作日数量和可选节假日清单，计算业务截止日期和提醒节点。",
        "func": calculate_business_deadline,
        "parameters": {
            "start_date": {
                "type": "string",
                "description": "起始日期，格式为 YYYY-MM-DD。",
                "required": True,
            },
            "business_days": {
                "type": "integer",
                "description": "需要增加的工作日数量。",
                "required": True,
            },
            "holidays": {
                "type": "string",
                "description": "可选节假日清单，多个日期用逗号或分号分隔，格式为 YYYY-MM-DD。",
                "required": False,
            },
        },
    }
]
