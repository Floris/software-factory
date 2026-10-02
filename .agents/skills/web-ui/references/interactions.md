# Interaction examples

Bad: after `navigator.clipboard.writeText(value)` rejects, the button says
"Copied". A status element is updated with `innerHTML = error.message`.

Better: await the write, show "Copied" only on success, and show a useful
failure message in an existing status region. Set `textContent` for text from
external or user-controlled sources. A focused interaction test rejects the
clipboard promise and checks the visible failure state.

```js
try {
  await navigator.clipboard.writeText(value);
  status.textContent = "Copied";
} catch {
  status.textContent = "Copy failed; select and copy the text manually.";
}
```

Bad: a new form uses clickable `div` elements, placeholder-only labels and a
new color palette because the task asks for one extra field.

Better: add a labeled native input and button using the existing form classes.
Check focus order and the narrow viewport after the field is added.
