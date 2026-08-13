
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_appt = '''                          await axios.post(${API_BASE}/appointments/, {
                            ...appointmentForm,
                            patient_id: Number(appointmentForm.patient_id)
                          });'''

new_appt = '''                          await axios.post(${API_BASE}/appointments/, {
                            ...appointmentForm,
                            patient_id: Number(appointmentForm.patient_id),
                            doctor_id: appointmentForm.doctor_id ? Number(appointmentForm.doctor_id) : null
                          });'''

content = content.replace(old_appt, new_appt)

with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed appointment submission')

