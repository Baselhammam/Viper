// This script runs INSIDE the sandboxed iframe. It is injected at serialize time
// (not stored in the seed) so the click listener is always present — including
// after a swap re-renders the whole document.
//
// On click it walks up to the nearest [data-eid] ancestor, captures its CLEAN
// outerHTML (before any highlight is applied — otherwise the selection outline
// would leak into the HTML we send to the model), outlines it, suppresses the
// element's default behavior (so buttons/links don't navigate on an edit click),
// and posts the eid + clean outerHTML to the parent window.
//
// The closing tag is split via interpolation (`<${'/script>'}`) so the literal
// substring "</script>" never appears in source, which would otherwise prematurely
// terminate the script context once this module is embedded in an HTML document.
export const CLICK_SCRIPT = `
<script>
(function () {
  var SELECTED_OUTLINE = '2px solid #2563eb';
  var current = null;

  function clearHighlight(el) {
    if (!el) return;
    el.style.outline = '';
    // Drop a now-empty style attribute so it never pollutes a future outerHTML read.
    if (el.getAttribute('style') === '') el.removeAttribute('style');
  }

  document.addEventListener('click', function (event) {
    var target = event.target && event.target.closest
      ? event.target.closest('[data-eid]')
      : null;
    if (!target) return;

    event.preventDefault();
    event.stopPropagation();

    // Clear any existing highlight (including target's own, on a re-click) BEFORE
    // reading outerHTML, so the captured HTML is free of the selection outline.
    clearHighlight(current);
    var html = target.outerHTML;

    current = target;
    target.style.outline = SELECTED_OUTLINE;

    parent.postMessage({
      source: 'scoped-edit-preview',
      eid: target.getAttribute('data-eid'),
      outerHTML: html
    }, '*');
  }, true);
})();
<${'/script>'}
`
