import sys
sys.stdout.reconfigure(encoding='utf-8')

from snipglide.engine.listener import ExpansionEngine
from snipglide.database.connection import initialize_database, get_connection
from snipglide.database.snippet_repo import get_all_snippets, add_snippet, delete_snippet
from snipglide.models.snippet import Snippet
from snipglide.engine.parser import parse_variables

initialize_database()

with get_connection() as conn:
    conn.execute("DELETE FROM snippets WHERE shortcut LIKE '@test_%' OR shortcut = '@autotest'")
    conn.commit()

engine = ExpansionEngine(settings_provider=lambda: {'enabled': True, 'case_sensitive': False, 'max_buffer': 250})
snippets = engine._get_cached_snippets()
print(f'Total active snippets: {len(snippets)}')

# 1. Test standard triggers from user's database
test_cases = ['@mr', '@1', '@dislov', '@el', '@glass', '@p', '@s']
for trigger in test_cases:
    engine.buffer = 'testing ' + trigger
    match = engine._find_snippet_match(settings={'case_sensitive': False}, win_title='Any Window - Notepad', win_proc='notepad.exe')
    assert match is not None, f'Failed to match trigger {trigger}'
    print(f'✓ Matched {trigger} -> snippet {match[1].shortcut}')

# 2. Test case insensitivity
engine.buffer = 'my email @MR'
match = engine._find_snippet_match(settings={'case_sensitive': False}, win_title='Chrome', win_proc='chrome.exe')
assert match is not None, 'Failed case insensitive match'
assert match[0] == '@MR', f'Matched slice should be @MR but got {match[0]}'
print('✓ Case-insensitive matching passed')

# 3. Test dynamic variable parsing in expansion
v_text = 'Date: {{date}}, Time: {{time}}, Host: {{hostname}}'
parsed = parse_variables(v_text)
assert '{{date}}' not in parsed, 'date variable not replaced'
assert '{{time}}' not in parsed, 'time variable not replaced'
print('✓ Variable parser test passed:', parsed)

# 4. Test adding a temporary snippet and verifying reload_snippets
temp_snippet = Snippet(
    id=None,
    shortcut='@test_dyn_123',
    replacement='Automated Test Success! 🚀',
    description='Temp Test',
    enabled=True
)
temp_id = add_snippet(temp_snippet)
engine.reload_snippets()
engine.buffer = 'prefix @test_dyn_123'
match = engine._find_snippet_match(settings={'case_sensitive': False}, win_title='Any', win_proc='app.exe')
assert match is not None and match[1].shortcut == '@test_dyn_123', 'Dynamic reload failed'
print('✓ Dynamic snippet addition and reload passed')
delete_snippet(temp_id)
engine.reload_snippets()

# 5. Test Arabic trigger matching
arabic_snippet = Snippet(
    id=None,
    shortcut='@test_arabic_شكر',
    replacement='شكراً جزيلاً لك على تواصلك معنا!',
    description='شكر عربي',
    enabled=True
)
ar_id = add_snippet(arabic_snippet)
engine.reload_snippets()
engine.buffer = 'السلام عليكم @test_arabic_شكر'
match = engine._find_snippet_match(settings={'case_sensitive': False}, win_title='WhatsApp', win_proc='chrome.exe')
assert match is not None and match[1].shortcut == '@test_arabic_شكر', 'Arabic trigger matching failed'
print('✓ Arabic trigger @test_arabic_شكر matched successfully')
delete_snippet(ar_id)
engine.reload_snippets()

# 6. Test Regex snippet matching
regex_snippet = Snippet(
    id=None,
    shortcut=r':testnum\d{2}',
    replacement='Matched dynamic digit regex',
    description='Regex test',
    regex_enabled=True,
    enabled=True
)
rg_id = add_snippet(regex_snippet)
engine.reload_snippets()
engine.buffer = 'test code :testnum99'
match = engine._find_snippet_match(settings={'case_sensitive': False}, win_title='VSCode', win_proc='code.exe')
assert match is not None and match[0] == ':testnum99', 'Regex snippet matching failed'
print('✓ Regex snippet :testnum99 matched successfully')
delete_snippet(rg_id)
engine.reload_snippets()

print('\n=========================================')
print('🎉 ALL 6 COMPREHENSIVE ENGINE TESTS PASSED 100%!')
print('=========================================')
