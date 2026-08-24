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
const clearSelectionButton = document.getElementById('clearSelectionButton');
const refineSizeInput = document.getElementById('refineSize');
const selectionSummary = document.getElementById('selectionSummary');
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
let sourcePreviewUrl = null;
let outputPreviewUrl = null;
let hasOutputFolder = false;
let previewTimer = null;
let previewRequestId = 0;
let sourceRequestId = 0;
let previewZoom = 1;
let syncingScroll = false;

let selectionRect = null;
let keepPoints = [];
let removePoints = [];
let selectionTool = 'box';
let boxStart = null;
let pendingRect = null;

const zoomSteps = [0.5, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64];

function setStatus(message, kind = '') {
  status.textContent = message;
  status.className = `status ${kind}`.trim();
}

function setPreviewState(message, kind = '') {
  previewState.textContent = message;
  previewState.className = `preview-state ${kind}`.trim();
}

function objectIsolationEnabled() {
  return isolationModeInput.value === 'object';
}

function selectionReady() {
  return !objectIsolationEnabled() || selectionRect !== null;
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
  if (objectIsolationEnabled()) parts.push('isolated');
  if (paletteIsLimited()) {
    parts.push(`${colorsInput.value}c`);
  } else {
    parts.push('preserve');
  }
  outputName.value = `${parts.join('-')}.png`;
}

