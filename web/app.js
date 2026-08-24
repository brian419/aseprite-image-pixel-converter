const sourceFrame = document.getElementById('sourceFrame');
const outputFrame = document.getElementById('outputFrame');
const sourceCanvas = document.getElementById('sourceCanvas');
const outputCanvas = document.getElementById('outputCanvas');
const sourcePreview = document.getElementById('sourcePreview');
const outputPreview = document.getElementById('outputPreview');
const selectionOverlay = document.getElementById('selectionOverlay');
const fileInput = document.getElementById('fileInput');
const changeImageButton = document.getElementById('changeImageButton');
const fileMeta = document.getElementById('fileMeta');
const previewState = document.getElementById('previewState');
const zoomOutButton = document.getElementById('zoomOutButton');
const zoomInButton = document.getElementById('zoomInButton');
const zoomValue = document.getElementById('zoomValue');
const widthInput = document.getElementById('width');
const heightInput = document.getElementById('height');
const isolationModeInput = document.getElementById('isolationMode');
const isolationNote = document.getElementById('isolationNote');
const objectSettings = document.getElementById('objectSettings');
const objectToolbar = document.getElementById('objectToolbar');
const objectInstructions = document.getElementById('objectInstructions');
const selectionSummary = document.getElementById('selectionSummary');
const clearSelectionButton = document.getElementById('clearSelectionButton');
const colorModeInput = document.getElementById('colorMode');
const paletteControl = document.getElementById('paletteControl');
const colorsInput = document.getElementById('colors');
const resampleInput = document.getElementById('resample');
const outputName = document.getElementById('outputName');
const folderButton = document.getElementById('folderButton');
const folderPath = document.getElementById('folderPath');
const convertButton = document.getElementById('convertButton');
const status = document.getElementById('status');

let selectedFile = null;
let isolatedSubjectBlob = null;
let sourcePreviewUrl = null;
let outputPreviewUrl = null;
let hasOutputFolder = false;
let previewTimer = null;
let previewRequestId = 0;
let sourceRequestId = 0;
let isolationRequestId = 0;
let previewZoom = 1;
let syncingScroll = false;

let selectionTool = 'click';
let selectionPoint = null;
let lassoPoints = [];
let drawingLasso = false;

const zoomSteps = [0.5, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64];

function setStatus(message, kind = '') {
  status.textContent = message;
  status.className = `status ${kind}`.trim();
}

function setPreviewState(message, kind = '') {
  previewState.textContent = message;
  previewState.className = `preview-state ${kind}`.trim();
}

function smartIsolationEnabled() {
  return isolationModeInput.value !== 'auto';
}

function selectionReady() {
  return !smartIsolationEnabled() || isolatedSubjectBlob !== null;
}

function updateConvertState() {
  convertButton.disabled = !(selectedFile && hasOutputFolder && selectionReady());
}

function baseName(name) {
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(0, dot) : name;
}

function paletteIsLimited() {
  return colorModeInput.value === 'limit';
}

function refreshColorControls() {
  const limited = paletteIsLimited();
  colorsInput.disabled = !limited;
  paletteControl.classList.toggle('inactive', !limited);
}

function refreshSuggestedName() {
  const stem = selectedFile ? baseName(selectedFile.name) : 'converted';
  const parts = [stem, `${widthInput.value}x${heightInput.value}`, resampleInput.value];
  if (smartIsolationEnabled()) parts.push('isolated');
  if (paletteIsLimited()) {
    parts.push(`${colorsInput.value}c`);
  } else {
    parts.push('preserve');
  }
  outputName.value = `${parts.join('-')}.png`;
}

function buildConversionForm(includeOutputName = false) {
  const form = new FormData();
  form.append('image', selectedFile);
  form.append('width', widthInput.value);
  form.append('height', heightInput.value);
  form.append('color_mode', colorModeInput.value);
  form.append('colors', colorsInput.value);
  form.append('resample', resampleInput.value);
  form.append('alpha_threshold', '8');
  form.append('isolation_mode', isolationModeInput.value);
  if (isolatedSubjectBlob) {
    form.append('isolated_image', isolatedSubjectBlob, 'isolated-subject.png');
  }
  if (includeOutputName) form.append('output_name', outputName.value);
  return form;
}

