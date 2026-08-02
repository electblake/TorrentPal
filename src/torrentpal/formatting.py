from datetime import datetime


def format_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    unit = units[0]
    for unit in units:
        if value < 1000 or unit == units[-1]:
            break
        value /= 1000
    return (
        f"{value:.0f} {unit}" if value >= 10 or unit == "B" else f"{value:.1f} {unit}"
    )


def format_date(value: datetime | None) -> str:
    return value.astimezone().strftime("%b %d, %Y, %I:%M:%S %p %Z") if value else ""
