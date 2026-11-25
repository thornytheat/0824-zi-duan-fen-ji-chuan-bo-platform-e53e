from app.business import DomainIssue, by_kind, prepared
from app.compat import LenientDict, PreparePayload


def prepare(rows):
    from graphlib import TopologicalSorter, CycleError
    audits = by_kind(rows, 'audit')
    if not audits:
        raise DomainIssue('EXPECTED_ONE_AUDIT')
    audit = audits[0]
    columns = by_kind(rows, 'column')
    grades = {r['field']: r['grade'] for r in columns}
    if (len(grades) != len(columns)
            or any(level > 3 for level in grades.values())
            or any(row['grade'] > 3 for row in audits)):
        raise DomainIssue('UNKNOWN_GRADE')
    if audit['field'] not in grades:
        raise DomainIssue('UNKNOWN_FIELD')
    parents = {field: set() for field in grades}
    for row in by_kind(rows, 'dependency'):
        field, parent = row['field'], row['parent']
        if field not in grades or parent not in grades:
            raise DomainIssue('UNKNOWN_FIELD')
        parents[field].add(parent)
    try:
        order = list(TopologicalSorter({f: sorted(parents[f]) for f in sorted(parents)}).static_order())
    except CycleError as error:
        raise DomainIssue('LINEAGE_CYCLE') from error

    approval_rows = by_kind(rows, 'approval')
    permits, expired = {}, set()
    active_by_field = {}
    for row in approval_rows:
        field, start, end = row['field'], row['day'], row['until_day']
        if field not in grades or not start < end or not grades[field] <= row['grade'] <= 3:
            raise DomainIssue('INVALID_APPROVAL')
        if start <= audit['day'] < end:
            active_by_field.setdefault(field, []).append(row)
        elif end <= audit['day']:
            expired.add(field)

    overlap_fields = []
    for field, active_rows in active_by_field.items():
        if len(active_rows) > 1:
            overlap_fields.append(field)
            # Conservative display value: when grades differ, retain the
            # highest effective level; the day is held separately.
            permits[field] = max(row['grade'] for row in active_rows)
        else:
            permits[field] = active_rows[0]['grade']

    details = LenientDict({
        'columns': len(order),
        'active_approvals': len(permits),
        'snapshot_day': audit['day'],
        'approval_overlap': len(overlap_fields),
        'overlap_fields': sorted(overlap_fields),
        'audit_days': sorted(row['day'] for row in audits),
    })
    base_payload = (grades, parents, order, permits, expired, audit)
    payload = PreparePayload(base_payload, approval_rows, audits)
    return prepared(len(order), details, payload)
