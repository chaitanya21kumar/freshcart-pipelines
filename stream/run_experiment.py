"""Run six real consumers and the 120-second dispatcher; verify every D1 probe."""
import json, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DRIVERS = {'Ravi': 'bangalore.koramangala.*', 'Priya': 'bangalore.indiranagar.*',
           'Arjun': 'bangalore.*.ride', 'Meena': 'bangalore.*.food',
           'Karthik': 'chennai.tnagar.food', 'Control': 'bangalore.#'}

def read_events(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.startswith('{')]

def main():
    evidence = ROOT/'evidence'; evidence.mkdir(exist_ok=True)
    processes = []; files = []
    try:
        for name, pattern in DRIVERS.items():
            file = (evidence/f'D-driver-{name}.txt').open('w'); files.append(file)
            proc = subprocess.Popen([sys.executable, '-m', 'stream.driver', name, pattern, '--duration', '128'],
                                    cwd=ROOT, stdout=file, stderr=subprocess.STDOUT)
            processes.append(proc)
        for attempt in range(100):
            if all('"event": "READY"' in (evidence/f'D-driver-{name}.txt').read_text() for name in DRIVERS): break
            if any(proc.poll() is not None for proc in processes): raise RuntimeError('A driver exited before READY')
            time.sleep(0.1)
        else: raise RuntimeError('Drivers did not become ready')
        print('All six drivers READY; starting two-minute dispatcher', flush=True)
        with (evidence/'D-dispatcher.txt').open('w') as file:
            subprocess.run([sys.executable, '-m', 'stream.dispatcher', '--duration', '120', '--probe'],
                           cwd=ROOT, stdout=file, stderr=subprocess.STDOUT, check=True, timeout=140)
        for proc in processes: proc.wait(timeout=15)
    finally:
        for proc in processes:
            if proc.poll() is None: proc.terminate(); proc.wait(timeout=10)
        for file in files: file.close()
    predicted = list(json.loads((evidence/'D1-predictions.json').read_text())['routing'].items())
    actual = {}; nacks = {}; acks = {}
    for name in DRIVERS:
        events = read_events(evidence/f'D-driver-{name}.txt')
        actual[name] = {e['id'] for e in events if e['event']=='ACK'}
        nacks[name] = sum(e['event']=='NACK_DISCARD' for e in events)
        acks[name] = sum(e['event']=='ACK' for e in events)
    rows = []
    for i,(key, expected) in enumerate(predicted,1):
        received = [name for name in DRIVERS if f'D1-{i}' in actual[name]]
        assert set(received)==set(expected),(key, received, expected)
        rows.append({'key':key, 'expected':expected, 'actual':received, 'match':True})
    publisher = read_events(evidence/'D-dispatcher.txt')
    finish = next(e for e in publisher if e['event']=='FINISHED')
    assert finish['elapsed_seconds'] >= 120 and finish['random_messages']==60
    assert all(nacks[name]==6 for name in ['Ravi','Meena','Control'])
    summary={'routing':rows, 'nacks':nacks, 'acks':acks, 'duration':finish,
             'bad_messages_per_10': True, 'driver_count':len(DRIVERS)}
    (evidence/'D-summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__ == '__main__': main()
