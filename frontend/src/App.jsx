import React, { useState, useCallback } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useVoiceControl } from './hooks/useVoiceControl';
import IntersectionMap from './components/IntersectionMap';
import RiskAlert from './components/RiskAlert';
import VehicleStatus from './components/VehicleStatus';
import EventLog from './components/EventLog';
import { ShieldCheck, ShieldAlert, Car, Settings, Activity, Navigation, ZoomIn, ZoomOut, Wine, Mic, MicOff, Volume2, VolumeX, ChevronLeft, ChevronRight, Siren } from 'lucide-react';

function App() {
  const {
    state, connected, status, agents, collisionPairs,
    startScenario, stopSimulation, restartSimulation,
    grid, toggleBackgroundTraffic, backgroundTrafficActive,
    spawnDrunkDriver, spawnPolice,
  } = useWebSocket();

  const [zoom, setZoom] = useState(0.7);
  const [minZoom, setMinZoom] = useState(0.15);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const handleMinZoom = useCallback((mz) => setMinZoom(mz), []);

  const {
    voiceEnabled, setVoiceEnabled,
    ttsEnabled, setTtsEnabled,
    lastCommand, listening, supported: voiceSupported,
  } = useVoiceControl({
    startScenario,
    stopSimulation,
    restartSimulation,
    spawnDrunkDriver,
    spawnPolice,
    toggleBackgroundTraffic,
    setZoom,
    collisionPairs,
  });

  const trafficLightIntersections = state?.traffic_light_intersections || [];

  const demoAgents = Object.values(agents || {}).filter(
    (a) => a.agent_type === 'vehicle' && !a.agent_id?.startsWith('BG_') && !a.agent_id?.startsWith('AMBULANCE_') && !a.agent_id?.startsWith('POLICE_') && !a.agent_id?.startsWith('DRUNK_')
  ).length;
  const bgAgents = Object.values(agents || {}).filter(
    (a) => a.agent_type === 'vehicle' && (a.agent_id?.startsWith('BG_') || a.agent_id?.startsWith('AMBULANCE_') || a.agent_id?.startsWith('POLICE_'))
  ).length;
  const drunkAgents = Object.values(agents || {}).filter(
    (a) => a.agent_type === 'vehicle' && a.is_drunk
  ).length;

  return (
    <div className="h-screen w-screen overflow-hidden relative bg-black">

      <IntersectionMap
        agents={agents}
        infrastructure={state?.infrastructure || {}}
        collisionPairs={collisionPairs}
        grid={grid}
        fullScreen={true}
        externalZoom={zoom}
        onMinZoom={handleMinZoom}
        onZoomChange={setZoom}
        trafficLightIntersections={trafficLightIntersections}
      />

      <RiskAlert type={status} collisionPairs={collisionPairs} />

      <div className="fixed top-4 left-4 right-4 z-20 pointer-events-auto">
        <div className="flex justify-between items-center px-5 py-3 rounded-2xl border border-white/10"
          style={{ background: 'rgba(10,10,10,0.75)', backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)' }}>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wide">V2X Safety Agent</h1>
            <p className="text-xs text-neutral-400">Team MVP</p>
          </div>
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl border transition-all duration-300 ${
              status === 'safe' ? 'bg-green-950/10 border-green-900/40' : 'bg-red-950/20 border-red-900/60'
            }`}>
              <div className="flex items-center gap-2">
                {status === 'safe'
                  ? <ShieldCheck size={20} className="text-green-500/80" />
                  : <ShieldAlert size={20} className="text-red-500 animate-bounce" />
                }
                <span className={`text-sm font-bold tracking-wide ${status === 'safe' ? 'text-green-500' : 'text-red-500'}`}>
                  {status === 'safe' ? 'SAFE' : 'DANGER'}
                </span>
              </div>
            </div>
            <div className="flex px-3 py-1.5 rounded-full items-center gap-2 border border-white/10"
              style={{ background: 'rgba(0,0,0,0.5)' }}>
              <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
              <span className="text-xs font-mono text-neutral-300">
                {connected ? 'Online' : 'Offline'} | {(state?.stats?.elapsed_time || '0')}s
              </span>
            </div>
          </div>
        </div>
      </div>

      <div
        className="fixed top-24 left-0 z-20 pointer-events-auto flex items-start"
        style={{ transition: 'transform 0.35s cubic-bezier(0.4,0,0.2,1)', transform: leftOpen ? 'translateX(0)' : 'translateX(calc(-100% + 32px))' }}
      >
        <div className="w-80 ml-4 rounded-2xl border border-white/10 p-5"
          style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)' }}>

          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Car className="text-neutral-400" size={18} />
              <span className="font-semibold text-sm text-neutral-300">Vehicles</span>
            </div>
            <div className="flex gap-3 text-xs font-mono">
              <span className="text-white">Demo: <strong>{demoAgents}</strong></span>
              <span className="text-neutral-500">BG: <strong>{bgAgents}</strong></span>
              {drunkAgents > 0 && <span className="text-pink-400">Drunk: <strong>{drunkAgents}</strong></span>}
            </div>
          </div>

          <button
            onClick={toggleBackgroundTraffic}
            className={`w-full mb-4 transition px-4 py-2.5 rounded-lg text-sm font-medium border flex justify-between items-center group ${
              backgroundTrafficActive
                ? 'bg-green-900/30 border-green-500/50 text-green-400 hover:bg-green-900/50'
                : 'bg-[#1a1a1a] border-neutral-700 text-neutral-300 hover:bg-neutral-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <Navigation size={14} />
              <span>Background Traffic</span>
            </span>
            <span className={`text-xs font-bold ${backgroundTrafficActive ? 'text-green-400' : 'text-neutral-500'}`}>
              {backgroundTrafficActive ? 'ON' : 'OFF'}
            </span>
          </button>

          <button
            onClick={spawnDrunkDriver}
            className="w-full mb-2 transition px-4 py-2.5 rounded-lg text-sm font-medium border flex justify-between items-center group
              bg-pink-950/20 border-pink-500/40 text-pink-300 hover:bg-pink-900/40 hover:border-pink-400/60 hover:text-pink-200"
          >
            <span className="flex items-center gap-2">
              <Wine size={14} />
              <span>Spawn Drunk Driver</span>
            </span>
            <span className="text-xs font-bold text-pink-400">!</span>
          </button>

          <button
            onClick={spawnPolice}
            className="w-full mb-4 transition px-4 py-2.5 rounded-lg text-sm font-medium border flex justify-between items-center group
              bg-blue-950/20 border-blue-500/40 text-blue-300 hover:bg-blue-900/40 hover:border-blue-400/60 hover:text-blue-200"
          >
            <span className="flex items-center gap-2">
              <Siren size={14} />
              <span>Spawn Police Car</span>
            </span>
            <span className="text-xs font-bold text-blue-400">🚔</span>
          </button>

          <h3 className="text-sm text-neutral-400 uppercase tracking-wider font-bold mb-3 flex items-center gap-2">
            <Settings size={15}/> Load Scenario
          </h3>
          <div className="flex flex-col gap-2">
            <ScenarioBtn label="3 Vehicles — Right of Way" onClick={() => startScenario('right_of_way')} hoverColor="green" />
            <ScenarioBtn label="4 Vehicles — Traffic Light" onClick={() => startScenario('multi_vehicle_traffic_light')} hoverColor="green" />
            <ScenarioBtn label="Ambulance — Traffic Light" onClick={() => startScenario('emergency_vehicle')} hoverColor="red" />
            <ScenarioBtn label="Ambulance — No Light" onClick={() => startScenario('emergency_vehicle_no_lights')} hoverColor="orange" />
            <ScenarioBtn label="Drunk Driver" onClick={() => startScenario('drunk_driver')} hoverColor="pink" />
          </div>
        </div>
        <button
          onClick={() => setLeftOpen(prev => !prev)}
          className="mt-2 p-1.5 rounded-r-lg border border-l-0 border-white/10 text-neutral-400 hover:text-white hover:bg-white/10 transition"
          style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(16px)' }}
        >
          {leftOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      <div
        className="fixed top-24 right-0 z-20 max-h-[calc(100vh-7rem)] pointer-events-auto flex items-start"
        style={{ transition: 'transform 0.35s cubic-bezier(0.4,0,0.2,1)', transform: rightOpen ? 'translateX(0)' : 'translateX(calc(100% - 32px))' }}
      >
        <button
          onClick={() => setRightOpen(prev => !prev)}
          className="mt-2 p-1.5 rounded-l-lg border border-r-0 border-white/10 text-neutral-400 hover:text-white hover:bg-white/10 transition"
          style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(16px)' }}
        >
          {rightOpen ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
        <div className="w-80 mr-4 rounded-2xl border border-white/10 p-5 max-h-[calc(100vh-7rem)] overflow-y-auto dark-scrollbar"
          style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)' }}>
          <VehicleStatus agents={agents} infrastructure={state?.infrastructure || {}} />
        </div>
      </div>

      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-20 pointer-events-auto">
        <div className="flex gap-5 px-5 py-2.5 rounded-full border border-white/10 text-xs text-neutral-400 font-mono"
          style={{ background: 'rgba(10,10,10,0.65)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#00e676] rounded-sm"></div>GO</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ffeb3b] rounded-sm"></div>YIELD</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ff9800] rounded-sm"></div>BRAKE</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#f44336] rounded-sm"></div>STOP</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ff1744] rounded-sm"></div>EMERGENCY</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#4488ff] rounded-sm"></div>POLICE</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#FF69B4] rounded-sm"></div>DRUNK</div>
        </div>
      </div>

      {/* Event Log Panel */}
      <div className="fixed bottom-14 left-4 z-20 w-80 pointer-events-auto">
        <EventLog collisionPairs={collisionPairs} agents={agents} />
      </div>

      <div className="fixed bottom-4 right-4 z-20 pointer-events-auto">
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-white/10"
          style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}>

          {/* Voice Controls */}
          {voiceSupported && (
            <>
              <button
                onClick={() => setVoiceEnabled(v => !v)}
                className={`p-1.5 rounded-lg border transition-all ${
                  voiceEnabled
                    ? listening
                      ? 'bg-green-900/40 border-green-500/60 text-green-400 animate-pulse'
                      : 'bg-yellow-900/40 border-yellow-500/60 text-yellow-400'
                    : 'bg-transparent border-neutral-700 text-neutral-500 hover:text-neutral-300'
                }`}
                title={voiceEnabled ? (listening ? 'Listening... say a command' : 'Voice ON — connecting mic') : 'Voice Commands OFF — click to enable'}
              >
                {voiceEnabled ? <Mic size={14} /> : <MicOff size={14} />}
              </button>
              <button
                onClick={() => setTtsEnabled(v => !v)}
                className={`p-1.5 rounded-lg border transition-all ${
                  ttsEnabled
                    ? 'bg-blue-900/40 border-blue-500/60 text-blue-400'
                    : 'bg-transparent border-neutral-700 text-neutral-500 hover:text-neutral-300'
                }`}
                title={ttsEnabled ? 'TTS Alerts ON' : 'TTS Alerts OFF'}
              >
                {ttsEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
              </button>
              {lastCommand && voiceEnabled && (
                <span className="text-[10px] text-green-400/70 font-mono max-w-24 truncate" title={lastCommand}>
                  "{lastCommand}"
                </span>
              )}
              <div className="w-px h-5 bg-neutral-700"></div>
            </>
          )}

          <ZoomOut size={14} className="text-neutral-500 shrink-0" />
          <input
            type="range"
            min={Math.round(minZoom * 100)}
            max="300"
            value={Math.round(Math.max(zoom, minZoom) * 100)}
            onChange={(e) => setZoom(Math.max(minZoom, Number(e.target.value) / 100))}
            className="w-32 h-1.5 appearance-none bg-neutral-700 rounded-full cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
              [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:cursor-pointer
              [&::-webkit-slider-thumb]:shadow-md
              [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full
              [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:border-0"
          />
          <ZoomIn size={14} className="text-neutral-500 shrink-0" />
          <span className="text-xs font-mono text-neutral-400 w-10 text-right">{Math.round(zoom * 100)}%</span>
        </div>
      </div>
    </div>
  );
}

function ScenarioBtn({ label, onClick, hoverColor = "green" }) {
  const hoverMap = {
    green: "hover:bg-[#00e676]/15 hover:border-[#00e676]/50",
    yellow: "hover:bg-yellow-900/30 hover:border-yellow-500/50",
    red: "hover:bg-red-900/30 hover:border-red-500/50",
    orange: "hover:bg-orange-900/30 hover:border-orange-500/50",
    pink: "hover:bg-pink-900/30 hover:border-pink-500/50",
  };
  const iconColorMap = {
    green: "group-hover:text-[#00e676]",
    yellow: "group-hover:text-yellow-400",
    red: "group-hover:text-red-400",
    orange: "group-hover:text-orange-400",
    pink: "group-hover:text-pink-400",
  };
  return (
    <button
      onClick={onClick}
      className={`w-full bg-[#1a1a1a]/80 text-neutral-200 transition px-4 py-2.5 rounded-lg text-sm font-medium border border-neutral-800 flex justify-between items-center group ${hoverMap[hoverColor]}`}
    >
      <span className="font-semibold">{label}</span>
      <Activity size={15} className={`text-neutral-600 transition-colors ${iconColorMap[hoverColor]}`} />
    </button>
  );
}

export default App;
