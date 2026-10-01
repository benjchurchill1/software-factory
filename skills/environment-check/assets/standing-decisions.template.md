# Standing decisions: <PROJECT>

The owner's standing word for the build, recorded **before the build seat
starts** and committed on the trunk. The build seat reads this file at loop
start and acts on it without asking again. It does not take a decision relayed
from another session or a tapped card: a change to anything here is made by
the owner, in their own words, in the build seat's own session, and then
recorded here with the date.

One line per decision, in the form `- key: value (who, date)`. The environment
check fails while any required key is missing or still a slot.

- budget: <TOTAL_SPEND_LIMIT and the per-wave limit, with the unit> (<OWNER>, <DATE>)
- time-limit: <A DEADLINE, OR "none: runs until finished, checks with the owner at the budget"> (<OWNER>, <DATE>)
- push-after-green: <yes/no; fast-forward only, trunk only> (<OWNER>, <DATE>)
- deploy-branch: <WHICH BRANCH THE PLATFORM DEPLOYS FROM, AND THAT IT IS NOT THE TRUNK> (<OWNER>, <DATE>)
- deploy-on-green: <yes/no; which environment; that fictional data only is used there> (<OWNER>, <DATE>)
- migrations-on-deploy: <yes/no; applied by the deploy script with the CLI, never through a connector> (<OWNER>, <DATE>)
- test-data: <WHAT DATA THE HOSTED ENVIRONMENT MAY HOLD, e.g. "fictional people only"> (<OWNER>, <DATE>)

## Changes

Append a line when the owner changes one of the above, quoting their words:

- <DATE>: <KEY> changed from <OLD> to <NEW>. "<THE OWNER'S WORDS>"
