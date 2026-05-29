import plotly.graph_objs as go
import numpy
import yaml

# World variables in meters
_STRIKE_ZONE_HALF_WIDTH = 0.2159  # half of 17 inches
_STRIKE_ZONE_BOTTOM     = 0.4572  # 1.5 ft
_STRIKE_ZONE_TOP        = 1.0668  # 3.5 ft
_BASEBALL_RADIUS        = 0.03683 # 2.9 inch diameter


class Trajectory3DPlot:
  def __init__(self):
    plot_layout_yaml = '''
scene:
  xaxis:
    title: x
    range: [-1.5, 1.5]
  yaxis:
    title: y
    range: [0, 20]
  zaxis:
    title: z
    range: [0, 3]
  camera:
    up:
      x: 0
      y: 0
      z: 1
    center:
      x: 0
      y: 0
      z: 0
    eye:
      x: 0
      y: -2
      z: 0
  aspectratio:
    x: 0.5
    y: 3.5
    z: 0.5
  aspectmode: manual
'''
    self.layout = yaml.safe_load(plot_layout_yaml)

  def _strike_zone_traces(self):
    w = _STRIKE_ZONE_HALF_WIDTH
    b = _STRIKE_ZONE_BOTTOM
    t = _STRIKE_ZONE_TOP
    outline = go.Scatter3d(
      x=[-w, -w,  w,  w, -w],
      y=[ 0,  0,  0,  0,  0],
      z=[ b,  t,  t,  b,  b],
      mode='lines',
      line=dict(color='blue', width=3),
      showlegend=False, hoverinfo='skip',
    )
    fill = go.Mesh3d(
      x=[-w, -w,  w,  w],
      y=[ 0,  0,  0,  0],
      z=[ b,  t,  t,  b],
      i=[0, 0], j=[1, 2], k=[2, 3],
      color='blue', opacity=0.1,
      showlegend=False, hoverinfo='skip',
    )
    return [outline, fill]

  def _crossing_trace(self, traj):
    y = traj[:, 2]
    above = numpy.where(y >= 0)[0]
    if not len(above) or above[-1] + 1 >= len(traj):
      return None
    i = above[-1]
    alpha = y[i] / (y[i] - y[i + 1])
    x = traj[i, 1] + alpha * (traj[i + 1, 1] - traj[i, 1])
    z = traj[i, 3] + alpha * (traj[i + 1, 3] - traj[i, 3])
    theta = numpy.linspace(0, 2 * numpy.pi, 64)
    return go.Scatter3d(
      x=x + _BASEBALL_RADIUS * numpy.cos(theta),
      y=numpy.zeros(64),
      z=z + _BASEBALL_RADIUS * numpy.sin(theta),
      mode='lines',
      line=dict(color='red', width=3),
      showlegend=False, hoverinfo='skip',
    )

  def _line_trace(self, traj, t_range=None):
    t_min, t_max = t_range if t_range else (traj[0, 0], traj[-1, 0])
    return go.Scatter3d(
      x=traj[:, 1], y=traj[:, 2], z=traj[:, 3],
      mode='lines',
      line=dict(width=2, color=traj[:, 0], colorscale='Plasma', cmin=t_min, cmax=t_max),
      showlegend=False,
    )

  def _ball_trace(self, pos):
    x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
    r = _BASEBALL_RADIUS
    theta = numpy.linspace(0, 2 * numpy.pi, 64)
    nan = [numpy.nan]
    # Three orthogonal great circles give a sphere wireframe in world space
    return go.Scatter3d(
      x=numpy.concatenate([x + r*numpy.cos(theta), nan, x + r*numpy.cos(theta), nan, numpy.full(64, x)]),
      y=numpy.concatenate([y + r*numpy.sin(theta), nan, numpy.full(64, y),       nan, y + r*numpy.cos(theta)]),
      z=numpy.concatenate([numpy.full(64, z),       nan, z + r*numpy.sin(theta), nan, z + r*numpy.sin(theta)]),
      mode='lines',
      line=dict(color='red', width=2),
      showlegend=False, hoverinfo='skip',
    )

  def _resample(self, traj, frame_dt_s):
    t = traj[:, 0]
    t_uniform = numpy.arange(t[0], t[-1], frame_dt_s)
    return numpy.column_stack([
      t_uniform,
      numpy.interp(t_uniform, t, traj[:, 1]),
      numpy.interp(t_uniform, t, traj[:, 2]),
      numpy.interp(t_uniform, t, traj[:, 3]),
    ])

  def plot(self, trajectories, extra_traces=None, animate=False, fps=30):
    arrays = [numpy.stack(t) for t in trajectories]
    t_ranges = [(a[0, 0], a[-1, 0]) for a in arrays]

    static_traces = list(extra_traces) if extra_traces else []
    static_traces.extend(self._strike_zone_traces())
    static_traces.extend(t for a in arrays for t in [self._crossing_trace(a)] if t is not None)

    # Full-resolution line is always static — never resampled
    line_traces = [self._line_trace(a, t_range=r) for a, r in zip(arrays, t_ranges)]

    if not animate:
      final_balls = [self._ball_trace(a[-1, 1:4]) for a in arrays]
      go.Figure(data=static_traces + line_traces + final_balls, layout=self.layout).show()
      return

    # Used in animated mode only; the ball marker is in frames; lines stay static
    n_static = len(static_traces) + len(line_traces)
    initial_balls = [self._ball_trace(a[-1, 1:4]) for a in arrays]

    frame_dt_s  = 1 / fps
    frame_dt_ms = frame_dt_s * 1000
    anim_arrays = [self._resample(a, frame_dt_s) for a in arrays]
    anim_max_len = max(len(a) for a in anim_arrays)

    frames = []
    for i in range(anim_max_len):
      frame_data = [self._ball_trace(a[min(i, len(a) - 1), 1:4]) for a in anim_arrays]
      t = anim_arrays[0][min(i, len(anim_arrays[0]) - 1), 0]
      frames.append(go.Frame(
        data=frame_data,
        traces=list(range(n_static, n_static + len(arrays))),
        name=f'{t:.3f}',
      ))

    slider_steps = [dict(
      args=[[f.name], dict(frame=dict(duration=0, redraw=True), mode='immediate', transition=dict(duration=0))],
      label=f.name,
      method='animate',
    ) for f in frames]

    layout = {
      **self.layout,
      'updatemenus': [dict(
        type='buttons',
        showactive=False,
        y=0.05,
        x=0.5,
        xanchor='center',
        buttons=[
          dict(label='Play', method='animate',
               args=[None, dict(frame=dict(duration=frame_dt_ms, redraw=True), fromcurrent=False, transition=dict(duration=0))]),
          dict(label='Pause', method='animate',
               args=[[None], dict(frame=dict(duration=0, redraw=False), mode='immediate', transition=dict(duration=0))]),
        ],
      )],
      'sliders': [dict(
        active=anim_max_len - 1,
        steps=slider_steps,
        x=0, y=0,
        currentvalue=dict(prefix='t = ', suffix=' s', visible=True),
        len=1.0,
      )],
    }

    go.Figure(
      data=static_traces + line_traces + initial_balls,
      layout=layout,
      frames=frames,
    ).show()
