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
  const fileInput = document.getElementById('fileInput');
  const previewState = document.getElementById('previewState');
  const outputName = document.getElementById('outputName');
  let smartLassoFallback = null;
  let automaticResultFallback = null;
  let shortFilenameCheckbox = null;

  if (selectionStatusCopy) {
    smartLassoFallback = document.createElement('p');
    smartLassoFallback.className = 'field-note selection-summary help-tip';
    smartLassoFallback.textContent = 'Not quite right? Try Smart Lasso for a more guided selection.';
    smartLassoFallback.hidden = true;
    smartLassoFallback.style.marginTop = '6px';
    selectionStatusCopy.appendChild(smartLassoFallback);
  }

  if (previewState) {
    automaticResultFallback = document.createElement('p');
    automaticResultFallback.className = 'preview-state help-tip';
    automaticResultFallback.textContent = 'Not quite right? Try Smart Lasso for a more guided selection.';
    automaticResultFallback.hidden = true;
    automaticResultFallback.style.marginTop = '6px';
    previewState.insertAdjacentElement('afterend', automaticResultFallback);
  }

  if (outputName) {
    const shortFilenameOption = document.createElement('label');
    shortFilenameOption.style.display = 'flex';
    shortFilenameOption.style.alignItems = 'center';
    shortFilenameOption.style.gap = '7px';
    shortFilenameOption.style.margin = '8px 1px 0';
    shortFilenameOption.style.color = 'var(--secondary)';
    shortFilenameOption.style.fontSize = '11px';
    shortFilenameOption.style.fontWeight = '400';
    shortFilenameOption.style.cursor = 'pointer';

    shortFilenameCheckbox = document.createElement('input');
    shortFilenameCheckbox.type = 'checkbox';
    shortFilenameCheckbox.id = 'shortFilename';
    shortFilenameCheckbox.style.margin = '0';
    shortFilenameCheckbox.style.accentColor = 'var(--blue)';

    const shortFilenameText = document.createElement('span');
    shortFilenameText.textContent = 'Short filename (original-name-converted.png)';

    shortFilenameOption.append(shortFilenameCheckbox, shortFilenameText);
    outputName.insertAdjacentElement('afterend', shortFilenameOption);
  }

  function imageIsLoaded() {
    return Boolean(fileMeta && fileMeta.textContent.trim() && fileMeta.textContent.trim() !== 'No image selected');
  }

  function sourceStem() {
    const file = fileInput?.files?.[0];
    const name = file?.name || fileMeta?.textContent.split(' · ')[0] || 'image';
    const dot = name.lastIndexOf('.');
    return dot > 0 ? name.slice(0, dot) : name;
  }

  function shortOutputName() {
    const stem = sourceStem();
    return `${stem.toLowerCase().endsWith('-converted') ? stem : `${stem}-converted`}.png`;
  }

  function syncShortFilename() {
    if (!shortFilenameCheckbox?.checked || !outputName || !imageIsLoaded()) return;
    outputName.value = shortOutputName();
  }

  function restoreDetailedFilename() {
    if (typeof window.refreshSuggestedName === 'function') {
      window.refreshSuggestedName();
    }
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

  shortFilenameCheckbox?.addEventListener('change', () => {
    if (shortFilenameCheckbox.checked) {
      syncShortFilename();
    } else {
      restoreDetailedFilename();
    }
  });

  fileInput?.addEventListener('change', () => window.setTimeout(syncShortFilename, 0));
  isolationModeInput?.addEventListener('change', () => {
    syncFallbackGuidance();
    window.setTimeout(syncShortFilename, 0);
  });

  ['width', 'height', 'colorMode', 'colors', 'resample'].forEach(id => {
    const control = document.getElementById(id);
    control?.addEventListener('input', () => window.setTimeout(syncShortFilename, 0));
    control?.addEventListener('change', () => window.setTimeout(syncShortFilename, 0));
  });

  document.querySelectorAll('.preset').forEach(button => {
    button.addEventListener('click', () => window.setTimeout(syncShortFilename, 0));
  });

  document.querySelectorAll('[data-tool]').forEach(button => {
    button.addEventListener('click', () => {
      window.setTimeout(syncFallbackGuidance, 0);
      window.setTimeout(syncShortFilename, 0);
    });
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
