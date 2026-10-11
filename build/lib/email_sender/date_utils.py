import calendar
from datetime import date, timedelta


def subtract_months(date_obj: date, months: int) -> date:
    """Subtract calendar months, handling month-end dates."""
    month_index = date_obj.month - 1 - months
    year = date_obj.year + month_index // 12
    month = month_index % 12 + 1

    day = min(
        date_obj.day,
        calendar.monthrange(year, month)[1]
    )

    return date_obj.replace(
        year=year,
        month=month,
        day=day
    )


def subtract_years(date_obj: date, years: int) -> date:
    """Subtract calendar years, handling leap days."""
    year = date_obj.year - years
    day = min(
        date_obj.day,
        calendar.monthrange(year, date_obj.month)[1]
    )

    return date_obj.replace(year=year, day=day)


def get_lookback_date(
    look_back: int,
    look_back_format: str
) -> date:
    """Return the earliest date allowed by the look-back period."""

    if (
        isinstance(look_back, bool)
        or not isinstance(look_back, int)
        or look_back < 0
    ):
        raise ValueError(
            "look_back must be a non-negative integer."
        )

    unit = look_back_format.strip().lower()
    today = date.today()

    if unit in ("day", "days"):
        return today - timedelta(days=look_back)

    if unit in ("month", "months"):
        return subtract_months(today, look_back)

    if unit in ("year", "years"):
        return subtract_years(today, look_back)

    raise ValueError(
        "look_back_format must be day, month, or year."
    )
