
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix Token Select
old_token_select = '''                      <Select
                        options={patients.map(p => ({ value: p.id, label: ${p.name} (Age: , ) }))}
                        onChange={(opt: any) => setSelectedPatientId(opt ? opt.value : '')}
                        styles={selectStyles}
                        isClearable
                      />'''
new_token_select = '''                      <Select
                        options={patients.map(p => ({ value: p.id, label: ${p.name} (Age: , ) }))}
                        value={selectedPatientId ? { value: selectedPatientId, label: patients.find(p => p.id === selectedPatientId)?.name + ' (Age: ' + patients.find(p => p.id === selectedPatientId)?.age + ')' } : null}
                        onChange={(opt: any) => setSelectedPatientId(opt ? opt.value : '')}
                        styles={selectStyles}
                        isClearable
                      />'''
content = content.replace(old_token_select, new_token_select)

# Fix Appointment Select
old_appt_select = '''                      <Select
                        options={patients.map(p => ({ value: p.id, label: ${p.name} (Age: , ) }))}
                        onChange={(opt: any) => setAppointmentForm({ ...appointmentForm, patient_id: opt ? opt.value : '' })}
                        styles={selectStyles}
                        isClearable
                      />'''
new_appt_select = '''                      <Select
                        options={patients.map(p => ({ value: p.id, label: ${p.name} (Age: , ) }))}
                        value={appointmentForm.patient_id ? { value: Number(appointmentForm.patient_id), label: patients.find(p => p.id === Number(appointmentForm.patient_id))?.name + ' (Age: ' + patients.find(p => p.id === Number(appointmentForm.patient_id))?.age + ')' } : null}
                        onChange={(opt: any) => setAppointmentForm({ ...appointmentForm, patient_id: opt ? opt.value : '' })}
                        styles={selectStyles}
                        isClearable
                      />'''
content = content.replace(old_appt_select, new_appt_select)

with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed select props')

