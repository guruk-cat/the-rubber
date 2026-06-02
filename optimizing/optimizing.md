# Better and Quicker Optimization for Constant *K*

## 1. Background

The physics implemented in `Simulator` calculates the net force acting on the baseball as follows:

$$ F_{net} = F_{gravity} + F_{drag} + F_{spin}$$

where the three force terms express gravity, air drag, and Magnus force caused by the spin of the ball. Because mass can be canceled out in each term, we can express the accleration of the ball as follows:

$$ \vec{a} = -g + \alpha |v|^2\hat{v} + \beta \vec{\omega} \times \vec{v} $$

Air drag is proportional to the magnitude of velocity squared, and is in the opposite direction of the velocity. The mangus force is proportional to the cross product of the spin vector (whose direction is defined as the spin axis accoording to the right-hand rule) and the velocity vector.

The two constants in the equation, $\alpha$ and $\beta$, have to be empirically determined. The `optimize.py` code exists for this purpose. In the code, the letter *k* is used to denote an unknown constant. In this document, we will assume that $\beta$ is unknown, and will refer to it as the "Magnus term coefficient" or "constant $K$. 

## 2. Methods

### 2.1. Overview

The optimizer performs a **gradient descent** on a function $f$ of state vector $s$ and constant $k$. Its operation in simple terms is as follows.

We must have a **sample** that includes initial state vector $s_0$ and final state vector $s_1$. In the context of the baseball simulator, these are the vectors that contains the ball's position, velocity, and spin at time $t$. So, we would need a set of datapoints from a ball that is actually thrown and tracked (e.g., Statcast) in order to have the $s_0$ and $s_1$ pairing. Let's say $s_0$ is measured at the release point (ball leaves pitcher's hand) and $s_1$ is measured when it crosses the home plate.

We then perform a simulation with $s_0$ and see what the final outcome is. Let's call this $s_2$, the state vector of the ball when it crosses the home plate in the simulation. So far, then, we have three state vectors:

* $s_0$: the intial state
* $s_1$: the "correct" answer for the final state
* $s_2$: the simulator's answer for the final state, calculated from $s_1$.

If the simulation is accurate, $s_1 - s_2$ should be nearly zero. The goal of the optimizer is to bring this difference as close as possible to zero.

If we make small changes to constant $K$, there would also be small changes to $s_2$. Hence, if we run the same simulation with $K$ and with $dK$, we should be able to compute a grandient of an error function $E$ in respect to $K$, like this:

$$  \frac{dE}{dK}  \approx \frac{E(K) - E(K + \delta)}{\delta} $$

We can then mutliply a "learning rate" to this result, and adjust $K$ by that amount; and repeat until error converges to near-zero.

The `optimizer\optimize.py` script does this. It loads a batch of samples and does the error calculation above (mean squared error used, and then converted to RMS for evaluation). It takes the initial state vector as calculated by the config logic (this remains untouched), runs the simulator, and compares the simulator's `x-z` position when crossing the plate with that recorded by Statcast.

### 2.2 Configs

The yaml files that are used as configuration starting points for each pitch has an optional block `training` for this purpose. It is written either by `statcast_to_config.py --training` or the `command.py` CLI tool when the appropriate option is selected. It stores the ground-truth plate crossing position from Statcast, used by the optimizer as the target output (s₂) for a pitch.

| Key | Type | Description |
|---|---|---|
| `plate_x` | quantity (length) | Horizontal position at home plate. Positive = catcher's right (from catcher's perspective). |
| `plate_z` | quantity (length) | Height above ground at home plate. |

```yaml
training:
  plate_x: "0.531479 ft"
  plate_z: "1.978534 ft"
```

Not read by `launch.py` or `Simulation` — ignored outside the optimizer.

### 2.3 Changes (implemted as of 2026-06-02)

The gradient descent approach remains the same. What changes, however, is the vector that is used as the "correct answer" to compare the simulation against.

The following are some keys in public Statcast data that are dropped by our configuration streams:

* `ax`, `ay`, `az`: instantaneous acceleration (ft/s^2) at the `y` = 50ft tracking start position. This position also happens to be where the "initial" velocity vector is tracked and used, although actual release positions typically have a `y` value that ranges 52-55 ft; an unavoidable but acceptable approximation.
* `pfx_x`, `pfx_z`: integrated horizontal/vertical movement (i.e., Magnus force + air drag; gravity removed).

We can thus acquire a set of $s_0$, $s_1$, and $s_2$ without running the simulator for the entire trajectory of the baseball. The simulator simply needs to calculate the acceleration $\vec{a}$ from a velocity $\vec{v}$ at time $t$, which it already does internally at every time step. The initial velocity vector tracked at `y` = 50 feet in Statcast becomes the velocity in $s_0$, the rest of the state vector being configured accordingly to the Statcast sample; the intial acceleration vector as explained above is the "correct" reference point; and the time derivative of velocity at $s_0$, as computed in the simulator, become the "prediction" that is compared for error calculation.

The `Simulator` class in the `phys` module gains a new `def point_run()` for this purpose. It uses the same precision as `run()`, but returns $dv/dt$ for the state vector that is passed onto it.
