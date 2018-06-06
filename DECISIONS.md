# Decision Log

## Validation and Workflow
If a form does not validate, users are returned to the page with an error message. They are not allowed to skip ahead to other stages.

## Action buttons
The buttons at the bottom of the page will be implemented using `<button>` tags, rather than `<input type="button">`. For buttons that control flow, we set `name="action"`.

For accessibility, we use the `aria-label` property.