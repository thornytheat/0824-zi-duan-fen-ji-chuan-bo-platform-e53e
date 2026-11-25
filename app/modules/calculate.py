from app.business import measured
from app.compat import LenientDict


def compute(data):
    grades, parents, order, permits, expired, audit = data[:6]
    inherited = {}
    approved = []
    for field in order:
        level = max([grades[field], *(inherited[p] for p in parents[field])])
        if permits.get(field, level) < level:
            level = permits[field]
            approved.append(field)
        inherited[field] = level
    evidence = LenientDict({
        'grades': {str(k): v for k, v in inherited.items()},
        'approved': sorted(approved),
        'expired': sorted(expired - set(permits) if isinstance(expired, set)
                          else set(expired) - set(permits)),
    })
    return measured(inherited[audit['field']], audit['grade'], '级', evidence)


def weekly(*args, **kwargs):
    from app.modules.weekly import smart_schedule
    return smart_schedule(*args, **kwargs)


daily_labels = weekly
weekly_labels = weekly
weekly_schedule = weekly
daily_schedule = weekly


def propagate_day(data, day):
    from app.modules.weekly import grades_on_day
    if isinstance(data, tuple) and len(data) >= 3:
        grades, parents, order = data[:3]
        approvals = data[6] if len(data) > 6 else ()
    else:
        grades, parents, order = data['grades'], data['parents'], data['order']
        approvals = data.get('approvals', ())
    return grades_on_day(day, grades, parents, order, approvals)


def propagate_for_day(grades, parents, order, approvals, day):
    from app.modules.weekly import grades_on_day
    return grades_on_day(day, grades, parents, order, approvals)
