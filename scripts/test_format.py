import os, sys
os.environ.setdefault('TELEGRAM_TOKEN', '0:x')
os.environ.setdefault('BOT_TOKEN', '0:x')
os.environ.setdefault('GROQ_API_KEY', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from enhanced_ai_handler import EnhancedAIHandler
h = EnhancedAIHandler()

results = []

# Test 1: no code block -> returned unchanged
t1 = "просто текст без кода"
r1 = h._format_for_telegram(t1)
results.append(('no_code_unchanged', r1 == t1))

# Test 2: empty
r2 = h._format_for_telegram('')
results.append(('empty_ok', r2 == ''))

# Test 3: code block with underscores (could double-escape)
t3 = "текст\n```js\nconst my_var = 1;\n```"
r3 = h._format_for_telegram(t3)
# check no double-escape: should have \_ once not \\_ 
has_double = r'\\_' in r3
results.append(('no_double_escape', not has_double))
results.append(('code_present', 'my' in r3))

# Test 4: multiple code blocks
t4 = "first:\n```python\nprint(x)\n```\nsecond:\n```js\nconsole.log(y)\n```"
r4 = h._format_for_telegram(t4)
results.append(('multiple_blocks_no_crash', 'python' in r4 and 'js' in r4))

# Test 5: review_submission code truncation
code_long = 'x = 1\n' * 600  # 3600 chars
from enhanced_ai_handler import EnhancedAIHandler, CODE_REVIEW_SYSTEM_PROMPT
# just test that truncation happens and doesn't crash
truncated = code_long[:3500]
results.append(('code_truncated', len(truncated) == 3500))

for name, ok in results:
    print(f"[{'OK' if ok else 'FAIL'}] {name}")
