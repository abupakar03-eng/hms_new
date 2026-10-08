import { describe, expect, it } from 'vitest';
import { hashForTab, tabFromHash } from '../routing';

describe('hash routing', () => {
  it('reads the screen from the hash', () => {
    expect(tabFromHash('#/billing')).toBe('billing');
    expect(tabFromHash('#billing')).toBe('billing');
    expect(tabFromHash('#/ipd_workspace/12')).toBe('ipd_workspace');
    expect(tabFromHash('#/reports?from=2026-01-01')).toBe('reports');
  });

  it('ignores empty or hostile hashes', () => {
    expect(tabFromHash('')).toBeNull();
    expect(tabFromHash('#/')).toBeNull();
    expect(tabFromHash('#/<script>')).toBeNull();
    expect(tabFromHash('#/' + 'a'.repeat(80))).toBeNull();
  });

  it('round-trips', () => {
    expect(tabFromHash(hashForTab('lab_dashboard'))).toBe('lab_dashboard');
  });
});
