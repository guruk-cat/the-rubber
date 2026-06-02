# About

## Purpose

This is a baseball pitch simulator. The repo contains physics simulations, configuration tools, and plotting tools, with which you can do the follwing:

* Tweak around arm slots, spin rate, etc. to explore differences in pitch trajectories.
* Import data from Statcast to comapre, modify, and play with pitches actually thrown in the MLB.
* Create imaginary pitcher profiles or test "what if" scenarios.

## Authors, History, and Progress

The original physics implementation was written in 2018/2019 by two undergraduate students, **June Jung** and **Richard Whitehill**. The code was then rewritten to provide a cleaner API by **C.D. Clark III**. Sometime in early 2020, we were working on learning-based models to simulate a batter's response to differnt types of pitchers. The repository can be found at [CD3/BaseballSimulator](https://github.com/CD3/BaseballSimulator). 

The present repository is maintained by June Jung. This repository focuses strictly on **accuracy, usability, and interpretability**. For the latest work undertaken, see the following:
* [Optimizing for constant *K*](optimizing/optimizing.md)
* [Back-computing initial velocity from Statcast](studies/init-v/back-computing-v.md)

# Try

## Simple two-way comparison

The below setup will give you a 4-seam fastball and a sinker to compare, thrown by an imaginary pitcher who's 6'2" with a 38-degree arm slot (which is nearly sidearm but still three-quarters). You can see what they mean by "tunneling" that confuses batters.

```bash
python main/launch.py "configs/examples/*" --plot
```

**Expected output** (the GIF had to resample the frame rate, so the animation is slowed down here):

![example-run-gif](docs/imgs/example-run.gif)

## MLB pitchers

While Statcast and Baseball Savant provide precise trackings of pitches and body mechanics, they lack a proper physics engine and therefore the ability to test imagined scenarios. Some examples include:

* Clayton Kershaw and Hyun-Jin Ryu, who played together for the Dodgers, reportedly shared with each other tips on their respective signature pitches: Kershaw's curveball and Ryu's changeup. But apparently, Kershaw's arm angle was simply not compatible with Ryu's changeup grip. If everything else stayed constant, what might it look like if Kershaw threw with Ryu's spin axis?
* Trey Yesavage's extremely high release point really confuses batters. Interestingly, his sliders break towards the *arm side* instead of the glove side. At what point does a slider act weirdly like his?

You can run `main/command.py` to launch a CLI tool that will help you search, select, and configure pitches from the Statcast database. The CLI tool uses `main/statcast-to-config.py` to configure its output. You can run this script directly from the terminal with line arguments. The file has a comment block that explains how to use the script. The above scripts rely on the [pybaseball](https://github.com/jldbc/pybaseball) package to retrieve raw values from the Statcast database. 

## Other Resources

See `docs/config-help.md` for making your own configs.\
See `configs/` for configs that are already prepared.\
See `studies/` for studies made using the simulator & plotter.
