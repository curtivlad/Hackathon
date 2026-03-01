import React from 'react';
import { Map, FlaskConical, ShieldCheck } from 'lucide-react';

function MainMenu({ onSelectMode }) {
  return (
    <div className="h-screen w-screen bg-black flex items-center justify-center">
      <div className="max-w-3xl w-full px-6">
        <div className="text-center mb-16">
          <div className="flex items-center justify-center gap-4 mb-6">
            <ShieldCheck size={52} className="text-green-500" />
            <h1 className="text-6xl font-extrabold text-white tracking-wide">V2X Safety Agent</h1>
          </div>
          <p className="text-neutral-400 text-lg leading-relaxed max-w-2xl mx-auto">
            Cooperative V2X Intersection Safety Agent — Simulation & Testing Platform
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
          <button
            onClick={() => onSelectMode('CITY')}
            className="group relative rounded-2xl border border-neutral-800 px-10 py-12 text-left transition-all duration-300
              hover:border-green-500/50 hover:bg-green-950/10 focus:outline-none focus:border-green-500/50"
            style={{ background: 'rgba(15,15,15,0.9)' }}
          >
            <div className="flex items-center gap-4 mb-6">
              <div className="p-4 rounded-xl border border-neutral-700 group-hover:border-green-500/40 transition-colors"
                style={{ background: 'rgba(0,0,0,0.5)' }}>
                <Map size={32} className="text-neutral-400 group-hover:text-green-400 transition-colors" />
              </div>
              <h2 className="text-2xl font-bold text-white">City Simulation</h2>
            </div>
            <p className="text-neutral-500 text-base leading-relaxed">
              Full 5x5 grid map with background traffic, random vehicle spawning, and multi-intersection coordination.
            </p>
          </button>

          <button
            onClick={() => onSelectMode('SCENARIO')}
            className="group relative rounded-2xl border border-neutral-800 px-10 py-12 text-left transition-all duration-300
              hover:border-blue-500/50 hover:bg-blue-950/10 focus:outline-none focus:border-blue-500/50"
            style={{ background: 'rgba(15,15,15,0.9)' }}
          >
            <div className="flex items-center gap-4 mb-6">
              <div className="p-4 rounded-xl border border-neutral-700 group-hover:border-blue-500/40 transition-colors"
                style={{ background: 'rgba(0,0,0,0.5)' }}>
                <FlaskConical size={32} className="text-neutral-400 group-hover:text-blue-400 transition-colors" />
              </div>
              <h2 className="text-2xl font-bold text-white">Scenarios</h2>
            </div>
            <p className="text-neutral-500 text-base leading-relaxed">
              Isolated single intersection for specific behavior testing — emergency vehicles, right of way, and more.
            </p>
          </button>
        </div>

        <p className="text-center text-neutral-600 text-xs mt-10">Designed by Team MVP</p>
      </div>
    </div>
  );
}

export default MainMenu;
