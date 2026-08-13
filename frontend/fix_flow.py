
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_register = '''      const response = await axios.post(${API_BASE}/patients/, patientForm);
      setPatients([...patients, response.data]);
      alert(Patient registered successfully! UHID: #);
      setPatientForm({ name: '', age: 0, gender: 'Male', phone: '', aadhaar: '', blood_group: '', guardian_name: '', emergency_contact: '', address: '', marital_status: 'Single', patient_category: 'General', insurance_details: '', registration_type: 'Walk-in' });
    } catch (err) {'''

new_register = '''      const response = await axios.post(${API_BASE}/patients/, patientForm);
      setPatients([...patients, response.data]);
      alert(Patient registered successfully! UHID: #);
      setPatientForm({ name: '', age: 0, gender: 'Male', phone: '', aadhaar: '', blood_group: '', guardian_name: '', emergency_contact: '', address: '', marital_status: 'Single', patient_category: 'General', insurance_details: '', registration_type: 'Walk-in' });
      // Automatically carry over to Token generation (Data Flow Validation)
      setSelectedPatientId(response.data.id);
      setActiveTab('op_token');
    } catch (err) {'''

content = content.replace(old_register, new_register)

with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Flow logic updated')

