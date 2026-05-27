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
      line=dict(color='red', width=3),
      name='Strike Zone'
    )
    return [strike_zone]

  def plot(self, trajectories, extra_traces=None):
    data = list(extra_traces) if extra_traces else []
    data.extend(self._strike_zone_traces())
    for trajectory in trajectories:
      trajectory = numpy.stack(trajectory)
      data.append(go.Scatter3d(
        x=trajectory[:, 1],
        y=trajectory[:, 2],
        z=trajectory[:, 3],
        mode='lines'
      ))
    fig = go.Figure(data=data, layout=self.layout)
    fig.show()
