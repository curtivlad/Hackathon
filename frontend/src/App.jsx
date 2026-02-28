import React from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import IntersectionMap from './components/IntersectionMap';
import RiskAlert from './components/RiskAlert';
import VehicleStatus from './components/VehicleStatus';
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
    <div className="h-screen bg-[#0a0a0a] text-neutral-100 font-sans p-4 flex flex-col overflow-hidden relative">

      <RiskAlert type={status} collisionPairs={collisionPairs} />

      <header className="w-full flex justify-between items-center bg-[#111] border border-neutral-800 px-5 py-3 rounded-2xl mb-4 shadow-sm shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white tracking-wide">
            V2X Safety Agent
          </h1>
          <p className="text-xs text-neutral-400">Team MVP</p>
        </div>
        <div className="flex items-center gap-4">
          <div className={`p-3 rounded-xl border transition-all duration-300 ${status === 'safe' ? 'bg-green-950/10 border-green-900/40' : 'bg-red-950/20 border-red-900/60'}`}>
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
          <div className="flex bg-[#0a0a0a] border border-neutral-800 px-3 py-1.5 rounded-full items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${stats.serverStatus === 'Online' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className="text-xs font-mono text-neutral-300">{stats.serverStatus} | {stats.latency}</span>
          </div>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-5 gap-4 min-h-0">

        <div className="col-span-3 min-w-0 bg-[#111] border border-neutral-800 p-2 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-black/50">
          <IntersectionMap
            agents={agents}
            infrastructure={state?.infrastructure || {}}
            collisionPairs={collisionPairs}
          />
          <div className="flex flex-wrap justify-center gap-5 mt-2 mb-1 text-xs text-neutral-400 font-mono shrink-0">
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#00e676] rounded-sm"></div>GO</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ffeb3b] rounded-sm"></div>YIELD</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ff9800] rounded-sm"></div>BRAKE</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#f44336] rounded-sm"></div>STOP</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-[#ff1744] rounded-sm"></div>EMERGENCY</div>
          </div>
        </div>

        <div className="col-span-2 flex flex-col gap-4 min-h-0">

          <div className="bg-[#111] border border-neutral-800 p-5 rounded-2xl shadow-sm shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Car className="text-neutral-400" size={20} />
                <span className="font-semibold text-sm text-neutral-300">Connected Vehicles</span>
              </div>
              <span className="text-3xl font-mono font-bold text-white">
                {stats.connectedAgents}
              </span>
            </div>
          </div>

          <div className="bg-[#111] border border-neutral-800 p-5 rounded-2xl shadow-sm shrink-0">
            <h3 className="text-sm text-neutral-400 uppercase tracking-wider font-bold mb-3 flex items-center gap-2">
              <Settings size={15}/> Load Scenario
            </h3>
            <div className="flex flex-col gap-2.5">
              <button onClick={() => startScenario('right_of_way')} className="w-full bg-[#1a1a1a] hover:bg-[#00e676]/20 text-neutral-200 transition px-4 py-3 rounded-lg text-sm font-medium border border-neutral-800 hover:border-[#00e676]/50 flex justify-between items-center group">
                <span className="font-semibold">3 Vehicles -- Right of Way</span>
                <Activity size={15} className="text-neutral-600 group-hover:text-[#00e676] transition-colors" />
              </button>
              <button onClick={() => startScenario('multi_vehicle')} className="w-full bg-[#1a1a1a] hover:bg-[#00e676]/20 text-neutral-200 transition px-4 py-3 rounded-lg text-sm font-medium border border-neutral-800 hover:border-[#00e676]/50 flex justify-between items-center group">
                <span className="font-semibold">4 Vehicles -- Right of Way</span>
                <Activity size={15} className="text-neutral-600 group-hover:text-[#00e676] transition-colors" />
              </button>
              <button onClick={() => startScenario('multi_vehicle_traffic_light')} className="w-full bg-[#1a1a1a] hover:bg-[#00e676]/20 text-neutral-200 transition px-4 py-3 rounded-lg text-sm font-medium border border-neutral-800 hover:border-[#00e676]/50 flex justify-between items-center group">
                <span className="font-semibold">4 Vehicles -- Traffic Light</span>
                <Activity size={15} className="text-neutral-600 group-hover:text-[#00e676] transition-colors" />
              </button>
              <button onClick={() => startScenario('blind_intersection')} className="w-full bg-[#1a1a1a] hover:bg-yellow-900/30 text-neutral-200 transition px-4 py-3 rounded-lg text-sm font-medium border border-neutral-800 hover:border-yellow-500/50 flex justify-between items-center group">
                <span className="font-semibold">Blind Intersection</span>
                <Activity size={15} className="text-neutral-600 group-hover:text-yellow-400 transition-colors" />
              </button>
              <button onClick={() => startScenario('emergency_vehicle')} className="w-full bg-[#1a1a1a] hover:bg-red-900/30 text-neutral-200 transition px-4 py-3 rounded-lg text-sm font-medium border border-neutral-800 hover:border-red-500/50 flex justify-between items-center group">
                <span className="font-semibold">Ambulance -- Traffic Light</span>
                <Activity size={15} className="text-neutral-600 group-hover:text-red-400 transition-colors" />
              </button>
              <button onClick={() => startScenario('emergency_vehicle_no_lights')} className="w-full bg-[#1a1a1a] hover:bg-orange-900/30 text-neutral-200 transition px-4 py-3 rounded-lg text-sm font-medium border border-neutral-800 hover:border-orange-500/50 flex justify-between items-center group">
                <span className="font-semibold">Ambulance -- No Light</span>
                <Activity size={15} className="text-neutral-600 group-hover:text-orange-400 transition-colors" />
              </button>
            </div>
          </div>

          <div className="flex-1 min-h-0 bg-[#111] border border-neutral-800 rounded-2xl p-5 shadow-sm flex flex-col">
            <div className="overflow-y-auto flex-1 min-h-0">
              <VehicleStatus agents={agents} infrastructure={state?.infrastructure || {}} />
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

export default App;
