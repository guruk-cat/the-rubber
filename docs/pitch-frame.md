# Pitch Frame

## About

A pitch frame is a coordinate system that is used to configure the initial state vector of the baseball from intuitive data points, which include: arm slot, pitcher height, release speed (scalar), etc. The pitch frame is not used for the simulation nor plotting.

## World frame

The world frame (or world coordinates) rely on Statcast conventions:

* Origin at home plate.
* `+x` points to the right side of the catcher/ump (= left side of the pitcher).
* `+y` towards pitcher (i.e., pitcher thros towards `-y`).
* `+z` points to the sky.

## Pitch frame

The pitch frame (or pitch coordinates) roughly follow the world frame, but the axes are aligned differently. It is primarily defined by, and for the purpose of working with, the position offset caused by the pitcher's arm and knee bends. Details are as follows:

* Origin remains at home plate
* `y` axis is defined by the line from origin to the pitcher's release point. Directionality remains roughly the same, `+y` pointing from home plate towards the pitcher.
* `x` axis is perpendicular to the *arm slot*. In other words, if a two-dimensinal plane was defined the `y` axis as described above and the pitcher's arm, the `x` axis would be perpendicular to this plane. Alternatively, the `x` axis can be understood as the pure back-spin axis (or pure top-spin axis) when given a certain arm slot.
* `z` axis is perpendicular to the `xy` plane. Assuming the pitcher does not throw underhand, the `+z` direction still points *roughly* to the sky.

All of this means, importantly, that matrix transformation of vectors from the pitch frame to the world frame, and vice versa, can be understood solely in terms of *rotation about the origin*.

## Release point

An important factor in defining the pitch frame is the release point. Statcast tracks the precise release point in their coordinate system which is functionally identical to the world frame described above. This is the most reliable datapoint to use for the purpose.

**However,** the purpose of the pitch frame, and by extension the purpose of the simulator, is to allow easily human-readable modifications of initial conditions, such that we can go beyond simply tracking real pitches and instead ask: "what would happen if *X* were to change?" Thus, while the release point can be specified directly (say, from Statcast), the configuration still has the capacity to do the following:

* Reverse-calculate the "shoulder" position from release point, estimated arm length, pitcher height, arm slot, etc.
* Re-calculate an alternative release point when given, say, deviations in the arm slot or the arm length.
* Or simply calculate a release point from imagined values.

All of this can be done via arguments in the configuration setup.

## Matrix transformation order

If a simulation is configured using the intutitve data points such as arm slot (as opposed to raw vector values for the initial state), the order of transformations is as follows:

1. Pitch frame is defined.
2. Initial state vector is configured within the pitch frame.
3. Initial state vector is translated into the world frame.
4. Simulation and plotting runs in the world frame.
