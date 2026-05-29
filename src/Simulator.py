import re
import types
import numbers
import pint
import numpy
from numpy.linalg import norm


ureg = pint.UnitRegistry()
ureg.define('percent = 0.01 rad')  # convenience unit for relative error tolerances
Q_ = ureg.Quantity
pint.set_application_registry(ureg)

xhat = numpy.array([1, 0, 0], dtype=float)
yhat = numpy.array([0, 1, 0], dtype=float)
zhat = numpy.array([0, 0, 1], dtype=float)

# pitcher body proportion constants (applied in _configure_physical)
_K_SH           = 0.63    # shoulder height as fraction of pitcher height during delivery (absorbs knee bend + forward lean)
_K_ARM          = 0.37    # arm length as fraction of pitcher height
_MOUND_HEIGHT_M = 0.254   # standard mound height above field level (10 in)


def rot_x(theta):
  t = theta.to('radian').magnitude
  return numpy.array([[1, 0,            0           ],
                      [0, numpy.cos(t), -numpy.sin(t)],
                      [0, numpy.sin(t),  numpy.cos(t)]])

def rot_y(theta):
  t = theta.to('radian').magnitude
  return numpy.array([[ numpy.cos(t), 0, numpy.sin(t)],
                      [ 0,            1, 0           ],
                      [-numpy.sin(t), 0, numpy.cos(t)]])

def rot_z(theta):
  t = theta.to('radian').magnitude
  return numpy.array([[numpy.cos(t), -numpy.sin(t), 0],
                      [numpy.sin(t),  numpy.cos(t), 0],
                      [0,             0,            1]])

def rot_axis(axis, theta):
  # Rodrigues rotation matrix: angle theta around arbitrary axis.
  k = numpy.asarray(axis, dtype=float)
  k = k / norm(k)
  t = theta.to('radian').magnitude
  K = numpy.array([[    0, -k[2],  k[1]],   # skew-symmetric cross-product matrix for k
                   [ k[2],     0, -k[0]],
                   [-k[1],  k[0],     0]])
  return numpy.cos(t)*numpy.eye(3) + numpy.sin(t)*K + (1 - numpy.cos(t))*numpy.outer(k, k)

def si_mag(quant):
  # Strip pint quantity to its SI base-unit magnitude.
  return quant.to_base_units().magnitude

def _parse_quantity(s):
  # Handle "X ft Y in" compound format not natively supported by pint.
  # Plain numbers default to metres.
  if isinstance(s, (int, float)):
    return Q_(float(s), 'm')
  m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*ft\s+(\d+(?:\.\d+)?)\s*in\s*$', s)
  if m:
    return Q_(float(m.group(1)) * 12 + float(m.group(2)), 'in')
  return Q_(s)

def arm_direction(arm_slot_rad, handedness, arm_extension_m=0.0, arm_length_m=1.0):
  # Unit vector from shoulder to hand at release, in world coordinates.
  # Righty arm is on world -x side (pitcher's right); lefty on +x.
  sign  = -1.0 if handedness.lower().startswith('r') else 1.0
  e     = arm_extension_m / arm_length_m   # normalised forward lean ∈ [0, 1)
  scale = numpy.sqrt(1.0 - e**2)          # lateral/vertical amplitude shrinks as arm leans forward
  v = numpy.array([sign * numpy.cos(arm_slot_rad) * scale,
                   -e,
                   numpy.sin(arm_slot_rad) * scale])
  return v / norm(v)

def build_pitch_frame(release_world, arm_dir):
  '''
  Build the pitch-to-world rotation matrix M (v_world = M @ v_pitch).
  y_pitch: unit vector from home plate toward release point.
  x_pitch: normal to the plane of y_pitch and arm (pure backspin/topspin axis).
  z_pitch: right-hand completion — points roughly up.
  Raises ValueError if arm_dir is parallel to y_pitch (degenerate frame).
  '''
  y_pitch = release_world / norm(release_world)
  cross   = numpy.cross(y_pitch, arm_dir)
  if norm(cross) < 1e-6:
    raise ValueError("arm_dir is parallel to y_pitch — pitch frame is degenerate (arm pointing straight at plate).")
  x_pitch = cross / norm(cross)
  z_pitch = numpy.cross(x_pitch, y_pitch)
  return numpy.column_stack([x_pitch, y_pitch, z_pitch])


