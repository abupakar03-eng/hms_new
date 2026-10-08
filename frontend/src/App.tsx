import React, { useState, useEffect, useRef, Fragment } from 'react';
import axios from 'axios';
import { 
  Users, FileText, Clipboard, Search, CheckCircle, Clock, Calendar, Activity, Pill, PlusCircle, TestTube, Bed, FlaskConical, Database, UserRound, ArrowRightCircle,
  ShoppingBag, Printer, AlertTriangle, DollarSign, BarChart2, Download,
  Building2, Receipt, Settings, Shield,
  Save, RefreshCw, UploadCloud, DownloadCloud,
  Sun, Moon, Loader2, CheckCircle2, List, Eye, Edit, Trash2, X, Plus, ChevronDown
} from 'lucide-react';
import Select from 'react-select';
import PatientPortal from './PatientPortal';
import RoleFlow from './RoleFlow';
import { API_BASE } from './api';

const selectStyles = {
  control: (base: any, state: any) => ({
    ...base,
    backgroundColor: 'var(--bg-input)',
    borderColor: state.isFocused ? 'var(--border-focus)' : 'var(--input-border)',
    color: 'var(--text-primary)',
    boxShadow: state.isFocused ? '0 0 0 3px var(--primary-glow)' : 'none',
    minHeight: '40px',
    '&:hover': { borderColor: 'var(--border-focus)' }
  }),
  menu: (base: any) => ({ ...base, backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', zIndex: 100 }),
  option: (base: any, state: any) => ({
    ...base,
    backgroundColor: state.isFocused ? 'var(--bg-card-hover)' : 'transparent',
    color: 'var(--text-primary)',
    '&:active': { backgroundColor: 'var(--primary-glow)' }
  }),
  singleValue: (base: any) => ({ ...base, color: 'var(--text-primary)' }),
  input: (base: any) => ({ ...base, color: 'var(--text-primary)' })
};

// The API base (and the session/token helpers) live in ./api so the staff shell
// and the patient portal resolve them identically.

// Ward/room/bed layout now comes from the server (/ipd/bed-board). The old
// HOSPITAL_LAYOUT constant was hard-coded hospital data and has been removed.

interface Patient {
  id: number;
  name: string;
  age: number;
  gender: string;
  phone?: string;
  address?: string;
  aadhaar?: string;
  blood_group?: string;
  details?: Record<string, any>;
  created_at: string;
}

interface OPToken {
  id: number;
  patient_id: number;
  token_number: number;
  session: string;
  date: string;
  status: string;
  fee: number;
  is_billed: boolean;
  doctor_id?: number;
  doctor_name?: string;
  department?: string;
  created_at?: string;
  details?: Record<string, any>;
  patient?: Patient;
}

interface Appointment {
  id: number;
  patient_id: number;
  doctor_id?: number;
  doctor_name?: string;
  appointment_date: string;
  time_slot?: string;
  reason?: string;
  status: string;
  details?: Record<string, any>;
  patient?: Patient;
}

interface MedicineStock {
  id: number;
  name: string;
  category: string;
  batch_no?: string;
  expiry_date?: string;
  quantity: number;
  unit_price: number;
  min_stock_level: number;
  details?: Record<string, any>;
}

interface PharmacyBillItem {
  id?: number;
  medicine_id: number;
  medicine_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

interface PharmacyBill {
  id: number;
  patient_id?: number;
  patient_name?: string;
  bill_date: string;
  subtotal: number;
  discount: number;
  gst: number;
  total: number;
  items: PharmacyBillItem[];
  patient?: Patient;
}

interface IPAdmission {
  id: number;
  patient_id: number;
  admission_date: string;
  bed_id?: number | null;
  bed_code?: string | null;
  ward_number?: string;
  room_number?: string;
  doctor_in_charge?: string;
  attending_doctor_id?: number | null;
  attending_doctor?: { id: number; full_name?: string | null; username: string } | null;
  department_id?: number | null;
  admission_type?: string;
  admission_source?: string | null;
  provisional_diagnosis?: string | null;
  reason_for_admission?: string;
  expected_discharge_date?: string | null;
  discharge_date?: string;
  discharge_type?: string | null;
  discharged_by?: string | null;
  status: string;
  bed?: { id: number; bed_code: string; daily_charge?: number | null } | null;
  patient?: Patient;
}

// ---- Laboratory ------------------------------------------------------------
export type LabFlag = 'Normal' | 'High' | 'Low' | 'Critical High' | 'Critical Low' | 'Abnormal';

export interface LabResultRow {
  parameter: string;
  result: string;
  unit: string;
  range: string;
  normal_range?: string;
  flag: LabFlag | string;
  remarks?: string;
  critical_low?: number | null;
  critical_high?: number | null;
}

export interface LabReport {
  id: number;
  patient_id: number;
  order_id?: number;
  test_id?: number;
  test_name: string;
  result_value?: string;
  normal_range?: string;
  units?: string;
  date_conducted: string;
  reported_by?: string;
  verified_by?: string;
  verified_at?: string;
  status?: string;
  is_abnormal?: boolean;
  interpretation?: string;
  remarks?: string;
  results_data?: LabResultRow[] | Record<string, any> | null;
  patient?: Patient;
}

export interface LabTestParameter {
  id?: number;
  test_id?: number;
  name: string;
  data_type?: string;
  options?: string;
  unit?: string;
  reference_range?: string;
  normal_range_male?: string;
  normal_range_female?: string;
  normal_range_child?: string;
  critical_low?: number | null;
  critical_high?: number | null;
  display_order?: number;
}

export interface LabTestMaster {
  id: number;
  test_code: string;
  test_name: string;
  category?: string;
  department?: string;
  sample_type?: string;
  container_type?: string;
  method?: string;
  unit?: string;
  reference_range?: string;
  normal_range_male?: string;
  normal_range_female?: string;
  normal_range_child?: string;
  price: number;
  tat_hours: number;
  is_panel?: boolean;
  is_active: boolean;
  parameters?: LabTestParameter[];
}

export interface LabOrder {
  id: number;
  patient_id: number;
  doctor_name?: string;
  test_id: number;
  panel_id?: number;
  bill_id?: number;
  order_date: string;
  status: string;
  priority?: string;
  tat_hours?: number;
  due_at?: string;
  sample_collected_at?: string;
  result_entered_at?: string;
  verified_by?: string;
  verified_at?: string;
  remarks?: string;
  interpretation?: string;
  patient?: Patient;
  test?: LabTestMaster;
}

export interface LabSample {
  id: number;
  order_id: number;
  sample_type: string;
  collection_date?: string;
  received_at?: string;
  collected_by?: string;
  container_type?: string;
  barcode?: string;
  volume?: string;
  rejection_reason?: string;
  remarks?: string;
  status: string;
  order?: LabOrder;
}

export interface LabStats {
  pending: number;
  sample_collected: number;
  testing: number;
  ready_to_report: number;
  verified_today: number;
  overdue: number;
  stat_pending: number;
  samples_pending: number;
  rejected_samples: number;
  total_tests: number;
  active_tests: number;
  panels: number;
  today_orders: number;
  today_revenue: number;
  pending_billing: number;
  tat_compliance_percent: number;
}

interface OPBill {
  id: number;
  patient_id: number;
  token_id?: number;
  bill_date: string;
  doctor_name?: string;
  department?: string;
  consultation_fee: number;
  lab_charges: number;
  pharmacy_charges: number;
  other_charges: {name: string; amount: number}[];
  subtotal: number;
  discount: number;
  gst: number;
  total: number;
  payment_mode: string;
  payment_details?: Record<string, number>;
  notes?: string;
  patient?: Patient;
}

interface IPBill {
  id: number;
  patient_id: number;
  admission_id?: number;
  bill_date: string;
  doctor_name?: string;
  room_charge_per_day: number;
  days_stayed: number;
  room_charges: number;
  doctor_charges: number;
  nursing_charges: number;
  pharmacy_charges: number;
  lab_charges: number;
  other_charges: {name: string; amount: number}[];
  subtotal: number;
  discount: number;
  gst: number;
  total: number;
  payment_mode: string;
  payment_details?: Record<string, number>;
  notes?: string;
  patient?: Patient;
}

interface SearchResultItem {
  type: string;
  id: number;
  patient_id?: number;
  patient_name?: string;
  detail: string;
  date?: string;
  amount?: number;
}

interface DailyReport {
  date: string;
  op_revenue: number;
  ip_revenue: number;
  pharmacy_revenue: number;
  lab_revenue: number;
  total_revenue: number;
  total_patients: number;
  total_bills: number;
}

interface User {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
  patient_id?: number | null;
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
}

const SearchableDropdown = ({ options, value, onChange, placeholder, renderOption, searchKeys = ['label'] }: any) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: any) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredOptions = options.filter((opt: any) => 
    searchKeys.some((key: string) => opt[key]?.toString().toLowerCase().includes(search.toLowerCase()))
  );

  const selectedOpt = options.find((o: any) => o.value === value);

  return (
    <div ref={wrapperRef} style={{ position: 'relative', width: '100%' }}>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '4px', background: 'white', color: '#0f172a', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
      >
        <span>{selectedOpt ? (renderOption ? renderOption(selectedOpt) : selectedOpt.label) : placeholder}</span>
        <ChevronDown size={16} />
      </div>
      {isOpen && (
        <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: 'white', color: '#0f172a', border: '1px solid #cbd5e1', borderRadius: '4px', zIndex: 100, maxHeight: '300px', overflowY: 'auto', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
          <div style={{ padding: '8px', position: 'sticky', top: 0, background: 'white', borderBottom: '1px solid #e2e8f0' }}>
            <input 
              type="text" 
              placeholder="Type to search..." 
              value={search} 
              onChange={e => setSearch(e.target.value)}
              style={{ width: '100%', padding: '6px', border: '1px solid #cbd5e1', borderRadius: '4px', color: '#0f172a' }}
              autoFocus
            />
          </div>
          {filteredOptions.length > 0 ? (
            filteredOptions.map((opt: any, index: number) => (
              <div 
                key={index}
                onClick={() => { onChange(opt.value); setIsOpen(false); setSearch(''); }}
                style={{ padding: '8px', cursor: 'pointer', borderBottom: '1px solid #f1f5f9' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#f8fafc')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                {renderOption ? renderOption(opt) : opt.label}
              </div>
            ))
          ) : (
            <div style={{ padding: '8px', color: 'var(--text-muted)', textAlign: 'center' }}>No results found</div>
          )}
        </div>
      )}
    </div>
  );
};


const LabPatientHeader = ({ patients, selectedId, onChange, labOrders, ipAdmissions }: any) => {
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

export default function App() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [globalLoading, setGlobalLoading] = useState(false);
  const [toast, setToast] = useState<{message:string, type:'success'|'error'} | null>(null);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const showToast = (message: string, type: 'success'|'error' = 'success') => {
    setToast({message, type});
    setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    const reqInterceptor = axios.interceptors.request.use(config => { setGlobalLoading(true); return config; });
    const resInterceptor = axios.interceptors.response.use(
      response => { setGlobalLoading(false); return response; },
      error => { 
        setGlobalLoading(false); 
        let errorMsg = 'An error occurred';
        if (error.response?.data?.detail) {
          const detail = error.response.data.detail;
          if (Array.isArray(detail)) {
            errorMsg = detail.map((err: any) => err.msg || err.type).join(', ');
          } else if (typeof detail === 'string') {
            errorMsg = detail;
          }
        }
        showToast(errorMsg, 'error'); 
        return Promise.reject(error); 
      }
    );
    return () => {
      axios.interceptors.request.eject(reqInterceptor);
      axios.interceptors.response.eject(resInterceptor);
    };
  }, []);

  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  
  const exportToCSV = (data: any[], filename: string) => {
    if(!data.length) return;
    const headers = Object.keys(data[0]).join(',');
    const rows = data.map(obj => Object.values(obj).map(v => `"${v}"`).join(',')).join('\n');
    const csvContent = "data:text/csv;charset=utf-8," + headers + "\n" + rows;
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const [patientSearch, setPatientSearch] = useState("");
  const [inventorySearch, setInventorySearch] = useState("");
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });

  // Patient self-registration (public, before any session exists)
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [registerBusy, setRegisterBusy] = useState(false);
  const [registerForm, setRegisterForm] = useState({
    name: '', age: 0, gender: 'Male', phone: '', username: '', email: '',
    address: '', blood_group: '', password: '', confirm: ''
  });
  
  const [activeTab, setActiveTab] = useState('dashboard');
  const [patients, setPatients] = useState<Patient[]>([]);
  const [tokens, setTokens] = useState<OPToken[]>([]);
  const [inventory, setInventory] = useState<MedicineStock[]>([]);
  const [pharmacyBills, setPharmacyBills] = useState<PharmacyBill[]>([]);
  const [ipAdmissions, setIpAdmissions] = useState<IPAdmission[]>([]);
  const [labReports, setLabReports] = useState<LabReport[]>([]);
  const [labTestMasters, setLabTestMasters] = useState<LabTestMaster[]>([]);
  const [labOrders, setLabOrders] = useState<LabOrder[]>([]);
  const [labSamples, setLabSamples] = useState<LabSample[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  // New state for billing & reports
  const [opBills, setOpBills] = useState<OPBill[]>([]);
  const [ipBills, setIpBills] = useState<IPBill[]>([]);
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Reports state
  const [reportType, setReportType] = useState('daily');
  const [reportDate, setReportDate] = useState(new Date().toISOString().split('T')[0]);
  const [reportMonth, setReportMonth] = useState(new Date().getMonth() + 1);
  const [reportYear, setReportYear] = useState(new Date().getFullYear());
  const [dailyReport, setDailyReport] = useState<DailyReport | null>(null);
  const [monthlyReport, setMonthlyReport] = useState<DailyReport[]>([]);
  const [yearlyReport, setYearlyReport] = useState<any[]>([]);
  const [revenueReport, setRevenueReport] = useState<any>(null);
  const [doctorReport, setDoctorReport] = useState<any[]>([]);
  const [medicineSalesReport, setMedicineSalesReport] = useState<any[]>([]);
  const [departmentWiseReport, setDepartmentWiseReport] = useState<any[]>([]);
  const [patientReportData, setPatientReportData] = useState<any>(null);
  const [patientReportId, setPatientReportId] = useState<string>('');
  const [medicineStockReport, setMedicineStockReport] = useState<any[]>([]);
  const [labSummaryReport, setLabSummaryReport] = useState<any[]>([]);
  const [dischargeReport, setDischargeReport] = useState<any[]>([]);
  // Dashboard stats & charts
  const [dashStats, setDashStats] = useState<any>(null);
  const [dashCharts, setDashCharts] = useState<any>(null);
  // Admin Settings
  const [hospitalSettings, setHospitalSettings] = useState<Record<string,string>>({
    hospital_name: 'MedBill Pro Hospital',
    gst_number: '33AAAAA0000A1Z5',
    address: '123 Healthcare Street, Chennai - 600001',
    contact: '+91 99999 99999',
    email: 'info@medbillpro.com',
    receipt_header: 'Thank you for visiting our hospital',
    receipt_footer: 'Get well soon! This is a computer generated receipt.',
    paper_size: 'A4',
    font_size: '12',
  });
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  // Audit trail view state: which rows have their before/after diff open, and
  // the server-side filters.
  const [auditExpanded, setAuditExpanded] = useState<Record<number, boolean>>({});
  const [auditFilter, setAuditFilter] = useState({ action: '', entity_type: '', patient_id: '' });
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [adminSettingsTab, setAdminSettingsTab] = useState('hospital_info');
  // Billing sub-tab
  const [billingTab, setBillingTab] = useState('op');
  // OP Bill Form
  const [opBillForm, setOpBillForm] = useState({
    patient_id: '', token_id: '', doctor_name: '', department: '',
    consultation_fee: 0, lab_charges: 0, pharmacy_charges: 0,
    discount: 0, gst: 5, payment_mode: 'Cash', notes: ''
  });
  const [opOtherCharges, setOpOtherCharges] = useState<{name: string; amount: number}[]>([]);
  const [opSplitPayment, setOpSplitPayment] = useState({cash: 0, upi: 0, card: 0, bank: 0});
  // IP Bill Form
  const [ipBillForm, setIpBillForm] = useState({
    patient_id: '', admission_id: '', doctor_name: '',
    room_charge_per_day: 0, days_stayed: 1, doctor_charges: 0,
    nursing_charges: 0, pharmacy_charges: 0, lab_charges: 0,
    discount: 0, gst: 5, payment_mode: 'Cash', notes: ''
  });
  const [ipOtherCharges, setIpOtherCharges] = useState<{name: string; amount: number}[]>([]);
  const [ipSplitPayment, setIpSplitPayment] = useState({cash: 0, upi: 0, card: 0, bank: 0});
  const [viewBillDetail, setViewBillDetail] = useState<any>(null);

  // Global Lab State
  const [selectedGlobalLabPatientId, setSelectedGlobalLabPatientId] = useState<number | null>(null);

  // Doctor Module Global States
  const [selectedDoctorPatientId, setSelectedDoctorPatientId] = useState<number | null>(null);

  // Lab Direct Orders States
  const [isLabRegistrationModalOpen, setIsLabRegistrationModalOpen] = useState(false);
  const [isLabOrderModalOpen, setIsLabOrderModalOpen] = useState(false);
  const [labDirectOrderPatientId, setLabDirectOrderPatientId] = useState<number | null>(null);
  const [labDirectOrderForm, setLabDirectOrderForm] = useState<{ test_ids: number[]; referring_doctor: string; priority: string }>({
    test_ids: [], referring_doctor: 'Walk-in / Self', priority: 'Routine'
  });

  // Lab Orders Workflow States
  const [labSearchQuery, setLabSearchQuery] = useState('');
  const [labFilterStatus, setLabFilterStatus] = useState('All');
  const [labFilterPriority, setLabFilterPriority] = useState('All');
  const [labOverdueOnly, setLabOverdueOnly] = useState(false);
  const [selectedViewOrder, setSelectedViewOrder] = useState<LabOrder | null>(null);
  const [selectedEditOrder, setSelectedEditOrder] = useState<LabOrder | null>(null);
  const [selectedCollectSampleOrder, setSelectedCollectSampleOrder] = useState<LabOrder | null>(null);
  const [selectedResultEntryOrder, setSelectedResultEntryOrder] = useState<LabOrder | null>(null);
  const [selectedBillOrderIds, setSelectedBillOrderIds] = useState<number[]>([]);

  const [editOrderForm, setEditOrderForm] = useState({ priority: 'Routine', remarks: '' });
  const [collectSampleForm, setCollectSampleForm] = useState({ barcode: '', collected_by: '', sample_type: '', container_type: '', volume: '', remarks: '', status: 'Collected' });
  const [resultEntryForm, setResultEntryForm] = useState<LabResultRow[]>([]);
  const [resultInterpretation, setResultInterpretation] = useState('');

  // Laboratory dashboard / statistics
  const [labStats, setLabStats] = useState<LabStats | null>(null);
  const [labReportFilter, setLabReportFilter] = useState<'all' | 'abnormal'>('all');

  // Lab test master editor (panel + parameter aware)
  const [labParamRows, setLabParamRows] = useState<LabTestParameter[]>([]);
  const [labPanelTestIds, setLabPanelTestIds] = useState<number[]>([]);

  // Self-service password change
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' });

  // Insurance desk
  const [insuranceClaims, setInsuranceClaims] = useState<any[]>([]);
  const [insurancePolicies, setInsurancePolicies] = useState<any[]>([]);
  const [insuranceStats, setInsuranceStats] = useState<any>(null);
  const [insuranceFilter, setInsuranceFilter] = useState('All');
  const [isClaimModalOpen, setIsClaimModalOpen] = useState(false);
  const [isPolicyModalOpen, setIsPolicyModalOpen] = useState(false);
  const [selectedClaim, setSelectedClaim] = useState<any>(null);
  const [claimStatusForm, setClaimStatusForm] = useState({ status: 'Submitted', approved_amount: 0, rejection_reason: '', remarks: '' });
  const [claimForm, setClaimForm] = useState({
    patient_id: '', policy_id: '', claim_type: 'Reimbursement', treatment_type: 'OP',
    diagnosis: '', claimed_amount: 0, remarks: '',
  });
  const [policyForm, setPolicyForm] = useState({
    patient_id: '', provider: '', policy_number: '', member_id: '', plan_name: '',
    sum_insured: 0, tpa_name: '', tpa_contact: '', notes: '',
  });

  // Patient 360 (staff view of one patient's whole record)
  const [patientDetail, setPatientDetail] = useState<any>(null);
  const [patientDetailLoading, setPatientDetailLoading] = useState(false);
  const [frontDeskSearch, setFrontDeskSearch] = useState('');
  const [pharmacySearch, setPharmacySearch] = useState('');

  // ---- Inpatient (IPD) ----------------------------------------------------
  // The bed list, wards and occupancy come from the server; nothing about the
  // hospital layout is hard-coded in the client.
  const [bedBoard, setBedBoard] = useState<any[]>([]);
  const [wards, setWards] = useState<any[]>([]);
  const [rooms, setRooms] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [ipdStats, setIpdStats] = useState<any>(null);
  const [activeWardId, setActiveWardId] = useState<number | null>(null);
  const [selectedBedId, setSelectedBedId] = useState<number | null>(null);
  const [bedBoardFilter, setBedBoardFilter] = useState('All');
  const [admissionDetail, setAdmissionDetail] = useState<any>(null);
  const [admissionTrail, setAdmissionTrail] = useState<any[]>([]);
  const [admissionDetailBusy, setAdmissionDetailBusy] = useState(false);
  const [transferTargetBedId, setTransferTargetBedId] = useState('');
  const [isDischargeOpen, setIsDischargeOpen] = useState(false);
  const [dischargeForm, setDischargeForm] = useState({ discharge_type: 'Routine', require_summary: true });
  const [nursingForm, setNursingForm] = useState({
    shift: 'Morning', temperature: '', pulse: '', respiratory_rate: '',
    bp_systolic: '', bp_diastolic: '', spo2: '', pain_score: '', blood_sugar: '',
    intake_ml: '', output_ml: '', notes: '',
  });
  const [medicationForm, setMedicationForm] = useState({
    medicine_name: '', dose: '', route: 'Oral', frequency: 'BD', notes: '',
  });
  const [dischargeSummaryForm, setDischargeSummaryForm] = useState({
    discharge_type: 'Routine', final_diagnosis: '', procedures_performed: '', investigations: '',
    condition_at_discharge: 'Improved', medication_summary: '', diet_advice: '',
    activity_advice: '', follow_up_instructions: '', follow_up_date: '',
  });
  const [newDepartment, setNewDepartment] = useState({ name: '', code: '', department_type: 'Clinical' });
  const [newWard, setNewWard] = useState({ name: '', code: '', ward_type: 'General', department_id: '', daily_charge: 0 });
  const [newRoom, setNewRoom] = useState({ ward_id: '', room_number: '', room_type: '' });
  const [newBed, setNewBed] = useState({ room_id: '', bed_code: '', bed_type: '' });

  // Axios Interceptor for Auth
  useEffect(() => {
    const reqInterceptor = axios.interceptors.request.use(config => {
      const currentToken = localStorage.getItem('token');
      if (currentToken) {
        config.headers.Authorization = `Bearer ${currentToken}`;
      }
      return config;
    });
    
    const resInterceptor = axios.interceptors.response.use(
      response => response,
      async error => {
        const originalRequest = error.config;
        if (error.response && error.response.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;
          try {
            const refreshToken = localStorage.getItem('refresh_token');
            if (refreshToken) {
              const res = await axios.post(`${API_BASE}/refresh-token?refresh_token=${refreshToken}`);
              const newToken = res.data.access_token;
              localStorage.setItem('token', newToken);
              setToken(newToken);
              axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
              return axios(originalRequest);
            } else {
              handleLogout();
            }
          } catch (refreshError) {
            handleLogout();
          }
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.request.eject(reqInterceptor);
      axios.interceptors.response.eject(resInterceptor);
    };
  }, [token]);

  // Load Current User on Token Change
  useEffect(() => {
    if (token) {
      axios.get(`${API_BASE}/users/me`)
        .then(res => {
          setCurrentUser(res.data);
          const role = res.data.role;
          // A patient account never renders the staff shell; PatientPortal is
          // returned instead (see the render guard below).
          if (role === 'Patient') setActiveTab('dashboard');
          else if (role === 'Pharmacy') setActiveTab('pharmacy');
          else if (role === 'Laboratory') setActiveTab('lab_dashboard');
          else if (role === 'Doctor') setActiveTab('casesheet');
          else if (role === 'Receptionist') setActiveTab('patients');
          else if (role === 'Insurance') setActiveTab('insurance');
          else if (role === 'Nurse') setActiveTab('ipd_workspace');
          else if (role === 'Billing') setActiveTab('billing');
          else setActiveTab('dashboard'); // Admin
        })
        .catch(() => handleLogout());
    }
  }, [token]);

  const handleLogout = async () => {
    try {
      if (token) {
        // Send the refresh token so the server revokes it along with the access token.
        await axios.post(`${API_BASE}/logout`, { refresh_token: localStorage.getItem('refresh_token') });
      }
    } catch (e) {
      console.error("Logout failed or token already invalid", e);
    }
    setToken(null);
    setCurrentUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    axios.defaults.headers.common['Authorization'] = '';
  };
  
  // IP Admission Form
  const [ipAdmissionForm, setIpAdmissionForm] = useState({
    patient_id: '', ward_number: '', room_number: '', doctor_in_charge: '', reason_for_admission: ''
  });

  // New Lab Forms
  const [labTestMasterForm, setLabTestMasterForm] = useState({
    test_code: '', test_name: '', category: 'Pathology', department: '', sample_type: 'Blood',
    container_type: '', method: '', unit: '', reference_range: '',
    normal_range_male: '', normal_range_female: '', normal_range_child: '',
    price: 0, tat_hours: 24, is_panel: false, is_active: true
  });
  const [selectedTestMasterId, setSelectedTestMasterId] = useState<number | null>(null);
  const [labMasterFilter, setLabMasterFilter] = useState('');

  // Forms & Selections
  const [selectedPatientId, setSelectedPatientId] = useState<number | ''>('');
  const [opSession, setOpSession] = useState<'Morning' | 'Evening'>('Morning');
  const [opFee, setOpFee] = useState<number>(150);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [tokenForm, setTokenForm] = useState({
    department: 'General', consultation_type: 'Routine', is_emergency: false, doctor_id: ''
  });
  const [appointmentForm, setAppointmentForm] = useState({
    patient_id: '', doctor_id: '', appointment_date: new Date().toISOString().split('T')[0], time_slot: '10:00 AM', reason: ''
  });
  
  // Registration Form
  const [patientForm, setPatientForm] = useState({
    name: '', age: 0, gender: 'Male', phone: '', address: '', aadhaar: '', blood_group: '',
    occupation: '', marital_status: 'Single', guardian_name: '', emergency_contact: '', insurance_details: '', referral_doctor: '', patient_category: 'General', registration_type: 'Walk-in'
  });

  // Casesheet Form
  const [selectedOPToken, setSelectedOPToken] = useState<OPToken | null>(null);
  const [casesheetForm, setCasesheetForm] = useState({
    vitalsBp: '', vitalsPulse: '', vitalsTemp: '', vitalsResp: '',
    chiefComplaint: '', hpi: '', pmh: '', familyHistory: '', allergies: '',
    clinicalFindings: '', diagnosis: '', icdCode: '', treatmentPlan: '', advice: '', followUpDate: ''
  });
  const [casesheetMeds, setCasesheetMeds] = useState<any[]>([]);
  const [newMed, setNewMed] = useState({ 
    medicine_id: 0, quantity: 1, duration: '', instructions: '',
    timing_morning: false, timing_afternoon: false, timing_night: false, timing_relation: 'After Food'
  });
  const [casesheetLabs, setCasesheetLabs] = useState<string[]>([]);

  // Pharmacy Billing
  const [billingPatientType, setBillingPatientType] = useState<'walkin' | 'registered'>('walkin');
  const [billingPatientId, setBillingPatientId] = useState<number | ''>('');
  const [billingWalkInName, setBillingWalkInName] = useState('');
  const [billingCart, setBillingCart] = useState<{ medicine_id: number; name: string; quantity: number; unit_price: number }[]>([]);
  const [billingNewItem, setBillingNewItem] = useState({ medicine_id: 0, quantity: 1 });
  const [billingDiscount, setBillingDiscount] = useState<number>(0);
  const [billingGst, setBillingGst] = useState<number>(18);
  const [viewInvoice, setViewInvoice] = useState<PharmacyBill | null>(null);
  const [barcodeInput, setBarcodeInput] = useState('');

  // Inventory Stock In
  const [inventoryForm, setInventoryForm] = useState({
    name: '', category: 'Pharmacy', batch_no: '', expiry_date: '', quantity: 0, unit_price: 0, min_stock_level: 10,
    details: {
      medicineCode: '', genericName: '', brandName: '', manufacturer: '', hsnCode: '', gstPercent: 12,
      mrp: 0, purchasePrice: 0, rackNumber: '', storageLocation: '', maxStock: 100, barcode: '',
      medicineImage: '', description: '', dosageForm: '', strength: '', scheduleType: ''
    }
  });

  // Inventory Stock In (GRN)
  const [grnForm, setGrnForm] = useState({
    medicine_id: '', quantity: 1, type: 'Stock In', notes: '', 
    details: { supplierName: '', invoiceNumber: '', purchaseOrder: '' }
  });

  // User Management Form
  const [userForm, setUserForm] = useState({
    username: '', password: '', role: 'Receptionist'
  });

  // =================== PATIENT 360 (staff) ===================
  /**
   * Loads everything known about one patient so the front desk, doctor, billing
   * and insurance desks all work from the same complete picture.
   * Uses allSettled: a desk that may not read one module (e.g. pharmacy cannot
   * read insurance) still gets the rest instead of a blank screen.
   */
  const openPatientDetail = async (patientId: number) => {
    setPatientDetailLoading(true);
    setPatientDetail({ patient: patients.find(p => p.id === patientId), loading: true });
    const get = (path: string) => axios.get(`${API_BASE}${path}`).then(r => r.data).catch(() => []);
    const [patient, sheets, orders, reports, opBills, ipBills, labBills, admissions, claims, policies] =
      await Promise.all([
        axios.get(`${API_BASE}/patients/${patientId}`).then(r => r.data).catch(() => null),
        get(`/patients/${patientId}/casesheets/`),
        get(`/lab-orders/?patient_id=${patientId}`),
        get(`/lab-reports/?patient_id=${patientId}`),
        get(`/billing/op/?patient_id=${patientId}`),
        get(`/billing/ip/?patient_id=${patientId}`),
        get(`/billing/lab/?patient_id=${patientId}`),
        get(`/ip-admissions/?patient_id=${patientId}`),
        get(`/insurance/claims?patient_id=${patientId}`),
        get(`/insurance/policies?patient_id=${patientId}`),
      ]);

    const billed =
      [...opBills, ...ipBills, ...labBills].reduce((sum: number, b: any) => sum + (b.total || 0), 0);

    setPatientDetail({
      patient, sheets, orders, reports, opBills, ipBills, labBills, admissions, claims, policies,
      billed, loading: false,
    });
    setPatientDetailLoading(false);
  };

  // =================== INPATIENT (IPD) ===================
  const loadIpdStructure = async () => {
    try {
      const [board, wardList, deptList, stats, roomList] = await Promise.all([
        axios.get(`${API_BASE}/ipd/bed-board`),
        axios.get(`${API_BASE}/wards/`),
        axios.get(`${API_BASE}/departments/`),
        axios.get(`${API_BASE}/ipd/stats`),
        axios.get(`${API_BASE}/rooms/`),
      ]);
      setBedBoard(board.data);
      setWards(wardList.data);
      setDepartments(deptList.data);
      setIpdStats(stats.data);
      setRooms(roomList.data);
      // Deliberately not auto-selecting a ward: the board defaults to "All wards",
      // which is also what you want right after creating a new one.
    } catch (e) { console.error('IPD load failed', e); }
  };

  const openAdmissionDetail = async (admissionId: number) => {
    setAdmissionDetail({ loading: true });
    setAdmissionTrail([]);
    try {
      const { data } = await axios.get(`${API_BASE}/ip-admissions/${admissionId}/detail`);
      setAdmissionDetail(data);
      // The clinical change history for this record, for the ward team.
      axios.get(`${API_BASE}/audit-logs/patient/${data.patient_id}`, { params: { limit: 100 } })
        .then(res => setAdmissionTrail(res.data))
        .catch(() => setAdmissionTrail([]));
      const s = data.discharge_summary;
      setDischargeSummaryForm({
        discharge_type: s?.discharge_type || 'Routine', final_diagnosis: s?.final_diagnosis || '',
        procedures_performed: s?.procedures_performed || '', investigations: s?.investigations || '',
        condition_at_discharge: s?.condition_at_discharge || 'Improved',
        medication_summary: s?.medication_summary || '', diet_advice: s?.diet_advice || '',
        activity_advice: s?.activity_advice || '', follow_up_instructions: s?.follow_up_instructions || '',
        follow_up_date: s?.follow_up_date || '',
      });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Could not load the admission.');
      setAdmissionDetail(null);
    }
  };
  const refreshAdmission = async () => { if (admissionDetail?.id) await openAdmissionDetail(admissionDetail.id); };

  /** Blank inputs must not become 0 — that would chart a real, wrong value. */
  const numeric = (v: string) => (v === '' || v === null || v === undefined ? null : Number(v));

  const handleAddNursingNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!admissionDetail?.id) return;
    setAdmissionDetailBusy(true);
    try {
      await axios.post(`${API_BASE}/ip-admissions/${admissionDetail.id}/nursing-notes`, {
        shift: nursingForm.shift,
        temperature: numeric(nursingForm.temperature), pulse: numeric(nursingForm.pulse),
        respiratory_rate: numeric(nursingForm.respiratory_rate),
        bp_systolic: numeric(nursingForm.bp_systolic), bp_diastolic: numeric(nursingForm.bp_diastolic),
        spo2: numeric(nursingForm.spo2), pain_score: numeric(nursingForm.pain_score),
        blood_sugar: numeric(nursingForm.blood_sugar),
        intake_ml: numeric(nursingForm.intake_ml), output_ml: numeric(nursingForm.output_ml),
        notes: nursingForm.notes || null,
      });
      showToast('Vitals charted');
      setNursingForm({ ...nursingForm, temperature: '', pulse: '', respiratory_rate: '', bp_systolic: '',
        bp_diastolic: '', spo2: '', pain_score: '', blood_sugar: '', intake_ml: '', output_ml: '', notes: '' });
      await refreshAdmission();
      loadIpdStructure();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not chart the vitals.'); }
    finally { setAdmissionDetailBusy(false); }
  };

  const handleAddMedication = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!admissionDetail?.id) return;
    if (!medicationForm.medicine_name.trim()) return alert('Enter the medicine name.');
    setAdmissionDetailBusy(true);
    try {
      await axios.post(`${API_BASE}/ip-admissions/${admissionDetail.id}/medications`, {
        medicine_name: medicationForm.medicine_name, dose: medicationForm.dose || null,
        route: medicationForm.route, frequency: medicationForm.frequency, notes: medicationForm.notes || null,
      });
      showToast('Medication prescribed');
      setMedicationForm({ medicine_name: '', dose: '', route: 'Oral', frequency: 'BD', notes: '' });
      await refreshAdmission();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not prescribe the medication.'); }
    finally { setAdmissionDetailBusy(false); }
  };

  const handleAdminister = async (orderId: number, status: string) => {
    try {
      await axios.post(`${API_BASE}/ipd/medications/${orderId}/administer`, { status });
      showToast(`Dose ${status.toLowerCase()}`);
      await refreshAdmission();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not record the administration.'); }
  };

  const handleStopMedication = async (orderId: number) => {
    const reason = window.prompt('Reason for stopping this medication:');
    if (!reason) return;
    try {
      await axios.put(`${API_BASE}/ipd/medications/${orderId}`, { status: 'Stopped', stop_reason: reason });
      showToast('Medication stopped');
      await refreshAdmission();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not stop the medication.'); }
  };

  const handleSaveDischargeSummary = async () => {
    if (!admissionDetail?.id) return;
    setAdmissionDetailBusy(true);
    try {
      await axios.post(`${API_BASE}/ip-admissions/${admissionDetail.id}/discharge-summary`, {
        ...dischargeSummaryForm, follow_up_date: dischargeSummaryForm.follow_up_date || null,
      });
      showToast('Discharge summary saved as draft');
      await refreshAdmission();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not save the summary.'); }
    finally { setAdmissionDetailBusy(false); }
  };

  const handleDischargeSummaryStatus = async (status: string) => {
    const summaryId = admissionDetail?.discharge_summary?.id;
    if (!summaryId) return alert('Save the summary first.');
    try {
      await axios.put(`${API_BASE}/ipd/discharge-summaries/${summaryId}`, { status });
      showToast(`Summary ${status.toLowerCase()}`);
      await refreshAdmission();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not update the summary.'); }
  };

  const handleTransferBed = async () => {
    if (!admissionDetail?.id) return;
    if (!transferTargetBedId) return alert('Choose the destination bed.');
    try {
      await axios.post(`${API_BASE}/ip-admissions/${admissionDetail.id}/transfer`, {
        to_bed_id: Number(transferTargetBedId), reason: 'Bed transfer',
      });
      showToast('Patient transferred');
      setTransferTargetBedId('');
      await refreshAdmission();
      loadAllData(); loadIpdStructure();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not transfer the patient.'); }
  };

  const handleDischarge = async () => {
    if (!admissionDetail?.id) return;
    try {
      await axios.post(`${API_BASE}/ip-admissions/${admissionDetail.id}/discharge`, dischargeForm);
      showToast('Patient discharged');
      setIsDischargeOpen(false);
      setAdmissionDetail(null);
      loadAllData(); loadIpdStructure();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not discharge the patient.'); }
  };

  const handleCreateDepartment = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await axios.post(`${API_BASE}/departments/`, newDepartment);
      showToast('Department created');
      setNewDepartment({ name: '', code: '', department_type: 'Clinical' });
      loadIpdStructure();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not create the department.'); }
  };

  const handleCreateWard = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await axios.post(`${API_BASE}/wards/`, {
        ...newWard, department_id: newWard.department_id ? Number(newWard.department_id) : null,
      });
      showToast('Ward created');
      setNewWard({ name: '', code: '', ward_type: 'General', department_id: '', daily_charge: 0 });
      loadIpdStructure();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not create the ward.'); }
  };

  const handleCreateRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRoom.ward_id) return alert('Choose a ward.');
    try {
      await axios.post(`${API_BASE}/rooms/`, { ...newRoom, ward_id: Number(newRoom.ward_id) });
      showToast('Room created');
      setNewRoom({ ward_id: newRoom.ward_id, room_number: '', room_type: '' });
      loadIpdStructure();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not create the room.'); }
  };

  const handleCreateBed = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBed.room_id) return alert('Choose a room.');
    try {
      await axios.post(`${API_BASE}/beds/`, { ...newBed, room_id: Number(newBed.room_id) });
      showToast('Bed created');
      setNewBed({ room_id: newBed.room_id, bed_code: '', bed_type: '' });
      loadIpdStructure();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not create the bed.'); }
  };

  const handleSetBedStatus = async (bedId: number, status: string) => {
    try {
      await axios.put(`${API_BASE}/beds/${bedId}`, { status });
      showToast(`Bed marked ${status}`);
      loadIpdStructure();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not update the bed.'); }
  };

  const handleAssignBed = async (admissionId: number, patientLabel: string) => {
    const bed = bedBoard.find(b => b.bed_id === selectedBedId);
    if (!bed) return alert(`Choose an available bed for ${patientLabel} first.`);
    try {
      await axios.post(`${API_BASE}/ip-admissions/${admissionId}/bed`, { bed_id: bed.bed_id });
      showToast(`${patientLabel} assigned to ${bed.bed_code}`);
      loadAllData(); loadIpdStructure();
    } catch (err: any) { alert(err.response?.data?.detail || 'Could not assign the bed.'); }
  };

  // =================== INSURANCE DESK ===================
  const loadInsurance = async () => {
    try {
      const [claims, policies, stats] = await Promise.all([
        axios.get(`${API_BASE}/insurance/claims`),
        axios.get(`${API_BASE}/insurance/policies`),
        axios.get(`${API_BASE}/insurance/stats`),
      ]);
      setInsuranceClaims(claims.data);
      setInsurancePolicies(policies.data);
      setInsuranceStats(stats.data);
    } catch (e) {
      console.error('Insurance load failed', e);
    }
  };

  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!policyForm.patient_id) return alert('Select a patient.');
    try {
      await axios.post(`${API_BASE}/insurance/policies`, {
        ...policyForm,
        patient_id: Number(policyForm.patient_id),
        sum_insured: Number(policyForm.sum_insured) || 0,
      });
      showToast('Policy added');
      setIsPolicyModalOpen(false);
      setPolicyForm({ patient_id: '', provider: '', policy_number: '', member_id: '', plan_name: '', sum_insured: 0, tpa_name: '', tpa_contact: '', notes: '' });
      loadInsurance();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add policy');
    }
  };

  const handleCreateClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!claimForm.patient_id) return alert('Select a patient.');
    try {
      await axios.post(`${API_BASE}/insurance/claims`, {
        ...claimForm,
        patient_id: Number(claimForm.patient_id),
        policy_id: claimForm.policy_id ? Number(claimForm.policy_id) : null,
        claimed_amount: Number(claimForm.claimed_amount) || 0,
      });
      showToast('Claim created');
      setIsClaimModalOpen(false);
      setClaimForm({ patient_id: '', policy_id: '', claim_type: 'Reimbursement', treatment_type: 'OP', diagnosis: '', claimed_amount: 0, remarks: '' });
      loadInsurance();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create claim');
    }
  };

  const handleUpdateClaimStatus = async () => {
    if (!selectedClaim) return;
    try {
      await axios.put(`${API_BASE}/insurance/claims/${selectedClaim.id}/status`, {
        status: claimStatusForm.status,
        approved_amount: claimStatusForm.approved_amount || null,
        rejection_reason: claimStatusForm.rejection_reason || null,
        remarks: claimStatusForm.remarks || null,
      });
      showToast(`Claim ${claimStatusForm.status}`);
      setSelectedClaim(null);
      loadInsurance();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update claim');
    }
  };

  /** Self-service password change (POST /users/me/password). */  const handleChangeMyPassword = async () => {
    if (!passwordForm.current) return alert('Enter your current password.');
    if (passwordForm.next !== passwordForm.confirm) return alert('The new passwords do not match.');
    if (passwordForm.next.length < 8) return alert('The new password must be at least 8 characters.');
    if (!/[A-Z]/.test(passwordForm.next) || !/\d/.test(passwordForm.next)) {
      return alert('The new password must contain an uppercase letter and a digit.');
    }
    try {
      await axios.post(`${API_BASE}/users/me/password`, {
        current_password: passwordForm.current,
        new_password: passwordForm.next,
      });
      showToast('Password updated. Sign in again on other devices.', 'success');
      setIsPasswordModalOpen(false);
      setPasswordForm({ current: '', next: '', confirm: '' });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update the password.');
    }
  };

  /** Change another user's role (PUT /users/{id}/role). */
  const handleChangeUserRole = async (userId: number, role: string) => {
    try {
      await axios.put(`${API_BASE}/users/${userId}/role?role=${encodeURIComponent(role)}`);
      showToast(`Role updated to ${role}`);
      loadUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to change the role.');
      loadUsers(); // put the dropdown back to the server value
    }
  };

  /** Admin-initiated password reset (PUT /users/{id}/reset-password). */  const handleAdminResetPassword = async (userId: number, username: string) => {
    const next = window.prompt(`New password for "${username}" (min 8 chars, 1 uppercase, 1 digit):`);
    if (!next) return;
    try {
      await axios.put(`${API_BASE}/users/${userId}/reset-password`, { new_password: next });
      showToast(`Password reset for ${username}`);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to reset the password.');
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userForm.username || !userForm.password) return showToast("Username and password required", "error");
    try {
      await axios.post(`${API_BASE}/users/`, userForm);
      showToast("User created successfully", "success");
      setUserForm({ username: '', password: '', role: 'Receptionist' });
      loadUsers();
    } catch (err: any) {
      console.error(err);
    }
  };


  const handleDeletePatient = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this patient?")) return;
    try {
      await axios.delete(`${API_BASE}/patients/${id}`);
      showToast("Patient deleted successfully", "success");
      loadAllData();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to delete patient");
    }
  };

  const handleDeleteMedicineStock = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this medicine?")) return;
    try {
      await axios.delete(`${API_BASE}/inventory/${id}`);
      showToast("Medicine deleted successfully", "success");
      loadAllData();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to delete medicine");
    }
  };

  const handleDeleteLabReport = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this report?")) return;
    try {
      await axios.delete(`${API_BASE}/lab-reports/${id}`);
      showToast("Report deleted successfully", "success");
      loadAllData();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to delete report");
    }
  };

  const handleDeleteAppointment = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this appointment?")) return;
    try {
      await axios.delete(`${API_BASE}/appointments/${id}`);
      showToast("Appointment deleted successfully", "success");
      loadAllData();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to delete appointment");
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!window.confirm("Are you sure you want to delete this user?")) return;
    try {
      await axios.delete(`${API_BASE}/users/${userId}`);
      showToast("User deleted successfully", "success");
      loadUsers();
    } catch (err) {
      console.error("Failed to delete user", err);
    }
  };

  // Load Data
  const loadAllData = async () => {
    try {
      const pats = await axios.get(`${API_BASE}/patients/`);
      setPatients(pats.data);
      
      const toks = await axios.get(`${API_BASE}/tokens/`);
      setTokens(toks.data);
      
      const inv = await axios.get(`${API_BASE}/inventory/`);
      setInventory(inv.data);
      
      const bills = await axios.get(`${API_BASE}/billing/pharmacy/`);
      setPharmacyBills(bills.data);
      
      const ip = await axios.get(`${API_BASE}/ip-admissions/`);
      setIpAdmissions(ip.data);
      
      const labs = await axios.get(`${API_BASE}/lab-reports/`);
      setLabReports(labs.data);

      const masters = await axios.get(`${API_BASE}/lab-test-masters/`);
      setLabTestMasters(masters.data);

      const orders = await axios.get(`${API_BASE}/lab-orders/`);
      setLabOrders(orders.data);

      const samples = await axios.get(`${API_BASE}/lab-samples/`);
      setLabSamples(samples.data);

      const opb = await axios.get(`${API_BASE}/billing/op/`);
      setOpBills(opb.data);

      const ipb = await axios.get(`${API_BASE}/billing/ip/`);
      setIpBills(ipb.data);

      const appts = await axios.get(`${API_BASE}/appointments/`);
      setAppointments(appts.data);

      // Lab statistics power the laboratory dashboard.
      try {
        const stats = await axios.get(`${API_BASE}/lab/stats`);
        setLabStats(stats.data);
      } catch { /* non-fatal */ }
    } catch (e) {
      console.error("Error loading data from API:", e);
    }
  };

  const loadDashboardData = async () => {
    try {
      const stats = await axios.get(`${API_BASE}/dashboard/stats`);
      setDashStats(stats.data);
      const charts = await axios.get(`${API_BASE}/dashboard/charts`);
      setDashCharts(charts.data);
    } catch (e) { console.error('Dashboard load error:', e); }
  };

  const loadHospitalSettings = async () => {
    try {
      const res = await axios.get(`${API_BASE}/hospital-settings/`);
      if (res.data && Object.keys(res.data).length > 0) setHospitalSettings(prev => ({...prev, ...res.data}));
    } catch (e) { console.error(e); }
  };

  const loadAuditLogs = async (overrides?: Partial<typeof auditFilter>) => {
    const filter = { ...auditFilter, ...(overrides || {}) };
    try {
      const params: Record<string, string> = { limit: '500' };
      if (filter.action) params.action = filter.action;
      if (filter.entity_type) params.entity_type = filter.entity_type;
      if (filter.patient_id) params.patient_id = filter.patient_id;
      const res = await axios.get(`${API_BASE}/audit-logs/`, { params });
      setAuditLogs(res.data);
    } catch (e) { console.error(e); }
  };

  /** Parses the stored before/after snapshots into the fields that changed. */
  const auditDiff = (log: any) => {
    const parse = (raw: string) => { try { return raw ? JSON.parse(raw) : null; } catch { return null; } };
    const before = parse(log.before_state);
    const after = parse(log.after_state);
    // Both sides are full snapshots. A creation has no "before", and listing
    // every field as new would be noise — the details line already conveys it.
    if (!before || !after) return [];
    const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)]));
    return keys
      .map(key => ({ field: key, before: before[key], after: after[key] }))
      .filter(row => JSON.stringify(row.before) !== JSON.stringify(row.after));
  };

  const renderAuditValue = (value: any) => {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };

  const saveHospitalSettings = async () => {
    try {
      const settings = Object.entries(hospitalSettings).map(([key, value]) => ({ key, value }));
      await axios.post(`${API_BASE}/hospital-settings/`, { settings });
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 3000);
    } catch (e) { alert('Failed to save settings'); }
  };

  const handleBackupDatabase = async () => {
    try {
      const res = await axios.get(`${API_BASE}/backup/`);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `hospital_backup_${new Date().toISOString().split('T')[0]}.json`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e) { alert('Backup failed'); }
  };

  useEffect(() => {
    // Without this guard every mount fired the whole data fan-out before the user
    // had a token, producing a burst of 401s and console noise on the login page.
    if (!token || !currentUser) return;
    // Patient accounts render PatientPortal, which loads its own /portal/* data.
    // Letting the staff fan-out run for them produced a burst of 403s.
    if (currentUser.role === 'Patient') return;
    loadAllData();
    loadDashboardData();
    loadHospitalSettings();
  }, [token, currentUser]);

  // Bar Chart Component (CSS-based, no external library)
  const BarChart = ({ data, title, color = '#3b82f6', valuePrefix = '₹' }: { data: {label:string;value:number}[]; title:string; color?:string; valuePrefix?:string }) => {
    const maxVal = Math.max(...data.map(d => d.value), 1);
    return (
      <div style={{padding:'16px'}}>
        <h4 style={{margin:'0 0 16px',fontSize:'14px',color:'var(--text-muted)',fontWeight:600,letterSpacing:'0.5px'}}>{title}</h4>
        <div style={{display:'flex',alignItems:'flex-end',gap:'8px',height:'120px',borderBottom:'1px solid var(--border-color)',paddingBottom:'8px'}}>
          {data.map((d, i) => (
            <div key={i} style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',gap:'4px'}}>
              <span style={{fontSize:'9px',color:'var(--text-muted)',fontWeight:600}}>{valuePrefix === '₹' && d.value > 0 ? `₹${d.value >= 1000 ? (d.value/1000).toFixed(1)+'k' : d.value}` : d.value}</span>
              <div style={{width:'100%',background:color,borderRadius:'4px 4px 0 0',height:`${(d.value/maxVal)*100}px`,minHeight:d.value > 0 ? '4px' : '2px',opacity:0.85,transition:'height 0.3s ease'}} />
              <span style={{fontSize:'9px',color:'var(--text-muted)',textAlign:'center',wordBreak:'break-word',lineHeight:'1.2'}}>{d.label}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // Handle Patient Registration
  const handleLabWalkinRegistration = async (e: React.FormEvent) => {
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
      const res = await axios.post(`${API_BASE}/patients/`, payload);
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

  const handleRegisterPatient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientForm.name || patientForm.age <= 0) return alert("Please fill correct name and age");
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
      const pRes = await axios.post(`${API_BASE}/patients/`, payload);
      // Auto-generate Token for newly registered patient
      try {
        await axios.post(`${API_BASE}/tokens/`, {
          patient_id: pRes.data.id,
          session: new Date().getHours() < 12 ? 'Morning' : 'Evening',
          date: new Date().toISOString().split('T')[0],
          fee: 500,
          details: {}
        });
      } catch(tokenErr) {
        console.error('Failed to auto-generate token', tokenErr);
      }
      alert("Patient registered and added to active queue successfully!");
      setPatientForm({ name: '', age: 0, gender: 'Male', phone: '', address: '', aadhaar: '', blood_group: '', occupation: '', marital_status: 'Single', guardian_name: '', emergency_contact: '', insurance_details: '', referral_doctor: '', patient_category: 'General', registration_type: 'Walk-in' });
      loadAllData();
    } catch (err) {
      console.error(err);
    }
  };

  // =================== GLOBAL SEARCH ===================
  const handleSearch = async (q: string) => {
    setSearchQuery(q);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    if (!q.trim()) { setSearchResults([]); return; }
    setSearchLoading(true);
    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const res = await axios.get(`${API_BASE}/search/?q=${encodeURIComponent(q)}`);
        setSearchResults(res.data);
      } catch (e) {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 400);
  };

  // =================== OP BILLING ===================
  const opOtherTotal = opOtherCharges.reduce((s, c) => s + c.amount, 0);
  const opSubtotal = opBillForm.consultation_fee + opBillForm.lab_charges + opBillForm.pharmacy_charges + opOtherTotal;
  const opDiscountAmt = (opBillForm.discount / 100) * opSubtotal;
  const opGstAmt = (opBillForm.gst / 100) * (opSubtotal - opDiscountAmt);
  const opTotal = opSubtotal - opDiscountAmt + opGstAmt;

  const handleCreateOPBill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!opBillForm.patient_id) return alert('Select a patient');
    try {
      const payload: any = {
        patient_id: Number(opBillForm.patient_id),
        token_id: opBillForm.token_id ? Number(opBillForm.token_id) : null,
        doctor_name: opBillForm.doctor_name || null,
        department: opBillForm.department || null,
        consultation_fee: opBillForm.consultation_fee,
        lab_charges: opBillForm.lab_charges,
        pharmacy_charges: opBillForm.pharmacy_charges,
        other_charges: opOtherCharges,
        discount: opBillForm.discount,
        gst: opBillForm.gst,
        payment_mode: opBillForm.payment_mode,
        payment_details: opBillForm.payment_mode === 'Split' ? opSplitPayment : null,
        notes: opBillForm.notes || null,
      };
      const res = await axios.post(`${API_BASE}/billing/op/`, payload);
      setViewBillDetail({...res.data, bill_type: 'op'});
      alert('OP Bill created successfully!');
      setOpBillForm({ patient_id: '', token_id: '', doctor_name: '', department: '', consultation_fee: 0, lab_charges: 0, pharmacy_charges: 0, discount: 0, gst: 5, payment_mode: 'Cash', notes: '' });
      setOpOtherCharges([]);
      loadAllData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error creating OP bill');
    }
  };

  // =================== IP BILLING ===================
  const ipOtherTotal = ipOtherCharges.reduce((s, c) => s + c.amount, 0);
  const ipRoomCharges = ipBillForm.room_charge_per_day * ipBillForm.days_stayed;
  const ipSubtotal = ipRoomCharges + ipBillForm.doctor_charges + ipBillForm.nursing_charges + ipBillForm.pharmacy_charges + ipBillForm.lab_charges + ipOtherTotal;
  const ipDiscountAmt = (ipBillForm.discount / 100) * ipSubtotal;
  const ipGstAmt = (ipBillForm.gst / 100) * (ipSubtotal - ipDiscountAmt);
  const ipTotal = ipSubtotal - ipDiscountAmt + ipGstAmt;

  const handleCreateIPBill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ipBillForm.patient_id) return alert('Select a patient');
    try {
      const payload: any = {
        patient_id: Number(ipBillForm.patient_id),
        admission_id: ipBillForm.admission_id ? Number(ipBillForm.admission_id) : null,
        doctor_name: ipBillForm.doctor_name || null,
        room_charge_per_day: ipBillForm.room_charge_per_day,
        days_stayed: ipBillForm.days_stayed,
        doctor_charges: ipBillForm.doctor_charges,
        nursing_charges: ipBillForm.nursing_charges,
        pharmacy_charges: ipBillForm.pharmacy_charges,
        lab_charges: ipBillForm.lab_charges,
        other_charges: ipOtherCharges,
        discount: ipBillForm.discount,
        gst: ipBillForm.gst,
        payment_mode: ipBillForm.payment_mode,
        payment_details: ipBillForm.payment_mode === 'Split' ? ipSplitPayment : null,
        notes: ipBillForm.notes || null,
      };
      const res = await axios.post(`${API_BASE}/billing/ip/`, payload);
      setViewBillDetail({...res.data, bill_type: 'ip'});
      alert('IP Bill created successfully!');
      setIpBillForm({ patient_id: '', admission_id: '', doctor_name: '', room_charge_per_day: 0, days_stayed: 1, doctor_charges: 0, nursing_charges: 0, pharmacy_charges: 0, lab_charges: 0, discount: 0, gst: 5, payment_mode: 'Cash', notes: '' });
      setIpOtherCharges([]);
      loadAllData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error creating IP bill');
    }
  };

  // =================== REPORTS ===================
  const loadDailyReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/daily/?report_date=${reportDate}`);
      setDailyReport(res.data);
    } catch (e) { console.error(e); }
  };

  const loadMonthlyReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/monthly/?year=${reportYear}&month=${reportMonth}`);
      setMonthlyReport(res.data);
    } catch (e) { console.error(e); }
  };

  const loadYearlyReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/yearly/?year=${reportYear}`);
      setYearlyReport(res.data);
    } catch (e) { console.error(e); }
  };

  const loadRevenueReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/revenue/`);
      setRevenueReport(res.data);
    } catch (e) { console.error(e); }
  };

  const loadDoctorReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/doctor-wise/`);
      setDoctorReport(res.data);
    } catch (e) { console.error(e); }
  };

  const loadMedicineSalesReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/medicine-sales/`);
      setMedicineSalesReport(res.data);
    } catch (e) { console.error(e); }
  };

  const loadDepartmentWiseReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/department-wise/`);
      setDepartmentWiseReport(res.data);
    } catch (e) { console.error(e); alert('Error loading department report'); }
  };

  const loadPatientReport = async () => {
    if (!patientReportId) return alert('Enter Patient ID');
    try {
      const res = await axios.get(`${API_BASE}/reports/patient/${patientReportId}`);
      setPatientReportData(res.data);
    } catch (e) { console.error(e); alert('Patient not found or error loading report'); }
  };

  const loadMedicineStockReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/medicine-stock/`);
      setMedicineStockReport(res.data);
    } catch (e) { console.error(e); alert('Error loading stock report'); }
  };

  const loadLabSummaryReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/lab-summary/`);
      setLabSummaryReport(res.data);
    } catch (e) { console.error(e); alert('Error loading lab report'); }
  };

  const loadDischargeReport = async () => {
    try {
      const res = await axios.get(`${API_BASE}/reports/discharge/`);
      setDischargeReport(res.data);
    } catch (e) { console.error(e); alert('Error loading discharge report'); }
  };


  // PDF/Excel Export (inline using browser APIs since jspdf may not be installed yet)
  const exportTableToCSV = (tableId: string, filename: string) => {
    const table = document.getElementById(tableId);
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tr'));
    const csvContent = rows.map(row => 
      Array.from(row.querySelectorAll('th, td')).map(cell => `"${cell.textContent}"`).join(',')
    ).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  const printSection = (sectionId: string) => {
    const content = document.getElementById(sectionId)?.innerHTML;
    if (!content) return;
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(`<html><head><title>Report</title><style>body{font-family:Arial;padding:20px}table{width:100%;border-collapse:collapse}th,td{border:1px solid #ccc;padding:8px;text-align:left}th{background:#f3f4f6}</style></head><body>${content}</body></html>`);
    win.document.close();
    win.print();
  };

  // GST Invoice Print
  const printInvoice = (bill: any, billType: string) => {
    const patient = patients.find(p => p.id === bill.patient_id);
    const dateStr = new Date(bill.bill_date).toLocaleDateString('en-IN');
    let rows = '';
    if (billType === 'op') {
      if (bill.consultation_fee) rows += `<tr><td>Consultation Fee</td><td>Dr. ${bill.doctor_name || ''}</td><td>₹${bill.consultation_fee.toFixed(2)}</td></tr>`;
      if (bill.lab_charges) rows += `<tr><td>Lab Charges</td><td></td><td>₹${bill.lab_charges.toFixed(2)}</td></tr>`;
      if (bill.pharmacy_charges) rows += `<tr><td>Pharmacy Charges</td><td></td><td>₹${bill.pharmacy_charges.toFixed(2)}</td></tr>`;
      (bill.other_charges || []).forEach((c: any) => { rows += `<tr><td>${c.name}</td><td></td><td>₹${c.amount.toFixed(2)}</td></tr>`; });
    } else if (billType === 'ip') {
      if (bill.room_charges) rows += `<tr><td>Room Charges (${bill.days_stayed} days × ₹${bill.room_charge_per_day})</td><td></td><td>₹${bill.room_charges.toFixed(2)}</td></tr>`;
      if (bill.doctor_charges) rows += `<tr><td>Doctor Charges</td><td>Dr. ${bill.doctor_name || ''}</td><td>₹${bill.doctor_charges.toFixed(2)}</td></tr>`;
      if (bill.nursing_charges) rows += `<tr><td>Nursing Charges</td><td></td><td>₹${bill.nursing_charges.toFixed(2)}</td></tr>`;
      if (bill.pharmacy_charges) rows += `<tr><td>Pharmacy Charges</td><td></td><td>₹${bill.pharmacy_charges.toFixed(2)}</td></tr>`;
      if (bill.lab_charges) rows += `<tr><td>Lab Charges</td><td></td><td>₹${bill.lab_charges.toFixed(2)}</td></tr>`;
      (bill.other_charges || []).forEach((c: any) => { rows += `<tr><td>${c.name}</td><td></td><td>₹${c.amount.toFixed(2)}</td></tr>`; });
    } else {
      (bill.items || []).forEach((item: any) => { rows += `<tr><td>${item.medicine_name}</td><td>${item.quantity} units × ₹${item.unit_price}</td><td>₹${item.total_price.toFixed(2)}</td></tr>`; });
    }
    const html = `<html><head><title>GST Invoice</title><style>
      body{font-family:Arial,sans-serif;padding:30px;color:#000}
      .header{text-align:center;margin-bottom:20px}
      .header h1{color:#1e40af;font-size:22px;margin:0}
      .header p{margin:4px 0;color:#555}
      .invoice-meta{display:flex;justify-content:space-between;margin:20px 0;font-size:13px}
      table{width:100%;border-collapse:collapse;margin:15px 0}
      th{background:#1e40af;color:#fff;padding:8px;text-align:left}
      td{padding:8px;border-bottom:1px solid #eee}
      .totals{text-align:right;margin-top:10px}
      .totals p{margin:4px 0}
      .total-final{font-size:18px;font-weight:bold;color:#1e40af;margin-top:8px}
      .footer{margin-top:30px;text-align:center;color:#888;font-size:12px}
      @media print{body{padding:10px}}
    </style></head><body>
      <div class="header"><h1>🏥 MEDBILL PRO HOSPITAL</h1><p>123 Healthcare Street, Chennai - 600001 | GST: 33AAAAA0000A1Z5</p><p>Phone: +91 99999 99999 | Email: info@medbillpro.com</p></div>
      <h2 style="text-align:center;color:#1e40af">${billType === 'op' ? 'OP' : billType === 'ip' ? 'IP' : 'Pharmacy'} GST Invoice</h2>
      <div class="invoice-meta">
        <div><b>Patient:</b> ${patient?.name || bill.patient_name || 'Walk-in'}<br><b>Age/Gender:</b> ${patient?.age || '-'}/${patient?.gender || '-'}<br><b>Phone:</b> ${patient?.phone || '-'}</div>
        <div style="text-align:right"><b>Bill No:</b> #${bill.id}<br><b>Date:</b> ${dateStr}<br><b>Payment:</b> ${bill.payment_mode}</div>
      </div>
      <table><thead><tr><th>Description</th><th>Details</th><th>Amount</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="totals">
        <p>Subtotal: ₹${bill.subtotal?.toFixed(2)}</p>
        <p>Discount (${bill.discount}%): -₹${((bill.discount/100)*bill.subtotal).toFixed(2)}</p>
        <p>GST (${bill.gst}%): +₹${((bill.gst/100)*(bill.subtotal-(bill.discount/100)*bill.subtotal)).toFixed(2)}</p>
        <p class="total-final">Total: ₹${bill.total?.toFixed(2)}</p>
      </div>
      <div class="footer">Thank you for choosing MEDBILL PRO Hospital. Get well soon!<br>This is a computer-generated invoice.</div>
    </body></html>`;
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(html);
    win.document.close();
    win.print();
  };

  // Handle IP Admission
  const handleAdmitPatient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ipAdmissionForm.patient_id) return alert("Please select a patient");
    try {
      // The bed is the source of truth now; ward/room are derived server-side
      // from it, so the client never sends free-text location.
      await axios.post(`${API_BASE}/ip-admissions/`, {
        patient_id: Number(ipAdmissionForm.patient_id),
        bed_id: selectedBedId,
        doctor_in_charge: ipAdmissionForm.doctor_in_charge || null,
        reason_for_admission: ipAdmissionForm.reason_for_admission || null,
        admission_type: 'Planned',
        admission_source: 'OPD',
      });
      showToast(selectedBedId ? 'Patient admitted and bed allocated' : 'Patient admitted');
      setIpAdmissionForm({ patient_id: '', ward_number: '', room_number: '', doctor_in_charge: '', reason_for_admission: '' });
      setSelectedBedId(null);
      loadAllData();
      loadIpdStructure();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Could not admit the patient.');
    }
  };

  // =================== LABORATORY ACTIONS ===================
  const emptyTestMasterForm = {
    test_code: '', test_name: '', category: 'Pathology', department: '', sample_type: 'Blood',
    container_type: '', method: '', unit: '', reference_range: '',
    normal_range_male: '', normal_range_female: '', normal_range_child: '',
    price: 0, tat_hours: 24, is_panel: false, is_active: true
  };

  const resetLabTestMasterForm = () => {
    setLabTestMasterForm(emptyTestMasterForm);
    setLabParamRows([]);
    setLabPanelTestIds([]);
    setSelectedTestMasterId(null);
  };

  const handleSaveLabTestMaster = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: any = {
      ...labTestMasterForm,
      parameters: labParamRows
        .filter(p => (p.name || '').trim())
        .map((p, index) => ({ ...p, display_order: index })),
      panel_test_ids: labTestMasterForm.is_panel ? labPanelTestIds : [],
    };
    if (labTestMasterForm.is_panel && labPanelTestIds.length === 0) {
      return alert('A panel must contain at least one test.');
    }
    try {
      if (selectedTestMasterId) {
        await axios.put(`${API_BASE}/lab-test-masters/${selectedTestMasterId}`, payload);
        showToast('Lab test updated');
      } else {
        await axios.post(`${API_BASE}/lab-test-masters/`, payload);
        showToast('Lab test created');
      }
      resetLabTestMasterForm();
      loadAllData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to save test');
    }
  };

  const handleEditLabTestMaster = (test: LabTestMaster) => {
    setSelectedTestMasterId(test.id);
    setLabTestMasterForm({
      test_code: test.test_code, test_name: test.test_name, category: test.category || '',
      department: test.department || '', sample_type: test.sample_type || '',
      container_type: test.container_type || '', method: test.method || '',
      unit: test.unit || '', reference_range: test.reference_range || '',
      normal_range_male: test.normal_range_male || '', normal_range_female: test.normal_range_female || '',
      normal_range_child: test.normal_range_child || '', price: test.price,
      tat_hours: test.tat_hours, is_panel: !!test.is_panel, is_active: test.is_active
    });
    setLabParamRows((test.parameters || []).map(p => ({ ...p })));
    setLabPanelTestIds((test as any).panel_test_ids || []);
  };

  const handleToggleLabTestActive = async (test: LabTestMaster) => {
    try {
      await axios.put(`${API_BASE}/lab-test-masters/${test.id}/active?is_active=${!test.is_active}`);
      showToast(test.is_active ? 'Test deactivated' : 'Test activated');
      loadAllData();
    } catch (err) { alert('Failed to change test status'); }
  };

  const addLabParamRow = () => setLabParamRows(prev => [...prev, { name: '', unit: '', reference_range: '', data_type: 'Numeric' } as LabTestParameter]);
  const updateLabParamRow = (index: number, patch: Partial<LabTestParameter>) =>
    setLabParamRows(prev => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  const removeLabParamRow = (index: number) => setLabParamRows(prev => prev.filter((_, i) => i !== index));

  /** Build the blank result sheet for an order from the test's parameter list. */
  const buildResultRows = (order: LabOrder): LabResultRow[] => {
    const test = order.test || labTestMasters.find(t => t.id === order.test_id);
    const patient = patients.find(p => p.id === order.patient_id);

    if (test?.parameters && test.parameters.length > 0) {
      return test.parameters.map(param => ({
        parameter: param.name,
        result: '',
        unit: param.unit || '',
        range: pickReferenceRange(param, patient),
        flag: 'Normal',
        remarks: '',
        critical_low: param.critical_low ?? null,
        critical_high: param.critical_high ?? null,
      }));
    }
    return [{ parameter: test?.test_name || 'Result', result: '', unit: test?.unit || '', range: test?.reference_range || '', flag: 'Normal', remarks: '' }];
  };

  const pickReferenceRange = (param: LabTestParameter, patient?: Patient): string => {
    if (patient && patient.age != null && patient.age < 13 && param.normal_range_child) return param.normal_range_child;
    if (patient?.gender === 'Male' && param.normal_range_male) return param.normal_range_male;
    if (patient?.gender === 'Female' && param.normal_range_female) return param.normal_range_female;
    return param.reference_range || param.normal_range_male || param.normal_range_female || param.normal_range_child || '';
  };

  /** Client-side mirror of the server flag rules, for instant feedback while typing. */
  const computeFlag = (result: string, range: string, criticalLow?: number | null, criticalHigh?: number | null): string => {
    const value = parseFloat(result);
    if (!result || Number.isNaN(value)) {
      if (result && /positive|reactive|detected|present/i.test(result)) return 'Abnormal';
      return 'Normal';
    }
    if (criticalLow != null && value < criticalLow) return 'Critical Low';
    if (criticalHigh != null && value > criticalHigh) return 'Critical High';
    const match = /(-?\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(-?\d+(?:\.\d+)?)/i.exec(range || '');
    if (match) {
      const low = parseFloat(match[1]);
      const high = parseFloat(match[2]);
      if (value < Math.min(low, high)) return 'Low';
      if (value > Math.max(low, high)) return 'High';
      return 'Normal';
    }
    const lt = /(?:<|<=|up to|below)\s*(-?\d+(?:\.\d+)?)/i.exec(range || '');
    if (lt && value > parseFloat(lt[1])) return 'High';
    const gt = /(?:>|>=|above)\s*(-?\d+(?:\.\d+)?)/i.exec(range || '');
    if (gt && value < parseFloat(gt[1])) return 'Low';
    return 'Normal';
  };

  const isFlagAbnormal = (flag: string) => flag !== 'Normal';

  const openResultEntry = (order: LabOrder) => {
    setResultEntryForm(buildResultRows(order));
    setResultInterpretation(order.interpretation || '');
    setSelectedResultEntryOrder(order);
  };

  const handleUpdateLabSampleStatus = async (sampleId: number, status: string) => {
    try {
      await axios.put(`${API_BASE}/lab-samples/${sampleId}/status?status=${encodeURIComponent(status)}`);
      showToast(`Sample marked ${status}`);
      loadAllData();
    } catch (err: any) { alert(err.response?.data?.detail || 'Failed to update sample status'); }
  };

  const handleUpdateLabOrderStatus = async (orderId: number, status: string) => {
    try {
      await axios.put(`${API_BASE}/lab-orders/${orderId}/status?status=${encodeURIComponent(status)}`);
      loadAllData();
      loadLabStats();
    } catch (err: any) { alert(err.response?.data?.detail || 'Failed to update order status'); }
  };

  const handleSaveEditOrder = async () => {
    if (!selectedEditOrder) return;
    try {
      await axios.put(`${API_BASE}/lab-orders/${selectedEditOrder.id}`, {
        priority: editOrderForm.priority,
        remarks: editOrderForm.remarks
      });
      showToast('Order updated');
      setSelectedEditOrder(null);
      loadAllData();
    } catch (err: any) { alert(err.response?.data?.detail || 'Failed to update order'); }
  };

  const handleSaveCollectSample = async () => {
    if (!selectedCollectSampleOrder) return;
    if (!collectSampleForm.sample_type.trim()) return alert('Sample type is required.');
    try {
      await axios.post(`${API_BASE}/lab-samples/`, {
        order_id: selectedCollectSampleOrder.id,
        sample_type: collectSampleForm.sample_type,
        collected_by: collectSampleForm.collected_by,
        container_type: collectSampleForm.container_type,
        volume: collectSampleForm.volume,
        barcode: collectSampleForm.barcode || null,
        remarks: collectSampleForm.remarks,
        status: collectSampleForm.status,
      });
      showToast(`Sample collected${collectSampleForm.barcode ? ` (${collectSampleForm.barcode})` : ''}`);
      setSelectedCollectSampleOrder(null);
      loadAllData();
      loadLabStats();
    } catch (err: any) { alert(err.response?.data?.detail || 'Failed to collect sample'); }
  };

  const handleSaveResultEntry = async (isFinal: boolean) => {
    if (!selectedResultEntryOrder) return;
    if (resultEntryForm.some(r => !r.parameter.trim())) return alert('Every row needs a parameter name.');
    if (isFinal && resultEntryForm.every(r => !r.result.trim())) return alert('Enter at least one result value before verifying.');
    try {
      await axios.post(`${API_BASE}/lab-orders/${selectedResultEntryOrder.id}/results`, {
        verify: isFinal,
        interpretation: resultInterpretation || null,
        results: resultEntryForm.map(r => ({
          parameter: r.parameter,
          result: r.result,
          unit: r.unit,
          range: r.range,
          flag: r.flag,
          remarks: r.remarks || null,
        })),
      });
      showToast(isFinal ? 'Result verified and report generated' : 'Draft saved');
      setSelectedResultEntryOrder(null);
      loadAllData();
      loadLabStats();
    } catch (err: any) { alert(err.response?.data?.detail || 'Failed to save result'); }
  };

  /** Create one bill for several selected lab orders (panel-aware pricing). */
  const handleBillSelectedOrders = async () => {
    if (selectedBillOrderIds.length === 0) return alert('Select at least one order to bill.');
    try {
      const res = await axios.post(`${API_BASE}/billing/lab/from-orders`, {
        order_ids: selectedBillOrderIds,
        mark_paid: true,
      });
      showToast(`Lab bill #${res.data.id} created — ₹${res.data.total}`);
      setSelectedBillOrderIds([]);
      loadAllData();
      loadLabStats();
    } catch (err: any) { alert(err.response?.data?.detail || 'Failed to create lab bill'); }
  };

  const toggleBillSelection = (orderId: number) =>
    setSelectedBillOrderIds(prev => prev.includes(orderId) ? prev.filter(id => id !== orderId) : [...prev, orderId]);

  const loadLabStats = async () => {
    try {
      const res = await axios.get(`${API_BASE}/lab/stats`);
      setLabStats(res.data);
    } catch (e) { console.error('Lab stats load failed', e); }
  };

  const handleCreateDirectLabOrders = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!labDirectOrderPatientId) return alert('No patient selected');
    if (labDirectOrderForm.test_ids.length === 0) return alert('Select at least one test');
    try {
      const res = await axios.post(`${API_BASE}/lab-orders/bulk`, {
        patient_id: labDirectOrderPatientId,
        test_ids: labDirectOrderForm.test_ids,
        doctor_name: labDirectOrderForm.referring_doctor,
        priority: labDirectOrderForm.priority,
      });
      showToast(`${res.data.length} lab order(s) created`);
      setIsLabOrderModalOpen(false);
      setLabDirectOrderPatientId(null);
      setLabDirectOrderForm({ test_ids: [], referring_doctor: 'Walk-in / Self', priority: 'Routine' });
      loadAllData();
      loadLabStats();
    } catch (err: any) { alert(err.response?.data?.detail || 'Failed to create lab orders'); }
  };

  /** Open a clean, print-isolated report window. */
  const printLabReport = (report: LabReport) => {
    const patient = patients.find(p => p.id === report.patient_id);
    const rows: LabResultRow[] = Array.isArray(report.results_data) ? report.results_data : [];
    const settings = hospitalSettings;

    const bodyRows = rows.length
      ? rows.map(r => `
          <tr class="${isFlagAbnormal(r.flag) ? 'abnormal' : ''}">
            <td>${r.parameter}</td>
            <td><b>${r.result ?? '-'}</b></td>
            <td>${r.unit || ''}</td>
            <td>${r.range || ''}</td>
            <td>${r.flag || ''}</td>
          </tr>`).join('')
      : `<tr><td>${report.test_name}</td><td><b>${report.result_value || '-'}</b></td><td>${report.units || ''}</td><td>${report.normal_range || ''}</td><td>-</td></tr>`;

    const order = labOrders.find(o => o.id === report.order_id);
    const html = `<html><head><title>Lab Report ${report.id}</title><style>
      body{font-family:Arial,sans-serif;padding:28px;color:#111}
      .head{text-align:center;border-bottom:2px solid #1e40af;padding-bottom:10px;margin-bottom:16px}
      .head h1{margin:0;color:#1e40af;font-size:20px}
      .head p{margin:3px 0;color:#666;font-size:12px}
      .meta{display:flex;justify-content:space-between;font-size:13px;margin-bottom:14px}
      table{width:100%;border-collapse:collapse;font-size:13px}
      th{background:#1e40af;color:#fff;padding:7px;text-align:left}
      td{padding:6px;border-bottom:1px solid #e5e7eb}
      tr.abnormal td{background:#fef2f2;color:#991b1b;font-weight:600}
      .foot{margin-top:26px;display:flex;justify-content:space-between;font-size:12px;color:#555}
      .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:#dcfce7;color:#166534}
      @media print{body{padding:8px}}
    </style></head><body>
      <div class="head">
        <h1>${settings.hospital_name || 'MedBill Pro Hospital'}</h1>
        <p>${settings.address || ''}</p>
        <p>${settings.contact || ''} ${settings.email ? '| ' + settings.email : ''}</p>
      </div>
      <h3 style="text-align:center;margin:6px 0 14px">LABORATORY REPORT</h3>
      <div class="meta">
        <div>
          <b>Patient:</b> ${patient?.name || 'N/A'}<br>
          <b>Age / Gender:</b> ${patient?.age ?? '-'} / ${patient?.gender || '-'}<br>
          <b>Patient ID:</b> ${report.patient_id}<br>
          <b>Phone:</b> ${patient?.phone || '-'}
        </div>
        <div style="text-align:right">
          <b>Report No:</b> #${report.id}<br>
          <b>Order No:</b> ${report.order_id ? '#' + report.order_id : '-'}<br>
          <b>Date:</b> ${new Date(report.date_conducted).toLocaleString()}<br>
          <b>Referred By:</b> ${order?.doctor_name || '-'}
        </div>
      </div>
      <p style="font-size:13px"><b>Test:</b> ${report.test_name}
        ${report.is_abnormal ? '<span class="badge" style="background:#fee2e2;color:#991b1b;margin-left:8px">ABNORMAL</span>' : '<span class="badge" style="margin-left:8px">NORMAL</span>'}
      </p>
      <table>
        <thead><tr><th>Parameter</th><th>Result</th><th>Unit</th><th>Reference Range</th><th>Flag</th></tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
      ${report.interpretation ? `<p style="margin-top:14px;font-size:13px"><b>Interpretation:</b> ${report.interpretation}</p>` : ''}
      ${report.remarks ? `<p style="font-size:13px"><b>Remarks:</b> ${report.remarks}</p>` : ''}
      <div class="foot">
        <div>Reported by: <b>${report.reported_by || '-'}</b><br>Status: ${report.status || 'Final'}</div>
        <div style="text-align:right">Verified by: <b>${report.verified_by || '-'}</b><br>${report.verified_at ? new Date(report.verified_at).toLocaleString() : ''}</div>
      </div>
      <p style="margin-top:30px;text-align:center;font-size:11px;color:#888">
        This is a computer-generated report. Please correlate clinically.
      </p>
    </body></html>`;

    const win = window.open('', '_blank', 'width=900,height=1000');
    if (!win) return alert('Please allow pop-ups to print the report.');
    win.document.write(html);
    win.document.close();
    win.focus();
    win.print();
  };

  const exportLabOrdersCsv = () => {
    const rows = labOrders.map(o => ({
      order_id: o.id,
      patient_id: o.patient_id,
      patient: patients.find(p => p.id === o.patient_id)?.name || '',
      test: o.test?.test_name || labTestMasters.find(t => t.id === o.test_id)?.test_name || '',
      priority: o.priority || 'Routine',
      status: o.status,
      ordered_at: o.order_date,
      due_at: o.due_at || '',
      billed: o.bill_id ? 'Yes' : 'No',
    }));
    exportToCSV(rows, `lab_orders_${new Date().toISOString().split('T')[0]}.csv`);
  };

  /** Move an OP token through its lifecycle (Pending → In Progress → Completed). */
  const handleUpdateTokenStatus = async (tokenId: number, status: string) => {
    try {
      await axios.put(`${API_BASE}/tokens/${tokenId}/status?status=${encodeURIComponent(status)}`);
      showToast(`Token marked ${status}`);
      loadAllData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update the token.');
    }
  };

  /** Update an appointment (check-in, complete, cancel). */
  const handleUpdateAppointmentStatus = async (appointmentId: number, status: string) => {
    try {
      await axios.put(`${API_BASE}/appointments/${appointmentId}`, { status });
      showToast(`Appointment ${status.toLowerCase()}`);
      loadAllData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update the appointment.');
    }
  };

  // Generate OP Token
  const handleGenerateToken = async () => {
    if (!selectedPatientId) return alert("Please select a patient");
    try {
      await axios.post(`${API_BASE}/tokens/`, {
        patient_id: Number(selectedPatientId),
        session: opSession,
        date: new Date().toISOString().split('T')[0],
        fee: opFee,
        details: tokenForm
      });
      alert("Token generated successfully!");
      loadAllData();
    } catch (err) {
      console.error(err);
    }
  };

  // Prescriptions handling
  const addMedicineToPrescription = () => {
    if (!newMed.medicine_id) return alert("Select a medicine");
    const stockItem = inventory.find(i => i.id === newMed.medicine_id);
    if (stockItem) {
      if (casesheetMeds.some(m => m.medicine_id === newMed.medicine_id)) {
        return alert("Medicine already added to prescription!");
      }
      setCasesheetMeds([...casesheetMeds, { ...newMed, name: stockItem.name }]);
      setNewMed({ medicine_id: 0, quantity: 1, duration: '', instructions: '', timing_morning: false, timing_afternoon: false, timing_night: false, timing_relation: 'After Food' });
    }
  };
  
  // Auto-calculate quantity effect
  useEffect(() => {
    const timesPerDay = (newMed.timing_morning ? 1 : 0) + (newMed.timing_afternoon ? 1 : 0) + (newMed.timing_night ? 1 : 0);
    const dur = parseInt(newMed.duration) || 0;
    if (timesPerDay > 0 && dur > 0) {
      setNewMed(prev => ({ ...prev, quantity: timesPerDay * dur }));
    }
  }, [newMed.timing_morning, newMed.timing_afternoon, newMed.timing_night, newMed.duration]);

  const removeMedicineFromPrescription = (index: number) => {
    setCasesheetMeds(casesheetMeds.filter((_, i) => i !== index));
  };

  const toggleLab = (labName: string) => {
    if (casesheetLabs.includes(labName)) setCasesheetLabs(casesheetLabs.filter(l => l !== labName));
    else setCasesheetLabs([...casesheetLabs, labName]);
  };

  // Save Casesheet

  const handleSaveCasesheet = async (isFinal: boolean) => {
    // Drafts are session-local; only a final save needs an active consultation.
    if (!isFinal) {
      alert("Draft saved locally for this session.");
      return;
    }
    if (!selectedOPToken) return alert("Please select an active consultation");
    const activeToken = selectedOPToken;

    const combinedSymptoms = `Chief Complaint: ${casesheetForm.chiefComplaint}
HPI: ${casesheetForm.hpi}
PMH: ${casesheetForm.pmh}
Family History: ${casesheetForm.familyHistory}
Allergies: ${casesheetForm.allergies}
Clinical Findings: ${casesheetForm.clinicalFindings}`.trim();

    const combinedDiagnosis = `Diagnosis: ${casesheetForm.diagnosis}
ICD Code: ${casesheetForm.icdCode}
Treatment Plan: ${casesheetForm.treatmentPlan}
Advice: ${casesheetForm.advice}
Follow-up: ${casesheetForm.followUpDate}`.trim();

    try {
      const res = await fetch(`${API_BASE}/casesheets/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: activeToken.patient_id,
          token_id: activeToken.id,
          doctor_name: activeToken.doctor_name || currentUser?.username || null,
          symptoms: combinedSymptoms,
          diagnosis: combinedDiagnosis,
          vitals_bp: casesheetForm.vitalsBp,
          vitals_pulse: casesheetForm.vitalsPulse,
          vitals_temp: casesheetForm.vitalsTemp,
          vitals_resp: casesheetForm.vitalsResp,
          prescribed_medicines: casesheetMeds.map(m => ({
            name: m.name, quantity: m.quantity, duration: m.duration,
            instructions: m.instructions,
            timing_morning: m.timing_morning, timing_afternoon: m.timing_afternoon, timing_night: m.timing_night,
            timing_relation: m.timing_relation
          })),
          prescribed_labs: casesheetLabs
        })
      });
      if (res.ok) {
        alert('Prescription Finalized successfully!');
        setSelectedOPToken(null);
        setCasesheetForm({ vitalsBp: '', vitalsPulse: '', vitalsTemp: '', vitalsResp: '', chiefComplaint: '', hpi: '', pmh: '', familyHistory: '', allergies: '', clinicalFindings: '', diagnosis: '', icdCode: '', treatmentPlan: '', advice: '', followUpDate: '' });
        setCasesheetMeds([]);
        setCasesheetLabs([]);
        loadAllData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleOrderDoctorLabs = async () => {
    if (!selectedDoctorPatientId) return alert("Please select a patient first.");
    if (casesheetLabs.length === 0) return alert("Please select at least one lab test to order.");
    
    try {
      for (const testName of casesheetLabs) {
        const test = labTestMasters.find(t => t.test_name === testName);
        if (test) {
          await axios.post(`${API_BASE}/lab-orders/`, {
            patient_id: selectedDoctorPatientId,
            doctor_name: currentUser?.username || 'Doctor',
            test_id: test.id,
            status: 'Pending',
            priority: 'Routine'
          });
        }
      }
      alert(`Successfully ordered ${casesheetLabs.length} lab tests.`);
      setCasesheetLabs([]);
      loadAllData();
    } catch (err) {
      console.error(err);
      alert("Failed to order labs.");
    }
  };

  const handleCreateDirectConsultation = async (type: string) => {
    if (!selectedDoctorPatientId) return alert("Please select a patient.");
    try {
      const res = await axios.post(`${API_BASE}/tokens/`, {
        patient_id: selectedDoctorPatientId,
        department: "General Medicine",
        doctor_name: currentUser?.username || 'Doctor',
        session: type, // "New Visit", "Follow-up", "Emergency"
        token_number: Math.floor(Math.random() * 1000)
      });
      alert(`${type} Consultation Created!`);
      loadAllData();
      setSelectedOPToken(res.data);
    } catch (err) {
      console.error(err);
      alert("Failed to create consultation.");
    }
  };
  const handleLoadPrescription = async (patId: number) => {
    try {
      const res = await axios.get(`${API_BASE}/patients/${patId}/casesheets/`);
      const casesheets = res.data;
      if (!casesheets || casesheets.length === 0) return alert("No casesheets found for this patient.");
      
      const latest = casesheets[0];
      if (!latest.prescribed_medicines || latest.prescribed_medicines.length === 0) {
        return alert("No medicines prescribed in the latest casesheet.");
      }

      let newCart = [...billingCart];
      let loadedCount = 0;
      const missingList: string[] = [];

      latest.prescribed_medicines.forEach((pm: any) => {
        // Try to match by generic name or brand name (or just medicine name if we had normalized it, but we can search inventory name)
        // Here we just search by name case-insensitive
        const medName = pm.name || pm.medicine_name || '';
        const stockItem = inventory.find(i => i.name.toLowerCase() === medName.toLowerCase());
        if (stockItem) {
          if (stockItem.quantity >= pm.quantity) {
            newCart.push({
              medicine_id: stockItem.id,
              name: stockItem.name,
              quantity: pm.quantity,
              unit_price: stockItem.unit_price
            });
            loadedCount++;
          } else {
             missingList.push(`${medName} (Insufficient Stock)`);
          }
        } else {
           missingList.push(`${medName} (Not found in inventory)`);
        }
      });
      setBillingCart(newCart);
      alert(`Loaded ${loadedCount} medicines. ${missingList.length > 0 ? "Skipped: " + missingList.join(", ") : ""}`);

    } catch (e) {
      console.error(e);
      alert("Failed to load prescription.");
    }
  };

  const handleBarcodeScan = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const code = barcodeInput.trim();
      if(!code) return;
      const stockItem = inventory.find(i => i.details?.barcode === code || String(i.id) === code || i.batch_no === code);
      if (stockItem) {
        setBillingNewItem({ medicine_id: stockItem.id, quantity: 1 });
        // Automatically add it to cart
        addToCart({ medicine_id: stockItem.id, quantity: 1 } as any, stockItem);
      } else {
        alert("Barcode/Item not found in inventory!");
      }
      setBarcodeInput('');
    }
  };

  const addToCart = (overrideItem?: any, stockRef?: any) => {
    const isEvent = overrideItem && overrideItem.nativeEvent;
    const itemToAdd = (!overrideItem || isEvent) ? billingNewItem : overrideItem;
    
    if (!itemToAdd.medicine_id || itemToAdd.quantity <= 0) return alert("Select medicine and quantity");
    const stockItem = stockRef || inventory.find(i => i.id === itemToAdd.medicine_id);
    if (!stockItem) return;
    if (stockItem.quantity < itemToAdd.quantity) {
      return alert(`Insufficient stock! Only ${stockItem.quantity} units left.`);
    }

    // Check if item already in cart
    const existing = billingCart.find(i => i.medicine_id === itemToAdd.medicine_id);
    if (existing) {
      if (stockItem.quantity < (existing.quantity + itemToAdd.quantity)) {
        return alert(`Cannot add. Exceeds available stock (${stockItem.quantity} units).`);
      }
      setBillingCart(billingCart.map(c => c.medicine_id === itemToAdd.medicine_id ? { ...c, quantity: c.quantity + itemToAdd.quantity } : c));
    } else {
      setBillingCart([...billingCart, {
        medicine_id: stockItem.id,
        name: stockItem.name,
        quantity: itemToAdd.quantity,
        unit_price: stockItem.unit_price
      }]);
    }
    if (!overrideItem || isEvent) setBillingNewItem({ medicine_id: 0, quantity: 1 });
  };

  const removeFromCart = (id: number) => {
    setBillingCart(billingCart.filter(item => item.medicine_id !== id));
  };

  // Submit Pharmacy Bill (Deducts stock automatically on backend)
  const handleCheckoutBill = async () => {
    if (billingCart.length === 0) return alert("Cart is empty");
    const payload = {
      patient_id: billingPatientType === 'registered' ? Number(billingPatientId) : null,
      patient_name: billingPatientType === 'walkin' ? billingWalkInName : null,
      discount: billingDiscount,
      gst: billingGst,
      items: billingCart.map(c => ({ medicine_id: c.medicine_id, quantity: c.quantity }))
    };

    try {
      const response = await axios.post(`${API_BASE}/billing/pharmacy/`, payload);
      alert("Pharmacy invoice generated and stock deducted successfully!");
      setBillingCart([]);
      setViewInvoice(response.data);
      setActiveTab('reports');
      loadAllData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Checkout failed");
    }
  };

  // Inventory Save
  const handleSaveInventoryItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inventoryForm.name) return;
    try {
      await axios.post(`${API_BASE}/inventory/`, inventoryForm);
      alert("Inventory item added!");
      setInventoryForm({
        name: '', category: 'Pharmacy', batch_no: '', expiry_date: '', quantity: 0, unit_price: 0, min_stock_level: 10,
        details: {
          medicineCode: '', genericName: '', brandName: '', manufacturer: '', hsnCode: '', gstPercent: 12,
          mrp: 0, purchasePrice: 0, rackNumber: '', storageLocation: '', maxStock: 100, barcode: '',
          medicineImage: '', description: '', dosageForm: '', strength: '', scheduleType: ''
        }
      });
      loadAllData();
    } catch (err) {
      console.error(err);
    }
  };

  // Process GRN (Stock In)
  const handleSaveGRN = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!grnForm.medicine_id) return alert("Please select a medicine.");
    try {
      await axios.post(`${API_BASE}/inventory/adjust/`, {
        medicine_id: Number(grnForm.medicine_id),
        type: grnForm.type,
        quantity: grnForm.quantity,
        notes: grnForm.notes,
        details: grnForm.details
      });
      alert("Stock successfully updated (GRN processed)!");
      setGrnForm({
        medicine_id: '', quantity: 1, type: 'Stock In', notes: '',
        details: { supplierName: '', invoiceNumber: '', purchaseOrder: '' }
      });
      loadAllData();
    } catch (err) {
      console.error(err);
      alert("Failed to process GRN.");
    }
  };

  // Calculation helpers
  const cartSubtotal = billingCart.reduce((sum, item) => sum + (item.quantity * item.unit_price), 0);
  const cartDiscountAmt = (billingDiscount / 100) * cartSubtotal;
  const cartGstAmt = (billingGst / 100) * (cartSubtotal - cartDiscountAmt);
  const cartTotal = cartSubtotal - cartDiscountAmt + cartGstAmt;

  const loadUsers = async () => {    try {
      const res = await axios.get(`${API_BASE}/users/?t=${new Date().getTime()}`);
      setUsers(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const formData = new URLSearchParams();
      formData.append('username', loginForm.username);
      formData.append('password', loginForm.password);
      
      const res = await axios.post(`${API_BASE}/login`, formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      const data = res.data;
      setToken(data.access_token);
      localStorage.setItem('token', data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }
      axios.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;
    } catch (err: any) {
      if (err.response && err.response.status === 429) {
        alert("Too many failed attempts. Account is temporarily locked.");
      } else {
        alert("Invalid credentials or account locked.");
      }
    }
  };

  const handleForgotPassword = () => {
    alert("Please contact the Administrator to reset your password.");
  };

  const handlePatientRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    const f = registerForm;
    if (!f.name.trim() || !f.username.trim()) return alert('Name and username are required.');
    if (!/^[6-9]\d{9}$/.test(f.phone.replace(/\D/g, ''))) return alert('Enter a valid 10-digit mobile number.');
    if (f.password !== f.confirm) return alert('The two passwords do not match.');
    if (f.password.length < 8 || !/[A-Z]/.test(f.password) || !/\d/.test(f.password)) {
      return alert('Password must be at least 8 characters and include an uppercase letter and a digit.');
    }
    setRegisterBusy(true);
    try {
      const res = await axios.post(`${API_BASE}/portal/register`, {
        username: f.username.trim(),
        password: f.password,
        name: f.name.trim(),
        age: Number(f.age),
        gender: f.gender,
        phone: f.phone.replace(/\D/g, ''),
        email: f.email.trim() || null,
        address: f.address.trim() || null,
        blood_group: f.blood_group || null,
      });
      const data = res.data;
      localStorage.setItem('token', data.access_token);
      if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;
      setToken(data.access_token);
      setAuthMode('login');
      showToast('Account created. Welcome!', 'success');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Could not create your account.');
    } finally {
      setRegisterBusy(false);
    }
  };

  if (!token || !currentUser) {
    return (
      <div className="login-container">
        <div className="login-card" style={{ maxWidth: authMode === 'register' ? '620px' : undefined }}>
          <div className="login-header">
            <Activity size={48} className="login-logo" />
            <h2>MEDBILL PRO</h2>
            <p>{authMode === 'login' ? 'Sign in to your account' : 'Create your patient account'}</p>
          </div>

          {authMode === 'login' ? (
            <>
              <form className="login-form" onSubmit={handleLogin}>
                <div className="form-group">
                  <label>Username or mobile number</label>
                  <input
                    type="text"
                    className="input-field"
                    value={loginForm.username}
                    onChange={e => setLoginForm({...loginForm, username: e.target.value})}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Password</label>
                  <input
                    type="password"
                    className="input-field"
                    value={loginForm.password}
                    onChange={e => setLoginForm({...loginForm, password: e.target.value})}
                    required
                  />
                </div>
                <div className="login-actions">
                  <button type="submit" className="btn btn-primary login-btn">Sign In</button>
                  <a href="#" className="forgot-password" onClick={handleForgotPassword}>Forgot Password?</a>
                </div>
              </form>
              <div style={{ marginTop: '18px', paddingTop: '16px', borderTop: '1px solid var(--border)', textAlign: 'center' }}>
                <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: '0 0 10px' }}>
                  New patient? Create an account to book appointments and view your reports.
                </p>
                <button type="button" className="btn btn-secondary" style={{ width: '100%' }} onClick={() => setAuthMode('register')}>
                  <UserRound size={16} /> Register as a patient
                </button>
              </div>
            </>
          ) : (
            <form className="login-form" onSubmit={handlePatientRegister}>
              <div className="form-grid">
                <div className="form-group">
                  <label>Full name *</label>
                  <input type="text" required value={registerForm.name} onChange={e => setRegisterForm({ ...registerForm, name: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Age *</label>
                  <input type="number" min="0" max="150" required value={registerForm.age || ''} onChange={e => setRegisterForm({ ...registerForm, age: Number(e.target.value) })} />
                </div>
                <div className="form-group">
                  <label>Gender *</label>
                  <select value={registerForm.gender} onChange={e => setRegisterForm({ ...registerForm, gender: e.target.value })}>
                    <option>Male</option><option>Female</option><option>Other</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Mobile number *</label>
                  <input
                    type="tel"
                    required
                    placeholder="10 digits"
                    value={registerForm.phone}
                    onChange={e => {
                      const digits = e.target.value.replace(/\D/g, '').slice(0, 10);
                      // Suggest the mobile number as the username on first typing.
                      setRegisterForm(prev => ({
                        ...prev,
                        phone: digits,
                        username: prev.username && prev.username !== prev.phone ? prev.username : digits,
                      }));
                    }}
                  />
                </div>
                <div className="form-group">
                  <label>Username *</label>
                  <input type="text" required value={registerForm.username} onChange={e => setRegisterForm({ ...registerForm, username: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Email</label>
                  <input type="email" value={registerForm.email} onChange={e => setRegisterForm({ ...registerForm, email: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Blood group</label>
                  <select value={registerForm.blood_group} onChange={e => setRegisterForm({ ...registerForm, blood_group: e.target.value })}>
                    <option value="">--</option>
                    <option>A+</option><option>A-</option><option>B+</option><option>B-</option>
                    <option>AB+</option><option>AB-</option><option>O+</option><option>O-</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Address</label>
                  <input type="text" value={registerForm.address} onChange={e => setRegisterForm({ ...registerForm, address: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Password *</label>
                  <input type="password" required value={registerForm.password} onChange={e => setRegisterForm({ ...registerForm, password: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Confirm password *</label>
                  <input type="password" required value={registerForm.confirm} onChange={e => setRegisterForm({ ...registerForm, confirm: e.target.value })} />
                </div>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '4px 0 12px' }}>
                Password needs at least 8 characters, one uppercase letter and one digit.
              </p>
              <div className="login-actions">
                <button type="submit" className="btn btn-primary login-btn" disabled={registerBusy}>
                  {registerBusy ? <><Loader2 size={16} className="spin" /> Creating…</> : 'Create account'}
                </button>
                <a href="#" className="forgot-password" onClick={e => { e.preventDefault(); setAuthMode('login'); }}>
                  Back to sign in
                </a>
              </div>
            </form>
          )}
        </div>
      </div>
    );
  }

  // Patient self-service accounts get their own shell; they have no access to the
  // hospital modules (enforced server-side, mirrored here for a sane UI).
  if (currentUser.role === 'Patient') {
    return (
      <PatientPortal
        user={currentUser}
        theme={theme}
        onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        onLogout={() => { setToken(null); setCurrentUser(null); }}
      />
    );
  }

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <div className="sidebar no-print">
        <div className="logo-container">
          <Activity size={28} className="logo-text" style={{ color: 'var(--accent-blue)' }} />
          <span className="logo-text">MEDBILL PRO</span>
        </div>
        <nav className="nav-links">
          {currentUser.role === 'Admin' && (
            <>
              <div className="nav-section-title" style={{fontSize:'10px', color:'var(--text-muted)', padding:'10px 20px', letterSpacing:'1px', marginTop:'10px'}}>ADMIN MODULES</div>
              <div className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}><Activity size={20} /> Dashboard</div>
              <div className={`nav-item ${activeTab === 'front_desk' ? 'active' : ''}`} onClick={() => setActiveTab('front_desk')}><Clipboard size={20} /> Front Desk Flow</div>
              <div className={`nav-item ${activeTab === 'users' ? 'active' : ''}`} onClick={() => { setActiveTab('users'); loadUsers(); }}><Users size={20} /> User Management</div>
              <div className={`nav-item ${activeTab === 'search' ? 'active' : ''}`} onClick={() => setActiveTab('search')}><Search size={20} /> Global Search</div>
              
              <div className="nav-section-title" style={{fontSize:'10px', color:'var(--text-muted)', padding:'10px 20px', letterSpacing:'1px', marginTop:'10px'}}>HOSPITAL MODULES</div>
              <div className={`nav-item ${activeTab === 'patients' ? 'active' : ''}`} onClick={() => setActiveTab('patients')}><Users size={20} /> Registration &amp; Tokens</div>
              <div className={`nav-item ${activeTab === 'doctor_workspace' ? 'active' : ''}`} onClick={() => setActiveTab('doctor_workspace')}><Activity size={20} /> Doctor Flow</div>
              <div className={`nav-item ${activeTab === 'casesheet' ? 'active' : ''}`} onClick={() => setActiveTab('casesheet')}><Clipboard size={20} /> OP Casesheet &amp; Prescription</div>
              <div className={`nav-item ${activeTab === 'ipd_workspace' ? 'active' : ''}`} onClick={() => { setActiveTab('ipd_workspace'); loadIpdStructure(); }}><Bed size={20} /> Inpatient Ward</div>
              <div className={`nav-item ${activeTab === 'ip_admissions' ? 'active' : ''}`} onClick={() => { setActiveTab('ip_admissions'); loadIpdStructure(); }}><Clipboard size={20} /> Admit Patient</div>
              <div className={`nav-item ${activeTab === 'ipd_setup' ? 'active' : ''}`} onClick={() => { setActiveTab('ipd_setup'); loadIpdStructure(); }}><Building2 size={20} /> Ward &amp; Bed Setup</div>
              
              <div className="nav-section-title" style={{fontSize:'10px', color:'var(--text-muted)', padding:'10px 20px', letterSpacing:'1px', marginTop:'10px'}}>BILLING</div>
              <div className={`nav-item ${activeTab === 'billing' ? 'active' : ''}`} onClick={() => { setActiveTab('billing'); setBillingTab('op'); }}><Receipt size={20} /> Billing Module</div>
              <div className={`nav-item ${activeTab === 'pharmacy_workspace' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_workspace')}><ShoppingBag size={20} /> Pharmacy Flow</div>
              <div className={`nav-item ${activeTab === 'pharmacy_purchase' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_purchase')}><UploadCloud size={20} /> Purchase / GRN</div>
              <div className={`nav-item ${activeTab === 'pharmacy_expiry' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_expiry')}><AlertTriangle size={20} /> Expiry Management</div>
              
              <div className="nav-section-title" style={{fontSize:'10px', color:'var(--text-muted)', padding:'10px 20px', letterSpacing:'1px', marginTop:'10px'}}>LABORATORY</div>
              <div className={`nav-item ${activeTab === 'lab_dashboard' ? 'active' : ''}`} onClick={() => { setActiveTab('lab_dashboard'); loadLabStats(); }}><Activity size={20} /> Lab Dashboard</div>
              <div className={`nav-item ${activeTab === 'lab_master' ? 'active' : ''}`} onClick={() => setActiveTab('lab_master')}><Database size={20} /> Lab Test Master</div>
              <div className={`nav-item ${activeTab === 'lab_orders' ? 'active' : ''}`} onClick={() => setActiveTab('lab_orders')}><FileText size={20} /> Lab Orders</div>
              <div className={`nav-item ${activeTab === 'lab_samples' ? 'active' : ''}`} onClick={() => setActiveTab('lab_samples')}><FlaskConical size={20} /> Sample Collection</div>
              <div className={`nav-item ${activeTab === 'lab_results' ? 'active' : ''}`} onClick={() => setActiveTab('lab_results')}><Clipboard size={20} /> Lab Result Entry</div>
              <div className={`nav-item ${activeTab === 'lab_reports_new' ? 'active' : ''}`} onClick={() => { setActiveTab('lab_reports_new'); loadLabStats(); }}><CheckCircle size={20} /> Lab Reports</div>

              <div className="nav-section-title" style={{fontSize:'10px', color:'var(--text-muted)', padding:'10px 20px', letterSpacing:'1px', marginTop:'10px'}}>OTHER</div>
              <div className={`nav-item ${activeTab === 'inventory' ? 'active' : ''}`} onClick={() => setActiveTab('inventory')}><Database size={20} /> Inventory</div>
              <div className={`nav-item ${activeTab === 'insurance' ? 'active' : ''}`} onClick={() => { setActiveTab('insurance'); loadInsurance(); }}><Shield size={20} /> Insurance Claims</div>
              <div className={`nav-item ${activeTab === 'insurance_policies' ? 'active' : ''}`} onClick={() => { setActiveTab('insurance_policies'); loadInsurance(); }}><Shield size={20} /> Insurance Policies</div>
              <div className={`nav-item ${activeTab === 'billing_lab' ? 'active' : ''}`} onClick={() => setActiveTab('billing_lab')}><FlaskConical size={20} /> Lab Billing</div>
              <div className={`nav-item ${activeTab === 'pharmacy_invoices' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_invoices')}><Receipt size={20} /> Pharmacy Invoices</div>
              <div className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => { setActiveTab('reports'); loadDailyReport(); loadRevenueReport(); }}><BarChart2 size={20} /> Reports</div>
              {currentUser.role === 'Admin' && <div className={`nav-item ${activeTab === 'admin_settings' ? 'active' : ''}`} onClick={() => { setActiveTab('admin_settings'); loadHospitalSettings(); loadAuditLogs(); }}><Settings size={20} /> Admin Settings</div>}
            </>
          )}

          {currentUser.role === 'Receptionist' && (
              <>
                <div className="sidebar-section">Front Desk</div>
                <div className={`nav-item ${activeTab === 'front_desk' ? 'active' : ''}`} onClick={() => setActiveTab('front_desk')}><Activity size={20} /> Front Desk Flow</div>
                <div className={`nav-item ${activeTab === 'patients' ? 'active' : ''}`} onClick={() => setActiveTab('patients')}><Users size={20} /> Registration</div>
                <div className={`nav-item ${activeTab === 'op_token' ? 'active' : ''}`} onClick={() => setActiveTab('op_token')}><Clipboard size={20} /> Token &amp; Check-in</div>
                <div className={`nav-item ${activeTab === 'live_queue' ? 'active' : ''}`} onClick={() => setActiveTab('live_queue')}><List size={20} /> Live Queue</div>
                <div className={`nav-item ${activeTab === 'appointments' ? 'active' : ''}`} onClick={() => setActiveTab('appointments')}><Calendar size={20} /> Appointments</div>
                <div className="sidebar-section">Records &amp; Money</div>
                <div className={`nav-item ${activeTab === 'billing' ? 'active' : ''}`} onClick={() => { setActiveTab('billing'); setBillingTab('op'); }}><Receipt size={20} /> Billing &amp; Payment</div>
                <div className={`nav-item ${activeTab === 'ip_admissions' ? 'active' : ''}`} onClick={() => setActiveTab('ip_admissions')}><Bed size={20} /> IP Admissions</div>
                <div className={`nav-item ${activeTab === 'patient_history' ? 'active' : ''}`} onClick={() => setActiveTab('patient_history')}><Search size={20} /> Patient Database</div>
                <div className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => setActiveTab('reports')}><BarChart2 size={20} /> Reports</div>
              </>
            )}

          {currentUser.role === 'Pharmacy' && (
            <>
              <div className="sidebar-section">Pharmacy</div>
              <div className={`nav-item ${activeTab === 'pharmacy_workspace' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_workspace')}><Activity size={20} /> Pharmacy Flow</div>
              <div className={`nav-item ${activeTab === 'pharmacy' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy')}><ShoppingBag size={20} /> Dispensary &amp; Billing</div>
              <div className={`nav-item ${activeTab === 'pharmacy_search' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_search')}><Search size={20} /> Medicine Search</div>
              <div className="sidebar-section">Stock</div>
              <div className={`nav-item ${activeTab === 'pharmacy_purchase' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_purchase')}><UploadCloud size={20} /> Purchase / GRN</div>
              <div className={`nav-item ${activeTab === 'pharmacy_expiry' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_expiry')}><AlertTriangle size={20} /> Expiry Management</div>
              <div className={`nav-item ${activeTab === 'inventory' ? 'active' : ''}`} onClick={() => setActiveTab('inventory')}><Database size={20} /> Full Inventory</div>
              <div className="sidebar-section">Records</div>
              <div className={`nav-item ${activeTab === 'pharmacy_invoices' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_invoices')}><Receipt size={20} /> Pharmacy Invoices</div>
              <div className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => setActiveTab('reports')}><BarChart2 size={20} /> Reports</div>
            </>
          )}

          {currentUser.role === 'Doctor' && (
            <div className="sidebar-group">
              <div className="group-title">Consultation</div>
              <div className={`nav-item ${activeTab === 'doctor_workspace' ? 'active' : ''}`} onClick={() => setActiveTab('doctor_workspace')}><Activity size={20} /> My Workflow</div>
              <div className={`nav-item ${activeTab === 'live_queue' ? 'active' : ''}`} onClick={() => setActiveTab('live_queue')}><List size={20} /> Today's Queue</div>
              <div className={`nav-item ${activeTab === 'casesheet' ? 'active' : ''}`} onClick={() => setActiveTab('casesheet')}><Clipboard size={20} /> Case Sheet &amp; Prescription</div>
              <div className="group-title">Results</div>
              <div className={`nav-item ${activeTab === 'lab_orders' ? 'active' : ''}`} onClick={() => setActiveTab('lab_orders')}><FlaskConical size={20} /> Lab Orders</div>
              <div className={`nav-item ${activeTab === 'lab_reports_new' ? 'active' : ''}`} onClick={() => setActiveTab('lab_reports_new')}><FileText size={20} /> Lab Reports</div>
              <div className={`nav-item ${activeTab === 'appointments' ? 'active' : ''}`} onClick={() => setActiveTab('appointments')}><Calendar size={20} /> Appointments</div>
              <div className={`nav-item ${activeTab === 'patient_history' ? 'active' : ''}`} onClick={() => setActiveTab('patient_history')}><Search size={20} /> Patient Database</div>
            </div>
          )}

          {currentUser.role === 'Nurse' && (
            <div className="sidebar-group">
              <div className="group-title">Ward</div>
              <div className={`nav-item ${activeTab === 'ipd_workspace' ? 'active' : ''}`} onClick={() => { setActiveTab('ipd_workspace'); loadIpdStructure(); }}><Bed size={20} /> Bed Board &amp; Ward</div>
              <div className={`nav-item ${activeTab === 'live_queue' ? 'active' : ''}`} onClick={() => setActiveTab('live_queue')}><List size={20} /> OP Queue</div>
              <div className="group-title">Patients</div>
              <div className={`nav-item ${activeTab === 'patient_history' ? 'active' : ''}`} onClick={() => setActiveTab('patient_history')}><Search size={20} /> Patient Database</div>
              <div className={`nav-item ${activeTab === 'appointments' ? 'active' : ''}`} onClick={() => setActiveTab('appointments')}><Calendar size={20} /> Appointments</div>
            </div>
          )}

          {currentUser.role === 'Laboratory' && (
            <div className="sidebar-group">
              <div className="group-title">Laboratory</div>
              <div className={`nav-item ${activeTab === 'lab_dashboard' ? 'active' : ''}`} onClick={() => { setActiveTab('lab_dashboard'); loadLabStats(); }}><Activity size={20} /> Dashboard</div>
              <div className={`nav-item ${activeTab === 'lab_master' ? 'active' : ''}`} onClick={() => setActiveTab('lab_master')}><Database size={20} /> Test Master</div>
              <div className={`nav-item ${activeTab === 'lab_orders' ? 'active' : ''}`} onClick={() => setActiveTab('lab_orders')}><FileText size={20} /> Lab Orders</div>
              <div className={`nav-item ${activeTab === 'lab_samples' ? 'active' : ''}`} onClick={() => setActiveTab('lab_samples')}><FlaskConical size={20} /> Sample Collection</div>
              <div className={`nav-item ${activeTab === 'lab_results' ? 'active' : ''}`} onClick={() => setActiveTab('lab_results')}><Clipboard size={20} /> Result Entry</div>
              <div className={`nav-item ${activeTab === 'lab_reports_new' ? 'active' : ''}`} onClick={() => setActiveTab('lab_reports_new')}><CheckCircle size={20} /> Reports</div>
            </div>
          )}

          {currentUser.role === 'Insurance' && (
            <div className="sidebar-group">
              <div className="group-title">Insurance Desk</div>
              <div className={`nav-item ${activeTab === 'insurance' ? 'active' : ''}`} onClick={() => { setActiveTab('insurance'); loadInsurance(); }}><Activity size={20} /> Claims Dashboard</div>
              <div className={`nav-item ${activeTab === 'insurance_policies' ? 'active' : ''}`} onClick={() => { setActiveTab('insurance_policies'); loadInsurance(); }}><Shield size={20} /> Policies</div>
              <div className={`nav-item ${activeTab === 'patient_history' ? 'active' : ''}`} onClick={() => setActiveTab('patient_history')}><Search size={20} /> Patient Lookup</div>
            </div>
          )}

          {currentUser.role === 'Billing' && (
            <div className="sidebar-group">
              <div className="group-title">Billing Desk</div>
              <div className={`nav-item ${activeTab === 'billing' ? 'active' : ''}`} onClick={() => { setActiveTab('billing'); setBillingTab('op'); }}><Receipt size={20} /> OP / IP Billing</div>
              <div className={`nav-item ${activeTab === 'pharmacy_invoices' ? 'active' : ''}`} onClick={() => setActiveTab('pharmacy_invoices')}><FileText size={20} /> Pharmacy Invoices</div>
              <div className={`nav-item ${activeTab === 'billing_lab' ? 'active' : ''}`} onClick={() => { setActiveTab('billing_lab'); }}><FlaskConical size={20} /> Lab Billing</div>
              <div className={`nav-item ${activeTab === 'patient_history' ? 'active' : ''}`} onClick={() => setActiveTab('patient_history')}><Search size={20} /> Patient Lookup</div>
              <div className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => { setActiveTab('reports'); loadDailyReport(); loadRevenueReport(); }}><BarChart2 size={20} /> Reports</div>
            </div>
          )}
        </nav>
        
        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar">{currentUser.username.charAt(0).toUpperCase()}</div>
            <div className="user-info">
              <span className="user-name">{currentUser.username}</span>
              <span className="user-role">{currentUser.role}</span>
            </div>
          </div>
          <button className="logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      {/* Main Content Pane */}
      <div className="main-content">
        {/* Top Navbar */}
        <div className="top-navbar no-print" style={{display:'flex', justifyContent:'space-between', alignItems:'center', padding:'16px 24px', background:'var(--bg-card)', borderBottom:'1px solid var(--border)', marginBottom:'24px', position:'sticky', top:0, zIndex:90}}>
          <div style={{fontWeight:600, fontSize:'16px'}}>Welcome back, {currentUser.username}!</div>
          <div style={{display:'flex', gap:'12px', alignItems:'center'}}>
            <button onClick={() => { setPasswordForm({ current: '', next: '', confirm: '' }); setIsPasswordModalOpen(true); }} className="btn btn-secondary" style={{display:'flex', alignItems:'center', gap:'6px'}} title="Change my password">
              <Shield size={16}/> Change password
            </button>
            <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="btn btn-primary" style={{padding:'8px', borderRadius:'50%', background:'transparent', border:'1px solid var(--border)', color:'var(--text-primary)'}} title="Toggle Theme">
              {theme === 'dark' ? <Sun size={18}/> : <Moon size={18}/>}
            </button>
            <div style={{background:'rgba(59,130,246,0.1)', color:'var(--accent-blue)', padding:'6px 12px', borderRadius:'20px', fontSize:'13px', fontWeight:600}}>
              {new Date().toLocaleDateString()}
            </div>
          </div>
        </div>

        {/* CHANGE MY PASSWORD */}
        {isPasswordModalOpen && (
          <div className="modal-overlay">
            <div className="modal-content" style={{ maxWidth: '440px' }}>
              <div className="modal-header">
                <h2>Change my password</h2>
                <button className="close-btn" onClick={() => setIsPasswordModalOpen(false)}><X size={20}/></button>
              </div>
              <div className="modal-body">
                <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: 0 }}>
                  Signed in as <b>{currentUser.username}</b>. Minimum 8 characters, with a letter, an uppercase letter and a digit.
                </p>
                <div className="form-group" style={{ marginTop: '12px' }}>
                  <label>Current password</label>
                  <input type="password" value={passwordForm.current} onChange={e => setPasswordForm({ ...passwordForm, current: e.target.value })} />
                </div>
                <div className="form-group" style={{ marginTop: '12px' }}>
                  <label>New password</label>
                  <input type="password" value={passwordForm.next} onChange={e => setPasswordForm({ ...passwordForm, next: e.target.value })} />
                </div>
                <div className="form-group" style={{ marginTop: '12px' }}>
                  <label>Confirm new password</label>
                  <input type="password" value={passwordForm.confirm} onChange={e => setPasswordForm({ ...passwordForm, confirm: e.target.value })} />
                </div>
                <button className="btn btn-primary" style={{ width: '100%', marginTop: '20px' }} onClick={handleChangeMyPassword}>
                  <Save size={16}/> Update password
                </button>
              </div>
            </div>
          </div>
        )}


        {activeTab === 'dashboard' && (
          <div>
            <div className="header no-print">
              <div className="header-title">
                <h1>Hospital Dashboard</h1>
                <p>Live overview — {new Date().toLocaleDateString('en-IN', {weekday:'long', year:'numeric', month:'long', day:'numeric'})}</p>
              </div>
              <button className="btn btn-primary" style={{display:'flex',alignItems:'center',gap:'6px'}} onClick={loadDashboardData}>
                <RefreshCw size={16} /> Refresh
              </button>
            </div>


            {currentUser?.role === 'Admin' ? (
              <>
                {/* 6 Stats Cards */}
            <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'16px',marginBottom:'20px'}}>
              <div className="glass-card stat-card" style={{borderLeft:'4px solid #3b82f6'}}>
                <div className="stat-icon" style={{backgroundColor:'rgba(59,130,246,0.15)',color:'var(--accent-blue)'}}><Users size={24}/></div>
                <div>
                  <label>Today's Patients</label>
                  <div className="stat-val">{dashStats?.today_patients ?? patients.filter(p => new Date(p.created_at).toDateString() === new Date().toDateString()).length}</div>
                  <small style={{color:'var(--text-muted)'}}>Total: {dashStats?.total_patients ?? patients.length}</small>
                </div>
              </div>
              <div className="glass-card stat-card" style={{borderLeft:'4px solid #10b981'}}>
                <div className="stat-icon" style={{backgroundColor:'rgba(16,185,129,0.15)',color:'var(--accent-emerald)'}}><DollarSign size={24}/></div>
                <div>
                  <label>Today's Revenue</label>
                  <div className="stat-val">₹{dashStats ? dashStats.today_revenue.toFixed(2) : '0.00'}</div>
                  <small style={{color:'var(--text-muted)'}}>All bills combined</small>
                </div>
              </div>
              <div className="glass-card stat-card" style={{borderLeft:'4px solid #8b5cf6'}}>
                <div className="stat-icon" style={{backgroundColor:'rgba(139,92,246,0.15)',color:'var(--accent-violet)'}}><Clipboard size={24}/></div>
                <div>
                  <label>OP Count (Today)</label>
                  <div className="stat-val">{dashStats?.op_count ?? tokens.filter(t => t.date === new Date().toISOString().split('T')[0]).length}</div>
                  <small style={{color:'var(--text-muted)'}}>Outpatient tokens</small>
                </div>
              </div>
              <div className="glass-card stat-card" style={{borderLeft:'4px solid #f59e0b'}}>
                <div className="stat-icon" style={{backgroundColor:'rgba(245,158,11,0.15)',color:'var(--accent-amber)'}}><Bed size={24}/></div>
                <div>
                  <label>IP Count (Active)</label>
                  <div className="stat-val">{dashStats?.ip_count ?? ipAdmissions.filter(a => a.status === 'Admitted').length}</div>
                  <small style={{color:'var(--text-muted)'}}>Inpatients admitted</small>
                </div>
              </div>
              <div className="glass-card stat-card" style={{borderLeft:'4px solid #06b6d4'}}>
                <div className="stat-icon" style={{backgroundColor:'rgba(6,182,212,0.15)',color:'var(--accent-cyan)'}}><FlaskConical size={24}/></div>
                <div>
                  <label>Lab Count (Today)</label>
                  <div className="stat-val">{dashStats?.lab_count ?? labReports.filter(r => new Date(r.date_conducted).toDateString() === new Date().toDateString()).length}</div>
                  <small style={{color:'var(--text-muted)'}}>Lab tests done</small>
                </div>
              </div>
              <div className="glass-card stat-card" style={{borderLeft:'4px solid #f43f5e'}}>
                <div className="stat-icon" style={{backgroundColor:'rgba(244,63,94,0.15)',color:'var(--accent-rose)'}}><ShoppingBag size={24}/></div>
                <div>
                  <label>Medicine Sales (Today)</label>
                  <div className="stat-val">₹{dashStats ? dashStats.medicine_sales.toFixed(2) : '0.00'}</div>
                  <small style={{color:'var(--accent-amber)',fontWeight:600}}>⚠ Low Stock: {dashStats?.low_stock_count ?? inventory.filter(i=>i.quantity<=i.min_stock_level).length} items</small>
                </div>
              </div>
            </div>

            {/* 4 Charts */}
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px',marginBottom:'20px'}}>
              <div className="glass-card">
                {dashCharts?.daily_revenue ? <BarChart data={dashCharts.daily_revenue} title="DAILY REVENUE (Last 7 Days)" color="#3b82f6" /> : <div style={{padding:'16px',color:'var(--text-muted)'}}>Loading daily revenue chart...</div>}
              </div>
              <div className="glass-card">
                {dashCharts?.monthly_revenue ? <BarChart data={dashCharts.monthly_revenue} title="MONTHLY REVENUE (Last 6 Months)" color="#10b981" /> : <div style={{padding:'16px',color:'var(--text-muted)'}}>Loading monthly revenue chart...</div>}
              </div>
              <div className="glass-card">
                {dashCharts?.patient_growth ? <BarChart data={dashCharts.patient_growth} title="PATIENT GROWTH (Last 6 Months)" color="#8b5cf6" valuePrefix="" /> : <div style={{padding:'16px',color:'var(--text-muted)'}}>Loading patient growth chart...</div>}
              </div>
              <div className="glass-card">
                {dashCharts?.medicine_sales && dashCharts.medicine_sales.length > 0 ? <BarChart data={dashCharts.medicine_sales} title="TOP MEDICINE SALES" color="#f59e0b" /> : <div style={{padding:'16px',color:'var(--text-muted)'}}>No medicine sales data yet</div>}
              </div>
            </div>

            {/* Alerts + Queue */}
            <div className="form-grid no-print">
              <div className="glass-card">
                <h3 style={{marginBottom:'16px',display:'flex',alignItems:'center',gap:'8px'}}><AlertTriangle color="#f59e0b" size={20}/> Low Stock Alert</h3>
                <div className="table-container">
                  <table><thead><tr><th>Item</th><th>Category</th><th>Available</th><th>Min Stock</th></tr></thead>
                    <tbody>
                      {inventory.filter(i=>i.quantity<=i.min_stock_level).map(item=>(
                        <tr key={item.id}><td>{item.name}</td><td>{item.category}</td><td style={{color:'var(--accent-rose)',fontWeight:700}}>{item.quantity}</td><td>{item.min_stock_level}</td></tr>
                      ))}
                      {inventory.filter(i=>i.quantity<=i.min_stock_level).length===0&&<tr><td colSpan={4} style={{textAlign:'center',color:'var(--accent-emerald)'}}>✅ All stock levels are healthy</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="glass-card">
                <h3>Today's OP Queue</h3>
                <div className="table-container">
                  <table><thead><tr><th>Token</th><th>Session</th><th>Patient</th><th>Status</th></tr></thead>
                    <tbody>
                      {tokens.filter(t=>t.date===new Date().toISOString().split('T')[0]).map(token=>(
                        <tr key={token.id}>
                          <td><div className="token-circle">{token.token_number}</div></td>
                          <td>{token.session}</td><td>{token.patient?.name}</td>
                          <td><span className={`badge badge-${(token.status || '').toLowerCase()}`}>{token.status}</span></td>
                        </tr>
                      ))}
                      {tokens.filter(t=>t.date===new Date().toISOString().split('T')[0]).length===0&&<tr><td colSpan={4} style={{textAlign:'center',color:'var(--text-muted)'}}>No patients in queue today</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
              </>
            ) : currentUser?.role === 'Doctor' ? (
              <>
                <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:'16px',marginBottom:'20px'}}>
                  <div className="glass-card stat-card" style={{borderLeft:'4px solid #3b82f6'}}>
                    <div className="stat-icon" style={{backgroundColor:'rgba(59,130,246,0.15)',color:'var(--accent-blue)'}}><Users size={24}/></div>
                    <div>
                      <label>Today's Appointments</label>
                      <div className="stat-val">{tokens.filter(t => t.date === new Date().toISOString().split('T')[0]).length}</div>
                    </div>
                  </div>
                  <div className="glass-card stat-card" style={{borderLeft:'4px solid #f59e0b'}}>
                    <div className="stat-icon" style={{backgroundColor:'rgba(245,158,11,0.15)',color:'var(--accent-amber)'}}><Clock size={24}/></div>
                    <div>
                      <label>Waiting Patients</label>
                      <div className="stat-val">{tokens.filter(t => t.status === 'Pending').length}</div>
                    </div>
                  </div>
                  <div className="glass-card stat-card" style={{borderLeft:'4px solid #8b5cf6'}}>
                    <div className="stat-icon" style={{backgroundColor:'rgba(139,92,246,0.15)',color:'var(--accent-violet)'}}><Clipboard size={24}/></div>
                    <div>
                      <label>OP Patients (Active)</label>
                      <div className="stat-val">{dashStats?.op_count ?? tokens.filter(t => t.date === new Date().toISOString().split('T')[0]).length}</div>
                    </div>
                  </div>
                  <div className="glass-card stat-card" style={{borderLeft:'4px solid #10b981'}}>
                    <div className="stat-icon" style={{backgroundColor:'rgba(16,185,129,0.15)',color:'var(--accent-emerald)'}}><Bed size={24}/></div>
                    <div>
                      <label>IP Patients (Admitted)</label>
                      <div className="stat-val">{ipAdmissions.filter(a => a.status === 'Admitted').length}</div>
                    </div>
                  </div>
                  
                  <div className="glass-card stat-card" style={{borderLeft:'4px solid #ef4444'}}>
                    <div className="stat-icon" style={{backgroundColor:'rgba(239,68,68,0.15)',color:'var(--accent-rose)'}}><AlertTriangle size={24}/></div>
                    <div>
                      <label>Emergency Patients</label>
                      <div className="stat-val">{tokens.filter(t => t.session === 'Evening' && t.status === 'Pending').length}</div>
                    </div>
                  </div>
                  <div className="glass-card stat-card" style={{borderLeft:'4px solid #0ea5e9'}}>
                    <div className="stat-icon" style={{backgroundColor:'rgba(14,165,233,0.15)',color:'var(--accent-sky)'}}><RefreshCw size={24}/></div>
                    <div>
                      <label>Follow-up Patients</label>
                      <div className="stat-val">{patients.filter(p => tokens.filter(t => t.patient_id === p.id).length > 1).length}</div>
                    </div>
                  </div>
                  <div className="glass-card stat-card" style={{borderLeft:'4px solid #f43f5e'}}>
                    <div className="stat-icon" style={{backgroundColor:'rgba(244,63,94,0.15)',color:'var(--accent-rose)'}}><FlaskConical size={24}/></div>
                    <div>
                      <label>Pending Lab Results</label>
                      <div className="stat-val">{labReports.filter(r => !r.result_value || r.result_value.trim() === '').length}</div>
                    </div>
                  </div>
                  <div className="glass-card stat-card" style={{borderLeft:'4px solid #10b981'}}>
                    <div className="stat-icon" style={{backgroundColor:'rgba(16,185,129,0.15)',color:'var(--accent-emerald)'}}><DollarSign size={24}/></div>
                    <div>
                      <label>Today's Revenue</label>
                      <div className="stat-val">₹{dashStats ? dashStats.today_revenue.toFixed(2) : '0.00'}</div>
                      <small style={{color:'var(--text-muted)'}}>View Only</small>
                    </div>
                  </div>
                </div>

                <div className="form-grid no-print">
                  <div className="glass-card">
                    <h3 style={{marginBottom:'16px',display:'flex',alignItems:'center',gap:'8px'}}><Activity color="#3b82f6" size={20}/> Patient Statistics</h3>
                    <div style={{display:'flex', gap:'20px', flexWrap:'wrap'}}>
                      <div style={{flex:1, minWidth:'150px', background:'rgba(255,255,255,0.05)', padding:'15px', borderRadius:'10px'}}>
                        <div style={{color:'var(--text-muted)', fontSize:'12px', marginBottom:'5px'}}>Total Registered Patients</div>
                        <div style={{fontSize:'24px', fontWeight:'bold', color:'var(--text-primary)'}}>{dashStats?.total_patients ?? patients.length}</div>
                      </div>
                      <div style={{flex:1, minWidth:'150px', background:'rgba(255,255,255,0.05)', padding:'15px', borderRadius:'10px'}}>
                        <div style={{color:'var(--text-muted)', fontSize:'12px', marginBottom:'5px'}}>Today's New Registrations</div>
                        <div style={{fontSize:'24px', fontWeight:'bold', color:'var(--text-primary)'}}>{dashStats?.today_patients ?? patients.filter(p => new Date(p.created_at).toDateString() === new Date().toDateString()).length}</div>
                      </div>
                    </div>
                  </div>
                  <div className="glass-card">
                    <h3 style={{marginBottom:'16px',display:'flex',alignItems:'center',gap:'8px'}}><FileText color="#8b5cf6" size={20}/> Recent Prescriptions</h3>
                    <div style={{color:'var(--text-muted)', fontSize:'14px', fontStyle:'italic'}}>
                      Prescriptions are generated directly via the OP Casesheet module. 
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div style={{padding:'40px', textAlign:'center', color:'var(--text-muted)'}}>
                <h2>Welcome to MedBill Pro</h2>
                <p>Select an option from the sidebar to begin.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'front_desk' && (() => {
          const today = new Date().toDateString();
          const todayTokens = tokens.filter(t => new Date(t.date).toDateString() === today);
          const waiting = todayTokens.filter(t => t.status === 'Pending');
          const inConsult = todayTokens.filter(t => t.status === 'In Progress');
          const completed = todayTokens.filter(t => t.status === 'Completed');
          const toBill = completed.filter(t => !t.is_billed);
          const todayRegistrations = patients.filter(p => new Date(p.created_at).toDateString() === today);
          const todayAppts = appointments.filter(a => new Date(a.appointment_date).toDateString() === today);
          const collectedToday = opBills
            .filter(b => new Date(b.bill_date).toDateString() === today)
            .reduce((s, b) => s + (b.total || 0), 0);

          const nameOf = (id: number) => patients.find(p => p.id === id)?.name || `Patient #${id}`;

          const tokenItem = (t: OPToken) => ({
            id: t.id,
            primary: `${nameOf(t.patient_id)}`,
            secondary: `Token #${t.token_number} · ${t.session}${t.doctor_name ? ` · ${t.doctor_name}` : ''}`,
            meta: `Fee ₹${(t.fee || 0).toFixed(0)}${t.is_billed ? ' · billed' : ''}`,
            badge: t.status,
            actions: [
              t.status === 'Pending'
                ? { label: 'Send to doctor', tone: 'primary' as const, onClick: () => handleUpdateTokenStatus(t.id, 'In Progress') }
                : null,
              t.status === 'In Progress'
                ? { label: 'Mark consulted', tone: 'primary' as const, onClick: () => handleUpdateTokenStatus(t.id, 'Completed') }
                : null,
              (t.status === 'Completed' && !t.is_billed)
                ? {
                    label: 'Raise bill', tone: 'primary' as const, onClick: () => {
                      const patient = patients.find(p => p.id === t.patient_id);
                      setOpBillForm({
                        ...opBillForm,
                        patient_id: String(t.patient_id),
                        token_id: String(t.id),
                        doctor_name: t.doctor_name || opBillForm.doctor_name,
                        consultation_fee: t.fee || opBillForm.consultation_fee || 0,
                      });
                      setBillingTab('op');
                      setActiveTab('billing');
                      showToast(patient ? `Billing ${patient.name}` : 'Opening billing');
                    },
                  }
                : null,
              { label: 'Record', onClick: () => openPatientDetail(t.patient_id) },
            ].filter(Boolean) as any,
          });

          return (
            <RoleFlow
              role="Front Desk"
              title="Front Desk — Full OPD Flow"
              subtitle="Register → token → queue → consultation → bill → payment, all from one screen."
              currentUser={currentUser.username}
              stats={[
                { label: 'Registered today', value: todayRegistrations.length, color: 'var(--accent-violet)', icon: <Users size={24} /> },
                { label: 'Tokens today', value: todayTokens.length, color: 'var(--accent-blue)', icon: <Clipboard size={24} /> },
                { label: 'Waiting now', value: waiting.length, color: 'var(--accent-amber)', icon: <Clock size={24} /> },
                { label: 'In consultation', value: inConsult.length, color: 'var(--accent-sky)', icon: <Activity size={24} /> },
                { label: 'Awaiting bill', value: toBill.length, color: 'var(--accent-rose)', icon: <Receipt size={24} /> },
                { label: 'Collected today', value: `₹${collectedToday.toFixed(0)}`, color: 'var(--accent-emerald)', icon: <DollarSign size={24} /> },
              ]}
              steps={[
                {
                  n: 1, title: 'Register patient', detail: 'New walk-in or follow-up; issues the patient ID.',
                  count: todayRegistrations.length, tone: 'done', action: 'Open registration',
                  onAction: () => setActiveTab('patients'),
                },
                {
                  n: 2, title: 'Issue OP token', detail: 'Morning/evening token with the consultation fee.',
                  count: todayTokens.length, tone: waiting.length ? 'active' : 'done', action: 'Token desk',
                  onAction: () => setActiveTab('op_token'),
                },
                {
                  n: 3, title: 'Manage the queue', detail: 'Call patients in and pass them to the doctor.',
                  count: waiting.length, tone: waiting.length ? 'active' : 'done', action: 'Live queue',
                  onAction: () => setActiveTab('live_queue'),
                },
                {
                  n: 4, title: 'Book appointment', detail: 'Schedule a future visit with a specific doctor.',
                  count: todayAppts.length, tone: 'done', action: 'Appointments',
                  onAction: () => setActiveTab('appointments'),
                },
                {
                  n: 5, title: 'Raise the bill', detail: 'Consultation, lab, pharmacy and other charges.',
                  count: toBill.length, tone: toBill.length ? 'active' : 'done', action: 'Billing module',
                  onAction: () => { setBillingTab('op'); setActiveTab('billing'); },
                },
                {
                  n: 6, title: 'Payment & invoice', detail: 'Cash / UPI / card, split payment and GST invoice.',
                  count: `₹${collectedToday.toFixed(0)}`, tone: 'done', action: 'Collect payment',
                  onAction: () => { setBillingTab('op'); setActiveTab('billing'); },
                },
              ]}
              lanes={[
                {
                  key: 'waiting', title: 'Waiting room', tone: '#f59e0b',
                  hint: 'Call the next patient, then send them through.',
                  emptyText: 'No one waiting',
                  items: waiting.map(tokenItem),
                },
                {
                  key: 'consult', title: 'In consultation', tone: '#0ea5e9',
                  hint: 'With the doctor now.',
                  emptyText: 'No active consultations',
                  items: inConsult.map(tokenItem),
                },
                {
                  key: 'bill', title: 'Ready to bill', tone: '#ef4444',
                  hint: 'Consultation finished — collect the charges.',
                  emptyText: 'Nothing to bill',
                  items: toBill.map(tokenItem),
                },
                {
                  key: 'appts', title: "Today's appointments", tone: '#10b981',
                  emptyText: 'No appointments today',
                  items: todayAppts.map(a => ({
                    id: a.id,
                    primary: nameOf(a.patient_id),
                    secondary: `${a.time_slot || '—'} · ${a.doctor_name || 'Any doctor'}`,
                    meta: a.reason || '',
                    badge: a.status,
                    actions: [
                      { label: 'Check in', tone: 'primary' as const, onClick: () => handleUpdateAppointmentStatus(a.id, 'Completed') },
                      { label: 'Record', onClick: () => openPatientDetail(a.patient_id) },
                    ],
                  })),
                },
              ]}
            >
              <div className="glass-card" style={{ marginTop: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginBottom: '12px', flexWrap: 'wrap' }}>
                  <h3 style={{ margin: 0 }}>Quick patient lookup</h3>
                  <input
                    type="text" className="search-bar" style={{ maxWidth: '340px' }}
                    placeholder="Name, phone, patient ID..."
                    value={frontDeskSearch}
                    onChange={e => setFrontDeskSearch(e.target.value)}
                  />
                </div>
                <div className="table-container">
                  <table>
                    <thead><tr><th>ID</th><th>Patient</th><th>Age / Gender</th><th>Phone</th><th>Actions</th></tr></thead>
                    <tbody>
                      {patients
                        .filter(p => {
                          const q = frontDeskSearch.trim().toLowerCase();
                          if (!q) return false;
                          return p.name.toLowerCase().includes(q) || String(p.id) === q || (p.phone || '').includes(q);
                        })
                        .slice(0, 8)
                        .map(p => (
                          <tr key={p.id}>
                            <td>#{p.id}</td>
                            <td><b>{p.name}</b></td>
                            <td>{p.age} / {p.gender}</td>
                            <td>{p.phone || '-'}</td>
                            <td>
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button className="btn btn-primary" style={{ padding: '4px 10px', fontSize: '12px' }} onClick={() => openPatientDetail(p.id)}>Open 360</button>
                                <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }} onClick={() => {
                                  setSelectedPatientId(p.id); setActiveTab('op_token');
                                }}>New token</button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      {frontDeskSearch.trim() && patients.filter(p => p.name.toLowerCase().includes(frontDeskSearch.toLowerCase()) || String(p.id).includes(frontDeskSearch) || (p.phone || '').includes(frontDeskSearch)).length === 0 && (
                        <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No matching patient. Register them from Appointments.</td></tr>
                      )}
                      {!frontDeskSearch.trim() && (
                        <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Type a name, phone number or patient ID to search.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </RoleFlow>
          );
        })()}

        {activeTab === 'doctor_workspace' && (() => {
          const today = new Date().toDateString();
          const todayTokens = tokens.filter(t => new Date(t.date).toDateString() === today);
          const waiting = todayTokens.filter(t => t.status === 'Pending');
          const withMe = todayTokens.filter(t => t.status === 'In Progress');
          const done = todayTokens.filter(t => t.status === 'Completed');
          const myPatients = new Set(todayTokens.map(t => t.patient_id));
          const readyResults = labOrders.filter(o => o.status === 'Verified' && myPatients.has(o.patient_id));
          const pendingLabs = labOrders.filter(o => !['Verified', 'Cancelled'].includes(o.status) && myPatients.has(o.patient_id));

          return (
            <RoleFlow
              role="Doctor"
              title="Doctor — Full Consultation Flow"
              subtitle="Call the patient in → examine → prescribe → order labs → review results → hand over to billing."
              currentUser={currentUser.username}
              headerActions={
                <button className="btn btn-secondary" onClick={() => { loadAllData(); loadLabStats(); }}><RefreshCw size={16} /> Refresh</button>
              }
              stats={[
                { label: 'Waiting', value: waiting.length, color: 'var(--accent-amber)', icon: <Clock size={24} /> },
                { label: 'With me now', value: withMe.length, color: 'var(--accent-sky)', icon: <Activity size={24} /> },
                { label: 'Seen today', value: done.length, color: 'var(--accent-emerald)', icon: <CheckCircle2 size={24} /> },
                { label: 'My labs pending', value: pendingLabs.length, color: 'var(--accent-violet)', icon: <FlaskConical size={24} /> },
                { label: 'Results ready', value: readyResults.length, color: 'var(--accent-emerald)', icon: <FileText size={24} /> },
              ]}
              steps={[
                {
                  n: 1, title: 'Pick the next patient', detail: 'Call from today’s queue.',
                  count: waiting.length, tone: waiting.length ? 'active' : 'done',
                  action: 'Today’s queue', onAction: () => setActiveTab('live_queue'),
                },
                {
                  n: 2, title: 'Open the case sheet', detail: 'Vitals, complaints, findings and diagnosis.',
                  count: withMe.length, tone: withMe.length ? 'active' : 'done',
                  action: 'Start consultation', onAction: () => setActiveTab('casesheet'),
                },
                {
                  n: 3, title: 'Prescribe', detail: 'Medicines with dose, duration and timing.',
                  tone: 'todo', action: 'Write prescription', onAction: () => setActiveTab('casesheet'),
                },
                {
                  n: 4, title: 'Order labs', detail: 'Tick tests in the case sheet; the lab is notified instantly.',
                  count: pendingLabs.length, tone: 'todo', action: 'Order tests', onAction: () => setActiveTab('casesheet'),
                },
                {
                  n: 5, title: 'Review results', detail: 'Read verified reports before they reach the patient.',
                  count: readyResults.length, tone: readyResults.length ? 'active' : 'done',
                  action: 'Lab reports', onAction: () => setActiveTab('lab_reports_new'),
                },
                {
                  n: 6, title: 'Send to billing', detail: 'Consultation fee and charges are raised at the desk.',
                  tone: 'todo', action: 'Billing', onAction: () => { setBillingTab('op'); setActiveTab('billing'); },
                },
              ]}
              lanes={[
                {
                  key: 'waiting', title: 'Waiting to be seen', tone: '#f59e0b', emptyText: 'Queue is clear',
                  items: waiting.map(t => ({
                    id: t.id,
                    primary: patients.find(p => p.id === t.patient_id)?.name || `Patient #${t.patient_id}`,
                    secondary: `Token #${t.token_number} · ${t.session}`,
                    meta: t.department || '',
                    badge: t.status,
                    actions: [
                      { label: 'Start consult', tone: 'primary' as const, onClick: () => { setSelectedOPToken(t); setActiveTab('casesheet'); } },
                      { label: '360', onClick: () => openPatientDetail(t.patient_id) },
                    ],
                  })),
                },
                {
                  key: 'mine', title: 'With me now', tone: '#0ea5e9', emptyText: 'No active consultation',
                  items: withMe.map(t => ({
                    id: t.id,
                    primary: patients.find(p => p.id === t.patient_id)?.name || `Patient #${t.patient_id}`,
                    secondary: `Token #${t.token_number} · ${t.session}`,
                    badge: t.status,
                    actions: [
                      { label: 'Resume', tone: 'primary' as const, onClick: () => { setSelectedOPToken(t); setActiveTab('casesheet'); } },
                      { label: 'Finish', onClick: () => handleUpdateTokenStatus(t.id, 'Completed') },
                      { label: '360', onClick: () => openPatientDetail(t.patient_id) },
                    ],
                  })),
                },
                {
                  key: 'results', title: 'Results to review', tone: '#10b981', emptyText: 'No new results',
                  items: readyResults.slice(0, 12).map(o => ({
                    id: o.id,
                    primary: o.test?.test_name || `Test #${o.test_id}`,
                    secondary: patients.find(p => p.id === o.patient_id)?.name || `Patient #${o.patient_id}`,
                    meta: o.verified_at ? `Verified ${new Date(o.verified_at).toLocaleString()}` : '',
                    badge: 'Verified',
                    actions: [
                      {
                        label: 'Print', tone: 'primary' as const, onClick: () => {
                          const r = labReports.find(x => x.order_id === o.id);
                          if (r) printLabReport(r); else showToast('Report still generating', 'error');
                        },
                      },
                      { label: '360', onClick: () => openPatientDetail(o.patient_id) },
                    ],
                  })),
                },
              ]}
            />
          );
        })()}

        {activeTab === 'pharmacy_workspace' && (() => {
          const lowStock = inventory.filter(i => i.category === 'Pharmacy' && i.quantity <= i.min_stock_level);
          const expiring = inventory
            .filter(i => i.expiry_date && new Date(i.expiry_date).getTime() < Date.now() + 90 * 86400000)
            .sort((a, b) => (a.expiry_date || '').localeCompare(b.expiry_date || ''));
          const today = new Date().toDateString();
          const todayBills = pharmacyBills.filter(b => new Date(b.bill_date).toDateString() === today);
          const todaySales = todayBills.reduce((s, b) => s + b.total, 0);

          return (
            <RoleFlow
              role="Pharmacy"
              title="Pharmacy — Full Dispensing Flow"
              subtitle="Check stock → dispense → bill → receive purchase → watch expiry."
              currentUser={currentUser.username}
              headerActions={
                <button className="btn btn-secondary" onClick={() => loadAllData()}><RefreshCw size={16} /> Refresh</button>
              }
              stats={[
                { label: 'Bills today', value: todayBills.length, color: 'var(--accent-blue)', icon: <Receipt size={24} /> },
                { label: 'Sales today', value: `₹${todaySales.toFixed(0)}`, color: 'var(--accent-emerald)', icon: <DollarSign size={24} /> },
                { label: 'Low stock items', value: lowStock.length, color: 'var(--accent-rose)', icon: <AlertTriangle size={24} /> },
                { label: 'Expiring in 90 days', value: expiring.length, color: 'var(--accent-amber)', icon: <Clock size={24} /> },
                { label: 'Medicines stocked', value: inventory.filter(i => i.category === 'Pharmacy').length, color: 'var(--accent-violet)', icon: <Database size={24} /> },
              ]}
              steps={[
                {
                  n: 1, title: 'Check availability', detail: 'Search stock by name, batch or barcode.',
                  count: inventory.filter(i => i.category === 'Pharmacy').length, tone: 'done',
                  action: 'Medicine search', onAction: () => setActiveTab('pharmacy_search'),
                },
                {
                  n: 2, title: 'Dispense & bill', detail: 'Cart, discount, GST and payment — stock is deducted automatically.',
                  count: todayBills.length, tone: 'active',
                  action: 'Open dispensary', onAction: () => setActiveTab('pharmacy'),
                },
                {
                  n: 3, title: 'Load a prescription', detail: 'Pull the doctor’s prescription straight into the cart.',
                  tone: 'todo', action: 'Dispensary', onAction: () => setActiveTab('pharmacy'),
                },
                {
                  n: 4, title: 'Purchase / GRN', detail: 'Receive new stock against a supplier invoice.',
                  tone: 'todo', action: 'Goods receipt', onAction: () => setActiveTab('pharmacy_purchase'),
                },
                {
                  n: 5, title: 'Reorder low stock', detail: 'Items at or below their minimum level.',
                  count: lowStock.length, tone: lowStock.length ? 'active' : 'done',
                  action: 'Low stock', onAction: () => setActiveTab('pharmacy_purchase'),
                },
                {
                  n: 6, title: 'Expiry control', detail: 'Pull short-dated batches before they are dispensed.',
                  count: expiring.length, tone: expiring.length ? 'active' : 'done',
                  action: 'Expiry list', onAction: () => setActiveTab('pharmacy_expiry'),
                },
              ]}
              lanes={[
                {
                  key: 'low', title: 'Reorder now', tone: '#ef4444', hint: 'At or below minimum stock.',
                  emptyText: 'Stock levels healthy',
                  items: lowStock.map(i => ({
                    id: i.id,
                    primary: i.name,
                    secondary: `${i.quantity} left · minimum ${i.min_stock_level}`,
                    meta: i.batch_no ? `Batch ${i.batch_no}` : '',
                    badge: 'Low', badgeTone: 'cancelled',
                    actions: [
                      {
                        label: 'Receive stock', tone: 'primary' as const, onClick: () => {
                          setGrnForm({ ...grnForm, medicine_id: String(i.id), type: 'Stock In' });
                          setActiveTab('pharmacy_purchase');
                        },
                      },
                    ],
                  })),
                },
                {
                  key: 'expiry', title: 'Expiring soon', tone: '#f59e0b', hint: 'Within 90 days.',
                  emptyText: 'No near-expiry stock',
                  items: expiring.slice(0, 12).map(i => {
                    const days = Math.ceil((new Date(i.expiry_date as string).getTime() - Date.now()) / 86400000);
                    return {
                      id: i.id,
                      primary: i.name,
                      secondary: `Expires ${new Date(i.expiry_date as string).toLocaleDateString()} · ${days} day(s)`,
                      meta: `${i.quantity} in stock`,
                      badge: days < 0 ? 'Expired' : 'Expiring',
                      badgeTone: days < 0 ? 'cancelled' : 'pending',
                    };
                  }),
                },
                {
                  key: 'recent', title: 'Recent dispensary bills', tone: '#10b981', emptyText: 'No bills yet',
                  items: pharmacyBills.slice(0, 12).map(b => ({
                    id: b.id,
                    primary: b.patient_name || patients.find(p => p.id === b.patient_id)?.name || 'Walk-in',
                    secondary: `Bill #${b.id} · ${b.items?.length || 0} item(s)`,
                    meta: new Date(b.bill_date).toLocaleString(),
                    badge: `₹${b.total.toFixed(0)}`,
                    actions: [{ label: 'View invoice', onClick: () => setViewInvoice(b) }],
                  })),
                },
              ]}
            />
          );
        })()}

        {activeTab === 'pharmacy_purchase' && (() => {
          const reorder = inventory.filter(i => i.quantity <= i.min_stock_level);
          const pharmacyItems = inventory.filter(i => i.category === 'Pharmacy');
          return (
            <div className="no-print">
              <div className="header">
                <div className="header-title">
                  <h1>Purchase &amp; Goods Receipt</h1>
                  <p>Receive supplier stock, and see what needs reordering.</p>
                </div>
                <button className="btn btn-secondary" onClick={() => setActiveTab('inventory')}><Database size={16} /> Full inventory</button>
              </div>

              <div className="grid-2">
                <div className="glass-card">
                  <h3>Receive stock (GRN)</h3>
                  <form onSubmit={handleSaveGRN}>
                    <div className="form-group">
                      <label>Medicine *</label>
                      <Select
                        styles={selectStyles}
                        options={inventory.map(i => ({ value: String(i.id), label: `${i.name} (in stock: ${i.quantity})` }))}
                        value={grnForm.medicine_id ? { value: grnForm.medicine_id, label: inventory.find(i => String(i.id) === grnForm.medicine_id)?.name || grnForm.medicine_id } : null}
                        onChange={(o: any) => setGrnForm({ ...grnForm, medicine_id: o?.value || '' })}
                        placeholder="Search medicine..."
                      />
                    </div>
                    <div className="form-grid" style={{ marginTop: '12px' }}>
                      <div className="form-group">
                        <label>Quantity received *</label>
                        <input type="number" min="1" required value={grnForm.quantity}
                          onChange={e => setGrnForm({ ...grnForm, quantity: Number(e.target.value) })} />
                      </div>
                      <div className="form-group">
                        <label>Movement type</label>
                        <select value={grnForm.type} onChange={e => setGrnForm({ ...grnForm, type: e.target.value })}>
                          <option>Stock In</option><option>Return</option><option>Stock Out</option><option>Adjustment</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Supplier</label>
                        <input type="text" value={grnForm.details.supplierName}
                          onChange={e => setGrnForm({ ...grnForm, details: { ...grnForm.details, supplierName: e.target.value } })} />
                      </div>
                      <div className="form-group">
                        <label>Invoice no.</label>
                        <input type="text" value={grnForm.details.invoiceNumber}
                          onChange={e => setGrnForm({ ...grnForm, details: { ...grnForm.details, invoiceNumber: e.target.value } })} />
                      </div>
                    </div>
                    <div className="form-group" style={{ marginTop: '12px' }}>
                      <label>Notes</label>
                      <input type="text" value={grnForm.notes} onChange={e => setGrnForm({ ...grnForm, notes: e.target.value })} />
                    </div>
                    <button type="submit" className="btn btn-primary" style={{ marginTop: '14px' }}>
                      <UploadCloud size={16} /> Post goods receipt
                    </button>
                  </form>
                </div>

                <div className="glass-card">
                  <h3>Reorder list ({reorder.length})</h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                    Items at or below their minimum level. Use <b>Receive</b> to post a GRN straight away.
                  </p>
                  <div className="table-container" style={{ maxHeight: '420px', overflowY: 'auto' }}>
                    <table>
                      <thead><tr><th>Item</th><th>Stock</th><th>Min</th><th></th></tr></thead>
                      <tbody>
                        {reorder.map(i => (
                          <tr key={i.id}>
                            <td>{i.name}<br /><small style={{ color: 'var(--text-muted)' }}>{i.category}{i.batch_no ? ` · ${i.batch_no}` : ''}</small></td>
                            <td style={{ color: 'var(--danger)', fontWeight: 700 }}>{i.quantity}</td>
                            <td>{i.min_stock_level}</td>
                            <td>
                              <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }}
                                onClick={() => setGrnForm({ ...grnForm, medicine_id: String(i.id), type: 'Stock In', quantity: Math.max(i.min_stock_level * 2 - i.quantity, 1) })}>
                                Receive
                              </button>
                            </td>
                          </tr>
                        ))}
                        {reorder.length === 0 && <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Everything is above its minimum level.</td></tr>}
                      </tbody>
                    </table>
                  </div>
                  <p style={{ marginTop: '12px', fontSize: '12px', color: 'var(--text-muted)' }}>
                    {pharmacyItems.length} pharmacy item(s) tracked.
                  </p>
                </div>
              </div>
            </div>
          );
        })()}

        {activeTab === 'pharmacy_expiry' && (() => {
          const withExpiry = inventory.filter(i => i.expiry_date);
          const expired = withExpiry.filter(i => new Date(i.expiry_date as string).getTime() < Date.now());
          const soon = withExpiry
            .filter(i => new Date(i.expiry_date as string).getTime() >= Date.now() && new Date(i.expiry_date as string).getTime() < Date.now() + 90 * 86400000)
            .sort((a, b) => (a.expiry_date || '').localeCompare(b.expiry_date || ''));
          const valueAtRisk = [...expired, ...soon].reduce((s, i) => s + i.quantity * i.unit_price, 0);
          return (
            <div className="no-print">
              <div className="header">
                <div className="header-title">
                  <h1>Expiry Management</h1>
                  <p>Pull short-dated batches before they reach a patient.</p>
                </div>
                <button className="btn btn-secondary" onClick={() => exportToCSV([...expired, ...soon], 'Expiring_Stock.csv')}><Download size={16} /> Export CSV</button>
              </div>

              <div className="dashboard-grid">
                <div className="stat-card">
                  <div className="stat-icon" style={{ background: 'rgba(239,68,68,0.1)', color: 'var(--accent-rose)' }}><AlertTriangle size={24} /></div>
                  <div><h3 style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>Already expired</h3><h2 style={{ margin: 0 }}>{expired.length}</h2></div>
                </div>
                <div className="stat-card">
                  <div className="stat-icon" style={{ background: 'rgba(245,158,11,0.1)', color: 'var(--accent-amber)' }}><Clock size={24} /></div>
                  <div><h3 style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>Expiring in 90 days</h3><h2 style={{ margin: 0 }}>{soon.length}</h2></div>
                </div>
                <div className="stat-card">
                  <div className="stat-icon" style={{ background: 'rgba(16,185,129,0.1)', color: 'var(--accent-emerald)' }}><DollarSign size={24} /></div>
                  <div><h3 style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>Stock value at risk</h3><h2 style={{ margin: 0 }}>₹{valueAtRisk.toFixed(0)}</h2></div>
                </div>
              </div>

              <div className="glass-card">
                <h3>Expired ({expired.length})</h3>
                <div className="table-container">
                  <table>
                    <thead><tr><th>Item</th><th>Batch</th><th>Expired</th><th>Qty</th><th>Value</th><th></th></tr></thead>
                    <tbody>
                      {expired.map(i => (
                        <tr key={i.id} style={{ background: 'rgba(239,68,68,0.06)' }}>
                          <td>{i.name}</td><td>{i.batch_no || '-'}</td>
                          <td>{new Date(i.expiry_date as string).toLocaleDateString()}</td>
                          <td>{i.quantity}</td>
                          <td>₹{(i.quantity * i.unit_price).toFixed(2)}</td>
                          <td>
                            <button className="btn btn-danger" style={{ padding: '4px 8px', fontSize: '12px' }}
                              onClick={async () => {
                                if (!window.confirm(`Write off ${i.quantity} x ${i.name}?`)) return;
                                try {
                                  await axios.post(`${API_BASE}/inventory/adjust/`, {
                                    medicine_id: i.id, type: 'Stock Out', quantity: i.quantity,
                                    notes: 'Expired stock written off',
                                  });
                                  showToast('Stock written off');
                                  loadAllData();
                                } catch (err: any) { alert(err.response?.data?.detail || 'Failed to write off.'); }
                              }}>Write off</button>
                          </td>
                        </tr>
                      ))}
                      {expired.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No expired stock.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="glass-card" style={{ marginTop: '16px' }}>
                <h3>Expiring within 90 days ({soon.length})</h3>
                <div className="table-container">
                  <table>
                    <thead><tr><th>Item</th><th>Batch</th><th>Expires</th><th>Days left</th><th>Qty</th><th>Value</th></tr></thead>
                    <tbody>
                      {soon.map(i => {
                        const days = Math.ceil((new Date(i.expiry_date as string).getTime() - Date.now()) / 86400000);
                        return (
                          <tr key={i.id}>
                            <td>{i.name}</td><td>{i.batch_no || '-'}</td>
                            <td>{new Date(i.expiry_date as string).toLocaleDateString()}</td>
                            <td style={{ color: days < 30 ? 'var(--danger)' : 'inherit', fontWeight: days < 30 ? 700 : 400 }}>{days}</td>
                            <td>{i.quantity}</td>
                            <td>₹{(i.quantity * i.unit_price).toFixed(2)}</td>
                          </tr>
                        );
                      })}
                      {soon.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Nothing expiring in the next 90 days.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          );
        })()}

        {activeTab === 'pharmacy_search' && (() => {
          const q = pharmacySearch.trim().toLowerCase();
          const results = inventory.filter(i => {
            if (!q) return true;
            return i.name.toLowerCase().includes(q)
              || (i.batch_no || '').toLowerCase().includes(q)
              || i.category.toLowerCase().includes(q)
              || String((i.details as any)?.barcode || '').toLowerCase().includes(q);
          });
          return (
            <div className="no-print">
              <div className="header">
                <div className="header-title"><h1>Medicine Search</h1><p>Find any item by name, batch, category or barcode.</p></div>
                <button className="btn btn-secondary" onClick={() => setActiveTab('pharmacy')}><ShoppingBag size={16} /> Go to dispensary</button>
              </div>
              <div className="glass-card">
                <input
                  type="text" className="search-bar" style={{ width: '100%', marginBottom: '14px' }}
                  placeholder="Type a medicine name, batch number, category or barcode..."
                  value={pharmacySearch} onChange={e => setPharmacySearch(e.target.value)}
                  autoFocus
                />
                <div className="table-container">
                  <table>
                    <thead><tr><th>Item</th><th>Category</th><th>Batch</th><th>Expiry</th><th>Stock</th><th>Unit price</th><th></th></tr></thead>
                    <tbody>
                      {results.map(i => (
                        <tr key={i.id}>
                          <td><b>{i.name}</b><br /><small style={{ color: 'var(--text-muted)' }}>{(i.details as any)?.genericName || ''}</small></td>
                          <td>{i.category}</td>
                          <td>{i.batch_no || '-'}</td>
                          <td>{i.expiry_date ? new Date(i.expiry_date).toLocaleDateString() : '-'}</td>
                          <td style={{ fontWeight: 700, color: i.quantity <= i.min_stock_level ? 'var(--danger)' : 'inherit' }}>{i.quantity}</td>
                          <td>₹{i.unit_price.toFixed(2)}</td>
                          <td>
                            <button className="btn btn-primary" style={{ padding: '4px 10px', fontSize: '12px' }}
                              disabled={i.quantity <= 0}
                              onClick={() => {
                                setBillingCart(prev => {
                                  const existing = prev.find(c => c.medicine_id === i.id);
                                  if (existing) return prev.map(c => c.medicine_id === i.id ? { ...c, quantity: c.quantity + 1 } : c);
                                  return [...prev, { medicine_id: i.id, name: i.name, quantity: 1, unit_price: i.unit_price }];
                                });
                                setActiveTab('pharmacy');
                                showToast(`${i.name} added to cart`);
                              }}>Add to cart</button>
                          </td>
                        </tr>
                      ))}
                      {results.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No medicine matches “{pharmacySearch}”.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          );
        })()}

        {activeTab === 'reception_dashboard' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Reception Dashboard</h1>
                <p>Overview of today's activities</p>
              </div>
            </div>
            <div className="form-grid" style={{ marginBottom: '24px' }}>
              <div className="glass-card" style={{ textAlign: 'center' }}>
                <Users size={32} color="#8b5cf6" style={{ marginBottom: '8px' }} />
                <h3>{patients.filter(p => new Date(p.created_at).toDateString() === new Date().toDateString()).length}</h3>
                <p style={{ color: 'var(--text-muted)' }}>New Registrations Today</p>
              </div>
              <div className="glass-card" style={{ textAlign: 'center' }}>
                <Clipboard size={32} color="#3b82f6" style={{ marginBottom: '8px' }} />
                <h3>{tokens.filter(t => new Date(t.date).toDateString() === new Date().toDateString()).length}</h3>
                <p style={{ color: 'var(--text-muted)' }}>Tokens Today</p>
              </div>
              <div className="glass-card" style={{ textAlign: 'center' }}>
                <Calendar size={32} color="#10b981" style={{ marginBottom: '8px' }} />
                <h3>{appointments.filter(a => new Date(a.appointment_date).toDateString() === new Date().toDateString()).length}</h3>
                <p style={{ color: 'var(--text-muted)' }}>Appointments Today</p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'patients' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Patient Registration</h1>
                <p>Register new outpatients and issue UHID</p>
              </div>
              <button className="btn btn-secondary" style={{display:'flex', alignItems:'center', gap:'8px'}} onClick={() => exportToCSV(patients, 'Patients_List.csv')}><Download size={16}/> Export CSV</button>
            </div>
            <div className="glass-card">
              <form onSubmit={handleRegisterPatient}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
                  <div className="form-group">
                    <label>Patient Full Name *</label>
                    <input type="text" value={patientForm.name} onChange={e => setPatientForm({ ...patientForm, name: e.target.value })} required />
                  </div>
                  <div className="form-group">
                    <label>Age *</label>
                    <input type="number" value={patientForm.age || ''} onChange={e => setPatientForm({ ...patientForm, age: Number(e.target.value) })} required />
                  </div>
                  <div className="form-group">
                    <label>Gender *</label>
                    <select value={patientForm.gender} onChange={e => setPatientForm({ ...patientForm, gender: e.target.value })}>
                      <option>Male</option>
                      <option>Female</option>
                      <option>Other</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Phone Number *</label>
                    <input type="text" value={patientForm.phone} onChange={e => setPatientForm({ ...patientForm, phone: e.target.value })} required />
                  </div>
                  <div className="form-group">
                    <label>Aadhaar Number</label>
                    <input type="text" value={patientForm.aadhaar} onChange={e => setPatientForm({ ...patientForm, aadhaar: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label>Blood Group</label>
                    <select value={patientForm.blood_group} onChange={e => setPatientForm({ ...patientForm, blood_group: e.target.value })}>
                      <option value="">-- Select --</option>
                      <option>A+</option><option>A-</option><option>B+</option><option>B-</option>
                      <option>AB+</option><option>AB-</option><option>O+</option><option>O-</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Guardian Name</label>
                    <input type="text" value={patientForm.guardian_name} onChange={e => setPatientForm({ ...patientForm, guardian_name: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label>Emergency Contact</label>
                    <input type="text" value={patientForm.emergency_contact} onChange={e => setPatientForm({ ...patientForm, emergency_contact: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label>Marital Status</label>
                    <select value={patientForm.marital_status} onChange={e => setPatientForm({ ...patientForm, marital_status: e.target.value })}>
                      <option>Single</option>
                      <option>Married</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Patient Category</label>
                    <select value={patientForm.patient_category} onChange={e => setPatientForm({ ...patientForm, patient_category: e.target.value })}>
                      <option>General</option>
                      <option>Corporate</option>
                      <option>Insurance</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Insurance Details</label>
                    <input type="text" value={patientForm.insurance_details} onChange={e => setPatientForm({ ...patientForm, insurance_details: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label>Registration Type</label>
                    <select value={patientForm.registration_type} onChange={e => setPatientForm({ ...patientForm, registration_type: e.target.value })}>
                      <option>Walk-in</option>
                      <option>Appointment</option>
                    </select>
                  </div>
                  <div className="form-group" style={{ gridColumn: 'span 3' }}>
                    <label>Address</label>
                    <textarea rows={2} value={patientForm.address} onChange={e => setPatientForm({ ...patientForm, address: e.target.value })} />
                  </div>
                </div>
                <div style={{ marginTop: '24px', display: 'flex', gap: '16px' }}>
                  <button type="submit" className="btn btn-primary"><Plus size={18} /> Register Patient</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {activeTab === 'op_token' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Book OP Session Token & Check-in</h1>
                <p>Generate consultation tokens and manage check-ins</p>
              </div>
            </div>
            <div className="form-grid">
              <div className="glass-card">
                <h3 style={{ marginBottom: '16px' }}>Book Token</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div className="form-group">
                    <label>Select Registered Patient</label>
                    <Select
                      options={patients.map(p => ({ value: p.id, label: `${p.name} (Age: ${p.age}, ${p.phone || 'No Phone'})` }))}
                      onChange={(opt: any) => setSelectedPatientId(opt ? opt.value : '')}
                      styles={selectStyles}
                      isClearable
                      placeholder="Search patient..."
                    />
                  </div>
                  <div className="form-grid">
                    <div className="form-group">
                      <label>Department</label>
                      <select value={tokenForm.department} onChange={e => setTokenForm({ ...tokenForm, department: e.target.value })}>
                        <option>General Medicine</option>
                        <option>Cardiology</option>
                        <option>Orthopedics</option>
                        <option>Pediatrics</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Consultation Type</label>
                      <select value={tokenForm.consultation_type} onChange={e => setTokenForm({ ...tokenForm, consultation_type: e.target.value })}>
                        <option>Routine</option>
                        <option>Follow-up</option>
                        <option>Emergency</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>OP Session</label>
                      <select value={opSession} onChange={e => setOpSession(e.target.value as any)}>
                        <option value="Morning">Morning OP Session</option>
                        <option value="Evening">Evening OP Session</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Consultation Fee (₹)</label>
                      <input type="number" value={opFee} onChange={e => setOpFee(Number(e.target.value))} />
                    </div>
                  </div>
                  <div className="form-group">
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <input type="checkbox" checked={tokenForm.is_emergency} onChange={e => setTokenForm({ ...tokenForm, is_emergency: e.target.checked })} />
                      Emergency Priority
                    </label>
                  </div>
                  <button type="button" className="btn btn-primary" onClick={handleGenerateToken} style={{ marginTop: '8px' }}>
                    <Clipboard size={18} /> Generate Token
                  </button>
                </div>
              </div>
              <div className="glass-card">
                <h3 style={{ marginBottom: '16px' }}>Today's Tokens</h3>
                <div className="table-container" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Token #</th>
                        <th>Patient Name</th>
                        <th>Session</th>
                        <th>Status</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tokens.filter(t => new Date(t.date).toDateString() === new Date().toDateString()).map(token => (
                        <tr key={token.id}>
                          <td><strong>{token.token_number}</strong></td>
                          <td>{token.patient?.name || 'Unknown'}</td>
                          <td>{token.session}</td>
                          <td>
                            <span className={`badge ${(token.status || '').toLowerCase()}`}>{token.status}</span>
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                              {token.status === 'Pending' && (
                                <button className="btn btn-primary" style={{ padding: '4px 8px', fontSize: '12px' }}
                                  onClick={() => handleUpdateTokenStatus(token.id, 'In Progress')}>Call in</button>
                              )}
                              {token.status === 'In Progress' && (
                                <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }}
                                  onClick={() => handleUpdateTokenStatus(token.id, 'Completed')}>Consulted</button>
                              )}
                              {token.status === 'Completed' && !token.is_billed && (
                                <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }}
                                  onClick={() => {
                                    setOpBillForm({ ...opBillForm, patient_id: String(token.patient_id), token_id: String(token.id), consultation_fee: token.fee || 0 });
                                    setBillingTab('op');
                                    setActiveTab('billing');
                                  }}>Bill</button>
                              )}
                              <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }}
                                onClick={() => openPatientDetail(token.patient_id)}>360</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'appointments' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Appointments</h1>
                <p>Book and manage future appointments</p>
              </div>
            </div>
            <div className="form-grid">
              <div className="glass-card">
                <h3 style={{ marginBottom: '16px' }}>Book Appointment</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div className="form-group">
                    <label>Select Registered Patient</label>
                    <Select
                      options={patients.map(p => ({ value: p.id, label: `${p.name} (Age: ${p.age}, ${p.phone || 'No Phone'})` }))}
                      onChange={(opt: any) => setAppointmentForm({ ...appointmentForm, patient_id: opt ? opt.value : '' })}
                      styles={selectStyles}
                      isClearable
                    />
                  </div>
                  <div className="form-grid">
                    <div className="form-group">
                      <label>Appointment Date</label>
                      <input type="date" value={appointmentForm.appointment_date} onChange={e => setAppointmentForm({ ...appointmentForm, appointment_date: e.target.value })} />
                    </div>
                    <div className="form-group">
                      <label>Time Slot</label>
                      <select value={appointmentForm.time_slot} onChange={e => setAppointmentForm({ ...appointmentForm, time_slot: e.target.value })}>
                        <option>09:00 AM - 10:00 AM</option>
                        <option>10:00 AM - 11:00 AM</option>
                        <option>11:00 AM - 12:00 PM</option>
                        <option>04:00 PM - 05:00 PM</option>
                        <option>05:00 PM - 06:00 PM</option>
                      </select>
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Reason for Visit</label>
                    <input type="text" value={appointmentForm.reason} onChange={e => setAppointmentForm({ ...appointmentForm, reason: e.target.value })} />
                  </div>
                  <button type="button" className="btn btn-primary" onClick={async () => {
                    if(!appointmentForm.patient_id) return alert("Select patient");
                    try {
                      await axios.post(`${API_BASE}/appointments/`, {
                        ...appointmentForm,
                        patient_id: Number(appointmentForm.patient_id),
                        doctor_id: appointmentForm.doctor_id ? Number(appointmentForm.doctor_id) : null
                      });
                      alert("Appointment booked!");
                      loadAllData();
                    } catch(e) { console.error(e); }
                  }}>
                    <Calendar size={18} /> Book Appointment
                  </button>
                </div>
              </div>
              <div className="glass-card">
                <h3 style={{ marginBottom: '16px' }}>Upcoming Appointments</h3>
                <div className="table-container" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Date & Time</th>
                        <th>Patient</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {appointments.map(a => (
                        <tr key={a.id}>
                          <td>{a.appointment_date} <br/><small>{a.time_slot}</small></td>
                          <td>{a.patient?.name}</td>
                          <td>{a.status}</td>
                          <td>
                            <button className="btn btn-danger" style={{ padding: '4px 8px' }} onClick={() => handleDeleteAppointment(a.id)}><Trash2 size={12}/> Delete</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'live_queue' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Live Queue</h1>
                <p>Monitor patient waiting list</p>
              </div>
            </div>
            <div className="glass-card">
              <h3 style={{ marginBottom: '16px' }}>Waiting Patients</h3>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Token #</th>
                      <th>Patient Name</th>
                      <th>Department</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tokens.filter(t => new Date(t.date).toDateString() === new Date().toDateString() && t.status !== 'Completed').map(token => (
                      <tr key={token.id}>
                        <td style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{token.token_number}</td>
                        <td>{token.patient?.name}</td>
                        <td>{token.details?.department || 'General'}</td>
                        <td>
                          <span className={`badge ${(token.status || '').toLowerCase()}`}>{token.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'casesheet' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Doctor Consultation & Patient Management</h1>
                <p>Manage patients, view history, write prescriptions and order labs.</p>
              </div>
            </div>

            {/* If NO patient is selected globally in the Doctor tab */}
            {!selectedDoctorPatientId && (
              <div className="form-grid">
                <div className="glass-card" style={{ gridColumn: 'span 2' }}>
                  <h3 style={{ marginBottom: '16px' }}>Search & Select Patient</h3>
                  <SearchableDropdown 
                    options={patients.map((p: any) => ({
                      label: `${p.id} - ${p.name} - ${p.phone}`,
                      value: p.id,
                      id: p.id,
                      name: p.name,
                      phone: p.phone,
                      uhid: p.aadhaar || '',
                    }))}
                    value={selectedDoctorPatientId}
                    onChange={(val: any) => setSelectedDoctorPatientId(val)}
                    placeholder="Search Patient ID, Name, Mobile, UHID..."
                    searchKeys={['id', 'name', 'phone', 'uhid']}
                  />
                </div>

                <div className="glass-card" style={{ gridColumn: 'span 2' }}>
                  <h3 style={{ marginBottom: '16px' }}>Today's Active Queue</h3>
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>Token</th>
                          <th>Session</th>
                          <th>Patient</th>
                          <th>Age/Gender</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tokens.filter(t => t.status === 'Pending').map(token => (
                          <tr key={token.id}>
                            <td><div className="token-circle">{token.token_number}</div></td>
                            <td>{token.session}</td>
                            <td><strong>{token.patient?.name}</strong></td>
                            <td>{token.patient?.age} / {token.patient?.gender}</td>
                            <td>
                              <button className="btn btn-primary" onClick={() => {
                                setSelectedDoctorPatientId(token.patient_id);
                                setSelectedOPToken(token);
                              }}>
                                Open Record
                              </button>
                            </td>
                          </tr>
                        ))}
                        {tokens.filter(t => t.status === 'Pending').length === 0 && (
                          <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No patients in queue</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* If a patient IS selected */}
            {selectedDoctorPatientId && (() => {
              const patient = patients.find(p => p.id === selectedDoctorPatientId);
              const activeToken = tokens.find(t => t.patient_id === selectedDoctorPatientId && t.status === 'Pending');
              const previousVisits = tokens.filter(t => t.patient_id === selectedDoctorPatientId && t.status !== 'Pending');
              const patientLabOrders = labOrders.filter(o => o.patient_id === selectedDoctorPatientId);

              if (!patient) return <div>Patient not found.</div>;

              return (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                    <button className="btn btn-secondary" onClick={() => { setSelectedDoctorPatientId(null); setSelectedOPToken(null); }}><ChevronDown size={18} style={{transform: 'rotate(90deg)'}}/> Back to Dashboard</button>
                    {!selectedOPToken && (
                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button className="btn btn-primary" onClick={() => handleCreateDirectConsultation("New Visit")} >+ New Consultation</button>
                        <button className="btn btn-secondary" onClick={() => handleCreateDirectConsultation("Follow-up")} >Follow-up</button>
                        <button className="btn btn-danger" onClick={() => handleCreateDirectConsultation("Emergency")} >Emergency</button>
                      </div>
                    )}
                  </div>

                  {/* Comprehensive Patient Context View */}
                  <div className="glass-card" style={{ marginBottom: '24px', background: 'rgba(59, 130, 246, 0.05)', border: '1px solid rgba(59, 130, 246, 0.2)' }}>
                    <h3 style={{ marginBottom: '16px', color: 'var(--accent-blue)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <UserRound size={20}/> {patient.name} 
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '15px' }}>
                      <div><small style={{color:'var(--text-muted)'}}>Patient ID</small><br/><strong>{patient.id}</strong></div>
                      <div><small style={{color:'var(--text-muted)'}}>Age / Gender</small><br/><strong>{patient.age} / {patient.gender}</strong></div>
                      <div><small style={{color:'var(--text-muted)'}}>Blood Group</small><br/><strong>{patient.blood_group || 'N/A'}</strong></div>
                      <div><small style={{color:'var(--text-muted)'}}>Mobile</small><br/><strong>{patient.phone || 'N/A'}</strong></div>
                      <div><small style={{color:'var(--text-muted)'}}>UHID / Aadhaar</small><br/><strong>{patient.aadhaar || 'N/A'}</strong></div>
                      <div><small style={{color:'var(--text-muted)'}}>Previous Visits</small><br/><strong>{previousVisits.length}</strong></div>
                    </div>
                  </div>

                  {/* Main Interaction Area: split into History and Active Consultation */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
                    
                    {/* LEFT COLUMN: History */}
                    <div>
                      <div className="glass-card" style={{ marginBottom: '20px' }}>
                        <h4 style={{marginBottom:'15px', display:'flex', alignItems:'center', gap:'8px'}}><Clock size={18}/> Patient History</h4>
                        <div style={{maxHeight: '300px', overflowY: 'auto'}}>
                          {previousVisits.map((v, i) => (
                            <div key={i} style={{padding: '10px', borderBottom: '1px solid var(--border)'}}>
                              <small>{new Date(v.created_at || Date.now()).toLocaleDateString()}</small><br/>
                              <strong>Dr. {v.doctor_name || 'N/A'}</strong> - {v.session}
                            </div>
                          ))}
                          {previousVisits.length === 0 && <span style={{color:'var(--text-muted)', fontSize:'12px'}}>No previous visits found.</span>}
                        </div>
                      </div>

                      <div className="glass-card">
                        <h4 style={{marginBottom:'15px', display:'flex', alignItems:'center', gap:'8px'}}><FlaskConical size={18}/> Previous Labs</h4>
                        <div style={{maxHeight: '300px', overflowY: 'auto'}}>
                          {patientLabOrders.map((o, i) => {
                            const test = labTestMasters.find(t => t.id === o.test_id);
                            return (
                              <div key={i} style={{padding: '10px', borderBottom: '1px solid var(--border)', display:'flex', justifyContent:'space-between'}}>
                                <div>
                                  <strong>{test?.test_name || 'Test'}</strong><br/>
                                  <small>{new Date(o.order_date || Date.now()).toLocaleDateString()}</small>
                                </div>
                                <div>
                                  <span className={`status-badge ${(o.status||'').replace(' ','-').toLowerCase()}`}>{o.status}</span>
                                </div>
                              </div>
                            );
                          })}
                          {patientLabOrders.length === 0 && <span style={{color:'var(--text-muted)', fontSize:'12px'}}>No lab orders found.</span>}
                        </div>
                      </div>
                    </div>

                    {/* RIGHT COLUMN: Active Consultation */}
                    <div className="glass-card">
                      {!selectedOPToken ? (
                        <div style={{textAlign: 'center', padding: '50px 20px'}}>
                          <Activity size={48} color="var(--text-muted)" style={{marginBottom:'16px'}}/>
                          <h3>No Active Consultation</h3>
                          <p style={{color:'var(--text-muted)', marginTop:'8px'}}>Select a patient from today's queue or click 'New Consultation' to start.</p>
                          {activeToken && (
                            <button className="btn btn-primary" style={{marginTop:'20px'}} onClick={() => setSelectedOPToken(activeToken)}>
                              Resume Active Consultation (Token #{activeToken.token_number})
                            </button>
                          )}
                        </div>
                      ) : (
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '16px', marginBottom: '24px' }}>
                            <h3 style={{ color: 'var(--accent-amber)' }}>Active Consultation</h3>
                            <div>
                              <span style={{marginRight: '15px'}}><strong>Token:</strong> {selectedOPToken.token_number}</span>
                              <span><strong>Session:</strong> {selectedOPToken.session}</span>
                            </div>
                          </div>

                          <div className="form-grid">
                            <div className="form-group"><label>Vitals - BP</label><input type="text" placeholder="120/80" value={casesheetForm.vitalsBp} onChange={e => setCasesheetForm({ ...casesheetForm, vitalsBp: e.target.value })} /></div>
                            <div className="form-group"><label>Vitals - Pulse</label><input type="text" placeholder="72" value={casesheetForm.vitalsPulse} onChange={e => setCasesheetForm({ ...casesheetForm, vitalsPulse: e.target.value })} /></div>
                            <div className="form-group"><label>Vitals - Temp (°F)</label><input type="text" placeholder="98.6" value={casesheetForm.vitalsTemp} onChange={e => setCasesheetForm({ ...casesheetForm, vitalsTemp: e.target.value })} /></div>
                          </div>

                          <h4 style={{ marginTop: '24px', marginBottom: '16px', color: 'var(--accent-blue)' }}>Clinical Details</h4>
                          <div className="form-grid">
                            <div className="form-group"><label>Chief Complaint</label><textarea rows={2} value={casesheetForm.chiefComplaint} onChange={e => setCasesheetForm({ ...casesheetForm, chiefComplaint: e.target.value })} /></div>
                            <div className="form-group"><label>Clinical Findings</label><textarea rows={2} value={casesheetForm.clinicalFindings} onChange={e => setCasesheetForm({ ...casesheetForm, clinicalFindings: e.target.value })} /></div>
                            <div className="form-group"><label>Diagnosis</label><textarea rows={2} value={casesheetForm.diagnosis} onChange={e => setCasesheetForm({ ...casesheetForm, diagnosis: e.target.value })} /></div>
                            <div className="form-group"><label>Treatment Plan</label><textarea rows={2} value={casesheetForm.treatmentPlan} onChange={e => setCasesheetForm({ ...casesheetForm, treatmentPlan: e.target.value })} /></div>
                          </div>

                          {/* Direct Lab Orders */}
                          <div style={{ background: 'rgba(0,0,0,0.1)', padding: '16px', borderRadius: '8px', marginTop: '24px' }}>
                            <h4 style={{ marginBottom: '16px', color: 'var(--accent-emerald)', display:'flex', alignItems:'center', gap:'8px' }}>
                              <TestTube size={18}/> Order Laboratory Tests
                            </h4>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px' }}>
                              {labTestMasters.filter(t => t.is_active).map(test => (
                                <label key={test.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', background:'var(--surface)', padding:'8px', borderRadius:'4px' }}>
                                  <input type="checkbox" checked={casesheetLabs.includes(test.test_name)} onChange={() => toggleLab(test.test_name)} />
                                  <span>{test.is_panel ? '🧩 ' : ''}{test.test_name}</span>
                                </label>
                              ))}
                              {labTestMasters.length === 0 && <span style={{ color: 'var(--text-muted)' }}>No tests configured.</span>}
                            </div>
                            <button
                              type="button"
                              className="btn btn-primary"
                              style={{ marginTop: '14px' }}
                              onClick={handleOrderDoctorLabs}
                            >
                              <TestTube size={16}/> Order selected tests ({casesheetLabs.length})
                            </button>
                          </div>

                          {/* Prescription */}
                          <div style={{ borderTop: '1px solid var(--border)', paddingTop: '24px', marginTop: '24px' }}>
                            <h4 style={{ marginBottom: '16px', color: 'var(--accent-violet)', display:'flex', alignItems:'center', gap:'8px' }}>
                              <Pill size={18}/> Prescribe Medicines
                            </h4>
                            <div className="form-grid" style={{ alignItems: 'flex-end', background: 'var(--surface)', padding: '16px', borderRadius: '8px', border:'1px solid var(--border)' }}>
                              <div className="form-group" style={{ gridColumn: 'span 2' }}>
                                <label>Select Medicine</label>
                                <Select 
                                  styles={selectStyles}
                                  options={inventory.filter(i => i.category === 'Pharmacy').map(item => ({ value: item.id, label: `${item.name} (Stock: ${item.quantity})` }))}
                                  value={newMed.medicine_id ? { value: newMed.medicine_id, label: inventory.find(i=>i.id === newMed.medicine_id)?.name || '' } : null}
                                  onChange={(opt: any) => setNewMed({ ...newMed, medicine_id: opt ? opt.value : 0 })}
                                  placeholder="-- Select Medicine --"
                                />
                              </div>
                              
                              <div className="form-group" style={{ gridColumn: 'span 2', display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
                                <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                  <span style={{fontSize:'12px', color:'var(--text-muted)'}}>Morning</span>
                                  <input type="checkbox" checked={newMed.timing_morning} onChange={e => setNewMed({...newMed, timing_morning: e.target.checked})} style={{width:'20px', height:'20px'}} />
                                </label>
                                <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                  <span style={{fontSize:'12px', color:'var(--text-muted)'}}>Afternoon</span>
                                  <input type="checkbox" checked={newMed.timing_afternoon} onChange={e => setNewMed({...newMed, timing_afternoon: e.target.checked})} style={{width:'20px', height:'20px'}} />
                                </label>
                                <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                  <span style={{fontSize:'12px', color:'var(--text-muted)'}}>Night</span>
                                  <input type="checkbox" checked={newMed.timing_night} onChange={e => setNewMed({...newMed, timing_night: e.target.checked})} style={{width:'20px', height:'20px'}} />
                                </label>
                              </div>

                              <div className="form-group">
                                <label>Relation</label>
                                <select value={newMed.timing_relation} onChange={e => setNewMed({...newMed, timing_relation: e.target.value})}>
                                  <option>After Food</option>
                                  <option>Before Food</option>
                                  <option>With Food</option>
                                </select>
                              </div>

                              <div className="form-group">
                                <label>Days</label>
                                <input type="number" min={1} value={newMed.duration} onChange={e => setNewMed({ ...newMed, duration: e.target.value })} />
                              </div>

                              <div className="form-group" style={{ gridColumn: 'span 2' }}>
                                <label>Instructions</label>
                                <input type="text" value={newMed.instructions} onChange={e => setNewMed({ ...newMed, instructions: e.target.value })} />
                              </div>

                              <button className="btn btn-secondary" onClick={addMedicineToPrescription} style={{ height: '42px', gridColumn: 'span 2' }}>
                                <Plus size={18} /> Add
                              </button>
                            </div>

                            {casesheetMeds.length > 0 && (
                              <div className="table-container" style={{ marginTop: '16px' }}>
                                <table>
                                  <thead>
                                    <tr>
                                      <th>Medicine</th>
                                      <th>Timing</th>
                                      <th>Relation</th>
                                      <th>Days</th>
                                      <th>Action</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {casesheetMeds.map((med, idx) => (
                                      <tr key={idx}>
                                        <td><strong>{med.name}</strong></td>
                                        <td>{med.timing_morning ? '1' : '0'}-{med.timing_afternoon ? '1' : '0'}-{med.timing_night ? '1' : '0'}</td>
                                        <td>{med.timing_relation}</td>
                                        <td>{med.duration}</td>
                                        <td><button className="btn btn-danger" style={{ padding: '4px' }} onClick={() => removeMedicineFromPrescription(idx)}><Trash2 size={14} /></button></td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>

                          <div className="no-print" style={{ marginTop: '32px', display: 'flex', gap: '16px' }}>
                            <button className="btn btn-secondary" onClick={() => handleSaveCasesheet(false)}>Save Draft</button>
                            <button className="btn btn-primary" onClick={() => handleSaveCasesheet(true)}>Finalize Consultation</button>
                            <button className="btn btn-secondary" onClick={() => window.print()}><Printer size={18} /> Print Rx</button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>
        )}
        {activeTab === 'pharmacy' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Pharmacy Billing Engine</h1>
                <p>Create invoice. Automatically decreases remaining stock count.</p>
              </div>
            </div>

            <div className="form-grid">
              
              {/* Checkout details & Patient Selection */}
              <div className="glass-card" style={{ gridColumn: 'span 2' }}>
                <h3 style={{ marginBottom: '16px' }}>1. Patient & Prescription Details</h3>
                <div className="form-grid" style={{ alignItems: 'flex-end' }}>
                  <div className="form-group">
                    <label>Patient Type</label>
                    <select value={billingPatientType} onChange={e => setBillingPatientType(e.target.value as any)}>
                      <option value="walkin">Walk-in Patient</option>
                      <option value="registered">Registered Patient</option>
                    </select>
                  </div>

                  {billingPatientType === 'walkin' ? (
                    <div className="form-group">
                      <label>Walk-in Patient Name</label>
                      <input type="text" placeholder="Enter patient name" value={billingWalkInName} onChange={e => setBillingWalkInName(e.target.value)} />
                    </div>
                  ) : (
                    <div className="form-group">
                      <label>Select Registered Patient</label>
                      <select value={billingPatientId} onChange={e => setBillingPatientId(e.target.value === '' ? '' : Number(e.target.value))}>
                        <option value="">-- Choose Patient --</option>
                        {patients.map(p => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {billingPatientType === 'registered' && (
                    <button className="btn btn-primary" onClick={() => handleLoadPrescription(Number(billingPatientId))} disabled={!billingPatientId} style={{ height: '42px' }}>
                      <FileText size={18} /> Load Prescription
                    </button>
                  )}
                </div>
              </div>

              {/* Basket / Cart */}
              <div className="glass-card" style={{ gridColumn: 'span 2' }}>
                <h3 style={{ marginBottom: '16px' }}>2. Add Medicines to Bill</h3>
                <div className="form-grid" style={{ alignItems: 'flex-end' }}>
                  
                  {/* Barcode Scanner */}
                  <div className="form-group">
                     <label style={{color: 'var(--accent-violet)'}}>Scan Barcode</label>
                     <input type="text" placeholder="Scan and press Enter..." value={barcodeInput} onChange={e => setBarcodeInput(e.target.value)} onKeyDown={handleBarcodeScan} autoFocus />
                  </div>

                  <div className="form-group" style={{ gridColumn: 'span 2' }}>
                    <label>Or Select Medicine Manually</label>
                    <Select 
                      styles={selectStyles}
                      options={inventory.filter(i => i.category === 'Pharmacy').map(item => ({ value: String(item.id), label: `${item.name} (Stock Available: ${item.quantity} | Price: ₹${item.unit_price})` }))}
                      value={billingNewItem.medicine_id ? { value: String(billingNewItem.medicine_id), label: (() => { const i = inventory.find(x => x.id === billingNewItem.medicine_id); return i ? `${i.name} (Stock Available: ${i.quantity} | Price: ₹${i.unit_price})` : ''; })() } : null}
                      onChange={(sel: any) => setBillingNewItem({ ...billingNewItem, medicine_id: sel ? Number(sel.value) : 0 })}
                      placeholder="-- Select Medicine --"
                      isClearable
                    />
                  </div>
                  <div className="form-group">
                    <label>Quantity</label>
                    <input type="number" min={1} value={billingNewItem.quantity} onChange={e => setBillingNewItem({ ...billingNewItem, quantity: Number(e.target.value) })} />
                  </div>
                  <button className="btn btn-secondary" onClick={addToCart} style={{ height: '42px' }}>
                    Add to Cart
                  </button>
                </div>

                <div className="table-container" style={{ marginTop: '24px' }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Item Name</th>
                        <th>Qty</th>
                        <th>Unit Price</th>
                        <th>Total</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {billingCart.map(item => (
                        <tr key={item.medicine_id}>
                          <td>{item.name}</td>
                          <td>{item.quantity}</td>
                          <td>₹{item.unit_price.toFixed(2)}</td>
                          <td>₹{(item.quantity * item.unit_price).toFixed(2)}</td>
                          <td>
                            <button className="btn btn-danger" style={{ padding: '6px' }} onClick={() => removeFromCart(item.medicine_id)}>
                              <Trash2 size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                      {billingCart.length === 0 && (
                        <tr>
                          <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Cart is empty</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Billing Summary */}
              <div className="glass-card">
                <h3 style={{ marginBottom: '16px' }}>3. Billing Summary</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

                  <div className="form-grid" style={{ marginTop: '8px' }}>
                    <div className="form-group">
                      <label>Discount (%)</label>
                      <input type="number" min={0} max={100} value={billingDiscount} onChange={e => setBillingDiscount(Number(e.target.value))} />
                    </div>
                    <div className="form-group">
                      <label>GST (%)</label>
                      <input type="number" min={0} max={100} value={billingGst} onChange={e => setBillingGst(Number(e.target.value))} />
                    </div>
                  </div>

                  {/* Pricing Breakdown */}
                  <div style={{ background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '12px', marginTop: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span>Subtotal:</span>
                      <span>₹{cartSubtotal.toFixed(2)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', color: 'var(--accent-rose)' }}>
                      <span>Discount ({billingDiscount}%):</span>
                      <span>-₹{cartDiscountAmt.toFixed(2)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span>GST ({billingGst}%):</span>
                      <span>₹{cartGstAmt.toFixed(2)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '1.1rem', borderTop: '1px solid var(--border)', paddingTop: '8px', marginTop: '8px', color: 'var(--accent-blue-soft)' }}>
                      <span>Grand Total:</span>
                      <span>₹{cartTotal.toFixed(2)}</span>
                    </div>
                  </div>

                  <button className="btn btn-primary" onClick={handleCheckoutBill} style={{ marginTop: '16px' }}>
                    Deduct Stock & Generate Bill
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'inventory' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Stock & Inventory Control</h1>
                <p>Manage stock levels, batch details, and low-level alerts</p>
              </div>
              <button className="btn btn-secondary" style={{display:'flex', alignItems:'center', gap:'8px'}} onClick={() => exportToCSV(inventory, 'Inventory_Stock.csv')}><Download size={16}/> Export CSV</button>
            </div>

            <div className="form-grid">
              <div className="glass-card" style={{ gridColumn: 'span 2' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                  <h3 style={{ margin: 0 }}>Stock Inventory</h3>
                  <input
                    type="text"
                    className="search-bar"
                    style={{ maxWidth: '320px' }}
                    placeholder="Search by name, category or batch..."
                    value={inventorySearch}
                    onChange={e => setInventorySearch(e.target.value)}
                  />
                </div>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Item Name</th>
                        <th>Category</th>
                        <th>Batch</th>
                        <th>Expiry</th>
                        <th>Remaining Stock</th>
                        <th>Unit Price</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inventory.filter(i => i.name.toLowerCase().includes(inventorySearch.toLowerCase()) || i.category.toLowerCase().includes(inventorySearch.toLowerCase()) || (i.batch_no && i.batch_no.toLowerCase().includes(inventorySearch.toLowerCase()))).map(item => (
                        <tr key={item.id}>
                          <td>{item.id}</td>
                          <td><strong>{item.name}</strong></td>
                          <td>{item.category}</td>
                          <td>{item.batch_no || 'N/A'}</td>
                          <td>{item.expiry_date || 'N/A'}</td>
                          <td style={{ fontWeight: 600 }}>{item.quantity}</td>
                          <td>₹{item.unit_price.toFixed(2)}</td>
                          <td>
                            {item.quantity <= item.min_stock_level ? (
                              <span className="badge badge-pending">Low Stock</span>
                            ) : (
                              <span className="badge badge-completed">Good</span>
                            )}
                          </td>
                          <td>
                            <button className="btn btn-danger" style={{ padding: '4px 8px' }} onClick={() => handleDeleteMedicineStock(item.id)}><Trash2 size={12}/></button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="glass-card">
                <h3 style={{ marginBottom: '16px' }}>Medicine Master (Add New Stock)</h3>
                <form onSubmit={handleSaveInventoryItem}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    
                    {/* Basic Info */}
                    <div style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                      <h4 style={{ marginBottom: '12px', color: 'var(--accent-blue)' }}>Basic Details</h4>
                      <div className="form-grid">
                        <div className="form-group"><label>Item Name *</label><input type="text" value={inventoryForm.name} onChange={e => setInventoryForm({ ...inventoryForm, name: e.target.value })} required /></div>
                        <div className="form-group"><label>Generic Name</label><input type="text" value={inventoryForm.details.genericName} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, genericName: e.target.value } })} /></div>
                        <div className="form-group"><label>Brand Name</label><input type="text" value={inventoryForm.details.brandName} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, brandName: e.target.value } })} /></div>
                        <div className="form-group"><label>Category *</label>
                          <select value={inventoryForm.category} onChange={e => setInventoryForm({ ...inventoryForm, category: e.target.value })}>
                            <option>Pharmacy</option><option>Lab</option><option>Consumable</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    {/* Identifiers & Clinical */}
                    <div style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                      <h4 style={{ marginBottom: '12px', color: 'var(--accent-emerald)' }}>Identifiers & Clinical</h4>
                      <div className="form-grid">
                        <div className="form-group"><label>Medicine Code</label><input type="text" value={inventoryForm.details.medicineCode} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, medicineCode: e.target.value } })} /></div>
                        <div className="form-group"><label>Barcode</label><input type="text" value={inventoryForm.details.barcode} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, barcode: e.target.value } })} placeholder="Scan Barcode here..." /></div>
                        <div className="form-group"><label>Manufacturer</label><input type="text" value={inventoryForm.details.manufacturer} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, manufacturer: e.target.value } })} /></div>
                        <div className="form-group"><label>Dosage Form</label><input type="text" placeholder="Tablet, Syrup, Injection..." value={inventoryForm.details.dosageForm} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, dosageForm: e.target.value } })} /></div>
                        <div className="form-group"><label>Strength</label><input type="text" placeholder="500mg, 10ml..." value={inventoryForm.details.strength} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, strength: e.target.value } })} /></div>
                        <div className="form-group"><label>Schedule Type</label><input type="text" placeholder="H, H1, X..." value={inventoryForm.details.scheduleType} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, scheduleType: e.target.value } })} /></div>
                      </div>
                    </div>

                    {/* Financials & Stock */}
                    <div style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                      <h4 style={{ marginBottom: '12px', color: 'var(--accent-amber)' }}>Financials & Inventory</h4>
                      <div className="form-grid">
                        <div className="form-group"><label>Batch No</label><input type="text" value={inventoryForm.batch_no} onChange={e => setInventoryForm({ ...inventoryForm, batch_no: e.target.value })} /></div>
                        <div className="form-group"><label>Expiry Date</label><input type="date" value={inventoryForm.expiry_date} onChange={e => setInventoryForm({ ...inventoryForm, expiry_date: e.target.value })} /></div>
                        <div className="form-group"><label>Initial Qty *</label><input type="number" value={inventoryForm.quantity || ''} onChange={e => setInventoryForm({ ...inventoryForm, quantity: Number(e.target.value) })} required /></div>
                        <div className="form-group"><label>Min Stock Level</label><input type="number" value={inventoryForm.min_stock_level || ''} onChange={e => setInventoryForm({ ...inventoryForm, min_stock_level: Number(e.target.value) })} /></div>
                        <div className="form-group"><label>Max Stock</label><input type="number" value={inventoryForm.details.maxStock || ''} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, maxStock: Number(e.target.value) } })} /></div>
                        <div className="form-group"><label>Selling Price (₹) *</label><input type="number" step="0.01" value={inventoryForm.unit_price || ''} onChange={e => setInventoryForm({ ...inventoryForm, unit_price: Number(e.target.value) })} required /></div>
                        <div className="form-group"><label>MRP (₹)</label><input type="number" step="0.01" value={inventoryForm.details.mrp || ''} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, mrp: Number(e.target.value) } })} /></div>
                        <div className="form-group"><label>Purchase Price (₹)</label><input type="number" step="0.01" value={inventoryForm.details.purchasePrice || ''} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, purchasePrice: Number(e.target.value) } })} /></div>
                        <div className="form-group"><label>HSN Code</label><input type="text" value={inventoryForm.details.hsnCode} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, hsnCode: e.target.value } })} /></div>
                        <div className="form-group"><label>GST %</label><input type="number" value={inventoryForm.details.gstPercent || ''} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, gstPercent: Number(e.target.value) } })} /></div>
                        <div className="form-group"><label>Rack Number</label><input type="text" value={inventoryForm.details.rackNumber} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, rackNumber: e.target.value } })} /></div>
                        <div className="form-group"><label>Storage Location</label><input type="text" value={inventoryForm.details.storageLocation} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, storageLocation: e.target.value } })} /></div>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Medicine Description / Notes</label>
                      <textarea rows={2} value={inventoryForm.details.description} onChange={e => setInventoryForm({ ...inventoryForm, details: { ...inventoryForm.details, description: e.target.value } })} />
                    </div>

                    <button type="submit" className="btn btn-primary" style={{ alignSelf: 'flex-start' }}><Plus size={18} /> Save Medicine Master</button>
                  </div>
                </form>
              </div>

              {/* Purchase / GRN Module */}
              <div className="glass-card" style={{ gridColumn: 'span 2' }}>
                <h3 style={{ marginBottom: '16px', color: 'var(--accent-emerald)' }}>Purchase & GRN (Goods Received Note)</h3>
                <form onSubmit={handleSaveGRN}>
                  <div className="form-grid">
                    <div className="form-group">
                      <label>Select Medicine *</label>
                      <Select
                        options={inventory.filter(i => i.name.toLowerCase().includes(inventorySearch.toLowerCase()) || i.category.toLowerCase().includes(inventorySearch.toLowerCase()) || (i.batch_no && i.batch_no.toLowerCase().includes(inventorySearch.toLowerCase()))).map(item => ({ value: String(item.id), label: `${item.name} (Current Stock: ${item.quantity})` }))}
                        value={grnForm.medicine_id ? { value: grnForm.medicine_id, label: inventory.find(i=>String(i.id) === grnForm.medicine_id)?.name || '' } : null}
                        onChange={(sel: any) => setGrnForm({ ...grnForm, medicine_id: sel?.value || '' })}
                        styles={selectStyles}
                        isClearable
                      />
                    </div>
                    <div className="form-group">
                      <label>Quantity Received *</label>
                      <input type="number" min="1" value={grnForm.quantity || ''} onChange={e => setGrnForm({ ...grnForm, quantity: Number(e.target.value) })} required />
                    </div>
                    <div className="form-group">
                      <label>Supplier Name</label>
                      <input type="text" value={grnForm.details.supplierName} onChange={e => setGrnForm({ ...grnForm, details: { ...grnForm.details, supplierName: e.target.value } })} />
                    </div>
                    <div className="form-group">
                      <label>Purchase Order No.</label>
                      <input type="text" value={grnForm.details.purchaseOrder} onChange={e => setGrnForm({ ...grnForm, details: { ...grnForm.details, purchaseOrder: e.target.value } })} />
                    </div>
                    <div className="form-group">
                      <label>Invoice Number</label>
                      <input type="text" value={grnForm.details.invoiceNumber} onChange={e => setGrnForm({ ...grnForm, details: { ...grnForm.details, invoiceNumber: e.target.value } })} />
                    </div>
                    <div className="form-group">
                      <label>Transaction Notes</label>
                      <input type="text" value={grnForm.notes} onChange={e => setGrnForm({ ...grnForm, notes: e.target.value })} />
                    </div>
                  </div>
                  <button type="submit" className="btn btn-primary" style={{ marginTop: '16px' }}><Plus size={18} /> Process GRN (Stock In)</button>
                </form>
              </div>

            </div>
          </div>
        )}

        {activeTab === 'pharmacy_invoices' && (
          <div>
            {!viewInvoice ? (
              <div className="glass-card no-print">
                <h3 style={{ marginBottom: '16px' }}>Pharmacy Billing Invoices Report</h3>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Bill ID</th>
                        <th>Bill Date</th>
                        <th>Patient Name</th>
                        <th>Bill Total</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pharmacyBills.map(bill => (
                        <tr key={bill.id}>
                          <td>#{bill.id}</td>
                          <td>{new Date(bill.bill_date).toLocaleString()}</td>
                          <td>{bill.patient_name || patients.find(p => p.id === bill.patient_id)?.name || 'Walk-in'}</td>
                          <td><strong>₹{bill.total.toFixed(2)}</strong></td>
                          <td>
                            <button className="btn btn-secondary" style={{ padding: '6px 12px' }} onClick={() => setViewInvoice(bill)}>
                              View Invoice
                            </button>
                          </td>
                        </tr>
                      ))}
                      {pharmacyBills.length === 0 && (
                        <tr>
                          <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No invoices generated yet</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div>
                {/* Print Invoice details */}
                <button className="btn btn-secondary no-print" onClick={() => setViewInvoice(null)} style={{ marginBottom: '20px' }}>
                  ← Back to Report
                </button>
                <button className="btn btn-primary no-print" onClick={() => window.print()} style={{ marginBottom: '20px', marginLeft: '12px' }}>
                  <Printer size={16} /> Print Invoice
                </button>

                <div className="glass-card print-bill-container" style={{ maxWidth: '600px', margin: '0 auto', padding: '32px' }}>
                  <div style={{ textAlign: 'center', borderBottom: '2px solid #ddd', paddingBottom: '16px', marginBottom: '24px' }}>
                    <h2 style={{ color: '#111', fontSize: '1.6rem', fontWeight: 800 }}>HOSPITAL PHARMACY INVOICE</h2>
                    <p style={{ color: '#666', fontSize: '0.9rem', marginTop: '4px' }}>MedBill Medical Centre & Pharmacy</p>
                    <p style={{ color: '#666', fontSize: '0.8rem' }}>123 Hospital Road, Chennai</p>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '0.9rem', color: '#333', marginBottom: '24px' }}>
                    <div>
                      <p><strong>Bill ID:</strong> #{viewInvoice.id}</p>
                      <p><strong>Date:</strong> {new Date(viewInvoice.bill_date).toLocaleString()}</p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <p><strong>Patient Name:</strong> {viewInvoice.patient_name || patients.find(p => p.id === viewInvoice.patient_id)?.name || 'Walk-in'}</p>
                      {viewInvoice.patient_id && <p><strong>Patient ID:</strong> {viewInvoice.patient_id}</p>}
                      {viewInvoice.patient_id && patients.find(p => p.id === viewInvoice.patient_id)?.phone && (
                        <p><strong>Phone:</strong> {patients.find(p => p.id === viewInvoice.patient_id)?.phone}</p>
                      )}
                    </div>
                  </div>

                  <table style={{ width: '100%', color: '#333', marginBottom: '24px' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid #333' }}>
                        <th style={{ color: '#333', padding: '8px 0', background: 'none' }}>Medicine</th>
                        <th style={{ color: '#333', padding: '8px 0', textAlign: 'right', background: 'none' }}>Qty</th>
                        <th style={{ color: '#333', padding: '8px 0', textAlign: 'right', background: 'none' }}>Price</th>
                        <th style={{ color: '#333', padding: '8px 0', textAlign: 'right', background: 'none' }}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {viewInvoice.items.map(item => (
                        <tr key={item.id} style={{ borderBottom: '1px solid #eee' }}>
                          <td style={{ padding: '8px 0' }}>{item.medicine_name}</td>
                          <td style={{ padding: '8px 0', textAlign: 'right' }}>{item.quantity}</td>
                          <td style={{ padding: '8px 0', textAlign: 'right' }}>₹{item.unit_price.toFixed(2)}</td>
                          <td style={{ padding: '8px 0', textAlign: 'right' }}>₹{item.total_price.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-end', fontSize: '0.95rem', color: '#333', borderTop: '1px solid #ddd', paddingTop: '16px' }}>
                    <div style={{ display: 'flex', width: '220px', justifyContent: 'space-between' }}>
                      <span>Subtotal:</span>
                      <span>₹{viewInvoice.subtotal.toFixed(2)}</span>
                    </div>
                    <div style={{ display: 'flex', width: '220px', justifyContent: 'space-between', color: '#c00' }}>
                      <span>Discount ({viewInvoice.discount}%):</span>
                      <span>-₹{((viewInvoice.discount / 100) * viewInvoice.subtotal).toFixed(2)}</span>
                    </div>
                    <div style={{ display: 'flex', width: '220px', justifyContent: 'space-between' }}>
                      <span>GST ({viewInvoice.gst}%):</span>
                      <span>₹{viewInvoice.gst.toFixed(2)}%</span>
                    </div>
                    <div style={{ display: 'flex', width: '220px', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '1.1rem', borderTop: '2px double #333', paddingTop: '8px', marginTop: '8px' }}>
                      <span>Grand Total:</span>
                      <span>₹{viewInvoice.total.toFixed(2)}</span>
                    </div>
                  </div>

                  <div style={{ textAlign: 'center', marginTop: '40px', borderTop: '1px solid #eee', paddingTop: '16px', color: '#888', fontSize: '0.8rem' }}>
                    Thank you for your visit. Get well soon!
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'ipd_workspace' && (() => {
          const active = ipAdmissions.filter(a => a.status === 'Admitted');
          const boardFiltered = bedBoard.filter(b =>
            bedBoardFilter === 'All' ? true : b.status === bedBoardFilter);
          const unassigned = active.filter(a => !a.bed_id);
          return (
            <div className="no-print">
              <div className="header">
                <div className="header-title">
                  <h1>Inpatient Ward</h1>
                  <p>Live bed board, admissions and ward workload.</p>
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  <button className="btn btn-secondary" onClick={() => { loadAllData(); loadIpdStructure(); }}>
                    <RefreshCw size={16} /> Refresh
                  </button>
                  <button className="btn btn-primary" onClick={() => setActiveTab('ip_admissions')}>
                    <PlusCircle size={16} /> Admit a patient
                  </button>
                </div>
              </div>

              <div className="dashboard-grid">
                {[
                  { label: 'Beds in service', value: ipdStats?.total_beds ?? 0, color: 'var(--accent-blue)' },
                  { label: 'Available now', value: ipdStats?.available_beds ?? 0, color: 'var(--accent-emerald)' },
                  { label: 'Occupied', value: ipdStats?.occupied_beds ?? 0, color: 'var(--accent-amber)' },
                  { label: 'Occupancy', value: `${ipdStats?.occupancy_percent ?? 0}%`, color: 'var(--accent-violet)' },
                  { label: 'Current admissions', value: ipdStats?.current_admissions ?? 0, color: 'var(--accent-sky)' },
                  { label: 'Admitted today', value: ipdStats?.admissions_today ?? 0, color: 'var(--accent-blue)' },
                  { label: 'Discharged today', value: ipdStats?.discharges_today ?? 0, color: 'var(--accent-emerald)' },
                  { label: 'Avg stay (days)', value: ipdStats?.average_length_of_stay ?? 0, color: 'var(--text-secondary)' },
                  { label: 'Critical (24h)', value: ipdStats?.critical_patients ?? 0, color: 'var(--accent-rose)' },
                  { label: 'Active medications', value: ipdStats?.active_medication_orders ?? 0, color: 'var(--accent-violet)' },
                ].map(s => (
                  <div className="stat-card" key={s.label}>
                    <div className="stat-icon" style={{ background: `${s.color}1a`, color: s.color }}><Bed size={22} /></div>
                    <div>
                      <h3 style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>{s.label}</h3>
                      <h2 style={{ margin: 0 }}>{s.value}</h2>
                    </div>
                  </div>
                ))}
              </div>

              {/* Bed board */}
              <div className="glass-card" style={{ marginBottom: '18px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
                  <h3 style={{ margin: 0 }}>Bed board</h3>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <select className="search-bar" style={{ maxWidth: '190px' }} value={bedBoardFilter}
                      onChange={e => setBedBoardFilter(e.target.value)}>
                      <option value="All">All statuses</option>
                      {['Available', 'Occupied', 'Reserved', 'Cleaning', 'Maintenance', 'Blocked'].map(s =>
                        <option key={s} value={s}>{s}</option>)}
                    </select>
                    <select className="search-bar" style={{ maxWidth: '220px' }}
                      value={activeWardId ?? ''} onChange={e => setActiveWardId(e.target.value ? Number(e.target.value) : null)}>
                      <option value="">All wards</option>
                      {wards.map((w: any) => <option key={w.id} value={w.id}>{w.name} ({w.ward_type})</option>)}
                    </select>
                  </div>
                </div>

                {bedBoard.length === 0 ? (
                  <div style={{ padding: '22px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No beds configured. Add wards, rooms and beds under <b>Ward &amp; Bed Setup</b>.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: '10px' }}>
                    {boardFiltered
                      .filter(b => !activeWardId || b.ward_id === activeWardId)
                      .map(b => {
                        const tone = b.status === 'Available' ? '#10b981'
                          : b.status === 'Occupied' ? '#f59e0b'
                          : b.status === 'Cleaning' ? 'var(--accent-sky)' : 'var(--accent-slate)';
                        return (
                          <div key={b.bed_id} style={{
                            border: `1px solid ${tone}55`, borderLeft: `4px solid ${tone}`,
                            borderRadius: '8px', padding: '10px', background: `${tone}0d`,
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <b>{b.bed_code}</b>
                              <span className={`status-badge ${b.status.toLowerCase()}`} style={{ fontSize: '10px' }}>{b.status}</span>
                            </div>
                            <small style={{ color: 'var(--text-muted)', display: 'block' }}>
                              {b.ward_name} · Room {b.room_number}{b.bed_type ? ` · ${b.bed_type}` : ''}
                            </small>
                            <small style={{ color: 'var(--text-muted)' }}>₹{b.daily_charge}/night</small>
                            {b.admission_id ? (
                              <div style={{ marginTop: '8px' }}>
                                <b style={{ fontSize: '13px' }}>{b.patient_name}</b>
                                <small style={{ display: 'block', color: 'var(--text-muted)' }}>
                                  {b.patient_uhid} · {b.admitted_at ? new Date(b.admitted_at).toLocaleDateString() : ''}
                                </small>
                                <small style={{ display: 'block', color: 'var(--text-muted)' }}>
                                  {b.attending_doctor || 'No doctor assigned'}
                                </small>
                                <button className="btn btn-secondary" style={{ marginTop: '6px', padding: '3px 8px', fontSize: '11px' }}
                                  onClick={() => openAdmissionDetail(b.admission_id)}>Open record</button>
                              </div>
                            ) : b.status === 'Cleaning' || b.status === 'Maintenance' ? (
                              <button className="btn btn-secondary" style={{ marginTop: '8px', padding: '3px 8px', fontSize: '11px' }}
                                onClick={() => handleSetBedStatus(b.bed_id, 'Available')}>Mark ready</button>
                            ) : b.status === 'Available' ? (
                              <button className="btn btn-secondary" style={{ marginTop: '8px', padding: '3px 8px', fontSize: '11px' }}
                                onClick={() => handleSetBedStatus(b.bed_id, 'Maintenance')}>Block</button>
                            ) : null}
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>

              {/* Active admissions */}
              <div className="glass-card">
                <h3 style={{ marginTop: 0 }}>Admitted patients ({active.length})</h3>
                {unassigned.length > 0 && (
                  <p style={{ fontSize: '12px', color: 'var(--warn, #f59e0b)' }}>
                    {unassigned.length} patient(s) have no bed yet — pick a free bed above and press Assign.
                  </p>
                )}
                <div className="table-container">
                  <table>
                    <thead><tr><th>Patient</th><th>Bed</th><th>Admitted</th><th>Type</th><th>Doctor</th><th>Actions</th></tr></thead>
                    <tbody>
                      {active.map(a => (
                        <tr key={a.id}>
                          <td><b>{a.patient?.name || `#${a.patient_id}`}</b>
                            <br /><small style={{ color: 'var(--text-muted)' }}>#{a.patient_id}</small></td>
                          <td>
                            {a.bed_id
                              ? <>{a.bed_code}<br /><small style={{ color: 'var(--text-muted)' }}>{a.ward_number} · {a.room_number}</small></>
                              : <span className="status-badge pending">No bed</span>}
                          </td>
                          <td>{new Date(a.admission_date).toLocaleDateString()}</td>
                          <td>{a.admission_type}</td>
                          <td>{a.attending_doctor?.full_name || a.doctor_in_charge || '—'}</td>
                          <td>
                            <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                              <button className="btn btn-primary" style={{ padding: '4px 8px', fontSize: '12px' }}
                                onClick={() => openAdmissionDetail(a.id)}>Open record</button>
                              {!a.bed_id && (
                                <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }}
                                  onClick={() => handleAssignBed(a.id, a.patient?.name || `#${a.patient_id}`)}>Assign bed</button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                      {active.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No patients admitted right now.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          );
        })()}

        {activeTab === 'ipd_setup' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Ward &amp; Bed Setup</h1>
                <p>Departments, wards, rooms and beds — the physical capacity of the hospital.</p>
              </div>
              <button className="btn btn-secondary" onClick={loadIpdStructure}><RefreshCw size={16} /> Refresh</button>
            </div>

            <div className="form-grid">
              <div className="glass-card">
                <h3>Department</h3>
                <form onSubmit={handleCreateDepartment}>
                  <div className="form-group"><label>Name *</label>
                    <input type="text" required value={newDepartment.name}
                      onChange={e => setNewDepartment({ ...newDepartment, name: e.target.value })} /></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Code *</label>
                    <input type="text" required value={newDepartment.code}
                      onChange={e => setNewDepartment({ ...newDepartment, code: e.target.value.toUpperCase() })} /></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Type</label>
                    <select value={newDepartment.department_type}
                      onChange={e => setNewDepartment({ ...newDepartment, department_type: e.target.value })}>
                      {['Clinical', 'Diagnostic', 'Support', 'Administrative', 'Emergency'].map(t => <option key={t}>{t}</option>)}
                    </select></div>
                  <button type="submit" className="btn btn-primary" style={{ marginTop: '12px' }}>Add department</button>
                </form>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '10px' }}>
                  {departments.length} department(s) configured.
                </p>
              </div>

              <div className="glass-card">
                <h3>Ward</h3>
                <form onSubmit={handleCreateWard}>
                  <div className="form-group"><label>Name *</label>
                    <input type="text" required value={newWard.name}
                      onChange={e => setNewWard({ ...newWard, name: e.target.value })} /></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Code *</label>
                    <input type="text" required value={newWard.code}
                      onChange={e => setNewWard({ ...newWard, code: e.target.value.toUpperCase() })} /></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Ward type</label>
                    <select value={newWard.ward_type} onChange={e => setNewWard({ ...newWard, ward_type: e.target.value })}>
                      {['General', 'Semi-Private', 'Private', 'ICU', 'HDU', 'NICU', 'Maternity', 'Paediatric', 'Emergency', 'Isolation', 'Day Care'].map(t => <option key={t}>{t}</option>)}
                    </select></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Department</label>
                    <select value={newWard.department_id} onChange={e => setNewWard({ ...newWard, department_id: e.target.value })}>
                      <option value="">— none —</option>
                      {departments.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}
                    </select></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Daily charge (₹)</label>
                    <input type="number" min="0" value={newWard.daily_charge}
                      onChange={e => setNewWard({ ...newWard, daily_charge: Number(e.target.value) })} /></div>
                  <button type="submit" className="btn btn-primary" style={{ marginTop: '12px' }}>Add ward</button>
                </form>
              </div>

              <div className="glass-card">
                <h3>Room</h3>
                <form onSubmit={handleCreateRoom}>
                  <div className="form-group"><label>Ward *</label>
                    <select required value={newRoom.ward_id} onChange={e => setNewRoom({ ...newRoom, ward_id: e.target.value, })}>
                      <option value="">— choose —</option>
                      {wards.map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
                    </select></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Room number *</label>
                    <input type="text" required value={newRoom.room_number}
                      onChange={e => setNewRoom({ ...newRoom, room_number: e.target.value })} /></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Room type</label>
                    <input type="text" value={newRoom.room_type} placeholder="General / Deluxe"
                      onChange={e => setNewRoom({ ...newRoom, room_type: e.target.value })} /></div>
                  <button type="submit" className="btn btn-primary" style={{ marginTop: '12px' }}>Add room</button>
                </form>
              </div>

              <div className="glass-card">
                <h3>Bed</h3>
                <form onSubmit={handleCreateBed}>
                  <div className="form-group"><label>Room *</label>
                    <select required value={newBed.room_id} onChange={e => setNewBed({ ...newBed, room_id: e.target.value })}>
                      <option value="">— choose —</option>
                      {rooms.map((r: any) => {
                        const w = wards.find((x: any) => x.id === r.ward_id);
                        return <option key={r.id} value={r.id}>{w ? `${w.name} / ` : ''}{r.room_number}</option>;
                      })}
                    </select></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Bed code *</label>
                    <input type="text" required value={newBed.bed_code} placeholder="A, B, 1, 2…"
                      onChange={e => setNewBed({ ...newBed, bed_code: e.target.value })} /></div>
                  <div className="form-group" style={{ marginTop: '10px' }}><label>Bed type</label>
                    <input type="text" value={newBed.bed_type} placeholder="Standard / Electric"
                      onChange={e => setNewBed({ ...newBed, bed_type: e.target.value })} /></div>
                  <button type="submit" className="btn btn-primary" style={{ marginTop: '12px' }}>Add bed</button>
                </form>
              </div>
            </div>

            <div className="glass-card" style={{ marginTop: '18px' }}>
              <h3 style={{ marginTop: 0 }}>Configured capacity</h3>
              <div className="table-container">
                <table>
                  <thead><tr><th>Ward</th><th>Type</th><th>Department</th><th>Rooms</th><th>Beds</th><th>Available</th><th>Occupied</th><th>Daily charge</th></tr></thead>
                  <tbody>
                    {wards.map((w: any) => {
                      const wardBeds = bedBoard.filter(b => b.ward_id === w.id);
                      return (
                        <tr key={w.id}>
                          <td><b>{w.name}</b><br /><small style={{ color: 'var(--text-muted)' }}>{w.code}</small></td>
                          <td>{w.ward_type}</td>
                          <td>{w.department?.name || '—'}</td>
                          <td>{rooms.filter((r: any) => r.ward_id === w.id).length}</td>
                          <td>{wardBeds.length}</td>
                          <td style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>{wardBeds.filter(b => b.status === 'Available').length}</td>
                          <td style={{ color: 'var(--accent-amber)', fontWeight: 600 }}>{wardBeds.filter(b => b.status === 'Occupied').length}</td>
                          <td>₹{w.daily_charge}</td>
                        </tr>
                      );
                    })}
                    {wards.length === 0 && <tr><td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No wards configured yet.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'ip_admissions' && (
          <div>
            <div className="header no-print">
              <div className="header-title">
                <h1>IP Admissions</h1>
                <p>Manage Inpatient Admissions</p>
              </div>
            </div>

            <div className="grid-2">
              <div className="glass-card">
                <h3>Admit Patient</h3>
                <form onSubmit={handleAdmitPatient}>
                  <div className="form-group">
                    <label>Select Patient</label>
                    <Select 
                      styles={selectStyles}
                      options={patients.map(p => ({ value: String(p.id), label: `${p.name} (ID: ${p.id})` }))}
                      value={ipAdmissionForm.patient_id ? { value: String(ipAdmissionForm.patient_id), label: patients.find(p => String(p.id) === String(ipAdmissionForm.patient_id))?.name + ' (ID: ' + ipAdmissionForm.patient_id + ')' } : null}
                      onChange={(sel: any) => setIpAdmissionForm({...ipAdmissionForm, patient_id: sel ? sel.value : ''})}
                      placeholder="Select Patient"
                      isClearable
                    />
                  </div>
                  <div className="ward-selection">
                    <label>Select Ward &amp; Bed</label>
                    {wards.length === 0 ? (
                      <div style={{ padding: '14px', border: '1px dashed var(--border)', borderRadius: '8px', color: 'var(--text-muted)', fontSize: '13px' }}>
                        No wards are configured yet. An administrator must add wards, rooms and beds
                        under <b>Ward &amp; Bed Setup</b> before patients can be admitted to a bed.
                      </div>
                    ) : (
                      <>
                        <div className="ward-tabs">
                          {wards.map((ward: any) => {
                            const wardBeds = bedBoard.filter(b => b.ward_id === ward.id);
                            const free = wardBeds.filter(b => b.status === 'Available').length;
                            return (
                              <div
                                key={ward.id}
                                className={`ward-tab ${activeWardId === ward.id ? 'active' : ''}`}
                                onClick={() => { setActiveWardId(ward.id); setSelectedBedId(null); }}
                              >
                                {ward.name}
                                <small style={{ display: 'block', fontSize: '10px', opacity: 0.75 }}>
                                  {free}/{wardBeds.length} free
                                </small>
                              </div>
                            );
                          })}
                        </div>

                        <div className="bus-layout-wrapper">
                          <div className="nurse-station-front">
                            <span>⚕️ Nurse Station</span>
                          </div>
                          <div className="bus-beds-container">
                            {(() => {
                              const wardBeds = bedBoard.filter(b => b.ward_id === activeWardId);
                              if (wardBeds.length === 0) {
                                return (
                                  <div style={{ padding: '18px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                                    This ward has no beds yet.
                                  </div>
                                );
                              }
                              const rows = Math.ceil(wardBeds.length / 2);
                              return Array.from({ length: rows }).map((_, rowIndex) => {
                                const left = wardBeds[rowIndex * 2];
                                const right = wardBeds[rowIndex * 2 + 1];
                                const renderBed = (bed: any) => {
                                  if (!bed) return <div className="bus-bed-item-empty"></div>;
                                  const free = bed.status === 'Available';
                                  const isSelected = selectedBedId === bed.bed_id;
                                  return (
                                    <div
                                      key={bed.bed_id}
                                      title={`${bed.room_number} · ${bed.bed_code} · ${bed.status}${bed.patient_name ? ` · ${bed.patient_name}` : ''}`}
                                      className={`bus-bed-item ${free ? (isSelected ? 'selected' : 'available') : 'occupied'}`}
                                      onClick={() => { if (free) setSelectedBedId(bed.bed_id); }}
                                    >
                                      <Bed size={24} />
                                      <span className="bed-number">{bed.bed_code}</span>
                                      <small style={{ fontSize: '9px', display: 'block', lineHeight: 1.1 }}>
                                        {bed.room_number}
                                      </small>
                                      {bed.patient_name && (
                                        <small style={{ fontSize: '9px', display: 'block', lineHeight: 1.1, opacity: 0.9 }}>
                                          {bed.patient_name}
                                        </small>
                                      )}
                                    </div>
                                  );
                                };
                                return (
                                  <div className="bus-row" key={`row-${rowIndex}`}>
                                    <div className="bus-seat-group left">{renderBed(left)}</div>
                                    <div className="bus-aisle"><div className="aisle-dots"></div></div>
                                    <div className="bus-seat-group right">{renderBed(right)}</div>
                                  </div>
                                );
                              });
                            })()}
                          </div>
                          <div className="bus-layout-legend">
                            <div className="legend-item"><span className="legend-color available"></span> Available</div>
                            <div className="legend-item"><span className="legend-color occupied"></span> Occupied</div>
                            <div className="legend-item"><span className="legend-color selected"></span> Selected</div>
                          </div>
                          <p style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-muted)' }}>
                            {selectedBedId
                              ? <>Selected bed: <b>{bedBoard.find(b => b.bed_id === selectedBedId)?.bed_code}</b> ({bedBoard.find(b => b.bed_id === selectedBedId)?.room_number})</>
                              : 'Pick a free bed — or leave empty to admit and assign a bed later.'}
                          </p>
                        </div>
                      </>
                    )}
                  </div>
                  <div className="form-group">
                    <label>Doctor in Charge</label>
                    <input type="text" value={ipAdmissionForm.doctor_in_charge} onChange={e => setIpAdmissionForm({...ipAdmissionForm, doctor_in_charge: e.target.value})} />
                  </div>
                  <div className="form-group">
                    <label>Reason for Admission</label>
                    <textarea value={ipAdmissionForm.reason_for_admission} onChange={e => setIpAdmissionForm({...ipAdmissionForm, reason_for_admission: e.target.value})} rows={3}></textarea>
                  </div>
                  <button type="submit" className="btn btn-primary"><Plus size={18} /> Admit Patient</button>
                </form>
              </div>

              <div className="glass-card">
                <h3>Current Admissions</h3>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Patient</th>
                        <th>Ward / Room / Bed</th>
                        <th>Doctor</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ipAdmissions.map(adm => (
                        <tr key={adm.id}>
                          <td>{new Date(adm.admission_date).toLocaleDateString()}</td>
                          <td>
                            <b>{adm.patient?.name || 'Unknown'}</b>
                            <br /><small style={{ color: 'var(--text-muted)' }}>#{adm.patient_id}{adm.patient?.age ? ` · ${adm.patient.age}/${adm.patient.gender?.[0]}` : ''}</small>
                          </td>
                          <td>
                            {adm.ward_number || '—'} / {adm.room_number || '—'}
                            {adm.bed_code ? <><br /><small style={{ color: 'var(--text-muted)' }}>Bed {adm.bed_code}</small></> : null}
                          </td>
                          <td>{adm.attending_doctor?.full_name || adm.doctor_in_charge || '—'}</td>
                          <td>{adm.admission_type || 'Planned'}</td>
                          <td><span className="status-badge" style={{backgroundColor: adm.status === 'Admitted' ? '#e0f2fe' : '#d1fae5', color: adm.status === 'Admitted' ? '#0369a1' : '#065f46'}}>{adm.status}</span></td>
                          <td>
                            <div style={{display:'flex', gap:'5px'}}>
                              <button className="btn btn-primary" style={{padding:'4px 8px', fontSize:'12px'}} onClick={async () => {
                                setActiveTab('reports');
                                setReportType('patient');
                                setPatientReportId(String(adm.patient_id));
                                try {
                                  const res = await axios.get(`${API_BASE}/reports/patient/${adm.patient_id}`);
                                  setPatientReportData(res.data);
                                } catch(e) {}
                              }}>View Details</button>
                              <button className="btn btn-secondary" style={{padding:'4px 8px', fontSize:'12px'}} onClick={() => {
                                setBillingPatientType('registered');
                                setBillingPatientId(adm.patient_id);
                                setActiveTab('pharmacy');
                              }}>Pharmacy</button>
                              <button className="btn btn-secondary" style={{padding:'4px 8px', fontSize:'12px'}} onClick={async () => {
                                // The server prices the whole stay (every bed, including after
                                // discharge when there is no current bed); fall back to the bed rate.
                                let roomPerDay = adm.bed?.daily_charge ?? ipBillForm.room_charge_per_day;
                                let days = ipBillForm.days_stayed;
                                try {
                                  const res = await axios.get(`${API_BASE}/ip-admissions/${adm.id}/detail`);
                                  days = Math.max(res.data.length_of_stay_days ?? 1, 1);
                                  roomPerDay = Math.round((res.data.billable_room_charge / days) * 100) / 100;
                                } catch (e) { /* keep the fallback */ }
                                setIpBillForm({...ipBillForm, patient_id: String(adm.patient_id), admission_id: String(adm.id), room_charge_per_day: roomPerDay, days_stayed: days});
                                setBillingTab('ip');
                                setActiveTab('billing');
                              }}>IP Bill</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                      {ipAdmissions.length === 0 && (
                        <tr><td colSpan={7} style={{textAlign: 'center', color: 'var(--text-muted)'}}>No IP Admissions found.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'insurance' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Insurance Claims</h1>
                <p>Track cashless and reimbursement claims against hospital bills.</p>
              </div>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button className="btn btn-secondary" onClick={loadInsurance}><RefreshCw size={16} /> Refresh</button>
                <button className="btn btn-secondary" onClick={() => setIsPolicyModalOpen(true)}><Shield size={16} /> Add policy</button>
                <button className="btn btn-primary" onClick={() => setIsClaimModalOpen(true)}><PlusCircle size={16} /> New claim</button>
              </div>
            </div>

            {insuranceStats && (
              <div className="dashboard-grid">
                {[
                  { label: 'Total claims', value: insuranceStats.total_claims, color: 'var(--accent-blue)' },
                  { label: 'Submitted', value: insuranceStats.submitted + insuranceStats.under_review, color: 'var(--accent-amber)' },
                  { label: 'Approved', value: insuranceStats.approved, color: 'var(--accent-emerald)' },
                  { label: 'Rejected', value: insuranceStats.rejected, color: 'var(--accent-rose)' },
                  { label: 'Settled', value: insuranceStats.settled, color: 'var(--accent-violet)' },
                  { label: 'Claimed amount', value: `₹${insuranceStats.claimed_amount.toFixed(0)}`, color: 'var(--accent-sky)' },
                  { label: 'Approved amount', value: `₹${insuranceStats.approved_amount.toFixed(0)}`, color: 'var(--accent-emerald)' },
                  { label: 'Pending payout', value: `₹${insuranceStats.pending_amount.toFixed(0)}`, color: 'var(--accent-yellow)' },
                ].map(s => (
                  <div className="stat-card" key={s.label}>
                    <div className="stat-icon" style={{ background: `${s.color}1a`, color: s.color }}><Shield size={24} /></div>
                    <div><h3 style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>{s.label}</h3><h2 style={{ margin: 0 }}>{s.value}</h2></div>
                  </div>
                ))}
              </div>
            )}

            <div className="glass-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', gap: '12px' }}>
                <h3 style={{ margin: 0 }}>Claims</h3>
                <select className="search-bar" value={insuranceFilter} onChange={e => setInsuranceFilter(e.target.value)} style={{ maxWidth: '220px' }}>
                  <option value="All">All statuses</option>
                  {['Draft','Submitted','Under Review','Approved','Partially Approved','Rejected','Settled'].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="table-container">
                <table>
                  <thead><tr><th>Claim #</th><th>Patient</th><th>Type</th><th>Treatment</th><th>Claimed</th><th>Approved</th><th>Status</th><th>Updated</th><th></th></tr></thead>
                  <tbody>
                    {insuranceClaims
                      .filter(c => insuranceFilter === 'All' || c.status === insuranceFilter)
                      .map(c => (
                        <tr key={c.id}>
                          <td><b>{c.claim_number}</b></td>
                          <td>{c.patient?.name || `#${c.patient_id}`}</td>
                          <td>{c.claim_type}</td>
                          <td>{c.treatment_type || '-'}</td>
                          <td>₹{c.claimed_amount?.toFixed(2)}</td>
                          <td>₹{c.approved_amount?.toFixed(2)}</td>
                          <td><span className={`status-badge ${(c.status || '').replace(/ /g, '-').toLowerCase()}`}>{c.status}</span></td>
                          <td><small>{c.updated_at ? new Date(c.updated_at).toLocaleDateString() : '-'}</small></td>
                          <td>
                            {!['Settled', 'Rejected'].includes(c.status) && (
                              <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }} onClick={() => {
                                setSelectedClaim(c);
                                setClaimStatusForm({
                                  status: c.status === 'Draft' ? 'Submitted' : 'Under Review',
                                  approved_amount: c.approved_amount || 0,
                                  rejection_reason: '', remarks: '',
                                });
                              }}>Update</button>
                            )}
                          </td>
                        </tr>
                      ))}
                    {insuranceClaims.length === 0 && <tr><td colSpan={9} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No claims yet.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>

            {/* CLAIM STATUS MODAL */}
            {selectedClaim && (
              <div className="modal-overlay">
                <div className="modal-content" style={{ maxWidth: '520px' }}>
                  <div className="modal-header">
                    <h2>{selectedClaim.claim_number}</h2>
                    <button className="close-btn" onClick={() => setSelectedClaim(null)}><X size={20} /></button>
                  </div>
                  <div className="modal-body">
                    <p><b>Patient:</b> {selectedClaim.patient?.name} &nbsp; <b>Claimed:</b> ₹{selectedClaim.claimed_amount?.toFixed(2)}</p>
                    <div className="form-group">
                      <label>New status</label>
                      <select value={claimStatusForm.status} onChange={e => setClaimStatusForm({ ...claimStatusForm, status: e.target.value })}>
                        {['Submitted','Under Review','Approved','Partially Approved','Rejected','Settled'].map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                    {['Approved', 'Partially Approved'].includes(claimStatusForm.status) && (
                      <div className="form-group" style={{ marginTop: '12px' }}>
                        <label>Approved amount (₹)</label>
                        <input type="number" min="0" value={claimStatusForm.approved_amount}
                          onChange={e => setClaimStatusForm({ ...claimStatusForm, approved_amount: Number(e.target.value) })} />
                      </div>
                    )}
                    {claimStatusForm.status === 'Rejected' && (
                      <div className="form-group" style={{ marginTop: '12px' }}>
                        <label>Rejection reason *</label>
                        <textarea rows={2} value={claimStatusForm.rejection_reason}
                          onChange={e => setClaimStatusForm({ ...claimStatusForm, rejection_reason: e.target.value })} />
                      </div>
                    )}
                    <div className="form-group" style={{ marginTop: '12px' }}>
                      <label>Remarks</label>
                      <input type="text" value={claimStatusForm.remarks} onChange={e => setClaimStatusForm({ ...claimStatusForm, remarks: e.target.value })} />
                    </div>
                    <button className="btn btn-primary" style={{ width: '100%', marginTop: '16px' }} onClick={handleUpdateClaimStatus}>
                      <Save size={16} /> Save status
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* NEW CLAIM MODAL */}
            {isClaimModalOpen && (
              <div className="modal-overlay">
                <div className="modal-content" style={{ maxWidth: '620px' }}>
                  <div className="modal-header">
                    <h2>New insurance claim</h2>
                    <button className="close-btn" onClick={() => setIsClaimModalOpen(false)}><X size={20} /></button>
                  </div>
                  <div className="modal-body">
                    <form onSubmit={handleCreateClaim}>
                      <div className="form-grid">
                        <div className="form-group">
                          <label>Patient *</label>
                          <Select
                            styles={selectStyles}
                            options={patients.map(p => ({ value: String(p.id), label: `${p.id} - ${p.name} (${p.phone || 'no phone'})` }))}
                            value={claimForm.patient_id ? { value: claimForm.patient_id, label: (() => { const p = patients.find(x => String(x.id) === claimForm.patient_id); return p ? `${p.id} - ${p.name}` : claimForm.patient_id; })() } : null}
                            onChange={(o: any) => {
                              const pid = o?.value || '';
                              setClaimForm(prev => ({ ...prev, patient_id: pid, policy_id: '' }));
                              if (pid) {
                                axios.get(`${API_BASE}/insurance/policies?patient_id=${pid}`)
                                  .then(r => setInsurancePolicies(prev => [...r.data, ...prev.filter((p: any) => p.patient_id !== Number(pid))]))
                                  .catch(() => { /* policies are optional */ });
                              }
                            }}
                            placeholder="Search patient..."
                          />
                        </div>
                        <div className="form-group">
                          <label>Policy</label>
                          <select value={claimForm.policy_id} onChange={e => setClaimForm({ ...claimForm, policy_id: e.target.value })}>
                            <option value="">No policy on file</option>
                            {insurancePolicies.filter(p => !claimForm.patient_id || String(p.patient_id) === claimForm.patient_id)
                              .map(p => <option key={p.id} value={p.id}>{p.provider} — {p.policy_number}</option>)}
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Claim type</label>
                          <select value={claimForm.claim_type} onChange={e => setClaimForm({ ...claimForm, claim_type: e.target.value })}>
                            <option>Reimbursement</option><option>Cashless</option>
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Treatment</label>
                          <select value={claimForm.treatment_type} onChange={e => setClaimForm({ ...claimForm, treatment_type: e.target.value })}>
                            {['OP','IP','Pharmacy','Laboratory','Other'].map(t => <option key={t}>{t}</option>)}
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Diagnosis</label>
                          <input type="text" value={claimForm.diagnosis} onChange={e => setClaimForm({ ...claimForm, diagnosis: e.target.value })} />
                        </div>
                        <div className="form-group">
                          <label>Claimed amount (₹) *</label>
                          <input type="number" min="0" required value={claimForm.claimed_amount}
                            onChange={e => setClaimForm({ ...claimForm, claimed_amount: Number(e.target.value) })} />
                        </div>
                        <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                          <label>Remarks</label>
                          <input type="text" value={claimForm.remarks} onChange={e => setClaimForm({ ...claimForm, remarks: e.target.value })} />
                        </div>
                      </div>
                      <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '16px' }}>Create claim</button>
                    </form>
                  </div>
                </div>
              </div>
            )}

            {/* NEW POLICY MODAL */}
            {isPolicyModalOpen && (
              <div className="modal-overlay">
                <div className="modal-content" style={{ maxWidth: '620px' }}>
                  <div className="modal-header">
                    <h2>Add insurance policy</h2>
                    <button className="close-btn" onClick={() => setIsPolicyModalOpen(false)}><X size={20} /></button>
                  </div>
                  <div className="modal-body">
                    <form onSubmit={handleCreatePolicy}>
                      <div className="form-grid">
                        <div className="form-group">
                          <label>Patient *</label>
                          <Select
                            styles={selectStyles}
                            options={patients.map(p => ({ value: String(p.id), label: `${p.id} - ${p.name} (${p.phone || 'no phone'})` }))}
                            value={policyForm.patient_id ? { value: policyForm.patient_id, label: (() => { const p = patients.find(x => String(x.id) === policyForm.patient_id); return p ? `${p.id} - ${p.name}` : policyForm.patient_id; })() } : null}
                            onChange={(o: any) => setPolicyForm({ ...policyForm, patient_id: o?.value || '' })}
                            placeholder="Search patient..."
                          />
                        </div>
                        <div className="form-group">
                          <label>Provider *</label>
                          <input type="text" required placeholder="e.g. Star Health" value={policyForm.provider}
                            onChange={e => setPolicyForm({ ...policyForm, provider: e.target.value })} />
                        </div>
                        <div className="form-group">
                          <label>Policy number *</label>
                          <input type="text" required value={policyForm.policy_number}
                            onChange={e => setPolicyForm({ ...policyForm, policy_number: e.target.value })} />
                        </div>
                        <div className="form-group">
                          <label>Member ID</label>
                          <input type="text" value={policyForm.member_id} onChange={e => setPolicyForm({ ...policyForm, member_id: e.target.value })} />
                        </div>
                        <div className="form-group">
                          <label>Plan name</label>
                          <input type="text" value={policyForm.plan_name} onChange={e => setPolicyForm({ ...policyForm, plan_name: e.target.value })} />
                        </div>
                        <div className="form-group">
                          <label>Sum insured (₹)</label>
                          <input type="number" min="0" value={policyForm.sum_insured}
                            onChange={e => setPolicyForm({ ...policyForm, sum_insured: Number(e.target.value) })} />
                        </div>
                        <div className="form-group">
                          <label>TPA</label>
                          <input type="text" value={policyForm.tpa_name} onChange={e => setPolicyForm({ ...policyForm, tpa_name: e.target.value })} />
                        </div>
                        <div className="form-group">
                          <label>TPA contact</label>
                          <input type="text" value={policyForm.tpa_contact} onChange={e => setPolicyForm({ ...policyForm, tpa_contact: e.target.value })} />
                        </div>
                      </div>
                      <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '16px' }}>Save policy</button>
                    </form>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'insurance_policies' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title"><h1>Insurance Policies</h1><p>Policies registered against patients.</p></div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button className="btn btn-secondary" onClick={loadInsurance}><RefreshCw size={16} /> Refresh</button>
                <button className="btn btn-primary" onClick={() => setIsPolicyModalOpen(true)}><PlusCircle size={16} /> Add policy</button>
              </div>
            </div>
            <div className="glass-card">
              <div className="table-container">
                <table>
                  <thead><tr><th>Policy #</th><th>Patient</th><th>Provider</th><th>Plan</th><th>Sum insured</th><th>Valid to</th><th>Status</th></tr></thead>
                  <tbody>
                    {insurancePolicies.map(p => (
                      <tr key={p.id}>
                        <td><b>{p.policy_number}</b></td>
                        <td>{p.patient?.name || `#${p.patient_id}`}</td>
                        <td>{p.provider}</td>
                        <td>{p.plan_name || '-'}</td>
                        <td>₹{p.sum_insured?.toFixed(0)}</td>
                        <td>{p.valid_to ? new Date(p.valid_to).toLocaleDateString() : '-'}</td>
                        <td><span className={`status-badge ${p.is_active ? 'completed' : 'cancelled'}`}>{p.is_active ? 'Active' : 'Inactive'}</span></td>
                      </tr>
                    ))}
                    {insurancePolicies.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No policies registered.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'billing_lab' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title"><h1>Laboratory Billing</h1><p>Raise bills for lab orders that are not yet invoiced.</p></div>
              <button className="btn btn-primary" disabled={selectedBillOrderIds.length === 0} onClick={handleBillSelectedOrders}>
                <Receipt size={16} /> Bill selected ({selectedBillOrderIds.length})
              </button>
            </div>
            <div className="glass-card">
              <div className="table-container">
                <table>
                  <thead><tr><th></th><th>Order</th><th>Patient</th><th>Test</th><th>Ordered</th><th>Status</th><th>Bill</th></tr></thead>
                  <tbody>
                    {labOrders.filter(o => o.status !== 'Cancelled').map(o => (
                      <tr key={o.id}>
                        <td>
                          <input type="checkbox" disabled={!!o.bill_id} checked={selectedBillOrderIds.includes(o.id)}
                            onChange={() => toggleBillSelection(o.id)} />
                        </td>
                        <td>#{o.id}</td>
                        <td>{patients.find(p => p.id === o.patient_id)?.name || `#${o.patient_id}`}</td>
                        <td>{o.test?.test_name || labTestMasters.find(t => t.id === o.test_id)?.test_name}</td>
                        <td>{new Date(o.order_date).toLocaleDateString()}</td>
                        <td><span className={`status-badge ${(o.status || '').replace(/ /g, '-').toLowerCase()}`}>{o.status}</span></td>
                        <td>{o.bill_id ? <span className="status-badge completed">#{o.bill_id}</span> : <span className="status-badge pending">Unbilled</span>}</td>
                      </tr>
                    ))}
                    {labOrders.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No lab orders.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'lab_dashboard' && (() => {
          const isToday = (d?: string | null) => !!d && new Date(d).toDateString() === new Date().toDateString();
          const pending = labOrders.filter(o => o.status === 'Pending');
          const collected = labOrders.filter(o => o.status === 'Sample Collected');
          const testing = labOrders.filter(o => o.status === 'Testing');
          const verifiedToday = labOrders.filter(o => o.status === 'Verified' && isToday(o.verified_at));
          const overdue = labOrders.filter(o =>
            o.due_at && new Date(o.due_at).getTime() < Date.now() && !['Verified', 'Cancelled'].includes(o.status));
          const unbilled = labOrders.filter(o => !o.bill_id && o.status !== 'Cancelled');
          const testName = (o: LabOrder) => o.test?.test_name || labTestMasters.find(t => t.id === o.test_id)?.test_name || `Test #${o.test_id}`;
          const patientName = (o: LabOrder) => patients.find(p => p.id === o.patient_id)?.name || `Patient #${o.patient_id}`;
          const dueText = (o: LabOrder) => {
            if (!o.due_at) return undefined;
            // Only an *open* order can be late; a verified report is not "overdue".
            const late = new Date(o.due_at).getTime() < Date.now() && !['Verified', 'Cancelled'].includes(o.status);
            return `Due ${new Date(o.due_at).toLocaleString()}${late ? ' · OVERDUE' : ''}`;
          };

          const card = (o: LabOrder, actions: any[]) => {
            const late = !!o.due_at && new Date(o.due_at).getTime() < Date.now() && !['Verified', 'Cancelled'].includes(o.status);
            return {
              id: o.id,
              primary: `${testName(o)}`,
              secondary: `${patientName(o)} · order #${o.id}`,
              meta: `${o.priority || 'Routine'}${o.doctor_name ? ` · ${o.doctor_name}` : ''}${o.bill_id ? ' · billed' : ''} · ${dueText(o) || 'no TAT'}`,
              badge: late ? 'Overdue' : o.status,
              badgeTone: late ? 'cancelled' : o.status,
              actions,
            };
          };

          const openSample = (o: LabOrder) => {
            setCollectSampleForm({
              barcode: '', collected_by: currentUser?.username || '',
              sample_type: o.test?.sample_type || 'Blood',
              container_type: o.test?.container_type || '', volume: '', remarks: '', status: 'Collected',
            });
            setSelectedCollectSampleOrder(o);
          };

          return (
            <RoleFlow
              role="Laboratory"
              title="Laboratory — Full Test Flow"
              subtitle="Receive order → collect sample → run test → enter results → verify → report and bill."
              currentUser={currentUser.username}
              headerActions={
                <>
                  <button className="btn btn-secondary" onClick={() => { loadAllData(); loadLabStats(); }}><RefreshCw size={16} /> Refresh</button>
                  <button className="btn btn-primary" onClick={() => setIsLabRegistrationModalOpen(true)}><PlusCircle size={16} /> Register walk-in</button>
                  <button className="btn btn-primary" disabled={selectedBillOrderIds.length === 0} onClick={handleBillSelectedOrders}>
                    <Receipt size={16} /> Bill selected ({selectedBillOrderIds.length})
                  </button>
                </>
              }
              stats={[
                { label: 'Pending collection', value: pending.length, color: 'var(--accent-blue)', icon: <Clock size={24} /> },
                { label: 'In lab', value: collected.length + testing.length, color: 'var(--accent-amber)', icon: <FlaskConical size={24} /> },
                { label: 'Verified today', value: verifiedToday.length, color: 'var(--accent-emerald)', icon: <CheckCircle2 size={24} /> },
                { label: 'Overdue (past TAT)', value: overdue.length, color: 'var(--accent-rose)', icon: <AlertTriangle size={24} /> },
                { label: 'TAT compliance', value: `${labStats?.tat_compliance_percent ?? 100}%`, color: 'var(--accent-violet)', icon: <Activity size={24} /> },
                { label: 'Unbilled orders', value: unbilled.length, color: 'var(--accent-yellow)', icon: <Receipt size={24} /> },
                { label: 'Rejected samples', value: labSamples.filter(s => s.status === 'Rejected').length, color: 'var(--accent-rose)', icon: <X size={24} /> },
                { label: 'Lab revenue today', value: `₹${(labStats?.today_revenue ?? 0).toFixed(0)}`, color: 'var(--accent-sky)', icon: <DollarSign size={24} /> },
              ]}
              steps={[
                {
                  n: 1, title: 'Receive the order', detail: 'Orders arrive from doctors, the front desk or a walk-in.',
                  count: pending.length, tone: pending.length ? 'active' : 'done',
                  action: 'Open orders', onAction: () => setActiveTab('lab_orders'),
                },
                {
                  n: 2, title: 'Collect the sample', detail: 'Barcode the specimen and record who drew it.',
                  count: collected.length, tone: collected.length ? 'active' : 'done',
                  action: 'Collection desk', onAction: () => setActiveTab('lab_samples'),
                },
                {
                  n: 3, title: 'Run the test', detail: 'Specimen received in the lab and being processed.',
                  count: testing.length, tone: testing.length ? 'active' : 'done',
                  action: 'Sample collection', onAction: () => setActiveTab('lab_samples'),
                },
                {
                  n: 4, title: 'Enter results', detail: 'Parameters are pre-filled from the test master.',
                  count: collected.length + testing.length, tone: 'active',
                  action: 'Result entry', onAction: () => setActiveTab('lab_results'),
                },
                {
                  n: 5, title: 'Verify & report', detail: 'Lock the report and publish it to the patient portal.',
                  count: verifiedToday.length, tone: 'done',
                  action: 'Reports', onAction: () => setActiveTab('lab_reports_new'),
                },
                {
                  n: 6, title: 'Bill the tests', detail: 'Raise the lab bill; panels are charged once.',
                  count: unbilled.length, tone: unbilled.length ? 'active' : 'done',
                  action: 'Lab billing', onAction: () => setActiveTab('billing_lab'),
                },
              ]}
              lanes={[
                {
                  key: 'pending', title: 'Pending collection', tone: '#3b82f6',
                  hint: 'Draw the sample and barcode it.',
                  emptyText: 'Nothing waiting',
                  items: pending.map(o => card(o, [
                    { label: 'Collect', tone: 'primary' as const, onClick: () => openSample(o) },
                    { label: 'Cancel', tone: 'danger' as const, onClick: () => handleUpdateLabOrderStatus(o.id, 'Cancelled') },
                    { label: '360', onClick: () => openPatientDetail(o.patient_id) },
                  ])),
                },
                {
                  key: 'collected', title: 'Sample collected', tone: '#f59e0b',
                  hint: 'Enter the results when the analyser is done.',
                  emptyText: 'No collected samples',
                  items: collected.map(o => card(o, [
                    { label: 'Enter results', tone: 'primary' as const, onClick: () => openResultEntry(o) },
                    { label: 'Move to testing', onClick: () => handleUpdateLabOrderStatus(o.id, 'Testing') },
                    { label: '360', onClick: () => openPatientDetail(o.patient_id) },
                  ])),
                },
                {
                  key: 'testing', title: 'Testing / draft', tone: '#8b5cf6',
                  hint: 'Draft saved — verify to publish.',
                  emptyText: 'Nothing in progress',
                  items: testing.map(o => card(o, [
                    { label: 'Verify', tone: 'primary' as const, onClick: () => openResultEntry(o) },
                    { label: '360', onClick: () => openPatientDetail(o.patient_id) },
                  ])),
                },
                {
                  key: 'verified', title: 'Verified today', tone: '#10b981',
                  hint: 'Reports the patient can already see.',
                  emptyText: 'No reports verified yet today',
                  items: verifiedToday.map(o => card(o, [
                    {
                      label: 'Print report', tone: 'primary' as const, onClick: () => {
                        const report = labReports.find(r => r.order_id === o.id);
                        if (report) printLabReport(report);
                        else showToast('Report is still being generated', 'error');
                      },
                    },
                    { label: '360', onClick: () => openPatientDetail(o.patient_id) },
                  ])),
                },
              ]}
            />
          );
        })()}
        {activeTab === 'lab_master' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Lab Test Master</h1>
                <p>Configure tests, multi-parameter panels and reference ranges.</p>
              </div>
              {selectedTestMasterId && (
                <button className="btn btn-secondary" onClick={resetLabTestMasterForm}>Cancel Edit</button>
              )}
            </div>

            <div className="glass-card">
              <h3>{selectedTestMasterId ? `Edit Test #${selectedTestMasterId}` : 'Add New Test / Panel'}</h3>
              <form onSubmit={handleSaveLabTestMaster}>
                <div className="form-grid">
                  <div className="form-group"><label>Test / Panel Code *</label><input type="text" required value={labTestMasterForm.test_code} onChange={e => setLabTestMasterForm({...labTestMasterForm, test_code: e.target.value.toUpperCase()})} /></div>
                  <div className="form-group"><label>Name *</label><input type="text" required value={labTestMasterForm.test_name} onChange={e => setLabTestMasterForm({...labTestMasterForm, test_name: e.target.value})} /></div>
                  <div className="form-group">
                    <label>Category</label>
                    <select value={labTestMasterForm.category} onChange={e => setLabTestMasterForm({...labTestMasterForm, category: e.target.value})}>
                      {['Pathology','Biochemistry','Haematology','Microbiology','Serology','Radiology','Histopathology','Molecular'].map(c => <option key={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="form-group"><label>Department</label><input type="text" value={labTestMasterForm.department} onChange={e => setLabTestMasterForm({...labTestMasterForm, department: e.target.value})} /></div>
                  <div className="form-group"><label>Sample Type</label><input type="text" value={labTestMasterForm.sample_type} onChange={e => setLabTestMasterForm({...labTestMasterForm, sample_type: e.target.value})} placeholder="Blood, Urine..." /></div>
                  <div className="form-group"><label>Container</label><input type="text" value={labTestMasterForm.container_type} onChange={e => setLabTestMasterForm({...labTestMasterForm, container_type: e.target.value})} placeholder="EDTA Tube" /></div>
                  <div className="form-group"><label>Method</label><input type="text" value={labTestMasterForm.method} onChange={e => setLabTestMasterForm({...labTestMasterForm, method: e.target.value})} placeholder="Photometry" /></div>
                  <div className="form-group"><label>Price (₹) *</label><input type="number" min="0" step="0.01" required value={labTestMasterForm.price} onChange={e => setLabTestMasterForm({...labTestMasterForm, price: Number(e.target.value)})} /></div>
                  <div className="form-group"><label>TAT (Hours)</label><input type="number" min="0" value={labTestMasterForm.tat_hours} onChange={e => setLabTestMasterForm({...labTestMasterForm, tat_hours: Number(e.target.value)})} /></div>
                  <div className="form-group" style={{ display: 'flex', alignItems: 'flex-end', gap: '16px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
                      <input type="checkbox" checked={labTestMasterForm.is_panel} onChange={e => setLabTestMasterForm({...labTestMasterForm, is_panel: e.target.checked})} /> Is a panel / profile
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
                      <input type="checkbox" checked={labTestMasterForm.is_active} onChange={e => setLabTestMasterForm({...labTestMasterForm, is_active: e.target.checked})} /> Active
                    </label>
                  </div>
                </div>

                {labTestMasterForm.is_panel ? (
                  <div style={{ marginTop: '16px' }}>
                    <h4>Panel members</h4>
                    <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                      Each member test is ordered and reported separately; the panel price is charged once.
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '8px', maxHeight: '220px', overflowY: 'auto', padding: '10px', border: '1px solid var(--border)', borderRadius: '8px' }}>
                      {labTestMasters.filter(t => !t.is_panel && t.id !== selectedTestMasterId).map(t => (
                        <label key={t.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                          <input
                            type="checkbox"
                            checked={labPanelTestIds.includes(t.id)}
                            onChange={e => setLabPanelTestIds(prev => e.target.checked ? [...prev, t.id] : prev.filter(id => id !== t.id))}
                          />
                          {t.test_name} <span style={{ color: 'var(--text-muted)' }}>({t.test_code})</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div style={{ marginTop: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h4 style={{ margin: 0 }}>Parameters &amp; reference ranges</h4>
                      <button type="button" className="btn btn-secondary" onClick={addLabParamRow}><Plus size={16} /> Add Parameter</button>
                    </div>
                    <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                      Parameters pre-fill the result-entry sheet and drive automatic High/Low/Critical flagging.
                    </p>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ minWidth: '1100px' }}>
                        <thead>
                          <tr>
                            <th>Parameter</th><th>Type</th><th>Unit</th><th>Range (any)</th>
                            <th>Male</th><th>Female</th><th>Child</th><th>Crit Low</th><th>Crit High</th><th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {labParamRows.map((row, index) => (
                            <tr key={index}>
                              <td><input type="text" value={row.name || ''} onChange={e => updateLabParamRow(index, { name: e.target.value })} placeholder="e.g. Haemoglobin" /></td>
                              <td>
                                <select value={row.data_type || 'Numeric'} onChange={e => updateLabParamRow(index, { data_type: e.target.value })}>
                                  <option>Numeric</option><option>Text</option><option>Options</option>
                                </select>
                              </td>
                              <td><input type="text" style={{ width: '80px' }} value={row.unit || ''} onChange={e => updateLabParamRow(index, { unit: e.target.value })} /></td>
                              <td><input type="text" style={{ width: '110px' }} value={row.reference_range || ''} onChange={e => updateLabParamRow(index, { reference_range: e.target.value })} placeholder="13 - 17" /></td>
                              <td><input type="text" style={{ width: '100px' }} value={row.normal_range_male || ''} onChange={e => updateLabParamRow(index, { normal_range_male: e.target.value })} /></td>
                              <td><input type="text" style={{ width: '100px' }} value={row.normal_range_female || ''} onChange={e => updateLabParamRow(index, { normal_range_female: e.target.value })} /></td>
                              <td><input type="text" style={{ width: '100px' }} value={row.normal_range_child || ''} onChange={e => updateLabParamRow(index, { normal_range_child: e.target.value })} /></td>
                              <td><input type="number" style={{ width: '80px' }} value={row.critical_low ?? ''} onChange={e => updateLabParamRow(index, { critical_low: e.target.value === '' ? null : Number(e.target.value) })} /></td>
                              <td><input type="number" style={{ width: '80px' }} value={row.critical_high ?? ''} onChange={e => updateLabParamRow(index, { critical_high: e.target.value === '' ? null : Number(e.target.value) })} /></td>
                              <td><button type="button" className="btn btn-danger" style={{ padding: '4px 8px' }} onClick={() => removeLabParamRow(index)}><Trash2 size={14} /></button></td>
                            </tr>
                          ))}
                          {labParamRows.length === 0 && (
                            <tr><td colSpan={10} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No parameters yet — the test will use a single free-text result.</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                <button type="submit" className="btn btn-primary" style={{ marginTop: '15px' }}>
                  {selectedTestMasterId ? <><Edit size={18} /> Update</> : <><PlusCircle size={18} /> Create</>}
                </button>
              </form>
            </div>

            <div className="glass-card" style={{ marginTop: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', gap: '12px' }}>
                <h3 style={{ margin: 0 }}>Catalogue</h3>
                <input
                  type="text"
                  className="search-bar"
                  style={{ maxWidth: '320px' }}
                  placeholder="Filter by name, code or category..."
                  value={labMasterFilter}
                  onChange={e => setLabMasterFilter(e.target.value)}
                />
              </div>
              <div className="table-container">
                <table>
                  <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Category</th><th>Params</th><th>Sample</th><th>Price</th><th>TAT</th><th>Status</th><th>Actions</th></tr></thead>
                  <tbody>
                    {labTestMasters
                      .filter(t => {
                        const q = labMasterFilter.toLowerCase();
                        return !q || t.test_name.toLowerCase().includes(q) || t.test_code.toLowerCase().includes(q) || (t.category || '').toLowerCase().includes(q);
                      })
                      .map(t => (
                        <tr key={t.id} style={{ opacity: t.is_active ? 1 : 0.5 }}>
                          <td>{t.test_code}</td>
                          <td>{t.test_name}</td>
                          <td>{t.is_panel ? '🧩 Panel' : 'Test'}</td>
                          <td>{t.category || '-'}</td>
                          <td>{t.is_panel ? '-' : (t.parameters?.length || 0)}</td>
                          <td>{t.sample_type || '-'}</td>
                          <td>₹{t.price}</td>
                          <td>{t.tat_hours}h</td>
                          <td><span className={`status-badge ${t.is_active ? 'completed' : 'cancelled'}`}>{t.is_active ? 'Active' : 'Inactive'}</span></td>
                          <td>
                            <div style={{ display: 'flex', gap: '5px' }}>
                              <button className="btn btn-secondary" style={{padding: '4px 8px'}} title="Edit" onClick={() => handleEditLabTestMaster(t)}><Edit size={14}/></button>
                              <button className="btn btn-secondary" style={{padding: '4px 8px'}} title={t.is_active ? 'Deactivate' : 'Activate'} onClick={() => handleToggleLabTestActive(t)}>
                                {t.is_active ? <X size={14}/> : <CheckCircle size={14}/>}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    {labTestMasters.length === 0 && <tr><td colSpan={10} style={{ textAlign: 'center', color: 'var(--text-muted)'}}>No lab tests configured.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'lab_orders' && (
          <div className="no-print">
            <LabPatientHeader
              patients={patients}
              selectedId={selectedGlobalLabPatientId}
              onChange={setSelectedGlobalLabPatientId}
              labOrders={labOrders}
              ipAdmissions={ipAdmissions}
            />

            <div className="header">
              <div className="header-title"><h1>Lab Orders Workflow</h1><p>Collect samples, enter results and raise lab bills.</p></div>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button className="btn btn-primary" onClick={() => setIsLabRegistrationModalOpen(true)}>+ Register Walk-in</button>
                <button className="btn btn-secondary" onClick={exportLabOrdersCsv}><Download size={16} /> CSV</button>
                <button className="btn btn-primary" disabled={selectedBillOrderIds.length === 0} onClick={handleBillSelectedOrders}>
                  <Receipt size={16} /> Bill selected ({selectedBillOrderIds.length})
                </button>
                <input
                  type="text"
                  className="search-bar"
                  placeholder="Search patient, doctor, test or ID..."
                  value={labSearchQuery}
                  onChange={e => setLabSearchQuery(e.target.value)}
                />
                <select className="search-bar" value={labFilterStatus} onChange={e => setLabFilterStatus(e.target.value)}>
                  <option value="All">All Statuses</option>
                  {['Pending','Sample Collected','Testing','Completed','Verified','Cancelled'].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <select className="search-bar" value={labFilterPriority} onChange={e => setLabFilterPriority(e.target.value)}>
                  <option value="All">All Priorities</option>
                  {['Routine','Urgent','STAT'].map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
                  <input type="checkbox" checked={labOverdueOnly} onChange={e => setLabOverdueOnly(e.target.checked)} /> Overdue only
                </label>
              </div>
            </div>

            <div className="glass-card">
              <div className="table-container">
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ minWidth: '1300px' }}>
                    <thead>
                      <tr>
                        <th></th><th>Order</th><th>Patient</th><th>Age/Gen</th><th>Mobile</th>
                        <th>Doctor</th><th>Test</th><th>Priority</th><th>Due</th><th>Billing</th><th>Status</th><th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {labOrders
                        .filter(o => {
                          if (selectedGlobalLabPatientId && o.patient_id !== selectedGlobalLabPatientId) return false;
                          const p = patients.find(pat => pat.id === o.patient_id);
                          const haystack = [
                            p?.name || '', o.doctor_name || '',
                            o.test?.test_name || labTestMasters.find(t => t.id === o.test_id)?.test_name || '',
                            String(o.id), String(o.patient_id),
                          ].join(' ').toLowerCase();
                          if (labSearchQuery && !haystack.includes(labSearchQuery.toLowerCase())) return false;
                          if (labFilterStatus !== 'All' && o.status !== labFilterStatus) return false;
                          if (labFilterPriority !== 'All' && (o.priority || 'Routine') !== labFilterPriority) return false;
                          if (labOverdueOnly && !(o.due_at && new Date(o.due_at).getTime() < Date.now() && o.status !== 'Verified' && o.status !== 'Cancelled')) return false;
                          return true;
                        })
                        .map(o => {
                          const p = patients.find(pat => pat.id === o.patient_id);
                          const t = o.test || labTestMasters.find(test => test.id === o.test_id);
                          const overdue = !!o.due_at && new Date(o.due_at).getTime() < Date.now() && o.status !== 'Verified' && o.status !== 'Cancelled';
                          const locked = o.status === 'Verified' || o.status === 'Cancelled';
                          return (
                            <tr key={o.id}>
                              <td>
                                <input
                                  type="checkbox"
                                  disabled={!!o.bill_id}
                                  checked={selectedBillOrderIds.includes(o.id)}
                                  onChange={() => toggleBillSelection(o.id)}
                                  title={o.bill_id ? 'Already billed' : 'Select for billing'}
                                />
                              </td>
                              <td>#{o.id}</td>
                              <td>{p?.name || `#${o.patient_id}`}</td>
                              <td>{p?.age} / {p?.gender?.charAt(0)}</td>
                              <td>{p?.phone || '-'}</td>
                              <td>{o.doctor_name || 'N/A'}</td>
                              <td>{t?.test_name}</td>
                              <td><span style={{ color: (o.priority || 'Routine') === 'Routine' ? 'inherit' : 'var(--danger)' }}>{o.priority || 'Routine'}</span></td>
                              <td style={{ color: overdue ? 'var(--danger)' : 'inherit', fontWeight: overdue ? 700 : 400 }}>
                                {o.due_at ? new Date(o.due_at).toLocaleString() : '-'}
                              </td>
                              <td>{o.bill_id ? <span className="status-badge completed">Billed</span> : <span className="status-badge pending">Unbilled</span>}</td>
                              <td><span className={`status-badge ${(o.status || '').replace(/ /g, '-').toLowerCase()}`}>{o.status}</span></td>
                              <td>
                                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                                  <button className="btn btn-secondary" style={{padding: '5px 8px'}} onClick={() => setSelectedViewOrder(o)} title="View"><Eye size={16}/></button>
                                  {!locked && (
                                    <button className="btn btn-secondary" style={{padding: '5px 8px'}} title="Edit" onClick={() => {
                                      setEditOrderForm({ priority: o.priority || 'Routine', remarks: o.remarks || '' });
                                      setSelectedEditOrder(o);
                                    }}><Edit size={16}/></button>
                                  )}
                                  {o.status === 'Pending' && (
                                    <button className="btn btn-primary" style={{padding: '5px 10px', fontSize: '12px'}} onClick={() => {
                                      setCollectSampleForm({
                                        barcode: '', collected_by: currentUser?.username || '',
                                        sample_type: t?.sample_type || 'Blood',
                                        container_type: t?.container_type || '', volume: '', remarks: '', status: 'Collected'
                                      });
                                      setSelectedCollectSampleOrder(o);
                                    }}>Collect</button>
                                  )}
                                  {(o.status === 'Sample Collected' || o.status === 'Testing') && (
                                    <button className="btn btn-primary" style={{padding: '5px 10px', fontSize: '12px'}} onClick={() => openResultEntry(o)}>Results</button>
                                  )}
                                  {o.status === 'Verified' && (
                                    <button className="btn btn-secondary" style={{padding: '5px 8px'}} title="Print report" onClick={() => {
                                      const report = labReports.find(r => r.order_id === o.id);
                                      if (report) printLabReport(report);
                                      else { setActiveTab('lab_reports_new'); showToast('Open Reports to print this order', 'error'); }
                                    }}><Printer size={16}/></button>
                                  )}
                                  {!locked && o.status !== 'Cancelled' && (
                                    <button className="btn btn-danger" style={{padding: '5px 8px', fontSize: '11px'}} title="Cancel order" onClick={() => {
                                      if (window.confirm(`Cancel lab order #${o.id}?`)) handleUpdateLabOrderStatus(o.id, 'Cancelled');
                                    }}>Cancel</button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      {labOrders.length === 0 && (
                        <tr><td colSpan={12} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No lab orders found.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

          </div>
        )}

        {/* Laboratory modals live outside the per-tab blocks so they can be
            opened from Orders, Sample Collection and Result Entry alike. */}
        {['lab_orders', 'lab_samples', 'lab_results', 'lab_dashboard'].includes(activeTab) && (
          <>
            {/* VIEW MODAL */}
            {selectedViewOrder && (
              <div className="modal-overlay">
                <div className="modal-content" style={{maxWidth: '640px'}}>
                  <div className="modal-header">
                    <h2>Order Details #{selectedViewOrder.id}</h2>
                    <button className="close-btn" onClick={() => setSelectedViewOrder(null)}><X size={20}/></button>
                  </div>
                  <div className="modal-body">
                    <p><strong>Patient:</strong> {patients.find(p=>p.id===selectedViewOrder.patient_id)?.name}</p>
                    <p><strong>Doctor:</strong> {selectedViewOrder.doctor_name || 'N/A'}</p>
                    <p><strong>Test:</strong> {selectedViewOrder.test?.test_name || labTestMasters.find(t=>t.id===selectedViewOrder.test_id)?.test_name}</p>
                    <p><strong>Priority:</strong> {selectedViewOrder.priority || 'Routine'}</p>
                    <p><strong>TAT:</strong> {selectedViewOrder.tat_hours ?? '-'} h &nbsp;|&nbsp; <strong>Due:</strong> {selectedViewOrder.due_at ? new Date(selectedViewOrder.due_at).toLocaleString() : '-'}</p>
                    <p><strong>Billed:</strong> {selectedViewOrder.bill_id ? `Yes (bill #${selectedViewOrder.bill_id})` : 'No'}</p>
                    <p><strong>Remarks:</strong> {selectedViewOrder.remarks || 'None'}</p>
                    <div style={{ marginTop: '20px', padding: '10px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                      <h4>Timeline</h4>
                      <p>➤ Ordered ( {new Date(selectedViewOrder.order_date).toLocaleString()} )</p>
                      {selectedViewOrder.sample_collected_at && <p>➤ Sample collected ({new Date(selectedViewOrder.sample_collected_at).toLocaleString()})</p>}
                      {selectedViewOrder.result_entered_at && <p>➤ Result entered ({new Date(selectedViewOrder.result_entered_at).toLocaleString()})</p>}
                      {selectedViewOrder.verified_at && <p>➤ Verified by {selectedViewOrder.verified_by || '-'} ({new Date(selectedViewOrder.verified_at).toLocaleString()})</p>}
                    </div>
                    {labSamples.filter(s => s.order_id === selectedViewOrder.id).length > 0 && (
                      <div style={{ marginTop: '16px' }}>
                        <h4>Samples</h4>
                        {labSamples.filter(s => s.order_id === selectedViewOrder.id).map(s => (
                          <p key={s.id} style={{ margin: '4px 0', fontSize: '13px' }}>
                            #{s.id} — {s.sample_type} — <span className={`status-badge ${(s.status||'').replace(/ /g,'-').toLowerCase()}`}>{s.status}</span>
                            {s.barcode ? ` — barcode ${s.barcode}` : ''}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* EDIT MODAL */}
            {selectedEditOrder && (
              <div className="modal-overlay">
                <div className="modal-content" style={{maxWidth: '420px'}}>
                  <div className="modal-header">
                    <h2>Edit Order #{selectedEditOrder.id}</h2>
                    <button className="close-btn" onClick={() => setSelectedEditOrder(null)}><X size={20}/></button>
                  </div>
                  <div className="modal-body">
                    <div className="form-group">
                      <label>Priority</label>
                      <select value={editOrderForm.priority} onChange={e => setEditOrderForm({...editOrderForm, priority: e.target.value})}>
                        <option>Routine</option><option>Urgent</option><option>STAT</option>
                      </select>
                    </div>
                    <div className="form-group" style={{marginTop: '15px'}}>
                      <label>Remarks</label>
                      <textarea rows={3} value={editOrderForm.remarks} onChange={e => setEditOrderForm({...editOrderForm, remarks: e.target.value})}></textarea>
                    </div>
                    <button className="btn btn-primary" style={{marginTop: '20px', width: '100%'}} onClick={handleSaveEditOrder}>Save Changes</button>
                  </div>
                </div>
              </div>
            )}

            {/* COLLECT SAMPLE MODAL */}
            {selectedCollectSampleOrder && (
              <div className="modal-overlay">
                <div className="modal-content" style={{maxWidth: '640px'}}>
                  <div className="modal-header">
                    <h2>Collect Sample — Order #{selectedCollectSampleOrder.id}</h2>
                    <button className="close-btn" onClick={() => setSelectedCollectSampleOrder(null)}><X size={20}/></button>
                  </div>
                  <div className="modal-body">
                    <div className="form-grid">
                      <div className="form-group">
                        <label>Sample Type *</label>
                        <input type="text" value={collectSampleForm.sample_type} onChange={e => setCollectSampleForm({...collectSampleForm, sample_type: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>Container Type</label>
                        <input type="text" placeholder="e.g. EDTA Tube, Plain Vial" value={collectSampleForm.container_type} onChange={e => setCollectSampleForm({...collectSampleForm, container_type: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>Barcode</label>
                        <input type="text" placeholder="Leave blank to auto-generate" value={collectSampleForm.barcode} onChange={e => setCollectSampleForm({...collectSampleForm, barcode: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>Volume</label>
                        <input type="text" placeholder="e.g. 2 mL" value={collectSampleForm.volume} onChange={e => setCollectSampleForm({...collectSampleForm, volume: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>Collected By</label>
                        <input type="text" value={collectSampleForm.collected_by} onChange={e => setCollectSampleForm({...collectSampleForm, collected_by: e.target.value})} />
                      </div>
                      <div className="form-group">
                        <label>Status</label>
                        <select value={collectSampleForm.status} onChange={e => setCollectSampleForm({...collectSampleForm, status: e.target.value})}>
                          <option value="Collected">Collected</option>
                          <option value="Received">Received in lab</option>
                          <option value="Pending">Pending</option>
                        </select>
                      </div>
                      <div className="form-group" style={{gridColumn: '1 / -1'}}>
                        <label>Remarks / Instructions</label>
                        <textarea rows={2} style={{width: '100%'}} value={collectSampleForm.remarks} onChange={e => setCollectSampleForm({...collectSampleForm, remarks: e.target.value})} />
                      </div>
                    </div>
                    <button className="btn btn-primary" style={{marginTop: '20px', width: '100%'}} onClick={handleSaveCollectSample}>Save and Mark as Collected</button>
                  </div>
                </div>
              </div>
            )}

            {/* LAB WALK-IN REGISTRATION MODAL */}
            {isLabRegistrationModalOpen && (
              <div className="modal-overlay">
                <div className="modal-content" style={{maxWidth: '800px', width: '90%'}}>
                  <div className="modal-header">
                    <h2>Register Walk-in Patient</h2>
                    <button className="close-btn" onClick={() => setIsLabRegistrationModalOpen(false)}><X size={20}/></button>
                  </div>
                  <div className="modal-body">
                    <form onSubmit={handleLabWalkinRegistration}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
                        <div className="form-group">
                          <label>Patient Full Name *</label>
                          <input type="text" value={patientForm.name} onChange={e => setPatientForm({ ...patientForm, name: e.target.value })} required />
                        </div>
                        <div className="form-group">
                          <label>Age *</label>
                          <input type="number" value={patientForm.age || ''} onChange={e => setPatientForm({ ...patientForm, age: Number(e.target.value) })} required />
                        </div>
                        <div className="form-group">
                          <label>Gender *</label>
                          <select value={patientForm.gender} onChange={e => setPatientForm({ ...patientForm, gender: e.target.value })}>
                            <option>Male</option><option>Female</option><option>Other</option>
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Phone Number *</label>
                          <input type="text" value={patientForm.phone} onChange={e => setPatientForm({ ...patientForm, phone: e.target.value })} required />
                        </div>
                        <div className="form-group">
                          <label>Blood Group</label>
                          <select value={patientForm.blood_group} onChange={e => setPatientForm({ ...patientForm, blood_group: e.target.value })}>
                            <option value="">--</option>
                            <option>A+</option><option>A-</option><option>B+</option><option>B-</option>
                            <option>AB+</option><option>AB-</option><option>O+</option><option>O-</option>
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Referred By</label>
                          <input type="text" value={patientForm.referral_doctor} onChange={e => setPatientForm({ ...patientForm, referral_doctor: e.target.value })} />
                        </div>
                        <div className="form-group" style={{ gridColumn: 'span 3' }}>
                          <label>Address</label>
                          <input type="text" value={patientForm.address} onChange={e => setPatientForm({ ...patientForm, address: e.target.value })} />
                        </div>
                        <div className="form-group" style={{ gridColumn: 'span 3', display: 'flex', justifyContent: 'flex-end', marginTop: '20px' }}>
                          <button type="submit" className="btn btn-primary" style={{ padding: '10px 24px' }}>Register &amp; Continue to Order</button>
                        </div>
                      </div>
                    </form>
                  </div>
                </div>
              </div>
            )}

            {/* DIRECT LAB ORDER MODAL (multi-test / panel aware) */}
            {isLabOrderModalOpen && (
              <div className="modal-overlay">
                <div className="modal-content" style={{maxWidth: '720px'}}>
                  <div className="modal-header">
                    <h2>New Lab Order</h2>
                    <button className="close-btn" onClick={() => { setIsLabOrderModalOpen(false); setLabDirectOrderPatientId(null); }}><X size={20}/></button>
                  </div>
                  <div className="modal-body">
                    <div style={{ background: 'rgba(59, 130, 246, 0.1)', padding: '15px', borderRadius: '8px', marginBottom: '20px', borderLeft: '4px solid #3b82f6' }}>
                      <p style={{ margin: 0, fontWeight: 'bold' }}>
                        Patient ID: {labDirectOrderPatientId}
                        {patients.find(p => p.id === labDirectOrderPatientId) ? ` — ${patients.find(p => p.id === labDirectOrderPatientId)?.name}` : ''}
                      </p>
                      <p style={{ margin: '5px 0 0 0', color: 'var(--text-muted)', fontSize: '14px' }}>Select one or more tests, or a panel. Panels expand into their member tests.</p>
                    </div>
                    <form onSubmit={handleCreateDirectLabOrders}>
                      <div className="form-group">
                        <label>Tests / Panels *</label>
                        <div style={{ maxHeight: '260px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '8px', padding: '10px' }}>
                          {labTestMasters.filter(t => t.is_active).map(t => (
                            <label key={t.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '5px 0', fontSize: '13px' }}>
                              <input
                                type="checkbox"
                                checked={labDirectOrderForm.test_ids.includes(t.id)}
                                onChange={e => setLabDirectOrderForm({
                                  ...labDirectOrderForm,
                                  test_ids: e.target.checked
                                    ? [...labDirectOrderForm.test_ids, t.id]
                                    : labDirectOrderForm.test_ids.filter(id => id !== t.id),
                                })}
                              />
                              {t.is_panel ? '🧩 ' : ''}{t.test_name} <span style={{ color: 'var(--text-muted)' }}>({t.test_code}) — ₹{t.price}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                      <div className="form-grid" style={{ marginTop: '12px' }}>
                        <div className="form-group">
                          <label>Referring Doctor</label>
                          <input type="text" value={labDirectOrderForm.referring_doctor} onChange={e => setLabDirectOrderForm({ ...labDirectOrderForm, referring_doctor: e.target.value })} />
                        </div>
                        <div className="form-group">
                          <label>Priority</label>
                          <select value={labDirectOrderForm.priority} onChange={e => setLabDirectOrderForm({ ...labDirectOrderForm, priority: e.target.value })}>
                            <option>Routine</option><option>Urgent</option><option>STAT</option>
                          </select>
                        </div>
                      </div>
                      <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '20px' }}>Create Lab Order(s)</button>
                    </form>
                  </div>
                </div>
              </div>
            )}

            {/* RESULT ENTRY MODAL */}
            {selectedResultEntryOrder && (
              <div className="modal-overlay">
                <div className="modal-content" style={{maxWidth: '1000px', width: '95%'}}>
                  <div className="modal-header">
                    <h2>Enter Results — Order #{selectedResultEntryOrder.id}</h2>
                    <button className="close-btn" onClick={() => setSelectedResultEntryOrder(null)}><X size={20}/></button>
                  </div>
                  <div className="modal-body">
                    <div style={{ background: 'var(--bg-card-hover)', padding: '15px', borderRadius: '8px', marginBottom: '20px', border: '1px solid var(--border)' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
                        <div><small>Patient</small><br/><b>{patients.find(p => p.id === selectedResultEntryOrder.patient_id)?.name}</b></div>
                        <div><small>Test</small><br/><b>{selectedResultEntryOrder.test?.test_name || labTestMasters.find(t => t.id === selectedResultEntryOrder.test_id)?.test_name}</b></div>
                        <div><small>Doctor</small><br/><b>{selectedResultEntryOrder.doctor_name || 'Walk-in'}</b></div>
                        <div><small>Status</small><br/><span className={`status-badge ${(selectedResultEntryOrder.status || '').replace(/ /g,'-').toLowerCase()}`}>{selectedResultEntryOrder.status}</span></div>
                      </div>
                    </div>

                    <div style={{ overflowX: 'auto' }}>
                      <table style={{marginBottom: '20px', minWidth: '900px'}}>
                        <thead><tr><th>Parameter</th><th>Result</th><th>Unit</th><th>Reference Range</th><th>Flag</th><th>Remarks</th><th></th></tr></thead>
                        <tbody>
                          {resultEntryForm.map((row, index) => {
                            const abnormal = isFlagAbnormal(row.flag);
                            return (
                              <tr key={index} style={abnormal ? { background: 'rgba(239,68,68,0.08)' } : undefined}>
                                <td><input type="text" placeholder="e.g. WBC" value={row.parameter} onChange={e => setResultEntryForm(prev => prev.map((r, i) => i === index ? { ...r, parameter: e.target.value } : r))} /></td>
                                <td>
                                  <input
                                    type="text"
                                    value={row.result}
                                    style={abnormal ? { color: 'var(--danger)', fontWeight: 700 } : undefined}
                                    onChange={e => {
                                      const value = e.target.value;
                                      setResultEntryForm(prev => prev.map((r, i) => i === index ? { ...r, result: value, flag: computeFlag(value, r.range, r.critical_low, r.critical_high) } : r));
                                    }}
                                  />
                                </td>
                                <td><input type="text" value={row.unit} style={{width: '80px'}} onChange={e => setResultEntryForm(prev => prev.map((r, i) => i === index ? { ...r, unit: e.target.value } : r))} /></td>
                                <td>
                                  <input
                                    type="text"
                                    value={row.range}
                                    onChange={e => {
                                      const value = e.target.value;
                                      setResultEntryForm(prev => prev.map((r, i) => i === index ? { ...r, range: value, flag: computeFlag(r.result, value, r.critical_low, r.critical_high) } : r));
                                    }}
                                  />
                                </td>
                                <td>
                                  <select
                                    value={row.flag}
                                    style={abnormal ? { color: 'var(--danger)', fontWeight: 700 } : undefined}
                                    onChange={e => setResultEntryForm(prev => prev.map((r, i) => i === index ? { ...r, flag: e.target.value } : r))}
                                  >
                                    {['Normal','High','Low','Critical High','Critical Low','Abnormal'].map(f => <option key={f}>{f}</option>)}
                                  </select>
                                </td>
                                <td><input type="text" value={row.remarks || ''} onChange={e => setResultEntryForm(prev => prev.map((r, i) => i === index ? { ...r, remarks: e.target.value } : r))} /></td>
                                <td>
                                  <button className="btn btn-danger" style={{ padding: '4px 8px' }} onClick={() => setResultEntryForm(prev => prev.filter((_, i) => i !== index))}><Trash2 size={14}/></button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    <div style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
                      <button className="btn btn-secondary" onClick={() => setResultEntryForm(prev => [...prev, { parameter: '', result: '', unit: '', range: '', flag: 'Normal', remarks: '' }])}>+ Add Row</button>
                      <button className="btn btn-secondary" onClick={() => selectedResultEntryOrder && setResultEntryForm(buildResultRows(selectedResultEntryOrder))}>Reset to template</button>
                    </div>

                    <div className="form-group">
                      <label>Interpretation / Clinical comment</label>
                      <textarea rows={2} style={{ width: '100%' }} value={resultInterpretation} onChange={e => setResultInterpretation(e.target.value)} />
                    </div>

                    {selectedResultEntryOrder.status === 'Verified' ? (
                      <div style={{ marginTop: '20px', padding: '15px', background: '#dcfce3', color: '#166534', borderRadius: '8px', textAlign: 'center', fontWeight: 'bold' }}>
                        This report is verified and locked. Duplicate reports and edits are not allowed.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '15px', marginTop: '20px' }}>
                        <button className="btn btn-secondary" style={{flex: 1}} onClick={() => handleSaveResultEntry(false)}><Save size={16}/> Save Draft</button>
                        <button className="btn btn-primary" style={{flex: 1}} onClick={() => handleSaveResultEntry(true)}><CheckCircle2 size={16}/> Verify &amp; Generate Report</button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === 'lab_samples' && (
          <div className="no-print">
            <LabPatientHeader
              patients={patients}
              selectedId={selectedGlobalLabPatientId}
              onChange={setSelectedGlobalLabPatientId}
              labOrders={labOrders}
              ipAdmissions={ipAdmissions}
            />
            <div className="header">
              <div className="header-title"><h1>Sample Collection</h1><p>Specimen tracking with barcodes and rejection reasons.</p></div>
            </div>
            <div className="glass-card">
              <div className="table-container">
                <table>
                  <thead><tr><th>Sample</th><th>Order</th><th>Patient</th><th>Type</th><th>Barcode</th><th>Collected</th><th>By</th><th>Status</th><th>Action</th></tr></thead>
                  <tbody>
                    {labSamples
                      .filter(s => !selectedGlobalLabPatientId || labOrders.find(o => o.id === s.order_id)?.patient_id === selectedGlobalLabPatientId)
                      .map(s => {
                        const order = labOrders.find(o => o.id === s.order_id);
                        return (
                          <tr key={s.id}>
                            <td>#{s.id}</td>
                            <td>#{s.order_id}</td>
                            <td>{patients.find(p => p.id === order?.patient_id)?.name || '-'}</td>
                            <td>{s.sample_type}</td>
                            <td><code style={{ fontSize: '11px' }}>{s.barcode || '-'}</code></td>
                            <td>{s.collection_date ? new Date(s.collection_date).toLocaleString() : '-'}</td>
                            <td>{s.collected_by || '-'}</td>
                            <td><span className={`status-badge ${(s.status || '').replace(/ /g, '-').toLowerCase()}`}>{s.status}</span></td>
                            <td>
                              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                {s.status === 'Pending' && <button className="btn btn-primary" style={{padding: '5px 10px'}} onClick={() => handleUpdateLabSampleStatus(s.id, 'Collected')}>Mark Collected</button>}
                                {s.status === 'Collected' && <button className="btn btn-secondary" style={{padding: '5px 10px'}} onClick={() => handleUpdateLabSampleStatus(s.id, 'Received')}>Receive</button>}
                                {s.status !== 'Rejected' && <button className="btn btn-danger" style={{padding: '5px 10px'}} onClick={() => handleUpdateLabSampleStatus(s.id, 'Rejected')}>Reject</button>}
                                {s.status === 'Rejected' && <button className="btn btn-secondary" style={{padding: '5px 10px'}} onClick={() => handleUpdateLabSampleStatus(s.id, 'Recollected')}>Recollect</button>}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    {labSamples.length === 0 && <tr><td colSpan={9} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No samples collected yet.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'lab_results' && (
          <div className="no-print">
            <LabPatientHeader
              patients={patients}
              selectedId={selectedGlobalLabPatientId}
              onChange={setSelectedGlobalLabPatientId}
              labOrders={labOrders}
              ipAdmissions={ipAdmissions}
            />
            <div className="header">
              <div className="header-title"><h1>Result Entry</h1><p>Orders awaiting results. Parameters are pre-filled from the test master.</p></div>
            </div>
            <div className="glass-card">
              <div className="table-container">
                <table>
                  <thead><tr><th>Order</th><th>Patient</th><th>Test</th><th>Priority</th><th>Due</th><th>Status</th><th>Action</th></tr></thead>
                  <tbody>
                    {labOrders
                      .filter(o => ['Sample Collected', 'Testing'].includes(o.status))
                      .filter(o => !selectedGlobalLabPatientId || o.patient_id === selectedGlobalLabPatientId)
                      .map(o => {
                        const test = o.test || labTestMasters.find(t => t.id === o.test_id);
                        const overdue = !!o.due_at && new Date(o.due_at).getTime() < Date.now();
                        return (
                          <tr key={o.id}>
                            <td>#{o.id}</td>
                            <td>{patients.find(p => p.id === o.patient_id)?.name}</td>
                            <td>{test?.test_name}</td>
                            <td><span style={{ color: (o.priority || 'Routine') === 'Routine' ? 'inherit' : 'var(--danger)' }}>{o.priority || 'Routine'}</span></td>
                            <td style={{ color: overdue ? 'var(--danger)' : 'inherit', fontWeight: overdue ? 700 : 400 }}>{o.due_at ? new Date(o.due_at).toLocaleString() : '-'}</td>
                            <td><span className={`status-badge ${(o.status || '').replace(/ /g, '-').toLowerCase()}`}>{o.status}</span></td>
                            <td><button className="btn btn-primary" style={{padding: '6px 12px'}} onClick={() => openResultEntry(o)}>Enter Results</button></td>
                          </tr>
                        );
                      })}
                    {labOrders.filter(o => ['Sample Collected', 'Testing'].includes(o.status)).length === 0 && (
                      <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Nothing awaiting results.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {(activeTab === 'lab_reports_new' || activeTab === 'lab_reports') && (
          <div>
            <div className="header no-print">
              <div className="header-title"><h1>Completed Lab Reports</h1><p>Search, review and print finalized reports.</p></div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
                  <input type="checkbox" checked={labReportFilter === 'abnormal'} onChange={e => setLabReportFilter(e.target.checked ? 'abnormal' : 'all')} /> Abnormal only
                </label>
                <button className="btn btn-secondary" onClick={() => loadAllData()}><RefreshCw size={16} /> Refresh</button>
              </div>
            </div>
            <div className="glass-card">
              <div className="table-container">
                <table>
                  <thead><tr><th>Date</th><th>Report</th><th>Patient</th><th>Test</th><th>Results</th><th>Status</th><th>Action</th></tr></thead>
                  <tbody>
                    {labReports
                      .filter(r => labReportFilter === 'all' || r.is_abnormal)
                      .filter(r => !selectedGlobalLabPatientId || r.patient_id === selectedGlobalLabPatientId)
                      .map(report => {
                        const rows = Array.isArray(report.results_data) ? report.results_data : [];
                        return (
                          <tr key={report.id}>
                            <td>{new Date(report.date_conducted).toLocaleDateString()}</td>
                            <td>#{report.id}{report.order_id ? ` (ord #${report.order_id})` : ''}</td>
                            <td>{patients.find(p=>p.id===report.patient_id)?.name || `#${report.patient_id}`}</td>
                            <td>{report.test_name}</td>
                            <td>
                              {rows.length > 0 ? rows.map((r, i) => (
                                <div key={i} style={{ fontSize: '12px', color: isFlagAbnormal(r.flag) ? 'var(--danger)' : 'inherit', fontWeight: isFlagAbnormal(r.flag) ? 600 : 400 }}>
                                  {r.parameter}: <b>{r.result || '-'}</b> {r.unit} {isFlagAbnormal(r.flag) ? `(${r.flag})` : ''}
                                </div>
                              )) : <div>{report.result_value} {report.units}</div>}
                            </td>
                            <td>
                              <span className={`status-badge ${(report.status || 'Final').toLowerCase()}`}>{report.status || 'Final'}</span>
                              {report.is_abnormal && <span className="status-badge cancelled" style={{ marginLeft: '4px' }}>Abnormal</span>}
                            </td>
                            <td>
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button className="btn btn-secondary" onClick={() => printLabReport(report)}><Printer size={16}/> Print</button>
                                <button className="btn btn-danger" style={{ padding: '5px 8px' }} title="Delete report" onClick={() => handleDeleteLabReport(report.id)}><Trash2 size={14}/></button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    {labReports.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No lab reports yet.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
        {activeTab === 'patient_history' && (
          <div className="no-print">
            <div className="header">
              <div className="header-title">
                <h1>Patient Search & History</h1>
                <p>Search for patients and view their complete medical history, lab reports, and prescriptions.</p>
              </div>
            </div>

            <div className="form-grid">
              <div className="glass-card" style={{ gridColumn: 'span 2' }}>
                <h3 style={{ marginBottom: '16px' }}>Patient Search</h3>
                <div className="form-group" style={{ marginBottom: '16px' }}>
                  <input type="text" placeholder="Search by name, phone, or ID..." className="input-field" value={patientSearch} onChange={e => setPatientSearch(e.target.value)} />
                </div>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Patient ID</th>
                        <th>Name</th>
                        <th>Age/Gender</th>
                        <th>Phone</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {patients.filter(p => p.name.toLowerCase().includes(patientSearch.toLowerCase()) || String(p.id).includes(patientSearch) || (p.phone && p.phone.includes(patientSearch))).slice(0, 10).map(p => (
                        <tr key={p.id}>
                          <td>#{p.id}</td>
                          <td><strong>{p.name}</strong></td>
                          <td>{p.age} / {p.gender}</td>
                          <td>{p.phone || 'N/A'}</td>
                          <td>
                            <div style={{display:'flex', gap:'5px'}}>
                              <button className="btn btn-primary" style={{ padding: '4px 8px', fontSize: '12px' }} onClick={() => openPatientDetail(p.id)}>View 360</button>
                              <button className="btn btn-danger" style={{ padding: '4px 8px', fontSize: '12px' }} onClick={() => handleDeletePatient(p.id)}><Trash2 size={12}/> Delete</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {currentUser?.role === 'Admin' && activeTab === 'users' && (
          <div>
            <div className="header no-print">
              <div className="header-title">
                <h1>User Management</h1>
                <p>Create, manage, and assign roles to users</p>
              </div>
            </div>

            <div className="grid grid-2">
              <div className="glass-card">
                <h3>Create New User</h3>
                <form className="form-container" onSubmit={handleCreateUser}>
                  <div className="form-group">
                    <label>Username</label>
                    <input type="text" value={userForm.username} onChange={e => setUserForm({...userForm, username: e.target.value})} required />
                  </div>
                  <div className="form-group">
                    <label>Password</label>
                    <input type="password" value={userForm.password} onChange={e => setUserForm({...userForm, password: e.target.value})} required />
                  </div>
                  <div className="form-group">
                    <label>Role</label>
                    <select value={userForm.role} onChange={e => setUserForm({...userForm, role: e.target.value})}>
                      <option value="Admin">Admin</option>
                      <option value="Doctor">Doctor</option>
                      <option value="Receptionist">Receptionist</option>
                      <option value="Nurse">Nurse</option>
                      <option value="Pharmacy">Pharmacy</option>
                      <option value="Laboratory">Laboratory</option>
                      <option value="Insurance">Insurance</option>
                      <option value="Billing">Billing</option>
                    </select>
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '0 0 10px' }}>
                    Patient accounts are created by patients themselves from the sign-in screen.
                  </p>
                  <button type="submit" className="btn btn-primary"><Plus size={18} /> Create User</button>
                </form>
              </div>

              <div className="glass-card">
                <h3>System Users</h3>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map(u => (
                        <tr key={u.id}>
                          <td>{u.username}</td>
                          <td>
                            <select
                              value={u.role}
                              disabled={currentUser.id === u.id}
                              title={currentUser.id === u.id ? 'You cannot change your own role' : 'Change role'}
                              onChange={e => handleChangeUserRole(u.id, e.target.value)}
                              style={{ padding: '4px 8px', fontSize: '12px' }}
                            >
                              {['Admin', 'Doctor', 'Nurse', 'Receptionist', 'Pharmacy', 'Laboratory', 'Insurance', 'Billing'].map(r => (
                                <option key={r} value={r}>{r}</option>
                              ))}
                            </select>
                            {currentUser.id === u.id && <small style={{ display: 'block', color: 'var(--text-muted)', fontSize: '11px' }}>you</small>}
                          </td>
                          <td>{u.is_active ? 'Active' : 'Inactive'}</td>
                          <td>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button className="btn btn-secondary" onClick={() => handleAdminResetPassword(u.id, u.username)} style={{padding: '4px 8px', fontSize: '12px'}}>
                                <Shield size={14} /> Reset password
                              </button>
                              {currentUser.id !== u.id && (
                                <button className="btn btn-danger" onClick={() => handleDeleteUser(u.id)} style={{padding: '4px 8px', fontSize: '12px'}}>
                                  <Trash2 size={14} /> Delete
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================== */}
        {/* BILLING MODULE */}
        {/* =========================================================== */}
        {activeTab === 'billing' && (
          <div>
            <div className="header no-print">
              <div className="header-title">
                <h1>Billing Module</h1>
                <p>OP Billing, IP Billing, Payment & GST Invoice</p>
              </div>
            </div>

            {/* Billing Sub-Tabs */}
            <div className="sub-tabs no-print" style={{display:'flex', gap:'8px', padding:'0 24px 16px', flexWrap:'wrap'}}>
              {[{key:'op', label:'OP Billing', icon:'🏥'}, {key:'ip', label:'IP Billing', icon:'🛏️'}, {key:'op_history', label:'OP Bill History', icon:'📋'}, {key:'ip_history', label:'IP Bill History', icon:'📋'}].map(tab => (
                <button key={tab.key} onClick={() => setBillingTab(tab.key)}
                  style={{padding:'8px 18px', borderRadius:'20px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'13px',
                    background: billingTab === tab.key ? 'linear-gradient(135deg, #3b82f6, #2563eb)' : 'var(--bg-input)',
                    color: billingTab === tab.key ? '#fff' : 'var(--accent-slate)', transition:'all 0.3s'}}>
                  {tab.icon} {tab.label}
                </button>
              ))}
            </div>

            {/* OP BILLING FORM */}
            {billingTab === 'op' && (
              <div className="form-grid">
                <div className="glass-card">
                  <h3 style={{marginBottom:'20px', display:'flex', alignItems:'center', gap:'8px'}}><Receipt size={20} color="#3b82f6" /> OP Bill Creation</h3>
                  <form onSubmit={handleCreateOPBill}>
                    <div className="form-grid" style={{gridTemplateColumns:'1fr 1fr', gap:'12px'}}>
                      <div className="form-group">
                        <label>Patient *</label>
                        <Select 
                          styles={selectStyles}
                          options={patients.map(p => ({ value: String(p.id), label: `${p.name} (ID: ${p.id})` }))}
                          value={opBillForm.patient_id ? { value: String(opBillForm.patient_id), label: patients.find(p => String(p.id) === String(opBillForm.patient_id))?.name + ' (ID: ' + opBillForm.patient_id + ')' } : null}
                          onChange={(sel: any) => setOpBillForm({...opBillForm, patient_id: sel ? sel.value : ''})}
                          placeholder="Select Patient"
                          isClearable
                        />
                      </div>
                      <div className="form-group">
                        <label>OP Token (Optional)</label>
                        <select value={opBillForm.token_id} onChange={e => setOpBillForm({...opBillForm, token_id: e.target.value})}>
                          <option value="">Select Token</option>
                          {tokens.filter(t => !opBillForm.patient_id || t.patient_id === Number(opBillForm.patient_id)).map(t => <option key={t.id} value={t.id}>Token #{t.token_number} | {t.date}</option>)}
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Doctor Name</label>
                        <input type="text" value={opBillForm.doctor_name} onChange={e => setOpBillForm({...opBillForm, doctor_name: e.target.value})} placeholder="Dr. Name" />
                      </div>
                      <div className="form-group">
                        <label>Department</label>
                        <input type="text" value={opBillForm.department} onChange={e => setOpBillForm({...opBillForm, department: e.target.value})} placeholder="e.g. Cardiology" />
                      </div>
                    </div>

                    <h4 style={{margin:'16px 0 12px', color:'var(--text-muted)'}}>Charge Breakdown</h4>
                    <div className="form-grid" style={{gridTemplateColumns:'1fr 1fr 1fr', gap:'12px'}}>
                      <div className="form-group">
                        <label>Consultation Fee (₹)</label>
                        <input type="number" min="0" step="0.01" value={opBillForm.consultation_fee} onChange={e => setOpBillForm({...opBillForm, consultation_fee: parseFloat(e.target.value)||0})} />
                      </div>
                      <div className="form-group">
                        <label>Lab Charges (₹)</label>
                        <input type="number" min="0" step="0.01" value={opBillForm.lab_charges} onChange={e => setOpBillForm({...opBillForm, lab_charges: parseFloat(e.target.value)||0})} />
                      </div>
                      <div className="form-group">
                        <label>Pharmacy Charges (₹)</label>
                        <input type="number" min="0" step="0.01" value={opBillForm.pharmacy_charges} onChange={e => setOpBillForm({...opBillForm, pharmacy_charges: parseFloat(e.target.value)||0})} />
                      </div>
                    </div>

                    {/* Other Charges */}
                    <div style={{marginBottom:'16px'}}>
                      <label style={{display:'block', marginBottom:'8px', fontSize:'13px', color:'var(--text-muted)'}}>Other Charges</label>
                      {opOtherCharges.map((c, i) => (
                        <div key={i} style={{display:'flex', gap:'8px', alignItems:'center', marginBottom:'6px'}}>
                          <span style={{flex:1, padding:'6px 10px', background:'rgba(255,255,255,0.05)', borderRadius:'6px', fontSize:'13px'}}>{c.name}: ₹{c.amount}</span>
                          <button type="button" onClick={() => setOpOtherCharges(opOtherCharges.filter((_,j) => j!==i))} style={{background:'#ef4444', border:'none', color:'#fff', borderRadius:'6px', padding:'4px 10px', cursor:'pointer'}}>×</button>
                        </div>
                      ))}
                      <div style={{display:'flex', gap:'8px', marginTop:'8px'}}>
                        <input id="op-other-name" type="text" placeholder="Charge name" style={{flex:2, padding:'8px', background:'var(--bg-input)', border:'1px solid var(--input-border)', borderRadius:'6px', color:'var(--text-primary)'}} />
                        <input id="op-other-amt" type="number" placeholder="Amount" style={{flex:1, padding:'8px', background:'var(--bg-input)', border:'1px solid var(--input-border)', borderRadius:'6px', color:'var(--text-primary)'}} />
                        <button type="button" className="btn btn-primary" style={{padding:'8px 14px'}} onClick={() => {
                          const n = (document.getElementById('op-other-name') as HTMLInputElement)?.value;
                          const a = parseFloat((document.getElementById('op-other-amt') as HTMLInputElement)?.value||'0');
                          if (n && a>0) { setOpOtherCharges([...opOtherCharges, {name:n, amount:a}]); (document.getElementById('op-other-name') as HTMLInputElement).value=''; (document.getElementById('op-other-amt') as HTMLInputElement).value=''; }
                        }}>+ Add</button>
                      </div>
                    </div>

                    <div className="form-grid" style={{gridTemplateColumns:'1fr 1fr 1fr', gap:'12px'}}>
                      <div className="form-group">
                        <label>Discount (%)</label>
                        <input type="number" min="0" max="100" value={opBillForm.discount} onChange={e => setOpBillForm({...opBillForm, discount: parseFloat(e.target.value)||0})} />
                      </div>
                      <div className="form-group">
                        <label>GST (%)</label>
                        <input type="number" min="0" max="28" value={opBillForm.gst} onChange={e => setOpBillForm({...opBillForm, gst: parseFloat(e.target.value)||0})} />
                      </div>
                      <div className="form-group">
                        <label>Payment Mode</label>
                        <select value={opBillForm.payment_mode} onChange={e => setOpBillForm({...opBillForm, payment_mode: e.target.value})}>
                          <option>Cash</option><option>UPI</option><option>Card</option><option>Bank Transfer</option><option>Split</option>
                        </select>
                      </div>
                    </div>

                    {opBillForm.payment_mode === 'Split' && (
                      <div className="glass-card" style={{background:'rgba(59,130,246,0.08)', border:'1px solid rgba(59,130,246,0.3)', marginBottom:'16px'}}>
                        <h4 style={{marginBottom:'12px', color:'var(--accent-blue-soft)'}}>Split Payment Breakdown</h4>
                        <div className="form-grid" style={{gridTemplateColumns:'1fr 1fr 1fr 1fr', gap:'10px'}}>
                          {(['cash','upi','card','bank'] as const).map(mode => (
                            <div key={mode} className="form-group">
                              <label style={{textTransform:'capitalize'}}>{mode} (₹)</label>
                              <input type="number" min="0" value={opSplitPayment[mode]} onChange={e => setOpSplitPayment({...opSplitPayment, [mode]: parseFloat(e.target.value)||0})} />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="form-group">
                      <label>Notes</label>
                      <textarea value={opBillForm.notes} onChange={e => setOpBillForm({...opBillForm, notes: e.target.value})} rows={2} placeholder="Additional notes..." />
                    </div>

                    {/* Bill Summary */}
                    <div style={{background:'rgba(59,130,246,0.1)', border:'1px solid rgba(59,130,246,0.3)', borderRadius:'12px', padding:'16px', marginBottom:'16px'}}>
                      <div style={{display:'flex', justifyContent:'space-between', marginBottom:'6px', fontSize:'14px'}}><span style={{color:'var(--text-muted)'}}>Subtotal</span><span>₹{opSubtotal.toFixed(2)}</span></div>
                      <div style={{display:'flex', justifyContent:'space-between', marginBottom:'6px', fontSize:'14px'}}><span style={{color:'var(--text-muted)'}}>Discount ({opBillForm.discount}%)</span><span style={{color:'var(--accent-rose)'}}>-₹{opDiscountAmt.toFixed(2)}</span></div>
                      <div style={{display:'flex', justifyContent:'space-between', marginBottom:'12px', fontSize:'14px'}}><span style={{color:'var(--text-muted)'}}>GST ({opBillForm.gst}%)</span><span style={{color:'var(--accent-emerald)'}}>+₹{opGstAmt.toFixed(2)}</span></div>
                      <div style={{display:'flex', justifyContent:'space-between', fontSize:'20px', fontWeight:'700', color:'var(--accent-blue)', borderTop:'1px solid rgba(59,130,246,0.3)', paddingTop:'10px'}}><span>Total</span><span>₹{opTotal.toFixed(2)}</span></div>
                    </div>

                    <button type="submit" className="btn btn-primary" style={{width:'100%', padding:'14px', fontSize:'16px'}}>
                      <Receipt size={18} style={{marginRight:'8px', verticalAlign:'middle'}} /> Generate OP Bill & GST Invoice
                    </button>
                  </form>
                </div>

                {/* Invoice Preview */}
                {viewBillDetail && viewBillDetail.bill_type === 'op' && (
                  <div className="glass-card">
                    <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'20px'}}>
                      <h3>✅ OP Bill #{viewBillDetail.id} Created</h3>
                      <button className="btn btn-primary" onClick={() => printInvoice(viewBillDetail, 'op')}><Printer size={16} style={{marginRight:'6px'}} />Print GST Invoice</button>
                    </div>
                    <p style={{color:'var(--accent-emerald)', marginBottom:'12px'}}>Patient: {patients.find(p=>p.id===viewBillDetail.patient_id)?.name}</p>
                    <div style={{display:'flex', justifyContent:'space-between', padding:'10px 0', borderBottom:'1px solid var(--border)'}}><span style={{color:'var(--text-muted)'}}>Total Amount</span><span style={{fontSize:'24px', fontWeight:'700', color:'var(--accent-blue)'}}>₹{viewBillDetail.total?.toFixed(2)}</span></div>
                    <div style={{display:'flex', justifyContent:'space-between', padding:'10px 0'}}><span style={{color:'var(--text-muted)'}}>Payment Mode</span><span style={{padding:'4px 12px', background:'rgba(16,185,129,0.2)', color:'var(--accent-emerald)', borderRadius:'20px', fontSize:'12px', fontWeight:'600'}}>{viewBillDetail.payment_mode}</span></div>
                  </div>
                )}
              </div>
            )}

            {/* IP BILLING FORM */}
            {billingTab === 'ip' && (
              <div className="form-grid">
                <div className="glass-card">
                  <h3 style={{marginBottom:'20px', display:'flex', alignItems:'center', gap:'8px'}}><Building2 size={20} color="#8b5cf6" /> IP Bill Creation</h3>
                  <form onSubmit={handleCreateIPBill}>
                    <div className="form-grid" style={{gridTemplateColumns:'1fr 1fr', gap:'12px'}}>
                      <div className="form-group">
                        <label>Patient *</label>
                        <Select 
                          styles={selectStyles}
                          options={patients.map(p => ({ value: String(p.id), label: `${p.name} (ID: ${p.id})` }))}
                          value={ipBillForm.patient_id ? { value: String(ipBillForm.patient_id), label: patients.find(p => String(p.id) === String(ipBillForm.patient_id))?.name + ' (ID: ' + ipBillForm.patient_id + ')' } : null}
                          onChange={(sel: any) => setIpBillForm({...ipBillForm, patient_id: sel ? sel.value : ''})}
                          placeholder="Select Patient"
                          isClearable
                        />
                      </div>
                      <div className="form-group">
                        <label>Admission (Optional)</label>
                        <select value={ipBillForm.admission_id} onChange={e => setIpBillForm({...ipBillForm, admission_id: e.target.value})}>
                          <option value="">Select Admission</option>
                          {ipAdmissions.filter(a => !ipBillForm.patient_id || a.patient_id === Number(ipBillForm.patient_id)).map(a => <option key={a.id} value={a.id}>#{a.id} | {a.ward_number} | {a.room_number} | {a.status}</option>)}
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Doctor Name</label>
                        <input type="text" value={ipBillForm.doctor_name} onChange={e => setIpBillForm({...ipBillForm, doctor_name: e.target.value})} placeholder="Dr. Name" />
                      </div>
                      <div className="form-group"></div>
                    </div>

                    <h4 style={{margin:'16px 0 12px', color:'var(--text-muted)'}}>Room Charges</h4>
                    <div className="form-grid" style={{gridTemplateColumns:'1fr 1fr', gap:'12px'}}>
                      <div className="form-group">
                        <label>Room Charge per Day (₹)</label>
                        <input type="number" min="0" value={ipBillForm.room_charge_per_day} onChange={e => setIpBillForm({...ipBillForm, room_charge_per_day: parseFloat(e.target.value)||0})} />
                      </div>
                      <div className="form-group">
                        <label>Days Stayed</label>
                        <input type="number" min="1" value={ipBillForm.days_stayed} onChange={e => setIpBillForm({...ipBillForm, days_stayed: parseInt(e.target.value)||1})} />
                      </div>
                    </div>
                    <div style={{padding:'10px 14px', background:'rgba(139,92,246,0.1)', border:'1px solid rgba(139,92,246,0.3)', borderRadius:'8px', marginBottom:'16px', fontSize:'14px'}}>
                      Room Charges: ₹{ipBillForm.room_charge_per_day} × {ipBillForm.days_stayed} days = <strong style={{color:'var(--accent-violet)'}}>₹{ipRoomCharges.toFixed(2)}</strong>
                    </div>

                    <h4 style={{margin:'0 0 12px', color:'var(--text-muted)'}}>Other Service Charges</h4>
                    <div className="form-grid" style={{gridTemplateColumns:'1fr 1fr 1fr', gap:'12px'}}>
                      {[
                        {key:'doctor_charges', label:'Doctor Charges (₹)'}, {key:'nursing_charges', label:'Nursing Charges (₹)'},
                        {key:'pharmacy_charges', label:'Pharmacy Charges (₹)'}, {key:'lab_charges', label:'Lab Charges (₹)'}
                      ].map(({key, label}) => (
                        <div key={key} className="form-group">
                          <label>{label}</label>
                          <input type="number" min="0" step="0.01" value={(ipBillForm as any)[key]} onChange={e => setIpBillForm({...ipBillForm, [key]: parseFloat(e.target.value)||0})} />
                        </div>
                      ))}
                    </div>

                    {/* Other Charges */}
                    <div style={{marginBottom:'16px'}}>
                      <label style={{display:'block', marginBottom:'8px', fontSize:'13px', color:'var(--text-muted)'}}>Other Charges</label>
                      {ipOtherCharges.map((c, i) => (
                        <div key={i} style={{display:'flex', gap:'8px', alignItems:'center', marginBottom:'6px'}}>
                          <span style={{flex:1, padding:'6px 10px', background:'rgba(255,255,255,0.05)', borderRadius:'6px', fontSize:'13px'}}>{c.name}: ₹{c.amount}</span>
                          <button type="button" onClick={() => setIpOtherCharges(ipOtherCharges.filter((_,j) => j!==i))} style={{background:'#ef4444', border:'none', color:'#fff', borderRadius:'6px', padding:'4px 10px', cursor:'pointer'}}>×</button>
                        </div>
                      ))}
                      <div style={{display:'flex', gap:'8px', marginTop:'8px'}}>
                        <input id="ip-other-name" type="text" placeholder="Charge name" style={{flex:2, padding:'8px', background:'var(--bg-input)', border:'1px solid var(--input-border)', borderRadius:'6px', color:'var(--text-primary)'}} />
                        <input id="ip-other-amt" type="number" placeholder="Amount" style={{flex:1, padding:'8px', background:'var(--bg-input)', border:'1px solid var(--input-border)', borderRadius:'6px', color:'var(--text-primary)'}} />
                        <button type="button" className="btn btn-primary" style={{padding:'8px 14px'}} onClick={() => {
                          const n = (document.getElementById('ip-other-name') as HTMLInputElement)?.value;
                          const a = parseFloat((document.getElementById('ip-other-amt') as HTMLInputElement)?.value||'0');
                          if (n && a>0) { setIpOtherCharges([...ipOtherCharges, {name:n, amount:a}]); (document.getElementById('ip-other-name') as HTMLInputElement).value=''; (document.getElementById('ip-other-amt') as HTMLInputElement).value=''; }
                        }}>+ Add</button>
                      </div>
                    </div>

                    <div className="form-grid" style={{gridTemplateColumns:'1fr 1fr 1fr', gap:'12px'}}>
                      <div className="form-group">
                        <label>Discount (%)</label>
                        <input type="number" min="0" max="100" value={ipBillForm.discount} onChange={e => setIpBillForm({...ipBillForm, discount: parseFloat(e.target.value)||0})} />
                      </div>
                      <div className="form-group">
                        <label>GST (%)</label>
                        <input type="number" min="0" max="28" value={ipBillForm.gst} onChange={e => setIpBillForm({...ipBillForm, gst: parseFloat(e.target.value)||0})} />
                      </div>
                      <div className="form-group">
                        <label>Payment Mode</label>
                        <select value={ipBillForm.payment_mode} onChange={e => setIpBillForm({...ipBillForm, payment_mode: e.target.value})}>
                          <option>Cash</option><option>UPI</option><option>Card</option><option>Bank Transfer</option><option>Split</option>
                        </select>
                      </div>
                    </div>

                    {ipBillForm.payment_mode === 'Split' && (
                      <div className="glass-card" style={{background:'rgba(139,92,246,0.08)', border:'1px solid rgba(139,92,246,0.3)', marginBottom:'16px'}}>
                        <h4 style={{marginBottom:'12px', color:'var(--accent-violet-soft)'}}>Split Payment Breakdown</h4>
                        <div className="form-grid" style={{gridTemplateColumns:'1fr 1fr 1fr 1fr', gap:'10px'}}>
                          {(['cash','upi','card','bank'] as const).map(mode => (
                            <div key={mode} className="form-group">
                              <label style={{textTransform:'capitalize'}}>{mode} (₹)</label>
                              <input type="number" min="0" value={ipSplitPayment[mode]} onChange={e => setIpSplitPayment({...ipSplitPayment, [mode]: parseFloat(e.target.value)||0})} />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Bill Summary */}
                    <div style={{background:'rgba(139,92,246,0.1)', border:'1px solid rgba(139,92,246,0.3)', borderRadius:'12px', padding:'16px', marginBottom:'16px'}}>
                      <div style={{display:'flex', justifyContent:'space-between', marginBottom:'6px', fontSize:'14px'}}><span style={{color:'var(--text-muted)'}}>Subtotal</span><span>₹{ipSubtotal.toFixed(2)}</span></div>
                      <div style={{display:'flex', justifyContent:'space-between', marginBottom:'6px', fontSize:'14px'}}><span style={{color:'var(--text-muted)'}}>Discount ({ipBillForm.discount}%)</span><span style={{color:'var(--accent-rose)'}}>-₹{ipDiscountAmt.toFixed(2)}</span></div>
                      <div style={{display:'flex', justifyContent:'space-between', marginBottom:'12px', fontSize:'14px'}}><span style={{color:'var(--text-muted)'}}>GST ({ipBillForm.gst}%)</span><span style={{color:'var(--accent-emerald)'}}>+₹{ipGstAmt.toFixed(2)}</span></div>
                      <div style={{display:'flex', justifyContent:'space-between', fontSize:'20px', fontWeight:'700', color:'var(--accent-violet)', borderTop:'1px solid rgba(139,92,246,0.3)', paddingTop:'10px'}}><span>Total</span><span>₹{ipTotal.toFixed(2)}</span></div>
                    </div>

                    <button type="submit" className="btn btn-primary" style={{width:'100%', padding:'14px', fontSize:'16px', background:'linear-gradient(135deg, #7c3aed, #8b5cf6)'}}>
                      <Building2 size={18} style={{marginRight:'8px', verticalAlign:'middle'}} /> Generate IP Bill & GST Invoice
                    </button>
                  </form>
                </div>
                {viewBillDetail && viewBillDetail.bill_type === 'ip' && (
                  <div className="glass-card">
                    <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'20px'}}>
                      <h3>✅ IP Bill #{viewBillDetail.id} Created</h3>
                      <button className="btn btn-primary" onClick={() => printInvoice(viewBillDetail, 'ip')} style={{background:'linear-gradient(135deg,#7c3aed,#8b5cf6)'}}><Printer size={16} style={{marginRight:'6px'}} />Print GST Invoice</button>
                    </div>
                    <p style={{color:'var(--accent-emerald)', marginBottom:'12px'}}>Patient: {patients.find(p=>p.id===viewBillDetail.patient_id)?.name}</p>
                    <div style={{display:'flex', justifyContent:'space-between', padding:'10px 0', borderBottom:'1px solid var(--border)'}}><span style={{color:'var(--text-muted)'}}>Total Amount</span><span style={{fontSize:'24px', fontWeight:'700', color:'var(--accent-violet)'}}>₹{viewBillDetail.total?.toFixed(2)}</span></div>
                    <div style={{display:'flex', justifyContent:'space-between', padding:'10px 0'}}><span style={{color:'var(--text-muted)'}}>Days Stayed</span><span style={{color:'var(--accent-violet-soft)'}}>{viewBillDetail.days_stayed} days</span></div>
                  </div>
                )}
              </div>
            )}

            {/* OP Bill History */}
            {billingTab === 'op_history' && (
              <div className="glass-card">
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'16px'}}>
                  <h3>OP Bill History ({opBills.length} bills)</h3>
                  <button className="btn btn-primary" style={{padding:'8px 14px', fontSize:'13px'}} onClick={() => exportTableToCSV('op-bill-table', 'op_bills.csv')}><Download size={14} style={{marginRight:'6px', verticalAlign:'middle'}} />Export CSV</button>
                </div>
                <div className="table-container">
                  <table id="op-bill-table">
                    <thead><tr><th>Bill #</th><th>Patient</th><th>Doctor</th><th>Date</th><th>Total</th><th>Payment</th><th>Actions</th></tr></thead>
                    <tbody>
                      {opBills.map(b => {
                        const pat = patients.find(p => p.id === b.patient_id);
                        return (
                          <tr key={b.id}>
                            <td>#{b.id}</td>
                            <td>{pat?.name || `Patient #${b.patient_id}`}</td>
                            <td>{b.doctor_name || '-'}</td>
                            <td>{new Date(b.bill_date).toLocaleDateString('en-IN')}</td>
                            <td style={{color:'var(--accent-emerald)', fontWeight:'600'}}>₹{b.total.toFixed(2)}</td>
                            <td><span style={{padding:'2px 10px', borderRadius:'12px', fontSize:'12px', background:'rgba(59,130,246,0.2)', color:'var(--accent-blue-soft)'}}>{b.payment_mode}</span></td>
                            <td><button style={{background:'none', border:'none', color:'var(--accent-blue)', cursor:'pointer', fontSize:'13px'}} onClick={() => printInvoice(b, 'op')}>🖨 Print</button></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* IP Bill History */}
            {billingTab === 'ip_history' && (
              <div className="glass-card">
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'16px'}}>
                  <h3>IP Bill History ({ipBills.length} bills)</h3>
                  <button className="btn btn-primary" style={{padding:'8px 14px', fontSize:'13px'}} onClick={() => exportTableToCSV('ip-bill-table', 'ip_bills.csv')}><Download size={14} style={{marginRight:'6px', verticalAlign:'middle'}} />Export CSV</button>
                </div>
                <div className="table-container">
                  <table id="ip-bill-table">
                    <thead><tr><th>Bill #</th><th>Patient</th><th>Doctor</th><th>Days</th><th>Date</th><th>Total</th><th>Payment</th><th>Actions</th></tr></thead>
                    <tbody>
                      {ipBills.map(b => {
                        const pat = patients.find(p => p.id === b.patient_id);
                        return (
                          <tr key={b.id}>
                            <td>#{b.id}</td>
                            <td>{pat?.name || `Patient #${b.patient_id}`}</td>
                            <td>{b.doctor_name || '-'}</td>
                            <td>{b.days_stayed}</td>
                            <td>{new Date(b.bill_date).toLocaleDateString('en-IN')}</td>
                            <td style={{color:'var(--accent-violet)', fontWeight:'600'}}>₹{b.total.toFixed(2)}</td>
                            <td><span style={{padding:'2px 10px', borderRadius:'12px', fontSize:'12px', background:'rgba(139,92,246,0.2)', color:'var(--accent-violet-soft)'}}>{b.payment_mode}</span></td>
                            <td><button style={{background:'none', border:'none', color:'var(--accent-violet)', cursor:'pointer', fontSize:'13px'}} onClick={() => printInvoice(b, 'ip')}>🖨 Print</button></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* =========================================================== */}
        {/* REPORTS MODULE */}
        {/* =========================================================== */}
        {activeTab === 'reports' && (
          <div>
            <div className="header no-print">
              <div className="header-title">
                <h1>Reports</h1>
                <p>Daily, Monthly, Yearly, Revenue & Department Reports</p>
              </div>
            </div>

            {/* Report Type Selector */}
            <div style={{display:'flex', gap:'8px', padding:'0 24px 16px', flexWrap:'wrap'}} className="no-print">
              {[
                {key:'daily', label:'📅 Daily'}, {key:'monthly', label:'📆 Monthly'}, {key:'yearly', label:'📊 Yearly'},
                {key:'revenue', label:'💰 Revenue'}, {key:'doctor', label:'👨‍⚕️ Doctor Wise'}, {key:'medicine', label:'💊 Medicine Sales'},
                {key:'department', label:'🏢 Department Wise'}, {key:'patient', label:'🧑‍⚕️ Patient History'},
                {key:'stock', label:'📦 Stock Valuation'}, {key:'lab', label:'🔬 Lab Summary'}, {key:'discharge', label:'🏥 Discharge'}
              ].map(r => (
                <button key={r.key} onClick={() => { 
                  setReportType(r.key); 
                  if(r.key==='daily') loadDailyReport(); 
                  else if(r.key==='monthly') loadMonthlyReport(); 
                  else if(r.key==='yearly') loadYearlyReport(); 
                  else if(r.key==='revenue') loadRevenueReport(); 
                  else if(r.key==='doctor') loadDoctorReport(); 
                  else if(r.key==='medicine') loadMedicineSalesReport(); 
                  else if(r.key==='department') loadDepartmentWiseReport();
                  else if(r.key==='patient') loadPatientReport();
                  else if(r.key==='stock') loadMedicineStockReport();
                  else if(r.key==='lab') loadLabSummaryReport();
                  else if(r.key==='discharge') loadDischargeReport();
                }}
                  style={{padding:'8px 18px', borderRadius:'20px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'13px',
                    background: reportType === r.key ? 'linear-gradient(135deg, #3b82f6, #2563eb)' : 'var(--bg-input)',
                    color: reportType === r.key ? '#fff' : 'var(--accent-slate)', transition:'all 0.3s'}}>
                  {r.label}
                </button>
              ))}
            </div>

            {/* Daily Report */}
            {reportType === 'daily' && (
              <div>
                <div style={{display:'flex', gap:'12px', alignItems:'center', padding:'0 24px 16px'}} className="no-print">
                  <input type="date" value={reportDate} onChange={e => setReportDate(e.target.value)}
                    style={{padding:'8px 12px', background:'var(--bg-input)', border:'1px solid var(--input-border)', borderRadius:'8px', color:'var(--text-primary)'}} />
                  <button className="btn btn-primary" onClick={loadDailyReport} style={{padding:'8px 18px'}}>Load Report</button>
                  {dailyReport && <><button className="btn btn-primary" style={{padding:'8px 14px', background:'var(--primary-glow)', border:'1px solid var(--border)'}} onClick={() => exportTableToCSV('daily-report-table', `daily_report_${reportDate}.csv`)}><Download size={14} style={{marginRight:'4px', verticalAlign:'middle'}} />CSV</button><button className="btn btn-primary" style={{padding:'8px 14px', background:'var(--primary-glow)', border:'1px solid var(--border)'}} onClick={() => printSection('daily-report-section')}><Printer size={14} style={{marginRight:'4px', verticalAlign:'middle'}} />Print</button></>}
                </div>
                {dailyReport && (
                  <div id="daily-report-section">
                    <div className="stat-grid" style={{padding:'0 24px 16px'}}>
                      {[
                        {label:'Total Revenue', value:`₹${dailyReport.total_revenue.toFixed(2)}`, color:'var(--accent-blue)'},
                        {label:'OP Revenue', value:`₹${dailyReport.op_revenue.toFixed(2)}`, color:'var(--accent-emerald)'},
                        {label:'IP Revenue', value:`₹${dailyReport.ip_revenue.toFixed(2)}`, color:'var(--accent-violet)'},
                        {label:'Pharmacy Revenue', value:`₹${dailyReport.pharmacy_revenue.toFixed(2)}`, color:'var(--accent-amber)'},
                        {label:'Lab Revenue', value:`₹${dailyReport.lab_revenue.toFixed(2)}`, color:'var(--accent-rose)'},
                        {label:'Total Bills', value:`${dailyReport.total_bills} bills`, color:'var(--text-muted)'},
                      ].map(({label, value, color}) => (
                        <div key={label} className="glass-card stat-card">
                          <div><label style={{color:'var(--text-muted)', fontSize:'12px'}}>{label}</label><div className="stat-val" style={{color, fontSize:'20px'}}>{value}</div></div>
                        </div>
                      ))}
                    </div>
                    <div className="glass-card" style={{margin:'0 24px'}}>
                      <h3 style={{marginBottom:'16px'}}>Daily Revenue Breakdown - {dailyReport.date}</h3>
                      <div className="table-container">
                        <table id="daily-report-table">
                          <thead><tr><th>Category</th><th>Revenue</th><th>% of Total</th></tr></thead>
                          <tbody>
                            {[['OP Billing', dailyReport.op_revenue], ['IP Billing', dailyReport.ip_revenue], ['Pharmacy', dailyReport.pharmacy_revenue], ['Laboratory', dailyReport.lab_revenue]].map(([cat, rev]) => (
                              <tr key={cat as string}><td>{cat}</td><td style={{color:'var(--accent-emerald)'}}>₹{(rev as number).toFixed(2)}</td><td>{dailyReport.total_revenue > 0 ? (((rev as number)/dailyReport.total_revenue)*100).toFixed(1) : 0}%</td></tr>
                            ))}
                            <tr style={{fontWeight:'700', borderTop:'2px solid var(--border)'}}><td>Total</td><td style={{color:'var(--accent-blue)'}}>₹{dailyReport.total_revenue.toFixed(2)}</td><td>100%</td></tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Monthly Report */}
            {reportType === 'monthly' && (
              <div>
                <div style={{display:'flex', gap:'12px', alignItems:'center', padding:'0 24px 16px'}} className="no-print">
                  <select value={reportMonth} onChange={e => setReportMonth(Number(e.target.value))} style={{padding:'8px 12px', background:'var(--bg-input)', border:'1px solid var(--input-border)', borderRadius:'8px', color:'var(--text-primary)'}}>
                    {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].map((m,i) => <option key={i} value={i+1}>{m}</option>)}
                  </select>
                  <input type="number" value={reportYear} onChange={e => setReportYear(Number(e.target.value))} style={{padding:'8px 12px', background:'var(--bg-input)', border:'1px solid var(--input-border)', borderRadius:'8px', color:'var(--text-primary)', width:'100px'}} />
                  <button className="btn btn-primary" onClick={loadMonthlyReport} style={{padding:'8px 18px'}}>Load Report</button>
                  {monthlyReport.length > 0 && <><button className="btn btn-primary" style={{padding:'8px 14px', background:'var(--primary-glow)', border:'1px solid var(--border)'}} onClick={() => exportTableToCSV('monthly-table', `monthly_report_${reportYear}_${reportMonth}.csv`)}><Download size={14} style={{marginRight:'4px', verticalAlign:'middle'}} />CSV</button><button className="btn btn-primary" style={{padding:'8px 14px', background:'var(--primary-glow)', border:'1px solid var(--border)'}} onClick={() => printSection('monthly-section')}><Printer size={14} style={{marginRight:'4px', verticalAlign:'middle'}} />Print</button></>}
                </div>
                {monthlyReport.length > 0 && (
                  <div id="monthly-section" className="glass-card" style={{margin:'0 24px'}}>
                    <h3 style={{marginBottom:'16px'}}>Monthly Report</h3>
                    <div className="table-container">
                      <table id="monthly-table">
                        <thead><tr><th>Date</th><th>OP Revenue</th><th>IP Revenue</th><th>Pharmacy</th><th>Lab</th><th>Total Revenue</th><th>Bills</th></tr></thead>
                        <tbody>
                          {monthlyReport.map(r => (
                            <tr key={r.date}>
                              <td>{r.date}</td><td>₹{r.op_revenue.toFixed(2)}</td><td>₹{r.ip_revenue.toFixed(2)}</td>
                              <td>₹{r.pharmacy_revenue.toFixed(2)}</td><td>₹{r.lab_revenue.toFixed(2)}</td>
                              <td style={{color:'var(--accent-blue)', fontWeight:'600'}}>₹{r.total_revenue.toFixed(2)}</td><td>{r.total_bills}</td>
                            </tr>
                          ))}
                          <tr style={{fontWeight:'700', borderTop:'2px solid var(--border)'}}>
                            <td>Total</td>
                            <td>₹{monthlyReport.reduce((s,r)=>s+r.op_revenue,0).toFixed(2)}</td>
                            <td>₹{monthlyReport.reduce((s,r)=>s+r.ip_revenue,0).toFixed(2)}</td>
                            <td>₹{monthlyReport.reduce((s,r)=>s+r.pharmacy_revenue,0).toFixed(2)}</td>
                            <td>₹{monthlyReport.reduce((s,r)=>s+r.lab_revenue,0).toFixed(2)}</td>
                            <td style={{color:'var(--accent-blue)'}}>₹{monthlyReport.reduce((s,r)=>s+r.total_revenue,0).toFixed(2)}</td>
                            <td>{monthlyReport.reduce((s,r)=>s+r.total_bills,0)}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Yearly Report */}
            {reportType === 'yearly' && (
              <div>
                <div style={{display:'flex', gap:'12px', alignItems:'center', padding:'0 24px 16px'}} className="no-print">
                  <input type="number" value={reportYear} onChange={e => setReportYear(Number(e.target.value))} style={{padding:'8px 12px', background:'var(--bg-input)', border:'1px solid var(--input-border)', borderRadius:'8px', color:'var(--text-primary)', width:'120px'}} />
                  <button className="btn btn-primary" onClick={loadYearlyReport} style={{padding:'8px 18px'}}>Load Report</button>
                  {yearlyReport.length > 0 && <button className="btn btn-primary" style={{padding:'8px 14px', background:'var(--primary-glow)', border:'1px solid var(--border)'}} onClick={() => exportTableToCSV('yearly-table', `yearly_report_${reportYear}.csv`)}><Download size={14} style={{marginRight:'4px', verticalAlign:'middle'}} />CSV</button>}
                </div>
                {yearlyReport.length > 0 && (
                  <div className="glass-card" style={{margin:'0 24px'}}>
                    <h3 style={{marginBottom:'16px'}}>Yearly Report - {reportYear}</h3>
                    <div className="table-container">
                      <table id="yearly-table">
                        <thead><tr><th>Month</th><th>OP</th><th>IP</th><th>Pharmacy</th><th>Lab</th><th>Total</th><th>Bills</th></tr></thead>
                        <tbody>
                          {yearlyReport.map(r => (
                            <tr key={r.month}><td>{r.month}</td><td>₹{r.op_revenue.toFixed(0)}</td><td>₹{r.ip_revenue.toFixed(0)}</td><td>₹{r.pharmacy_revenue.toFixed(0)}</td><td>₹{r.lab_revenue.toFixed(0)}</td><td style={{color:'var(--accent-blue)', fontWeight:'600'}}>₹{r.total_revenue.toFixed(0)}</td><td>{r.total_bills}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Revenue Breakdown */}
            {reportType === 'revenue' && (
              <div>
                <div style={{padding:'0 24px 16px'}} className="no-print">
                  <button className="btn btn-primary" onClick={loadRevenueReport} style={{padding:'8px 18px'}}>Load Revenue Breakdown</button>
                </div>
                {revenueReport && (
                  <div className="stat-grid" style={{padding:'0 24px'}}>
                    {[
                      {label:'OP Billing', value: revenueReport.op_total, color:'var(--accent-blue)', icon:'🏥'},
                      {label:'IP Billing', value: revenueReport.ip_total, color:'var(--accent-violet)', icon:'🛏️'},
                      {label:'Pharmacy', value: revenueReport.pharmacy_total, color:'var(--accent-emerald)', icon:'💊'},
                      {label:'Laboratory', value: revenueReport.lab_total, color:'var(--accent-amber)', icon:'🧪'},
                      {label:'Grand Total', value: revenueReport.grand_total, color:'var(--accent-rose)', icon:'💰'},
                    ].map(({label, value, color, icon}) => (
                      <div key={label} className="glass-card stat-card" style={{border:`1px solid ${color}30`}}>
                        <div style={{fontSize:'28px', marginBottom:'8px'}}>{icon}</div>
                        <label style={{color:'var(--text-muted)', fontSize:'12px'}}>{label}</label>
                        <div className="stat-val" style={{color, fontSize:'22px', fontWeight:'700'}}>₹{value.toFixed(2)}</div>
                        {revenueReport.grand_total > 0 && <div style={{color:'var(--text-secondary)', fontSize:'12px', marginTop:'4px'}}>{((value/revenueReport.grand_total)*100).toFixed(1)}% of total</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Doctor Wise Report */}
            {reportType === 'doctor' && (
              <div>
                <div style={{padding:'0 24px 16px'}} className="no-print">
                  <button className="btn btn-primary" onClick={loadDoctorReport} style={{padding:'8px 18px'}}>Load Doctor Report</button>
                  {doctorReport.length > 0 && <button className="btn btn-primary" style={{marginLeft:'8px', padding:'8px 14px', background:'var(--primary-glow)', border:'1px solid var(--border)'}} onClick={() => exportTableToCSV('doctor-table', 'doctor_wise_report.csv')}><Download size={14} style={{marginRight:'4px', verticalAlign:'middle'}} />CSV</button>}
                </div>
                {doctorReport.length > 0 && (
                  <div className="glass-card" style={{margin:'0 24px'}}>
                    <h3 style={{marginBottom:'16px'}}>Doctor Wise Revenue</h3>
                    <div className="table-container">
                      <table id="doctor-table">
                        <thead><tr><th>Doctor Name</th><th>OP Bills</th><th>IP Bills</th><th>Total Revenue</th></tr></thead>
                        <tbody>
                          {doctorReport.sort((a,b) => b.total_revenue - a.total_revenue).map((d, i) => (
                            <tr key={i}><td>👨‍⚕️ {d.doctor_name}</td><td>{d.op_bills}</td><td>{d.ip_bills}</td><td style={{color:'var(--accent-emerald)', fontWeight:'600'}}>₹{d.total_revenue.toFixed(2)}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Department Wise Report */}
            {reportType === 'department' && (
              <div className="glass-card" style={{margin:'0 24px'}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'16px'}}>
                  <h3>Department Wise Revenue</h3>
                  <div>
                    <button className="btn btn-primary" style={{marginRight:'8px'}} onClick={() => exportTableToCSV('dept-table', 'department_report.csv')}><Download size={14}/> CSV</button>
                    <button className="btn btn-primary" onClick={() => printSection('dept-section')}><Printer size={14}/> Print</button>
                  </div>
                </div>
                <div id="dept-section" className="table-container">
                  <table id="dept-table">
                    <thead><tr><th>Department</th><th>Total Bills</th><th>Revenue</th></tr></thead>
                    <tbody>
                      {departmentWiseReport.map(r => (
                        <tr key={r.department}>
                          <td>{r.department}</td>
                          <td>{r.total_bills}</td>
                          <td style={{color:'var(--accent-emerald)', fontWeight:'bold'}}>₹{r.total_revenue.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Patient Report */}
            {reportType === 'patient' && (
              <div style={{margin:'0 24px'}}>
                <div style={{display:'flex', gap:'12px', marginBottom:'16px'}}>
                  <input type="text" placeholder="Enter Patient ID" value={patientReportId} onChange={e => setPatientReportId(e.target.value)} style={{padding:'8px', borderRadius:'6px', background:'var(--bg-input)', color:'var(--text-primary)', border:'1px solid var(--input-border)'}} />
                  <button className="btn btn-primary" onClick={loadPatientReport}>Load Patient Summary</button>
                  {patientReportData && <button className="btn btn-primary" onClick={() => printSection('patient-section')}><Printer size={14}/> Print</button>}
                </div>
                {patientReportData && (
                  <div id="patient-section" className="glass-card">
                    <h3>Patient: {patientReportData.patient.name} (ID: {patientReportData.patient.id})</h3>
                    <p style={{color:'var(--text-muted)', marginBottom:'16px'}}>Age: {patientReportData.patient.age} | Gender: {patientReportData.patient.gender} | Phone: {patientReportData.patient.phone}</p>
                    <div className="stat-grid">
                      <div className="glass-card"><div><label>OP Visits</label><div className="stat-val">{patientReportData.op_visits}</div></div></div>
                      <div className="glass-card"><div><label>Admissions</label><div className="stat-val">{patientReportData.admissions}</div></div></div>
                      <div className="glass-card"><div><label>Total Revenue</label><div className="stat-val" style={{color:'var(--accent-blue)'}}>₹{patientReportData.total_revenue.toFixed(2)}</div></div></div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Medicine Stock Report */}
            {reportType === 'stock' && (
              <div className="glass-card" style={{margin:'0 24px'}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'16px'}}>
                  <h3>Medicine Stock & Valuation</h3>
                  <div>
                    <button className="btn btn-primary" style={{marginRight:'8px'}} onClick={() => exportTableToCSV('stock-table', 'stock_report.csv')}><Download size={14}/> CSV</button>
                    <button className="btn btn-primary" onClick={() => printSection('stock-section')}><Printer size={14}/> Print</button>
                  </div>
                </div>
                <div id="stock-section" className="table-container">
                  <table id="stock-table">
                    <thead><tr><th>Item Name</th><th>Category</th><th>Qty</th><th>Unit Price</th><th>Total Value</th></tr></thead>
                    <tbody>
                      {medicineStockReport.map(r => (
                        <tr key={r.id}>
                          <td>{r.name}</td>
                          <td>{r.category}</td>
                          <td style={{color: r.quantity <= r.min_stock_level ? '#ef4444' : '#10b981'}}>{r.quantity}</td>
                          <td>₹{r.unit_price.toFixed(2)}</td>
                          <td>₹{(r.quantity * r.unit_price).toFixed(2)}</td>
                        </tr>
                      ))}
                      <tr style={{fontWeight:'bold', borderTop:'2px solid var(--border)'}}>
                        <td colSpan={4}>Total Inventory Valuation</td>
                        <td style={{color:'var(--accent-blue)'}}>₹{medicineStockReport.reduce((s:number, r:any) => s + (r.quantity * r.unit_price), 0).toFixed(2)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Lab Report */}
            {reportType === 'lab' && (
              <div className="glass-card" style={{margin:'0 24px'}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'16px'}}>
                  <h3>Lab Test Reports</h3>
                  <div>
                    <button className="btn btn-primary" style={{marginRight:'8px'}} onClick={() => exportTableToCSV('lab-table', 'lab_report.csv')}><Download size={14}/> CSV</button>
                    <button className="btn btn-primary" onClick={() => printSection('lab-section')}><Printer size={14}/> Print</button>
                  </div>
                </div>
                <div id="lab-section" className="table-container">
                  <table id="lab-table">
                    <thead><tr><th>Date</th><th>Patient ID</th><th>Test Name</th><th>Status</th><th>Result</th><th>Actions</th></tr></thead>
                    <tbody>
                      {labSummaryReport.map(r => (
                        <tr key={r.id}>
                          <td>{new Date(r.report_date).toLocaleDateString()}</td>
                          <td>{r.patient_id}</td>
                          <td>{r.test_name}</td>
                          <td>{r.status}</td>
                          <td>{r.result_value || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Discharge Report */}
            {reportType === 'discharge' && (
              <div className="glass-card" style={{margin:'0 24px'}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'16px'}}>
                  <h3>Discharged Patients</h3>
                  <div>
                    <button className="btn btn-primary" style={{marginRight:'8px'}} onClick={() => exportTableToCSV('discharge-table', 'discharge_report.csv')}><Download size={14}/> CSV</button>
                    <button className="btn btn-primary" onClick={() => printSection('discharge-section')}><Printer size={14}/> Print</button>
                  </div>
                </div>
                <div id="discharge-section" className="table-container">
                  <table id="discharge-table">
                    <thead><tr><th>Patient ID</th><th>Admission Date</th><th>Discharge Date</th><th>Ward</th></tr></thead>
                    <tbody>
                      {dischargeReport.map(r => (
                        <tr key={r.id}>
                          <td>{r.patient_id}</td>
                          <td>{new Date(r.admission_date).toLocaleDateString()}</td>
                          <td>{r.discharge_date ? new Date(r.discharge_date).toLocaleDateString() : '-'}</td>
                          <td>{r.ward_number}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Medicine Sales Report */}
            {reportType === 'medicine' && (
              <div>
                <div style={{padding:'0 24px 16px'}} className="no-print">
                  <button className="btn btn-primary" onClick={loadMedicineSalesReport} style={{padding:'8px 18px'}}>Load Medicine Sales</button>
                  {medicineSalesReport.length > 0 && <button className="btn btn-primary" style={{marginLeft:'8px', padding:'8px 14px', background:'var(--primary-glow)', border:'1px solid var(--border)'}} onClick={() => exportTableToCSV('medicine-table', 'medicine_sales_report.csv')}><Download size={14} style={{marginRight:'4px', verticalAlign:'middle'}} />CSV</button>}
                </div>
                {medicineSalesReport.length > 0 && (
                  <div className="glass-card" style={{margin:'0 24px'}}>
                    <h3 style={{marginBottom:'16px'}}>Medicine Sales Report</h3>
                    <div className="table-container">
                      <table id="medicine-table">
                        <thead><tr><th>#</th><th>Medicine Name</th><th>Qty Sold</th><th>Revenue</th></tr></thead>
                        <tbody>
                          {medicineSalesReport.map((m, i) => (
                            <tr key={i}><td>{i+1}</td><td>💊 {m.medicine_name}</td><td>{m.total_quantity_sold}</td><td style={{color:'var(--accent-emerald)', fontWeight:'600'}}>₹{m.total_revenue.toFixed(2)}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* =========================================================== */}
        {/* GLOBAL SEARCH */}
        {/* =========================================================== */}
        {activeTab === 'search' && (
          <div>
            <div className="header no-print">
              <div className="header-title">
                <h1>Global Search</h1>
                <p>Search by Patient ID, Name, Mobile, Aadhaar, Token #, Bill #, Admission #</p>
              </div>
            </div>

            <div style={{padding:'0 24px 24px'}}>
              {/* Search Input */}
              <div style={{position:'relative', marginBottom:'24px'}}>
                <Search size={20} style={{position:'absolute', left:'16px', top:'50%', transform:'translateY(-50%)', color:'var(--text-muted)'}} />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => handleSearch(e.target.value)}
                  placeholder="Type patient name, ID, mobile, Aadhaar, token #, bill #..."
                  style={{
                    width:'100%', padding:'16px 16px 16px 48px', fontSize:'16px',
                    background:'var(--bg-input)', border:'1px solid var(--input-border)',
                    borderRadius:'12px', color:'var(--text-primary)', outline:'none',
                    boxShadow:'0 0 0 0 rgba(59,130,246,0)', transition:'all 0.3s'
                  }}
                  onFocus={e => e.target.style.border='1px solid rgba(59,130,246,0.5)'}
                  onBlur={e => e.target.style.border='1px solid var(--input-border)'}
                />
                {searchLoading && <div style={{position:'absolute', right:'16px', top:'50%', transform:'translateY(-50%)', color:'var(--accent-blue)', fontSize:'13px'}}>Searching...</div>}
              </div>

              {/* Search Tips */}
              {!searchQuery && (
                <div className="stat-grid" style={{marginBottom:'24px'}}>
                  {[
                    {icon:'🆔', label:'Patient ID', hint:'Type: 123'},
                    {icon:'👤', label:'Patient Name', hint:'Type: Arun'},
                    {icon:'📱', label:'Mobile Number', hint:'Type: 9876543210'},
                    {icon:'🪪', label:'Aadhaar', hint:'Type: XXXX XXXX XXXX'},
                    {icon:'🎫', label:'Token Number', hint:'Type: 5'},
                    {icon:'🧾', label:'Bill Number', hint:'Type: 12'},
                  ].map(({icon, label, hint}) => (
                    <div key={label} className="glass-card" style={{textAlign:'center', padding:'16px'}}>
                      <div style={{fontSize:'24px', marginBottom:'6px'}}>{icon}</div>
                      <div style={{fontWeight:'600', fontSize:'13px', marginBottom:'4px'}}>{label}</div>
                      <div style={{color:'var(--text-secondary)', fontSize:'12px'}}>{hint}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Search Results */}
              {searchQuery && searchResults.length === 0 && !searchLoading && (
                <div style={{textAlign:'center', padding:'40px', color:'var(--text-secondary)'}}>
                  <Search size={48} style={{opacity:0.3, marginBottom:'12px'}} />
                  <p>No results found for "{searchQuery}"</p>
                </div>
              )}

              {searchResults.length > 0 && (
                <div>
                  <h3 style={{marginBottom:'16px', color:'var(--text-muted)', fontSize:'14px', letterSpacing:'1px', textTransform:'uppercase'}}>{searchResults.length} Results Found</h3>
                  <div style={{display:'flex', flexDirection:'column', gap:'12px'}}>
                    {searchResults.map((result, i) => {
                      const typeColors: Record<string, string> = {
                        patient: '#3b82f6', op_token: '#10b981', op_bill: '#f59e0b',
                        ip_bill: '#8b5cf6', pharmacy_bill: '#06b6d4', lab_bill: '#ef4444', admission: '#84cc16'
                      };
                      const typeIcons: Record<string, string> = {
                        patient: '👤', op_token: '🎫', op_bill: '🏥', ip_bill: '🛏️',
                        pharmacy_bill: '💊', lab_bill: '🧪', admission: '🏨'
                      };
                      const color = typeColors[result.type] || 'var(--accent-slate)';
                      return (
                        <div key={i} className="glass-card" style={{display:'flex', alignItems:'center', gap:'16px', padding:'16px', border:`1px solid ${color}30`, cursor:'pointer', transition:'all 0.2s'}}
                          onClick={async () => {
                            try {
                              if (result.type === 'patient' || result.type === 'op_token' || result.type === 'admission') { 
                                setActiveTab('reports'); 
                                setReportType('patient'); 
                                setPatientReportId(String(result.patient_id));
                                const res = await axios.get(`${API_BASE}/reports/patient/${result.patient_id}`);
                                setPatientReportData(res.data);
                              }
                              else if (result.type === 'op_bill') {
                                setActiveTab('billing');
                              }
                              else if (result.type === 'ip_bill') {
                                setActiveTab('billing');
                              }
                              else if (result.type === 'pharmacy_bill') { 
                                setActiveTab('pharmacy'); 
                              }
                              else if (result.type === 'lab_bill') { 
                                setActiveTab('lab_reports'); 
                              }
                            } catch(e) { console.error(e); }
                          }}
                          onMouseOver={e => (e.currentTarget.style.border = `1px solid ${color}60`)}
                          onMouseOut={e => (e.currentTarget.style.border = `1px solid ${color}30`)}>
                          <div style={{width:'44px', height:'44px', borderRadius:'10px', background:`${color}20`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:'20px', flexShrink:0}}>{typeIcons[result.type] || '📄'}</div>
                          <div style={{flex:1}}>
                            <div style={{display:'flex', alignItems:'center', gap:'8px', marginBottom:'4px'}}>
                              <span style={{padding:'2px 10px', borderRadius:'12px', fontSize:'11px', fontWeight:'700', background:`${color}25`, color, textTransform:'uppercase'}}>{result.type.replace('_', ' ')}</span>
                              <span style={{fontWeight:'600', fontSize:'14px'}}>{result.patient_name}</span>
                            </div>
                            <div style={{color:'var(--text-muted)', fontSize:'13px'}}>{result.detail}</div>
                          </div>
                          <div style={{textAlign:'right', flexShrink:0}}>
                            {result.amount !== null && result.amount !== undefined && <div style={{fontWeight:'700', color:'var(--accent-emerald)', fontSize:'16px'}}>₹{result.amount?.toFixed(2)}</div>}
                            {result.date && <div style={{color:'var(--text-secondary)', fontSize:'12px', marginTop:'2px'}}>{result.date}</div>}
                            <div style={{color:color, fontSize:'12px', marginTop:'4px'}}>Click to view →</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* =================== ADMIN SETTINGS =================== */}
        {currentUser?.role === 'Admin' && activeTab === 'admin_settings' && (
          <div>
            <div className="header">
              <div className="header-title">
                <h1>Admin Settings</h1>
                <p>Configure hospital information, receipt format, and system settings</p>
              </div>
              <button className="btn btn-primary" style={{display:'flex',alignItems:'center',gap:'6px'}} onClick={saveHospitalSettings}>
                {settingsSaved ? <><span>✅</span> Saved!</> : <><Save size={16}/> Save Settings</>}
              </button>
            </div>

            {/* Sub-tabs */}
            <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
              {[
                {id:'hospital_info', icon:<Building2 size={16}/>, label:'Hospital Info'},
                {id:'receipt_format', icon:<Receipt size={16}/>, label:'Receipt Format'},
                {id:'printer_settings', icon:<Printer size={16}/>, label:'Printer Settings'},
                {id:'backup', icon:<Database size={16}/>, label:'Backup & Restore'},
                {id:'audit_logs', icon:<Shield size={16}/>, label:'Audit Logs'},
              ].map(tab => (
                <button key={tab.id}
                  onClick={() => setAdminSettingsTab(tab.id)}
                  style={{display:'flex',alignItems:'center',gap:'6px',padding:'8px 16px',borderRadius:'8px',border:`2px solid ${adminSettingsTab===tab.id?'#3b82f6':'var(--border-color)'}`,background:adminSettingsTab===tab.id?'rgba(59,130,246,0.1)':'transparent',color:adminSettingsTab===tab.id?'#3b82f6':'var(--text-muted)',cursor:'pointer',fontWeight:600,fontSize:'13px',transition:'all 0.2s'}}>
                  {tab.icon}{tab.label}
                </button>
              ))}
            </div>

            {/* Hospital Information */}
            {adminSettingsTab === 'hospital_info' && (
              <div className="glass-card">
                <h3 style={{marginBottom:'20px',display:'flex',alignItems:'center',gap:'8px'}}><Building2 size={20}/> Hospital Information</h3>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                  <div className="form-group">
                    <label>Hospital Name</label>
                    <input className="input-field" value={hospitalSettings.hospital_name||''} onChange={e=>setHospitalSettings({...hospitalSettings,hospital_name:e.target.value})} placeholder="Hospital Name"/>
                  </div>
                  <div className="form-group">
                    <label>GST Number</label>
                    <input className="input-field" value={hospitalSettings.gst_number||''} onChange={e=>setHospitalSettings({...hospitalSettings,gst_number:e.target.value})} placeholder="GST Registration Number"/>
                  </div>
                  <div className="form-group" style={{gridColumn:'span 2'}}>
                    <label>Address</label>
                    <input className="input-field" value={hospitalSettings.address||''} onChange={e=>setHospitalSettings({...hospitalSettings,address:e.target.value})} placeholder="Full Hospital Address"/>
                  </div>
                  <div className="form-group">
                    <label>Contact Number</label>
                    <input className="input-field" value={hospitalSettings.contact||''} onChange={e=>setHospitalSettings({...hospitalSettings,contact:e.target.value})} placeholder="+91 XXXXX XXXXX"/>
                  </div>
                  <div className="form-group">
                    <label>Email</label>
                    <input className="input-field" type="email" value={hospitalSettings.email||''} onChange={e=>setHospitalSettings({...hospitalSettings,email:e.target.value})} placeholder="info@hospital.com"/>
                  </div>
                </div>
                <div style={{marginTop:'20px',padding:'16px',background:'rgba(59,130,246,0.05)',borderRadius:'8px',border:'1px solid rgba(59,130,246,0.2)'}}>
                  <h4 style={{marginBottom:'12px',color:'var(--accent-blue)'}}>Preview (GST Invoice Header)</h4>
                  <div style={{textAlign:'center',fontFamily:'Arial'}}>
                    <div style={{fontWeight:'bold',fontSize:'18px'}}>{hospitalSettings.hospital_name}</div>
                    <div style={{color:'var(--text-secondary)',fontSize:'13px'}}>{hospitalSettings.address}</div>
                    <div style={{color:'var(--text-secondary)',fontSize:'13px'}}>📞 {hospitalSettings.contact} | ✉ {hospitalSettings.email}</div>
                    <div style={{color:'var(--text-secondary)',fontSize:'13px'}}>GST: {hospitalSettings.gst_number}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Receipt Format */}
            {adminSettingsTab === 'receipt_format' && (
              <div className="glass-card">
                <h3 style={{marginBottom:'20px',display:'flex',alignItems:'center',gap:'8px'}}><Receipt size={20}/> Receipt Format</h3>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                  <div className="form-group" style={{gridColumn:'span 2'}}>
                    <label>Receipt Header Text</label>
                    <textarea className="input-field" rows={3} value={hospitalSettings.receipt_header||''} onChange={e=>setHospitalSettings({...hospitalSettings,receipt_header:e.target.value})} placeholder="Text to appear at top of receipt"/>
                  </div>
                  <div className="form-group" style={{gridColumn:'span 2'}}>
                    <label>Receipt Footer Text</label>
                    <textarea className="input-field" rows={3} value={hospitalSettings.receipt_footer||''} onChange={e=>setHospitalSettings({...hospitalSettings,receipt_footer:e.target.value})} placeholder="Text to appear at bottom of receipt (e.g. Thank you message)"/>
                  </div>
                </div>
                <div style={{marginTop:'20px',padding:'16px',background:'rgba(16,185,129,0.05)',borderRadius:'8px',border:'1px solid rgba(16,185,129,0.2)'}}>
                  <h4 style={{marginBottom:'12px',color:'var(--accent-emerald)'}}>Preview (Receipt)</h4>
                  <div style={{textAlign:'center',fontFamily:'Arial',border:'1px dashed #ccc',padding:'12px',borderRadius:'8px'}}>
                    <div style={{fontWeight:'bold'}}>{hospitalSettings.hospital_name}</div>
                    <div style={{fontSize:'11px',color:'var(--text-secondary)',marginTop:'4px'}}>{hospitalSettings.receipt_header}</div>
                    <div style={{borderTop:'1px dashed #ccc',margin:'8px 0'}}/>
                    <div style={{fontSize:'11px',color:'var(--text-secondary)'}}>... Receipt Items ...</div>
                    <div style={{borderTop:'1px dashed #ccc',margin:'8px 0'}}/>
                    <div style={{fontSize:'11px',color:'var(--text-secondary)'}}>{hospitalSettings.receipt_footer}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Printer Settings */}
            {adminSettingsTab === 'printer_settings' && (
              <div className="glass-card">
                <h3 style={{marginBottom:'20px',display:'flex',alignItems:'center',gap:'8px'}}><Printer size={20}/> Printer Settings</h3>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                  <div className="form-group">
                    <label>Paper Size</label>
                    <select className="input-field" value={hospitalSettings.paper_size||'A4'} onChange={e=>setHospitalSettings({...hospitalSettings,paper_size:e.target.value})}>
                      <option value="A4">A4 (210 × 297 mm)</option>
                      <option value="A5">A5 (148 × 210 mm)</option>
                      <option value="Letter">Letter (216 × 279 mm)</option>
                      <option value="Thermal80">Thermal 80mm</option>
                      <option value="Thermal57">Thermal 57mm</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Font Size</label>
                    <select className="input-field" value={hospitalSettings.font_size||'12'} onChange={e=>setHospitalSettings({...hospitalSettings,font_size:e.target.value})}>
                      <option value="10">10px (Small)</option>
                      <option value="12">12px (Normal)</option>
                      <option value="14">14px (Large)</option>
                      <option value="16">16px (Extra Large)</option>
                    </select>
                  </div>
                </div>
                <div style={{marginTop:'20px',padding:'16px',background:'rgba(139,92,246,0.05)',borderRadius:'8px',border:'1px solid rgba(139,92,246,0.2)'}}>
                  <p style={{color:'var(--accent-violet)',margin:0,fontSize:'14px'}}>🖨️ Paper: <strong>{hospitalSettings.paper_size}</strong> | Font Size: <strong>{hospitalSettings.font_size}px</strong></p>
                  <p style={{color:'var(--text-muted)',margin:'8px 0 0',fontSize:'12px'}}>These settings apply to all printed invoices, receipts, and reports.</p>
                </div>
              </div>
            )}

            {/* Backup & Restore */}
            {adminSettingsTab === 'backup' && (
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                <div className="glass-card">
                  <h3 style={{marginBottom:'16px',display:'flex',alignItems:'center',gap:'8px'}}><DownloadCloud size={20}/> Backup Database</h3>
                  <p style={{color:'var(--text-muted)',marginBottom:'20px',fontSize:'14px',lineHeight:'1.6'}}>
                    Download a complete backup of the hospital database including all patients, bills, inventory, and settings.
                  </p>
                  <div style={{background:'rgba(16,185,129,0.08)',borderRadius:'8px',padding:'16px',marginBottom:'20px',border:'1px solid rgba(16,185,129,0.2)'}}>
                    <div style={{display:'flex',gap:'16px',flexWrap:'wrap'}}>
                      <div style={{textAlign:'center'}}><div style={{fontSize:'24px',fontWeight:'bold',color:'var(--accent-emerald)'}}>{patients.length}</div><div style={{fontSize:'12px',color:'var(--text-muted)'}}>Patients</div></div>
                      <div style={{textAlign:'center'}}><div style={{fontSize:'24px',fontWeight:'bold',color:'var(--accent-blue)'}}>{pharmacyBills.length}</div><div style={{fontSize:'12px',color:'var(--text-muted)'}}>Pharmacy Bills</div></div>
                      <div style={{textAlign:'center'}}><div style={{fontSize:'24px',fontWeight:'bold',color:'var(--accent-violet)'}}>{inventory.length}</div><div style={{fontSize:'12px',color:'var(--text-muted)'}}>Inventory Items</div></div>
                    </div>
                  </div>
                  <button className="btn btn-primary" style={{display:'flex',alignItems:'center',gap:'8px',width:'100%',justifyContent:'center'}} onClick={handleBackupDatabase}>
                    <DownloadCloud size={18}/> Download Backup (JSON)
                  </button>
                </div>
                <div className="glass-card">
                  <h3 style={{marginBottom:'16px',display:'flex',alignItems:'center',gap:'8px'}}><UploadCloud size={20}/> Restore Database</h3>
                  <p style={{color:'var(--text-muted)',marginBottom:'20px',fontSize:'14px',lineHeight:'1.6'}}>
                    Restore your database from a previously downloaded backup file. This will overwrite existing data.
                  </p>
                  <div style={{background:'rgba(244,63,94,0.08)',borderRadius:'8px',padding:'12px',marginBottom:'20px',border:'1px solid rgba(244,63,94,0.2)'}}>
                    <p style={{color:'var(--accent-rose)',margin:0,fontSize:'13px',display:'flex',alignItems:'center',gap:'6px'}}><AlertTriangle size={16}/> <strong>Warning:</strong> Restore will replace all current data. Backup first!</p>
                  </div>
                  <input type="file" accept=".json" className="input-field" onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) { alert(`File "${file.name}" selected. Restore functionality requires manual admin review.`); }
                  }}/>
                  <button className="btn" style={{marginTop:'12px',display:'flex',alignItems:'center',gap:'8px',width:'100%',justifyContent:'center',background:'rgba(244,63,94,0.1)',color:'var(--accent-rose)',border:'1px solid rgba(244,63,94,0.3)'}}>
                    <UploadCloud size={18}/> Restore from Backup
                  </button>
                </div>
              </div>
            )}

            {/* Audit Logs */}
            {adminSettingsTab === 'audit_logs' && (
              <div className="glass-card">
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'16px',flexWrap:'wrap',gap:'10px'}}>
                  <h3 style={{display:'flex',alignItems:'center',gap:'8px',margin:0}}><Shield size={20}/> Clinical Audit Trail</h3>
                  <div style={{display:'flex',gap:'8px',alignItems:'center',flexWrap:'wrap'}}>
                    <select className="search-bar" style={{maxWidth:'190px'}} value={auditFilter.entity_type}
                      onChange={e => { const v = e.target.value; setAuditFilter(f => ({...f, entity_type: v})); loadAuditLogs({entity_type: v}); }}>
                      <option value="">All record types</option>
                      {['ip_admission','nursing_note','medication_order','medication_administration','discharge_summary'].map(t =>
                        <option key={t} value={t}>{t.replace(/_/g,' ')}</option>)}
                    </select>
                    <input className="search-bar" style={{maxWidth:'150px'}} placeholder="Patient ID"
                      value={auditFilter.patient_id}
                      onChange={e => setAuditFilter(f => ({...f, patient_id: e.target.value}))}
                      onKeyDown={e => { if (e.key === 'Enter') loadAuditLogs(); }} />
                    <input className="search-bar" style={{maxWidth:'180px'}} placeholder="Filter action…"
                      value={auditFilter.action}
                      onChange={e => setAuditFilter(f => ({...f, action: e.target.value}))}
                      onKeyDown={e => { if (e.key === 'Enter') loadAuditLogs(); }} />
                    <button className="btn" style={{display:'flex',alignItems:'center',gap:'6px',background:'rgba(59,130,246,0.1)',color:'var(--accent-blue)',border:'1px solid rgba(59,130,246,0.2)'}}
                      onClick={() => loadAuditLogs()}>
                      <RefreshCw size={16}/> Refresh
                    </button>
                  </div>
                </div>
                <p style={{fontSize:'12px',color:'var(--text-muted)',marginTop:0}}>
                  Append-only. Entries cannot be edited or deleted — pressing a row reveals the exact
                  before/after values that changed.
                </p>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Timestamp</th>
                        <th>Who</th>
                        <th>Action</th>
                        <th>Record</th>
                        <th>Details</th>
                        <th>IP</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLogs.length === 0 && (
                        <tr><td colSpan={7} style={{textAlign:'center',color:'var(--text-muted)',padding:'32px'}}>
                          <Clock size={32} style={{marginBottom:'8px',opacity:0.3}}/><br/>No audit logs yet. Actions will be logged here.
                        </td></tr>
                      )}
                      {auditLogs.map((log: any) => {
                        const changes = auditDiff(log);
                        const open = !!auditExpanded[log.id];
                        const isClinical = !!log.entity_type;
                        return (
                          <Fragment key={log.id}>
                            <tr onClick={() => (changes.length ? setAuditExpanded(p => ({...p, [log.id]: !p[log.id]})) : null)}
                                style={{cursor: changes.length ? 'pointer' : 'default',
                                        background: isClinical ? 'rgba(139,92,246,0.04)' : undefined}}>
                              <td>{log.id}</td>
                              <td style={{fontSize:'12px',color:'var(--text-muted)'}}>{new Date(log.timestamp).toLocaleString('en-IN')}</td>
                              <td>
                                <strong>{log.username || 'System'}</strong>
                                {log.actor_role && <><br/><small style={{color:'var(--text-muted)'}}>{log.actor_role}</small></>}
                              </td>
                              <td>
                                <span style={{padding:'2px 10px',borderRadius:'12px',fontSize:'11px',fontWeight:'700',whiteSpace:'nowrap',
                                  background: log.action.includes('APPROVE')?'rgba(16,185,129,0.15)':log.action.includes('DELETE')?'rgba(244,63,94,0.15)':log.action.includes('DISCHARGE')?'rgba(245,158,11,0.15)':log.action.includes('BACKUP')?'rgba(16,185,129,0.15)':'rgba(59,130,246,0.15)',
                                  color: log.action.includes('APPROVE')?'#10b981':log.action.includes('DELETE')?'#f43f5e':log.action.includes('DISCHARGE')?'#f59e0b':log.action.includes('BACKUP')?'#10b981':'#3b82f6'
                                }}>{log.action}</span>
                              </td>
                              <td style={{fontSize:'12px'}}>
                                {isClinical
                                  ? <>{log.entity_type.replace(/_/g,' ')} <b>#{log.entity_id}</b>
                                      {log.patient_id ? <><br/><small style={{color:'var(--text-muted)'}}>patient #{log.patient_id}</small></> : null}</>
                                  : <span style={{color:'var(--text-muted)'}}>—</span>}
                              </td>
                              <td style={{fontSize:'12px'}}>
                                {log.details}
                                {changes.length > 0 && <small style={{display:'block',color:'var(--primary)'}}>
                                  {open ? '▾' : '▸'} {changes.length} field{changes.length===1?'':'s'} changed
                                </small>}
                              </td>
                              <td style={{fontSize:'12px',color:'var(--text-muted)'}}>{log.ip_address||'-'}</td>
                            </tr>
                            {open && changes.length > 0 && (
                              <tr>
                                <td colSpan={7} style={{background:'rgba(15,23,42,0.35)',padding:'14px'}}>
                                  <table style={{width:'100%',fontSize:'12px'}}>
                                    <thead>
                                      <tr>
                                        <th style={{textAlign:'left'}}>Field</th>
                                        <th style={{textAlign:'left'}}>Before</th>
                                        <th style={{textAlign:'left'}}>After</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {changes.map(c => (
                                        <tr key={c.field}>
                                          <td style={{fontWeight:600}}>{c.field}</td>
                                          <td style={{color:'var(--accent-rose)',wordBreak:'break-word'}}>{renderAuditValue(c.before)}</td>
                                          <td style={{color:'var(--accent-emerald)',wordBreak:'break-word'}}>{renderAuditValue(c.after)}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

          </div>
        )}

      </div>

      {/* Global Overlays */}
      {globalLoading && (
        <div style={{position:'fixed', top:0, left:0, right:0, bottom:0, background:'rgba(0,0,0,0.5)', zIndex:9999, display:'flex', justifyContent:'center', alignItems:'center', backdropFilter:'blur(4px)'}}>
          <div style={{background:'var(--bg-card)', padding:'24px', borderRadius:'12px', display:'flex', flexDirection:'column', alignItems:'center', gap:'12px', color:'var(--primary)'}}>
            <Loader2 size={32} className="animate-spin" />
            <span style={{fontWeight:'bold'}}>Processing...</span>
          </div>
        </div>
      )}
      {/* ============ PATIENT 360 (staff view of one patient) ============ */}
      {patientDetail && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '1080px', width: '95%', maxHeight: '92vh', overflowY: 'auto' }}>
            <div className="modal-header">
              <h2>Patient 360 — {patientDetail.patient?.name || 'Loading…'}</h2>
              <button className="close-btn" onClick={() => setPatientDetail(null)}><X size={20} /></button>
            </div>
            <div className="modal-body">
              {patientDetailLoading ? (
                <div style={{ textAlign: 'center', padding: '40px' }}><Loader2 size={28} className="spin" /> Loading record…</div>
              ) : (
                <>
                  {/* Demographics */}
                  <div className="glass-card" style={{ padding: '14px', marginBottom: '14px' }}>
                    <div className="form-grid">
                      <div><small style={{ color: 'var(--text-muted)' }}>Patient ID</small><br /><b>#{patientDetail.patient?.id}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Name</small><br /><b>{patientDetail.patient?.name}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Age / Gender</small><br /><b>{patientDetail.patient?.age} / {patientDetail.patient?.gender}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Phone</small><br /><b>{patientDetail.patient?.phone || '-'}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Blood group</small><br /><b>{patientDetail.patient?.blood_group || '-'}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Total billed</small><br /><b>₹{(patientDetail.billed || 0).toFixed(2)}</b></div>
                    </div>
                  </div>

                  {/* Summary tiles */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px', marginBottom: '14px' }}>
                    {[
                      { label: 'Prescriptions', value: patientDetail.sheets?.length || 0 },
                      { label: 'Lab orders', value: patientDetail.orders?.length || 0 },
                      { label: 'Lab reports', value: patientDetail.reports?.length || 0 },
                      { label: 'OP bills', value: patientDetail.opBills?.length || 0 },
                      { label: 'IP bills', value: patientDetail.ipBills?.length || 0 },
                      { label: 'Lab bills', value: patientDetail.labBills?.length || 0 },
                      { label: 'Admissions', value: patientDetail.admissions?.length || 0 },
                      { label: 'Claims', value: patientDetail.claims?.length || 0 },
                    ].map(t => (
                      <div key={t.label} style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '10px', textAlign: 'center' }}>
                        <div style={{ fontSize: '20px', fontWeight: 800 }}>{t.value}</div>
                        <small style={{ color: 'var(--text-muted)' }}>{t.label}</small>
                      </div>
                    ))}
                  </div>

                  {/* Prescriptions */}
                  <h3 style={{ marginTop: 0 }}>Prescriptions</h3>
                  {(patientDetail.sheets || []).length === 0 && <p style={{ color: 'var(--text-muted)' }}>None recorded.</p>}
                  {(patientDetail.sheets || []).map((s: any) => (
                    <div key={s.id} className="glass-card" style={{ padding: '12px', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                        <div>
                          <b>{new Date(s.date).toDateString()}</b>
                          <small style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>{s.doctor_name || 'Doctor not recorded'}</small>
                          {s.diagnosis && <div style={{ fontSize: '13px', marginTop: '4px' }}>{s.diagnosis}</div>}
                        </div>
                        <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                          onClick={() => {
                            const w = window.open('', '_blank');
                            if (!w) return;
                            w.document.write(`<html><head><title>Prescription ${s.id}</title><style>body{font-family:Arial;padding:24px}table{width:100%;border-collapse:collapse;font-size:13px}th{background:#1e40af;color:#fff;padding:6px;text-align:left}td{padding:6px;border-bottom:1px solid #ddd}</style></head><body><h2>Prescription #${s.id}</h2><p><b>Patient:</b> ${patientDetail.patient?.name} &nbsp; <b>Date:</b> ${new Date(s.date).toLocaleDateString()} &nbsp; <b>Doctor:</b> ${s.doctor_name || '-'}</p>${s.diagnosis ? `<p><b>Diagnosis:</b> ${s.diagnosis}</p>` : ''}<table><thead><tr><th>Medicine</th><th>Qty</th><th>Duration</th><th>Instructions</th></tr></thead><tbody>${(s.prescribed_medicines || []).map((m: any) => `<tr><td>${m.name}</td><td>${m.quantity ?? ''}</td><td>${m.duration || ''}</td><td>${m.instructions || ''}</td></tr>`).join('')}</tbody></table>${s.advice ? `<p><b>Advice:</b> ${s.advice}</p>` : ''}</body></html>`);
                            w.document.close(); w.print();
                          }}><Printer size={13} /> Print</button>
                      </div>
                      {(s.prescribed_medicines || []).length > 0 && (
                        <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
                          {s.prescribed_medicines.map((m: any) => `${m.name}${m.quantity ? ` ×${m.quantity}` : ''}`).join(' · ')}
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Lab */}
                  <h3>Laboratory</h3>
                  {(patientDetail.orders || []).length === 0 && <p style={{ color: 'var(--text-muted)' }}>No lab tests ordered.</p>}
                  {(patientDetail.orders || []).length > 0 && (
                    <div className="table-container">
                      <table>
                        <thead><tr><th>Order</th><th>Test</th><th>Ordered</th><th>Status</th><th>Bill</th><th></th></tr></thead>
                        <tbody>
                          {patientDetail.orders.map((o: any) => (
                            <tr key={o.id}>
                              <td>#{o.id}</td>
                              <td>{o.test?.test_name || labTestMasters.find(t => t.id === o.test_id)?.test_name || `Test #${o.test_id}`}</td>
                              <td>{new Date(o.order_date).toLocaleDateString()}</td>
                              <td><span className={`status-badge ${(o.status || '').replace(/ /g, '-').toLowerCase()}`}>{o.status}</span></td>
                              <td>{o.bill_id ? `#${o.bill_id}` : 'unbilled'}</td>
                              <td>
                                {o.status === 'Verified' && (
                                  <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }}
                                    onClick={() => {
                                      const r = labReports.find(x => x.order_id === o.id);
                                      if (r) printLabReport(r); else showToast('Report still generating', 'error');
                                    }}><Printer size={13} /> Report</button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Bills */}
                  <h3>Bills</h3>
                  {[...(patientDetail.opBills || []), ...(patientDetail.ipBills || []), ...(patientDetail.labBills || [])].length === 0
                    ? <p style={{ color: 'var(--text-muted)' }}>No bills raised.</p>
                    : (
                      <div className="table-container">
                        <table>
                          <thead><tr><th>Type</th><th>Bill</th><th>Date</th><th>Total</th><th>Status</th></tr></thead>
                          <tbody>
                            {[
                              ...(patientDetail.opBills || []).map((b: any) => ({ ...b, _t: 'OP' })),
                              ...(patientDetail.ipBills || []).map((b: any) => ({ ...b, _t: 'IP' })),
                              ...(patientDetail.labBills || []).map((b: any) => ({ ...b, _t: 'Laboratory' })),
                            ].map((b: any) => (
                              <tr key={`${b._t}-${b.id}`}>
                                <td>{b._t}</td>
                                <td>#{b.id}</td>
                                <td>{new Date(b.bill_date).toLocaleDateString()}</td>
                                <td><b>₹{b.total?.toFixed(2)}</b></td>
                                <td>{b.status || 'Paid'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                  {/* Admissions + insurance */}
                  {(patientDetail.admissions || []).length > 0 && (
                    <>
                      <h3>Admissions</h3>
                      <div className="table-container">
                        <table>
                          <thead><tr><th>#</th><th>Admitted</th><th>Discharged</th><th>Ward / Room</th><th>Doctor</th><th>Status</th></tr></thead>
                          <tbody>
                            {patientDetail.admissions.map((a: any) => (
                              <tr key={a.id}>
                                <td>#{a.id}</td>
                                <td>{new Date(a.admission_date).toLocaleDateString()}</td>
                                <td>{a.discharge_date ? new Date(a.discharge_date).toLocaleDateString() : '-'}</td>
                                <td>{a.ward_number || '-'} / {a.room_number || '-'}</td>
                                <td>{a.doctor_in_charge || '-'}</td>
                                <td><span className={`status-badge ${(a.status || '').toLowerCase()}`}>{a.status}</span></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}

                  {(patientDetail.policies || []).length > 0 && (
                    <>
                      <h3>Insurance</h3>
                      <div className="table-container">
                        <table>
                          <thead><tr><th>Provider</th><th>Policy</th><th>Plan</th><th>Sum insured</th><th>Status</th></tr></thead>
                          <tbody>
                            {patientDetail.policies.map((p: any) => (
                              <tr key={p.id}>
                                <td>{p.provider}</td><td>{p.policy_number}</td><td>{p.plan_name || '-'}</td>
                                <td>₹{(p.sum_insured || 0).toFixed(0)}</td>
                                <td><span className={`status-badge ${p.is_active ? 'completed' : 'cancelled'}`}>{p.is_active ? 'Active' : 'Inactive'}</span></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ============ INPATIENT ADMISSION RECORD ============ */}
      {admissionDetail && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '1180px', width: '96%', maxHeight: '93vh', overflowY: 'auto' }}>
            <div className="modal-header">
              <h2>
                Ward Record — {admissionDetail.patient?.name || 'Loading…'}
                {admissionDetail.id ? (
                  <span className={`status-badge ${(admissionDetail.status || '').toLowerCase()}`} style={{ marginLeft: '10px' }}>
                    {admissionDetail.status}
                  </span>
                ) : null}
              </h2>
              <button className="close-btn" onClick={() => { setAdmissionDetail(null); setIsDischargeOpen(false); }}>
                <X size={20} />
              </button>
            </div>
            <div className="modal-body">
              {admissionDetail.loading ? (
                <div style={{ textAlign: 'center', padding: '40px' }}><Loader2 size={26} className="spin" /> Loading record…</div>
              ) : (
                <>
                  {/* Header facts */}
                  <div className="glass-card" style={{ padding: '14px', marginBottom: '14px' }}>
                    <div className="form-grid">
                      <div><small style={{ color: 'var(--text-muted)' }}>Patient</small><br /><b>{admissionDetail.patient?.name}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Age / Gender</small><br /><b>{admissionDetail.patient?.age} / {admissionDetail.patient?.gender}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Bed</small><br /><b>{admissionDetail.bed?.bed_code || '—'}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Location</small><br /><b>{admissionDetail.ward_number || '—'} · {admissionDetail.room_number || '—'}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Admitted</small><br /><b>{new Date(admissionDetail.admission_date).toLocaleString()}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Length of stay</small><br /><b>{admissionDetail.length_of_stay_days} day(s)</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Type / Source</small><br /><b>{admissionDetail.admission_type} · {admissionDetail.admission_source || '—'}</b></div>
                      <div><small style={{ color: 'var(--text-muted)' }}>Room charge</small><br /><b>₹{admissionDetail.billable_room_charge}</b></div>
                    </div>
                    {admissionDetail.reason_for_admission && (
                      <p style={{ marginTop: '10px', fontSize: '13px' }}><b>Reason:</b> {admissionDetail.reason_for_admission}</p>
                    )}
                    {admissionDetail.provisional_diagnosis && (
                      <p style={{ margin: '4px 0 0', fontSize: '13px' }}><b>Provisional diagnosis:</b> {admissionDetail.provisional_diagnosis}</p>
                    )}
                  </div>

                  {admissionDetail.status === 'Admitted' ? (
                    <>
                      {/* Transfer + discharge */}
                      <div className="glass-card" style={{ padding: '14px', marginBottom: '14px' }}>
                        <h3 style={{ marginTop: 0 }}>Bed &amp; discharge</h3>
                        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                          <div className="form-group" style={{ minWidth: '240px' }}>
                            <label>Transfer to bed</label>
                            <select value={transferTargetBedId} onChange={e => setTransferTargetBedId(e.target.value)}>
                              <option value="">— choose a free bed —</option>
                              {bedBoard.filter(b => b.status === 'Available').map(b => (
                                <option key={b.bed_id} value={b.bed_id}>{b.ward_name} / {b.room_number} / {b.bed_code}</option>
                              ))}
                            </select>
                          </div>
                          <button className="btn btn-secondary" onClick={handleTransferBed} disabled={!transferTargetBedId}>
                            <ArrowRightCircle size={16} /> Transfer
                          </button>
                          <button className="btn btn-primary" onClick={() => setIsDischargeOpen(true)}>
                            <CheckCircle2 size={16} /> Discharge patient
                          </button>
                        </div>

                        {isDischargeOpen && (
                          <div style={{ marginTop: '14px', padding: '12px', border: '1px solid var(--border)', borderRadius: '8px' }}>
                            <p style={{ marginTop: 0, fontSize: '13px' }}>
                              A discharge summary is required. Save one below, or switch the requirement off to
                              discharge immediately.
                            </p>
                            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                              <select value={dischargeForm.discharge_type}
                                onChange={e => setDischargeForm({ ...dischargeForm, discharge_type: e.target.value })}>
                                {['Routine', 'Transfer', 'Against Medical Advice', 'Expired', 'Absconded'].map(t => <option key={t}>{t}</option>)}
                              </select>
                              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
                                <input type="checkbox" checked={dischargeForm.require_summary}
                                  onChange={e => setDischargeForm({ ...dischargeForm, require_summary: e.target.checked })} />
                                Require a saved summary
                              </label>
                              <button className="btn btn-danger" onClick={handleDischarge}>Confirm discharge</button>
                              <button className="btn btn-secondary" onClick={() => setIsDischargeOpen(false)}>Cancel</button>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Nursing chart */}
                      <div className="glass-card" style={{ padding: '14px', marginBottom: '14px' }}>
                        <h3 style={{ marginTop: 0 }}>Nursing chart — vitals</h3>
                        <form onSubmit={handleAddNursingNote}>
                          <div className="form-grid">
                            <div className="form-group"><label>Shift</label>
                              <select value={nursingForm.shift} onChange={e => setNursingForm({ ...nursingForm, shift: e.target.value })}>
                                {['Morning', 'Evening', 'Night'].map(s => <option key={s}>{s}</option>)}
                              </select></div>
                            {([['temperature', 'Temp (°C)'], ['pulse', 'Pulse (bpm)'], ['respiratory_rate', 'Resp (/min)'],
                               ['bp_systolic', 'BP systolic'], ['bp_diastolic', 'BP diastolic'], ['spo2', 'SpO₂ (%)'],
                               ['pain_score', 'Pain (0-10)'], ['blood_sugar', 'Blood sugar'], ['intake_ml', 'Intake (ml)'],
                               ['output_ml', 'Output (ml)']] as [keyof typeof nursingForm, string][]).map(([key, label]) => (
                              <div className="form-group" key={key}><label>{label}</label>
                                <input type="number" step="any" value={nursingForm[key] as string}
                                  onChange={e => setNursingForm({ ...nursingForm, [key]: e.target.value })} /></div>
                            ))}
                            <div className="form-group" style={{ gridColumn: '1 / -1' }}><label>Notes</label>
                              <input type="text" value={nursingForm.notes}
                                onChange={e => setNursingForm({ ...nursingForm, notes: e.target.value })} /></div>
                          </div>
                          <button type="submit" className="btn btn-primary" style={{ marginTop: '10px' }} disabled={admissionDetailBusy}>
                            <Save size={16} /> Chart vitals
                          </button>
                        </form>

                        <div className="table-container" style={{ marginTop: '14px', maxHeight: '280px', overflowY: 'auto' }}>
                          <table>
                            <thead><tr><th>When</th><th>Shift</th><th>Temp</th><th>Pulse</th><th>BP</th><th>SpO₂</th><th>By</th></tr></thead>
                            <tbody>
                              {(admissionDetail.nursing_notes || []).map((n: any) => (
                                <tr key={n.id} style={n.is_critical ? { background: 'rgba(239,68,68,0.08)' } : undefined}>
                                  <td>{new Date(n.recorded_at).toLocaleString()}</td>
                                  <td>{n.shift}</td>
                                  <td>{n.temperature ?? '—'}</td>
                                  <td>{n.pulse ?? '—'}</td>
                                  <td>{n.bp_systolic && n.bp_diastolic ? `${n.bp_systolic}/${n.bp_diastolic}` : '—'}</td>
                                  <td style={n.spo2 && n.spo2 < 92 ? { color: 'var(--danger)', fontWeight: 700 } : undefined}>{n.spo2 ?? '—'}</td>
                                  <td>{n.recorded_by || '—'}{n.is_critical ? ' ⚠' : ''}</td>
                                </tr>
                              ))}
                              {(admissionDetail.nursing_notes || []).length === 0 && (
                                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No vitals charted yet.</td></tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Medication */}
                      <div className="glass-card" style={{ padding: '14px', marginBottom: '14px' }}>
                        <h3 style={{ marginTop: 0 }}>Medication orders &amp; administration</h3>
                        <form onSubmit={handleAddMedication}>
                          <div className="form-grid">
                            <div className="form-group"><label>Medicine *</label>
                              <input type="text" required value={medicationForm.medicine_name}
                                onChange={e => setMedicationForm({ ...medicationForm, medicine_name: e.target.value })} /></div>
                            <div className="form-group"><label>Dose</label>
                              <input type="text" placeholder="500 mg" value={medicationForm.dose}
                                onChange={e => setMedicationForm({ ...medicationForm, dose: e.target.value })} /></div>
                            <div className="form-group"><label>Route</label>
                              <select value={medicationForm.route} onChange={e => setMedicationForm({ ...medicationForm, route: e.target.value })}>
                                {['Oral', 'IV', 'IM', 'SC', 'Topical', 'Inhalation', 'Rectal', 'Nasal', 'Ophthalmic'].map(r => <option key={r}>{r}</option>)}
                              </select></div>
                            <div className="form-group"><label>Frequency</label>
                              <select value={medicationForm.frequency} onChange={e => setMedicationForm({ ...medicationForm, frequency: e.target.value })}>
                                {['OD', 'BD', 'TDS', 'QID', 'HS', 'SOS', 'STAT', 'Weekly'].map(f => <option key={f}>{f}</option>)}
                              </select></div>
                          </div>
                          <button type="submit" className="btn btn-primary" style={{ marginTop: '10px' }} disabled={admissionDetailBusy}>
                            <PlusCircle size={16} /> Prescribe
                          </button>
                        </form>

                        <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                          {(admissionDetail.medication_orders || []).map((o: any) => (
                            <div key={o.id} style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '10px' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                                <div>
                                  <b>{o.medicine_name}</b> <small style={{ color: 'var(--text-muted)' }}>{o.dose || ''} · {o.route} · {o.frequency}</small>
                                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                                    Prescribed by {o.prescribed_by || '—'} on {new Date(o.start_date).toLocaleString()}
                                    {o.stop_reason ? ` · stopped: ${o.stop_reason}` : ''}
                                  </div>
                                </div>
                                <span className={`status-badge ${(o.status || '').toLowerCase()}`}>{o.status}</span>
                              </div>
                              {o.status === 'Active' && (
                                <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
                                  <button className="btn btn-primary" style={{ padding: '3px 9px', fontSize: '11px' }}
                                    onClick={() => handleAdminister(o.id, 'Given')}>Given</button>
                                  <button className="btn btn-secondary" style={{ padding: '3px 9px', fontSize: '11px' }}
                                    onClick={() => handleAdminister(o.id, 'Held')}>Held</button>
                                  <button className="btn btn-secondary" style={{ padding: '3px 9px', fontSize: '11px' }}
                                    onClick={() => handleAdminister(o.id, 'Refused')}>Refused</button>
                                  <button className="btn btn-danger" style={{ padding: '3px 9px', fontSize: '11px' }}
                                    onClick={() => handleStopMedication(o.id)}>Stop</button>
                                </div>
                              )}
                              {(o.administrations || []).length > 0 && (
                                <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                                  {(o.administrations || []).slice(0, 5).map((a: any) => (
                                    <div key={a.id}>
                                      {new Date(a.administered_at).toLocaleString()} — {a.status}
                                      {a.dose_given ? ` (${a.dose_given})` : ''} by {a.administered_by || '—'}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                          {(admissionDetail.medication_orders || []).length === 0 && (
                            <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No medication orders.</p>
                          )}
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="glass-card" style={{ padding: '14px', marginBottom: '14px', background: 'rgba(16,185,129,0.06)' }}>
                      <b>This admission is {admissionDetail.status}.</b>
                      <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                        Discharged {admissionDetail.discharge_date ? new Date(admissionDetail.discharge_date).toLocaleString() : ''}
                        {admissionDetail.discharge_type ? ` · ${admissionDetail.discharge_type}` : ''}
                        {admissionDetail.discharged_by ? ` · by ${admissionDetail.discharged_by}` : ''}
                      </div>
                    </div>
                  )}

                  {/* Discharge summary */}
                  <div className="glass-card" style={{ padding: '14px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                      <h3 style={{ margin: 0 }}>Discharge summary</h3>
                      {admissionDetail.discharge_summary && (
                        <span className={`status-badge ${(admissionDetail.discharge_summary.status || '').toLowerCase()}`}>
                          {admissionDetail.discharge_summary.status}
                        </span>
                      )}
                    </div>
                    {admissionDetail.discharge_summary?.status === 'Approved' ? (
                      <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                        Approved by {admissionDetail.discharge_summary.approved_by} on{' '}
                        {new Date(admissionDetail.discharge_summary.approved_at).toLocaleString()}. This summary is locked.
                      </p>
                    ) : (
                      <>
                        <div className="form-grid" style={{ marginTop: '10px' }}>
                          <div className="form-group"><label>Discharge type</label>
                            <select value={dischargeSummaryForm.discharge_type}
                              onChange={e => setDischargeSummaryForm({ ...dischargeSummaryForm, discharge_type: e.target.value })}>
                              {['Routine', 'Transfer', 'Against Medical Advice', 'Expired', 'Absconded'].map(t => <option key={t}>{t}</option>)}
                            </select></div>
                          <div className="form-group"><label>Condition at discharge</label>
                            <select value={dischargeSummaryForm.condition_at_discharge}
                              onChange={e => setDischargeSummaryForm({ ...dischargeSummaryForm, condition_at_discharge: e.target.value })}>
                              {['Stable', 'Improved', 'Unchanged', 'Deteriorated', 'Cured'].map(c => <option key={c}>{c}</option>)}
                            </select></div>
                          <div className="form-group"><label>Follow-up date</label>
                            <input type="date" value={dischargeSummaryForm.follow_up_date}
                              onChange={e => setDischargeSummaryForm({ ...dischargeSummaryForm, follow_up_date: e.target.value })} /></div>
                          <div className="form-group"><label>Final diagnosis</label>
                            <input type="text" value={dischargeSummaryForm.final_diagnosis}
                              onChange={e => setDischargeSummaryForm({ ...dischargeSummaryForm, final_diagnosis: e.target.value })} /></div>
                        </div>
                        {([['procedures_performed', 'Procedures performed'], ['investigations', 'Investigations'],
                           ['medication_summary', 'Medication on discharge'], ['diet_advice', 'Diet advice'],
                           ['activity_advice', 'Activity advice'], ['follow_up_instructions', 'Follow-up instructions']] as [keyof typeof dischargeSummaryForm, string][])
                          .map(([key, label]) => (
                            <div className="form-group" key={key} style={{ marginTop: '10px' }}>
                              <label>{label}</label>
                              <textarea rows={2} style={{ width: '100%' }} value={dischargeSummaryForm[key] as string}
                                onChange={e => setDischargeSummaryForm({ ...dischargeSummaryForm, [key]: e.target.value })} />
                            </div>
                          ))}
                        <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
                          <button className="btn btn-primary" onClick={handleSaveDischargeSummary} disabled={admissionDetailBusy}>
                            <Save size={16} /> Save draft
                          </button>
                          {admissionDetail.discharge_summary && admissionDetail.discharge_summary.status === 'Draft' && (
                            <button className="btn btn-secondary" onClick={() => handleDischargeSummaryStatus('Final')}>
                              <CheckCircle size={16} /> Finalise
                            </button>
                          )}
                          {admissionDetail.discharge_summary && admissionDetail.discharge_summary.status === 'Final' && (
                            <button className="btn btn-secondary" onClick={() => handleDischargeSummaryStatus('Approved')}>
                              <CheckCircle2 size={16} /> Approve
                            </button>
                          )}
                          <button className="btn btn-secondary" onClick={() => {
                            const s = admissionDetail.discharge_summary;
                            if (!s) return showToast('Save the summary first', 'error');
                            const p = admissionDetail.patient || {};
                            const w = window.open('', '_blank');
                            if (!w) return;
                            w.document.write(`<html><head><title>Discharge Summary ${s.id}</title><style>
                              body{font-family:Arial;padding:28px;color:#111}
                              .head{text-align:center;border-bottom:2px solid #1e40af;padding-bottom:10px;margin-bottom:16px}
                              .head h1{margin:0;color:#1e40af;font-size:20px}
                              h3{margin:16px 0 4px;font-size:14px;color:#1e40af}
                              p{margin:2px 0;font-size:13px}
                              .grid{display:flex;justify-content:space-between;font-size:13px;margin-bottom:12px}
                              @media print{body{padding:8px}}
                            </style></head><body>
                              <div class="head"><h1>${hospitalSettings.hospital_name || 'MedBill Pro Hospital'}</h1>
                              <p>${hospitalSettings.address || ''}</p></div>
                              <h2 style="text-align:center;margin:6px 0 14px">DISCHARGE SUMMARY</h2>
                              <div class="grid">
                                <div><b>Patient:</b> ${p.name || ''}<br><b>Age / Gender:</b> ${p.age ?? ''} / ${p.gender || ''}<br>
                                <b>Patient ID:</b> ${admissionDetail.patient_id}<br><b>Phone:</b> ${p.phone || ''}</div>
                                <div style="text-align:right"><b>Summary No:</b> #${s.id}<br>
                                <b>Admitted:</b> ${new Date(admissionDetail.admission_date).toLocaleString()}<br>
                                <b>Discharged:</b> ${admissionDetail.discharge_date ? new Date(admissionDetail.discharge_date).toLocaleString() : '—'}<br>
                                <b>Ward / Bed:</b> ${admissionDetail.ward_number || ''} / ${admissionDetail.bed?.bed_code || ''}</div>
                              </div>
                              <h3>Final diagnosis</h3><p>${s.final_diagnosis || '—'}</p>
                              <h3>Procedures performed</h3><p>${s.procedures_performed || '—'}</p>
                              <h3>Investigations</h3><p>${s.investigations || '—'}</p>
                              <h3>Condition at discharge</h3><p>${s.condition_at_discharge || '—'}</p>
                              <h3>Medication on discharge</h3><p>${(s.medication_summary || '—').replace(/\\n/g, '<br>')}</p>
                              <h3>Diet &amp; activity</h3><p>${s.diet_advice || '—'}<br>${s.activity_advice || '—'}</p>
                              <h3>Follow-up</h3><p>${s.follow_up_instructions || '—'}${s.follow_up_date ? ' — on ' + new Date(s.follow_up_date).toLocaleDateString() : ''}</p>
                              <div class="grid" style="margin-top:26px">
                                <div>Prepared by: <b>${s.prepared_by || '—'}</b></div>
                                <div style="text-align:right">Approved by: <b>${s.approved_by || '—'}</b></div>
                              </div>
                            </body></html>`);
                            w.document.close(); w.focus(); w.print();
                          }}><Printer size={16} /> Print / Save PDF</button>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Clinical change history — who did what, and when */}
                  {admissionTrail.length > 0 && (
                    <div className="glass-card" style={{ padding: '14px', marginTop: '14px' }}>
                      <h3 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Shield size={18} /> Clinical history
                        <small style={{ fontWeight: 400, color: 'var(--text-muted)' }}>append-only</small>
                      </h3>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '320px', overflowY: 'auto' }}>
                        {admissionTrail.map((entry: any) => (
                          <div key={entry.id} style={{
                            display: 'flex', gap: '10px', alignItems: 'flex-start',
                            padding: '8px 10px', borderRadius: '8px',
                            border: '1px solid var(--border)',
                            borderLeft: `3px solid ${entry.action.includes('DISCHARG') ? '#f59e0b'
                              : entry.action.includes('CRITICAL') || entry.action.includes('STOPPED') ? '#f43f5e'
                              : '#3b82f6'}`,
                          }}>
                            <div style={{ minWidth: '132px', fontSize: '11px', color: 'var(--text-muted)' }}>
                              {new Date(entry.timestamp).toLocaleString('en-IN')}
                            </div>
                            <div style={{ flex: 1 }}>
                              <b style={{ fontSize: '12px' }}>{entry.action.replace(/_/g, ' ')}</b>
                              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{entry.details}</div>
                            </div>
                            <div style={{ fontSize: '11px', textAlign: 'right', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                              {entry.username}{entry.actor_role ? <><br/>{entry.actor_role}</> : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* History */}
                  {(admissionDetail.allocations || []).length > 0 && (
                    <div className="glass-card" style={{ padding: '14px', marginTop: '14px' }}>
                      <h3 style={{ marginTop: 0 }}>Bed history</h3>
                      <div className="table-container">
                        <table>
                          <thead><tr><th>Bed</th><th>From</th><th>To</th><th>By</th><th>Reason</th></tr></thead>
                          <tbody>
                            {(admissionDetail.allocations || []).map((a: any) => (
                              <tr key={a.id}>
                                <td>{a.bed?.bed_code || `#${a.bed_id}`}</td>
                                <td>{new Date(a.allocated_at).toLocaleString()}</td>
                                <td>{a.released_at ? new Date(a.released_at).toLocaleString() : 'current'}</td>
                                <td>{a.allocated_by || '—'}{a.released_by ? ` / ${a.released_by}` : ''}</td>
                                <td>{a.release_reason || '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div style={{position:'fixed', bottom:'24px', right:'24px', zIndex:9999, background: toast.type === 'success' ? '#10b981' : '#ef4444', color:'#fff', padding:'12px 24px', borderRadius:'8px', display:'flex', alignItems:'center', gap:'8px', boxShadow:'0 4px 12px rgba(0,0,0,0.15)', animation:'slideIn 0.3s ease-out'}}>
          {toast.type === 'success' ? <CheckCircle2 size={18}/> : <AlertTriangle size={18}/>}
          <span style={{fontWeight:500}}>{toast.message}</span>
        </div>
      )}
    </div>
  );
}
