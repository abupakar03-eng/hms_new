import { describe, expect, it } from 'vitest';
import { csvCell, recordsToCsv, toCsv } from '../ui/csv';

describe('csv', () => {
  it('quotes cells and doubles embedded quotes', () => {
    expect(csvCell('a,b')).toBe('"a,b"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell(null)).toBe('""');
    expect(csvCell(12.5)).toBe('"12.5"');
  });

  it('neutralises spreadsheet formulas', () => {
    expect(csvCell('=HYPERLINK("http://x")')).toBe(`"'=HYPERLINK(""http://x"")"`);
    expect(csvCell('+91 98765')).toBe(`"'+91 98765"`);
    expect(csvCell('-5')).toBe(`"'-5"`);
    expect(csvCell('@SUM(A1)')).toBe(`"'@SUM(A1)"`);
    expect(csvCell(-5)).toBe('"-5"'); // a real number is left alone
  });

  it('keeps # and new lines inside a cell', () => {
    expect(toCsv([['Bed #4', 'line1\nline2']])).toBe('"Bed #4","line1\nline2"');
  });

  it('builds a header row from record keys', () => {
    expect(recordsToCsv([{ id: 1, name: 'A' }, { id: 2, name: 'B' }])).toBe('"id","name"\r\n"1","A"\r\n"2","B"');
    expect(recordsToCsv([])).toBe('');
  });
});
