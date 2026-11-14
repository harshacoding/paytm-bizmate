import { useEffect, useRef, useState } from 'react';
import { questions } from './demo';
import { speechLocales, useLanguage } from './i18n';
import type { Language } from './i18n';

type Result = { [index: number]: { transcript: string } };
type Recognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: { results: ArrayLike<Result> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start(): void;
  abort(): void;
};
type Session = {
  original: string;
  timers: number[];
  recognition?: Recognition;
};
const fallback = 'You can still type your question.';

export function useDictation(
  draft: string,
  setDraft: (value: string) => void,
  focus: () => void,
  language: Language = 'en',
) {
  const { t } = useLanguage();
  const [mode, setMode] = useState<'mic' | 'simulation' | null>(null);
  const [notice, setNotice] = useState('');
  const current = useRef<Session | null>(null);

  function release() {
    const session = current.current;
    current.current = null;
    session?.timers.forEach((timer) => window.clearTimeout(timer));
    if (session?.recognition) {
      session.recognition.onresult = session.recognition.onerror = session.recognition.onend = null;
      session.recognition.abort();
    }
    return session;
  }

  useEffect(
    () => () => {
      release();
    },
    [],
  );

  function end(cancel = false) {
    const session = release();
    if (!session) return;
    if (cancel) setDraft(session.original);
    setMode(null);
    setNotice(t(cancel ? 'Dictation cancelled.' : 'Review your draft, then choose Send.'));
    focus();
  }

  function start(simulate: boolean) {
    if (current.current) return;
    const session: Session = { original: draft, timers: [] };
    const apply = (words: string) => {
      if (current.current === session)
        setDraft([session.original.trimEnd(), words.trim()].filter(Boolean).join(' '));
    };
    current.current = session;
    setNotice('');
    if (simulate) {
      setMode('simulation');
      const words = t(questions[0]).split(' ');
      session.timers = words.map((_, index) =>
        window.setTimeout(() => apply(words.slice(0, index + 1).join(' ')), (index + 1) * 310),
      );
      return;
    }
    const browser = window as Window & {
      SpeechRecognition?: new () => Recognition;
      webkitSpeechRecognition?: new () => Recognition;
    };
    const SpeechRecognition = browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
    const fail = () => {
      if (current.current !== session) return;
      release();
      setDraft(session.original);
      setMode(null);
      setNotice(t(fallback));
      focus();
    };
    if (!SpeechRecognition) {
      fail();
      return;
    }
    try {
      const recognition = new SpeechRecognition();
      session.recognition = recognition;
      recognition.lang = speechLocales[language];
      recognition.interimResults = true;
      recognition.continuous = true;
      recognition.onresult = (event) =>
        apply(Array.from(event.results, (result) => result[0].transcript).join(' '));
      recognition.onerror = fail;
      recognition.onend = () => end();
      recognition.start();
      setMode('mic');
    } catch {
      fail();
    }
  }

  return {
    mode,
    notice,
    start,
    end,
    reset: () => {
      release();
      setMode(null);
      setNotice('');
    },
  };
}
