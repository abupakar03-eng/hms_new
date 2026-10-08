import { describe, expect, it } from 'vitest';
import { amountInWords, escapeHtml, gstBreakdown, html, numberToWordsIndian, raw, renderInvoice } from '../ui/print';

describe('html escaping', () => {
  it('escapes interpolated values', () => {
    const name = '<img src=x onerror=alert(1)>';
    expect(html`<b>${name}</b>`.value).toBe('<b>&lt;img src=x onerror=alert(1)&gt;</b>');
    expect(escapeHtml(`"'&`)).toBe('&quot;&#39;&amp;');
  });

  it('keeps nested html and arrays of it, drops empty values', () => {
    const rows = ['a<', 'b'].map(x => html`<li>${x}</li>`);
    expect(html`<ul>${rows}</ul>${null}${undefined}${false}`.value).toBe('<ul><li>a&lt;</li><li>b</li></ul>');
    expect(html`${raw('<br>')}`.value).toBe('<br>');
  });
});

describe('amount in words (Indian system)', () => {
  it.each([
    [0, 'Zero'],
    [15, 'Fifteen'],
    [105, 'One Hundred Five'],
    [1250, 'One Thousand Two Hundred Fifty'],
    [100000, 'One Lakh'],
    [1234567, 'Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven'],
    [25000000, 'Two Crore Fifty Lakh'],
  ])('%i', (n, words) => expect(numberToWordsIndian(n)).toBe(words));

  it('includes paise', () => {
    expect(amountInWords(1250.5)).toBe('Rupees One Thousand Two Hundred Fifty and Fifty Paise Only');
    expect(amountInWords(99)).toBe('Rupees Ninety Nine Only');
  });
});

describe('GST breakdown', () => {
  it('matches the backend: discount first, then tax split into CGST/SGST', () => {
    const g = gstBreakdown(1000, 10, 12);
    expect(g).toEqual({ subtotal: 1000, discount: 100, taxable: 900, cgst: 54, sgst: 54, igst: 0, total: 1008 });
  });

  it('uses IGST for inter-state supply and splits odd paise without losing any', () => {
    expect(gstBreakdown(100, 0, 18, true).igst).toBe(18);
    const odd = gstBreakdown(33.33, 0, 5);
    expect(Math.round((odd.cgst + odd.sgst) * 100)).toBe(Math.round(odd.total * 100 - odd.taxable * 100));
  });
});

describe('invoice', () => {
  const settings = { hospital_name: 'City Hospital', gst_number: '33ABCDE1234F1Z5', address: 'Chennai' };

  it('shows the receipt number, GSTIN, tax split, words and balance due', () => {
    const doc = renderInvoice({
      kind: 'op', settings, patient: { name: 'Ravi', id: 7 },
      bill: { id: 3, receipt_no: 'OP/2026-27/000003', bill_date: '2026-10-08T10:00:00', consultation_fee: 1000,
              subtotal: 1000, discount: 0, gst: 18, total: 1180, payment_mode: 'Cash',
              payment_status: 'Partial', amount_paid: 500, amount_due: 680 },
    }).value;
    expect(doc).toContain('OP/2026-27/000003');
    expect(doc).toContain('33ABCDE1234F1Z5');
    expect(doc).toContain('CGST (9%)');
    expect(doc).toContain('Balance due');
    expect(doc).toContain('Rupees One Thousand One Hundred Eighty Only');
  });

  it('escapes patient-controlled text', () => {
    const doc = renderInvoice({
      kind: 'pharmacy', settings, patient: null,
      bill: { id: 1, bill_date: '2026-10-08', patient_name: '<script>x()</script>', subtotal: 5, discount: 0,
              gst: 0, total: 5, payment_mode: 'Cash',
              items: [{ medicine_name: '<b>Med</b>', quantity: 1, unit_price: 5, total_price: 5 }] },
    }).value;
    expect(doc).not.toContain('<script>');
    expect(doc).not.toContain('<b>Med</b>');
    expect(doc).toContain('&lt;script&gt;');
  });

  it('warns when tax is charged without a GSTIN and marks cancelled bills', () => {
    const doc = renderInvoice({
      kind: 'op', settings: { hospital_name: 'X' }, patient: null,
      bill: { id: 1, bill_date: '2026-10-08', subtotal: 100, discount: 0, gst: 5, total: 105,
              payment_status: 'Cancelled', cancelled_reason: 'Duplicate' },
    }).value;
    expect(doc).toContain('GSTIN is not set');
    expect(doc).toContain('CANCELLED');
    expect(doc).toContain('Cancelled: Duplicate');
  });
});
