import { apiBase, request } from './api/client';
import type { components } from './api/schema';

export class VoiceSetupError extends Error {}

export async function prepareVoiceInput(signal?: AbortSignal) {
  const status = await request<components['schemas']['VoiceStatus']>('/api/v1/voice/status', {
    signal,
    cache: 'no-store',
  });
  if (!status.configured) throw new VoiceSetupError('Voice service not configured');
}

export type VoiceStream = {
  sendAudio: (samples: Float32Array, sampleRate: number) => void;
  finish: () => Promise<string>;
  cancel: () => void;
};

function encodeAudio(samples: Float32Array, sampleRate: number) {
  const ratio = sampleRate / 16000;
  const length = Math.floor(samples.length / ratio);
  const buffer = new ArrayBuffer(length * 2);
  const view = new DataView(buffer);
  for (let index = 0; index < length; index++) {
    const position = index * ratio;
    const left = Math.floor(position);
    const fraction = position - left;
    const value = Math.max(
      -1,
      Math.min(
        1,
        samples[left] * (1 - fraction) + samples[Math.min(left + 1, samples.length - 1)] * fraction,
      ),
    );
    view.setInt16(index * 2, Math.round(value * (value < 0 ? 32768 : 32767)), true);
  }
  let binary = '';
  for (const byte of new Uint8Array(buffer)) binary += String.fromCharCode(byte);
  return btoa(binary);
}

export function openVoiceStream(
  onTranscript: (text: string) => void,
  onError: (error: Error) => void,
  signal: AbortSignal,
): Promise<VoiceStream> {
  return new Promise((resolve, reject) => {
    const url = new URL(apiBase + '/api/v1/voice/stream', window.location.href);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(url);
    let closed = false;
    let ready = false;
    let sentAudio = false;
    let committed = '';
    let partial = '';
    let finishing:
      | { resolve: (text: string) => void; reject: (error: Error) => void; timer: number }
      | undefined;
    const text = () => [committed, partial].filter(Boolean).join(' ').trim();
    const close = () => {
      closed = true;
      clearTimeout(timeout);
      signal.removeEventListener('abort', abort);
      socket.close();
    };
    const fail = (error: Error) => {
      if (closed) return;
      close();
      if (finishing) {
        clearTimeout(finishing.timer);
        finishing.reject(error);
      }
      if (!ready) reject(error);
      else onError(error);
    };
    const abort = () => fail(new Error('Dictation cancelled'));
    const timeout = window.setTimeout(() => fail(new Error('Voice connection timed out')), 30000);
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) {
      abort();
      return;
    }
    socket.onerror = () => fail(new Error('Voice connection unavailable'));
    socket.onclose = () => {
      if (!closed) fail(new Error('Voice connection closed'));
    };
    socket.onmessage = (event) => {
      if (closed) return;
      try {
        const data = JSON.parse(event.data);
        if (data.message_type === 'error') {
          fail(
            data.code === 'voice_not_configured'
              ? new VoiceSetupError()
              : new Error('Voice provider unavailable'),
          );
        } else if (data.message_type === 'session_started') {
          ready = true;
          clearTimeout(timeout);
          resolve({
            sendAudio(samples, sampleRate) {
              if (closed || socket.readyState !== WebSocket.OPEN)
                throw new Error('Voice connection closed');
              socket.send(
                JSON.stringify({
                  message_type: 'input_audio_chunk',
                  audio_base_64: encodeAudio(samples, sampleRate),
                  sample_rate: 16000,
                  commit: false,
                }),
              );
              sentAudio = true;
            },
            finish() {
              if (!sentAudio) {
                const result = text();
                close();
                return Promise.resolve(result);
              }
              return new Promise<string>((resolve, reject) => {
                finishing = {
                  resolve,
                  reject,
                  timer: window.setTimeout(() => fail(new Error('Voice commit timed out')), 15000),
                };
                socket.send(
                  JSON.stringify({
                    message_type: 'input_audio_chunk',
                    audio_base_64: '',
                    sample_rate: 16000,
                    commit: true,
                  }),
                );
              });
            },
            cancel() {
              fail(new Error('Dictation cancelled'));
            },
          });
        } else if (data.message_type === 'partial_transcript') {
          partial = String(data.text ?? '');
          onTranscript(text());
        } else if (data.message_type === 'committed_transcript') {
          committed = [committed, String(data.text ?? '')].filter(Boolean).join(' ');
          partial = '';
          onTranscript(text());
          if (finishing) {
            clearTimeout(finishing.timer);
            finishing.resolve(text());
            close();
          }
        }
      } catch {
        fail(new Error('Invalid voice response'));
      }
    };
  });
}
