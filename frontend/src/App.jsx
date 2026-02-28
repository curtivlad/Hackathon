import React, { useState, useCallback } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import IntersectionMap from './components/IntersectionMap';
import RiskAlert from './components/RiskAlert';
import VehicleStatus from './components/VehicleStatus';
import V2XLog from './components/V2XLog';
import { ShieldCheck, ShieldAlert, Car, Settings, Activity, Navigation, ZoomIn, ZoomOut, Keyboard } from 'lucide-react';

function App() {
  const {
    state, connected, status, agents, collisionPairs,
    startScenario, stopSimulation, restartSimulation,
    grid, toggleBackgroundTraffic, backgroundTrafficActive,
  } = useWebSocket();

  const [zoom, setZoom] = useState(0.7);
  const [minZoom, setMinZoom] = useState(0.15);
  const handleMinZoom = useCallback((mz) => setMinZoom(mz), []);


  // Keyboard shortcuts: 1-6 scenarios, S stop, R restart, B background
  useKeyboardShortcuts({ startScenario, stopSimulation, restartSimulation, toggleBackgroundTraffic });

  const trafficLightIntersections = state?.traffic_light_intersections || [];

  const demoAgents = Object.values(agents || {}).filter(
    (a) => a.agent_type === 'vehicle' && !a.agent_id?.startsWith('BG_')
  ).length;
  const bgAgents = Object.values(agents || {}).filter(
    (a) => a.agent_type === 'vehicle' && a.agent_id?.startsWith('BG_')
  ).length;

  return (
    <div className="h-screen w-screen overflow-hidden relative bg-black">

      {/* ───── FULL-SCREEN MAP BACKGROUND ───── */}
      <IntersectionMap
        agents={agents}
        infrastructure={state?.infrastructure || {}}
        collisionPairs={collisionPairs}
        grid={grid}
        fullScreen={true}
        externalZoom={zoom}
        onMinZoom={handleMinZoom}
        trafficLightIntersections={trafficLightIntersections}
      />

      {/* ───── RISK ALERT OVERLAY ───── */}
      <RiskAlert type={status} collisionPairs={collisionPairs} />

      {/* ───── TOP HEADER BAR (frosted glass) ───── */}
      <div className="fixed top-4 left-4 right-4 z-20 pointer-events-auto">
        <div className="flex justify-between items-center px-5 py-3 rounded-2xl border border-white/10"
          style={{ background: 'rgba(10,10,10,0.75)', backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)' }}>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wide">V2X Safety Agent</h1>
            <p className="text-xs text-neutral-400">Team MVP</p>
          </div>
          <div className="flex items-center gap-4">
            {/* Status badge */}
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
            {/* Connection indicator */}
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

      {/* ───── LEFT PANEL: Scenario Buttons (frosted glass) ───── */}
      <div className="fixed top-24 left-4 z-20 w-80 pointer-events-auto">
        <div className="rounded-2xl border border-white/10 p-5"
          style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)' }}>

          {/* Vehicle counts */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Car className="text-neutral-400" size={18} />
              <span className="font-semibold text-sm text-neutral-300">Vehicles</span>
            </div>
            <div className="flex gap-3 text-xs font-mono">
              <span className="text-white">Demo: <strong>{demoAgents}</strong></span>
              <span className="text-neutral-500">BG: <strong>{bgAgents}</strong></span>
            </div>
          </div>

          {/* Background Traffic Toggle */}
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

          <h3 className="text-sm text-neutral-400 uppercase tracking-wider font-bold mb-3 flex items-center gap-2">
            <Settings size={15}/> Load Scenario
          </h3>
          <div className="flex flex-col gap-2">
            <ScenarioBtn label="3 Vehicles — Right of Way" onClick={() => startScenario('right_of_way')} hoverColor="green" />
            <ScenarioBtn label="4 Vehicles — Right of Way" onClick={() => startScenario('multi_vehicle')} hoverColor="green" />
            <ScenarioBtn label="4 Vehicles — Traffic Light" onClick={() => startScenario('multi_vehicle_traffic_light')} hoverColor="green" />
            <ScenarioBtn label="Blind Intersection" onClick={() => startScenario('blind_intersection')} hoverColor="yellow" />
            <ScenarioBtn label="Ambulance — Traffic Light" onClick={() => startScenario('emergency_vehicle')} hoverColor="red" />
            <ScenarioBtn label="Ambulance — No Light" onClick={() => startScenario('emergency_vehicle_no_lights')} hoverColor="orange" />
          </div>
        </div>
      </div>

      {/* ───── RIGHT PANEL: Vehicle Status (frosted glass) ───── */}
      <div className="fixed top-24 right-4 z-20 w-80 max-h-[calc(100vh-7rem)] pointer-events-auto">
        <div className="rounded-2xl border border-white/10 p-5 max-h-[calc(100vh-7rem)] overflow-y-auto"
          style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)' }}>
          <VehicleStatus agents={agents} infrastructure={state?.infrastructure || {}} />
        </div>
      </div>

      {/* ───── BOTTOM-LEFT: V2X Log Panel (frosted glass) ───── */}
      <div className="fixed bottom-4 left-4 z-20 w-80 pointer-events-auto">
        <V2XLog />
      </div>

      {/* ───── BOTTOM LEGEND (frosted glass) ───── */}
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-20 pointer-events-auto">
        <div className="flex gap-5 px-5 py-2.5 rounded-full border border-white/10 text-xs text-neutral-400 font-mono items-center"
          style={{ background: 'rgba(10,10,10,0.65)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#00e676] rounded-sm"></div>GO</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ffeb3b] rounded-sm"></div>YIELD</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ff9800] rounded-sm"></div>BRAKE</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#f44336] rounded-sm"></div>STOP</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ff1744] rounded-sm"></div>EMERGENCY</div>
          <div className="border-l border-white/10 pl-3 flex items-center gap-1" title="Keys: 1-6 scenarios, S stop, R restart, B background">
            <Keyboard size={12} className="text-neutral-600" />
            <span className="text-neutral-600 text-[10px]">1-6 S R B</span>
          </div>
        </div>
      </div>

      {/* ───── ZOOM SLIDER (bottom-right, frosted glass) ───── */}
      <div className="fixed bottom-4 right-4 z-20 pointer-events-auto">
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-white/10"
          style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}>
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
  };
  const iconColorMap = {
    green: "group-hover:text-[#00e676]",
    yellow: "group-hover:text-yellow-400",
    red: "group-hover:text-red-400",
    orange: "group-hover:text-orange-400",
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