class Simulation:
  def __init__(self):
    self.config = types.SimpleNamespace()
    self.config.wind_speed                  = Q_(0, 'mph')
    self.config.wind_direction              = Q_(0, 'degree')
    self.config.drag_coefficient            = Q_(0.0007884037809624002, 'kg/m')
    self.config.magnus_coefficient          = Q_(2.2075e-06, 'kg * s / m')
    self.config.magnus_model                = 'squared velocity'
    self.config.ball_mass                   = Q_(145, 'g')
    self.config.ball_diameter               = Q_(3, 'in')
    self.config.gravitational_acceleration  = Q_(9.8, 'm/s**2')
    self.config.time_step                   = Q_(1, 'ms')
    self.config.time_step_growth_rate       = Q_(1, '')
    self.config.error_tolerance             = Q_(1, 'percent')
    self.config.auto_converge_time_step     = True

  def configure(self, config):
    config_keys_used = []
    for k in self.config.__dict__:
      config_key = None
      if k in config:
        config_key = k
      if k.replace("_", " ") in config:
        config_key = k.replace("_", " ")

      if config_key is not None:
        config_keys_used.append(config_key)
        new_val = Q_(config[config_key])
        if new_val.dimensionality != self.config.__dict__[k].dimensionality:
          raise Exception(f"Configuration parameter '{config_key}' has wrong dimensions. "
                          f"Expected '{self.config.__dict__[k].dimensionality}' "
                          f"but got '{new_val.dimensionality}'.")
        self.config.__dict__[k] = new_val

    if len(config_keys_used) != len(config.keys()):
      print("Warning: there were unused keys when configuring Simulation:")
      for k in list(set(config.keys()) - set(config_keys_used)):
        print("  ", k)
      print("Make sure you didn't mispell something.")

  @property
  def state_size(self):
    '''
    state vector layout:
    [0]    t
    [1:4]  x, y, z     (m)
    [4:7]  vx, vy, vz  (m/s)
    [7:10] wx, wy, wz  (rad/s)
    '''
    return 10

  def derivative(self, state):
    dsdt = numpy.zeros(self.state_size)

    dsdt[0]   = 1           # dt/dt = 1
    dsdt[1:4] = state[4:7]  # dx/dt = v
    # dw/dt = 0 (spin treated as constant for now)

    # dv/dt = (Fg + Fd + Fm) / m
    dsdt[4:7] -= si_mag(self.config.gravitational_acceleration) * zhat  # gravity
    speed = norm(state[4:7])
    dsdt[4:7] -= si_mag(self.config.drag_coefficient) * speed * state[4:7] / si_mag(self.config.ball_mass)  # drag
    if self.config.magnus_model == 'squared velocity':
      dsdt[4:7] += si_mag(self.config.magnus_coefficient) * speed * numpy.cross(state[7:10], state[4:7]) / si_mag(self.config.ball_mass)
    elif self.config.magnus_model == 'linear velocity':
      dsdt[4:7] += si_mag(self.config.magnus_coefficient) * numpy.cross(state[7:10], state[4:7]) / si_mag(self.config.ball_mass)
    else:
      raise Exception(f"Unrecognized magnus model '{self.config.magnus_model}'")

    return dsdt

  def rk4(self, time_step, state):
    k1 = time_step * self.derivative(state)
    k2 = time_step * self.derivative(state + k1 / 2)
    k3 = time_step * self.derivative(state + k2 / 2)
    k4 = time_step * self.derivative(state + k3)
    return state + (k1 + 2*k2 + 2*k3 + k4) / 6

  def _step_error(self, s0, s1, s2):
    # relative error: how much the double-half-step s2 differs from the full-step s1,
    # normalised by the total displacement from s0
    return norm(s2 - s1) / norm(s2 - s0)

  def run(self, launch_config, terminate_function=lambda record: len(record) > 1000, record_all=True):
    state = numpy.zeros(self.state_size)
    state[1:4]  = launch_config.get_position()
    state[4:7]  = launch_config.get_velocity()
    state[7:10] = launch_config.get_spin()

    record = [state.copy()]
    dt = self.config.time_step.to('s').magnitude
    while not terminate_function(record):
      # adaptive step: compare one full step vs two half steps; halve dt if error too large
      while True:
        s1  = self.rk4(dt,   state)
        s2  = self.rk4(dt/2, self.rk4(dt/2, state))
        err = self._step_error(state, s1, s2)
        if self.config.auto_converge_time_step and err > self.config.error_tolerance.to('').magnitude:
          print(f"Info: decreasing time step from {dt} to {dt/2}")
          dt /= 2
        else:
          break

      state = s2
      if record_all:
        record.append(state.copy())
      else:
        record[0] = state.copy()

      dt *= self.config.time_step_growth_rate.to('').magnitude

    return record


