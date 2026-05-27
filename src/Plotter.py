import plotly.graph_objs as go
import numpy
import yaml

# Standard strike zone dimensions
_STRIKE_ZONE_HALF_WIDTH = 0.2159  # half of 17 inches
_STRIKE_ZONE_BOTTOM     = 0.4572  # 1.5 ft
_STRIKE_ZONE_TOP        = 1.0668  # 3.5 ft


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
    strike_zone = go.Scatter3d(
      x=[-w, -w,  w,  w, -w],
      y=[ 0,  0,  0,  0,  0],
      z=[ b,  t,  t,  b,  b],
      mode='lines',
      line=dict(color='blue', width=3),
      name='Strike Zone'
    )
    return [strike_zone]

  def _trajectory_trace(self, traj, end_idx):
    pts = traj[:end_idx + 1]
    sizes = [3] * len(pts)
    sizes[-1] = 8  # large marker at current position for the "ball"
    return go.Scatter3d(
      x=pts[:, 1],
      y=pts[:, 2],
      z=pts[:, 3],
      mode='lines+markers',
      marker=dict(size=sizes),
      line=dict(width=2),
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

  def plot(self, trajectories, extra_traces=None, animate=False):
    arrays = [numpy.stack(t) for t in trajectories]

    static_traces = list(extra_traces) if extra_traces else []
    static_traces.extend(self._strike_zone_traces())

    if not animate:
      data = static_traces + [self._trajectory_trace(a, len(a) - 1) for a in arrays]
      go.Figure(data=data, layout=self.layout).show()
      return

    n_static = len(static_traces)
    initial_traces = [self._trajectory_trace(a, len(a) - 1) for a in arrays]

    frame_dt_s  = 1 / 30
    frame_dt_ms = frame_dt_s * 1000
    anim_arrays = [self._resample(a, frame_dt_s) for a in arrays]
    anim_max_len = max(len(a) for a in anim_arrays)

    frames = []
    for i in range(anim_max_len):
      frame_data = [self._trajectory_trace(a, min(i, len(a) - 1)) for a in anim_arrays]
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
      data=static_traces + initial_traces,
      layout=layout,
      frames=frames,
    ).show()
