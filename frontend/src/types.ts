/** Shapes of the API resources used across the staff application. */

export interface Patient {
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

export interface OPToken {
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

export interface Appointment {
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

export interface MedicineStock {
  id: number;
  name: string;
  category: string;
  batch_no?: string;
  expiry_date?: string;
  quantity: number;
  unit_price: number;
  min_stock_level: number;
  details?: Record<string, any>;
  sellable_quantity?: number;
}

export interface MedicineBatch {
  id: number;
  medicine_id: number;
  batch_number: string;
  expiry_date?: string | null;
  quantity: number;
  received_at: string;
}

export interface BillSettlement {
  payment_status?: 'Pending' | 'Partial' | 'Paid' | 'Cancelled';
  amount_paid?: number;
  amount_due?: number;
  cancelled_reason?: string | null;
}

export interface ClearanceCheck { key: string; label: string; status: 'ok' | 'warning' | 'info'; detail: string; }
export interface DischargeClearance { ready: boolean; outstanding_amount: number; unbilled_amount: number; checks: ClearanceCheck[]; }

export interface PharmacyBillItem {
  id?: number;
  medicine_id: number;
  medicine_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface PharmacyBill {
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

export interface IPAdmission {
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

export interface OPBill extends BillSettlement {
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

export interface IPBill extends BillSettlement {
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

export interface SearchResultItem {
  type: string;
  id: number;
  patient_id?: number;
  patient_name?: string;
  detail: string;
  date?: string;
  amount?: number;
}

export interface DailyReport {
  date: string;
  op_revenue: number;
  ip_revenue: number;
  pharmacy_revenue: number;
  lab_revenue: number;
  total_revenue: number;
  total_patients: number;
  total_bills: number;
}

export interface User {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
  patient_id?: number | null;
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
  /** Bootstrap admin or admin-reset password: must be replaced before anything else. */
  must_change_password?: boolean;
}