function buildSourcePreviewForm() {
  const form = new FormData();
  form.append('image', selectedFile);
  form.append('alpha_threshold', '8');
  form.append('isolation_mode', isolationModeInput.value);
  return form;
}

function buildIsolationForm() {
  const form = new FormData();
  form.append('image', selectedFile);
  form.append('isolation_mode', isolationModeInput.value);
  if (isolationModeInput.value === 'smart_click' && selectionPoint) {
    form.append('selection_point', JSON.stringify(selectionPoint));
  }
  if (isolationModeInput.value === 'smart_lasso' && lassoPoints.length >= 3) {
    form.append('lasso_points', JSON.stringify(lassoPoints));
  }
  return form;
}

function suggestedPreviewZoom() {
  const width = Number(widthInput.value) || 128;
  const height = Number(heightInput.value) || 128;
  const largestSide = Math.max(width, height);
  if (largestSide <= 64) return 6;
  if (largestSide <= 96) return 4;
  if (largestSide <= 160) return 3;
  if (largestSide <= 256) return 2;
  return 1;
}

function applyCanvasGeometry() {
  const width = Math.max(8, Number(widthInput.value) || 128) * previewZoom;
  const height = Math.max(8, Number(heightInput.value) || 128) * previewZoom;
  for (const canvas of [sourceCanvas, outputCanvas]) {
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
  }

  zoomValue.textContent = `${Math.round(previewZoom * 100)}%`;
  const index = zoomSteps.indexOf(previewZoom);
  zoomOutButton.disabled = !selectedFile || index <= 0;
  zoomInButton.disabled = !selectedFile || index < 0 || index >= zoomSteps.length - 1;
  requestAnimationFrame(drawSelectionOverlay);
}

function viewCenter(frame) {
  const scrollableWidth = Math.max(1, frame.scrollWidth);
  const scrollableHeight = Math.max(1, frame.scrollHeight);
  return {
    x: (frame.scrollLeft + frame.clientWidth / 2) / scrollableWidth,
    y: (frame.scrollTop + frame.clientHeight / 2) / scrollableHeight,
  };
}

function restoreViewCenter(center) {
  requestAnimationFrame(() => {
    for (const frame of [sourceFrame, outputFrame]) {
      frame.scrollLeft = Math.max(0, center.x * frame.scrollWidth - frame.clientWidth / 2);
      frame.scrollTop = Math.max(0, center.y * frame.scrollHeight - frame.clientHeight / 2);
    }
  });
}

function setPreviewZoom(zoom) {
  const center = viewCenter(outputFrame);
  previewZoom = zoom;
  applyCanvasGeometry();
  restoreViewCenter(center);
}

function stepPreviewZoom(direction) {
  let index = zoomSteps.indexOf(previewZoom);
  if (index < 0) index = zoomSteps.findIndex(value => value >= previewZoom);
  if (index < 0) index = zoomSteps.length - 1;
  index = Math.max(0, Math.min(zoomSteps.length - 1, index + direction));
  setPreviewZoom(zoomSteps[index]);
}

function syncFrames(source, target) {
  if (syncingScroll) return;
  syncingScroll = true;
  target.scrollLeft = source.scrollLeft;
  target.scrollTop = source.scrollTop;
  requestAnimationFrame(() => { syncingScroll = false; });
}

sourceFrame.addEventListener('scroll', () => syncFrames(sourceFrame, outputFrame));
outputFrame.addEventListener('scroll', () => syncFrames(outputFrame, sourceFrame));

