import pathlib
import argparse
import glob
import sys
import yaml
import numpy

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from phys import Configuration

def main():
    parser = argparse.ArgumentParser(description='Quickly check init vectors')
    parser.add_argument('configs', nargs='+', help='Path(s) to YAML launch configuration file(s); glob patterns are supported')
    args = parser.parse_args()

    # Expand any glob patterns (handles shells that don't expand them, e.g. Windows cmd)
    config_paths = []
    for pattern in args.configs:
        matched = sorted(glob.glob(pattern))
        config_paths.extend(matched if matched else [pattern])
    labels = [pathlib.Path(p).stem for p in config_paths]

    for i, config_path in enumerate(config_paths):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        config = Configuration()
        config.configure(cfg['launch'])
        velo = numpy.array(config.get_velocity())
        spin = numpy.array(config.get_spin())
        speed = numpy.linalg.norm(velo)

        print(f"\n[{labels[i]}]")
        print(f"  init speed  : {speed} (m/s)")
        print(f"  init velo   : [ {velo[0]}, {velo[1]}, {velo[2]} ]")
        print(f"  init spin   : [ {spin[0]}, {spin[1]}, {spin[2]} ]")

if __name__ == '__main__':
    main()