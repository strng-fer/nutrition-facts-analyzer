/**
 * 🍎 Nutrition Facts Extractor — Interactive Client Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const dropzone = document.getElementById('uploadDropzone');
  const fileInput = document.getElementById('fileInput');
  const previewContainer = document.getElementById('previewContainer');
  const previewImage = document.getElementById('previewImage');
  const previewMeta = document.getElementById('previewMeta');
  const btnRemovePreview = document.getElementById('btnRemovePreview');
  const btnExtract = document.getElementById('btnExtract');

  const emptyState = document.getElementById('emptyState');
  const loadingState = document.getElementById('loadingState');
  const resultsContainer = document.getElementById('resultsContainer');

  const backendStatus = document.getElementById('backendStatus');
  const searchInput = document.getElementById('nutrientSearchInput');
  const toast = document.getElementById('toastNotification');

  let currentFile = null;
  let currentResult = null;
  let stepTimer = null;

  // ═══════════════════════════════════════
  // 1. HEALTH CHECK MONITORING
  // ═══════════════════════════════════════
  async function checkHealth() {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        backendStatus.className = 'status-badge';
        backendStatus.innerHTML = '<span class="status-dot"></span> Backend Connected';
      } else {
        throw new Error('Not OK');
      }
    } catch {
      backendStatus.className = 'status-badge offline';
      backendStatus.innerHTML = '<span class="status-dot"></span> Backend Offline';
    }
  }
  checkHealth();
  setInterval(checkHealth, 15000);

  // ═══════════════════════════════════════
  // 2. DRAG & DROP AND FILE SELECTION
  // ═══════════════════════════════════════
  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFileSelected(files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  // Support Ctrl+V paste image from clipboard
  window.addEventListener('paste', (e) => {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (const item of items) {
      if (item.kind === 'file' && item.type.startsWith('image/')) {
        const file = item.getAsFile();
        handleFileSelected(file);
        showToast('📋 Gambar ditempel dari clipboard');
        break;
      }
    }
  });

  function handleFileSelected(file) {
    if (!file.type.match(/^image\/(jpeg|png|webp)$/i)) {
      alert('Harap pilih gambar dalam format JPEG, PNG, atau WebP.');
      return;
    }

    currentFile = file;
    const reader = new FileReader();

    reader.onload = (e) => {
      previewImage.src = e.target.result;
      const img = new Image();
      img.onload = () => {
        const sizeKb = (file.size / 1024).toFixed(1);
        previewMeta.textContent = `📐 ${img.width}×${img.height} px | 📁 ${file.name || 'Pasted Image'} | 💾 ${sizeKb} KB`;
        previewContainer.classList.add('active');
        btnExtract.disabled = false;
        dropzone.style.display = 'none';
      };
      img.src = e.target.result;
    };

    reader.readAsDataURL(file);
  }

  btnRemovePreview.addEventListener('click', () => {
    currentFile = null;
    fileInput.value = '';
    previewImage.src = '';
    previewContainer.classList.remove('active');
    dropzone.style.display = 'block';
    btnExtract.disabled = true;
  });

  // ═══════════════════════════════════════
  // 3. PIPELINE STEP ANIMATION
  // ═══════════════════════════════════════
  const steps = [
    { id: 'step-detection', name: 'Step 1: Detection (Roboflow)', time: 0 },
    { id: 'step-crop', name: 'Step 2: Crop & Preprocess (OpenCV)', time: 3000 },
    { id: 'step-ocr', name: 'Step 3: OCR Engine (PaddleOCR)', time: 6000 },
    { id: 'step-llm', name: 'Step 4: AI Extraction (Gemini Flash)', time: 14000 }
  ];

  function startPipelineAnimation() {
    clearPipelineAnimation();
    let index = 0;
    const setStepActive = (i) => {
      steps.forEach((s, idx) => {
        const el = document.getElementById(s.id);
        if (!el) return;
        if (idx < i) {
          el.className = 'step-item completed';
        } else if (idx === i) {
          el.className = 'step-item active';
        } else {
          el.className = 'step-item';
        }
      });
    };

    setStepActive(0);
    stepTimer = setInterval(() => {
      index++;
      if (index < steps.length) {
        setStepActive(index);
      }
    }, 4500);
  }

  function completePipelineAnimation() {
    if (stepTimer) clearInterval(stepTimer);
    steps.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) el.className = 'step-item completed';
    });
  }

  function clearPipelineAnimation() {
    if (stepTimer) clearInterval(stepTimer);
    steps.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) el.className = 'step-item';
    });
  }

  // ═══════════════════════════════════════
  // 4. SUBMIT & RUN EXTRACTION
  // ═══════════════════════════════════════
  btnExtract.addEventListener('click', async () => {
    if (!currentFile) return;

    // UI state
    btnExtract.disabled = true;
    emptyState.style.display = 'none';
    resultsContainer.classList.remove('active');
    loadingState.classList.add('active');
    startPipelineAnimation();

    const formData = new FormData();
    formData.append('file', currentFile);

    try {
      const response = await fetch('/extract-nutrition', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();
      currentResult = result;
      completePipelineAnimation();

      if (!response.ok || !result.success) {
        showError(result.error || `HTTP ${response.status}: Ekstraksi gagal.`);
        return;
      }

      displayResults(result);
      showToast('🎉 Berhasil mengekstrak data nutrisi!');

    } catch (err) {
      completePipelineAnimation();
      showError('Gagal terhubung ke backend. Pastikan server aktif.');
      console.error(err);
    } finally {
      loadingState.classList.remove('active');
      btnExtract.disabled = false;
    }
  });

  // ═══════════════════════════════════════
  // 5. RENDER RESULTS
  // ═══════════════════════════════════════
  function displayResults(res) {
    resultsContainer.classList.add('active');

    // Warnings
    const warningBox = document.getElementById('warningBanner');
    if (res.warnings && res.warnings.length > 0) {
      warningBox.style.display = 'flex';
      warningBox.querySelector('.alert-text').innerHTML = res.warnings.map(w => `• ${w}`).join('<br>');
    } else {
      warningBox.style.display = 'none';
    }

    // Metrics
    document.getElementById('metricEngine').textContent = res.ocr_engine_used || 'N/A';
    document.getElementById('metricOcrConf').textContent = res.ocr_confidence ? `${(res.ocr_confidence * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('metricDetConf').textContent = res.detection_confidence ? `${(res.detection_confidence * 100).toFixed(1)}%` : 'Full Image';

    // Nutrition Data
    const nd = res.nutrition_data || {};
    
    // Product Tag
    const productTag = document.getElementById('productNameTag');
    if (nd.product_name) {
      productTag.style.display = 'inline-flex';
      productTag.textContent = `🏷️ ${nd.product_name}`;
    } else {
      productTag.style.display = 'none';
    }

    // Hero Stats
    document.getElementById('valServingSize').textContent = nd.serving_size || '-';
    document.getElementById('valServingsPerPkg').textContent = nd.servings_per_package || '-';
    document.getElementById('valCalories').textContent = nd.calories || '-';

    // Render Table
    renderNutrientsTable(nd.nutrients || []);

    // Raw OCR Text
    document.getElementById('rawOcrText').textContent = res.raw_ocr_text || '(Tidak ada teks OCR)';

    // Raw JSON
    document.getElementById('rawJsonText').textContent = JSON.stringify(res, null, 2);
  }

  function renderNutrientsTable(nutrients) {
    const tbody = document.getElementById('nutrientsTableBody');
    tbody.innerHTML = '';

    if (!nutrients || nutrients.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-dim); padding: 24px;">Tidak ada nutrisi spesifik ditemukan.</td></tr>`;
      return;
    }

    nutrients.forEach(n => {
      const tr = document.createElement('tr');
      tr.setAttribute('data-nutrient-name', (n.name || '').toLowerCase());

      // Parse AKG percentage for progress bar
      let akgNum = 0;
      let akgDisplay = n.percent_daily_value || '-';
      if (n.percent_daily_value) {
        const match = n.percent_daily_value.match(/(\d+(\.\d+)?)/);
        if (match) {
          akgNum = Math.min(Math.max(parseFloat(match[1]), 0), 100);
        }
      }

      tr.innerHTML = `
        <td class="nutrient-name">${escapeHtml(n.name || '-')}</td>
        <td class="nutrient-amount">${escapeHtml(n.amount_per_serving || '-')}</td>
        <td>
          <div class="akg-cell">
            <span class="akg-text">${escapeHtml(akgDisplay)}</span>
            <div class="akg-bar-track">
              <div class="akg-bar-fill" style="width: ${akgNum}%"></div>
            </div>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ═══════════════════════════════════════
  // 6. FILTER / SEARCH NUTRIENTS
  // ═══════════════════════════════════════
  searchInput.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    const rows = document.querySelectorAll('#nutrientsTableBody tr');
    rows.forEach(row => {
      const name = row.getAttribute('data-nutrient-name') || '';
      row.style.display = name.includes(q) ? '' : 'none';
    });
  });

  // ═══════════════════════════════════════
  // 7. ACCORDION HANDLERS
  // ═══════════════════════════════════════
  document.querySelectorAll('.accordion-header').forEach(header => {
    header.addEventListener('click', () => {
      const item = header.closest('.accordion-item');
      item.classList.toggle('open');
    });
  });

  // ═══════════════════════════════════════
  // 8. COPY & EXPORT ACTIONS
  // ═══════════════════════════════════════
  document.getElementById('btnCopyOcr').addEventListener('click', () => {
    const text = document.getElementById('rawOcrText').textContent;
    copyToClipboard(text, '📋 Teks OCR disalin ke clipboard');
  });

  document.getElementById('btnCopyJson').addEventListener('click', () => {
    const text = document.getElementById('rawJsonText').textContent;
    copyToClipboard(text, '📋 JSON disalin ke clipboard');
  });

  document.getElementById('btnDownloadJson').addEventListener('click', () => {
    if (!currentResult) return;
    const blob = new Blob([JSON.stringify(currentResult, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nutrition_facts_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('💾 JSON berhasil diunduh');
  });

  document.getElementById('btnCopySummary').addEventListener('click', () => {
    if (!currentResult || !currentResult.nutrition_data) return;
    const nd = currentResult.nutrition_data;
    let summary = `🍎 NUTRITION FACTS SUMMARY\n`;
    if (nd.product_name) summary += `Produk: ${nd.product_name}\n`;
    if (nd.serving_size) summary += `Takaran Saji: ${nd.serving_size}\n`;
    if (nd.servings_per_package) summary += `Sajian per Kemasan: ${nd.servings_per_package}\n`;
    if (nd.calories) summary += `Kalori: ${nd.calories}\n`;
    summary += `\nNUTRISI:\n`;
    (nd.nutrients || []).forEach(n => {
      summary += `- ${n.name}: ${n.amount_per_serving || '-'} (AKG: ${n.percent_daily_value || '-'})\n`;
    });
    copyToClipboard(summary, '📋 Ringkasan nutrisi disalin!');
  });

  // ═══════════════════════════════════════
  // UTILITIES
  // ═══════════════════════════════════════
  function showError(msg) {
    emptyState.style.display = 'none';
    resultsContainer.classList.add('active');
    const warningBox = document.getElementById('warningBanner');
    warningBox.className = 'alert-banner error';
    warningBox.style.display = 'flex';
    warningBox.querySelector('.alert-icon').textContent = '❌';
    warningBox.querySelector('.alert-text').textContent = msg;

    // Reset details
    document.getElementById('metricEngine').textContent = 'N/A';
    document.getElementById('metricOcrConf').textContent = 'N/A';
    document.getElementById('metricDetConf').textContent = 'N/A';
    document.getElementById('nutrientsTableBody').innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--rose-400); padding: 24px;">Gagal mengekstrak data nutrisi.</td></tr>`;
  }

  function copyToClipboard(text, message) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(message);
    }).catch(() => {
      showToast('Gagal menyalin');
    });
  }

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 2800);
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
});
