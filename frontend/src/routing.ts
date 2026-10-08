/**
 * Hash-based routing for the staff shell: `#/billing`, `#/ipd_workspace`, ...
 *
 * The hash keeps the current screen across a reload, makes the browser Back
 * button work, and lets a screen be bookmarked or linked. A hash (rather than a
 * path) never collides with API routes such as `/patients/` that the same
 * backend serves, and needs no server-side fallback.
 */
import { useCallback, useEffect, useState } from 'react';

const TAB_PATTERN = /^[a-z0-9_]{1,40}$/i;

export function tabFromHash(hash: string): string | null {
  const tab = hash.replace(/^#\/?/, '').split(/[/?]/)[0];
  return TAB_PATTERN.test(tab) ? tab : null;
}

export function hashForTab(tab: string): string {
  return `#/${tab}`;
}

/** `[tab, setTab]` kept in sync with the URL hash. */
export function useHashTab(fallback: string): [string, (tab: string) => void, boolean] {
  const initial = tabFromHash(window.location.hash);
  const [tab, setTabState] = useState(initial || fallback);

  useEffect(() => {
    const onHashChange = () => {
      const next = tabFromHash(window.location.hash);
      if (next) setTabState(next);
    };
    // pushState entries come back through popstate; typed/linked hashes through hashchange.
    window.addEventListener('hashchange', onHashChange);
    window.addEventListener('popstate', onHashChange);
    return () => {
      window.removeEventListener('hashchange', onHashChange);
      window.removeEventListener('popstate', onHashChange);
    };
  }, []);

  const setTab = useCallback((next: string) => {
    setTabState(next);
    if (tabFromHash(window.location.hash) !== next) {
      // pushState so Back returns to the previous screen without a reload.
      window.history.pushState(null, '', hashForTab(next));
    }
  }, []);

  // Whether the user arrived on a specific screen (so role defaults must not override it).
  return [tab, setTab, initial !== null];
}