function enablePanning(frame) {
  let isPanning = false;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;

  const stop = pointerId => {
    if (!isPanning) return;
    isPanning = false;
    frame.classList.remove('panning');
    if (pointerId !== null && frame.hasPointerCapture(pointerId)) frame.releasePointerCapture(pointerId);
  };

  frame.addEventListener('pointerdown', event => {
    if (!frame.classList.contains('has-image') || event.button !== 0) return;
    if (frame === sourceFrame && smartIsolationEnabled() && selectionTool !== 'pan') return;

    isPanning = true;
    startX = event.clientX;
    startY = event.clientY;
    startLeft = frame.scrollLeft;
    startTop = frame.scrollTop;
    frame.classList.add('panning');
    frame.setPointerCapture(event.pointerId);
    event.preventDefault();
  });

  frame.addEventListener('pointermove', event => {
    if (!isPanning) return;
    frame.scrollLeft = startLeft - (event.clientX - startX);
    frame.scrollTop = startTop - (event.clientY - startY);
    event.preventDefault();
  });

  frame.addEventListener('pointerup', event => stop(event.pointerId));
  frame.addEventListener('pointercancel', event => stop(event.pointerId));
  frame.addEventListener('lostpointercapture', () => stop(null));
}

enablePanning(sourceFrame);
enablePanning(outputFrame);
sourcePreview.addEventListener('dragstart', event => event.preventDefault());
outputPreview.addEventListener('dragstart', event => event.preventDefault());

function sourceImageGeometry() {
  if (!sourcePreview.naturalWidth || !sourcePreview.naturalHeight) return null;

  const canvasWidth = sourceCanvas.clientWidth;
  const canvasHeight = sourceCanvas.clientHeight;
  if (!canvasWidth || !canvasHeight) return null;

  const scale = Math.min(
    canvasWidth / sourcePreview.naturalWidth,
    canvasHeight / sourcePreview.naturalHeight,
  );
  const width = sourcePreview.naturalWidth * scale;
  const height = sourcePreview.naturalHeight * scale;

  return {
    x: (canvasWidth - width) / 2,
    y: (canvasHeight - height) / 2,
    width,
    height,
  };
}

function overlayPointToNormalized(event) {
  const geometry = sourceImageGeometry();
  if (!geometry) return null;

  const bounds = selectionOverlay.getBoundingClientRect();
  const x = event.clientX - bounds.left;
  const y = event.clientY - bounds.top;

  if (
    x < geometry.x ||
    y < geometry.y ||
    x > geometry.x + geometry.width ||
    y > geometry.y + geometry.height
  ) {
    return null;
  }

  return [
    Math.max(0, Math.min(1, (x - geometry.x) / geometry.width)),
    Math.max(0, Math.min(1, (y - geometry.y) / geometry.height)),
  ];
}

function normalizedPointToCanvas(point, geometry) {
  return {
    x: geometry.x + point[0] * geometry.width,
    y: geometry.y + point[1] * geometry.height,
  };
}

function cssVariable(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function drawSelectionOverlay() {
  const bounds = selectionOverlay.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(bounds.width * dpr));
  const height = Math.max(1, Math.round(bounds.height * dpr));

  if (selectionOverlay.width !== width || selectionOverlay.height !== height) {
    selectionOverlay.width = width;
    selectionOverlay.height = height;
  }

  const context = selectionOverlay.getContext('2d');
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, bounds.width, bounds.height);

  if (!smartIsolationEnabled() || !selectedFile) return;
  const geometry = sourceImageGeometry();
  if (!geometry) return;

  if (selectionPoint) {
    const point = normalizedPointToCanvas(selectionPoint, geometry);
    context.save();
    context.strokeStyle = cssVariable('--selection', '#0071e3');
    context.fillStyle = 'rgba(0, 113, 227, 0.14)';
    context.lineWidth = 2;
    context.beginPath();
    context.arc(point.x, point.y, 9, 0, Math.PI * 2);
    context.fill();
    context.stroke();
    context.beginPath();
    context.moveTo(point.x - 13, point.y);
    context.lineTo(point.x + 13, point.y);
    context.moveTo(point.x, point.y - 13);
    context.lineTo(point.x, point.y + 13);
    context.stroke();
    context.restore();
  }

  if (lassoPoints.length > 0) {
    context.save();
    context.strokeStyle = cssVariable('--selection', '#0071e3');
    context.fillStyle = 'rgba(0, 113, 227, 0.10)';
    context.lineWidth = 2;
    context.setLineDash(drawingLasso ? [] : [7, 5]);
    context.beginPath();
    lassoPoints.forEach((point, index) => {
      const display = normalizedPointToCanvas(point, geometry);
      if (index === 0) context.moveTo(display.x, display.y);
      else context.lineTo(display.x, display.y);
    });
    if (!drawingLasso && lassoPoints.length >= 3) {
      context.closePath();
      context.fill();
    }
    context.stroke();
    context.restore();
  }
}

