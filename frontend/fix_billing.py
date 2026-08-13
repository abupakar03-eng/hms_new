
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Auto-calculate Lab Charges for OP Billing
old_op_patient = '''                            onChange={(sel: any) => setOpBillForm({...opBillForm, patient_id: sel ? sel.value : ''})}'''

new_op_patient = '''                            onChange={(sel: any) => {
                              const patId = sel ? sel.value : '';
                              let autoLabCharges = 0;
                              if (patId) {
                                const patOrders = labOrders.filter(o => String(o.patient_id) === String(patId));
                                patOrders.forEach(o => {
                                  const test = labTestMasters.find(t => t.id === o.test_id);
                                  if (test) autoLabCharges += (test.price || 0);
                                });
                              }
                              setOpBillForm({...opBillForm, patient_id: patId, lab_charges: autoLabCharges});
                            }}'''

content = content.replace(old_op_patient, new_op_patient)

# Auto-calculate Lab Charges for IP Billing
old_ip_patient = '''                            onChange={(sel: any) => setIpBillForm({...ipBillForm, patient_id: sel ? sel.value : ''})}'''

new_ip_patient = '''                            onChange={(sel: any) => {
                              const patId = sel ? sel.value : '';
                              let autoLabCharges = 0;
                              if (patId) {
                                const patOrders = labOrders.filter(o => String(o.patient_id) === String(patId));
                                patOrders.forEach(o => {
                                  const test = labTestMasters.find(t => t.id === o.test_id);
                                  if (test) autoLabCharges += (test.price || 0);
                                });
                              }
                              setIpBillForm({...ipBillForm, patient_id: patId, lab_charges: autoLabCharges});
                            }}'''

content = content.replace(old_ip_patient, new_ip_patient)

with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Billing Integration Complete')

