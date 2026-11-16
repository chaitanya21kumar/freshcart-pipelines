"""Run C1/C2/C3/C4 with the real Mage CLI and capture unedited output."""
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence'

def run():
    EVIDENCE.mkdir(exist_ok=True)
    results = []
    for depth in range(1, 6):
        for filename in ['iris_predictions.csv', 'iris_metrics.csv', 'iris_model.pkl']:
            (ROOT / filename).unlink(missing_ok=True)
        command = [str(Path(sys.executable).with_name('mage')), 'run', 'iris_project',
                   'iris_classifier', '--test', '--runtime-vars', json.dumps({'max_depth': depth})]
        started = time.time()
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=180)
        log = result.stdout
        (EVIDENCE / f'C2-depth-{depth}.txt').write_text('$ ' + ' '.join(command[1:]) + '\n' + log)
        import re
        found = re.search(r'Test accuracy = ([0-9.]+)', log)
        row = {'max_depth': depth, 'test_accuracy': float(found.group(1)) if found else None,
               'exit_code': result.returncode, 'accuracy_gate_failed': 'Model accuracy is below 80%' in log,
               'predictions_created': (ROOT / 'iris_predictions.csv').exists(),
               'metrics_created': (ROOT / 'iris_metrics.csv').exists(),
               'elapsed_seconds': round(time.time() - started, 2)}
        results.append(row)
        print(row, flush=True)
    (EVIDENCE / 'C2-results.json').write_text(json.dumps(results, indent=2))
    # Leave the default successful run and its outputs visible for the notebook and UI.
    command = [str(Path(sys.executable).with_name('mage')), 'run', 'iris_project',
               'iris_classifier', '--test']
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=180)
    (EVIDENCE / 'C1-default-run.txt').write_text('$ mage run iris_project iris_classifier --test\n'+result.stdout)
    print('Default run exit:', result.returncode, flush=True)
    if result.returncode: raise SystemExit(result.returncode)

if __name__ == '__main__': run()
