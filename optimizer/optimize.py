import argparse
import glob
import pathlib
import sys
import pint
import numpy
import yaml
import os
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'src'))
from phys import Simulation, Configuration



# UNIT HELPERS

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity  # type: ignore[misc]
pint.set_application_registry(ureg)

xhat = numpy.array([1, 0, 0], dtype=float)
yhat = numpy.array([0, 1, 0], dtype=float)
zhat = numpy.array([0, 0, 1], dtype=float)

def si_mag(quant):
  # Strip pint quantity to its SI base-unit magnitude.
  return quant.to_base_units().magnitude 



# OPTIMIZER SETUP CONSTANTS

k_unit = 'kg*s/m'
k_init = Q_(1e-4, k_unit)     # arbitrary initial value for constant K
delta_k_ratio = 0.01                # delta K is 1% of K; used in error compute
target_step_fraction = 0.1          # used to calibrate learning rate

estimated_flight_time = si_mag(Q_(0.5, "second"))
err_goal_displacement = si_mag(Q_(0.5, "inch"))
err_goal_da = 2 * err_goal_displacement / (estimated_flight_time ** 2)



# CLI HELPERS

def clear_cli():
    os.system('cls' if os.name == 'nt' else 'clear')

def delete_lines(n):
    for _ in range(n):
        # \033[F moves cursor up one line; \033[K clears that line
        sys.stdout.write("\033[F\033[K")



# FILE I/O

def load_configs(patterns):
    # Expand glob patterns, load each YAML, and return a list of config dicts.
    # Files without a 'training' block are skipped with a warning.
    paths = []
    for pattern in patterns:
        matched = sorted(glob.glob(pattern))
        paths.extend(matched if matched else [pattern])

    cfgs = []
    for path in paths:
        with open(path) as f:
            cfg = yaml.safe_load(f)
        if 'training' not in cfg:
            print(f"Warning: {path} has no 'training' block — skipping.")
            continue
        cfgs.append(cfg)

    if not cfgs:
        raise ValueError("No config files with a 'training' block were found.")
    return cfgs

def extract_true_acc(cfgs):
    # Pull ax, ay, az from each config's 'training' block.
    # Returns an (N, 3) numpy array of [ax, ay, az] in m/s².
    result = []
    for cfg in cfgs:
        t = cfg['training']
        ax = si_mag(Q_(t['ax']))
        ay = si_mag(Q_(t['ay']))
        az = si_mag(Q_(t['az']))
        result.append([ax, ay, az])
    return numpy.array(result)

def select_batches():
    # Lists subdirectories of `learning samples/` and prompts the user to 
    # choose which ones to include in the training run.

    samples_dir = pathlib.Path(__file__).parent / 'learning samples'
    all_batches = sorted([d for d in samples_dir.iterdir() if d.is_dir()])

    if not all_batches:
        raise ValueError(f"No subdirectories found in {samples_dir}")

    clear_cli()
    print("\nAvailable training batches:")
    for i, b in enumerate(all_batches, 1):
        n = len(list(b.glob('*.yaml')))
        print(f"  [{i}] {b.name}  ({n} pitches)")

    while True:
        raw = input("\nBatches to include (e.g. '1 3 4'), or Enter for all: ").strip()
        if not raw:
            selected = all_batches
            break
        try:
            indices  = [int(x) - 1 for x in raw.split()]
            if any(i < 0 or i >= len(all_batches) for i in indices):
                raise IndexError
            selected = [all_batches[i] for i in indices]
            break
        except (ValueError, IndexError):
            print(f"  Invalid input. Enter numbers between 1 and {len(all_batches)}, separated by spaces.")

    clear_cli()
    print(f"\nSelecting {len(selected)} batches...")
    return selected



# MATH STUFF

def squared_err(prediction, reference):
    # pred, true: (N, M) arrays. Returns a length-N array of per-sample squared errors.
    diff = numpy.asarray(prediction) - numpy.asarray(reference)
    return numpy.sum(diff**2, axis=1)

def de_dk(errs_k, errs_k_delta, delta_k):
    # Numerical finite-difference gradient of mean squared error w.r.t. K.
    # errs_k, errs_k_delta: per-sample error arrays at K and K+delta_k.
    # delta_k: finite-difference step in SI units (kg·s/m).
    return (numpy.mean(errs_k_delta) - numpy.mean(errs_k)) / delta_k

def run_single(cfg, k):
    # cfg: full YAML dict (with 'launch', optionally 'simulation').
    # k: magnus_coefficient as a pint Quantity.
    # Returns numpy [ax, ay, az] in m/s².
    sim = Simulation()
    if 'simulation' in cfg:
        sim.configure(cfg['simulation'])
    sim.config.magnus_coefficient = k
    launch = Configuration()
    launch.configure(cfg['launch'])
    return sim.point_run(launch)

