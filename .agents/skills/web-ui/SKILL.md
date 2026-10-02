---
name: web-ui
description: Implement or review visible web interfaces across React, Go templates, vanilla JavaScript, CSS and presentation configuration. Use for UI-affecting files, honoring the product's design and accessibility patterns.
---

# Web UI that works in context

Read the target `AGENTS.md`, existing components or templates, styles and
interaction tests. The registered projects include React pages, Go HTML
templates, maintained shared JavaScript/CSS and Homepage presentation YAML.
Use the existing design system and asset pipeline; do not assume a bundler is
present because one project's UI uses Next.js.

- Preserve the current visual hierarchy, spacing, typography and responsive
  behavior unless the user asks to change them. Extend existing tokens and
  components when they fit; introduce a new pattern only for a real need.
- Make controls semantic and keyboard operable. Give inputs names and
  associated labels, retain visible focus, and use native HTML before custom
  ARIA. Check contrast and narrow screens for changed states.
- Show loading, empty, success and failure states that match the operation.
  Do not replace a failed save or copy with a success message.
- Render untrusted text as text, not markup. In vanilla JavaScript, prefer
  `textContent` for ordinary status and user-supplied values; in React, use its
  normal text rendering. Treat raw HTML insertion as a separate reviewed need.
- Keep interaction state close to the control. Avoid effects, memoization or
  global state when derived render values or a local event handler suffice.
- Test a changed interaction at the user-visible boundary, including a
  meaningful failure path. Use the target project's supplied validation.

Read [interaction examples](references/interactions.md) when touching status
messages, form controls or client-side state. The
[WAI-ARIA authoring advice](https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/)
favors native semantics; see [MDN `textContent`](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent)
for text insertion and [React's Effect guide](https://react.dev/learn/you-might-not-need-an-effect)
for derived render state.
