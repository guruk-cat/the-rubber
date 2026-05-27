import argparse
import pathlib
import sys
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from Simulator import Simulation, LaunchConfiguration
from Plotter import Trajectory3DPlot

MOUND_HEIGHT = 0.254  # meters (10 inches above field level)


def terminate(record):
    state = record[-1]
    if state[3] < 0:    # z < 0: ball hit the ground
        return True
    if state[2] < -1:   # y < -1: ball is 1m past home plate (catcher position)
        return True
    if state[0] > 10:   # t > 10s: safety valve
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description='Baseball pitch simulator')
    parser.add_argument('config', help='Path to YAML launch configuration file')
    parser.add_argument('--plot', '-p', nargs='?', const='animated', choices=['static', 'animated'], help='Display 3D trajectory plot')
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    sim = Simulation()
    launch = LaunchConfiguration()

    if 'simulation' in cfg:
        sim.configure(cfg['simulation'])
    launch.configure(cfg['launch'])

    trajectory = sim.run(launch, terminate)

    print(f"Simulation complete: {len(trajectory)} steps, "
          f"final t={trajectory[-1][0]:.3f}s, "
          f"final pos=({trajectory[-1][1]:.2f}, {trajectory[-1][2]:.2f}, {trajectory[-1][3]:.2f}) m")

    if args.plot:
        plotter = Trajectory3DPlot()
        plotter.plot([trajectory], animate=(args.plot == 'animated'))


if __name__ == '__main__':
    main()
