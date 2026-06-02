import argparse
import pathlib
import sys
import yaml
import numpy
import os
import pint

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / 'src'))

from phys import Simulation, Configuration
from plotting import Trajectory3DPlot

ureg = pint.UnitRegistry()
pint.set_application_registry(ureg)

PLATE_Y = 0.2159  # middle of plate (8.5 inches from back tip); Statcast 2026+

def m_to_in(quantity_m):
    return ureg.Quantity(quantity_m, "meter").to("inch").magnitude

def terminate(record):
    state = record[-1]
    if state[3] < 0:    # z < 0: ball hit the ground
        return True
    if state[2] < -1:   # y < -1: ball is at catcher position
        return True
    if state[0] > 10:   # t > 10s: safety valve
        return True
    return False

def crossing_point(traj):
    y = traj[:, 2]
    above = numpy.where(y >= PLATE_Y)[0]
    if not len(above) or above[-1] + 1 >= len(traj):
      return None
    
    i = above[-1]
    alpha = (y[i] - PLATE_Y) / (y[i] - y[i + 1])
    x = float(traj[i, 1] + alpha * (traj[i + 1, 1] - traj[i, 1]))
    z = float(traj[i, 3] + alpha * (traj[i + 1, 3] - traj[i, 3]))
    return numpy.array((x, z))

def main():
    parser = argparse.ArgumentParser(description='Launch script for testing compound error from v_0')
    parser.add_argument('--plot', '-p', nargs='?', const='animated', choices=['static', 'animated'], help='Display 3D trajectory plot')
    args = parser.parse_args()
    os.system('cls' if os.name == 'nt' else 'clear')
    print("Working on it...")

    tests_dir = pathlib.Path(__file__).parent / 'init-v-tests'
    config_paths = [
        tests_dir / 'adjusted.yaml',
        tests_dir / 'pseudo.yaml',
    ]

    trajectories = []
    for config_path in config_paths:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        sim = Simulation()
        launch = Configuration()
        launch.configure(cfg['launch'])
        trajectory = numpy.array(sim.run(launch, terminate))
        trajectories.append(trajectory)

    cross_adjusted = crossing_point(trajectories[0]) 
    cross_pseudo = crossing_point(trajectories[1])
    diff = numpy.abs(cross_adjusted - cross_pseudo)

    a_x = m_to_in(cross_adjusted[0])
    a_z = m_to_in(cross_adjusted[1])
    p_x = m_to_in(cross_pseudo[0])
    p_z = m_to_in(cross_pseudo[1])
    d_x = m_to_in(diff[0])
    d_z = m_to_in(diff[1])

    sys.stdout.write("\033[F\033[K")
    print(f"Adjusted trajectory crossed plate at    (x, z) = ({a_x:.4f}, {a_z:.4f}) inches")
    print(f"Pseudo trajectory crossed plate at      (x, z) = ({p_x:.4f}, {p_z:.4f}) inches")
    print(f"\nThe difference is ({d_x:.4f}, {d_z:.4f}) inches\n")

    if args.plot:
        labels = [pathlib.Path(p).stem for p in config_paths]
        plotter = Trajectory3DPlot()
        plotter.plot(trajectories, labels=labels, animate=(args.plot == 'animated'))

if __name__ == '__main__':
    main()