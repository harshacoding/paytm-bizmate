import { useEffect, useState } from 'react';

export function useSidebarWidth() {
  const [width, setWidth] = useState(() => {
    try {
      const saved = Number(localStorage.getItem('bizmate-sidebar-width'));
      if (saved >= 200 && saved <= 420) return saved;
    } catch {}
    return 232;
  });
  const [resizing, setResizing] = useState(false);
  function resize(next: number) {
    setWidth(Math.max(200, Math.min(420, window.innerWidth * 0.85, next)));
  }
  useEffect(() => {
    try {
      localStorage.setItem('bizmate-sidebar-width', String(width));
    } catch {}
  }, [width]);
  return { width, resize, resizing, setResizing };
}
