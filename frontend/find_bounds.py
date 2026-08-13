
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if '{activeTab === \'lab_results\' && (' in line:
        print(f'Start: {i}')
    if '{activeTab === \'lab_reports_new\' && (' in line:
        print(f'End: {i}')

