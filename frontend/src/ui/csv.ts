/**
 * CSV export shared by every "Export CSV" button.
 *
 * - Every cell is quoted and embedded quotes are doubled, so commas, quotes and
 *   new lines inside values do not shift columns.
 * - Cells starting with = + - @ (or tab/CR) are prefixed with ' so a spreadsheet
 *   shows them as text instead of executing them as formulas (CSV injection).
 * - A UTF-8 BOM lets Excel display ₹ and Tamil text correctly.
 * - Downloads go through a Blob URL; a data: URI built with encodeURI silently
 *   truncated the file at the first "#".
 */

export function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? '' : String(value);
  // Numbers cannot carry a formula, so negative amounts stay numeric.
  const safe = typeof value !== 'number' && /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
}

export function toCsv(rows: unknown[][]): string {
  return rows.map(row => row.map(csvCell).join(',')).join('\r\n');
}

export function recordsToCsv(records: Record<string, unknown>[]): string {
  if (!records.length) return '';
  const headers = Object.keys(records[0]);
  return toCsv([headers, ...records.map(r => headers.map(h => r[h]))]);
}

export function downloadCsv(csv: string, filename: string): void {
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
