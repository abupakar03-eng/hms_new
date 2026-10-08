/**
 * Patient self-service portal.
 *
 * Rendered instead of the staff shell whenever the signed-in account has the
 * "Patient" role. Every request it makes goes to `/portal/*`, which the backend
 * scopes to the caller's own patient id — the component never sends a patient id.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { confirmDialog } from './ui/feedback';
import {
  Activity, Calendar, Clipboard, Download, FileText, FlaskConical, Loader2, LogOut,
  Printer, Receipt, RefreshCw, Save, Shield, UserRound, X, CheckCircle2, AlertTriangle,
} from 'lucide-react';
import { API_BASE, REFRESH_KEY, api, clearSession, errorMessage } from './api';

type Tab = 'overview' | 'appointments' | 'prescriptions' | 'labs' | 'bills' | 'documents' | 'profile';

interface Profile {
  id: number; name: string; age: number; gender: string; phone?: string | null;
  email?: string | null; address?: string | null; aadhaar_masked?: string | null;
  blood_group?: string | null; username?: string | null; details?: Record<string, any>;
  created_at?: string | null;
}
interface Appointment {
  id: number; doctor_id?: number | null; doctor_name?: string | null;
  appointment_date: string; time_slot?: string | null; reason?: string | null;
  status: string; created_at?: string | null;
}
interface Doctor { id: number; name: string; department?: string | null }
interface Medicine {
  name: string; quantity?: number | null; dosage?: string | null; duration?: string | null;
  instructions?: string | null; timing_morning?: boolean | null; timing_afternoon?: boolean | null;
  timing_night?: boolean | null; timing_relation?: string | null;
}
interface Prescription {
  id: number; date: string; doctor_name?: string | null; diagnosis?: string | null;
  symptoms?: string | null; advice?: string | null; follow_up_date?: string | null;
  vitals_bp?: string | null; vitals_pulse?: string | null; vitals_temp?: string | null; vitals_resp?: string | null;
  medicines: Medicine[]; advised_labs: string[];
}
interface LabResultRow {
  parameter: string; result?: string | null; unit?: string | null; range?: string | null;
  flag?: string | null; remarks?: string | null;
}
interface LabOrder {
  id: number; test_name: string; order_date: string; status: string; priority: string;
  due_at?: string | null; report_ready: boolean; report_id?: number | null;
}
interface LabReport {
  id: number; order_id?: number | null; test_name: string; date_conducted: string;
  status: string; is_abnormal: boolean; reported_by?: string | null; verified_by?: string | null;
  verified_at?: string | null; interpretation?: string | null; results: LabResultRow[];
}
interface Bill {
  id: number; bill_type: string; bill_date: string; description: string;
  subtotal: number; discount: number; gst: number; total: number;
  payment_mode?: string | null; status?: string | null; items: any[];
}
interface DocumentRow {
  type: string; id: number; title: string; date?: string | null;
  subtitle?: string | null; downloadable: boolean;
}
interface Dashboard {
  profile: Profile; next_appointment?: Appointment | null; upcoming_appointments: number;
  pending_lab_tests: number; ready_reports: number; abnormal_reports: number; prescriptions: number;
  outstanding_bills: number; total_billed: number; active_insurance: number;
  recent_lab_orders: LabOrder[]; recent_documents: DocumentRow[];
}

const HOSPITAL_NAME = 'MedBill Pro Hospital';
const money = (n: number) => `₹${(n ?? 0).toFixed(2)}`;
const flagIsAbnormal = (f?: string | null) => !!f && f !== 'Normal';
const statusClass = (s: string) => `status-badge ${(s || '').replace(/ /g, '-').toLowerCase()}`;

export default function PatientPortal({ user, onLogout, theme, onToggleTheme }: {
  user: { username: string; patient_id?: number | null; full_name?: string | null };
  onLogout: () => void;
  theme: string;
  onToggleTheme: () => void;
}) {
  const [tab, setTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ msg: string; kind: 'ok' | 'err' } | null>(null);

  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [slots, setSlots] = useState<string[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [labOrders, setLabOrders] = useState<LabOrder[]>([]);
  const [labReports, setLabReports] = useState<LabReport[]>([]);
  const [bills, setBills] = useState<Bill[]>([]);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [insurance, setInsurance] = useState<{ policies: any[]; claims: any[] }>({ policies: [], claims: [] });

  const [bookForm, setBookForm] = useState({
    doctor_id: '', appointment_date: new Date().toISOString().split('T')[0], time_slot: '', reason: '',
  });
  const [profileForm, setProfileForm] = useState({ phone: '', email: '', address: '', blood_group: '' });
  const [openReport, setOpenReport] = useState<LabReport | null>(null);

  const notify = (msg: string, kind: 'ok' | 'err' = 'ok') => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 3500);
  };

  const loadAll = async () => {
    setLoading(true);
    try {
      const [dash, appts, docs, slotList, presc, orders, reports, billList, docList, ins] = await Promise.all([
        api.get(`${API_BASE}/portal/dashboard`),
        api.get(`${API_BASE}/portal/appointments`),
        api.get(`${API_BASE}/portal/doctors`),
        api.get(`${API_BASE}/portal/slots`),
        api.get(`${API_BASE}/portal/prescriptions`),
        api.get(`${API_BASE}/portal/lab-orders`),
        api.get(`${API_BASE}/portal/lab-reports`),
        api.get(`${API_BASE}/portal/bills`),
        api.get(`${API_BASE}/portal/documents`),
        api.get(`${API_BASE}/portal/insurance`),
      ]);
      setDashboard(dash.data);
      setAppointments(appts.data);
      setDoctors(docs.data);
      setSlots(slotList.data);
      setPrescriptions(presc.data);
      setLabOrders(orders.data);
      setLabReports(reports.data);
      setBills(billList.data);
      setDocuments(docList.data);
      setInsurance(ins.data);
      setProfileForm({
        phone: dash.data.profile.phone || '',
        email: dash.data.profile.email || '',
        address: dash.data.profile.address || '',
        blood_group: dash.data.profile.blood_group || '',
      });
      if (!bookForm.time_slot && slotList.data.length) {
        setBookForm(prev => ({ ...prev, time_slot: slotList.data[0] }));
      }
    } catch (err) {
      notify(errorMessage(err, 'Could not load your records.'), 'err');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const handleLogout = async () => {
    try { await api.post(`${API_BASE}/logout`, { refresh_token: localStorage.getItem(REFRESH_KEY) }); } catch { /* token may already be gone */ }
    clearSession();
    onLogout();
  };

  const bookAppointment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bookForm.appointment_date || !bookForm.time_slot) return notify('Choose a date and a time slot.', 'err');
    setBusy(true);
    try {
      await api.post(`${API_BASE}/portal/appointments`, {
        doctor_id: bookForm.doctor_id ? Number(bookForm.doctor_id) : null,
        appointment_date: bookForm.appointment_date,
        time_slot: bookForm.time_slot,
        reason: bookForm.reason || null,
      });
      notify('Appointment booked. Please arrive 10 minutes early.');
      setBookForm(prev => ({ ...prev, reason: '' }));
      await loadAll();
    } catch (err) {
      notify(errorMessage(err, 'Could not book that appointment.'), 'err');
    } finally {
      setBusy(false);
    }
  };

  const cancelAppointment = async (id: number) => {
    if (!(await confirmDialog('The slot will be released for other patients.', { title: 'Cancel this appointment?', confirmLabel: 'Cancel appointment', danger: true }))) return;
    try {
      await api.put(`${API_BASE}/portal/appointments/${id}/cancel`);
      notify('Appointment cancelled.');
      await loadAll();
    } catch (err) {
      notify(errorMessage(err, 'Could not cancel.'), 'err');
    }
  };

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.put(`${API_BASE}/portal/me`, {
        phone: profileForm.phone || null,
        email: profileForm.email || null,
        address: profileForm.address || null,
        blood_group: profileForm.blood_group || null,
      });
      notify('Contact details updated.');
      await loadAll();
    } catch (err) {
      notify(errorMessage(err, 'Could not save your details.'), 'err');
    } finally {
      setBusy(false);
    }
  };

  // ---- printing ----------------------------------------------------------
  const printHtml = (title: string, inner: string) => {
    const win = window.open('', '_blank', 'width=900,height=1000');
    if (!win) return notify('Allow pop-ups to print.', 'err');
    win.document.write(`<html><head><title>${title}</title><style>
      body{font-family:Arial,sans-serif;padding:28px;color:#111}
      .head{text-align:center;border-bottom:2px solid #1e40af;padding-bottom:10px;margin-bottom:16px}
      .head h1{margin:0;color:#1e40af;font-size:20px}
      .head p{margin:3px 0;color:#666;font-size:12px}
      .meta{display:flex;justify-content:space-between;font-size:13px;margin-bottom:14px}
      table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
      th{background:#1e40af;color:#fff;padding:7px;text-align:left}
      td{padding:6px;border-bottom:1px solid #e5e7eb}
      tr.abnormal td{background:#fef2f2;color:#991b1b;font-weight:600}
      h3{margin:14px 0 6px}
      .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px}
      .foot{margin-top:26px;font-size:11px;color:#888;text-align:center}
      @media print{body{padding:8px}}
    </style></head><body>
      <div class="head"><h1>${HOSPITAL_NAME}</h1><p>Patient copy</p></div>
      ${inner}
      <div class="foot">Computer-generated document. Please correlate clinically.</div>
    </body></html>`);
    win.document.close();
    win.focus();
    win.print();
  };

  const printReport = (r: LabReport) => {
    const rows = (r.results || []).map(row => `
      <tr class="${flagIsAbnormal(row.flag) ? 'abnormal' : ''}">
        <td>${row.parameter}</td><td><b>${row.result ?? '-'}</b></td>
        <td>${row.unit || ''}</td><td>${row.range || ''}</td><td>${row.flag || ''}</td>
      </tr>`).join('');
    printHtml(`Lab Report ${r.id}`, `
      <div class="meta">
        <div><b>Patient:</b> ${dashboard?.profile.name || user.full_name || user.username}<br>
             <b>Age / Gender:</b> ${dashboard?.profile.age ?? '-'} / ${dashboard?.profile.gender ?? '-'}</div>
        <div style="text-align:right"><b>Report No:</b> #${r.id}<br>
             <b>Date:</b> ${new Date(r.date_conducted).toLocaleString()}<br>
             <b>Referred by:</b> ${r.reported_by || '-'}</div>
      </div>
      <h3>${r.test_name}
        <span class="badge" style="background:${r.is_abnormal ? '#fee2e2' : '#dcfce7'};color:${r.is_abnormal ? '#991b1b' : '#166534'}">
          ${r.is_abnormal ? 'ABNORMAL' : 'NORMAL'}</span></h3>
      <table><thead><tr><th>Parameter</th><th>Result</th><th>Unit</th><th>Reference</th><th>Flag</th></tr></thead>
      <tbody>${rows}</tbody></table>
      ${r.interpretation ? `<p><b>Interpretation:</b> ${r.interpretation}</p>` : ''}
      <div class="meta" style="margin-top:20px">
        <div>Status: <b>${r.status}</b></div>
        <div style="text-align:right">Verified by: <b>${r.verified_by || '-'}</b></div>
      </div>`);
  };

  const printPrescription = (p: Prescription) => {
    const meds = (p.medicines || []).map(m => {
      const timing = [m.timing_morning && 'Morning', m.timing_afternoon && 'Afternoon', m.timing_night && 'Night']
        .filter(Boolean).join(', ');
      return `<tr><td>${m.name}</td><td>${m.quantity ?? '-'}</td><td>${m.duration || '-'}</td>
              <td>${timing || m.dosage || '-'}${m.timing_relation ? ` (${m.timing_relation})` : ''}</td>
              <td>${m.instructions || '-'}</td></tr>`;
    }).join('');
    printHtml(`Prescription ${p.id}`, `
      <div class="meta">
        <div><b>Patient:</b> ${dashboard?.profile.name || user.full_name || user.username}<br>
             <b>Age / Gender:</b> ${dashboard?.profile.age ?? '-'} / ${dashboard?.profile.gender ?? '-'}</div>
        <div style="text-align:right"><b>Date:</b> ${new Date(p.date).toLocaleDateString()}<br>
             <b>Doctor:</b> ${p.doctor_name || '-'}</div>
      </div>
      ${p.diagnosis ? `<p><b>Diagnosis:</b> ${p.diagnosis}</p>` : ''}
      ${p.symptoms ? `<p><b>Complaints:</b> ${p.symptoms}</p>` : ''}
      <h3>Medicines</h3>
      <table><thead><tr><th>Medicine</th><th>Qty</th><th>Duration</th><th>When</th><th>Notes</th></tr></thead>
      <tbody>${meds || '<tr><td colspan="5">No medicines prescribed</td></tr>'}</tbody></table>
      ${p.advised_labs?.length ? `<p><b>Advised tests:</b> ${p.advised_labs.join(', ')}</p>` : ''}
      ${p.advice ? `<p><b>Advice:</b> ${p.advice}</p>` : ''}
      ${p.follow_up_date ? `<p><b>Follow-up:</b> ${new Date(p.follow_up_date).toLocaleDateString()}</p>` : ''}`);
  };

  const printBill = (b: Bill) => {
    const items = (b.items || [])
      .filter(i => (i.amount ?? 0) > 0 || i.name)
      .map(i => `<tr><td>${i.name}</td><td>${i.quantity ?? ''}</td><td>${money(i.amount ?? 0)}</td></tr>`).join('');
    printHtml(`${b.bill_type} Bill ${b.id}`, `
      <div class="meta">
        <div><b>Patient:</b> ${dashboard?.profile.name || user.full_name || user.username}</div>
        <div style="text-align:right"><b>Bill No:</b> ${b.bill_type}-${b.id}<br>
             <b>Date:</b> ${new Date(b.bill_date).toLocaleString()}<br>
             <b>Payment:</b> ${b.payment_mode || '-'}</div>
      </div>
      <table><thead><tr><th>Description</th><th>Qty</th><th>Amount</th></tr></thead><tbody>${items}</tbody></table>
      <div style="text-align:right;margin-top:12px;font-size:13px">
        <p>Subtotal: ${money(b.subtotal)}</p>
        ${b.discount ? `<p>Discount (${b.discount}%): -${money((b.discount / 100) * b.subtotal)}</p>` : ''}
        ${b.gst ? `<p>GST (${b.gst}%): +${money((b.gst / 100) * (b.subtotal - (b.discount / 100) * b.subtotal))}</p>` : ''}
        <p style="font-size:17px;font-weight:bold;color:#1e40af">Total: ${money(b.total)}</p>
      </div>`);
  };

  const exportCsv = (rows: Record<string, any>[], filename: string) => {
    if (!rows.length) return notify('Nothing to export yet.', 'err');
    const headers = Object.keys(rows[0]);
    const csv = [
      headers.join(','),
      ...rows.map(r => headers.map(h => `"${String(r[h] ?? '').replace(/"/g, '""')}"`).join(',')),
    ].join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  const upcoming = useMemo(
    () => appointments.filter(a => a.status !== 'Cancelled' && new Date(a.appointment_date) >= new Date(new Date().toDateString())),
    [appointments],
  );
  const past = useMemo(
    () => appointments.filter(a => !upcoming.some(u => u.id === a.id)),
    [appointments, upcoming],
  );

  const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'overview', label: 'Overview', icon: <Activity size={18} /> },
    { key: 'appointments', label: 'Appointments', icon: <Calendar size={18} /> },
    { key: 'prescriptions', label: 'Prescriptions', icon: <Clipboard size={18} /> },
    { key: 'labs', label: 'Lab Reports', icon: <FlaskConical size={18} /> },
    { key: 'bills', label: 'Bills', icon: <Receipt size={18} /> },
    { key: 'documents', label: 'Documents', icon: <FileText size={18} /> },
    { key: 'profile', label: 'My Profile', icon: <UserRound size={18} /> },
  ];

  const card = (children: React.ReactNode, style: React.CSSProperties = {}) => (
    <div className="glass-card" style={{ padding: '18px', ...style }}>{children}</div>
  );

  return (
    <div className="app-container" style={{ display: 'block' }}>
      {/* Portal header */}
      <div className="top-navbar no-print" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 24px', background: 'var(--bg-card)', borderBottom: '1px solid var(--border)', position: 'sticky', top: 0, zIndex: 95 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Activity size={22} style={{ color: 'var(--accent-blue)' }} />
          <b>MedBill Pro</b>
          <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Patient Portal</span>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button className="btn btn-secondary" onClick={loadAll} title="Refresh"><RefreshCw size={16} /></button>
          <button className="btn btn-secondary" onClick={onToggleTheme} title="Toggle theme">
            {theme === 'dark' ? '☀' : '☾'}
          </button>
          <div style={{ textAlign: 'right', lineHeight: 1.2, marginRight: '6px' }}>
            <div style={{ fontWeight: 600, fontSize: '14px' }}>{dashboard?.profile.name || user.full_name || user.username}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {dashboard?.profile.id ? `Patient ID ${dashboard.profile.id}` : ''}
            </div>
          </div>
          <button className="btn btn-secondary" onClick={handleLogout}><LogOut size={16} /> Sign out</button>
        </div>
      </div>

      <div style={{ padding: '20px 24px', maxWidth: '1280px', margin: '0 auto' }}>
        {/* Tabs */}
        <div className="no-print" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '18px' }}>
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="btn"
              style={{
                display: 'flex', alignItems: 'center', gap: '7px', padding: '9px 16px', borderRadius: '20px',
                border: 'none', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
                background: tab === t.key ? 'linear-gradient(135deg,#3b82f6,#2563eb)' : 'rgba(255,255,255,0.07)',
                color: tab === t.key ? '#fff' : 'var(--text-muted)',
              }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px' }}>
            <Loader2 size={32} className="spin" /> <p style={{ color: 'var(--text-muted)' }}>Loading your records…</p>
          </div>
        ) : (
          <>
            {/* ---------------- OVERVIEW ---------------- */}
            {tab === 'overview' && dashboard && (
              <>
                <div className="dashboard-grid">
                  {[
                    { label: 'Upcoming appointments', value: dashboard.upcoming_appointments, icon: <Calendar size={24} />, color: 'var(--accent-blue)' },
                    { label: 'Tests in progress', value: dashboard.pending_lab_tests, icon: <FlaskConical size={24} />, color: 'var(--accent-amber)' },
                    { label: 'Reports ready', value: dashboard.ready_reports, icon: <FileText size={24} />, color: 'var(--accent-emerald)' },
                    { label: 'Abnormal results', value: dashboard.abnormal_reports, icon: <AlertTriangle size={24} />, color: 'var(--accent-rose)' },
                    { label: 'Prescriptions', value: dashboard.prescriptions, icon: <Clipboard size={24} />, color: 'var(--accent-violet)' },
                    { label: 'Total billed', value: money(dashboard.total_billed), icon: <Receipt size={24} />, color: 'var(--accent-sky)' },
                  ].map(s => (
                    <div className="stat-card" key={s.label}>
                      <div className="stat-icon" style={{ background: `${s.color}1a`, color: s.color }}>{s.icon}</div>
                      <div><h3 style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>{s.label}</h3>
                        <h2 style={{ margin: 0 }}>{s.value}</h2></div>
                    </div>
                  ))}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  {card(
                    <>
                      <h3 style={{ marginTop: 0 }}>Next appointment</h3>
                      {dashboard.next_appointment ? (
                        <>
                          <p style={{ margin: '4px 0', fontSize: '15px' }}>
                            <b>{new Date(dashboard.next_appointment.appointment_date).toDateString()}</b> at {dashboard.next_appointment.time_slot}
                          </p>
                          <p style={{ margin: '4px 0', color: 'var(--text-muted)' }}>
                            {dashboard.next_appointment.doctor_name || 'Any available doctor'}
                          </p>
                          <span className={statusClass(dashboard.next_appointment.status)}>{dashboard.next_appointment.status}</span>
                        </>
                      ) : (
                        <p style={{ color: 'var(--text-muted)' }}>No upcoming appointment.
                          <button className="btn btn-secondary" style={{ marginLeft: '10px' }} onClick={() => setTab('appointments')}>Book now</button>
                        </p>
                      )}
                    </>,
                  )}

                  {card(
                    <>
                      <h3 style={{ marginTop: 0 }}>Recent test progress</h3>
                      {dashboard.recent_lab_orders.length === 0 && <p style={{ color: 'var(--text-muted)' }}>No lab tests yet.</p>}
                      {dashboard.recent_lab_orders.map(o => (
                        <div key={o.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: '14px' }}>{o.test_name}</div>
                            <small style={{ color: 'var(--text-muted)' }}>{new Date(o.order_date).toLocaleDateString()}</small>
                          </div>
                          <span className={statusClass(o.status)}>{o.status}</span>
                        </div>
                      ))}
                    </>,
                  )}
                </div>

                {card(
                  <>
                    <h3 style={{ marginTop: 0 }}>Recent documents</h3>
                    {dashboard.recent_documents.length === 0 && <p style={{ color: 'var(--text-muted)' }}>Nothing here yet.</p>}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '10px' }}>
                      {dashboard.recent_documents.map(d => (
                        <div key={`${d.type}-${d.id}`} style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '10px' }}>
                          <div style={{ fontWeight: 600, fontSize: '13px' }}>{d.title}</div>
                          <small style={{ color: 'var(--text-muted)' }}>{d.subtitle}</small><br />
                          <small style={{ color: 'var(--text-muted)' }}>{d.date ? new Date(d.date).toLocaleDateString() : ''}</small>
                        </div>
                      ))}
                    </div>
                    <button className="btn btn-secondary" style={{ marginTop: '12px' }} onClick={() => setTab('documents')}>All documents</button>
                  </>,
                  { marginTop: '16px' },
                )}
              </>
            )}

            {/* ---------------- APPOINTMENTS ---------------- */}
            {tab === 'appointments' && (
              <>
                {card(
                  <form onSubmit={bookAppointment}>
                    <h3 style={{ marginTop: 0 }}>Book an appointment</h3>
                    <div className="form-grid">
                      <div className="form-group">
                        <label>Date *</label>
                        <input type="date" required min={new Date().toISOString().split('T')[0]}
                          value={bookForm.appointment_date}
                          onChange={e => setBookForm({ ...bookForm, appointment_date: e.target.value })} />
                      </div>
                      <div className="form-group">
                        <label>Time slot *</label>
                        <select value={bookForm.time_slot} onChange={e => setBookForm({ ...bookForm, time_slot: e.target.value })}>
                          <option value="">-- choose --</option>
                          {slots.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Doctor</label>
                        <select value={bookForm.doctor_id} onChange={e => setBookForm({ ...bookForm, doctor_id: e.target.value })}>
                          <option value="">Any available doctor</option>
                          {doctors.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Reason for visit</label>
                        <input type="text" placeholder="e.g. Fever since 2 days"
                          value={bookForm.reason} onChange={e => setBookForm({ ...bookForm, reason: e.target.value })} />
                      </div>
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={busy} style={{ marginTop: '10px' }}>
                      {busy ? <><Loader2 size={16} className="spin" /> Booking…</> : <><Calendar size={16} /> Book appointment</>}
                    </button>
                  </form>,
                )}

                {card(
                  <>
                    <h3 style={{ marginTop: 0 }}>Upcoming ({upcoming.length})</h3>
                    <div className="table-container">
                      <table>
                        <thead><tr><th>Date</th><th>Time</th><th>Doctor</th><th>Reason</th><th>Status</th><th></th></tr></thead>
                        <tbody>
                          {upcoming.map(a => (
                            <tr key={a.id}>
                              <td>{new Date(a.appointment_date).toDateString()}</td>
                              <td>{a.time_slot}</td>
                              <td>{a.doctor_name || 'Any available'}</td>
                              <td>{a.reason || '-'}</td>
                              <td><span className={statusClass(a.status)}>{a.status}</span></td>
                              <td>
                                <button className="btn btn-danger" style={{ padding: '4px 10px', fontSize: '12px' }}
                                  onClick={() => cancelAppointment(a.id)}>Cancel</button>
                              </td>
                            </tr>
                          ))}
                          {upcoming.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No upcoming appointments.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                  </>,
                  { marginTop: '16px' },
                )}

                <details style={{ marginTop: '16px' }}>
                  <summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>Past appointments ({past.length})</summary>
                  {card(
                    <div className="table-container">
                      <table>
                        <thead><tr><th>Date</th><th>Time</th><th>Doctor</th><th>Status</th></tr></thead>
                        <tbody>
                          {past.map(a => (
                            <tr key={a.id}>
                              <td>{new Date(a.appointment_date).toDateString()}</td>
                              <td>{a.time_slot}</td>
                              <td>{a.doctor_name || '-'}</td>
                              <td><span className={statusClass(a.status)}>{a.status}</span></td>
                            </tr>
                          ))}
                          {past.length === 0 && <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Nothing yet.</td></tr>}
                        </tbody>
                      </table>
                    </div>,
                    { marginTop: '10px' },
                  )}
                </details>
              </>
            )}

            {/* ---------------- PRESCRIPTIONS ---------------- */}
            {tab === 'prescriptions' && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h2 style={{ margin: 0 }}>My prescriptions</h2>
                  <button className="btn btn-secondary" onClick={() => exportCsv(
                    prescriptions.flatMap(p => p.medicines.map(m => ({ date: p.date, doctor: p.doctor_name, diagnosis: p.diagnosis, medicine: m.name, quantity: m.quantity, duration: m.duration }))),
                    'my_prescriptions.csv')}><Download size={16} /> Export CSV</button>
                </div>
                {prescriptions.length === 0 && card(<p style={{ color: 'var(--text-muted)' }}>No prescriptions available yet.</p>)}
                {prescriptions.map(p => (
                  <div key={p.id} className="glass-card" style={{ padding: '18px', marginBottom: '14px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                      <div>
                        <h3 style={{ margin: 0 }}>{new Date(p.date).toDateString()}</h3>
                        <small style={{ color: 'var(--text-muted)' }}>{p.doctor_name || 'Doctor not recorded'}</small>
                      </div>
                      <button className="btn btn-secondary" onClick={() => printPrescription(p)}><Printer size={16} /> Print</button>
                    </div>
                    {p.diagnosis && <p style={{ marginTop: '10px' }}><b>Diagnosis:</b> {p.diagnosis}</p>}
                    <div className="table-container" style={{ marginTop: '10px' }}>
                      <table>
                        <thead><tr><th>Medicine</th><th>Qty</th><th>Duration</th><th>When</th><th>Notes</th></tr></thead>
                        <tbody>
                          {p.medicines.map((m, i) => (
                            <tr key={i}>
                              <td>{m.name}</td>
                              <td>{m.quantity ?? '-'}</td>
                              <td>{m.duration || '-'}</td>
                              <td>{[m.timing_morning && 'Morning', m.timing_afternoon && 'Afternoon', m.timing_night && 'Night'].filter(Boolean).join(', ') || m.dosage || '-'}</td>
                              <td>{m.instructions || '-'}</td>
                            </tr>
                          ))}
                          {p.medicines.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No medicines recorded.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                    {p.advised_labs?.length > 0 && <p style={{ marginTop: '8px' }}><b>Advised tests:</b> {p.advised_labs.join(', ')}</p>}
                    {p.advice && <p><b>Advice:</b> {p.advice}</p>}
                    {p.follow_up_date && <p><b>Follow-up:</b> {new Date(p.follow_up_date).toDateString()}</p>}
                  </div>
                ))}
              </>
            )}

            {/* ---------------- LAB ---------------- */}
            {tab === 'labs' && (
              <>
                {card(
                  <>
                    <h3 style={{ marginTop: 0 }}>Test progress</h3>
                    <div className="table-container">
                      <table>
                        <thead><tr><th>Test</th><th>Ordered</th><th>Priority</th><th>Expected by</th><th>Status</th><th></th></tr></thead>
                        <tbody>
                          {labOrders.map(o => (
                            <tr key={o.id}>
                              <td>{o.test_name}</td>
                              <td>{new Date(o.order_date).toLocaleDateString()}</td>
                              <td>{o.priority}</td>
                              <td>{o.due_at ? new Date(o.due_at).toLocaleString() : '-'}</td>
                              <td><span className={statusClass(o.status)}>{o.status}</span></td>
                              <td>
                                {o.report_ready && (
                                  <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                                    onClick={() => {
                                      const r = labReports.find(x => x.id === o.report_id);
                                      if (r) setOpenReport(r);
                                      else notify('Report is being finalised.', 'err');
                                    }}><FileText size={14} /> View report</button>
                                )}
                              </td>
                            </tr>
                          ))}
                          {labOrders.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No lab tests ordered.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                  </>,
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '20px 0 10px' }}>
                  <h2 style={{ margin: 0 }}>My lab reports</h2>
                  <button className="btn btn-secondary" onClick={() => exportCsv(
                    labReports.flatMap(r => (r.results || []).map(row => ({ report: r.id, test: r.test_name, date: new Date(r.date_conducted).toLocaleDateString(), parameter: row.parameter, result: row.result, unit: row.unit, range: row.range, flag: row.flag }))),
                    'my_lab_reports.csv')}><Download size={16} /> Export CSV</button>
                </div>
                {labReports.length === 0 && card(<p style={{ color: 'var(--text-muted)' }}>No reports published yet.</p>)}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '14px' }}>
                  {labReports.map(r => (
                    <div key={r.id} className="glass-card" style={{ padding: '16px', borderLeft: r.is_abnormal ? '4px solid #ef4444' : '4px solid #10b981' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div style={{ fontWeight: 700 }}>{r.test_name}</div>
                          <small style={{ color: 'var(--text-muted)' }}>{new Date(r.date_conducted).toLocaleDateString()}</small>
                        </div>
                        {r.is_abnormal
                          ? <span className="status-badge cancelled">Abnormal</span>
                          : <span className="status-badge completed">Normal</span>}
                      </div>
                      <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                        <button className="btn btn-secondary" onClick={() => setOpenReport(r)}><FileText size={15} /> View</button>
                        <button className="btn btn-secondary" onClick={() => printReport(r)}><Printer size={15} /> Print</button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* ---------------- BILLS ---------------- */}
            {tab === 'bills' && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h2 style={{ margin: 0 }}>My bills</h2>
                  <button className="btn btn-secondary" onClick={() => exportCsv(
                    bills.map(b => ({ type: b.bill_type, id: b.id, date: new Date(b.bill_date).toLocaleDateString(), description: b.description, total: b.total, status: b.status })),
                    'my_bills.csv')}><Download size={16} /> Export CSV</button>
                </div>
                {bills.length === 0 && card(<p style={{ color: 'var(--text-muted)' }}>No bills yet.</p>)}
                {bills.map(b => (
                  <div key={`${b.bill_type}-${b.id}`} className="glass-card" style={{ padding: '16px', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                      <div>
                        <div style={{ fontWeight: 700 }}>{b.bill_type} bill #{b.id}</div>
                        <small style={{ color: 'var(--text-muted)' }}>{new Date(b.bill_date).toLocaleString()} · {b.description}</small>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '19px', fontWeight: 700 }}>{money(b.total)}</div>
                        <small style={{ color: 'var(--text-muted)' }}>{b.payment_mode || '-'} · {b.status}</small>
                      </div>
                    </div>
                    {(b.items || []).length > 0 && (
                      <div className="table-container" style={{ marginTop: '10px' }}>
                        <table>
                          <thead><tr><th>Item</th><th>Qty</th><th>Amount</th></tr></thead>
                          <tbody>
                            {b.items.filter(i => i.name).map((i, idx) => (
                              <tr key={idx}>
                                <td>{i.name}</td>
                                <td>{i.quantity ?? '-'}</td>
                                <td>{money(i.amount ?? 0)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                    <button className="btn btn-secondary" style={{ marginTop: '10px' }} onClick={() => printBill(b)}>
                      <Printer size={15} /> Print
                    </button>
                  </div>
                ))}
              </>
            )}

            {/* ---------------- DOCUMENTS ---------------- */}
            {tab === 'documents' && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h2 style={{ margin: 0 }}>My documents</h2>
                  <button className="btn btn-secondary" onClick={() => exportCsv(
                    documents.map(d => ({ type: d.type, title: d.title, date: d.date ? new Date(d.date).toLocaleDateString() : '', details: d.subtitle })),
                    'my_documents.csv')}><Download size={16} /> Export list</button>
                </div>
                {card(
                  <div className="table-container">
                    <table>
                      <thead><tr><th>Type</th><th>Document</th><th>Date</th><th>Details</th><th></th></tr></thead>
                      <tbody>
                        {documents.map(d => (
                          <tr key={`${d.type}-${d.id}`}>
                            <td style={{ textTransform: 'capitalize' }}>{d.type.replace('_', ' ')}</td>
                            <td><b>{d.title}</b></td>
                            <td>{d.date ? new Date(d.date).toLocaleDateString() : '-'}</td>
                            <td>{d.subtitle}</td>
                            <td>
                              {d.type === 'lab_report' && (
                                <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                                  onClick={() => { const r = labReports.find(x => x.id === d.id); if (r) setOpenReport(r); }}>
                                  <FileText size={13} /> Open
                                </button>
                              )}
                              {d.type === 'prescription' && (
                                <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                                  onClick={() => { const p = prescriptions.find(x => x.id === d.id); if (p) printPrescription(p); }}>
                                  <Printer size={13} /> Print
                                </button>
                              )}
                              {d.type === 'bill' && (
                                <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                                  onClick={() => { const b = bills.find(x => x.id === d.id); if (b) printBill(b); }}>
                                  <Printer size={13} /> Print
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                        {documents.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No documents yet.</td></tr>}
                      </tbody>
                    </table>
                  </div>,
                )}
              </>
            )}

            {/* ---------------- PROFILE ---------------- */}
            {tab === 'profile' && dashboard && (
              <>
                {card(
                  <>
                    <h3 style={{ marginTop: 0 }}>Patient record</h3>
                    <div className="form-grid">
                      <div><small style={{ color: 'var(--text-muted)' }}>Patient ID</small><br /><b>{dashboard.profile.id}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Name</small><br /><b>{dashboard.profile.name}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Age / Gender</small><br /><b>{dashboard.profile.age} / {dashboard.profile.gender}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Aadhaar</small><br /><b>{dashboard.profile.aadhaar_masked || 'Not on file'}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Username</small><br /><b>{dashboard.profile.username}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Registered</small><br /><b>{dashboard.profile.created_at ? new Date(dashboard.profile.created_at).toLocaleDateString() : '-'}</b></div>
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '10px' }}>
                      Name, age and gender can only be corrected at the hospital reception.
                    </p>
                  </>,
                )}

                {card(
                  <form onSubmit={saveProfile}>
                    <h3 style={{ marginTop: 0 }}>Contact details</h3>
                    <div className="form-grid">
                      <div className="form-group">
                        <label>Mobile number</label>
                        <input type="tel" value={profileForm.phone}
                          onChange={e => setProfileForm({ ...profileForm, phone: e.target.value.replace(/\D/g, '').slice(0, 10) })} />
                      </div>
                      <div className="form-group">
                        <label>Email</label>
                        <input type="email" value={profileForm.email}
                          onChange={e => setProfileForm({ ...profileForm, email: e.target.value })} />
                      </div>
                      <div className="form-group">
                        <label>Blood group</label>
                        <select value={profileForm.blood_group} onChange={e => setProfileForm({ ...profileForm, blood_group: e.target.value })}>
                          <option value="">--</option>
                          {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(b => <option key={b}>{b}</option>)}
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Address</label>
                        <input type="text" value={profileForm.address}
                          onChange={e => setProfileForm({ ...profileForm, address: e.target.value })} />
                      </div>
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={busy} style={{ marginTop: '10px' }}>
                      {busy ? <><Loader2 size={16} className="spin" /> Saving…</> : <><Save size={16} /> Save changes</>}
                    </button>
                  </form>,
                  { marginTop: '16px' },
                )}

                {card(
                  <>
                    <h3 style={{ marginTop: 0 }}><Shield size={18} /> Insurance</h3>
                    {insurance.policies.length === 0 && <p style={{ color: 'var(--text-muted)' }}>No policy on file. Contact the insurance desk to add one.</p>}
                    {insurance.policies.map((p: any) => (
                      <div key={p.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                        <b>{p.provider}</b> — {p.policy_number}
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {p.plan_name || ''} {p.sum_insured ? `· Sum insured ${money(p.sum_insured)}` : ''} {p.is_active ? '· Active' : '· Inactive'}
                        </div>
                      </div>
                    ))}
                    {insurance.claims.length > 0 && (
                      <>
                        <h4 style={{ marginBottom: 6 }}>Claims</h4>
                        <div className="table-container">
                          <table>
                            <thead><tr><th>Claim</th><th>Status</th><th>Claimed</th><th>Approved</th></tr></thead>
                            <tbody>
                              {insurance.claims.map((c: any) => (
                                <tr key={c.id}>
                                  <td>{c.claim_number}</td>
                                  <td><span className={statusClass(c.status)}>{c.status}</span></td>
                                  <td>{money(c.claimed_amount)}</td>
                                  <td>{money(c.approved_amount)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                  </>,
                  { marginTop: '16px' },
                )}
              </>
            )}
          </>
        )}
      </div>

      {/* Lab report viewer */}
      {openReport && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '900px', width: '95%' }}>
            <div className="modal-header">
              <h2>{openReport.test_name}</h2>
              <button className="close-btn" onClick={() => setOpenReport(null)}><X size={20} /></button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <small style={{ color: 'var(--text-muted)' }}>Collected / reported</small><br />
                  <b>{new Date(openReport.date_conducted).toLocaleString()}</b>
                </div>
                <div>
                  {openReport.is_abnormal
                    ? <span className="status-badge cancelled">Abnormal</span>
                    : <span className="status-badge completed">Normal</span>}
                  <span className={statusClass(openReport.status)} style={{ marginLeft: '6px' }}>{openReport.status}</span>
                </div>
              </div>
              <div className="table-container">
                <table>
                  <thead><tr><th>Parameter</th><th>Result</th><th>Unit</th><th>Reference</th><th>Flag</th></tr></thead>
                  <tbody>
                    {openReport.results.map((row, i) => (
                      <tr key={i} style={flagIsAbnormal(row.flag) ? { background: 'rgba(239,68,68,0.08)' } : undefined}>
                        <td>{row.parameter}</td>
                        <td style={flagIsAbnormal(row.flag) ? { color: 'var(--danger)', fontWeight: 700 } : undefined}>{row.result ?? '-'}</td>
                        <td>{row.unit}</td>
                        <td>{row.range}</td>
                        <td>{row.flag}</td>
                      </tr>
                    ))}
                    {openReport.results.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No parameters recorded.</td></tr>}
                  </tbody>
                </table>
              </div>
              {openReport.interpretation && <p style={{ marginTop: '12px' }}><b>Interpretation:</b> {openReport.interpretation}</p>}
              <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {openReport.verified_by ? `Verified by ${openReport.verified_by}` : `Reported by ${openReport.reported_by || '-'}`}
              </p>
              <div style={{ display: 'flex', gap: '10px', marginTop: '14px' }}>
                <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => printReport(openReport)}><Printer size={16} /> Print / Save PDF</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div style={{
          position: 'fixed', bottom: '24px', right: '24px', zIndex: 999, padding: '12px 18px', borderRadius: '10px',
          color: '#fff', fontWeight: 600, boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
          background: toast.kind === 'ok' ? '#10b981' : '#ef4444',
          display: 'flex', alignItems: 'center', gap: '8px',
        }}>
          {toast.kind === 'ok' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />} {toast.msg}
        </div>
      )}
    </div>
  );
}
