(() => {
  const href = '/ui-assets/issue-tracking.css';
  if ([...document.styleSheets].some((sheet) => sheet.href && sheet.href.endsWith(href))) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = href;
  document.head.appendChild(link);
})();
