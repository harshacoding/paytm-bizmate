export type VoiceCapture = { sampleRate: number; stop: () => Promise<void> };

export async function captureVoice(
  onSamples: (samples: Float32Array) => void,
): Promise<VoiceCapture> {
  const context = new AudioContext({ sampleRate: 16000 });
  let stream: MediaStream | undefined;
  try {
    await context.resume();
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
      video: false,
    });
    await context.audioWorklet.addModule(import.meta.env.BASE_URL + 'audio/dictation-processor.js');
    const source = context.createMediaStreamSource(stream);
    const processor = new AudioWorkletNode(context, 'bizmate-dictation');
    const mute = context.createGain();
    mute.gain.value = 0;
    source.connect(processor).connect(mute).connect(context.destination);
    let flushed: (() => void) | undefined;
    processor.port.onmessage = ({ data }) => {
      if (data.samples) onSamples(data.samples);
      if (data.flushed) flushed?.();
    };
    let stopping: Promise<void> | undefined;
    return {
      sampleRate: context.sampleRate,
      stop() {
        stopping ??= (async () => {
          stream?.getTracks().forEach((track) => track.stop());
          await new Promise<void>((resolve) => {
            const timer = window.setTimeout(resolve, 500);
            flushed = () => {
              clearTimeout(timer);
              resolve();
            };
            processor.port.postMessage('flush');
          });
          source.disconnect();
          processor.disconnect();
          mute.disconnect();
          processor.port.close();
          await context.close();
        })();
        return stopping;
      },
    };
  } catch (error) {
    stream?.getTracks().forEach((track) => track.stop());
    await context.close();
    throw error;
  }
}
