import { useEffect } from "react";

export function useKeyboardShortcuts({
  startScenario,
  stopSimulation,
  restartSimulation,
  toggleBackgroundTraffic,
}) {
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

      switch (e.key) {
        case "1":
          startScenario("right_of_way");
          break;
        case "2":
          startScenario("multi_vehicle_traffic_light");
          break;
        case "3":
          startScenario("emergency_vehicle");
          break;
        case "4":
          startScenario("emergency_vehicle_no_lights");
          break;
        case "s":
        case "S":
          stopSimulation();
          break;
        case "r":
        case "R":
          restartSimulation();
          break;
        case "b":
        case "B":
          toggleBackgroundTraffic();
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [startScenario, stopSimulation, restartSimulation, toggleBackgroundTraffic]);
}
