
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

new_handler = '''  const handleLabWalkinRegistration = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientForm.name || patientForm.age <= 0) return alert('Please fill correct name and age');
    try {
      const payload = {
        name: patientForm.name,
        age: patientForm.age,
        gender: patientForm.gender,
        phone: patientForm.phone,
        address: patientForm.address,
        aadhaar: patientForm.aadhaar,
        blood_group: patientForm.blood_group,
        details: {
          occupation: patientForm.occupation,
          marital_status: patientForm.marital_status,
          guardian_name: patientForm.guardian_name,
          emergency_contact: patientForm.emergency_contact,
          insurance_details: patientForm.insurance_details,
          referral_doctor: patientForm.referral_doctor,
          patient_category: patientForm.patient_category,
          registration_type: patientForm.registration_type
        }
      };
      const res = await axios.post(${API_BASE}/patients/, payload);
      alert('Patient registered successfully!');
      setPatientForm({
        name: '', age: 0, gender: 'Male', phone: '', address: '', aadhaar: '', blood_group: 'A+', occupation: '', marital_status: 'Single', guardian_name: '', emergency_contact: '', insurance_details: '', referral_doctor: '', patient_category: 'General', registration_type: 'Walk-in'
      });
      loadAllData();
      setIsLabRegistrationModalOpen(false);
      setLabDirectOrderPatientId(res.data.id);
      setIsLabOrderModalOpen(true);
    } catch (err) {
      console.error(err);
      alert('Failed to register patient');
    }
  };

  const handleCreateDirectLabOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!labDirectOrderPatientId || !labDirectOrderForm.test_id) return alert('Please select a test');
    try {
      await axios.post(${API_BASE}/lab-orders/, {
        patient_id: labDirectOrderPatientId,
        doctor_name: labDirectOrderForm.referring_doctor,
        test_id: Number(labDirectOrderForm.test_id)
      });
      alert('Lab ordered successfully!');
      setIsLabOrderModalOpen(false);
      setLabDirectOrderPatientId(null);
      setLabDirectOrderForm({ test_id: '', referring_doctor: 'Walk-in / Self' });
      loadAllData();
    } catch (err) { console.error(err); alert('Failed to order lab'); }
  };
'''

content = content.replace('  const handleRegisterPatient = async (e: React.FormEvent) => {', new_handler + '\n  const handleRegisterPatient = async (e: React.FormEvent) => {')

with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Handlers added successfully')

