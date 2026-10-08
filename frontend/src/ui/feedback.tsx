/**
 * App-wide feedback: toasts, confirm/prompt dialogs and a request progress bar.
 *
 * They replace window.alert / confirm / prompt, which block the whole tab, look
 * like browser errors, cannot be styled or themed, and are suppressed entirely by
 * some browsers after a few calls. Everything is driven by tiny module-level
 * stores so plain functions (`notify.success(...)`, `await confirmDialog(...)`)
 * work from any handler without threading context through 8,000 lines of JSX.
 */
import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { AxiosInstance } from 'axios';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';

// ---------------------------------------------------------------------------
// A minimal observable store
// ---------------------------------------------------------------------------
function createStore<T>(initial: T) {
  let state = initial;
  const listeners = new Set<() => void>();
  return {
    get: () => state,
    set(next: T) {
      state = next;
      listeners.forEach(l => l());
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

// ---------------------------------------------------------------------------
// Toasts
// ---------------------------------------------------------------------------
export type ToastTone = 'success' | 'error' | 'warning' | 'info';
export interface Toast { id: number; tone: ToastTone; message: string; }

const toastStore = createStore<Toast[]>([]);
let nextToastId = 1;

const TOAST_MS: Record<ToastTone, number> = { success: 3500, info: 4500, warning: 6000, error: 8000 };

export function dismissToast(id: number) {
  toastStore.set(toastStore.get().filter(t => t.id !== id));
}

function push(tone: ToastTone, message: unknown): number {
  const text = typeof message === 'string' ? message : String(message ?? '');
  const id = nextToastId++;
  // Keep the stack short; the newest message matters most.
  toastStore.set([...toastStore.get().slice(-3), { id, tone, message: text }]);
  setTimeout(() => dismissToast(id), TOAST_MS[tone]);
  return id;
}

export const notify = {
  success: (message: unknown) => push('success', message),
  error: (message: unknown) => push('error', message),
  warning: (message: unknown) => push('warning', message),
  info: (message: unknown) => push('info', message),
};

/** Test hook: current toasts. */
export const _toasts = () => toastStore.get();

const TONE_ICON = { success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info };

export function Toaster() {
  const toasts = useSyncExternalStore(toastStore.subscribe, toastStore.get);
  return (
    <div className="toast-stack" role="region" aria-label="Notifications">
      {toasts.map(t => {
        const Icon = TONE_ICON[t.tone];
        return (
          <div key={t.id} className={`toast toast-${t.tone}`} role={t.tone === 'error' ? 'alert' : 'status'}>
            <Icon size={18} aria-hidden />
            <span className="toast-message">{t.message}</span>
            <button className="toast-close" onClick={() => dismissToast(t.id)} aria-label="Dismiss">
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------
interface DialogRequest {
  kind: 'confirm' | 'prompt';
  title: string;
  message?: string;
  confirmLabel: string;
  danger: boolean;
  defaultValue: string;
  inputType: 'text' | 'number';
  required: boolean;
  resolve: (value: any) => void;
}

const dialogStore = createStore<DialogRequest | null>(null);

/** A newer dialog replaces an unanswered one, which resolves as cancelled. */
function supersedeOpenDialog() {
  const open = dialogStore.get();
  if (open) open.resolve(open.kind === 'confirm' ? false : null);
}

export interface ConfirmOptions { title?: string; confirmLabel?: string; danger?: boolean; }

/** Resolves true when confirmed, false when cancelled or dismissed. */
export function confirmDialog(message: string, options: ConfirmOptions = {}): Promise<boolean> {
  return new Promise(resolve => {
    supersedeOpenDialog();
    dialogStore.set({
      kind: 'confirm',
      title: options.title || 'Please confirm',
      message,
      confirmLabel: options.confirmLabel || (options.danger ? 'Delete' : 'Confirm'),
      danger: !!options.danger,
      defaultValue: '',
      inputType: 'text',
      required: false,
      resolve,
    });
  });
}

export interface PromptOptions {
  title?: string;
  defaultValue?: string;
  confirmLabel?: string;
  inputType?: 'text' | 'number';
  required?: boolean;
  danger?: boolean;
}

/** Resolves the entered text, or null when cancelled. */
export function promptDialog(message: string, options: PromptOptions = {}): Promise<string | null> {
  return new Promise(resolve => {
    supersedeOpenDialog();
    dialogStore.set({
      kind: 'prompt',
      title: options.title || message,
      message: options.title ? message : undefined,
      confirmLabel: options.confirmLabel || 'OK',
      danger: !!options.danger,
      defaultValue: options.defaultValue ?? '',
      inputType: options.inputType || 'text',
      required: options.required ?? true,
      resolve,
    });
  });
}

/** Test hook: close the open dialog as if the user answered. */
export function _answerDialog(value: any) {
  const current = dialogStore.get();
  dialogStore.set(null);
  current?.resolve(value);
}

export function DialogHost() {
  const dialog = useSyncExternalStore(dialogStore.subscribe, dialogStore.get);
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!dialog) return;
    setValue(dialog.defaultValue);
    // Focus the field (prompt) or the safe choice (confirm) once rendered.
    setTimeout(() => (dialog.kind === 'prompt' ? inputRef.current?.select() : confirmRef.current?.focus()), 0);
  }, [dialog]);

  if (!dialog) return null;

  const close = (result: any) => {
    dialogStore.set(null);
    dialog.resolve(result);
  };
  const cancelValue = dialog.kind === 'confirm' ? false : null;
  const canSubmit = dialog.kind === 'confirm' || !dialog.required || value.trim() !== '';
  const submit = () => {
    if (!canSubmit) return;
    close(dialog.kind === 'confirm' ? true : value);
  };

  return (
    <div className="dialog-backdrop" onMouseDown={e => e.target === e.currentTarget && close(cancelValue)}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        onKeyDown={e => {
          if (e.key === 'Escape') close(cancelValue);
          if (e.key === 'Enter' && dialog.kind === 'prompt') submit();
        }}
      >
        <h3 id="dialog-title" className="dialog-title">{dialog.title}</h3>
        {dialog.message && <p className="dialog-message">{dialog.message}</p>}
        {dialog.kind === 'prompt' && (
          <input
            ref={inputRef}
            className="dialog-input"
            type={dialog.inputType}
            value={value}
            onChange={e => setValue(e.target.value)}
          />
        )}
        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={() => close(cancelValue)}>Cancel</button>
          <button
            ref={confirmRef}
            className={`btn ${dialog.danger ? 'btn-danger' : 'btn-primary'}`}
            onClick={submit}
            disabled={!canSubmit}
          >
            {dialog.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Request progress
// ---------------------------------------------------------------------------
const pendingStore = createStore(0);

/** Count in-flight requests on an axios instance so the UI can show activity. */
export function trackRequests(instance: AxiosInstance) {
  const done = (value: any) => {
    pendingStore.set(Math.max(pendingStore.get() - 1, 0));
    return value;
  };
  instance.interceptors.request.use(config => {
    pendingStore.set(pendingStore.get() + 1);
    return config;
  });
  instance.interceptors.response.use(done, error => Promise.reject(done(error)));
}

export function RequestProgress() {
  const pending = useSyncExternalStore(pendingStore.subscribe, pendingStore.get);
  // Delay showing it so fast requests do not flash.
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (pending === 0) { setVisible(false); return; }
    const t = setTimeout(() => setVisible(true), 250);
    return () => clearTimeout(t);
  }, [pending]);
  return <div className={`request-progress ${visible ? 'is-active' : ''}`} role="progressbar" aria-hidden={!visible} />;
}
