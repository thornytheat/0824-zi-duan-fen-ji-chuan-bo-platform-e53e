from app.business import decision


def policy(result):
    if isinstance(result, dict) and (result.get('overlap') or result.get('code') == 'APPROVAL_OVERLAP'):
        delta = result['value'] - result['expected']
        return dict(status='APPROVAL_OVERLAP', delta=delta)
    return decision(result, 'LABEL_TOO_LOW' if result['value'] > result['expected'] else None, upper_bound=True)


def daily_policy(day):
    return policy(day)


evaluate_day = daily_policy
weekly_policy = daily_policy
day_policy = daily_policy
