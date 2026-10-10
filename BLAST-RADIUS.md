<!-- ai-generated: ??% - TODO replace ?? with a number and say in one line how this file was written -->
<!-- Stretch 4 only (RELEASE-SPEC.md R-33). The file must then BEGIN with this front matter: move the four lines
between the markers to the very top of the file, delete the markers and this comment, and put the ai-generated line
on the line right after the closing ---.
BEGIN
---
lab6_blast_radius:
  postmortem_action: {bug: TODO, commit: TODO}      # the row's Bug in your Lab 4 baseline's Action Items; the full sha
---
END
-->

# Blast radius

Copy this file to `BLAST-RADIUS.md` at your repository root and replace every `TODO`. It is the reasoning artifact of
Lab 6 (RELEASE-SPEC.md R-28): the checker counts the three sections and their length (L6-CORE-4.04, at least 300
characters each); the lecturer reads what they say. Defend your numbers in plain prose, with the arithmetic next to
each claim; do not restate the rules. RELEASE-SPEC.md section 8 works the same questions through on the checkpoint
SLO - your answers are about your SLO, your `kb-index` profile and your runs. Delete these instructions when you
write the file.

## Gate

TODO: your baseline (student or checkpoint, and why), and each SLI's threshold as a burn rate with the arithmetic:
`max_burn_rate x (1 - objective)`, against the floor your stable build showed in the traffic table (its 5xx share and
its share above your threshold) and against the 30 % every errors or slow candidate reaches. How many canary searches a
step sees at your weights and durations, and how many it needs before a bad share is told from the honest floor - how
often your gate looks, and what each extra look costs you in false rollbacks. What your gate does with no data (an
empty result, NaN, a canary whose searches stop arriving), and why that is the right decision for the hang.

## Blast radius

TODO: each practice run's measured blast radius (in `changes/<run>/run.json`) against what
`failures ~ c + R x w x q x D` predicts for it, with your c, w, q and D, and where the difference comes from.

| run | behaviour | outcome | measured blast radius | c | w | q | D (s) | predicted |
|---|---|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

Which term dominates for each behaviour, what would push a run over the ceiling of 150 (a larger first step, a
longer window, a slower loop), and what the honest run's blast radius says about the floor.

## Change classification

TODO: the change type your records declare, defended - is this release a standard change, and on what grounds - and
the autonomy class of each kind of action your script takes (starting the candidate, reading Prometheus, changing a
weight, promoting, rolling back), with why each sits where it does on the ladder. What would you want a person to
approve, and when, if this were not a course lab?

<!-- Stretch 4 only: add a fourth section, the level-2 heading "Postmortem action", at least 400 characters: the
action item (its Bug, and what the postmortem found), what it asked for, what the commit named in the front matter
changes in deploy.sh, deploy.config.yaml or release/, and how a run of your deploy.sh shows it working - or where it
stops short. -->
