from flask import Flask, request, jsonify
from flask_cors import cross_origin
import threading
import state_machine

app = Flask(__name__)
current_thread = None

@app.route('/trigger', methods=['POST', 'OPTIONS'])
@cross_origin()
def trigger():
    global current_thread
    data = request.json
    scenario_id = data.get('scenario_id')

    if scenario_id == 'flood_a':
        fn = state_machine.run_scenario_a
    elif scenario_id == 'flood_b':
        fn = state_machine.run_scenario_b
    else:
        return jsonify({"error": "unknown scenario"}), 400

    current_thread = threading.Thread(target=fn)
    current_thread.start()
    return jsonify({"status": "started", "scenario_id": scenario_id})

@app.route('/metrics', methods=['GET'])
@cross_origin()
def metrics():
    with open('metrics.json') as f:
        import json
        return jsonify(json.load(f))

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8765, debug=False)