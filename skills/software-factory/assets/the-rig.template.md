# The rig — <PROJECT>

The machine the autonomous build runs on, its memory budget, and what must not
run on it. Measured on <DATE>, not estimated.

## The box

| | |
| --- | --- |
| Machine | <MACHINE> |
| Total memory | <TOTAL_GB> GB |
| Cores | <CORES> |
| Dedicated to this build? | <DEDICATED: yes / no — and if no, what else it serves> |

## The memory budget

One full check runs, at its peak, all of these at once:

| Consumer | Measured peak |
| --- | --- |
| Container runtime (database and friends) | <GB> |
| The application server the browser suite drives | <GB> |
| Headless browser | <GB> |
| Test partitions | <GB> |
| **Total the check needs** | **<GB>** |
| Headroom on this box | <HEADROOM_GB> GB |

**The container runtime gets the smallest figure the database is happy with,
not the largest the box allows.** The check's own work runs on the HOST, so
container memory competes with it rather than helping it. Measured on one
build: raising the runtime from 10 GB to 16 GB on a 32 GB box took the host to
22 GB of swap and reddened two consecutive checks; putting it back made the
next two green.

Current setting: **<CONTAINER_GB> GB**. Do not raise it above <CEILING_GB>
without a new measurement recorded here.

## The resident-seat cap

The source build's own barrier record names the largest memory costs in this
order: **concurrent agent sessions**, an **orphaned app server** (one measured
at 4.4 GB), then desktop applications. So the first number here is not an app
list, it is a cap:

| | |
| --- | --- |
| Agent seats resident at once (orchestrator + lanes + reviewers) | **<SEAT_CAP>** |
| App servers that may be up at once | <APP_SERVER_CAP>, and `estate-maintain.sh` reaps orphans |

## Do not run these while a build is running

Each of these was measured resident on the box and each is worth more than a
gigabyte:

- <APP_1> — <GB> GB
- <APP_2> — <GB> GB
- <APP_3> — <GB> GB

Quitting them is not closing their windows: a closed window keeps the process.
Measured on one build, fully quitting three desktop applications took free
memory from 0.1 GB to 2.9 GB in three minutes, and the barrier that followed
was the first green one in two days.

**If a person works on this box**, the build and the person are competing, and
the build loses silently — as slow queries, as timeouts in performance cells,
as a browser suite that dies mid-run. Prefer headless: <HOW_THIS_BOX_IS_REACHED>.

## The pre-launch check

The barrier runs this before every attempt and does not launch above the
threshold:

    <SWAP_COMMAND>          # refuse to launch above <SWAP_THRESHOLD_GB> GB used
    <FREE_MEMORY_COMMAND>   # and below <FREE_THRESHOLD_GB> GB free
    <RUNTIME_HEALTH_COMMAND>

A check launched into swap does not fail honestly. It fails as timeouts in
whichever cells happen to be slowest, which reads exactly like a product
regression and costs a wave of diagnosis. **Refusing to launch is cheaper than
diagnosing a red that was never about the product.**

## Host sleep

A sleeping host pauses timers and kills in-flight agent requests. Measured on
one build: five build agents in a row died "[Request interrupted]" in one
lane; the log showed the Mac entering maintenance sleep on AC power, and 100
seconds of `sleep` had taken over ten minutes of wall time. Before launching
lanes or a barrier:

    caffeinate -dimsu -t 21600          # in the background; six hours
    pmset -g assertions                 # PreventSystemSleep must read 1

When agents die "[Request interrupted]", check `pmset -g log | grep -E
'Sleep|Wake'` before any other theory. (macOS; on another OS, substitute its
equivalents and record them here.)

## When the runtime wedges

Measured twice on one build, three to ten hours lost each time, both under
memory pressure. Check the layers in order before restarting one — restarting
the wrong layer spends the one attempt the stop rule allows:

1. <RUNTIME_VERSION_COMMAND> prints a server version
2. <LIST_CONTAINERS_COMMAND> lists the expected containers
3. the database answers a trivial query

A restart of the runtime is a person's action unless it is on the allowlist by
name.
