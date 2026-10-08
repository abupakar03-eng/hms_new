/**
 * Printable documents (invoices, reports, prescriptions) opened in their own window.
 *
 * Every value interpolated into `html\`...\`` is HTML-escaped unless it is itself
 * the output of `html` (or wrapped in `raw`). The print window shares the app's
 * origin, so an unescaped patient name like `<img src=x onerror=...>` would run
 * with the signed-in user's session; escaping by default makes that impossible
 * to forget.
 */

export class SafeHtml {
  constructor(readonly value: string) {}
  toString() { return this.value; }
}

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, ch => ESCAPES[ch]);
}

function render(value: unknown): string {
  if (value instanceof SafeHtml) return value.value;
  if (Array.isArray(value)) return value.map(render).join('');
  if (value === null || value === undefined || value === false) return '';
  return escapeHtml(value);
}

/** Tagged template: interpolations are escaped; nested `html` and arrays of it are kept. */
export function html(strings: TemplateStringsArray, ...values: unknown[]): SafeHtml {
  let out = strings[0];
  values.forEach((value, i) => { out += render(value) + strings[i + 1]; });
  return new SafeHtml(out);
}

/** Trusted markup that must not be escaped (only for constants written in this codebase). */
export const raw = (markup: string) => new SafeHtml(markup);

export function openPrintWindow(title: string, body: SafeHtml, css = ''): boolean {
  const win = window.open('', '_blank');
  if (!win) return false;
  win.document.write(
    `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>` +
    `<style>${css}</style></head><body>${body.value}</body></html>`,
  );
  win.document.close();
  win.focus();
  win.print();
  return true;
}

