import { useState } from 'react';
import { LiveKitRoom, RoomAudioRenderer, StartAudio, useVoiceAssistant } from '@livekit/components-react';
import '@livekit/components-styles';
import { api, formatCallTestFailureMessage } from './lib/api';
import { Spinner } from './components/UiFeedback';

export default function VoiceTester() {
  const [token, setToken] = useState('');
  const [url, setUrl] = useState('');
  const [connecting, setConnecting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const connect = async () => {
    setConnecting(true);
    setErrorMessage('');
    try {
      const data = await api.browserTest();
      if (!data.token || !data.url) throw new Error('LiveKit token response is incomplete.');
      setToken(data.token);
      setUrl(data.url);
    } catch (err: unknown) {
      console.error(err);
      setErrorMessage(formatCallTestFailureMessage(err));
    } finally {
      setConnecting(false);
    }
  };

  const disconnect = () => {
    setToken('');
    setUrl('');
    setErrorMessage('');
  };

  if (!token) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center shadow-sm">
        <h2 className="text-xl font-bold text-slate-950">Test Voice Agent</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
          Run a secured browser-room check through your Railway backend and LiveKit. Allow microphone access when prompted.
        </p>
        {errorMessage ? (
          <div className="mx-auto mt-4 max-w-md rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-left text-sm text-red-800">
            <p>{errorMessage}</p>
            <button
              type="button"
              onClick={() => void navigator.clipboard?.writeText(errorMessage).catch(() => undefined)}
              className="mt-3 rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-red-900 shadow-sm ring-1 ring-red-100 hover:bg-red-50"
            >
              Copy error for support
            </button>
          </div>
        ) : null}
        <button
          type="button"
          onClick={connect}
          disabled={connecting}
          className="mt-6 inline-flex min-h-11 w-full max-w-xs items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
        >
          {connecting ? (
            <>
              <Spinner className="h-5 w-5 text-white" label="Connecting" /> Connecting securely…
            </>
          ) : (
            '📞 Start Live Call'
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 shadow-sm">
      <LiveKitRoom
        serverUrl={url}
        token={token}
        connect={true}
        audio={true}
        video={false}
        onDisconnected={disconnect}
        className="rounded-lg border border-slate-200 bg-slate-50 p-6"
      >
        <RoomAudioRenderer />
        <ActiveCallUI onDisconnect={disconnect} />
      </LiveKitRoom>
    </div>
  );
}

function ActiveCallUI({ onDisconnect }: { onDisconnect: () => void }) {
  const { state } = useVoiceAssistant();

  return (
    <div className="flex flex-col items-center gap-6 py-4">
      <StartAudio label="Allow Audio Playback" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500" />

      <div className="relative flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-tr from-blue-600 to-indigo-500 shadow-lg">
        <span className="relative z-10 text-4xl">🤖</span>
        {state === 'speaking' && <span className="absolute inset-0 animate-ping rounded-full bg-blue-400 opacity-50" />}
      </div>
      <p className="text-center text-xs font-medium capitalize text-slate-600">{String(state ?? 'idle')}</p>

      <button
        type="button"
        onClick={onDisconnect}
        className="rounded-full border border-slate-200 bg-white px-6 py-2 text-sm font-semibold text-slate-900 shadow hover:bg-slate-50"
      >
        Disconnect
      </button>
    </div>
  );
}