function setSelectionTool(tool) {
  selectionTool = tool;
  document.querySelectorAll('[data-tool]').forEach(button => {
    button.classList.toggle('active', button.dataset.tool === tool);
  });

  selectionOverlay.classList.remove('interactive', 'tool-click', 'tool-lasso');
  if (smartIsolationEnabled() && tool !== 'pan') {
    selectionOverlay.classList.add('interactive', `tool-${tool}`);
  }
}

function clearSubjectSelection({ keepTool = false } = {}) {
  isolationRequestId += 1;
  isolatedSubjectBlob = null;
  selectionPoint = null;
  lassoPoints = [];
  drawingLasso = false;
  if (!keepTool) {
    setSelectionTool(isolationModeInput.value === 'smart_lasso' ? 'lasso' : 'click');
  }
  selectionSummary.textContent = 'No subject selected yet.';
  outputFrame.classList.remove('has-image');
  if (smartIsolationEnabled() && selectedFile) {
    setPreviewState(
      isolationModeInput.value === 'smart_lasso'
        ? 'Draw a loose loop around the subject in the Source Image.'
        : 'Click the subject you want to isolate in the Source Image.'
    );
  }
  drawSelectionOverlay();
  updateConvertState();
  refreshSuggestedName();
}

function scheduleOutputPreview(delay = 250) {
  if (!selectedFile) return;
  window.clearTimeout(previewTimer);

  if (smartIsolationEnabled() && !isolatedSubjectBlob) {
    outputFrame.classList.remove('has-image');
    setPreviewState(
      isolationModeInput.value === 'smart_lasso'
        ? 'Draw a loose loop around the subject in the Source Image.'
        : 'Click the subject you want to isolate in the Source Image.'
    );
    updateConvertState();
    return;
  }

  previewTimer = window.setTimeout(renderOutputPreview, delay);
}

async function isolateCurrentSelection() {
  if (!selectedFile || !smartIsolationEnabled()) return;
  if (isolationModeInput.value === 'smart_click' && !selectionPoint) return;
  if (isolationModeInput.value === 'smart_lasso' && lassoPoints.length < 3) return;

  const requestId = ++isolationRequestId;
  isolatedSubjectBlob = null;
  outputFrame.classList.remove('has-image');
  updateConvertState();
  selectionSummary.textContent = 'Apple Vision is identifying the subject...';
  setPreviewState('Identifying and lifting the selected subject...');

  try {
    const response = await fetch('/api/isolate', {
      method: 'POST',
      body: buildIsolationForm(),
    });
    if (!response.ok) {
      const contentType = response.headers.get('content-type') || '';
      const data = contentType.includes('application/json') ? await response.json() : {};
      throw new Error(data.error || 'The selected subject could not be isolated.');
    }

    const blob = await response.blob();
    if (requestId !== isolationRequestId) return;

    isolatedSubjectBlob = blob;
    selectionSummary.textContent = 'Subject isolated. Click or lasso again to choose a different subject.';
    setSelectionTool('pan');
    drawSelectionOverlay();
    updateConvertState();
    setStatus(hasOutputFolder ? 'Ready to convert.' : 'Choose an output folder.');
    await renderOutputPreview();
  } catch (error) {
    if (requestId !== isolationRequestId) return;
    isolatedSubjectBlob = null;
    selectionSummary.textContent = 'No subject selected. Try again.';
    setPreviewState(error.message, 'error');
    setStatus('Subject selection needs another try.', 'error');
    updateConvertState();
  }
}

