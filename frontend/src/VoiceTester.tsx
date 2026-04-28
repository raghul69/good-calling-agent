import { useState } from 'react';
import { LiveKitRoom, RoomAudioRenderer, StartAudio, useVoiceAssistant } from '@livekit/components-react';
import '@livekit/components-styles';
import { api } from './lib/api';

export default function VoiceTester() {
  const [token, setToken] = useState("");
  const [url, setUrl] = useState("");
  const [connecting, setConnecting] = useState(false);

  const connect = async () => {
    setConnecting(true);
    try {
      const data = await api.demoToken();
      if (data.error) throw new Error(data.error);
      if (!data.token || !data.url) throw new Error("LiveKit token response is incomplete.");
      setToken(data.token);
      setUrl(data.url);
    } catch (err: any) {
      console.error(err);
      alert("Error generating token: " + err.message);
    } finally {
      setConnecting(false);
    }
  }

  const disconnect = () => {
    setToken("");
    setUrl("");
  }

  if (!token) {
    return (
      <div className="card bg-gray-800 p-8 rounded-2xl border border-gray-700 text-center max-w-md mx-auto mt-12 shadow-2xl">
        <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/40 mx-auto mb-6">
          <span className="text-3xl">🎙️</span>
        </div>
        <h2 className="text-2xl font-bold mb-3">Test Voice Agent</h2>
        <p className="text-gray-400 mb-8 text-sm">
          Initiate a live demo call securely from your browser using LiveKit WebRTC.
        </p>
        <button 
          onClick={connect} 
          disabled={connecting} 
          className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-6 rounded-xl transition-all hover:scale-[1.02] active:scale-95 shadow-lg shadow-indigo-500/20"
        >
          {connecting ? "Connecting securely..." : "📞 Start Live Call"}
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto mt-12 shadow-2xl">
      <LiveKitRoom
        serverUrl={url}
        token={token}
        connect={true}
        audio={true}
        video={false}
        onDisconnected={disconnect}
        className="card bg-gray-800 p-8 rounded-xl border border-gray-700 w-full"
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
      <StartAudio label="Allow Audio Playback" className="bg-indigo-600 px-4 py-2 rounded-lg text-white mb-2 shadow-lg hover:bg-indigo-500 transition-colors" />
      
      <div className="w-24 h-24 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/50 relative">
         <span className="text-4xl relative z-10">🤖</span>
         {state === 'speaking' && <span className="absolute inset-0 rounded-full animate-ping bg-indigo-400 opacity-60"></span>}
         {state === 'listening' && <span className="absolute inset-0 rounded-full animate-ping bg-green-400 opacity-60"></span>}
         {state === 'connecting' && <span className="absolute inset-0 rounded-full animate-ping bg-yellow-400 opacity-60"></span>}
      </div>
      
      <div className="text-center">
        <h3 className="font-bold text-xl text-white">Agent Status</h3>
        <p className={`font-mono mt-1 font-semibold uppercase tracking-widest text-sm ${state === 'listening' ? 'text-green-400' : state === 'speaking' ? 'text-indigo-400' : 'text-yellow-400'}`}>
          {state || 'Connecting...'}
        </p>
      </div>
      
      <button 
        onClick={onDisconnect} 
        className="mt-6 w-full bg-red-600 hover:bg-red-500 text-white px-6 py-4 rounded-xl font-bold transition-all hover:scale-[1.02] shadow-lg shadow-red-500/20"
      >
        📵 End Call
      </button>
    </div>
  )
}
