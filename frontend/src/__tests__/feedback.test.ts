import { afterEach, describe, expect, it, vi } from 'vitest';
import { _answerDialog, _toasts, confirmDialog, dismissToast, notify, promptDialog } from '../ui/feedback';

afterEach(() => {
  _toasts().forEach(t => dismissToast(t.id));
  vi.useRealTimers();
});

describe('notify', () => {
  it('queues toasts with their tone and auto-dismisses them', () => {
    vi.useFakeTimers();
    notify.success('Saved');
    notify.error('Failed');
    expect(_toasts().map(t => [t.tone, t.message])).toEqual([['success', 'Saved'], ['error', 'Failed']]);

    vi.advanceTimersByTime(3600); // success expires first, errors stay longer
    expect(_toasts().map(t => t.tone)).toEqual(['error']);
    vi.advanceTimersByTime(10000);
    expect(_toasts()).toEqual([]);
  });

  it('keeps only the most recent few', () => {
    for (let i = 0; i < 10; i++) notify.info(`m${i}`);
    expect(_toasts().map(t => t.message)).toEqual(['m6', 'm7', 'm8', 'm9']);
  });

  it('coerces non-string messages', () => {
    notify.warning(undefined);
    notify.info(42);
    expect(_toasts().map(t => t.message)).toEqual(['', '42']);
  });
});

describe('dialogs', () => {
  it('confirm resolves with the answer', async () => {
    const answer = confirmDialog('Delete?', { danger: true });
    _answerDialog(true);
    await expect(answer).resolves.toBe(true);
  });

  it('a newer dialog cancels an unanswered one', async () => {
    const first = confirmDialog('First?');
    const second = promptDialog('Reason?');
    await expect(first).resolves.toBe(false);
    _answerDialog('typo');
    await expect(second).resolves.toBe('typo');
  });

  it('prompt resolves null when cancelled', async () => {
    const answer = promptDialog('Amount?', { inputType: 'number' });
    _answerDialog(null);
    await expect(answer).resolves.toBeNull();
  });
});
