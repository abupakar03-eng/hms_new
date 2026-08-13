
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''                              else if (result.type === 'op_bill' || result.type === 'ip_bill') {
                                // For now just navigate to billing or show report
                                setActiveTab('billing');
                              }'''

new_code = '''                              else if (result.type === 'op_bill') {
                                setActiveTab('billing');
                              }
                              else if (result.type === 'ip_bill') {
                                setActiveTab('billing');
                              }'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced search bills onClick')
else:
    print('old_code not found')

