import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Lock, Printer, RefreshCw } from 'lucide-react';
import { API_BASE, errorMessage } from '../api';
import { notify, confirmDialog } from '../ui/feedback';
import { html, money, openPrintWindow } from '../ui/print';

interface Summary {
  date: string;
  by_mode: Record<string, number>;
  by_source: Record<string, number>;
  total_collected: number;
  refunds_due: number;
  expected_cash: number;
  receipts: number;
  closing: null | {
    counted_cash: number; expected_cash: number; variance: number;
    notes?: string | null; closed_by?: string | null; closed_at?: string | null;
  };
}

const SOURCE_LABELS: Record<string, string> = { op: 'Outpatient', ip: 'Inpatient', pharmacy: 'Pharmacy counter', lab: 'Laboratory' };
const localToday = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

/**
 * End-of-day cash closing: what each counter should hold, by payment mode, and
 * the cashier's count. A closing is frozen once saved.
 */
export function DayClosePanel({ canClose, hospitalName }: { canClose: boolean; hospitalName?: string }) {
  const [day, setDay] = useState(localToday());
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [counted, setCounted] = useState('');
  const [notes, setNotes] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/reports/day-close`, { params: { date: day } });
      setSummary(res.data);
      setCounted('');
      setNotes('');
    } catch (err) {
      notify.error(errorMessage(err, 'Could not load the day summary.'));
    } finally {
      setLoading(false);
    }
  }, [day]);

  useEffect(() => { load(); }, [load]);

  const countedValue = counted === '' ? null : Number(counted);
  const variance = summary && countedValue !== null ? Math.round((countedValue - summary.expected_cash) * 100) / 100 : null;
  const needsNote = variance !== null && Math.abs(variance) >= 0.01 && !notes.trim();

  const close = async () => {
    if (!summary || countedValue === null) return;
    const ok = await confirmDialog(
      `Expected cash ${money(summary.expected_cash)}, counted ${money(countedValue)}` +
      (variance ? ` (difference ${money(variance)})` : '') + '. A closed day cannot be edited.',
      { title: `Close ${day}?`, confirmLabel: 'Close the day' },
    );
    if (!ok) return;
    try {
      const res = await axios.post(`${API_BASE}/reports/day-close`, { date: day, counted_cash: countedValue, notes: notes || null });
      setSummary(res.data);
      notify.success(`${day} closed.`);
    } catch (err) {
      notify.error(errorMessage(err, 'Could not close the day.'));
    }
  };

  const print = () => {
    if (!summary) return;
    const c = summary.closing;
    openPrintWindow(`Day closing ${summary.date}`, html`
      <h2>${hospitalName || 'Hospital'} — Day closing</h2>
      <p><b>Date:</b> ${summary.date} &nbsp; <b>Receipts:</b> ${summary.receipts}</p>
      <h3>By payment mode</h3>
      <table>${Object.entries(summary.by_mode).map(([m, v]) => html`<tr><td>${m}</td><td class="n">${money(v)}</td></tr>`)}</table>
      <h3>By counter</h3>
      <table>${Object.entries(summary.by_source).map(([s, v]) => html`<tr><td>${SOURCE_LABELS[s] || s}</td><td class="n">${money(v)}</td></tr>`)}</table>
      <table style="margin-top:12px">
        <tr><td>Total collected</td><td class="n">${money(summary.total_collected)}</td></tr>
        <tr><td>Refunds due (cancelled bills)</td><td class="n">− ${money(summary.refunds_due)}</td></tr>
        <tr><td><b>Expected cash</b></td><td class="n"><b>${money(summary.expected_cash)}</b></td></tr>
        ${c ? html`<tr><td>Counted cash</td><td class="n">${money(c.counted_cash)}</td></tr>
                  <tr><td>Variance</td><td class="n">${money(c.variance)}</td></tr>` : ''}
      </table>
      ${c ? html`<p>Closed by <b>${c.closed_by || '—'}</b> at ${c.closed_at ? new Date(c.closed_at + 'Z').toLocaleString() : ''}</p>
                 ${c.notes ? html`<p><b>Notes:</b> ${c.notes}</p>` : ''}` : html`<p><i>Not closed yet.</i></p>`}`,
      'body{font-family:Arial;padding:24px;font-size:13px}table{width:100%;max-width:480px;border-collapse:collapse}td{padding:5px 8px;border-bottom:1px solid #ddd}.n{text-align:right}');
  };

  return (
    <div className="glass-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <h3 style={{ margin: 0 }}>Day-end cash closing</h3>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <input type="date" value={day} max={localToday()} onChange={e => setDay(e.target.value)} className="input-field" />
          <button className="btn btn-secondary" onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className="btn btn-secondary" onClick={print} disabled={!summary}><Printer size={16} /> Print</button>
        </div>
      </div>

      {summary && (
        <>
          <div className="stat-grid" style={{ marginTop: '16px' }}>
            <div className="glass-card"><small>Total collected</small><h2 style={{ margin: '4px 0' }}>{money(summary.total_collected)}</h2><small>{summary.receipts} receipt(s)</small></div>
            <div className="glass-card"><small>Refunds due</small><h2 style={{ margin: '4px 0' }}>{money(summary.refunds_due)}</h2><small>from cancelled bills</small></div>
            <div className="glass-card"><small>Expected cash in drawer</small><h2 style={{ margin: '4px 0' }}>{money(summary.expected_cash)}</h2><small>cash collected − refunds</small></div>
          </div>

          <div className="grid-2" style={{ marginTop: '16px', display: 'grid', gap: '16px', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
            <div className="table-container">
              <table>
                <thead><tr><th>Payment mode</th><th style={{ textAlign: 'right' }}>Amount</th></tr></thead>
                <tbody>
                  {Object.keys(summary.by_mode).length === 0 && <tr><td colSpan={2}>No collections on this day.</td></tr>}
                  {Object.entries(summary.by_mode).map(([m, v]) => <tr key={m}><td>{m}</td><td style={{ textAlign: 'right' }}>{money(v)}</td></tr>)}
                </tbody>
              </table>
            </div>
            <div className="table-container">
              <table>
                <thead><tr><th>Counter</th><th style={{ textAlign: 'right' }}>Amount</th></tr></thead>
                <tbody>
                  {Object.entries(summary.by_source).map(([s, v]) => <tr key={s}><td>{SOURCE_LABELS[s] || s}</td><td style={{ textAlign: 'right' }}>{money(v)}</td></tr>)}
                </tbody>
              </table>
            </div>
          </div>

          {summary.closing ? (
            <div className="glass-card" style={{ marginTop: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
              <Lock size={20} />
              <div>
                <b>Closed</b> by {summary.closing.closed_by || '—'} — counted {money(summary.closing.counted_cash)},
                variance <b style={{ color: Math.abs(summary.closing.variance) >= 0.01 ? 'var(--accent-amber)' : 'var(--accent-emerald)' }}>
                  {money(summary.closing.variance)}</b>
                {summary.closing.notes && <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>{summary.closing.notes}</div>}
              </div>
            </div>
          ) : canClose ? (
            <div className="form-grid" style={{ marginTop: '16px', alignItems: 'end' }}>
              <div className="form-group">
                <label>Cash counted in drawer (₹)</label>
                <input type="number" min="0" step="0.01" value={counted} onChange={e => setCounted(e.target.value)} />
                {variance !== null && (
                  <small style={{ color: Math.abs(variance) >= 0.01 ? 'var(--accent-amber)' : 'var(--accent-emerald)' }}>
                    {Math.abs(variance) < 0.01 ? 'Matches expected cash' : `${variance > 0 ? 'Excess' : 'Short'} by ${money(Math.abs(variance))}`}
                  </small>
                )}
              </div>
              <div className="form-group">
                <label>Notes {needsNote && <span style={{ color: 'var(--accent-amber)' }}>(required — explain the difference)</span>}</label>
                <input type="text" value={notes} onChange={e => setNotes(e.target.value)} placeholder="e.g. ₹500 float kept for tomorrow" />
              </div>
              <button className="btn btn-primary" onClick={close} disabled={countedValue === null || needsNote}>
                <CheckCircle2 size={16} /> Close the day
              </button>
            </div>
          ) : (
            <p style={{ marginTop: '16px', color: 'var(--text-muted)' }}>Only Billing or Admin can close a day.</p>
          )}
        </>
      )}
    </div>
  );
}