selectionOverlay.addEventListener('pointerdown', event => {
  if (!smartIsolationEnabled() || selectionTool === 'pan' || event.button !== 0) return;
  const point = overlayPointToNormalized(event);
  if (!point) return;

  if (selectionTool === 'click') {
    isolationModeInput.value = 'smart_click';
    selectionPoint = point;
    lassoPoints = [];
    isolatedSubjectBlob = null;
    drawSelectionOverlay();
    refreshSuggestedName();
    isolateCurrentSelection();
    event.preventDefault();
    return;
  }

  if (selectionTool === 'lasso') {
    isolationModeInput.value = 'smart_lasso';
    selectionPoint = null;
    isolatedSubjectBlob = null;
    lassoPoints = [point];
    drawingLasso = true;
    selectionOverlay.setPointerCapture(event.pointerId);
    selectionSummary.textContent = 'Drawing Smart Lasso...';
    drawSelectionOverlay();
    event.preventDefault();
  }
});

selectionOverlay.addEventListener('pointermove', event => {
  if (!drawingLasso || selectionTool !== 'lasso') return;
  const point = overlayPointToNormalized(event);
  if (!point) return;

  const previous = lassoPoints[lassoPoints.length - 1];
  const distance = Math.hypot(point[0] - previous[0], point[1] - previous[1]);
  if (distance >= 0.004 && lassoPoints.length < 800) {
    lassoPoints.push(point);
    drawSelectionOverlay();
  }
  event.preventDefault();
});

function finishLasso(event) {
  if (!drawingLasso || selectionTool !== 'lasso') return;
  drawingLasso = false;
  if (selectionOverlay.hasPointerCapture(event.pointerId)) {
    selectionOverlay.releasePointerCapture(event.pointerId);
  }

  if (lassoPoints.length < 3) {
    lassoPoints = [];
    selectionSummary.textContent = 'No subject selected yet.';
    setPreviewState('Draw a larger loop around the subject.', 'error');
    drawSelectionOverlay();
    return;
  }

  drawSelectionOverlay();
  refreshSuggestedName();
  isolateCurrentSelection();
}

selectionOverlay.addEventListener('pointerup', finishLasso);
selectionOverlay.addEventListener('pointercancel', event => {
  drawingLasso = false;
  lassoPoints = [];
  if (selectionOverlay.hasPointerCapture(event.pointerId)) {
    selectionOverlay.releasePointerCapture(event.pointerId);
  }
  selectionSummary.textContent = 'No subject selected yet.';
  drawSelectionOverlay();
});

document.querySelectorAll('[data-tool]').forEach(button => {
  button.addEventListener('click', () => {
    const tool = button.dataset.tool;
    if (tool === 'click' && isolationModeInput.value !== 'smart_click') {
      isolationModeInput.value = 'smart_click';
      clearSubjectSelection({ keepTool: true });
      refreshIsolationUI({ rerenderSource: false });
    } else if (tool === 'lasso' && isolationModeInput.value !== 'smart_lasso') {
      isolationModeInput.value = 'smart_lasso';
      clearSubjectSelection({ keepTool: true });
      refreshIsolationUI({ rerenderSource: false });
    }
    setSelectionTool(tool);
    drawSelectionOverlay();
  });
});
clearSelectionButton.addEventListener('click', () => clearSubjectSelection());

async function renderSourceComparison() {
  if (!selectedFile) return;
  const requestId = ++sourceRequestId;

  try {
    const response = await fetch('/api/source-preview', {
      method: 'POST',
      body: buildSourcePreviewForm(),
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || 'Source preview could not be generated.');
    }

    const blob = await response.blob();
    if (requestId !== sourceRequestId) return;

    if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl);
    sourcePreviewUrl = URL.createObjectURL(blob);
    sourcePreview.src = sourcePreviewUrl;
    sourceFrame.classList.add('has-image');
  } catch (error) {
    if (requestId !== sourceRequestId) return;
    sourceFrame.classList.remove('has-image');
    setPreviewState(error.message, 'error');
  }
}

