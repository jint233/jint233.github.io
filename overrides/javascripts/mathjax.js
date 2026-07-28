// Configure MathJax before loading its browser runtime.
window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex",
    enableMenu: false,
  },
};

document$.subscribe(() => {
  if (typeof window.MathJax?.typesetPromise !== "function") {
    return;
  }

  window.MathJax.startup?.output?.clearCache?.();
  window.MathJax.typesetClear?.();
  window.MathJax.texReset?.();
  window.MathJax.typesetPromise().catch((error) => {
    console.error("MathJax typesetting failed:", error);
  });
});
