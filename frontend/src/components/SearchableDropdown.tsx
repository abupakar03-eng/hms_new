import { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';

export const SearchableDropdown = ({ options, value, onChange, placeholder, renderOption, searchKeys = ['label'] }: any) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: any) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredOptions = options.filter((opt: any) => 
    searchKeys.some((key: string) => opt[key]?.toString().toLowerCase().includes(search.toLowerCase()))
  );

  const selectedOpt = options.find((o: any) => o.value === value);

  return (
    <div ref={wrapperRef} style={{ position: 'relative', width: '100%' }}>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{ padding: '8px', border: '1px solid var(--input-border)', borderRadius: '6px', background: 'var(--bg-input)', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
      >
        <span>{selectedOpt ? (renderOption ? renderOption(selectedOpt) : selectedOpt.label) : placeholder}</span>
        <ChevronDown size={16} />
      </div>
      {isOpen && (
        <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: 'var(--bg-card-solid, var(--bg-input))', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: '4px', zIndex: 100, maxHeight: '300px', overflowY: 'auto', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
          <div style={{ padding: '8px', position: 'sticky', top: 0, background: 'var(--bg-card-solid, var(--bg-input))', borderBottom: '1px solid var(--border)' }}>
            <input 
              type="text" 
              placeholder="Type to search..." 
              value={search} 
              onChange={e => setSearch(e.target.value)}
              style={{ width: '100%', padding: '6px', border: '1px solid var(--input-border)', borderRadius: '4px', background: 'var(--bg-input)', color: 'var(--text-primary)' }}
              autoFocus
            />
          </div>
          {filteredOptions.length > 0 ? (
            filteredOptions.map((opt: any, index: number) => (
              <div 
                key={index}
                onClick={() => { onChange(opt.value); setIsOpen(false); setSearch(''); }}
                style={{ padding: '8px', cursor: 'pointer', borderBottom: '1px solid var(--border)' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--bg-card-hover)')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                {renderOption ? renderOption(opt) : opt.label}
              </div>
            ))
          ) : (
            <div style={{ padding: '8px', color: 'var(--text-muted)', textAlign: 'center' }}>No results found</div>
          )}
        </div>
      )}
    </div>
  );
};
