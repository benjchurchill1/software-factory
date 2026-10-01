# What a missing environment check cost

Measured on the Keystone build (a staff web and mobile app: Next.js, a hosted
Supabase Postgres in London, Netlify hosting, built from a cloud session on
2026-09-30 and 2026-10-01). Each snag below was found mid-build, after waves
had already been spent, and each is now a line of the check. Quote them when
someone wants to start the build first and sort the environment out later.

## The hosted database could not be migrated

The build wrote 26 migrations. When the owner asked for them to be loaded into
the hosted database and kept current on every deploy, only 3 applied. The cloud
environment had no Supabase access token and no database password, so the
Supabase CLI could not push. The fallback, applying them through the Supabase
connector, was refused by the session's safety checks for every migration that
drops or replaces a function, even with the owner's yes in the transcript. With
the schema incomplete, nobody could sign in to the hosted site.

The fix needed the owner at a computer: a token added to the cloud
environment, and a fresh session to see it. In the meantime the owner had to run
`supabase db push` locally by hand.

**The check now:** the database token is a required secret; a probe reads the
hosted migration history with it; a second probe dry-runs the push; and the
deploy script must contain the apply command, so migrations travel with every
deploy rather than being an afterthought. The skill's rule is that migrations
go through the CLI from a script, never through a connector.

## Nobody could sign in, by design

Claude does not invent passwords for real people. The owner's admin login, and
any other real login, had to be created by the owner by hand, and that was
discovered only when the site was first opened.

**The check now:** the `logins` section names every account, how it comes to
exist (seeded with no password, invited, or created by the owner), and stays red
until the owner has confirmed the ones that are theirs to do.

## A token stored under the wrong name

The Netlify token was saved on the cloud environment as `NETLIFY_AUT_TOKEN`. The
deploy script was changed to accept either spelling rather than the name being
fixed.

**The check now:** a missing secret is compared against every variable that is
set, and a near match is reported as a probable misspelling with the rename to
make, not as "missing".

## Settings that a running session never sees

Environment variables and network access belong to the cloud environment
(claude.ai/code, the environment's settings), not to the project's settings,
which only choose the environment. A session that is already running does not
pick up a change. Each fix to the environment therefore cost a new session, and
the build seat could not be restarted mid-wave without a handover.

**The check now:** it runs from a fresh session on the same environment the
build will use, and every fix it asks for says where the setting lives and that
a fresh session is needed. It runs again as the loop's first step, so a seat
started on the wrong environment stops before wave 0.

## Too many agents for the machine

The build machine had 4 cores. Three lanes, each with three review lenses in
parallel, drove the load to 65 and the build seat's worker was lost three times
(twice around 11:00 and again at 17:49 on 2026-10-01). Two lanes at a time, with
review lenses run one after another, held.

**The check now:** it measures cores and memory, works out how many lanes can
run at once (two cores and 3 GB each by default) and whether review lenses must
run one after another, and fails if the planned wave shape is wider than that.

## Approvals the build seat would not take

The owner raised the budget, turned on deploy-on-green and asked for migrations
on deploy from other threads and by tapping cards. The build seat refused each
one, correctly: an instruction relayed by another session is not the owner's
word. Each had to be typed again in the build seat's own thread.

**The check now:** the standing decisions (budget, time limit, push after
green, deploy branch, deploy on green, migrations on deploy, what data the
hosted site may hold) are recorded in the repo before the build starts, in the
owner's words with the date. The loop reads them from there.
