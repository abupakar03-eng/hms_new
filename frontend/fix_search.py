
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''                          onClick={() => {
                            if (result.type === 'patient') { setActiveTab('patients'); }
                            else if (result.type === 'op_token') { setActiveTab('patients'); }
                            else if (result.type === 'op_bill' || result.type === 'ip_bill') { setActiveTab('billing'); }
                            else if (result.type === 'pharmacy_bill') { setActiveTab('pharmacy'); }
                            else if (result.type === 'lab_bill') { setActiveTab('lab_reports'); }
                            else if (result.type === 'admission') { setActiveTab('ip_admissions'); }
                          }}'''

new_code = '''                          onClick={async () => {
                            try {
                              if (result.type === 'patient' || result.type === 'op_token' || result.type === 'admission') { 
                                setActiveTab('reports'); 
                                setReportType('patient'); 
                                setPatientReportId(String(result.patient_id));
                                const res = await axios.get(${API_BASE}/reports/patient/);
                                setPatientReportData(res.data);
                              }
                              else if (result.type === 'op_bill' || result.type === 'ip_bill') {
                                // For now just navigate to billing or show report
                                setActiveTab('billing');
                              }
                              else if (result.type === 'pharmacy_bill') { 
                                setActiveTab('pharmacy'); 
                              }
                              else if (result.type === 'lab_bill') { 
                                setActiveTab('lab_reports'); 
                              }
                            } catch(e) { console.error(e); }
                          }}'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.tsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced search onClick')
else:
    print('old_code not found')

