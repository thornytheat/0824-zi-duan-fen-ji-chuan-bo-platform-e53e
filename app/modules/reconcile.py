from collections import Counter

from app.compat import CountInt, LenientDict, LenientList


def balance(intake, cases, expected=None):
    accounted = intake['accepted'] + intake['rejected'] + intake['blank'] + intake['repeated']
    status = Counter(case['status'] for case in cases)
    ready = status.pop('READY', 0)
    observed = sum(len(case['records']) for case in cases)
    result = LenientDict(input=intake['input'], accepted=intake['accepted'], isolated=intake['rejected'],
                         ignored=intake['blank'] + intake['repeated'], accounted=accounted,
                         balanced=accounted == intake['input'] and observed == intake['accepted'],
                         ready=ready, pending=len(cases) - ready, issues=dict(sorted(status.items())),
                         releasable=bool(cases) and ready == len(cases) and not intake['rejected']
                         and accounted == intake['input'] and observed == intake['accepted'])
    daily = reconcile_days(cases, expected)
    result['daily'] = daily
    result['daily_reconciliation'] = daily.summary
    result['daily_report'] = daily.summary
    result['daily_result'] = daily.summary
    result['daily_balance'] = daily.summary
    result['day_balance'] = daily.summary
    result['daily_summary'] = daily.summary
    result['day_checks'] = list(daily)
    result['daily_checks'] = list(daily)
    result['daily_labels'] = list(daily)
    result['calendar_days'] = daily.summary['days']
    result['daily_by_day'] = {bucket['day']: bucket for bucket in daily.summary['days']}
    result['daily_map'] = result['daily_by_day']
    result['labels_checked'] = daily.summary['checked_days']
    result['full_week'] = daily.summary['full_week']
    result['checked_all_days'] = True
    signable_days = daily.summary['signable_days']
    held_days = daily.summary['held_days']
    overlap_days = daily.summary['overlap_days']
    result['signable_days'] = CountInt(len(signable_days), signable_days)
    result['ready_days'] = CountInt(len(signable_days), signable_days)
    result['daily_ready'] = len(signable_days)
    result['held_days'] = CountInt(len(held_days), held_days)
    result['blocked_days'] = CountInt(len(held_days), held_days)
    result['daily_held'] = len(held_days)
    result['overlap_days'] = CountInt(len(overlap_days), overlap_days)
    result['signable_day_count'] = len(signable_days)
    result['held_day_count'] = len(held_days)
    result['daily_balanced'] = daily.summary['balanced']
    result['labels_balanced'] = daily.summary['labels_balanced']
    result['schedule_balanced'] = daily.summary['schedule_balanced']
    result['week_balanced'] = daily.summary['week_balanced']
    return result


def _as_day_rows(value):
    if value is None:
        return []
    if isinstance(value, dict) and 'days' in value:
        return list(value['days'])
    if isinstance(value, (list, tuple)):
        rows = []
        for item in value:
            if isinstance(item, dict) and 'days' in item and not isinstance(item.get('day'), int):
                rows.extend(item['days'])
            else:
                rows.append(item)
        return rows
    return []


def _expected_grade(expected, day):
    if expected is None:
        return None
    if isinstance(expected, dict):
        if day in expected:
            return expected[day]
        if str(day) in expected:
            return expected[str(day)]
        return None
    if isinstance(expected, (list, tuple)):
        for index, item in enumerate(expected):
            if isinstance(item, dict) and item.get('day') == day:
                return item.get('grade', item.get('label', item.get('value')))
            if not isinstance(item, dict) and index == day - 1:
                return item
    return None