async function renderOutputPreview() {
  if (!selectedFile) return;
  if (smartIsolationEnabled() && !isolatedSubjectBlob) {
    scheduleOutputPreview();
    return;
  }

  const requestId = ++previewRequestId;
  setPreviewState(smartIsolationEnabled() ? 'Pixelating isolated subject...' : 'Updating preview...');

  try {
    const response = await fetch('/api/preview', {
      method: 'POST',
      body: buildConversionForm(false),
    });
    if (!response.ok) {
      const contentType = response.headers.get('content-type') || '';
      const data = contentType.includes('application/json') ? await response.json() : {};
      throw new Error(data.error || 'Preview could not be generated.');
    }

    const blob = await response.blob();
    if (requestId !== previewRequestId) return;

    if (outputPreviewUrl) URL.revokeObjectURL(outputPreviewUrl);
    outputPreviewUrl = URL.createObjectURL(blob);
    outputPreview.src = outputPreviewUrl;
    outputFrame.classList.add('has-image');

    const colorText = paletteIsLimited() ? `up to ${colorsInput.value} colors` : 'resized colors preserved';
    const isolationText = smartIsolationEnabled() ? 'Apple Vision subject only' : 'automatic outer background';
    setPreviewState(`${widthInput.value} x ${heightInput.value} · ${colorText} · ${isolationText}`);
  } catch (error) {
    if (requestId !== previewRequestId) return;
    outputFrame.classList.remove('has-image');
    setPreviewState(error.message, 'error');
  }
}

async function chooseFile(file) {
  if (!file || !file.type.startsWith('image/')) {
    setStatus('Choose a PNG, JPEG, or WebP image.', 'error');
    return;
  }

  selectedFile = file;
  isolatedSubjectBlob = null;
  selectionPoint = null;
  lassoPoints = [];
  drawingLasso = false;
  isolationRequestId += 1;

  fileMeta.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
  changeImageButton.hidden = false;
  refreshSuggestedName();
  previewZoom = suggestedPreviewZoom();
  applyCanvasGeometry();

  sourceFrame.scrollTop = 0;
  sourceFrame.scrollLeft = 0;
  outputFrame.scrollTop = 0;
  outputFrame.scrollLeft = 0;

  if (smartIsolationEnabled()) {
    setSelectionTool(isolationModeInput.value === 'smart_lasso' ? 'lasso' : 'click');
    selectionSummary.textContent = 'No subject selected yet.';
  }
  updateConvertState();
  setStatus(hasOutputFolder ? (selectionReady() ? 'Ready to convert.' : 'Select a subject to convert.') : 'Choose an output folder.');

  await renderSourceComparison();
  drawSelectionOverlay();
  scheduleOutputPreview();
}

function refreshIsolationUI({ rerenderSource = true } = {}) {
  const enabled = smartIsolationEnabled();
  objectSettings.hidden = !enabled;
  objectToolbar.hidden = !enabled;

  if (!enabled) {
    isolationNote.textContent = 'The current automatic background behavior stays enabled.';
    selectionOverlay.classList.remove('interactive', 'tool-click', 'tool-lasso');
  } else if (isolationModeInput.value === 'smart_lasso') {
    isolationNote.textContent = 'Draw a loose loop around the object. Apple Vision chooses the detected foreground subject that best matches the lasso.';
    objectInstructions.textContent = 'Draw around the object loosely. You do not need to trace its exact edge. Apple Vision detects foreground subjects and keeps the subject occupying the lasso.';
    setSelectionTool('lasso');
  } else {
    isolationNote.textContent = 'Click directly on the object. Apple Vision detects and lifts the complete foreground subject with the background removed.';
    objectInstructions.textContent = 'Click directly on the object you want. Apple Vision detects the complete foreground subject and removes everything else.';
    setSelectionTool('click');
  }

  refreshSuggestedName();
  updateConvertState();
  drawSelectionOverlay();

  if (selectedFile && rerenderSource) renderSourceComparison();
  scheduleOutputPreview(100);
}

