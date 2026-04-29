import { useEffect, useRef, useState } from 'react';
import { Terminal } from 'xterm';
import 'xterm/css/xterm.css';
import { TerminalWindow, Play, Stop, ArrowsOutSimple, FlowArrow } from '@phosphor-icons/react';

export default function TerminalPage() {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    if (!terminalRef.current || xtermRef.current) return;

    // Initialize xterm.js for that authentic IDE feel
    const term = new Terminal({
      theme: {
        background: '#0d1117', // GitHub Dark Dimmed background
        foreground: '#c9d1d9',
        cursor: '#58a6ff',
        selectionBackground: '#394150',
        black: '#484f58',
        blue: '#58a6ff',
        cyan: '#39c5cf',
        green: '#3fb950',
        magenta: '#bc8cff',
        red: '#ff7b72',
        white: '#b1bac4',
        yellow: '#d29922',
        brightBlack: '#6e7681',
        brightBlue: '#79c0ff',
        brightCyan: '#56d4dd',
        brightGreen: '#56d364',
        brightMagenta: '#d2a8ff',
        brightRed: '#ffa198',
        brightWhite: '#ffffff',
        brightYellow: '#e3b341',
      },
      fontFamily: '"Fira Code", "JetBrains Mono", Consolas, monospace',
      fontSize: 14,
      cursorBlink: true,
      disableStdin: true, // Read-only out of the box for safety
      rows: 30,
      convertEol: true, // Handle \n properly
    });

    term.open(terminalRef.current);
    xtermRef.current = term;

    // Initial Welcome Message
    term.writeln('\x1b[1;36mJettone \x1b[0m\x1b[38;5;244mv2.0.0 (Antigravity IDE Edition)\x1b[0m');
    term.writeln('\x1b[38;5;244mSystem Initialized. Waiting for execution...\x1b[0m\n');
    
    // Simulate initial loading
    term.writeln('\x1b[32m[INFO]\x1b[0m Booting up agent sandbox...');

    return () => {
      term.dispose();
      xtermRef.current = null;
    };
  }, []);

  const handleStartSim = () => {
    if (!xtermRef.current || isRunning) return;
    setIsRunning(true);
    
    const term = xtermRef.current;
    term.writeln('\x1b[33m[WARN]\x1b[0m No active LiveKit room found. Falling back to local SIP trunk.');
    term.writeln('\x1b[32m[INFO]\x1b[0m Connecting to database [oxgbvrutinsoximfchep]...');
    
    setTimeout(() => term.writeln('\x1b[32m[INFO]\x1b[0m Database connection established.'), 800);
    setTimeout(() => term.writeln('\x1b[34m[SYSTEM]\x1b[0m Worker 0 pid 18423 is alive.'), 1500);
    setTimeout(() => term.writeln('\x1b[34m[SYSTEM]\x1b[0m Listening for inbound STT streams on port 8081.\n'), 2000);
  };

  const handleClear = () => {
    if (xtermRef.current) {
      xtermRef.current.clear();
      setIsRunning(false);
      xtermRef.current.writeln('\x1b[38;5;244mTerminal cleared. Waiting for logs...\x1b[0m\n');
    }
  };

  return (
    <div className="page p-8 max-w-7xl mx-auto flex flex-col h-[calc(100vh-2rem)]">
      <div className="flex justify-between items-end mb-6 shrink-0">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <TerminalWindow size={32} className="text-indigo-400" />
            Live Backend Console
          </h1>
          <p className="text-gray-400 mt-2">Monitor real-time worker logs, LiveKit events, and WebRTC statuses.</p>
        </div>
      </div>

      <div className="flex-1 bg-[#0d1117] rounded-xl border border-gray-700 shadow-2xl flex flex-col overflow-hidden ring-1 ring-white/10">
        {/* Fake IDE Toolbar */}
        <div className="bg-[#161b22] px-4 py-3 border-b border-gray-700 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4 text-sm font-medium text-gray-400">
            <button className="text-gray-200 border-b-2 border-indigo-500 pb-1 -mb-[13px] px-2 flex items-center gap-2">
              <TerminalWindow weight="fill" /> Local
            </button>
            <button className="hover:text-gray-200 transition-colors pb-1 -mb-[13px] px-2 flex items-center gap-2">
              <FlowArrow /> Pipeline
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button 
              onClick={handleStartSim}
              disabled={isRunning}
              className={`p-1.5 rounded hover:bg-gray-700 transition-colors ${isRunning ? 'text-gray-600' : 'text-green-400'}`} 
              title="Start Python Backend"
            >
              <Play size={16} weight="fill" />
            </button>
            <button 
              onClick={handleClear}
              className="p-1.5 rounded hover:bg-gray-700 transition-colors text-red-400" 
              title="Stop / Clear"
            >
              <Stop size={16} weight="fill" />
            </button>
            <div className="w-px h-4 bg-gray-700 mx-2" />
            <button className="p-1.5 rounded hover:bg-gray-700 transition-colors text-gray-400">
              <ArrowsOutSimple size={16} />
            </button>
          </div>
        </div>

        {/* The Actual Terminal Canvas */}
        <div className="flex-1 p-4 overflow-hidden relative">
           <div ref={terminalRef} className="w-full h-full [&>.terminal]:w-full [&>.terminal]:h-full" />
        </div>
      </div>
    </div>
  );
}
