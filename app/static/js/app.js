/**
 * ═══════════════════════════════════════════════════════════════════════
 * SISTEM EKSTRAKSI INFORMASI NILAI GIZI : CLIENT CONTROLLER
 * Fitur: Live Camera Capture, Mobile Floating Actions, Dual Themes
 * Standar Kualitas: Anti-Slop Bebas Em Dash, Aksesibilitas Penuh
 * ═══════════════════════════════════════════════════════════════════════
 */

document.addEventListener('DOMContentLoaded', () => {
  // ─── DOM ELEMENTS ───
  // Input Switcher Tabs
  const tabUploadMode = document.getElementById('tabUploadMode');
  const tabCameraMode = document.getElementById('tabCameraMode');
  const uploadTabContent = document.getElementById('uploadTabContent');
  const cameraTabContent = document.getElementById('cameraTabContent');

  // Upload Elements
  const dropzone = document.getElementById('uploadDropzone');
  const fileInput = document.getElementById('fileInput');

  // Camera Elements
  const cameraVideo = document.getElementById('cameraVideo');
  const cameraCanvas = document.getElementById('cameraCanvas');
  const btnCapturePhoto = document.getElementById('btnCapturePhoto');
  const btnSwitchCamera = document.getElementById('btnSwitchCamera');
  const btnCloseCamera = document.getElementById('btnCloseCamera');
  const cameraLoadingOverlay = document.getElementById('cameraLoadingOverlay');
  const cameraErrorOverlay = document.getElementById('cameraErrorOverlay');
  const cameraErrorMessage = document.getElementById('cameraErrorMessage');
  const btnRetryCamera = document.getElementById('btnRetryCamera');

  // Preview Elements
  const previewContainer = document.getElementById('previewContainer');
  const previewImage = document.getElementById('previewImage');
  const previewMeta = document.getElementById('previewMeta');
  const previewSourceBadge = document.getElementById('previewSourceBadge');
  const btnRemovePreview = document.getElementById('btnRemovePreview');

  // Extraction Action Buttons
  const btnExtract = document.getElementById('btnExtract');
  const btnExtractMobile = document.getElementById('btnExtractMobile');
  const mobileFloatingBar = document.getElementById('mobileFloatingBar');
  const mobileFloatingText = document.getElementById('mobileFloatingText');

  // States
  const emptyState = document.getElementById('emptyState');
  const loadingState = document.getElementById('loadingState');
  const loadingStepIndicator = document.getElementById('loadingStepIndicator');
  const resultsContainer = document.getElementById('resultsContainer');

  // Header & Utilities
  const backendStatus = document.getElementById('backendStatus');
  const searchInput = document.getElementById('nutrientSearchInput');
  const toast = document.getElementById('toastNotification');
  const btnThemeToggle = document.getElementById('btnThemeToggle');
  const themeLabel = document.getElementById('themeLabel');

  // State Variables
  let currentFile = null;
  let currentResult = null;
  let stepTimer = null;
  let cameraStream = null;
  let currentFacingMode = 'environment'; // Default rear camera for scanning packages

  // ═══════════════════════════════════════
  // 1. THEME MANAGEMENT (LIGHT / DARK)
  // ═══════════════════════════════════════
  function initTheme() {
    const savedTheme = localStorage.getItem('nutrition_facts_theme');
    if (savedTheme === 'light' || savedTheme === 'dark') {
      applyTheme(savedTheme);
    } else {
      applyTheme('dark');
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('nutrition_facts_theme', theme);
    if (themeLabel) {
      themeLabel.textContent = theme === 'dark' ? 'Tema Gelap' : 'Tema Terang';
    }
  }

  if (btnThemeToggle) {
    btnThemeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const nextTheme = current === 'dark' ? 'light' : 'dark';
      applyTheme(nextTheme);
      showToast(`Beralih ke ${nextTheme === 'dark' ? 'Tema Gelap' : 'Tema Terang'}`);
    });
  }

  initTheme();

  // ═══════════════════════════════════════
  // 2. LIVE BACKEND STATUS MONITORING
  // ═══════════════════════════════════════
  async function checkHealth() {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        backendStatus.className = 'status-badge';
        backendStatus.innerHTML = '<span class="status-dot"></span> <span class="status-label">Backend Terhubung</span>';
      } else {
        throw new Error('Non-200');
      }
    } catch {
      backendStatus.className = 'status-badge offline';
      backendStatus.innerHTML = '<span class="status-dot"></span> <span class="status-label">Backend Terputus</span>';
    }
  }

  checkHealth();
  setInterval(checkHealth, 15000);

  // ═══════════════════════════════════════
  // 3. TAB CONTROLLER (UPLOAD VS LIVE CAMERA)
  // ═══════════════════════════════════════
  function switchTab(mode) {
    if (mode === 'camera') {
      tabCameraMode.classList.add('active');
      tabCameraMode.setAttribute('aria-selected', 'true');
      tabUploadMode.classList.remove('active');
      tabUploadMode.setAttribute('aria-selected', 'false');

      cameraTabContent.classList.add('active');
      uploadTabContent.classList.remove('active');

      startCamera();
    } else {
      tabUploadMode.classList.add('active');
      tabUploadMode.setAttribute('aria-selected', 'true');
      tabCameraMode.classList.remove('active');
      tabCameraMode.setAttribute('aria-selected', 'false');

      uploadTabContent.classList.add('active');
      cameraTabContent.classList.remove('active');

      stopCamera();
    }
  }

  if (tabUploadMode && tabCameraMode) {
    tabUploadMode.addEventListener('click', () => switchTab('upload'));
    tabCameraMode.addEventListener('click', () => switchTab('camera'));
  }

  // ═══════════════════════════════════════
  // 4. LIVE CAMERA CAPTURE CONTROLLER
  // ═══════════════════════════════════════
  async function startCamera() {
    stopCamera();
    cameraLoadingOverlay.style.display = 'flex';
    cameraErrorOverlay.style.display = 'none';

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showCameraError('Peramban tidak mendukung akses kamera langsung. Silakan gunakan metode unggah berkas.');
      return;
    }

    const constraints = {
      video: {
        facingMode: { ideal: currentFacingMode },
        width: { ideal: 1920 },
        height: { ideal: 1080 }
      },
      audio: false
    };

    try {
      cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
      cameraVideo.srcObject = cameraStream;
      
      cameraVideo.onloadedmetadata = () => {
        cameraVideo.play();
        cameraLoadingOverlay.style.display = 'none';
      };
    } catch (err) {
      console.warn('Gagal mengakses kamera dengan ideal constraints, mencoba fallback:', err);
      try {
        // Fallback with simpler constraints
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        cameraVideo.srcObject = cameraStream;
        cameraVideo.onloadedmetadata = () => {
          cameraVideo.play();
          cameraLoadingOverlay.style.display = 'none';
        };
      } catch (fallbackErr) {
        console.error('Akses kamera ditolak:', fallbackErr);
        let msg = 'Izin akses kamera tidak diberikan. Harap berikan izin akses kamera pada peramban Anda.';
        if (fallbackErr.name === 'NotFoundError' || fallbackErr.name === 'DevicesNotFoundError') {
          msg = 'Tidak ada perangkat kamera yang terdeteksi pada perangkat ini.';
        } else if (fallbackErr.name === 'NotReadableError' || fallbackErr.name === 'TrackStartError') {
          msg = 'Kamera sedang digunakan oleh aplikasi lain. Tutup aplikasi tersebut dan coba kembali.';
        }
        showCameraError(msg);
      }
    }
  }

  function stopCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      cameraStream = null;
    }
    if (cameraVideo) {
      cameraVideo.srcObject = null;
    }
    if (cameraLoadingOverlay) cameraLoadingOverlay.style.display = 'none';
  }

  function showCameraError(msg) {
    if (cameraLoadingOverlay) cameraLoadingOverlay.style.display = 'none';
    if (cameraErrorOverlay) {
      cameraErrorOverlay.style.display = 'flex';
      if (cameraErrorMessage) cameraErrorMessage.textContent = msg;
    }
  }

  // Switch between front & rear cameras
  if (btnSwitchCamera) {
    btnSwitchCamera.addEventListener('click', () => {
      currentFacingMode = currentFacingMode === 'environment' ? 'user' : 'environment';
      showToast(`Mengalihkan ke kamera ${currentFacingMode === 'environment' ? 'belakang' : 'depan'}...`);
      startCamera();
    });
  }

  // Close / stop camera and back to upload tab
  if (btnCloseCamera) {
    btnCloseCamera.addEventListener('click', () => {
      switchTab('upload');
    });
  }

  // Retry camera
  if (btnRetryCamera) {
    btnRetryCamera.addEventListener('click', () => {
      startCamera();
    });
  }

  // Shutter button (Take picture)
  if (btnCapturePhoto) {
    btnCapturePhoto.addEventListener('click', () => {
      if (!cameraStream || !cameraVideo.videoWidth) {
        showToast('Kamera belum siap');
        return;
      }

      // Haptic feedback if supported on mobile
      if (navigator.vibrate) {
        try { navigator.vibrate(40); } catch { /* Ignore */ }
      }

      // Set canvas to real video dimensions
      cameraCanvas.width = cameraVideo.videoWidth || 1280;
      cameraCanvas.height = cameraVideo.videoHeight || 960;

      const ctx = cameraCanvas.getContext('2d');
      ctx.drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);

      // Convert captured frame to Blob and File
      cameraCanvas.toBlob((blob) => {
        if (!blob) {
          showToast('Gagal memproses gambar');
          return;
        }

        const now = new Date();
        const timestamp = `${now.getHours()}${now.getMinutes()}${now.getSeconds()}`;
        const capturedFile = new File([blob], `label_kamera_${timestamp}.jpg`, { type: 'image/jpeg' });

        handleFileSelected(capturedFile, 'Kamera Langsung');
        stopCamera();
        switchTab('upload');
        showToast('Foto label berhasil dipotret');
      }, 'image/jpeg', 0.95);
    });
  }

  // ═══════════════════════════════════════
  // 5. FILE DRAG & DROP AND SELECTION
  // ═══════════════════════════════════════
  dropzone.addEventListener('click', () => fileInput.click());

  // Keyboard activation for dropzone (R-32)
  dropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

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
      handleFileSelected(files[0], 'Unggahan Berkas');
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0], 'Unggahan Berkas');
    }
  });

  // Support Ctrl+V paste image from clipboard
  window.addEventListener('paste', (e) => {
    const items = (e.clipboardData || (e.originalEvent && e.originalEvent.clipboardData))?.items;
    if (!items) return;

    for (const item of items) {
      if (item.kind === 'file' && item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) {
          handleFileSelected(file, 'Papan Klip');
          showToast('Gambar berhasil ditempel dari papan klip');
          break;
        }
      }
    }
  });

  // Global Escape key handling (R-32)
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (currentFile && !btnExtract.disabled) {
        clearPreview();
        showToast('Gambar dibatalkan');
      } else if (searchInput && searchInput.value) {
        searchInput.value = '';
        filterNutrientRows('');
      }
    }
  });

  function handleFileSelected(file, sourceLabel = 'Unggahan') {
    if (!file.type.match(/^image\/(jpeg|png|webp)$/i)) {
      alert('Format berkas tidak didukung. Harap pilih gambar JPEG, PNG, atau WebP.');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      alert('Ukuran berkas melebihi batas maksimal 10 MB.');
      return;
    }

    currentFile = file;
    const reader = new FileReader();

    reader.onload = (e) => {
      previewImage.src = e.target.result;
      const img = new Image();
      img.onload = () => {
        const sizeKb = (file.size / 1024).toFixed(1);
        previewMeta.textContent = `Resolusi: ${img.width}×${img.height} px | Nama: ${file.name || 'Foto'} | Ukuran: ${sizeKb} KB`;
        if (previewSourceBadge) previewSourceBadge.textContent = sourceLabel;
        
        previewContainer.classList.add('active');
        btnExtract.disabled = false;
        dropzone.style.display = 'none';

        // Show mobile floating action bar
        if (mobileFloatingBar) {
          mobileFloatingBar.classList.add('active');
          if (mobileFloatingText) mobileFloatingText.textContent = file.name || 'Foto siap diekstrak';
        }
      };
      img.src = e.target.result;
    };

    reader.readAsDataURL(file);
  }

  function clearPreview() {
    currentFile = null;
    fileInput.value = '';
    previewImage.src = '';
    previewContainer.classList.remove('active');
    dropzone.style.display = 'flex';
    btnExtract.disabled = true;

    if (mobileFloatingBar) {
      mobileFloatingBar.classList.remove('active');
    }
  }

  btnRemovePreview.addEventListener('click', clearPreview);

  // ═══════════════════════════════════════
  // 6. PIPELINE STAGES ANIMATION
  // ═══════════════════════════════════════
  const steps = [
    { id: 'step-detection', name: 'Tahap 1: Deteksi Area Tabel (Roboflow Vision)' },
    { id: 'step-crop', name: 'Tahap 2: Pemotongan Citra & Normalisasi (OpenCV)' },
    { id: 'step-ocr', name: 'Tahap 3: Pembacaan Teks Label (PaddleOCR)' },
    { id: 'step-llm', name: 'Tahap 4: Restrukturisasi Nilai Gizi (Gemini Flash)' }
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
          if (loadingStepIndicator) {
            loadingStepIndicator.textContent = s.name;
          }
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
  // 7. RUN EXTRACTION PIPELINE
  // ═══════════════════════════════════════
  async function executeExtraction() {
    if (!currentFile) return;

    // Set UI processing state
    btnExtract.disabled = true;
    if (btnExtractMobile) btnExtractMobile.disabled = true;
    if (mobileFloatingBar) mobileFloatingBar.classList.remove('active');

    emptyState.style.display = 'none';
    resultsContainer.classList.remove('active');
    loadingState.classList.add('active');
    startPipelineAnimation();

    // Scroll to results panel on mobile for instant visibility
    if (window.innerWidth < 1040) {
      resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

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
        showError(result.error || `HTTP ${response.status}: Proses ekstraksi tidak berhasil.`);
        return;
      }

      displayResults(result);
      showToast('Informasi nilai gizi berhasil diekstrak');

    } catch (err) {
      completePipelineAnimation();
      showError('Gagal menghubungi server backend. Pastikan layanan aplikasi berjalan dengan baik.');
      console.error(err);
    } finally {
      loadingState.classList.remove('active');
      btnExtract.disabled = false;
      if (btnExtractMobile) btnExtractMobile.disabled = false;
    }
  }

  btnExtract.addEventListener('click', executeExtraction);
  if (btnExtractMobile) {
    btnExtractMobile.addEventListener('click', executeExtraction);
  }

  // ═══════════════════════════════════════
  // 8. RENDER RESULTS STATE
  // ═══════════════════════════════════════
  function displayResults(res) {
    resultsContainer.classList.add('active');

    // Warning Banner Handling
    const warningBox = document.getElementById('warningBanner');
    if (res.warnings && res.warnings.length > 0) {
      warningBox.style.display = 'flex';
      warningBox.querySelector('.alert-text').innerHTML = res.warnings.map(w => `• ${escapeHtml(w)}`).join('<br>');
    } else {
      warningBox.style.display = 'none';
    }

    // Accuracy and Engine Metrics
    document.getElementById('metricEngine').textContent = res.ocr_engine_used || 'PaddleOCR';
    document.getElementById('metricOcrConf').textContent = res.ocr_confidence ? `${(res.ocr_confidence * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('metricDetConf').textContent = res.detection_confidence ? `${(res.detection_confidence * 100).toFixed(1)}%` : 'Citra Penuh';

    // Structured Nutrition Facts Data
    const nd = res.nutrition_data || {};
    
    // Product Name Tag
    const productTag = document.getElementById('productNameTag');
    const productNameText = document.getElementById('productNameText');
    if (nd.product_name) {
      productTag.style.display = 'inline-flex';
      if (productNameText) productNameText.textContent = nd.product_name;
    } else {
      productTag.style.display = 'none';
    }

    // Hero Nutrition Stats
    document.getElementById('valServingSize').textContent = nd.serving_size || 'N/A';
    document.getElementById('valServingsPerPkg').textContent = nd.servings_per_package || 'N/A';
    document.getElementById('valCalories').textContent = nd.calories || 'N/A';

    // Table Population
    renderNutrientsTable(nd.nutrients || []);

    // Raw OCR Text
    document.getElementById('rawOcrText').textContent = res.raw_ocr_text || '(Tidak ditemukan teks hasil ekstraksi OCR)';

    // Raw JSON Text
    document.getElementById('rawJsonText').textContent = JSON.stringify(res, null, 2);
  }

  function renderNutrientsTable(nutrients) {
    const tbody = document.getElementById('nutrientsTableBody');
    tbody.innerHTML = '';

    if (!nutrients || nutrients.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 24px;">Tidak ada rincian nutrisi yang teridentifikasi secara spesifik.</td></tr>`;
      return;
    }

    nutrients.forEach(n => {
      const tr = document.createElement('tr');
      tr.setAttribute('data-nutrient-name', (n.name || '').toLowerCase());

      // Parse Daily Value percentage for visual progress indicator
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
        <td class="nutrient-amount font-mono">${escapeHtml(n.amount_per_serving || '-')}</td>
        <td>
          <div class="akg-cell">
            <span class="akg-text font-mono">${escapeHtml(akgDisplay)}</span>
            <div class="akg-bar-track" aria-hidden="true">
              <div class="akg-bar-fill" style="width: ${akgNum}%"></div>
            </div>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ═══════════════════════════════════════
  // 9. SEARCH & FILTER NUTRIENT TABLE
  // ═══════════════════════════════════════
  function filterNutrientRows(query) {
    const q = query.toLowerCase().trim();
    const rows = document.querySelectorAll('#nutrientsTableBody tr');
    rows.forEach(row => {
      const name = row.getAttribute('data-nutrient-name') || '';
      row.style.display = name.includes(q) ? '' : 'none';
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      filterNutrientRows(e.target.value);
    });
  }

  // ═══════════════════════════════════════
  // 10. ACCORDION LOGIC & ACCESSIBILITY (R-32)
  // ═══════════════════════════════════════
  document.querySelectorAll('.accordion-header').forEach(header => {
    header.addEventListener('click', () => {
      toggleAccordion(header);
    });

    header.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleAccordion(header);
      }
    });
  });

  function toggleAccordion(header) {
    const item = header.closest('.accordion-item');
    const isExpanded = header.getAttribute('aria-expanded') === 'true';
    header.setAttribute('aria-expanded', !isExpanded);
    item.classList.toggle('open');
  }

  // ═══════════════════════════════════════
  // 11. EXPORT & CLIPBOARD ACTIONS
  // ═══════════════════════════════════════
  const btnCopyOcr = document.getElementById('btnCopyOcr');
  if (btnCopyOcr) {
    btnCopyOcr.addEventListener('click', () => {
      const text = document.getElementById('rawOcrText').textContent;
      copyToClipboard(text, 'Teks hasil OCR berhasil disalin');
    });
  }

  const btnCopyJson = document.getElementById('btnCopyJson');
  if (btnCopyJson) {
    btnCopyJson.addEventListener('click', () => {
      const text = document.getElementById('rawJsonText').textContent;
      copyToClipboard(text, 'Data JSON berhasil disalin');
    });
  }

  const btnDownloadJson = document.getElementById('btnDownloadJson');
  if (btnDownloadJson) {
    btnDownloadJson.addEventListener('click', () => {
      if (!currentResult) return;
      const blob = new Blob([JSON.stringify(currentResult, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `nutrition_facts_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('Berkas JSON berhasil diunduh');
    });
  }

  const btnCopySummary = document.getElementById('btnCopySummary');
  if (btnCopySummary) {
    btnCopySummary.addEventListener('click', () => {
      if (!currentResult || !currentResult.nutrition_data) return;
      const nd = currentResult.nutrition_data;
      let summary = `RINGKASAN INFORMASI NILAI GIZI\n`;
      if (nd.product_name) summary += `Nama Produk: ${nd.product_name}\n`;
      if (nd.serving_size) summary += `Takaran Saji: ${nd.serving_size}\n`;
      if (nd.servings_per_package) summary += `Sajian per Kemasan: ${nd.servings_per_package}\n`;
      if (nd.calories) summary += `Kalori (Energi Total): ${nd.calories}\n`;
      summary += `\nRINCIAN KANDUNGAN GIZI:\n`;
      (nd.nutrients || []).forEach(n => {
        summary += `- ${n.name}: ${n.amount_per_serving || '-'} (% AKG: ${n.percent_daily_value || '-'})\n`;
      });
      copyToClipboard(summary, 'Ringkasan nutrisi disalin ke papan klip');
    });
  }

  // ═══════════════════════════════════════
  // 12. ERROR & FEEDBACK UTILITIES
  // ═══════════════════════════════════════
  function showError(msg) {
    emptyState.style.display = 'none';
    resultsContainer.classList.add('active');
    const warningBox = document.getElementById('warningBanner');
    warningBox.className = 'alert-banner error';
    warningBox.style.display = 'flex';
    warningBox.querySelector('.alert-title').textContent = 'Kegagalan Proses Ekstraksi';
    warningBox.querySelector('.alert-text').textContent = msg;

    document.getElementById('metricEngine').textContent = 'N/A';
    document.getElementById('metricOcrConf').textContent = 'N/A';
    document.getElementById('metricDetConf').textContent = 'N/A';
    document.getElementById('nutrientsTableBody').innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--rose-500); padding: 24px;">Tidak dapat mengekstrak data nutrisi dari berkas ini.</td></tr>`;
  }

  function copyToClipboard(text, message) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(message);
    }).catch(() => {
      showToast('Gagal menyalin data');
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
