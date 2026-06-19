// Hardcoded seed document that stands in for the (not-yet-built) generation step.
// It is a single self-contained HTML document with inline CSS. Every editable
// element carries a unique data-eid so the scoped-edit loop can target it by id.
export const SEED_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #f5f5f5; color: #1a1a1a; }
  .wrap { max-width: 720px; margin: 0 auto; padding: 48px 24px; }
  h1 { font-size: 40px; margin: 0 0 16px; }
  .cta { display: inline-block; padding: 12px 20px; border: none; border-radius: 8px;
         background: #1a1a1a; color: #fff; font-size: 16px; cursor: pointer; }
  .cards { display: flex; gap: 16px; margin-top: 40px; }
  .card { flex: 1; background: #fff; border-radius: 12px; padding: 24px;
          box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  .card h2 { margin: 0 0 8px; font-size: 20px; }
  .card p { margin: 0; color: #555; }
</style>
</head>
<body>
  <div class="wrap">
    <h1 data-eid="hero-title">Build pages by talking to them</h1>
    <button class="cta" data-eid="hero-cta">Get started</button>
    <div class="cards">
      <div class="card" data-eid="card-1">
        <h2>Click anything</h2>
        <p>Select an element in the live preview to edit just that piece.</p>
      </div>
      <div class="card" data-eid="card-2">
        <h2>Edit in place</h2>
        <p>Only the chosen element is sent to the model and swapped back in.</p>
      </div>
    </div>
  </div>
</body>
</html>`
