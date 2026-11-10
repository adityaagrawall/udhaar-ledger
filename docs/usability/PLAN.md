# Usability test plan

A small moderated test of Udhaar Ledger with people who do or could do collections work (owner, accounts clerk, sales or field staff of a distributor or wholesaler). Run it on the live demo at https://udhaarledger.vercel.app (use "Explore the live demo"; it is read-only and uses synthetic data). Record results in [FINDINGS.md](FINDINGS.md). No results are included here; this is the kit only.

**Suggested sample:** 5 participants is enough to surface most of the big problems. Include at least one person who uses a screen reader, magnifier or keyboard only, if you can find one.

## Task scenarios

Read each one aloud as a situation. Do not name buttons or pages.

| # | Scenario to read out | Success looks like | Where it happens |
|---|---|---|---|
| 1 | "It's Monday morning and you have time for a few calls. Find out who you should call first today." | Names the first account in the Call today lane (or says which lane it is in) | Today |
| 2 | "You notice one retailer is near the top. Find out why the system ranked it there, and what would move it down." | Opens "Why this lane" or the account page and explains the reason in their own words | Today, account detail |
| 3 | "That retailer has an overdue invoice. Prepare a reminder message to send them in Hindi, check it, and get it ready to approve." | Opens the reminder dialog, switches language, reads the draft, and finds the approval step (the demo is read-only, so they stop at "can't log it") | Invoice queue, reminder dialog |
| 4 | "A retailer tells you one invoice is wrong. Find out which accounts are marked as disputed and what happens to them." | Finds the Resolve lane and states that disputed accounts are not chased | Today |

Optional extra if time allows: "Find out how much is overdue in total and how old most of it is" (Overview).

## Session script (20 minutes)

| Time | Step |
|---|---|
| 0:00 to 0:03 | **Welcome.** Say: "We're testing the software, not you. There are no wrong answers. Please think aloud. I can't help during the tasks, but I'll answer questions at the end." Ask permission to take notes (and to record, if you want to). Fill in participant ID, role and assistive technology used. |
| 0:03 to 0:05 | **Warm-up questions.** How do you decide today whom to call? What tools do you use now (notebook, Tally, Excel, WhatsApp)? |
| 0:05 to 0:06 | **Start.** Open the live demo and ask them to click "Explore the live demo". Say: "You're the person who handles collections at a distributor." |
| 0:06 to 0:18 | **Tasks 1 to 4**, about 3 minutes each. Read the scenario, start the timer when they begin, stop it when they say they're done or after 4 minutes. If they are stuck for over 90 seconds, note it and give the lightest hint possible, and record that you did. |
| 0:18 to 0:20 | **Wrap-up.** What was the clearest part? What was most confusing? Would you trust the ranking enough to act on it? Why or why not? Thank them. |

## What to record per task

For every participant and task:

- **Completed**: yes / no / yes with help (say what help)
- **Time on task**: seconds, from the end of reading the scenario to "I'm done"
- **Errors**: wrong clicks, wrong pages, wrong answers, misread labels (count them and note what)
- **Quotes**: exact words, especially confusion, surprise or distrust
- **Notes**: where they hesitated, what they tried first, anything they said about colours, icons, text size or the mobile layout

Score observed problems with this scale when you fill the findings table:

| Severity | Meaning |
|---|---|
| 4 Blocker | Prevents completing the task |
| 3 Major | Completed, but with real difficulty or a wrong turn |
| 2 Minor | Noticed, slowed them slightly |
| 1 Cosmetic | Mentioned, no effect on the task |

## After the sessions

Group the issues across participants, rank by severity and by how many people hit them, and fix the top few first. Do not report percentages from five people; report counts ("3 of 5 could not find the approval step").
