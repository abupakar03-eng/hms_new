/**
 * RoleFlow — the "complete workflow on one page" layout used by every role.
 *
 * Each role gets a single screen that answers: what is my job, where am I in it,
 * what needs doing right now, and what do I do next. The steps link into the
 * detailed screens; the lanes show the live work queue with inline actions.
 */
import React from 'react';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

export interface FlowStat {
  label: string;
  value: string | number;
  color?: string;
  icon?: React.ReactNode;
  hint?: string;
}

export interface FlowStep {
  n: number;
  title: string;
  detail: string;
  count?: string | number;
  action: string;
  onAction: () => void;
  tone?: 'todo' | 'active' | 'done';
}

export interface FlowAction {
  label: string;
  onClick: () => void;
  tone?: 'primary' | 'secondary' | 'danger';
}

export interface FlowItem {
  id: string | number;
  primary: string;
  secondary?: string;
  meta?: string;
  badge?: string;
  badgeTone?: string;
  actions?: FlowAction[];
}

export interface FlowLane {
  key: string;
  title: string;
  hint?: string;
  tone?: string;
  items: FlowItem[];
  emptyText?: string;
}

interface RoleFlowProps {
  role: string;
  title: string;
  subtitle: string;
  currentUser: string;
  stats: FlowStat[];
  steps: FlowStep[];
  lanes?: FlowLane[];
  headerActions?: React.ReactNode;
  children?: React.ReactNode;
}

const TONE: Record<string, string> = {
  todo: 'var(--text-muted)',
  active: '#3b82f6',
  done: '#10b981',
};

export default function RoleFlow({
  role, title, subtitle, currentUser, stats, steps, lanes, headerActions, children,
}: RoleFlowProps) {
  const doneCount = steps.filter(s => s.tone === 'done').length;

  return (
    <div className="no-print">
      <div className="header">
        <div className="header-title">
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          {headerActions}
          <div style={{
            background: 'rgba(59,130,246,0.1)', color: '#3b82f6', padding: '6px 14px',
            borderRadius: '20px', fontSize: '12px', fontWeight: 700, letterSpacing: '0.4px',
          }}>
            {role.toUpperCase()} · {currentUser}
          </div>
        </div>
      </div>

      {/* Live counters */}
      {stats.length > 0 && (
        <div className="dashboard-grid">
          {stats.map(s => (
            <div className="stat-card" key={s.label}>
              <div className="stat-icon" style={{ background: `${s.color || '#3b82f6'}1a`, color: s.color || '#3b82f6' }}>
                {s.icon}
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>{s.label}</h3>
                <h2 style={{ margin: 0 }}>{s.value}</h2>
                {s.hint && <small style={{ color: 'var(--text-muted)' }}>{s.hint}</small>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* The workflow itself */}
      <div className="glass-card" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
          <h3 style={{ margin: 0 }}>Your workflow</h3>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {doneCount} of {steps.length} steps clear
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(215px, 1fr))', gap: '12px' }}>
          {steps.map(step => (
            <div
              key={step.n}
              style={{
                border: `1px solid ${step.tone === 'done' ? 'rgba(16,185,129,0.4)' : 'var(--border)'}`,
                borderLeft: `4px solid ${TONE[step.tone || 'todo']}`,
                borderRadius: '10px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '6px',
                background: step.tone === 'active' ? 'rgba(59,130,246,0.06)' : 'transparent',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '6px' }}>
                <b style={{ fontSize: '14px' }}>
                  <span style={{
                    display: 'inline-flex', width: '20px', height: '20px', borderRadius: '50%',
                    background: TONE[step.tone || 'todo'], color: '#fff', fontSize: '11px',
                    alignItems: 'center', justifyContent: 'center', marginRight: '7px',
                  }}>{step.tone === 'done' ? '✓' : step.n}</span>
                  {step.title}
                </b>
                {step.count !== undefined && (
                  <span style={{ fontSize: '17px', fontWeight: 800, color: TONE[step.tone || 'todo'] }}>{step.count}</span>
                )}
              </div>
              <small style={{ color: 'var(--text-muted)', minHeight: '30px' }}>{step.detail}</small>
              <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '12px' }} onClick={step.onAction}>
                {step.action} <ArrowRight size={13} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Live work queues */}
      {lanes && lanes.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(auto-fit, minmax(${lanes.length > 2 ? '260px' : '320px'}, 1fr))`,
          gap: '14px', alignItems: 'start',
        }}>
          {lanes.map(lane => (
            <div className="glass-card" key={lane.key} style={{ padding: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <b style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: lane.tone || '#64748b', display: 'inline-block' }} />
                  {lane.title}
                </b>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{lane.items.length}</span>
              </div>
              {lane.hint && <small style={{ color: 'var(--text-muted)', display: 'block', marginBottom: '8px' }}>{lane.hint}</small>}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '420px', overflowY: 'auto', marginTop: '8px' }}>
                {lane.items.map(item => (
                  <div key={item.id} style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '9px 10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '6px', alignItems: 'flex-start' }}>
                      <b style={{ fontSize: '13px' }}>{item.primary}</b>
                      {item.badge && (
                        <span className={`status-badge ${(item.badgeTone || item.badge).replace(/ /g, '-').toLowerCase()}`} style={{ fontSize: '10px' }}>
                          {item.badge}
                        </span>
                      )}
                    </div>
                    {item.secondary && <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{item.secondary}</div>}
                    {item.meta && <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{item.meta}</div>}
                    {item.actions && item.actions.length > 0 && (
                      <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
                        {item.actions.map(a => (
                          <button
                            key={a.label}
                            className={`btn btn-${a.tone === 'danger' ? 'danger' : a.tone === 'primary' ? 'primary' : 'secondary'}`}
                            style={{ padding: '4px 9px', fontSize: '11px' }}
                            onClick={a.onClick}
                          >{a.label}</button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {lane.items.length === 0 && (
                  <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px', padding: '18px 6px' }}>
                    <CheckCircle2 size={20} style={{ opacity: 0.5 }} />
                    <div style={{ marginTop: '6px' }}>{lane.emptyText || 'Nothing pending'}</div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {children}
    </div>
  );
}
