# Accessibility changelog (branch `a11y/wcag-pass`)

Measured before and after with axe-core and Lighthouse; see [SUMMARY.md](SUMMARY.md) and the raw JSON in `before/` and `after/`. Backend and the scoring model were not touched.

| Fix | WCAG criterion | Files |
|---|---|---|
| Skip-to-content link; `<main id="main-content">` target | 2.4.1 Bypass Blocks | `app/layout.tsx`, `app/globals.css` |
| One labelled `Main` nav landmark with real lists; labelled sidebar | 1.3.1, 2.4.1 | `components/Sidebar.tsx` |
| Per-page document titles | 2.4.2 Page Titled | `components/Navbar.tsx` |
| Breadcrumbs as an ordered list with `aria-current` | 1.3.1 | `components/Navbar.tsx` |
| Lane titles and section titles are real headings; hero line on login is no longer a heading before the page `h1` | 1.3.1, 2.4.6 | `app/today/page.tsx`, `components/ui.tsx`, `components/AuthShell.tsx` |
| Shared accessible dialog: named, focus moves in, Tab trapped, Esc closes, focus returns, page behind inert and not scrollable | 2.1.1, 2.1.2, 2.4.3, 4.1.2 | `components/Modal.tsx`, `components/useDialogBehavior.ts`, all four modal components |
| Mobile menu drawer uses the same dialog behaviour; trigger has `aria-expanded` and `aria-controls` | 2.1.2, 2.4.3, 4.1.2 | `components/Sidebar.tsx` |
| Visible focus outline forced on all controls (also over `focus:outline-none`); saffron outline on dark surfaces | 2.4.7 | `app/globals.css` |
| Scroll padding so sticky headers do not cover focused elements | 2.4.3 | `app/globals.css` |
| Contrast-safe palette: `slate-400/500`, `rose-600`, `emerald-600`, `accent-600/700` darkened; logo "Ledger" uses a darker tone on light backgrounds; white-on-emerald buttons darkened | 1.4.3 | `tailwind.config.ts`, `components/Logo.tsx`, `components/ReminderModal.tsx` |
| Labels on the phone field and message draft; Channel and Language are labelled groups with `aria-pressed` | 1.3.1, 3.3.2, 4.1.2 | `components/ReminderModal.tsx` |
| `lang="hi"` on Hindi text and the Hindi draft | 3.1.2 | `components/ReminderModal.tsx` |
| Segmented control uses buttons with `aria-pressed` instead of an unfinished radio pattern | 4.1.2 | `components/ui.tsx` |
| Status messages announced through live regions (list loaded, invoice count, draft copied, loading, success, error) | 4.1.3 Status Messages | `components/Providers.tsx`, `app/today/page.tsx`, `app/queue/page.tsx`, `components/ReminderModal.tsx` |
| Icon buttons and links have accessible names; repeated "Why this lane", "Remind", "Log" buttons name their customer and invoice; decorative icons hidden | 1.1.1, 2.4.4, 4.1.2 | `app/today/page.tsx`, `app/queue/page.tsx`, `components/Sidebar.tsx`, `components/ReminderModal.tsx` |
| Logo link name matches its visible text; mark is decorative inside the wordmark | 2.5.3 Label in Name | `components/Logo.tsx`, `components/Sidebar.tsx` |
| Score and risk are not colour-only: priority tier is also given as text; each account row names its lane | 1.4.1 Use of Color | `app/queue/page.tsx`, `app/today/page.tsx` |
| Queue table has a caption, `scope="col"` headers and a keyboard-focusable scroll region | 1.3.1, 2.1.1 | `app/queue/page.tsx`, all pages with tables |
| Count-up numbers skip the animation under reduced motion; CSS animations and transitions shortened under `prefers-reduced-motion` (Framer Motion already honoured it through `MotionConfig`) | 2.3.3 | `components/ui.tsx`, `app/globals.css` |
| At 767px and below every button, select and text input is at least 44px tall; icon buttons at least 44px wide; nav links, close buttons and stepper buttons enlarged | 2.5.5 | `app/globals.css`, `components/Sidebar.tsx`, `app/today/page.tsx`, `components/ReminderModal.tsx` |
| Screen-reader-only text could cause sideways scrolling inside the queue table; the scroll region is now a positioning context | 1.4.10 Reflow | `app/queue/page.tsx` |

## Tooling added

- `frontend/a11y/audit.mjs` and `summarize.mjs`: the audit harness (`npm run a11y:audit`, `npm run a11y:summary`).
- `frontend/e2e/a11y.spec.ts` and `playwright.config.ts`: a Playwright + axe test that fails on any serious or critical violation (`npm run test:a11y`).

## Not fixed, and why

- **The axe test is not in CI yet.** CI builds with a placeholder Clerk key, which Clerk rejects, so the login page renders blank. It needs a real Clerk publishable key as a CI secret (or a mocked Clerk). Until then run `npm run test:a11y` locally against a running build.
- **Signed-in pages are tested with the read-only demo user only.** The edit dialogs (record payment, log follow-up, invoice detail) were converted to the shared dialog and had their markup reviewed, but were not scanned by axe because the demo user cannot open them. Their form labels in particular need a scan with an editor account.
- **Charts** (Overview, Analytics) have no text alternative or data table; Analytics, Invoices, Customers and Import pages were not audited.
- **Some targets remain under 44px at 375px:** inline text links inside sentences (exempt under WCAG 2.2), the three customer links and one link on Overview, and links inside Clerk's own sign-in widget.
- **Contrast of Clerk's embedded widget and of text over images or gradients** is not fully covered by automated checks.
- **Automated tools find only part of WCAG.** Still needed: a screen-reader pass (VoiceOver, NVDA), a keyboard-only walkthrough, 200% and 400% browser zoom, Windows high-contrast mode, and the usability sessions in `docs/usability/PLAN.md`.
