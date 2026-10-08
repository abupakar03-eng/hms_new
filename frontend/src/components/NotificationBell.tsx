import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Bell, Info, XCircle } from 'lucide-react';
import { API_BASE } from '../api';

interface Notice {
  key: string;
  severity: 'error' | 'warning' | 'info';
  title: string;
  detail: string;
  tab: string;
  count: number;
}

const ICON = { error: XCircle, warning: AlertTriangle, info: Info };
const REFRESH_MS = 2 * 60 * 1000;

/** Top-bar bell: role-specific things needing attention, each linking to its screen. */
export function NotificationBell({ onOpen }: { onOpen: (tab: string) => void }) {
  const [items, setItems] = useState<Notice[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/notifications`);
      setItems(res.data);
    } catch {
      /* the bell is advisory; never interrupt work over it */
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => { if (document.visibilityState === 'visible') load(); }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const urgent = items.filter(i => i.severity !== 'info').length;

  return (
    <div className="notify-bell" ref={ref}>
      <button
        className="notify-bell-button"
        onClick={() => { setOpen(o => !o); if (!open) load(); }}
        aria-label={`Notifications${items.length ? ` (${items.length})` : ''}`}
        aria-expanded={open}
      >
        <Bell size={18} />
        {items.length > 0 && <span className={`notify-badge ${urgent ? 'is-urgent' : ''}`}>{items.length}</span>}
      </button>
      {open && (
        <div className="notify-panel" role="menu">
          <div className="notify-panel-head">Needs attention</div>
          {items.length === 0 && <div className="notify-empty">All clear — nothing needs your attention.</div>}
          {items.map(item => {
            const Icon = ICON[item.severity];
            return (
              <button key={item.key} role="menuitem" className={`notify-item notify-${item.severity}`}
                onClick={() => { setOpen(false); onOpen(item.tab); }}>
                <Icon size={16} />
                <span>
                  <b>{item.title}</b>
                  <small>{item.detail}</small>
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