function appendIsolationData(form) {
  form.append('isolation_mode', isolationModeInput.value);
  if (!objectIsolationEnabled()) return;

  if (selectionRect) form.append('selection_rect', JSON.stringify(selectionRect));
  form.append('keep_points', JSON.stringify(keepPoints));
  form.append('remove_points', JSON.stringify(removePoints));
  form.append('refine_radius', refineSizeInput.value);
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
  appendIsolationData(form);
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
    if (frame === sourceFrame && objectIsolationEnabled() && selectionTool !== 'pan') return;

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

function normalizedRectToCanvas(rect, geometry) {
  return {
    x: geometry.x + rect[0] * geometry.width,
    y: geometry.y + rect[1] * geometry.height,
    width: rect[2] * geometry.width,
    height: rect[3] * geometry.height,
  };
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

  if (!objectIsolationEnabled() || !selectedFile) return;
  const geometry = sourceImageGeometry();
  if (!geometry) return;

  const rect = pendingRect || selectionRect;
  if (rect) {
    const displayRect = normalizedRectToCanvas(rect, geometry);

    context.save();
    context.fillStyle = 'rgba(0, 0, 0, 0.18)';
    context.beginPath();
    context.rect(geometry.x, geometry.y, geometry.width, geometry.height);
    context.rect(displayRect.x, displayRect.y, displayRect.width, displayRect.height);
    context.fill('evenodd');
    context.restore();

    context.save();
    context.strokeStyle = cssVariable('--selection', '#0071e3');
    context.lineWidth = 2;
    context.setLineDash([7, 5]);
    context.strokeRect(displayRect.x, displayRect.y, displayRect.width, displayRect.height);
    context.restore();
  }

  const markerRadius = Math.max(3, Number(refineSizeInput.value) * Math.min(geometry.width, geometry.height));

  const drawMarks = (points, variable, fallback, label) => {
    context.save();
    context.fillStyle = cssVariable(variable, fallback);
    context.strokeStyle = 'rgba(255,255,255,.9)';
    context.lineWidth = 1.5;
    context.font = '600 10px -apple-system, BlinkMacSystemFont, sans-serif';
    context.textAlign = 'center';
    context.textBaseline = 'middle';

    for (const point of points) {
      const displayPoint = normalizedPointToCanvas(point, geometry);
      context.beginPath();
      context.arc(displayPoint.x, displayPoint.y, markerRadius, 0, Math.PI * 2);
      context.fill();
      context.stroke();
      context.fillStyle = '#fff';
      context.fillText(label, displayPoint.x, displayPoint.y + .5);
      context.fillStyle = cssVariable(variable, fallback);
    }
    context.restore();
  };

  drawMarks(keepPoints, '--keep', '#1f8f4d', '+');
  drawMarks(removePoints, '--remove', '#d23b32', '-');
}

function pointInsideSelection(point) {
  if (!selectionRect) return false;
  return (
    point[0] >= selectionRect[0] &&
    point[1] >= selectionRect[1] &&
    point[0] <= selectionRect[0] + selectionRect[2] &&
    point[1] <= selectionRect[1] + selectionRect[3]
  );
}

function normalizedRectFromPoints(first, second) {
  const left = Math.min(first[0], second[0]);
  const top = Math.min(first[1], second[1]);
  const right = Math.max(first[0], second[0]);
  const bottom = Math.max(first[1], second[1]);
  return [left, top, right - left, bottom - top];
}

function refreshSelectionSummary() {
  if (!selectionRect) {
    selectionSummary.textContent = 'No object box drawn yet.';
    return;
  }

  const refinements = keepPoints.length + removePoints.length;
  selectionSummary.textContent = refinements
    ? `Object box ready. ${keepPoints.length} Keep and ${removePoints.length} Remove mark${refinements === 1 ? '' : 's'}.`
    : 'Object box ready. Add Keep or Remove marks only if the preview needs refinement.';
}

function setSelectionTool(tool) {
  selectionTool = tool;
  document.querySelectorAll('[data-tool]').forEach(button => {
    button.classList.toggle('active', button.dataset.tool === tool);
  });

  selectionOverlay.classList.remove('interactive', 'tool-box', 'tool-keep', 'tool-remove');
  if (objectIsolationEnabled() && tool !== 'pan') {
    selectionOverlay.classList.add('interactive', `tool-${tool}`);
  }
}

function clearSelection() {
  selectionRect = null;
  keepPoints = [];
  removePoints = [];
  boxStart = null;
  pendingRect = null;
  setSelectionTool('box');
  refreshSelectionSummary();
  drawSelectionOverlay();
  updateConvertState();

  if (objectIsolationEnabled()) {
    outputFrame.classList.remove('has-image');
    setPreviewState('Draw a box around the object in the Source Image.');
  }
}

function scheduleOutputPreview(delay = 300) {
  if (!selectedFile) return;
  window.clearTimeout(previewTimer);

  if (objectIsolationEnabled() && !selectionRect) {
    outputFrame.classList.remove('has-image');
    setPreviewState('Draw a box around the object in the Source Image.');
    updateConvertState();
    return;
  }

  previewTimer = window.setTimeout(renderOutputPreview, delay);
}

function selectionChanged() {
  refreshSelectionSummary();
  drawSelectionOverlay();
  updateConvertState();
  refreshSuggestedName();
  scheduleOutputPreview(120);
}

selectionOverlay.addEventListener('pointerdown', event => {
  if (!objectIsolationEnabled() || selectionTool === 'pan' || event.button !== 0) return;

  const point = overlayPointToNormalized(event);
  if (!point) return;

  if (selectionTool === 'box') {
    boxStart = point;
    pendingRect = [point[0], point[1], 0, 0];
    selectionOverlay.setPointerCapture(event.pointerId);
    drawSelectionOverlay();
    event.preventDefault();
    return;
  }

  if (!selectionRect) {
    setPreviewState('Draw a box around the object before adding refinement marks.', 'error');
    return;
  }
  if (!pointInsideSelection(point)) {
    setPreviewState('Keep and Remove marks must be inside the object box.', 'error');
    return;
  }

  if (selectionTool === 'keep') {
    keepPoints.push(point);
  } else if (selectionTool === 'remove') {
    removePoints.push(point);
  }
  selectionChanged();
  event.preventDefault();
});

selectionOverlay.addEventListener('pointermove', event => {
  if (!boxStart || selectionTool !== 'box') return;
  const point = overlayPointToNormalized(event);
  if (!point) return;
  pendingRect = normalizedRectFromPoints(boxStart, point);
  drawSelectionOverlay();
  event.preventDefault();
});

function finishBox(event) {
  if (!boxStart || selectionTool !== 'box') return;

  const point = overlayPointToNormalized(event);
  const rect = point ? normalizedRectFromPoints(boxStart, point) : pendingRect;
  boxStart = null;
  pendingRect = null;

  if (selectionOverlay.hasPointerCapture(event.pointerId)) {
    selectionOverlay.releasePointerCapture(event.pointerId);
  }

  if (!rect || rect[2] < 0.01 || rect[3] < 0.01) {
    drawSelectionOverlay();
    setPreviewState('Draw a larger box around the object.', 'error');
    return;
  }

  selectionRect = rect;
  keepPoints = [];
  removePoints = [];
  setSelectionTool('pan');
  selectionChanged();
}

selectionOverlay.addEventListener('pointerup', finishBox);
selectionOverlay.addEventListener('pointercancel', event => {
  boxStart = null;
  pendingRect = null;
  if (selectionOverlay.hasPointerCapture(event.pointerId)) {
    selectionOverlay.releasePointerCapture(event.pointerId);
  }
  drawSelectionOverlay();
});

document.querySelectorAll('[data-tool]').forEach(button => {
  button.addEventListener('click', () => setSelectionTool(button.dataset.tool));
});
clearSelectionButton.addEventListener('click', clearSelection);
refineSizeInput.addEventListener('change', () => {
  drawSelectionOverlay();
  if (selectionRect && (keepPoints.length || removePoints.length)) scheduleOutputPreview(120);
});

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
  if (objectIsolationEnabled() && !selectionRect) {
    setPreviewState('Draw a box around the object in the Source Image.');
    return;
  }

  const requestId = ++previewRequestId;
  setPreviewState(objectIsolationEnabled() ? 'Isolating object and updating preview...' : 'Updating preview...');

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
    const isolationText = objectIsolationEnabled() ? 'selected object only' : 'automatic outer background';
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
  selectionRect = null;
  keepPoints = [];
  removePoints = [];
  boxStart = null;
  pendingRect = null;

  fileMeta.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
  changeImageButton.hidden = false;
  refreshSuggestedName();
  previewZoom = suggestedPreviewZoom();
  applyCanvasGeometry();

  sourceFrame.scrollTop = 0;
  sourceFrame.scrollLeft = 0;
  outputFrame.scrollTop = 0;
  outputFrame.scrollLeft = 0;

  if (objectIsolationEnabled()) setSelectionTool('box');
  refreshSelectionSummary();
  updateConvertState();
  setStatus(hasOutputFolder ? (selectionReady() ? 'Ready to convert.' : 'Select the object to convert.') : 'Choose an output folder.');

  await renderSourceComparison();
  drawSelectionOverlay();
  scheduleOutputPreview();
}

