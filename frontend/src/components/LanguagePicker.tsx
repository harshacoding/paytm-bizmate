import { useEffect, useRef, useState } from 'react';
import { languages, useLanguage } from '../i18n';
import type { Language } from '../i18n';

const codes = Object.keys(languages) as Language[];
const names = { en: 'English', hi: 'Hindi', te: 'Telugu' };

export function LanguagePicker({
  disabled,
  onSelect,
}: {
  disabled: boolean;
  onSelect: () => void;
}) {
  const { language, setLanguage, t } = useLanguage();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const options = useRef<(HTMLButtonElement | null)[]>([]);
  const gesture = useRef<{ y: number; dragged: boolean } | null>(null);

  function close(restoreFocus = false) {
    setOpen(false);
    if (restoreFocus) trigger.current?.focus();
  }

  useEffect(() => {
    if (!open) return;
    options.current[codes.indexOf(language)]?.focus();
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open, language]);

  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  return (
    <div
      className="language-picker"
      ref={root}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) close();
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.preventDefault();
          event.stopPropagation();
          close(true);
        }
      }}
    >
      <div className="language-popover" data-open={open} aria-hidden={!open} inert={!open}>
        <div
          className="language-grip"
          aria-hidden="true"
          onPointerDown={(event) => {
            gesture.current = { y: event.clientY, dragged: false };
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerUp={(event) => {
            if (gesture.current && event.clientY - gesture.current.y > 24) close(true);
            gesture.current = null;
          }}
        >
          <span />
        </div>
        <div className="language-menu-title">{t('Language')}</div>
        <div
          id="language-menu"
          role="menu"
          aria-label={t('Language')}
          onKeyDown={(event) => {
            const index = options.current.indexOf(document.activeElement as HTMLButtonElement);
            const target =
              event.key === 'Home'
                ? 0
                : event.key === 'End'
                  ? codes.length - 1
                  : event.key === 'ArrowDown'
                    ? (index + 1) % codes.length
                    : event.key === 'ArrowUp'
                      ? (index + codes.length - 1) % codes.length
                      : -1;
            if (target >= 0) {
              event.preventDefault();
              options.current[target]?.focus();
            }
          }}
        >
          {codes.map((code, index) => (
            <button
              key={code}
              type="button"
              role="menuitemradio"
              aria-checked={language === code}
              tabIndex={open && language === code ? 0 : -1}
              ref={(element) => {
                options.current[index] = element;
              }}
              onClick={() => {
                onSelect();
                setLanguage(code);
                close(true);
              }}
            >
              <span className="language-native" lang={code}>
                {languages[code]}
              </span>
              {code !== 'en' && <span className="language-english">{names[code]}</span>}
              <span className="language-check" aria-hidden="true">
                {language === code ? '✓' : ''}
              </span>
            </button>
          ))}
        </div>
      </div>
      <button
        ref={trigger}
        type="button"
        className="language-trigger"
        aria-label={`${t('Language')}: ${languages[language]}`}
        aria-haspopup="menu"
        aria-controls="language-menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => {
          const dragged = gesture.current?.dragged;
          gesture.current = null;
          if (dragged) return;
          setOpen((value) => !value);
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
            event.preventDefault();
            setOpen(true);
          }
        }}
        onPointerDown={(event) => {
          gesture.current = { y: event.clientY, dragged: false };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (
            gesture.current &&
            event.currentTarget.hasPointerCapture(event.pointerId) &&
            gesture.current.y - event.clientY > 14
          ) {
            gesture.current.dragged = true;
          }
        }}
        onPointerUp={() => {
          if (gesture.current?.dragged) setOpen(true);
        }}
        onPointerCancel={() => {
          gesture.current = null;
        }}
      >
        <svg
          className="language-globe"
          width="21"
          height="21"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z" />
        </svg>
        <span className="language-trigger-copy">
          <small>{t('Language')}</small>
          <span lang={language}>{languages[language]}</span>
        </span>
        <svg
          className="language-chevron"
          data-open={open}
          width="17"
          height="17"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="m7 14 5-5 5 5" />
        </svg>
      </button>
    </div>
  );
}
