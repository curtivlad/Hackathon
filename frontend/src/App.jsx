import React from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import IntersectionMap from './components/IntersectionMap';
import RiskAlert from './components/RiskAlert';
import { ShieldCheck, ShieldAlert, Car, Settings, Activity } from 'lucide-react';

function App() {
  const { state, connected, status, agents, collisionPairs, startScenario } = useWebSocket();
  
  const connectedAgents = Object.values(agents || {}).filter((a) => a.agent_type === 'vehicle').length;
  
  const stats = {
    connectedAgents: connectedAgents,
    serverStatus: connected ? 'Online' : 'Offline',
    latency: connected ? (state?.stats?.elapsed_time || '0') + 's' : '---'
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-100 font-sans p-6 flex flex-col items-center">
      
      {/* HEADER */}
      <header className="w-full max-w-6xl flex justify-between items-center bg-[#111] border border-neutral-800 p-5 rounded-2xl mb-8 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-wide">
            V2X Safety Agent
          </h1>
          <p className="text-sm text-neutral-400">BEST Brașov Hackathon</p>
        </div>

        <div className="flex bg-[#0a0a0a] border border-neutral-800 px-4 py-2 rounded-full items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${stats.serverStatus === 'Online' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
          <span className="text-sm font-mono text-neutral-300">{stats.serverStatus} • {stats.latency}</span>
        </div>
      </header>

      {/* OVERALL CONTAINER */}
      <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* LEFT COLUMN: MAP AREA */}
        <div className="col-span-1 lg:col-span-2 flex flex-col gap-4">
          
          <div className="flex-1 bg-[#111] border border-neutral-800 p-6 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-black/50">
             
             <IntersectionMap 
               agents={agents} 
               infrastructure={state?.infrastructure || {}} 
               collisionPairs={collisionPairs} 
             />
             
             {/* Map Legend (Moved below the map cleanly) */}
             <div className="flex flex-wrap justify-center gap-6 mt-6 text-xs text-neutral-400 font-mono">
               <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#00e676] rounded-sm"></div>GO</div>
               <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ffeb3b] rounded-sm"></div>YIELD</div>
               <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ff9800] rounded-sm"></div>BRAKE</div>
               <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#f44336] rounded-sm"></div>STOP</div>
               <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ff1744] rounded-sm"></div>EMERGENCY</div>
             </div>

          </div>

          {/* ALERTS (Shows up BELOW map so it doesn't shift layout) */}
          <div className="empty:hidden min-h-[100px]">
            {status !== 'safe' && (
               <RiskAlert type={status} collisionPairs={collisionPairs} />
            )}
          </div>

        </div>

        {/* RIGHT COLUMN: STATS & CONTROLS */}
        <div className="flex flex-col gap-6">
          
          {/* Connected Vehicles */}
          <div className="bg-[#111] border border-neutral-800 p-6 rounded-2xl shadow-sm">
            <div className="flex items-center gap-3 mb-2">
              <Car className="text-neutral-400" size={20} />
              <h3 className="font-semibold text-neutral-300">Connected Vehicles</h3>
            </div>
            <div className="text-5xl font-mono font-bold text-white mt-2">
              {stats.connectedAgents} <span className="text-sm text-neutral-500 font-normal">active</span>
            </div>
          </div>

          {/* Safety Status */}
          <div className={`p-6 rounded-2xl border transition-all duration-300 shadow-sm ${status === 'safe' ? 'bg-green-950/10 border-green-900/40' : 'bg-red-950/20 border-red-900/60'}`}>
            <div className="flex flex-col mb-4">
               <p className="text-neutral-400 text-sm mb-1">Intersection Status</p>
               <div className="flex justify-between items-center">
                 <p className={`text-2xl font-bold tracking-wide ${status === 'safe' ? 'text-green-500' : 'text-red-500'}`}>
                   {status === 'safe' ? 'SAFE' : 'DANGER'}
                 </p>
                 {status === 'safe' 
                   ? <ShieldCheck size={36} className="text-green-500/80" />
                   : <ShieldAlert size={36} className="text-red-500 animate-bounce" />
                 }
               </div>
            </div>
          </div>

          {/* Scenarios */}
          <div className="bg-[#111] border border-neutral-800 p-6 rounded-2xl flex-1 shadow-sm">
             <h3 className="text-sm text-neutral-400 uppercase tracking-wider font-bold mb-4 flex items-center gap-2">
               <Settings size={16}/> Load Scenario
             </h3>
             <div className="flex flex-col gap-3">
               <button onClick={() => startScenario('right_of_way')} className="w-full bg-[#1a1a1a] hover:bg-[#00e676]/20 text-neutral-200 transition px-5 py-4 rounded-xl text-sm font-medium border border-neutral-800 hover:border-[#00e676]/50 flex flex-col items-start gap-1 group">
                 <div className="flex w-full justify-between items-center">
                   <span className="font-semibold">🚗 3 Vehicule — Prioritate de Dreapta</span>
                   <Activity size={16} className="text-neutral-600 group-hover:text-[#00e676] transition-colors" />
                 </div>
                 <span className="text-xs text-neutral-500">Fără semafor · Regulă prioritate de dreapta</span>
               </button>
               <button onClick={() => startScenario('multi_vehicle')} className="w-full bg-[#1a1a1a] hover:bg-[#00e676]/20 text-neutral-200 transition px-5 py-4 rounded-xl text-sm font-medium border border-neutral-800 hover:border-[#00e676]/50 flex flex-col items-start gap-1 group">
                 <div className="flex w-full justify-between items-center">
                   <span className="font-semibold">🚗 4 Vehicule — Prioritate de Dreapta</span>
                   <Activity size={16} className="text-neutral-600 group-hover:text-[#00e676] transition-colors" />
                 </div>
                 <span className="text-xs text-neutral-500">Fără semafor · Regulă prioritate de dreapta</span>
               </button>
               <button onClick={() => startScenario('multi_vehicle_traffic_light')} className="w-full bg-[#1a1a1a] hover:bg-[#00e676]/20 text-neutral-200 transition px-5 py-4 rounded-xl text-sm font-medium border border-neutral-800 hover:border-[#00e676]/50 flex flex-col items-start gap-1 group">
                 <div className="flex w-full justify-between items-center">
                   <span className="font-semibold">🚦 4 Vehicule — Cu Semafor</span>
                   <Activity size={16} className="text-neutral-600 group-hover:text-[#00e676] transition-colors" />
                 </div>
                 <span className="text-xs text-neutral-500">Cu semafor · Trafic controlat de semafoare</span>
               </button>
               <button onClick={() => startScenario('blind_intersection')} className="w-full bg-[#1a1a1a] hover:bg-[#222] text-neutral-200 transition px-5 py-4 rounded-xl text-sm font-medium border border-neutral-800 hover:border-neutral-500 flex flex-col items-start gap-1 group">
                 <div className="flex w-full justify-between items-center">
                   <span className="font-semibold">⚠️ Intersecție cu Vizibilitate Redusă</span>
                   <Activity size={16} className="text-neutral-600 group-hover:text-yellow-400 transition-colors" />
                 </div>
                 <span className="text-xs text-neutral-500">Fără semafor · 2 vehicule, cedează B lui A</span>
               </button>
               <button onClick={() => startScenario('emergency_vehicle')} className="w-full bg-[#1a1a1a] hover:bg-red-900/30 text-neutral-200 transition px-5 py-4 rounded-xl text-sm font-medium border border-neutral-800 hover:border-red-500 flex flex-col items-start gap-1 group">
                 <div className="flex w-full justify-between items-center">
                   <span className="font-semibold">🚑 Ambulanță — Cu Semafor</span>
                   <Activity size={16} className="text-neutral-600 group-hover:text-red-400 transition-colors" />
                 </div>
                 <span className="text-xs text-neutral-500">Cu semafor · Semaforul se adaptează la urgență</span>
               </button>
               <button onClick={() => startScenario('emergency_vehicle_no_lights')} className="w-full bg-[#1a1a1a] hover:bg-orange-900/30 text-neutral-200 transition px-5 py-4 rounded-xl text-sm font-medium border border-neutral-800 hover:border-orange-500 flex flex-col items-start gap-1 group">
                 <div className="flex w-full justify-between items-center">
                   <span className="font-semibold">🚑 Ambulanță — Fără Semafor</span>
                   <Activity size={16} className="text-neutral-600 group-hover:text-orange-400 transition-colors" />
                 </div>
                 <span className="text-xs text-neutral-500">Fără semafor · Prioritate negociată prin V2X</span>
               </button>
             </div>
          </div>

        </div>
      </div>
    </div>
  );
}

export default App;
