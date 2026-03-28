/**
 * Séance — Main App
 *
 * Layout: 3D room fills the screen, chat panel docked on the right.
 * Stats overlay floats over the 3D view.
 * Everything wired to the same WebSocket data stream.
 */

import { useState } from "react";
import useSeanceData from "./hooks/useSeanceData";
import RoomView from "./components/RoomView";
import SeanceChat from "./components/SeanceChat";
import CandleDetail from "./components/CandleDetail";
import StatsOverlay from "./components/StatsOverlay";
import "./App.css";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { CANDLES } from "./lib/config";

function App() {
  const { data, connected } = useSeanceData();
  const [selectedCandle, setSelectedCandle] = useState(null);

  const candleConfig = selectedCandle ? CANDLES[selectedCandle] : null;

  return (
    <div className="seance-app">
      {/* 3D Room — fills left side */}
      <div className="seance-room">
        <ErrorBoundary fallback={<div style={{color:'red',padding:20}}>3D view crashed</div>}>
          <RoomView data={data} onCandleClick={setSelectedCandle} selectedCandle={selectedCandle} />
        </ErrorBoundary>
        <StatsOverlay data={data} connected={connected} />
      </div>

      {/* Right panel — candle detail or chat */}
      <div className="seance-chat-panel">
        <div className="seance-chat-header">
          {selectedCandle && candleConfig ? (
            <>
              <span className="seance-chat-title" style={{ color: candleConfig.color }}>
                {candleConfig.name} #{candleConfig.id}
              </span>
              <span
                className="seance-chat-subtitle"
                style={{ cursor: "pointer", color: "#FF8C00" }}
                onClick={() => setSelectedCandle(null)}
              >
                &#x2190; back to chat
              </span>
            </>
          ) : (
            <>
              <span className="seance-chat-title">&#x26B5; Séance</span>
              <span className="seance-chat-subtitle">commune with the room</span>
            </>
          )}
        </div>
        <div className="seance-chat-body">
          <ErrorBoundary fallback={<div style={{color:'red',padding:20}}>Panel crashed</div>}>
            {selectedCandle ? (
              <CandleDetail mac={selectedCandle} data={data} />
            ) : (
              <SeanceChat data={data} />
            )}
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}

export default App;
