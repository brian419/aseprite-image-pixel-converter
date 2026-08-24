(() => {
  const replacements = [
    ['Apple Vision subject only', 'isolated subject only'],
    ['Apple Vision is identifying the subject', 'Smart subject detection is identifying the subject'],
    ['Apple Vision', 'Smart subject detection'],
  ];

  function cleanText(value) {
    let cleaned = value;
    for (const [from, to] of replacements) {
      cleaned = cleaned.split(from).join(to);
    }
    return cleaned;
  }

  function cleanNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const cleaned = cleanText(node.nodeValue || '');
      if (cleaned !== node.nodeValue) node.nodeValue = cleaned;
      return;
    }

    if (!(node instanceof Element)) return;
    for (const child of node.childNodes) cleanNode(child);
  }

  cleanNode(document.body);

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      if (mutation.type === 'characterData') {
        cleanNode(mutation.target);
        continue;
      }
      for (const node of mutation.addedNodes) cleanNode(node);
    }
  });

  observer.observe(document.body, {
    subtree: true,
    childList: true,
    characterData: true,
  });
})();
