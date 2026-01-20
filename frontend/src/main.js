import './style.css'

// API base URL - empty in production (same origin), localhost in dev
const API_URL = '';

// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const clearFile = document.getElementById('clearFile');
const extractionType = document.getElementById('extractionType');
const modelSelect = document.getElementById('modelSelect');
const promptPreset = document.getElementById('promptPreset');
const customPromptGroup = document.getElementById('customPromptGroup');
const customPrompt = document.getElementById('customPrompt');
const extractBtn = document.getElementById('extractBtn');
const resultsSection = document.getElementById('resultsSection');
const resultsMeta = document.getElementById('resultsMeta');
const cleanedText = document.getElementById('cleanedText');
const rawText = document.getElementById('rawText');
const errorMessage = document.getElementById('errorMessage');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');

// State
let selectedFile = null;

// Initialize
checkApiHealth();
setupEventListeners();

function setupEventListeners() {
  // Drag and drop
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length && files[0].type === 'application/pdf') {
      handleFileSelect(files[0]);
    }
  });

  dropZone.addEventListener('click', () => fileInput.click());
  browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
      handleFileSelect(e.target.files[0]);
    }
  });

  clearFile.addEventListener('click', (e) => {
    e.stopPropagation();
    clearSelectedFile();
  });

  // Extraction type toggle
  extractionType.addEventListener('change', toggleAiOptions);

  // Prompt preset toggle
  promptPreset.addEventListener('change', () => {
    customPromptGroup.hidden = promptPreset.value !== 'custom';
  });

  // Extract button
  extractBtn.addEventListener('click', extractPdf);

  // Tab switching
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });

  // Copy buttons
  document.getElementById('copyCleaned').addEventListener('click', () => copyToClipboard(cleanedText.textContent));
  document.getElementById('copyRaw').addEventListener('click', () => copyToClipboard(rawText.textContent));

  // Download buttons
  document.getElementById('downloadCleaned').addEventListener('click', () => downloadText(cleanedText.textContent, 'cleaned.md'));
  document.getElementById('downloadRaw').addEventListener('click', () => downloadText(rawText.textContent, 'raw.md'));
}

function handleFileSelect(file) {
  selectedFile = file;
  fileName.textContent = file.name;
  fileInfo.hidden = false;
  dropZone.style.display = 'none';
  extractBtn.disabled = false;
  hideError();
}

function clearSelectedFile() {
  selectedFile = null;
  fileInput.value = '';
  fileInfo.hidden = true;
  dropZone.style.display = 'block';
  extractBtn.disabled = true;
}

function toggleAiOptions() {
  const isAi = extractionType.value === 'extract-with-ai';
  document.querySelectorAll('.ai-options').forEach(el => {
    el.classList.toggle('hidden', !isAi);
  });

  // Update tabs visibility
  const tabs = document.querySelector('.results-tabs');
  if (tabs) {
    tabs.style.display = isAi ? 'flex' : 'none';
  }
}

async function extractPdf() {
  if (!selectedFile) return;

  const btnText = extractBtn.querySelector('.btn-text');
  const btnLoading = extractBtn.querySelector('.btn-loading');

  // Show loading state
  btnText.hidden = true;
  btnLoading.hidden = false;
  extractBtn.disabled = true;
  hideError();
  resultsSection.hidden = true;

  const formData = new FormData();
  formData.append('file', selectedFile);

  const endpoint = extractionType.value;

  if (endpoint === 'extract-with-ai') {
    formData.append('model', modelSelect.value);
    formData.append('prompt_preset', promptPreset.value);
    if (promptPreset.value === 'custom' && customPrompt.value.trim()) {
      formData.append('custom_prompt', customPrompt.value.trim());
    }
  }

  try {
    const response = await fetch(`${API_URL}/${endpoint}`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'Extraction failed');
    }

    displayResults(data, endpoint);
  } catch (err) {
    showError(err.message);
  } finally {
    btnText.hidden = false;
    btnLoading.hidden = true;
    extractBtn.disabled = false;
  }
}

function displayResults(data, endpoint) {
  resultsSection.hidden = false;

  // Update tabs based on endpoint
  const tabs = document.querySelector('.results-tabs');
  const cleanedTab = document.querySelector('[data-tab="cleaned"]');

  if (endpoint === 'extract-with-ai') {
    tabs.style.display = 'flex';
    cleanedTab.textContent = `AI Cleaned (${data.model_used})`;
    cleanedText.textContent = data.cleaned_text || data.markdown;
    rawText.textContent = data.markdown;
    resultsMeta.textContent = `${data.page_count} pages`;

    if (data.error) {
      showError(`AI Error: ${data.error}`);
    }
  } else {
    tabs.style.display = 'none';
    cleanedText.textContent = data.markdown;
    rawText.textContent = data.markdown;
    resultsMeta.textContent = `${data.page_count} pages`;
    switchTab('cleaned');
  }

  // Scroll to results
  resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function switchTab(tabName) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

  document.querySelectorAll('.result-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`${tabName}Panel`).classList.add('active');
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function hideError() {
  errorMessage.hidden = true;
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    // Could add a toast notification here
  } catch (err) {
    console.error('Failed to copy:', err);
  }
}

function downloadText(text, filename) {
  const blob = new Blob([text], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function checkApiHealth() {
  try {
    const response = await fetch(`${API_URL}/health`);
    if (response.ok) {
      statusDot.classList.add('online');
      statusText.textContent = 'Online';
    } else {
      throw new Error('API not healthy');
    }
  } catch (err) {
    statusDot.classList.add('offline');
    statusText.textContent = 'Offline';
  }
}

// Initial AI options toggle
toggleAiOptions();
