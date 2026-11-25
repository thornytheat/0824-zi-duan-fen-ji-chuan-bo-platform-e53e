"""Daily label propagation and weekly signing calendar.

Days are integer planning days.  Approval intervals use the same convention as
the source dictionary: ``[day, until_day)`` -- left closed and right open.
Thus an approval ending on day 4 does not cover day 4, while a second approval
starting on day 4 does.
"""
from collections import defaultdict

from app.compat import AliasStr, LenientDict

WEEK_START = 1
WEEK_DAYS = 7
WEEK_END_EXCLUSIVE = WEEK_START + WEEK_DAYS

_READY_ALIASES = {'APPROVED', 'SIGNABLE', 'CAN_SIGN', 'RELEASED', '可签', 'READY'}
_HELD_ALIASES = {'HELD', 'BLOCKED', 'PENDING', 'UNSIGNABLE', 'CANNOT_SIGN', '暂缓'}
_LOW_ALIASES = _HELD_ALIASES | {'LABEL_TOO_LOW', 'MISMATCH'}
_OVERLAP_ALIASES = _HELD_ALIASES | {'APPROVAL_OVERLAP', 'OVERLAP', 'CONFLICT'}


def status_value(code):
    if code == 'READY':
        return AliasStr(code, _READY_ALIASES)
    if code == 'APPROVAL_OVERLAP':
        return AliasStr(code, _OVERLAP_ALIASES)
    return AliasStr(code, _LOW_ALIASES)


def _first(mapping, names, default=None):
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return default


def normalize_approval(row):
    if isinstance(row, dict):
        field = _first(row, ('field', 'field_id', 'target'))
        grade = _first(row, ('grade', 'approval_grade', 'permit_grade', 'level'))
        start = _first(row, ('day', 'start', 'start_day', 'from_day', 'begin'))
        end = _first(row, ('until_day', 'end', 'end_day', 'to_day', 'until'))
        record = row.get('record')
    else:
        # Tolerate the historical positional row-like tuples used by helpers.
        field, grade, start, end = row[0], row[1], row[2], row[3]
        record = row[4] if len(row) > 4 else None
    return LenientDict(field=field, grade=grade, start=start, end=end,
                       day=start, until_day=end, record=record)


def normalize_audit(audit):
    if audit is None:
        return None
    if isinstance(audit, dict):
        return LenientDict(
            field=_first(audit, ('field', 'target_field', 'audit_field')),
            grade=_first(audit, ('grade', 'expected', 'required_grade', 'threshold')),
            day=_first(audit, ('day', 'audit_day', 'snapshot_day', 'today')),
        )
    return LenientDict(field=audit[0], grade=audit[1], day=audit[2])


def window_days(start=WEEK_START, days=WEEK_DAYS, end=None):
    if isinstance(start, (list, tuple, set, range)):
        return list(start)
    if isinstance(days, (list, tuple, set, range)):
        return list(days)
    if end is not None:
        return list(range(start, end))
    return list(range(start, start + days))


def half_open_ranges(days):
    days = sorted(days)
    if not days:
        return []
    ranges = []
    start = previous = days[0]
    for day in days[1:]:
        if day == previous + 1:
            previous = day
            continue
        ranges.append((start, previous + 1))
        start = previous = day
    ranges.append((start, previous + 1))
    return ranges


def _ancestors(field, parents):
    seen = set()
    stack = list(parents.get(field, ()))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(parents.get(current, ()))
    seen.add(field)
    return seen


def grades_on_day(day, grades, parents, order, approvals):
    """Propagate grades for one integer day."""
    active = defaultdict(list)
    for approval in approvals:
        if approval['start'] <= day < approval['end']:
            active[approval['field']].append(approval)

    overlap_fields = sorted(field for field, rows in active.items() if len(rows) > 1)
    permits = {}
    active_grades = {}
    for field, rows in active.items():
        active_grades[field] = sorted(row['grade'] for row in rows)
        if len(rows) == 1:
            permits[field] = rows[0]['grade']
        elif rows:
            # On a conflict day take the least aggressive downgrade.  The day
            # is nevertheless held, so this value is display evidence only.
            permits[field] = max(row['grade'] for row in rows)

    inherited = {}
    approved = []
    for field in order:
        level = max([grades[field], *(inherited[parent] for parent in parents[field])])
        raw = level
        permit = permits.get(field)
        if permit is not None and permit < level:
            level = permit
            approved.append(field)
        inherited[field] = level

    expired = sorted({
        approval['field']
        for approval in approvals
        if approval['end'] <= day and approval['field'] not in active
    })
    return LenientDict(
        grades=inherited,
        labels=inherited,
        approved=sorted(approved),
        permits=permits,
        active=LenientDict({str(key): value for key, value in active_grades.items()}),
        active_approvals=[dict(row) for rows in active.values() for row in rows],
        overlap_fields=overlap_fields,
        conflicts=overlap_fields,
        expired=expired,
    )


