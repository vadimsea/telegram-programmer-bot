import os, sys
os.environ.setdefault('TELEGRAM_TOKEN','0:x')
os.environ.setdefault('BOT_TOKEN','0:x')
os.environ.setdefault('GROQ_API_KEY','dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from enhanced_ai_handler import EnhancedAIHandler
h = EnhancedAIHandler()

tests = [
    ('привет', 'small_talk'),
    ('как дела?', 'small_talk'),
    ('как сделать flexbox?', None),
    ('как сделать калькулятор', None),
    ('не работает', 'small_talk'),
    ('не работает fetch', None),
    ('сделал layout', 'small_talk'),
    ('я сделал задание', 'small_talk'),
    ('где посмотреть документацию по css', None),
    ('что такое promise', None),
    ('расскажи про eventloop', None),
    ('как начать учить js', None),
    ('добрый вечер', 'small_talk'),
    ('мне ошибку выдаёт типа TypeError', None),   # TypeError — техслово → Groq
]

results = []
bugs = []
for text, expected in tests:
    res = h._match_small_talk(text.lower())
    got = 'small_talk' if res else None
    ok = got == expected
    status = 'OK' if ok else 'BUG'
    if not ok:
        bugs.append(text)
    results.append(f'[{status}] {text!r:42s} -> {got or "Groq":10s} (expected {expected or "Groq"})')

with open('test_smalltalk.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
    f.write(f'\n\nTotal: {len(tests)} | Bugs: {len(bugs)}')
    if bugs:
        f.write('\nBuggy inputs: ' + ', '.join(repr(b) for b in bugs))
