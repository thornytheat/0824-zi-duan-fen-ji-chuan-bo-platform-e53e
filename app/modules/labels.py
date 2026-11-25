from app.modules.weekly import *  # noqa: F401,F403
from app.modules.weekly import smart_schedule, build_schedule, grades_on_day  # noqa: F401

weekly = smart_schedule


def for_day(data, day, **kwargs):
    if isinstance(data, tuple) and len(data) >= 6:
        grades, parents, order = data[:3]
        approvals = getattr(data, 'approvals', None)
        if approvals is None and len(data) > 6:
            approvals = data[6]
        return grades_on_day(day, grades, parents, order, approvals or ())
    return smart_schedule(data, **kwargs)['days']