function refreshIsolationUI({ rerenderSource = true } = {}) {
  const enabled = objectIsolationEnabled();
  objectSettings.hidden = !enabled;
  objectToolbar.hidden = !enabled;
  isolationNote.textContent = enabled
    ? 'Only the object inside your interactive selection will be kept. The rest becomes transparent before pixel conversion.'
    : 'The current automatic background behavior stays enabled.';

  if (enabled) {
    setSelectionTool(selectionRect ? 'pan' : 'box');
  } else {
    selectionOverlay.classList.remove('interactive', 'tool-box', 'tool-keep', 'tool-remove');
  }

  refreshSuggestedName();
  updateConvertState();
  refreshSelectionSummary();
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

isolationModeInput.addEventListener('change', () => refreshIsolationUI());
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
      setStatus(selectedFile ? (selectionReady() ? 'Choose an output folder.' : 'Select the object to convert.') : 'Choose an image and output folder to begin.');
      return;
    }

    hasOutputFolder = true;
    folderPath.textContent = data.path;
    updateConvertState();

    if (!selectedFile) {
      setStatus('Choose an image.');
    } else if (!selectionReady()) {
      setStatus('Draw a box around the object.');
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
  setStatus(objectIsolationEnabled() ? 'Isolating object and converting...' : 'Converting...');

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
