/**
 * Séance — Main App
 *
 * Layout: 3D room fills the screen, chat panel docked on the right.
 * Stats overlay floats over the 3D view.
 * Everything wired to the same WebSocket data stream.
 */

import useSeanceData from "./hooks/useSeanceData";
import RoomView from "./components/RoomView";
import SeanceChat from "./components/SeanceChat";
import StatsOverlay from "./components/StatsOverlay";
import "./App.css";

function App() {
  const { data, connected } = useSeanceData();

  return (
    <div className="seance-app">
      {/* 3D Room — fills left side */}
      <div className="seance-room">
        <RoomView data={data} />
        <StatsOverlay data={data} connected={connected} />
      </div>

      {/* Chat — docked right */}
      <div className="seance-chat-panel">
        <div className="seance-chat-header">
          <span className="seance-chat-title">&#x26B5; Séance</span>
          <span className="seance-chat-subtitle">commune with the room</span>
        </div>
        <div className="seance-chat-body">
          <SeanceChat data={data} />
        </div>
      </div>
    </div>
  );
}

export default App;
