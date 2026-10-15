"""Presentation metadata only. Never changes source fingerprints, scores or formulas."""
from .dashboard import GROUP_LABELS, NATIONAL_GROUP_CODES

GROUP_NAMES = {**GROUP_LABELS, **{code: GROUP_LABELS[group] for group, code in NATIONAL_GROUP_CODES.items()},
    'total': 'Tổng hợp 6 nhóm chỉ tiêu', 'national': 'Tổng hợp 6 nhóm chỉ tiêu'}
PARAMETER_NAMES = {'totalMaxScore': 'Điểm tối đa của nhóm', 'maxScore': 'Điểm tối đa của chỉ tiêu',
    'threshold': 'Ngưỡng đạt điểm (%)', 'targetRatio': 'Tỷ lệ mục tiêu (%)',
    'formula': 'Công thức tính', 'formulaVersion': 'Phiên bản công thức',
    'scorePolicy': 'Quy tắc chấm điểm', 'weight': 'Trọng số', 'name': 'Tên chỉ tiêu',
    'groupCodes': 'Danh sách nhóm chỉ tiêu', 'score': 'Điểm ghi nhận', 'totalScore': 'Tổng điểm ghi nhận'}


def names(value):
    if isinstance(value, str): return [value] if value.strip() else []
    if isinstance(value, list): return list(dict.fromkeys(v for v in value if isinstance(v, str) and v.strip()))
    return []


def describe_changes(changes, contexts=(), *, profiles=(), province_names=None):
    """Capture names from before/after profiles, including added/removed metrics.

    Existing captured labels take precedence over newer baselines when viewing history.
    Unknown new fields keep their raw path and explicitly state that no name is known.
    """
    province_names = province_names or {}
    result = []
    for change in changes:
        if isinstance(change.get('display'), dict) and all(isinstance(change['display'].get(k),str)
                for k in ('groupName','indicatorName','parameterName')):
            result.append(dict(change)); continue
        field = str(change.get('field', ''))
        cohort, sep, key = field.partition('/')
        if not sep: key, cohort = field, ''
        context_groups = list(dict.fromkeys(c.get('group') for c in contexts if c.get('group')))
        group = context_groups[0] if len(context_groups) == 1 else None
        indicator = None; metric_code = None; scope = None; entity = None
        parameter = key
        if cohort in province_names:
            # Closed-month samples contain group scores, not component metric scores.
            group = key; entity = province_names[cohort]; scope = 'Cấp tỉnh'
            indicator = 'Tổng điểm' if key == 'total' else 'Điểm nhóm chỉ tiêu'
            parameter_name = 'Điểm ghi nhận'
        else:
            if key.startswith('metric:'):
                parts = key.split(':', 2); metric_code = parts[1] if len(parts)>1 else ''
                parameter = parts[2] if len(parts)>2 else 'presence'
                name_path = (cohort+'/' if cohort else '')+'metric:'+metric_code+':name'
                candidates = []
                for profile in profiles:
                    candidates.extend(names(profile.get(name_path)))
                # Companion name changes are available for new/deleted/renamed indicators.
                for entry in changes:
                    if entry.get('field') == name_path:
                        candidates.extend(names(entry.get('before'))); candidates.extend(names(entry.get('after')))
                candidates = list(dict.fromkeys(candidates))
                indicator = ' / '.join(candidates) if candidates else 'Chưa có tên chỉ tiêu trong bằng chứng đã lưu'
            if cohort == 'root': scope = 'Cấp tỉnh'
            elif cohort.startswith('child:'):
                scope = 'Cấp xã, phường' if 'COMMUNE' in cohort else 'Sở, ban, ngành' if 'DEPARTMENT' in cohort else 'Cơ quan trực thuộc'
            if key == 'groupCodes': group = 'national'; scope = 'Toàn quốc'
            parameter_name = 'Chỉ tiêu được bổ sung / loại bỏ' if parameter == 'presence' else PARAMETER_NAMES.get(parameter, 'Tham số mới / chưa có tên diễn giải')
            if not indicator: indicator = 'Cơ cấu các nhóm chỉ tiêu' if key=='groupCodes' else 'Thông số chung của nhóm'
        display = {'groupId': group, 'groupName': GROUP_NAMES.get(group, 'Nhóm mới: '+str(group) if group else 'Chưa xác định nhóm từ bằng chứng đã lưu'),
            'indicatorName': indicator, 'parameterName': parameter_name, 'parameterCode': parameter,
            'metricCode': metric_code, 'scopeLabel': scope, 'entityName': entity, 'sourcePath': field}
        result.append({**change, 'display': display})
    return result


def describe_details(details, *, profiles=()):
    changes = describe_changes(details.get('changes', []), details.get('contexts', []),
        profiles=profiles, province_names=details.get('provinceNames', {}))
    return {**details, 'changes': changes}


def alert_summary(details):
    changes = describe_details(details)['changes']
    groups = list(dict.fromkeys(c['display']['groupName'] for c in changes))
    if not groups:
        groups = list(dict.fromkeys(GROUP_NAMES.get(c.get('group'), 'Nhóm mới: '+str(c.get('group')))
            for c in details.get('contexts', []) if c.get('group')))
    subjects = []
    for change in changes:
        display = change['display']
        item = {k: display[k] for k in ('groupName', 'indicatorName', 'parameterName')}
        if item not in subjects: subjects.append(item)
    return {'groups': groups[:6], 'subjects': subjects[:3], 'subjectCount': len(subjects)}
