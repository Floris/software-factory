---
name: web-ui
description: Implement or review visible web interfaces across React, Go templates, vanilla JavaScript, CSS and presentation configuration. Use for UI-affecting files, honoring the product's design and accessibility patterns.
---

# Web UI best practices

## Contents

- [Visual and component design](#visual-and-component-design)
- [Semantic HTML and accessibility](#semantic-html-and-accessibility)
- [Forms and feedback](#forms-and-feedback)
- [State and interaction](#state-and-interaction)
- [Responsive layout and styling](#responsive-layout-and-styling)
- [Rendering and security](#rendering-and-security)
- [Testing](#testing)
- [Performance](#performance)
- [Anti-slop review](#anti-slop-review)
- [Tooling and verification](#tooling-and-verification)

Read the target `AGENTS.md`, existing components or templates, styles and
interaction tests. The registered projects include React pages, Go HTML
templates, maintained shared JavaScript/CSS and Homepage presentation YAML.
Use the existing design system and asset pipeline; do not assume a bundler is
present because one project's UI uses Next.js.
Read [interaction examples](references/interactions.md) for status messages,
forms and client-side state.

## Visual and component design

- Begin with the product's existing visual hierarchy, type scale, spacing,
  color tokens and components. A new field should look and behave like
  adjacent fields. Introduce a new visual pattern only when it solves a
  specific user need.
- Keep related content together and make the primary action recognizable.
  Use meaningful headings and labels rather than decorative sections.
  A component should own a distinct piece of behavior or presentation,
  not be extracted solely for a shorter file.
- Registered interfaces span Next.js/React, Go templates, maintained
  vanilla JS/CSS and Homepage YAML. Do not assume a bundler or React
  runtime in a Go or Homepage repository. In `droppert-platform`, files
  under `packages/ui/dist` are maintained source by local convention.

## Semantic HTML and accessibility

- Start with a native `button`, `a`, `label`, `input` or `select` that
  matches the action. A clickable `div` needs keyboard, focus and role
  work that native controls already supply.
- Give each form input an accessible name and a visible label where
  appropriate. Link help and errors to the input. Preserve a visible
  focus indicator and logical tab order; test keyboard operation.
- Use headings in document order and meaningful link text. Add ARIA
  only to express behavior native HTML cannot provide. The
  [WAI-ARIA authoring advice](https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/)
  explains why native controls are the starting point.

```html
<label for="project-name">Project name</label>
<input id="project-name" name="projectName" required
       aria-describedby="project-name-help">
<p id="project-name-help">Use a name your team will recognize.</p>
```

Add error text and `aria-invalid` when validation actually fails; do not
leave every field marked invalid by default.

## Forms and feedback

- Model loading, empty, success and failure as distinct user outcomes.
  Announce a successful operation only after it succeeds. Keep user input
  available when a save fails so the user can retry or correct it.
- Field errors should say what to fix and identify the field. A form-level
  failure should explain the next step without exposing raw stack or
  backend details. Dynamic messages may need a status/live region when
  they would otherwise be missed by assistive technology.
- For a destructive action, make the target and consequence clear in
  the product's existing confirmation pattern. Do not add repeated
  confirmation to harmless interactions.

```html
<label for="name">Project name</label>
<p id="name-error">Enter a project name.</p>
<input id="name" aria-invalid="true" aria-describedby="name-error">
<p role="status" id="save-status"></p>
```

See [WAI form notifications](https://www.w3.org/WAI/tutorials/forms/notifications/)
for field association and status patterns. Keep the visible label alongside
the error in a real form.

## State and interaction

- Keep state near the control that owns it. Derived values should be
  computed during rendering. An Effect belongs to synchronization with
  an external system, not to copying props or calculating a count.
- In vanilla JavaScript, attach handlers to semantic controls, clean up
  subscriptions that outlive their view and handle rejected promises.
  In React, use stable keys from data identity when lists can reorder.
- Avoid a new global store, generic event bus or custom hook for a single
  toggle or form field. Introduce shared state when multiple parts of the
  interface genuinely need one consistent value.

```js
copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(copyValue);
    status.textContent = "Copied";
  } catch {
    status.textContent = "Copy failed; select and copy the text manually.";
  }
});
```

The [interaction examples](references/interactions.md) cover the rejected
clipboard path. In React, see [Effect guidance](https://react.dev/learn/you-might-not-need-an-effect).

## Responsive layout and styling

- Check the narrow viewport, zoom, long labels and changed content states.
  Prefer layout rules that allow wrapping or stacking to fixed widths that
  clip content. Preserve hit target size and spacing for touch.
- Extend existing CSS custom properties, classes and responsive rules.
  Avoid a one-off palette or a layer of overrides that fights the current
  system. CSS should express the layout the component actually needs.
- Preserve readable contrast and visible focus in both supported themes.
  Test the actual states affected by the change, including disabled and
  error appearance.

```css
.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}
```

Use only a token that exists in the target product; this illustrates a
wrapping layout, not a proposed new design-system name.

## Rendering and security

- Render untrusted strings as text. Use React's normal text rendering,
  `textContent` in vanilla JavaScript and `html/template` in Go. Raw HTML
  insertion needs a separate sanitization and review decision.
- Keep secret or user-specific data out of public pages and client bundles.
  UI hiding is not authorization; the server operation must enforce access.
- Avoid displaying raw exception messages from network or backend errors.
  Preserve useful diagnostics at the owning server boundary.

```js
status.textContent = userSuppliedMessage;
```

[MDN's `textContent` reference](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent)
explains the text insertion behavior.

## Testing

- Test changed behavior from a user's point of view: can the labeled
  control be activated, does a rejected action show failure, does success
  happen only after completion? Assert visible text/state rather than
  private component implementation.
- Use the target repository's runner or existing static validator.
  Keyboard and narrow-screen checks are valuable for changed controls;
  do not claim a visual or assistive-technology check occurred unless it did.
- A focused regression test should fail for a plausible bug. Mock the
  external clipboard/network operation, not the interaction handler.

## Performance

- Avoid shipping server-only dependencies into the browser and large data
  props that the control never uses. Profile a slow interaction before
  adding memoization, virtualization or debouncing.
- Clean up timers/listeners and bound repeated requests when the view
  can trigger them. Do not cache mutable or private data without an
  explicit freshness and identity rule.

## Anti-slop review

- Reject placeholder-only labels, clickable `div` controls, invisible focus
  and a newly invented palette for one field.
- Reject an optimistic "Saved"/"Copied" after a rejected promise, empty
  fallback for unavailable data, or raw `innerHTML` for user text.
- Reject a client-wide state container or Effect for a derived count,
  decorative animation that obscures the primary action, and a screenshot
  check that ignores keyboard and failure states.

## Tooling and verification

Use the supplied validation for the target: Next.js scripts, Go `make verify`
or the Homepage static validator as applicable. Review the affected page at
the supported viewport and interaction states when that environment is
available. Report what was actually verified; a configuration parse does
not prove a visual result.