sourcePreview.addEventListener('load', () => requestAnimationFrame(drawSelectionOverlay));
window.addEventListener('resize', () => requestAnimationFrame(drawSelectionOverlay));

sourceFrame.addEventListener('click', () => {
  if (!selectedFile) fileInput.click();
});
sourceFrame.addEventListener('keydown', event => {
  if (!selectedFile && (event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault();
    fileInput.click();
  }
});
changeImageButton.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => chooseFile(fileInput.files[0]));

['dragenter', 'dragover'].forEach(type => sourceFrame.addEventListener(type, event => {
  event.preventDefault();
  sourceFrame.classList.add('dragging');
}));
['dragleave', 'drop'].forEach(type => sourceFrame.addEventListener(type, event => {
  event.preventDefault();
  sourceFrame.classList.remove('dragging');
}));
sourceFrame.addEventListener('drop', event => chooseFile(event.dataTransfer.files[0]));

document.querySelectorAll('.preset').forEach(button => button.addEventListener('click', () => {
  widthInput.value = button.dataset.size;
  heightInput.value = button.dataset.size;
  refreshSuggestedName();
  previewZoom = suggestedPreviewZoom();
  applyCanvasGeometry();
  scheduleOutputPreview();
}));

[widthInput, heightInput].forEach(input => input.addEventListener('input', () => {
  refreshSuggestedName();
  applyCanvasGeometry();
  scheduleOutputPreview();
}));

isolationModeInput.addEventListener('change', () => {
  clearSubjectSelection({ keepTool: true });
  refreshIsolationUI();
});
colorModeInput.addEventListener('change', () => {
  refreshColorControls();
  refreshSuggestedName();
  scheduleOutputPreview();
});
colorsInput.addEventListener('input', () => {
  refreshSuggestedName();
  if (paletteIsLimited()) scheduleOutputPreview();
});
resampleInput.addEventListener('change', () => {
  refreshSuggestedName();
  scheduleOutputPreview();
});
zoomOutButton.addEventListener('click', () => stepPreviewZoom(-1));
zoomInButton.addEventListener('click', () => stepPreviewZoom(1));

folderButton.addEventListener('click', async () => {
  folderButton.disabled = true;
  setStatus('Opening folder chooser...');

  try {
    const response = await fetch('/api/choose-folder', { method: 'POST' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not choose a folder.');

    if (data.cancelled) {
      setStatus(selectedFile ? (selectionReady() ? 'Choose an output folder.' : 'Select a subject to convert.') : 'Choose an image and output folder to begin.');
      return;
    }

    hasOutputFolder = true;
    folderPath.textContent = data.path;
    updateConvertState();

    if (!selectedFile) {
      setStatus('Choose an image.');
    } else if (!selectionReady()) {
      setStatus('Select a subject in the Source Image.');
    } else {
      setStatus('Ready to convert.');
    }
  } catch (error) {
    setStatus(error.message, 'error');
  } finally {
    folderButton.disabled = false;
  }
});

convertButton.addEventListener('click', async () => {
  if (!selectedFile || !hasOutputFolder || !selectionReady()) return;

  convertButton.disabled = true;
  setStatus(smartIsolationEnabled() ? 'Converting isolated subject...' : 'Converting...');

  try {
    const response = await fetch('/api/convert', {
      method: 'POST',
      body: buildConversionForm(true),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Conversion failed.');

    hasOutputFolder = false;
    folderPath.textContent = 'Choose a folder for the next conversion.';
    updateConvertState();
    setStatus(`Saved ${data.filename}`, 'success');
  } catch (error) {
    updateConvertState();
    setStatus(error.message, 'error');
  }
});

refreshColorControls();
refreshIsolationUI({ rerenderSource: false });
