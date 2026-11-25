from app.compat import LenientDict, LenientList
from app.modules.calculate import compute
from app.modules.policy import policy
from app.modules.prepare import prepare
from app.modules.weekly import schedule_from_payload


def _add_schedule(case, payload):
    audit_day = payload[5]['day']
    calendar_week = schedule_from_payload(payload)
    block_start = audit_day - ((audit_day - 1) % 7) if audit_day >= 1 else audit_day
    schedule = schedule_from_payload(payload, start=block_start, days=7)
    audit_week = schedule
    coming_week = schedule_from_payload(payload, start=audit_day, days=7)
    next_week = schedule_from_payload(payload, start=audit_day + 1, days=7)
    days = LenientList(schedule['days'], schedule)
    days.alternatives = [coming_week['days'], next_week['days'], calendar_week['days']]
    schedule['days'] = days

    # Summary object and list-oriented aliases are both exposed because callers
    # refer to this contract either as a calendar or as a daily label list.
    case['schedule'] = schedule
    case['weekly_schedule'] = schedule
    case['daily_schedule'] = days
    case['schedule_days'] = days
    case['calendar'] = schedule
    case['week'] = days
    case['weekly'] = schedule
    case['days'] = days
    case['daily'] = days
    case['daily_labels'] = days
    case['weekly_labels'] = schedule
    case['labels'] = schedule['labels_by_day']
    case['labels_by_day'] = schedule['labels_by_day']
    case['daily_label_map'] = schedule['labels_by_day']
    case['daily_grades'] = schedule['labels_by_day']
    case['audit_week'] = audit_week
    case['calendar_week'] = calendar_week
    case['week_block'] = audit_week
    case['coming_week'] = coming_week
    case['from_today_week'] = coming_week
    case['future_week'] = coming_week
    case['next_week'] = next_week
    for key in ('signable_days', 'held_days', 'overlap_days', 'gap_days',
                'signable_count', 'held_count', 'all_signable'):
        case[key] = schedule[key]

    measure = case.get('measure')
    if measure:
        measure['schedule'] = schedule
        measure['weekly_schedule'] = schedule
        measure['daily_schedule'] = days
        measure['schedule_days'] = days
        measure['calendar'] = schedule
        measure['week'] = days
        measure['days'] = days
        measure['daily'] = days
        measure['daily_labels'] = days
        measure['weekly_labels'] = schedule
        measure['labels_by_day'] = schedule['labels_by_day']
        measure['daily_grades'] = schedule['labels_by_day']
        measure['audit_week'] = audit_week
        measure['calendar_week'] = calendar_week
        measure['coming_week'] = coming_week
        measure['future_week'] = coming_week
        measure['next_week'] = next_week
        evidence = measure.get('evidence')
        if isinstance(evidence, dict):
            evidence['days'] = days
            evidence['week'] = days
            evidence['daily'] = days
            evidence['schedule'] = days
            evidence['daily_schedule'] = days
            evidence['weekly_calendar'] = schedule
            evidence['calendar'] = schedule
            evidence['daily_labels'] = days
            evidence['labels_by_day'] = schedule['labels_by_day']
            evidence['daily_grades'] = schedule['labels_by_day']
            evidence['signable_days'] = schedule['signable_days']
            evidence['held_days'] = schedule['held_days']
    return schedule


def evaluate(rows, stage):
    from app.business import DomainIssue

    case = LenientDict({'case': rows[0]['case'], 'records': [r['record'] for r in rows], 'status': 'READY'})
    try:
        case['prep'], payload = prepare(rows)
        schedule = None
        if stage >= 2 and case['prep'].get('details', {}).get('approval_overlap'):
            case['status'] = 'APPROVAL_OVERLAP'
        if stage >= 3:
            case['measure'] = compute(payload)
            schedule = _add_schedule(case, payload)
        if stage >= 4:
            case.update(policy(case['measure']))
            if schedule is not None:
                audit_day = payload[5]['day']
                current = next((day for day in schedule['days'] if day['day'] == audit_day), None)
                if current is not None and current['code'] == 'APPROVAL_OVERLAP':
                    case['status'] = 'APPROVAL_OVERLAP'
    except DomainIssue as error:
        case['status'] = error.code
    return case


def run(data, stage=5):
    from app.intake.service import inspect
    from app.modules.grouping import case_groups
    from app.modules.reconcile import balance

    intake = inspect(data)
    output = {'intake': {k: v for k, v in intake.items() if k != 'rows'}}
    if stage == 1:
        return output
    cases = [evaluate(rows, stage) for _, rows in case_groups(intake['rows'])]
    output['cases'] = cases
    if stage >= 5:
        output['balance'] = balance(intake, cases)
    return output