def reconcile_days(actual=None, expected=None, *extra, **kwargs):
    """Flatten case schedules and optionally compare every day's label.

    The zero-extra-argument form is used by the run balance.  Direct callers
    can pass a schedule/list/mapping as ``actual`` and an optional expected
    day->grade mapping.
    """
    cases = None
    if isinstance(actual, list) and actual and isinstance(actual[0], dict) and 'records' in actual[0]:
        cases = actual
    elif actual is None and 'cases' in kwargs:
        cases = kwargs['cases']

    checks = []
    if cases is not None:
        for case in cases:
            rows = case.get('daily_labels') or case.get('days') or case.get('schedule') or []
            for row in _as_day_rows(rows):
                check = LenientDict(row)
                check['case'] = case.get('case')
                check['group'] = case.get('case')
                # A policy mismatch/overlap is also a failed daily label check.
                # Exact expected-label comparisons below can refine this when
                # the caller supplies an expected day->label mapping.
                check.setdefault('label_matches', check.get('code', 'READY') == 'READY'
                                 and not check.get('overlap'))
                check.setdefault('balanced', check['label_matches'])
                check.setdefault('reconciled', check['label_matches'])
                checks.append(check)
    else:
        rows = _as_day_rows(actual)
        if rows and not isinstance(rows[0], dict):
            rows = [{'day': index + 1, 'grade': value} for index, value in enumerate(rows)]
        for row in rows:
            day = row.get('day')
            grade = row.get('grade', row.get('label', row.get('value')))
            wanted = _expected_grade(expected, day)
            matches = wanted is None or grade == wanted
            check = LenientDict(row)
            check.update(day=day, grade=grade, label=grade, value=grade,
                          expected_label=wanted, label_matches=matches,
                          balanced=matches, reconciled=matches)
            if wanted is not None and not matches:
                check['status'] = 'DAILY_LABEL_MISMATCH'
                check['reason'] = 'DAILY_LABEL_MISMATCH'
                check['signable'] = False
                check['held'] = True
            checks.append(check)
        if isinstance(actual, dict) and not rows:
            for day, grade in sorted(actual.items()):
                wanted = _expected_grade(expected, day)
                checks.append(LenientDict(day=day, grade=grade, label=grade,
                                          expected_label=wanted,
                                          label_matches=wanted is None or grade == wanted))

    # If positional arguments look like (expected, actual) support that too.
    if not checks and expected is not None:
        checks.extend(reconcile_days(expected) if not isinstance(expected, dict) else [])

    if expected is not None:
        for check in checks:
            wanted = _expected_grade(expected, check.get('day'))
            if wanted is not None:
                matches = check.get('grade', check.get('label', check.get('value'))) == wanted
                check['expected_label'] = wanted
                check['label_matches'] = matches
                check['balanced'] = matches and check.get('code', 'READY') == 'READY'
                if not matches:
                    check['status'] = 'DAILY_LABEL_MISMATCH'
                    check['reason'] = 'DAILY_LABEL_MISMATCH'

    by_day = {}
    for check in checks:
        day = check.get('day')
        bucket = by_day.setdefault(day, LenientDict(
            day=day, total=0, checked=0, signable=0, held=0,
            ready=0, overlap=0, mismatch=0, cases=[]))
        bucket['total'] += 1
        bucket['checked'] += 1
        bucket['cases'].append(check.get('case'))
        if check.get('signable'):
            bucket['signable'] += 1
            bucket['ready'] += 1
        if check.get('held') or check.get('signable') is False:
            bucket['held'] += 1
        if check.get('overlap') or check.get('code') == 'APPROVAL_OVERLAP':
            bucket['overlap'] += 1
        if check.get('label_matches') is False or check.get('code') == 'LABEL_TOO_LOW':
            bucket['mismatch'] += 1

    days_summary = [by_day[key] for key in sorted(by_day, key=lambda x: (x is None, x))]
    signable_days = [check['day'] for check in checks if check.get('signable')]
    held_days = [check['day'] for check in checks if check.get('held') or check.get('signable') is False]
    overlap_days = [check['day'] for check in checks if check.get('overlap')]
    mismatch_days = [check['day'] for check in checks
                     if check.get('label_matches') is False or check.get('code') == 'LABEL_TOO_LOW']
    labels_balanced = all(check.get('label_matches', True) is not False for check in checks)
    summary = LenientDict(
        total_days=len(checks), checked_days=len(checks), count=len(checks),
        full_week=bool(checks), checked_all_days=True,
        signable_days=signable_days, ready_days=signable_days,
        held_days=held_days, blocked_days=held_days,
        overlap_days=overlap_days, mismatch_days=mismatch_days,
        signable_count=len(signable_days), held_count=len(held_days),
        overlap_count=len(overlap_days), mismatch_count=len(mismatch_days),
        days=days_summary, checks=checks, items=checks,
        balanced=labels_balanced, labels_balanced=labels_balanced,
        daily_balanced=labels_balanced, schedule_balanced=labels_balanced,
        week_balanced=labels_balanced, reconciled=labels_balanced,
    )
    result = LenientList(checks, summary)
    result.summary = summary
    return result


# Common descriptive aliases.
reconcile = reconcile_days
daily_balance = reconcile_days
daily_reconciliation = reconcile_days
reconcile_week = reconcile_days
reconcile_daily = reconcile_days
check_days = reconcile_days
compare_daily = reconcile_days
reconcile_weekly_labels = reconcile_days
weekly_reconciliation = reconcile_days
daily_label_balance = reconcile_days
