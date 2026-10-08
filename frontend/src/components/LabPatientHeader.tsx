import { SearchableDropdown } from './SearchableDropdown';

export const LabPatientHeader = ({ patients, selectedId, onChange, labOrders, ipAdmissions }: any) => {
  const patientOptions = patients.map((p: any) => ({
    label: `${p.id} - ${p.name} - ${p.phone}`,
    value: p.id,
    id: p.id,
    name: p.name,
    phone: p.phone,
    uhid: p.aadhaar || '',
  }));

  const selectedPatient = patients.find((p: any) => p.id === selectedId);
  
  // Try to find recent order to get Doctor/Dept
  const recentOrder = labOrders.filter((o: any) => o.patient_id === selectedId).sort((a: any, b: any) => b.id - a.id)[0];
  const isIP = ipAdmissions.some((a: any) => a.patient_id === selectedId && a.status === 'Admitted');
  
  return (
    <div className="glass-card" style={{ marginBottom: '20px', padding: '15px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '20px', alignItems: 'start' }}>
        <div>
          <label style={{ fontWeight: 'bold', marginBottom: '8px', display: 'block' }}>Search & Select Patient</label>
          <SearchableDropdown 
            options={patientOptions}
            value={selectedId}
            onChange={onChange}
            placeholder="Search ID, Name, Mobile, UHID..."
            searchKeys={['id', 'name', 'phone', 'uhid']}
          />
        </div>
        {selectedPatient && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', background: 'var(--bg-card)', padding: '15px', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <div><small style={{color:'var(--text-muted)'}}>Patient Name</small><br/><b>{selectedPatient.name}</b></div>
            <div><small style={{color:'var(--text-muted)'}}>ID / UHID</small><br/><b>{selectedPatient.id} / {selectedPatient.aadhaar || 'N/A'}</b></div>
            <div><small style={{color:'var(--text-muted)'}}>Age / Gender</small><br/><b>{selectedPatient.age} / {selectedPatient.gender}</b></div>
            <div><small style={{color:'var(--text-muted)'}}>Mobile / Blood</small><br/><b>{selectedPatient.phone} / {selectedPatient.blood_group || 'N/A'}</b></div>
            <div><small style={{color:'var(--text-muted)'}}>Visit Type</small><br/><b>{isIP ? 'IP Admission' : 'OP Visit'}</b></div>
            <div><small style={{color:'var(--text-muted)'}}>Doctor</small><br/><b>{recentOrder ? recentOrder.doctor_name || 'Walk-in' : 'N/A'}</b></div>
            <div><small style={{color:'var(--text-muted)'}}>Visit Date</small><br/><b>{recentOrder ? new Date(recentOrder.created_at || Date.now()).toLocaleDateString() : 'N/A'}</b></div>
          </div>
        )}
      </div>
    </div>
  );
};
