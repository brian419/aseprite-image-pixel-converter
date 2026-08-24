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

  const isolationModeInput = document.getElementById('isolationMode');
  const selectionSummary = document.getElementById('selectionSummary');
  const selectionStatusCopy = selectionSummary?.closest('.selection-status-copy');
  const fileMeta = document.getElementById('fileMeta');
  const previewState = document.getElementById('previewState');
  let smartLassoFallback = null;
  let automaticResultFallback = null;

  if (selectionStatusCopy) {
    smartLassoFallback = document.createElement('p');
    smartLassoFallback.className = 'field-note selection-summary';
    smartLassoFallback.textContent = 'Not quite right? Try Smart Lasso for a more guided selection.';
    smartLassoFallback.hidden = true;
    smartLassoFallback.style.marginTop = '6px';
    selectionStatusCopy.appendChild(smartLassoFallback);
  }

  if (previewState) {
    automaticResultFallback = document.createElement('p');
    automaticResultFallback.className = 'preview-state';
    automaticResultFallback.textContent = 'Not quite right? Try Smart Lasso for a more guided selection.';
    automaticResultFallback.hidden = true;
    automaticResultFallback.style.marginTop = '6px';
    previewState.insertAdjacentElement('afterend', automaticResultFallback);
  }

  function imageIsLoaded() {
    return Boolean(fileMeta && fileMeta.textContent.trim() && fileMeta.textContent.trim() !== 'No image selected');
  }

  function syncFallbackGuidance() {
    if (!isolationModeInput) return;

    if (smartLassoFallback && selectionSummary) {
      const subjectIsolated = selectionSummary.textContent.trim().startsWith('Subject isolated.');
      smartLassoFallback.hidden = !(isolationModeInput.value === 'smart_click' && subjectIsolated);
    }

    if (automaticResultFallback) {
      automaticResultFallback.hidden = !(isolationModeInput.value === 'auto' && imageIsLoaded());
    }
  }

  cleanNode(document.body);
  syncFallbackGuidance();

  isolationModeInput?.addEventListener('change', syncFallbackGuidance);
  document.querySelectorAll('[data-tool]').forEach(button => {
    button.addEventListener('click', () => window.setTimeout(syncFallbackGuidance, 0));
  });

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      if (mutation.type === 'characterData') {
        cleanNode(mutation.target);
        continue;
      }
      for (const node of mutation.addedNodes) cleanNode(node);
    }
    syncFallbackGuidance();
  });

  observer.observe(document.body, {
    subtree: true,
    childList: true,
    characterData: true,
  });
})();
