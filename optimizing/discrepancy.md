# Discrepancy Between Optimizer and Closed Solution

## Background

The optimizer finds the value for constant $K$ in the dynamics equation that minimizes the mean squared error. Because *K* enters the dynamics equation linearly, the squared error function $E(K)$ is a parabola with one global minimum. We thus solve solve for $K$ at this minimum point, setting $dE/dK = 0$. We expect that the $K$ values from the optimizer and the analytic solution will be very similar, if not practically identical leaving aside floating errors.

For more information, see the following two documentations: 
- [Better and Quicker Optimization for Constant K](optimizing.md)
- [Closed-Form Solution for Constant K](solving.md)

## Setup and Results

We assume a "linear velocity" Magnus model for its documented consistency with empirical findings specific to baseballs. The optimizer was run with the following configuration:

- initial $K$ = $1.0 \times 10^{-3} $ (kg * s / m)
- $\Delta K  = 0.0001 \cdot K$
- internally calibrated learning rate $l$ at the first epoch
- each epoch iterates over 10 batches, each batch containing roughly 100 pitches from the same pitcher on the same day.

The optimizer declared convergence at `epoch = 18/50` as follows:

```
Error is not getting any smaller... declaring convergence
Final K                             = 6.735553241834e-05 (kg*s/m)
Final RMS error across all bacthes  = 2.352487969422 (m/s²)
Est. ceiling of displacement error  = 7.4 ~ 9.4 (inches)
```

The solution script was also run over the same data. However, it yielded very different results:

```
Final K                             = 4.640061747337e-04 (kg*s/m)
Final RMS error across all bacthes  = 4.920826139955 m/s²
Est. ceiling of displacement error  = 15.5 ~ 19.6 (inch)
```

The $K$ value is an order of magnitude larger here than from the optimizer, and the error is also roughly twice as large. Judging by the error alone, intuition tells me that the optimizer is closer to the correct value. 

## Tentative Conclusion (or a Hypothesis, I suppose)

Solution is wrong, or implementaion of the solution is wrong.
