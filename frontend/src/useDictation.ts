import { useEffect, useRef, useState } from 'react';
import { useLanguage } from './i18n';
import { openVoiceStream, prepareVoiceInput, VoiceSetupError } from './voiceEngine';
import type { VoiceStream } from './voiceEngine';
import { captureVoice } from './voiceCapture';
import type { VoiceCapture } from './voiceCapture';

type Session = {
  original: string;
  text: string;
  controller: AbortController;
  stream?: VoiceStream;
  capture?: VoiceCapture;
};

export function useDictation(draft: string, setDraft: (value: string) => void, focus: () => void) {
  const { t } = useLanguage();
  const [mode, setMode] = useState<'loading' | 'mic' | 'processing' | null>(null);
  const [notice, setNotice] = useState('');
  const [waveform, setWaveform] = useState<number[]>(Array(27).fill(0));
  const current = useRef<Session | null>(null);

  function release() {
    const session = current.current;
    current.current = null;
    if (session) {
      session.controller.abort();
      session.stream?.cancel();
      void session.capture?.stop().catch(() => {});
    }
    return session;
  }
  useEffect(
    () => () => {
      release();
    },
    [],
  );

  function fail(session: Session, error: unknown) {
    if (current.current !== session) return;
    release();
    setDraft(session.original);
    setMode(null);
    setNotice(
      t(
        error instanceof VoiceSetupError
          ? 'Voice dictation needs backend setup. You can still type your question.'
          : 'Voice input is unavailable. You can still type your question.',
      ),
    );
    focus();
  }

  async function start() {
    if (current.current) return;
    const session: Session = { original: draft, text: '', controller: new AbortController() };
    current.current = session;
    setMode('loading');
    setNotice(t('Preparing voice input…'));
    setWaveform(Array(27).fill(0));
    try {
      await prepareVoiceInput(session.controller.signal);
      if (current.current !== session) return;
      const stream = await openVoiceStream(
        (text) => {
          if (current.current !== session) return;
          session.text = text.trim();
          setDraft([session.original.trimEnd(), session.text].filter(Boolean).join(' '));
        },
        (error) => fail(session, error),
        session.controller.signal,
      );
      if (current.current !== session) {
        stream.cancel();
        return;
      }
      session.stream = stream;
      const capture = await captureVoice((samples) => {
        if (current.current !== session) return;
        try {
          stream.sendAudio(samples, session.capture?.sampleRate ?? 16000);
        } catch (error) {
          fail(session, error);
          return;
        }
        let power = 0;
        for (const sample of samples) power += sample * sample;
        setWaveform((previous) => [
          ...previous.slice(1),
          Math.min(1, Math.sqrt(power / samples.length) * 5),
        ]);
      });
      if (current.current !== session) {
        await capture.stop();
        return;
      }
      session.capture = capture;
      setMode('mic');
      setNotice(t('Speak in English, Hindi or Telugu. Replies use your selected language.'));
    } catch (error) {
      fail(session, error);
    }
  }

  async function end(cancel = false) {
    const session = current.current;
    if (!session) return;
    if (cancel) {
      release();
      setDraft(session.original);
      setMode(null);
      setNotice(t('Dictation cancelled.'));
      focus();
      return;
    }
    if (!session.capture || mode === 'processing') return;
    setMode('processing');
    setNotice(t('Finishing transcription…'));
    try {
      await session.capture.stop();
      if (current.current !== session) return;
      await session.stream!.finish();
      if (current.current !== session) return;
      release();
      setMode(null);
      setNotice(
        t(
          session.text
            ? 'Review your draft, then choose Send.'
            : 'No speech was detected. You can still type your question.',
        ),
      );
      focus();
    } catch (error) {
      fail(session, error);
    }
  }
  return {
    mode,
    notice,
    waveform,
    start,
    end,
    reset: () => {
      release();
      setMode(null);
      setNotice('');
    },
  };
}
