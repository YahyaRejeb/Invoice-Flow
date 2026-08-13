/* ==========================================================================
   STEG Facture Platform - OCR Extraction Engine Simulator
   ========================================================================== */

const OCRSimulator = {
  sampleFactures: [
    {
      id: "FACT-2026-0891",
      supplier: "STEG",
      invoice_no: "2026-STEG-77491",
      invoice_date: "2026-07-01",
      amount_excl_tax: 320.000,
      tva: 64.450,
      amount_incl_tax: 384.450,
      currency: "TND",
      kwh_consumed: 1230,
      due_date: "2026-08-25",
      is_digital: true,
      confidence: 99.4,
      boxes: {
        supplier: { top: '10%', left: '5%', width: '35%', height: '10%' },
        invoice_no: { top: '10%', left: '45%', width: '50%', height: '10%' },
        invoice_date: { top: '25%', left: '5%', width: '90%', height: '10%' },
        amount_excl_tax: { top: '42%', left: '5%', width: '90%', height: '25%' },
        amount_incl_tax: { top: '72%', left: '45%', width: '50%', height: '20%' }
      }
    },
    {
      id: "FACT-2026-0902",
      supplier: "STEG",
      invoice_no: "2026-STEG-88102",
      invoice_date: "2026-06-15",
      amount_excl_tax: 180.000,
      tva: 35.120,
      amount_incl_tax: 215.120,
      currency: "TND",
      kwh_consumed: 750,
      due_date: "2026-08-30",
      is_digital: false,
      confidence: 94.8,
      boxes: {
        supplier: { top: '10%', left: '5%', width: '35%', height: '10%' },
        invoice_no: { top: '10%', left: '45%', width: '50%', height: '10%' },
        invoice_date: { top: '25%', left: '5%', width: '90%', height: '10%' },
        amount_excl_tax: { top: '42%', left: '5%', width: '90%', height: '25%' },
        amount_incl_tax: { top: '72%', left: '45%', width: '50%', height: '20%' }
      }
    }
  ],

  async runExtraction(file, onProgress, onComplete) {
    onProgress('Uploading PDF to FastAPI endpoint...', 15);
    await new Promise(r => setTimeout(r, 600));

    onProgress('Analyzing document structure (PdfPlumber / PyMuPDF)...', 40);
    await new Promise(r => setTimeout(r, 700));

    onProgress('Preprocessing image: Grayscale, Otsu Thresholding & Deskewing...', 70);
    await new Promise(r => setTimeout(r, 800));

    onProgress('Tesseract OCR engine running on defined STEG layout regions...', 90);
    await new Promise(r => setTimeout(r, 600));

    onProgress('Extraction complete! Standardizing fields...', 100);
    await new Promise(r => setTimeout(r, 300));

    const extractedData = JSON.parse(JSON.stringify(this.sampleFactures[Math.floor(Math.random() * this.sampleFactures.length)]));
    extractedData.id = "FACT-" + Math.floor(1000 + Math.random() * 9000);
    extractedData.uploaded_at = new Date().toISOString();

    if (onComplete) onComplete(extractedData);
  },

  highlightBox(fieldKey) {
    document.querySelectorAll('.ocr-bounding-box').forEach(el => el.classList.remove('active'));
    const targetBox = document.querySelector(`.ocr-bounding-box[data-field="${fieldKey}"]`);
    if (targetBox) {
      targetBox.classList.add('active');
    }
  }
};

window.OCRSimulator = OCRSimulator;
