import types
import numbers
import pint
import numpy
from numpy.linalg import norm as Norm


# module configuration
ureg = pint.UnitRegistry()
ureg.define('percent = 0.01 rad')
Q_ = ureg.Quantity
pint.set_application_registry(ureg)

xhat = numpy.array([1, 0, 0], dtype=float)
yhat = numpy.array([0, 1, 0], dtype=float)
zhat = numpy.array([0, 0, 1], dtype=float)

def num(quant):
  return quant.to_base_units().magnitude


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
    # state vector layout:
    # [0]    t
    # [1:4]  x, y, z     (m)
    # [4:7]  vx, vy, vz  (m/s)
    # [7:10] wx, wy, wz  (rad/s)
    return 10

  def derivative(self, state):
    dsdt = numpy.zeros(self.state_size)

    dsdt[0]   = 1           # dt/dt = 1
    dsdt[1:4] = state[4:7]  # dx/dt = v
    # dw/dt = 0 (spin treated as constant for now)

    # dv/dt = (Fg + Fd + Fm) / m
    dsdt[4:7] -= num(self.config.gravitational_acceleration) * zhat  # gravity
    speed = Norm(state[4:7])
    dsdt[4:7] -= num(self.config.drag_coefficient) * speed * state[4:7] / num(self.config.ball_mass)  # drag
    if self.config.magnus_model == 'squared velocity':
      dsdt[4:7] += num(self.config.magnus_coefficient) * speed * numpy.cross(state[7:10], state[4:7]) / num(self.config.ball_mass)
    elif self.config.magnus_model == 'linear velocity':
      dsdt[4:7] += num(self.config.magnus_coefficient) * numpy.cross(state[7:10], state[4:7]) / num(self.config.ball_mass)
    else:
      raise Exception(f"Unrecognized magnus model '{self.config.magnus_model}'")

    return dsdt

  def rk4(self, time_step, state):
    k1 = time_step * self.derivative(state)
    k2 = time_step * self.derivative(state + k1 / 2)
    k3 = time_step * self.derivative(state + k2 / 2)
    k4 = time_step * self.derivative(state + k3)
    return state + (k1 + 2*k2 + 2*k3 + k4) / 6

  def _compute_error(self, s0, s1, s2):
    return Norm(s2 - s1) / Norm(s2 - s0)

  def run(self, launch_config, terminate_function=lambda record: len(record) > 1000, record_all=True):
    '''
    Run simulation and return trajectory as a list of state arrays.

    Each state array has 10 elements (all SI units):
      state[0]    time (s)
      state[1:4]  position (m)
      state[4:7]  velocity (m/s)
      state[7:10] angular velocity (rad/s)
    '''
    state = numpy.zeros(self.state_size)
    state[1:4]  = launch_config.get_position_tensor()
    state[4:7]  = launch_config.get_velocity_tensor()
    state[7:10] = launch_config.get_spin_tensor()

    record = [state.copy()]
    dt = self.config.time_step.to('s').magnitude
    while not terminate_function(record):
      while True:
        s1  = self.rk4(dt,   state)
        s2  = self.rk4(dt/2, self.rk4(dt/2, state))
        err = self._compute_error(state, s1, s2)
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
    self.position         = Q_(0, 'm') * xhat
    self.velocity         = Q_(0, 'm/s') * (-yhat)
    self.angular_velocity = Q_(0, 'rad/s') * xhat

  def configure(self, config):
    def load_tensor(v):
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

    config_keys_used = []
    for k in ['position', 'velocity', 'angular_velocity']:
      if k in config:
        setattr(self, k, load_tensor(config[k]))
        config_keys_used.append(k)

    if len(config_keys_used) != len(config.keys()):
      print("Warning: there were unused keys when configuring LaunchConfiguration:")
      for k in list(set(config.keys()) - set(config_keys_used)):
        print("  ", k)
      print("Make sure you didn't mispell something.")

  def get_position_tensor(self, unit=ureg.meter):
    v = self.position
    if isinstance(v, Q_):
      return numpy.array([x.to(unit).magnitude for x in v])
    return numpy.asarray(v, dtype=float)

  def get_velocity_tensor(self, unit=(ureg.meter/ureg.second)):
    v = self.velocity
    if isinstance(v, Q_):
      return numpy.array([x.to(unit).magnitude for x in v])
    return numpy.asarray(v, dtype=float)

  def get_spin_tensor(self, unit=ureg.radian/ureg.second):
    w = self.angular_velocity
    if isinstance(w, Q_):
      return numpy.array([x.to(unit).magnitude for x in w])
    return numpy.asarray(w, dtype=float)
