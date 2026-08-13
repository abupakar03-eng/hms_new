
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_state = '''  // Lab Orders Workflow States
  const [labSearchQuery, setLabSearchQuery] = useState('');'''

new_state = '''  // Lab Direct Orders States
  const [isLabRegistrationModalOpen, setIsLabRegistrationModalOpen] = useState(false);
  const [isLabOrderModalOpen, setIsLabOrderModalOpen] = useState(false);
  const [labDirectOrderPatientId, setLabDirectOrderPatientId] = useState<number | null>(null);
  const [labDirectOrderForm, setLabDirectOrderForm] = useState({ test_id: '', referring_doctor: 'Walk-in / Self' });

  // Lab Orders Workflow States
  const [labSearchQuery, setLabSearchQuery] = useState('');'''

if old_state in content:
    content = content.replace(old_state, new_state)
    with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('State replaced successfully')
else:
    print('Failed to find old state')

