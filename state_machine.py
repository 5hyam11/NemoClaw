import json, time, os

METRICS_PATH = os.path.join(os.path.dirname(__file__), "metrics.json")

def write_metrics(data):
    with open(METRICS_PATH, "w") as f:
        json.dump(data, f, indent=2)

def run_scenario_a():
    print("Running Scenario A: No Infrastructure")
    steps = 40
    for i in range(steps):
        t = i / steps
        speed = 65.0
        flood_severity = min(1.0, t * 2.5)
        friction = round(0.8 * (1 - flood_severity), 3)
        braking_distance = (speed ** 2) / max(friction * 2 * 9.8 * 3.28, 0.1)
        distance_to_hazard = max(1, 200 - (t * 220))
        collision_risk = round(min(0.92, braking_distance / distance_to_hazard), 3)

        if t < 0.3:
            av_action = "cruising"
        else:
            av_action = "hydroplaning"

        write_metrics({
            "scenario_id": "flood_a",
            "scenario_label": "Without Infrastructure",
            "timestamp": round(time.time(), 2),
            "speed_mph": round(speed, 1),
            "road_friction": friction,
            "collision_risk": collision_risk,
            "infrastructure_status": "none",
            "perception_confidence": round(max(0.1, 0.32 - t * 0.15), 3),
            "av_action": av_action
        })
        time.sleep(0.3)

def run_scenario_b():
    print("Running Scenario B: With V2X Intervention")
    steps = 40
    for i in range(steps):
        t = i / steps
        flood_severity = min(1.0, t * 2.5)
        friction = round(0.8 * (1 - flood_severity * 0.5), 3)

        if t < 0.2:
            speed = 65.0
            infra = "none"
            av_action = "cruising"
            confidence = 0.91
        elif t < 0.4:
            speed = round(65 - (t - 0.2) * 150, 1)
            infra = "warning_sent"
            av_action = "warned"
            confidence = 0.92
        elif t < 0.6:
            speed = round(max(35, 65 - (t - 0.2) * 200), 1)
            infra = "speed_advised"
            av_action = "decelerating"
            confidence = 0.93
        else:
            speed = 35.0
            infra = "speed_advised"
            av_action = "safe_stop"
            confidence = 0.94

        braking_distance = (speed ** 2) / max(friction * 2 * 9.8 * 3.28, 0.1)
        distance_to_hazard = max(1, 200 - (t * 180))
        collision_risk = round(min(0.18, braking_distance / distance_to_hazard), 3)

        write_metrics({
            "scenario_id": "flood_b",
            "scenario_label": "With V2X Intervention",
            "timestamp": round(time.time(), 2),
            "speed_mph": speed,
            "road_friction": friction,
            "collision_risk": collision_risk,
            "infrastructure_status": infra,
            "perception_confidence": confidence,
            "av_action": av_action
        })
        time.sleep(0.3)

if __name__ == "__main__":
    run_scenario_a()