// ---------------------------------------------------------------------------
// Money
// ---------------------------------------------------------------------------
export const money = (n: number | null | undefined) =>
  `₹${(Number(n) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const ONES = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve',
  'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
const TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];

function belowThousand(n: number): string {
  const parts: string[] = [];
  if (n >= 100) { parts.push(`${ONES[Math.floor(n / 100)]} Hundred`); n %= 100; }
  if (n >= 20) { parts.push(TENS[Math.floor(n / 10)] + (n % 10 ? ` ${ONES[n % 10]}` : '')); }
  else if (n > 0) { parts.push(ONES[n]); }
  return parts.join(' ');
}

/** Whole number in the Indian system: 12,34,567 -> "Twelve Lakh Thirty Four Thousand ...". */
export function numberToWordsIndian(n: number): string {
  n = Math.floor(Math.abs(n));
  if (n === 0) return 'Zero';
  const parts: string[] = [];
  const crore = Math.floor(n / 1e7); n %= 1e7;
  const lakh = Math.floor(n / 1e5); n %= 1e5;
  const thousand = Math.floor(n / 1e3); n %= 1e3;
  if (crore) parts.push(`${numberToWordsIndian(crore)} Crore`);
  if (lakh) parts.push(`${belowThousand(lakh)} Lakh`);
  if (thousand) parts.push(`${belowThousand(thousand)} Thousand`);
  if (n) parts.push(belowThousand(n));
  return parts.join(' ');
}

/** "Rupees One Thousand Two Hundred and Fifty Paise Only". */
export function amountInWords(amount: number): string {
  const paiseTotal = Math.round(Math.abs(Number(amount) || 0) * 100);
  const rupees = Math.floor(paiseTotal / 100);
  const paise = paiseTotal % 100;
  return `Rupees ${numberToWordsIndian(rupees)}${paise ? ` and ${numberToWordsIndian(paise)} Paise` : ''} Only`;
}

// ---------------------------------------------------------------------------
// GST
// ---------------------------------------------------------------------------
export interface GstBreakdown {
  subtotal: number;
  discount: number;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
}

const round2 = (n: number) => Math.round((n + Number.EPSILON) * 100) / 100;

/**
 * Same arithmetic as the backend (discount on the subtotal, GST on what remains).
 * Intra-state supply splits GST equally into CGST and SGST; inter-state is IGST.
 */
export function gstBreakdown(subtotal: number, discountPct: number, gstPct: number, interState = false): GstBreakdown {
  const discount = round2((discountPct / 100) * subtotal);
  const taxable = round2(subtotal - discount);
  const tax = round2((gstPct / 100) * taxable);
  const half = round2(tax / 2);
  return {
    subtotal: round2(subtotal),
    discount,
    taxable,
    cgst: interState ? 0 : half,
    sgst: interState ? 0 : round2(tax - half),
    igst: interState ? tax : 0,
    total: round2(taxable + tax),
  };
}

// ---------------------------------------------------------------------------
// Invoice
// ---------------------------------------------------------------------------
export type InvoiceKind = 'op' | 'ip' | 'pharmacy' | 'lab';

export interface InvoiceInput {
  kind: InvoiceKind;
  bill: any;
  patient?: { name?: string; age?: number; gender?: string; phone?: string; address?: string; id?: number } | null;
  settings: Record<string, string | undefined>;
}

interface Line { description: string; detail?: string; amount: number; }

function invoiceLines(kind: InvoiceKind, bill: any): Line[] {
  const lines: Line[] = [];
  const add = (description: string, amount: number, detail?: string) => {
    if (amount) lines.push({ description, amount, detail });
  };
  const others = () => (bill.other_charges || []).forEach((c: any) => add(c.name, c.amount));
  if (kind === 'op') {
    add('Consultation', bill.consultation_fee, bill.doctor_name ? `Dr. ${bill.doctor_name}` : undefined);
    add('Laboratory', bill.lab_charges);
    add('Pharmacy', bill.pharmacy_charges);
    others();
  } else if (kind === 'ip') {
    add('Room / bed', bill.room_charges, `${bill.days_stayed} day(s) × ${money(bill.room_charge_per_day)}`);
    add('Doctor', bill.doctor_charges, bill.doctor_name ? `Dr. ${bill.doctor_name}` : undefined);
    add('Nursing', bill.nursing_charges);
    add('Pharmacy', bill.pharmacy_charges);
    add('Laboratory', bill.lab_charges);
    others();
  } else if (kind === 'pharmacy') {
    (bill.items || []).forEach((i: any) => lines.push({
      description: i.medicine_name,
      detail: `${i.quantity} × ${money(i.unit_price)}${(i.batches || []).length
        ? ` · Batch ${(i.batches as any[]).map(b => b.batch_number || '—').join(', ')}` : ''}`,
      amount: i.total_price,
    }));
  } else {
    (bill.items || []).forEach((i: any) => lines.push({ description: i.test_name, amount: i.price }));
  }
  return lines;
}

const TITLES: Record<InvoiceKind, string> = {
  op: 'Outpatient Bill', ip: 'Inpatient Final Bill', pharmacy: 'Pharmacy Invoice', lab: 'Laboratory Bill',
};

export const INVOICE_CSS = `
  *{box-sizing:border-box} body{font-family:Arial,Helvetica,sans-serif;color:#111;margin:0;padding:28px;font-size:13px}
  .head{display:flex;justify-content:space-between;gap:20px;border-bottom:2px solid #1e3a8a;padding-bottom:12px}
  .head h1{margin:0;font-size:20px;color:#1e3a8a} .head p{margin:2px 0;color:#444}
  .doc{text-align:right} .doc h2{margin:0 0 4px;font-size:16px;letter-spacing:.5px;text-transform:uppercase}
  .meta{display:grid;grid-template-columns:1fr 1fr;gap:4px 24px;margin:14px 0}
  .meta div{display:flex;gap:6px} .meta b{min-width:92px;display:inline-block;color:#333}
  table{width:100%;border-collapse:collapse;margin-top:6px}
  th{background:#1e3a8a;color:#fff;text-align:left;padding:7px 8px;font-weight:600}
  td{padding:7px 8px;border-bottom:1px solid #e5e7eb;vertical-align:top} td.num,th.num{text-align:right;white-space:nowrap}
  .detail{color:#555;font-size:12px}
  .totals{margin-left:auto;width:320px;margin-top:10px} .totals div{display:flex;justify-content:space-between;padding:3px 0}
  .totals .grand{border-top:2px solid #1e3a8a;margin-top:4px;padding-top:6px;font-size:16px;font-weight:700}
  .words{margin-top:10px;font-style:italic}
  .status{display:inline-block;padding:2px 10px;border-radius:12px;font-weight:600;font-size:12px}
  .status.Paid{background:#dcfce7;color:#166534} .status.Partial{background:#fef3c7;color:#92400e}
  .status.Pending{background:#fee2e2;color:#991b1b} .status.Cancelled{background:#e5e7eb;color:#374151}
  .void{position:fixed;top:40%;left:0;right:0;text-align:center;font-size:90px;color:rgba(153,27,27,.12);transform:rotate(-20deg);font-weight:800}
  .warn{background:#fef3c7;color:#92400e;padding:6px 10px;border-radius:6px;margin-top:10px}
  .foot{margin-top:28px;display:flex;justify-content:space-between;align-items:flex-end;color:#555;font-size:12px}
  .sign{text-align:center;border-top:1px solid #999;padding-top:4px;width:200px}
  @media print{body{padding:10mm} .no-print{display:none}}
`;

export function renderInvoice({ kind, bill, patient, settings }: InvoiceInput): SafeHtml {
  const lines = invoiceLines(kind, bill);
  const gst = gstBreakdown(Number(bill.subtotal) || 0, Number(bill.discount) || 0, Number(bill.gst) || 0,
    settings.gst_interstate === 'true');
  // The server's total is authoritative; the breakdown explains it.
  const total = Number(bill.total ?? gst.total);
  const status: string | undefined = bill.payment_status || (kind === 'lab' ? bill.status : undefined);
  const paid = bill.amount_paid ?? (status === 'Paid' ? total : undefined);
  const due = bill.amount_due ?? (paid !== undefined ? Math.max(total - paid, 0) : undefined);
  const gstin = settings.gst_number?.trim();
  const sac = settings.sac_code?.trim();
  const isCredit = bill.payment_mode === 'IP Credit';

  return html`
    ${status === 'Cancelled' ? html`<div class="void">CANCELLED</div>` : ''}
    <div class="head">
      <div>
        <h1>${settings.hospital_name || 'Hospital'}</h1>
        <p>${settings.address || ''}</p>
        <p>${[settings.contact, settings.email].filter(Boolean).join(' · ')}</p>
        ${gstin ? html`<p><b>GSTIN:</b> ${gstin}</p>` : ''}
      </div>
      <div class="doc">
        <h2>${TITLES[kind]}</h2>
        <p><b>No.</b> ${bill.receipt_no || `#${bill.id}`}</p>
        <p><b>Date</b> ${new Date(bill.bill_date).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</p>
        ${status ? html`<p><span class="status ${status}">${status}</span></p>` : ''}
      </div>
    </div>

    <div class="meta">
      <div><b>Patient</b> ${patient?.name || bill.patient_name || 'Walk-in'}</div>
      <div><b>Patient ID</b> ${patient?.id ?? bill.patient_id ?? '—'}</div>
      <div><b>Age / Sex</b> ${patient?.age ?? '—'} / ${patient?.gender || '—'}</div>
      <div><b>Phone</b> ${patient?.phone || '—'}</div>
      ${kind === 'ip' && bill.admission_id ? html`<div><b>Admission</b> #${bill.admission_id}</div>` : ''}
      <div><b>Payment</b> ${isCredit ? 'Charged to inpatient account' : bill.payment_mode || '—'}</div>
      ${sac && kind !== 'pharmacy' ? html`<div><b>SAC</b> ${sac}</div>` : ''}
    </div>

    <table>
      <thead><tr><th style="width:40px">#</th><th>Description</th><th class="num">Amount</th></tr></thead>
      <tbody>
        ${lines.length ? lines.map((l, i) => html`
          <tr><td>${i + 1}</td><td>${l.description}${l.detail ? html`<div class="detail">${l.detail}</div>` : ''}</td>
          <td class="num">${money(l.amount)}</td></tr>`) : html`<tr><td colspan="3">No chargeable items</td></tr>`}
      </tbody>
    </table>

    <div class="totals">
      <div><span>Subtotal</span><span>${money(gst.subtotal)}</span></div>
      ${gst.discount ? html`<div><span>Discount (${bill.discount}%)</span><span>− ${money(gst.discount)}</span></div>` : ''}
      <div><span>Taxable value</span><span>${money(gst.taxable)}</span></div>
      ${gst.cgst ? html`<div><span>CGST (${Number(bill.gst) / 2}%)</span><span>${money(gst.cgst)}</span></div>` : ''}
      ${gst.sgst ? html`<div><span>SGST (${Number(bill.gst) / 2}%)</span><span>${money(gst.sgst)}</span></div>` : ''}
      ${gst.igst ? html`<div><span>IGST (${bill.gst}%)</span><span>${money(gst.igst)}</span></div>` : ''}
      <div class="grand"><span>Total</span><span>${money(total)}</span></div>
      ${paid !== undefined && !isCredit ? html`<div><span>Paid</span><span>${money(paid)}</span></div>` : ''}
      ${due ? html`<div><span><b>Balance due</b></span><span><b>${money(due)}</b></span></div>` : ''}
    </div>
    <div class="words">${amountInWords(total)}</div>
    ${!gstin && Number(bill.gst) > 0
      ? html`<div class="warn no-print">GSTIN is not set in Hospital Settings; a tax invoice must show it.</div>` : ''}
    ${status === 'Cancelled' && bill.cancelled_reason ? html`<div class="warn">Cancelled: ${bill.cancelled_reason}</div>` : ''}

    <div class="foot">
      <div>${settings.receipt_footer || 'This is a computer-generated document.'}</div>
      <div class="sign">Authorised signatory</div>
    </div>`;
}