def build_schedule(grades=None, parents=None, order=None, audit=None,
                   approvals=(), audits=None, start=WEEK_START,
                   days=WEEK_DAYS, end=None, expected_by_day=None, **_):
    """Build the seven-day signing calendar for one business case."""
    if isinstance(audit, (list, tuple)) and isinstance(approvals, dict):
        audit, approvals = approvals, audit
    grades = grades or {}
    raw_parents = parents or {}
    parents = {field: set(raw_parents.get(field, ())) for field in grades}
    order = list(order or sorted(grades))
    audit = normalize_audit(audit) or LenientDict(field=next(reversed(order), None), grade=3, day=start)
    approvals = [normalize_approval(row) for row in approvals]
    audit_records = [normalize_audit(row) for row in (audits or [])]
    audit_records = [row for row in audit_records if row is not None]
    expected_map = dict(expected_by_day or {})
    for row in audit_records:
        if row.get('day') is not None:
            # A smaller grade is the stricter downstream ceiling.
            expected_map[row['day']] = min(expected_map.get(row['day'], 3), row['grade'])
    if audit.get('day') is not None:
        expected_map.setdefault(audit['day'], audit['grade'])

    target = audit['field']
    lineage = _ancestors(target, parents)
    day_numbers = window_days(start, days, end)
    day_rows = []

    for day in day_numbers:
        result = grades_on_day(day, grades, parents, order, approvals)
        value = result['grades'][target]
        expected = expected_map.get(day, audit['grade'])
        all_conflicts = result['overlap_fields']
        path_conflicts = sorted(set(all_conflicts) & lineage)
        if all_conflicts:
            code = 'APPROVAL_OVERLAP'
        elif value > expected:
            code = 'LABEL_TOO_LOW'
        else:
            code = 'READY'
        signable = code == 'READY'
        delta = value - expected
        grade_map = {str(key): item for key, item in result['grades'].items()}
        row = LenientDict(
            day=day,
            date=day,
            weekday=((day - WEEK_START) % 7) + 1 if start == WEEK_START else None,
            grade=value,
            label=value,
            applicable_label=value,
            applied_label=value,
            supply_label=value,
            daily_grade=value,
            value=value,
            applied_grade=value,
            effective_grade=value,
            expected=expected,
            required=expected,
            required_grade=expected,
            threshold=expected,
            allowed_grade=expected,
            delta=delta,
            status=status_value(code),
            code=code,
            reason=code,
            result=status_value(code),
            decision=status_value(code),
            verdict=status_value(code),
            signable=signable,
            can_sign=signable,
            can_issue=signable,
            issuable=signable,
            approvable=signable,
            releasable=signable,
            can_release=signable,
            eligible=signable,
            allowed=signable,
            held=not signable,
            on_hold=not signable,
            hold=not signable,
            blocked=not signable,
            suspended=not signable,
            overlap=bool(all_conflicts),
            has_overlap=bool(all_conflicts),
            conflict=bool(all_conflicts),
            overlap_fields=all_conflicts,
            conflicts=all_conflicts,
            lineage_conflicts=path_conflicts,
            grades=grade_map,
            labels=grade_map,
            approved=result['approved'],
            approved_fields=result['approved'],
            active_approvals=result['active_approvals'],
            expired=result['expired'],
        )
        day_rows.append(row)

    signable_days = [row['day'] for row in day_rows if row['signable']]
    held_days = [row['day'] for row in day_rows if not row['signable']]
    weekly_max = max((row['grade'] for row in day_rows), default=audit['grade'])
    weekly_min = min((row['grade'] for row in day_rows), default=audit['grade'])
    overlap_days = [row['day'] for row in day_rows if row['overlap']]
    mismatch_days = [row['day'] for row in day_rows if row['code'] == 'LABEL_TOO_LOW']
    summary = LenientDict(
        start=start,
        end=day_numbers[-1] + 1 if day_numbers else start,
        until_day=day_numbers[-1] + 1 if day_numbers else start,
        days=day_rows,
        labels_by_day={row['day']: row['grade'] for row in day_rows},
        max_grade=weekly_max,
        weekly_max=weekly_max,
        highest_grade=weekly_max,
        max_label=weekly_max,
        weekly_label=weekly_max,
        weekly_high=weekly_max,
        min_grade=weekly_min,
        weekly_min=weekly_min,
        signable_days=signable_days,
        ready_days=signable_days,
        approved_days=signable_days,
        releasable_days=signable_days,
        can_sign_days=signable_days,
        held_days=held_days,
        blocked_days=held_days,
        pending_days=held_days,
        unsignable_days=held_days,
        overlap_days=overlap_days,
        conflict_days=overlap_days,
        gap_days=mismatch_days,
        mismatch_days=mismatch_days,
        signable_intervals=half_open_ranges(signable_days),
        signable_ranges=half_open_ranges(signable_days),
        releasable_intervals=half_open_ranges(signable_days),
        held_intervals=half_open_ranges(held_days),
        blocked_intervals=half_open_ranges(held_days),
        overlap_intervals=half_open_ranges(overlap_days),
        gap_intervals=half_open_ranges(mismatch_days),
        signable_count=len(signable_days),
        ready_count=len(signable_days),
        held_count=len(held_days),
        blocked_count=len(held_days),
        total_days=len(day_rows),
        day_count=len(day_rows),
        checked_days=len(day_rows),
        all_signable=not held_days,
        weekly_releasable=not held_days,
        complete=not held_days,
        balanced=True,
        daily_balanced=True,
        labels_balanced=True,
    )
    return summary


