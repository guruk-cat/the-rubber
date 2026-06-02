# Back-Computing $\vec{V_0}$ at $t=0$ from Statcast Data

## Coordinates

In this document, unless otherwise noted, we use the *world frame*, which follows Statcast conventions for coordinate system:

* Origin at home plate (the back point).
* `+x` points to the right side of the catcher/ump (= left side of the pitcher).
* `+y` towards pitcher (i.e., pitcher throws towards `-y`).
* `+z` points to the sky.

## The Problem

The pitcher's rubber is 60 ft 6 in away from the origin, and 10 inches high. Because of the pitcher's extension (stride + arm lean), the `y` component of the release position typically ranges 53 ~ 55 feet. However, Statcast begins to track the velocity of the ball at `y` = 50 ft, and thus we lose 3 ~ 5 feet of data.

Right now, the configuration simply uses Statcast's 50-feet velocity vector as the initial velocity. This requires an assumption that this is a reasonably approximation. We can use `point_run()` from `Simulation` to test this idea.

## Test

The following test uses a real pitch tracked by Statcast: a changeup (#100 in the game) thrown by Landen Roupp, on 2026-04-26. The pseudo-initial velocity and spin vectors, at the earliest Statcast tracking point, are:

```
init velo: [1.7559473536712067, -38.486628117326106, -0.7941129849602245]
init spin: [-39.890919498709984, 16.411640761495466, -187.47176493878413]
```

These are expressed in SI base units. Given a time step of 0.5 ms, the acceleration vector comes out to be:

```
dv_dt: [-4.607394470849271, 7.851070767055077, -8.749286207450119]
```

The release point of this pitch was tracked to be `(1.69, 54.15, 5.1)` in feet. We're only interested in the `y` component here.