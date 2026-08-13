
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_func = '''  const handleSaveResultEntry = async (isFinal: boolean) => {
    if (!selectedResultEntryOrder) return;'''

new_func = '''  const handleSaveResultEntry = async (isFinal: boolean) => {
    if (!selectedResultEntryOrder) return;
    if (!selectedResultEntryOrder.patient_id) return alert('Cannot submit results without a selected patient.');
    if (isFinal && selectedResultEntryOrder.status === 'Verified') return alert('This order has already been verified. Duplicate reports are not allowed.');'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Updated handleSaveResultEntry checks')
else:
    print('Failed to find handleSaveResultEntry')

