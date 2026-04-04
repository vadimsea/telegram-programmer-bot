import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from enhanced_ai_handler import _parse_submission_review

cases = [
    ('', 'ERROR'),
    ('OK', 'OK'),
    ('ERROR', 'ERROR'),
    ('ok хорошо', 'OK'),
    ('error что-то не так', 'ERROR'),
    ('Отлично! Это хорошо', 'ERROR'),     # модель не следует формату -> должен быть ERROR
    ('LGTM всё окей', 'ERROR'),
    ('OK. Очень хорошо\nно есть нюанс', 'OK'),
    ('ERROR\nНе хватает DOCTYPE', 'ERROR'),
    ('\nOK\nТекст', 'ERROR'),             # пробел перед OK — модель нарушила формат
]

bugs = []
for raw, expected in cases:
    status, feedback = _parse_submission_review(raw)
    ok = status == expected
    if not ok:
        bugs.append(repr(raw))
    tag = 'OK' if ok else 'BUG'
    print(f'[{tag}] {repr(raw):45s} -> {status} (expected {expected})')

print()
print(f'Total: {len(cases)} | Bugs: {len(bugs)}: {bugs if bugs else "none"}')
