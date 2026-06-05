import pathlib
import sys
import argparse
import glob
import yaml


sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'main'))
from phys import Simulation, Configuration

def main():
    parser = argparse.ArgumentParser(description='Baseball pitch simulator')
    parser.add_argument('configs', nargs='+', help='Path(s) to YAML launch configuration file(s); glob patterns are supported')
    args = parser.parse_args()

    # Expand any glob patterns (handles shells that don't expand them, e.g. Windows cmd)
    config_paths = []
    for pattern in args.configs:
        matched = sorted(glob.glob(pattern))
        config_paths.extend(matched if matched else [pattern])

    for i, config_path in enumerate(config_paths, 1):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        sim = Simulation()
        launch = Configuration()

        if 'simulation' in cfg:
            sim.configure(cfg['simulation'])
        launch.configure(cfg['launch'])

        print(f"Simulation #{i}:\n")
        sim.point_run(launch, print_debug=True)

if __name__ == '__main__':
    main()