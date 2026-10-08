/** react-select theme that follows the app's CSS variables (light and dark). */
export const selectStyles = {
  control: (base: any, state: any) => ({
    ...base,
    backgroundColor: 'var(--bg-input)',
    borderColor: state.isFocused ? 'var(--border-focus)' : 'var(--input-border)',
    color: 'var(--text-primary)',
    boxShadow: state.isFocused ? '0 0 0 3px var(--primary-glow)' : 'none',
    minHeight: '40px',
    '&:hover': { borderColor: 'var(--border-focus)' }
  }),
  menu: (base: any) => ({ ...base, backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', zIndex: 100 }),
  option: (base: any, state: any) => ({
    ...base,
    backgroundColor: state.isFocused ? 'var(--bg-card-hover)' : 'transparent',
    color: 'var(--text-primary)',
    '&:active': { backgroundColor: 'var(--primary-glow)' }
  }),
  singleValue: (base: any) => ({ ...base, color: 'var(--text-primary)' }),
  input: (base: any) => ({ ...base, color: 'var(--text-primary)' })
};