def run_batch(cfgs, k, label, info=None):
    # Runs run_single for each config with progress updates
    if info is not None:
        batch_name = info[0]
        name_w = info[1]

    results = []
    total   = len(cfgs)
    for i, cfg in enumerate(cfgs):
        if info is not None:
            if i > 0:
                delete_lines(1)
            print(f'  [{batch_name:<{name_w}}] {label}: {i}/{total}')
        results.append(run_single(cfg, k))

    if info is not None:
        # Clear the line when done so the caller can print its own output
        delete_lines(1)
    return results

def correct_k_from_err(lr, grad):
    # Gradient descent correction: the additive update to apply to K.
    # Caller does: k += correct_k_from_err(lr, grad)
    return -lr * grad

def gradient_step(cfgs, true_acc, k, lr, info):
    # Run one gradient descent step over a batch.
    # Returns updated k (float, SI) and the RMS error before the update.
    delta_k = k * delta_k_ratio
    k_q = Q_(k,           'kg * s / m')
    k_delta_q = Q_(k + delta_k, 'kg * s / m')

    pred_k = run_batch(cfgs, k_q, 'K', info=info)
    pred_k_delta = run_batch(cfgs, k_delta_q, 'K+δ',info=info)

    pred_k_arr = numpy.array(pred_k)
    pred_k_delta_arr = numpy.array(pred_k_delta)

    errs_k = squared_err(pred_k_arr,       true_acc)
    errs_k_delta = squared_err(pred_k_delta_arr, true_acc)

    grad = de_dk(errs_k, errs_k_delta, delta_k)
    dk = correct_k_from_err(lr, grad)
    k += dk
    rms_err = numpy.sqrt(numpy.mean(errs_k))
    mean_dk = numpy.mean(dk)

    return k, rms_err, mean_dk

def calibrate_learning_rate(batches, k, redo=False):
    # Run one batch at K and K+δ to measure the gradient scale, then set lr
    # so the first step moves K by target_step_fraction of its initial value.
    _, cfgs, true_acc = batches[0]
    delta_k   = k * delta_k_ratio
    k_q       = Q_(k,           'kg * s / m')
    k_delta_q = Q_(k + delta_k, 'kg * s / m')

    if redo:
        print("  Re-calibrating learning rate...")
    else:
        print("\nCalibrating learning rate...")
    pred_k       = run_batch(cfgs, k_q, 'K')
    pred_k_delta = run_batch(cfgs, k_delta_q, 'K+δ')

    errs_k       = squared_err(numpy.array(pred_k), true_acc)
    errs_k_delta = squared_err(numpy.array(pred_k_delta), true_acc)

    grad = de_dk(errs_k, errs_k_delta, delta_k)
    lr   = target_step_fraction * abs(k) / abs(grad)
    print(f"  Calibrated: grad={grad:.4e}  lr={lr:.4e}")
    time.sleep(1)
    return lr

def main():
    parser = argparse.ArgumentParser(description='Optimize magnus coefficient K via gradient descent.')
    parser.add_argument('--epochs', type=int, default=50,
                        help='Number of full passes over all selected batches (default: 10).')
    args = parser.parse_args()

    batch_dirs = select_batches()

    # Pre-load all configs and ground-truth accelerations so disk I/O isn't repeated each epoch.
    batches = []
    for d in batch_dirs:
        cfgs = load_configs([str(d / '*.yaml')])
        true_acc = extract_true_acc(cfgs)
        batches.append((d.name, cfgs, true_acc))
        print(f"  {d.name}: {len(cfgs)} pitches loaded.")
    time.sleep(1)

    k  = si_mag(k_init)
    lr = calibrate_learning_rate(batches, k)
    recalibrate_at = 5
    batch_count = len(batches)
    name_w = max(len(name) for name, _, _ in batches)

    converged = False
    for epoch in range(1, args.epochs + 1):
        print(f"\n--- Epoch {epoch}/{args.epochs} ---")
        '''
        if epoch % recalibrate_at == 0:
            lr = calibrate_learning_rate(batches, k, redo=True)
        '''
        rms_sum = 0
        dk_sum = 0
        for batch_name, cfgs, true_acc in batches:
            k, rms_err, dk = gradient_step(cfgs, true_acc, k, lr, (batch_name, name_w))
            # print(f"  [{batch_name:<{name_w}}]  K={k:.4e} ({k_unit})  RMS={rms_err:.4f} (m/s²)  Mean dK={dk:.4e} ({k_unit})")
            rms_sum += rms_err
            dk_sum += dk

            if rms_err <= err_goal_da:
                converged = True
                break
        
        mean_rms = rms_sum / batch_count

        print("")
        # print(f"  Mean dK across all batches        : {mean_dk:.4e} ({k_unit})")
        print(f"  K after epoch     : {k:.4e} ({k_unit})")
        print(f"  Mean RMS error    : {mean_rms:.4f} (m/s²)")

        if converged:
            print(f"\nConverged at epoch {epoch}.")
            break
    else:
        print(f"\nReached {args.epochs} epoch(s) without converging.")

    print(f"Final K = {k:.6e} kg·s/m")



if __name__ == '__main__':
    main()