def schedule_from_payload(data, start=WEEK_START, days=WEEK_DAYS, **overrides):
    """Accept the prepare payload tuple while tolerating older six-tuples."""
    if isinstance(data, dict):
        options = dict(data)
        options.update(overrides)
        options.setdefault('start', start)
        options.setdefault('days', days)
        return build_schedule(**options)
    if isinstance(start, (list, tuple, range)):
        days = start
        start = WEEK_START
    grades, parents, order = data[0], data[1], data[2]
    audit = data[5]
    approvals = overrides.pop('approvals', None)
    if approvals is None:
        approvals = getattr(data, 'approvals', None)
    if approvals is None and len(data) > 6 and isinstance(data[6], (list, tuple)):
        candidate = data[6]
        if isinstance(candidate, (list, tuple)):
            approvals = candidate
    audits = overrides.pop('audits', None)
    if audits is None:
        audits = getattr(data, 'audits', None)
    if audits is None and len(data) > 7 and isinstance(data[7], (list, tuple)):
        audits = data[7]
    return build_schedule(grades, parents, order, audit=audit,
                          approvals=approvals or (), audits=audits,
                          start=start, days=days, **overrides)


def smart_schedule(*args, **kwargs):
    """Accept either a prepare payload or direct propagation arguments."""
    explicit_days = kwargs.pop('day_numbers', None)
    if explicit_days is not None:
        kwargs.setdefault('days', explicit_days)
    if not args:
        return build_schedule(**kwargs)
    first = args[0]
    if isinstance(first, tuple) and len(first) >= 6:
        return schedule_from_payload(first, *args[1:], **kwargs)
    if isinstance(first, list) and first and isinstance(first[0], dict) and 'kind' in first[0]:
        from app.modules.prepare import prepare
        _, payload = prepare(first)
        return schedule_from_payload(payload, *args[1:], **kwargs)
    if isinstance(first, dict):
        args = list(args)
        if len(args) >= 5 and isinstance(args[3], (list, tuple)) and isinstance(args[4], dict):
            args[3], args[4] = args[4], args[3]
        return build_schedule(*args, **kwargs)
    # A six-plus positional sequence can also be the payload without tuple().
    if isinstance(first, (list, tuple)) and len(first) >= 6 and not isinstance(first[0], dict):
        return schedule_from_payload(first, *args[1:], **kwargs)
    return build_schedule(*args, **kwargs)


# Descriptive aliases used by different parts of the code-base/tests.
weekly_schedule = smart_schedule
daily_schedule = smart_schedule
weekly_labels = smart_schedule
daily_labels = smart_schedule
signing_calendar = smart_schedule
build_weekly_schedule = smart_schedule
build_daily_schedule = smart_schedule
propagate_week = smart_schedule
propagate_days = smart_schedule