class LaunchConfiguration:
  def __init__(self):
    self.position       = Q_(0, 'm') * xhat
    self.speed          = Q_(0, 'm/s')
    self.direction      = -yhat.copy()
    self.spin           = Q_(0, 'rad/s')
    self.spin_direction = xhat.copy()

  def configure(self, config):
    def load_tensor(v):
      # normalise list inputs: list of Q_, list of strings, or plain numbers
      if isinstance(v, list):
        if isinstance(v[0], Q_):
          units = v[0].units
          return units * numpy.array([q.to(units).magnitude for q in v])
        if isinstance(v[0], str):
          units = Q_(v[0]).units
          return units * numpy.array([Q_(q).to(units).magnitude for q in v])
        if isinstance(v[0], numbers.Number):
          return numpy.array(v, dtype=float)
      return v

    def decompose(v):
      # Split a vector quantity into (float magnitude, units str, unit direction array).
      tensor = v.magnitude if isinstance(v, Q_) else v
      units  = str(v.units) if isinstance(v, Q_) else None
      mag    = float(norm(tensor))
      uhat   = tensor / mag if mag > 0 else None
      return mag, units, uhat

    config_keys_used = []

    # pitch_frame is processed first so individual keys below can override if present
    if 'pitch_frame' in config:
      self.configure_pitch_frame(config['pitch_frame'])
      config_keys_used.append('pitch_frame')

    if 'position' in config:
      self.position = load_tensor(config['position'])
      config_keys_used.append('position')

    # velocity vector OR speed + direction — both supported
    if 'velocity' in config:
      mag, units, uhat = decompose(load_tensor(config['velocity']))
      self.speed     = Q_(mag, units or 'm/s')
      self.direction = uhat if uhat is not None else -yhat.copy()
      config_keys_used.append('velocity')

    if 'speed' in config:
      self.speed = Q_(config['speed'])
      config_keys_used.append('speed')

    if 'direction' in config:
      d = load_tensor(config['direction'])
      d = d.magnitude if isinstance(d, Q_) else numpy.asarray(d, dtype=float)
      self.direction = d / norm(d)
      config_keys_used.append('direction')

    # angular velocity vector OR spin + spin_direction — both supported
    if 'angular_velocity' in config:
      mag, units, uhat = decompose(load_tensor(config['angular_velocity']))
      self.spin           = Q_(mag, units or 'rad/s')
      self.spin_direction = uhat if uhat is not None else xhat.copy()
      config_keys_used.append('angular_velocity')

    if 'spin' in config:
      self.spin = Q_(config['spin'])
      config_keys_used.append('spin')

    for k in ['spin_direction', 'spin direction']:
      if k in config:
        d = load_tensor(config[k])
        d = d.magnitude if isinstance(d, Q_) else numpy.asarray(d, dtype=float)
        self.spin_direction = d / norm(d)
        config_keys_used.append(k)

    if len(config_keys_used) != len(config.keys()):
      print("Warning: there were unused keys when configuring LaunchConfiguration:")
      for k in list(set(config.keys()) - set(config_keys_used)):
        print("  ", k)
      print("Make sure you didn't mispell something.")

  def configure_pitch_frame(self, config):
    if 'pitcher_height' in config:
      self._configure_physical(config)
    elif 'release_pos_x' in config:
      raise NotImplementedError("Statcast direct mode (release_pos_x) not yet implemented.")
    else:
      raise ValueError("pitch_frame must contain 'pitcher_height' (physical mode) or 'release_pos_x' (Statcast mode).")

  def _configure_physical(self, config):
    handedness   = config['handedness']
    height_m     = _parse_quantity(config['pitcher_height']).to('m').magnitude
    arm_slot_rad = _parse_quantity(config['arm_slot']).to('radian').magnitude
    arm_length_m = _parse_quantity(config['arm_length']).to('m').magnitude if 'arm_length' in config \
                   else _K_ARM * height_m
    arm_ext_m    = _parse_quantity(config['arm_extension']).to('m').magnitude if 'arm_extension' in config \
                   else 0.0

    rubber   = config.get('rubber', ['0 m', '18.44 m'])
    rubber_x = _parse_quantity(rubber[0]).to('m').magnitude
    rubber_y = _parse_quantity(rubber[1]).to('m').magnitude

    # shoulder position: rubber (x, y) + proportional height above mound surface
    shoulder_z     = _K_SH * height_m + _MOUND_HEIGHT_M
    shoulder_world = numpy.array([rubber_x, rubber_y, shoulder_z])
    arm_dir        = arm_direction(arm_slot_rad, handedness, arm_ext_m, arm_length_m)
    release_world  = shoulder_world + arm_length_m * arm_dir
    M              = build_pitch_frame(release_world, arm_dir)

    # velocity aimed at a target in world coordinates
    if 'velocity_target' in config:
      vt = config['velocity_target']
      target_world = numpy.array([_parse_quantity(vt[0]).to('m').magnitude,
                                   _parse_quantity(vt[1]).to('m').magnitude,
                                   _parse_quantity(vt[2]).to('m').magnitude])
    elif 'sz_top' in config and 'sz_bot' in config:
      sz_top_m = _parse_quantity(config['sz_top']).to('m').magnitude
      sz_bot_m = _parse_quantity(config['sz_bot']).to('m').magnitude
      target_world = numpy.array([0.0, 0.0, (sz_top_m + sz_bot_m) / 2])
    else:
      bh_m     = _parse_quantity(config.get('batter_height', '6 ft')).to('m').magnitude
      sz_bot_m = 0.277 * bh_m   # ABS formula: top of kneecap
      sz_top_m = 0.536 * bh_m   # ABS formula: midpoint of shoulders and belt
      target_world = numpy.array([0.0, 0.0, (sz_top_m + sz_bot_m) / 2])

    self.position  = Q_(release_world, 'm')
    self.speed     = _parse_quantity(config['speed'])
    direction      = target_world - release_world
    self.direction = direction / norm(direction)

    # spin axis given in pitch frame; clock_angle rotates it around y_pitch before transforming to world
    self.spin = _parse_quantity(config['spin'])
    spin_ax   = numpy.asarray(config['spin_axis'], dtype=float)
    spin_ax   = spin_ax / norm(spin_ax)
    clock_R   = rot_axis(yhat, _parse_quantity(config.get('clock_angle', '0 degree')))
    self.spin_direction = M @ (clock_R @ spin_ax)
    self.spin_direction = self.spin_direction / norm(self.spin_direction)

  def point_velocity_at(self, r):
    # Aim velocity toward world-frame position r (metres), preserving speed.
    dr = numpy.asarray(r, dtype=float) - self.get_position()
    self.direction = dr / norm(dr)

  def rotate_velocity(self, R):
    # Apply rotation matrix R to velocity direction, preserving speed.
    self.direction = R @ self.direction
    self.direction /= norm(self.direction)

  def rotate_spin(self, R):
    # Apply rotation matrix R to spin axis.
    self.spin_direction = R @ self.spin_direction
    self.spin_direction /= norm(self.spin_direction)

  def get_position(self, unit=ureg.meter):
    v = self.position
    if isinstance(v, Q_):
      return numpy.array([x.to(unit).magnitude for x in v])
    return numpy.asarray(v, dtype=float)

  def get_velocity(self, unit=(ureg.meter/ureg.second)):
    uhat = self.direction / norm(self.direction)
    return float(self.speed.to(unit).magnitude) * uhat

  def get_spin(self, unit=ureg.radian/ureg.second):
    uhat = self.spin_direction / norm(self.spin_direction)
    return float(self.spin.to(unit).magnitude) * uhat
