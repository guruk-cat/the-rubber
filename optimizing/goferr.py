'''
GOFErr stands for "Good Ole Fashioned Error"
'''

import glob
import pathlib
import sys
import pint
import numpy
from math import sqrt
import yaml
import os
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'main'))
from phys import Simulation, Configuration
from optimize import load_configs, select_batches, squared_err

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity  # type: ignore[misc]
pint.set_application_registry(ureg)

xhat = numpy.array([1, 0, 0], dtype=float)
yhat = numpy.array([0, 1, 0], dtype=float)
zhat = numpy.array([0, 0, 1], dtype=float)

# middle of plate; Statcast 2026+
PLATE_Y = Q_(8.5, "inch")
report_d_error = "inch"

def si_mag(quant):
  # Strip pint quantity to its SI base-unit magnitude.
  return quant.to_base_units().magnitude 

def clear_cli():
    os.system('cls' if os.name == 'nt' else 'clear')

def delete_lines(n):
    for _ in range(n):
        # \033[F moves cursor up one line; \033[K clears that line
        sys.stdout.write("\033[F\033[K")

def terminate(record):
    state = record[-1]
    if state[3] < 0:
        return True
    if state[2] < -0.5:  
        return True
    if state[0] > 5:    # safety valve  
        return True
    return False



def get_plate_xz(cfgs):
    result = []
    for cfg in cfgs:
        t = cfg['training']
        plate_x = si_mag(Q_(t['plate_x']))
        plate_z = si_mag(Q_(t['plate_z']))
        result.append([plate_x, plate_z])
    return numpy.array(result)

def crossing_point(traj):
    y = traj[:, 2]
    i = numpy.argmin(numpy.abs(y - si_mag(PLATE_Y)))
    return i

def main():
    batch_dirs = select_batches()
    delete_lines(1)
    errs = []
    for d in batch_dirs:
        print(f"Computing errors for [{d.name}]")
        cfgs = load_configs([str(d / '*.yaml')])
        true_plates = get_plate_xz(cfgs)
        pred_plates = []

        for i, cfg in enumerate(cfgs):
            print(f"...running pitch # {i}")
            sim = Simulation()
            launch = Configuration()
            launch.configure(cfg['launch'])
            trajectory = numpy.array(sim.run(launch, terminate))
            crossing_i = crossing_point(trajectory)
            pred_plates.append([trajectory[crossing_i][1], trajectory[crossing_i][3]])
            delete_lines(1)
            print(f"pred: {trajectory[crossing_i][1]}, {trajectory[crossing_i][3]}")
            print(f"true: {true_plates[i]}\n")
        numpy.array(pred_plates)
        err = numpy.mean(squared_err(pred_plates, true_plates))
        errs.append(err)
        delete_lines(1)
    
    displacement = Q_(sqrt(numpy.mean(numpy.array(errs))), "meter")
    displacement = displacement.to(report_d_error).magnitude
    print(f"Average error when crossing plate: {displacement:.2f} ({report_d_error})")


if __name__ == '__main__':
    main()