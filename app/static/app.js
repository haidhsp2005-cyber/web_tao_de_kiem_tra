const { createApp, ref, reactive, computed, onMounted, nextTick } = Vue;

createApp({
  setup() {
    const form = reactive({
      subject: "Toán học",
      grade: "12",
      duration_minutes: 50,
      school_name: "SỞ GD&ĐT ... - TRƯỜNG THPT ...",
      academic_year: "NĂM HỌC 2026 - 2027",
      num_part1: 20,
      num_part2: 4,
      num_part3: 6,
      num_essay: 0,
      topic: "",
      prompt: "",
      file_content: ""
    });

    const inputMode = ref("prompt");
    const isCustomSubject = ref(false);
    const handleSubjectSelectChange = () => {
      if (form.subject === "__other__") {
        isCustomSubject.value = true;
        form.subject = "";
      }
    };
    const uploadedFileName = ref("");
    const extractedPreview = ref("");
    const fileInput = ref(null);

    // Chuẩn Công văn 7991/BGDĐT-GDTrH Ma trận & Bản đặc tả
    const matrixSpec = ref(null);
    const matrixUploadedFileName = ref("");
    const isAnalyzingMatrix = ref(false);
    const matrixError = ref("");
    const matrixFileInput = ref(null);
    const showRawMatrixModal = ref(false);

    const isExtracting = ref(false);
    const isGenerating = ref(false);
    const isShuffling = ref(false);
    const generateError = ref("");

    const exam = ref(null);
    const variants = ref([]);
    const activeVariantCode = ref("101");
    const gradingMatrix = ref(null);
    const viewSection = ref("questions");

    const shuffleConfig = reactive({
      num_variants: 4,
      start_code: 101,
      shuffle_part1_options: true,
      shuffle_part2_subitems: true
    });

    const showApiModal = ref(false);
    const apiProvider = ref("gemini");
    const apiKey = ref(localStorage.getItem("eduexam_api_key") || "");
    const modelName = ref(localStorage.getItem("eduexam_model_name") || "auto");

    const serverConfig = reactive({
      has_env_keys: false,
      gemini_keys_count: 0,
      gemini_masked_keys: [],
      openai_keys_count: 0,
      openai_masked_keys: []
    });

    const fetchServerConfig = async () => {
      try {
        const res = await fetch("/api/config");
        if (res.ok) {
          const data = await res.json();
          Object.assign(serverConfig, data);
        }
      } catch (err) {
        console.log("Could not load /api/config", err);
      }
    };

    const parsedKeys = computed(() => {
      if (!apiKey.value) return [];
      return apiKey.value
        .split(/[\r\n,;]+/)
        .map(k => k.trim().replace(/['"`]/g, ""))
        .filter(k => k.length > 5);
    });

    const parsedKeyCount = computed(() => parsedKeys.value.length);

    const effectiveKeyCount = computed(() => {
      if (parsedKeyCount.value > 0) return parsedKeyCount.value;
      if (apiProvider.value === "gemini") return serverConfig.gemini_keys_count || 0;
      if (apiProvider.value === "openai") return serverConfig.openai_keys_count || 0;
      return 0;
    });

    const isUsingEnvKeys = computed(() => {
      return parsedKeyCount.value === 0 && (
        (apiProvider.value === "gemini" && serverConfig.gemini_keys_count > 0) ||
        (apiProvider.value === "openai" && serverConfig.openai_keys_count > 0)
      );
    });

    const toast = reactive({
      show: false,
      message: "",
      type: "info"
    });

    const showToast = (message, type = "info") => {
      toast.message = message;
      toast.type = type;
      toast.show = true;
      setTimeout(() => { toast.show = false; }, 4000);
    };

    const saveApiKey = () => {
      if (apiKey.value.trim()) {
        localStorage.setItem("eduexam_api_key", apiKey.value.trim());
      } else {
        localStorage.removeItem("eduexam_api_key");
      }
      localStorage.setItem("eduexam_model_name", modelName.value);
      showApiModal.value = false;
      const count = parsedKeyCount.value;
      if (count > 1) {
        showToast(`Đã lưu cấu hình AI! Đang bật chế độ xoay vòng ${count} API Keys.`);
      } else if (count === 1) {
        showToast("Đã lưu cấu hình AI thành công (1 API Key)!");
      } else if (isUsingEnvKeys.value) {
        showToast(`Đang sử dụng ${effectiveKeyCount.value} API Keys tự động từ file .env!`);
      } else {
        showToast("Đã lưu cấu hình AI (Sử dụng đề mẫu chuẩn)!");
      }
    };

    const isSavingEnv = ref(false);

    const saveToEnvFile = async () => {
      const keysList = parsedKeys.value;
      if (!keysList.length) {
        showToast("Vui lòng nhập ít nhất 1 API Key vào khung trên để lưu vào file .env!", "error");
        return;
      }
      isSavingEnv.value = true;
      try {
        const res = await fetch("/api/save-env", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: apiProvider.value,
            keys: keysList
          })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Lỗi ghi file .env");
        }
        const updatedConfig = await res.json();
        Object.assign(serverConfig, updatedConfig);
        // Clear local storage key so server .env key takes precedence cleanly
        apiKey.value = "";
        localStorage.removeItem("eduexam_api_key");
        localStorage.setItem("eduexam_model_name", modelName.value);
        showToast(`Đã lưu thành công ${keysList.length} API Keys vào file .env cấu trúc chuẩn!`);
        showApiModal.value = false;
      } catch (err) {
        showToast("Lỗi lưu file .env: " + err.message, "error");
      } finally {
        isSavingEnv.value = false;
      }
    };

    const loadFromEnvFile = async () => {
      try {
        const res = await fetch("/api/config?include_raw=true");
        if (res.ok) {
          const data = await res.json();
          Object.assign(serverConfig, data);
          const envKeys = apiProvider.value === "openai" ? data.openai_keys : data.gemini_keys;
          if (envKeys && envKeys.length) {
            apiKey.value = envKeys.join("\n");
            showToast(`Đã nạp ${envKeys.length} API Keys từ file .env vào khung chỉnh sửa!`);
          } else {
            showToast("File .env hiện chưa có khóa nào!", "error");
          }
        }
      } catch (err) {
        showToast("Không thể tải từ file .env: " + err.message, "error");
      }
    };

    // Current active exam to display
    const activeExam = computed(() => {
      if (!variants.value.length) return exam.value;
      const found = variants.value.find(v => v.code === activeVariantCode.value);
      return found ? found.exam : exam.value;
    });

    // Helper function to calculate exam scoring matching backend
    const calculateScoring = (numP1, numP2, numP3, numP4, p4PointsTotal = 0) => {
      let s1 = 0, s2 = 0, s3 = 0, s4 = 0;
      let q1 = 0, q2 = 0, q3 = 0, q4 = 0;

      // Phần I: Trắc nghiệm khách quan luôn cố định 0.25 đ/câu
      if (numP1 > 0) {
        s1 = Math.round(numP1 * 0.25 * 100) / 100;
        q1 = 0.25;
      }

      // Phần II: Trắc nghiệm Đúng / Sai luôn cố định 1.0 đ/câu
      if (numP2 > 0) {
        s2 = Math.round(numP2 * 1.0 * 100) / 100;
        q2 = 1.0;
      }

      const fixedPoints = Math.round((s1 + s2) * 100) / 100;
      const remaining = Math.max(0, Math.round((10.0 - fixedPoints) * 100) / 100);

      // Phần III và Phần IV điều chỉnh theo 2 phần trên
      if (numP3 === 0 && numP4 === 0) {
        if (numP1 > 0 && numP2 === 0 && numP1 === 40) {
          s1 = 10.0;
          q1 = 0.25;
        }
      } else if (numP4 === 0 && numP3 > 0) {
        s3 = remaining;
        q3 = Math.round((s3 / numP3) * 100) / 100;
      } else if (numP3 === 0 && numP4 > 0) {
        s4 = remaining;
        q4 = Math.round((s4 / numP4) * 100) / 100;
      } else {
        if (p4PointsTotal > 0) {
          s4 = Math.min(p4PointsTotal, Math.max(0.5, remaining - 0.25 * numP3));
        } else {
          const w3 = numP3 * 1.0;
          const w4 = numP4 * 4.0;
          s4 = Math.round(((remaining * w4) / (w3 + w4)) * 10) / 10;
          if (s4 >= remaining) {
            s4 = remaining >= 1.0 ? Math.round((remaining - 0.5) * 10) / 10 : Math.round((remaining / 2) * 10) / 10;
          }
          if (s4 <= 0) {
            s4 = remaining >= 1.0 ? 0.5 : Math.round((remaining / 2) * 10) / 10;
          }
        }
        s3 = Math.round((remaining - s4) * 100) / 100;
        q3 = Math.round((s3 / numP3) * 100) / 100;
        q4 = Math.round((s4 / numP4) * 100) / 100;
      }

      // Đảm bảo tổng tuyệt đối 10.0 điểm, bù trừ vào Phần III hoặc Phần IV trước
      const sumAll = Math.round((s1 + s2 + s3 + s4) * 100) / 100;
      const diff = Math.round((10.0 - sumAll) * 100) / 100;
      if (diff !== 0) {
        if (s3 > 0) {
          s3 = Math.round((s3 + diff) * 100) / 100;
          q3 = Math.round((s3 / numP3) * 100) / 100;
        } else if (s4 > 0) {
          s4 = Math.round((s4 + diff) * 100) / 100;
          q4 = Math.round((s4 / numP4) * 100) / 100;
        } else if (s2 > 0) {
          s2 = Math.round((s2 + diff) * 100) / 100;
        } else if (s1 > 0) {
          s1 = Math.round((s1 + diff) * 100) / 100;
        }
      }

      const fmt = (v) => v.toFixed(1).replace('.', ',');
      const fmtPerQ = (v) => (Math.round(v * 100) / 100).toFixed(2).replace('.', ',');

      return {
        total_points: "10,0",
        part1_points: fmt(s1),
        part1_per_q: fmtPerQ(q1),
        part2_points: fmt(s2),
        part2_per_q: fmtPerQ(q2),
        part3_points: fmt(s3),
        part3_per_q: fmtPerQ(q3),
        part4_points: fmt(s4),
        part4_per_q: fmtPerQ(q4)
      };
    };

    const formScoring = computed(() => {
      const p1 = parseInt(form.num_part1) || 0;
      const p2 = parseInt(form.num_part2) || 0;
      const p3 = parseInt(form.num_part3) || 0;
      const p4 = parseInt(form.num_essay) || 0;
      return calculateScoring(p1, p2, p3, p4);
    });

    const activeScoring = computed(() => {
      if (activeExam.value && activeExam.value.scoring) {
        return activeExam.value.scoring;
      }
      if (activeExam.value) {
        const p1 = (activeExam.value.part1_mcq || []).length;
        const p2 = (activeExam.value.part2_tf || []).length;
        const p3 = (activeExam.value.part3_short || []).length;
        const p4 = (activeExam.value.part4_essay || []).length;
        const p4Pts = (activeExam.value.part4_essay || []).reduce((acc, q) => acc + (q.points || 1.0), 0);
        return calculateScoring(p1, p2, p3, p4, p4Pts);
      }
      return formScoring.value;
    });

    const formatPoints = (val) => {
      if (val === undefined || val === null) return "0";
      const num = typeof val === "number" ? val : parseFloat(String(val).replace(",", "."));
      if (isNaN(num)) return String(val);
      if (Math.floor(num) === num) return num.toString();
      return (Math.round(num * 100) / 100).toFixed(2).replace(/\.?0+$/, "").replace(".", ",");
    };

    const getEssayPoints = (q, idx) => {
      const essays = activeExam.value?.part4_essay || [];
      if (!essays.length) return formatPoints(q?.points || 1.0);
      
      const s4Str = activeScoring.value?.part4_points || "0";
      const totalS4 = parseFloat(String(s4Str).replace(',', '.')) || 0;
      if (totalS4 <= 0) return formatPoints(q?.points || 1.0);
      
      const n = essays.length;
      if (n === 1) return formatPoints(totalS4);
      
      const rawPoints = essays.map(item => (typeof item.points === 'number' && item.points > 0) ? item.points : 1.0);
      const allEqual = rawPoints.every(v => v === rawPoints[0]);
      
      let allocated = [];
      if (allEqual) {
        const base = Math.round((totalS4 / n) * 100) / 100;
        allocated = Array(n).fill(base);
      } else {
        const sumRaw = rawPoints.reduce((a, b) => a + b, 0);
        allocated = rawPoints.map(pts => Math.round(((pts / sumRaw) * totalS4) * 100) / 100);
      }
      
      const currentSum = Math.round(allocated.reduce((a, b) => a + b, 0) * 100) / 100;
      const diff = Math.round((totalS4 - currentSum) * 100) / 100;
      if (diff !== 0) {
        allocated[allocated.length - 1] = Math.round((allocated[allocated.length - 1] + diff) * 100) / 100;
      }
      
      const res = allocated[idx] !== undefined ? allocated[idx] : (q?.points || 1.0);
      return formatPoints(res);
    };

    const cleanEssayExplanation = (text) => {
      if (!text) return "";
      const lines = String(text).split("\n");
      const cleaned = [];
      const pointsPattern = "(?:[\\(\\[]\\s*\\d+(?:[.,]\\d+)?\\s*(?:đ|điểm|pt|pts)?\\s*[\\)\\]]|\\d+(?:[.,]\\d+)?\\s*(?:đ|điểm))";
      const stepPatternStr = "(?:bước|giai\\s*đoạn)\\s*\\d+";
      const prefixPattern = new RegExp(
        "^\\s*(?:[-*+•]|\\d+[\\.)])?\\s*" +
        "(?:" +
          stepPatternStr + "\\s*(?:" + pointsPattern + ")?" +
          "|" +
          pointsPattern + "\\s*(?:" + stepPatternStr + ")?" +
          "|" +
          pointsPattern +
          "|" +
          stepPatternStr +
        ")\\s*[:.-]*\\s*",
        "i"
      );
      const trailingPointPattern = /\s*[\(\[]\s*\d+(?:[.,]\d+)?\s*(?:đ|điểm|pt|pts)?\s*[\)\]]\s*$/i;

      for (let rawLine of lines) {
        let line = rawLine.trim();
        if (!line) continue;
        let subbed = line.replace(prefixPattern, "").replace(trailingPointPattern, "").replace(/^\s*[-*+•]\s*/, "").trim();
        if (subbed) {
          if (/^[a-zà-ỹ]/i.test(subbed)) {
            subbed = subbed.charAt(0).toUpperCase() + subbed.slice(1);
          }
          cleaned.push("- " + subbed);
        }
      }
      return cleaned.length > 0 ? cleaned.join("\n") : text;
    };

    const setActiveVariant = (code) => {
      activeVariantCode.value = code;
      nextTick(triggerKaTeX);
    };

    // KaTeX Math Rendering
    const renderMath = (text) => {
      if (!text) return "";
      if (typeof window.katex === "undefined") return escapeHtml(text);
      
      try {
        let sanitized = text;
        // 1. Normalize fragile matrix syntax into robust cases
        sanitized = sanitized.replace(/\\left\\{\s*\\begin\{(?:matrix|array)\}/g, "\\begin{cases}");
        sanitized = sanitized.replace(/\\end\{(?:matrix|array)\}\s*\\right\.?/g, "\\end{cases}");
        sanitized = sanitized.replace(/\\end\{(?:matrix|array)\}/g, "\\end{cases}");
        if (sanitized.includes("\\left\\{") && !sanitized.includes("\\right")) {
          sanitized = sanitized.replace(/\\left\\{/g, "\\{");
        }

        // 2. Heal unclosed $ if odd count
        const dollarCount = (sanitized.match(/\$/g) || []).length;
        if (dollarCount % 2 !== 0) {
          sanitized = sanitized.trim() + "$";
        }

        // Replace $$...$$ and $...$ with KaTeX rendered HTML
        return sanitized.replace(/(\$\$[\s\S]*?\$\$|\$[\s\S]*?\$)/g, (match) => {
          const isBlock = match.startsWith("$$");
          let formula = isBlock ? match.slice(2, -2) : match.slice(1, -1);

          // Extra safety inside formula
          formula = formula.replace(/\\left\\{\s*\\begin\{(?:matrix|array)\}/g, "\\begin{cases}");
          formula = formula.replace(/\\end\{(?:matrix|array)\}\s*\\right\.?/g, "\\end{cases}");
          if (formula.includes("\\begin{cases}") && !formula.includes("\\end{cases}")) {
            formula = formula.trim() + " \\end{cases}";
          }
          if (formula.includes("\\left\\{") && !formula.includes("\\right")) {
            formula = formula.trim() + " \\right.";
          }

          try {
            return window.katex.renderToString(formula, {
              displayMode: isBlock,
              throwOnError: false
            });
          } catch (e) {
            return match;
          }
        });
      } catch (err) {
        return escapeHtml(text);
      }
    };

    const escapeHtml = (str) => {
      return str.replace(/[&<>"'\/]/g, function (s) {
        return {
          "&": "&amp;", "<": "&lt;", ">": "&gt;",
          '"': "&quot;", "'": "&#39;", "/": "&#x2F;"
        }[s];
      });
    };

    const triggerKaTeX = () => {
      // KaTeX is rendered reactively through v-html="renderMath(...)"
    };

    // File Upload Handler
    const uploadFile = async (file) => {
      if (!file) return;
      uploadedFileName.value = file.name;
      isExtracting.value = true;
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch("/api/extract", {
          method: "POST",
          body: fd
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Lỗi đọc tệp");
        }
        const data = await res.json();
        extractedPreview.value = data.text;
        form.file_content = data.text;

        // Auto-detect Subject and Grade from filename and content
        const combinedText = (file.name + " " + data.text.slice(0, 3000)).toLowerCase();
        let detectedSubject = null;
        let detectedGrade = null;
        
        // Subject detection
        if (combinedText.includes("quốc phòng") || combinedText.includes("gdqp") || combinedText.includes("an ninh") || combinedText.includes("quân sự") || file.name.toLowerCase().includes("gdqp")) {
          detectedSubject = "Giáo dục Quốc phòng & An ninh";
        } else if (combinedText.includes("công nghệ") || file.name.toLowerCase().includes("cong_nghe") || file.name.toLowerCase().includes("congnghe")) {
          detectedSubject = "Công nghệ";
        } else if (combinedText.includes("tin học") || combinedText.includes("tin 10") || combinedText.includes("tin 11") || combinedText.includes("tin 12") || combinedText.includes("python") || file.name.toLowerCase().includes("tin")) {
          detectedSubject = "Tin học";
        } else if (combinedText.includes("vật lý") || combinedText.includes("vật lí") || file.name.toLowerCase().includes("ly") || file.name.toLowerCase().includes("vat_li")) {
          detectedSubject = "Vật lý";
        } else if (combinedText.includes("hóa học") || combinedText.includes("hóa") || file.name.toLowerCase().includes("hoa")) {
          detectedSubject = "Hóa học";
        } else if (combinedText.includes("sinh học") || file.name.toLowerCase().includes("sinh")) {
          detectedSubject = "Sinh học";
        } else if (combinedText.includes("lịch sử") || file.name.toLowerCase().includes("su")) {
          detectedSubject = "Lịch sử";
        } else if (combinedText.includes("địa lý") || combinedText.includes("địa lí") || file.name.toLowerCase().includes("dia")) {
          detectedSubject = "Địa lý";
        } else if (combinedText.includes("tiếng anh") || combinedText.includes("english")) {
          detectedSubject = "Tiếng Anh";
        } else if (combinedText.includes("kinh tế") || combinedText.includes("gdkt")) {
          detectedSubject = "Giáo dục kinh tế & Pháp luật";
        } else if (combinedText.includes("ngữ văn") || combinedText.includes("văn học")) {
          detectedSubject = "Ngữ văn";
        } else if (combinedText.includes("toán")) {
          detectedSubject = "Toán học";
        }
        
        // Grade detection
        for (const g of ["12", "11", "10", "9", "8", "7", "6"]) {
          const re = new RegExp(`(?:lớp|khối|k|tin|toán|lý|hóa|sinh|gdqp|tuần|tuan)\\s*${g}\\b|_${g}[_\\.]|\\b${g}\\b`, "i");
          if (re.test(file.name) || (data.text.slice(0, 1000).match(new RegExp(`(?:lớp|khối)\\s*${g}\\b`, "i")))) {
            detectedGrade = g;
            break;
          }
        }
        
        const standardList = [
          "Toán học", "Vật lý", "Hóa học", "Sinh học", "Tiếng Anh", "Lịch sử", "Địa lý",
          "Giáo dục kinh tế & Pháp luật", "Tin học", "Giáo dục Quốc phòng & An ninh", "Công nghệ", "Ngữ văn"
        ];
        
        if (detectedSubject) {
          form.subject = detectedSubject;
          isCustomSubject.value = !standardList.includes(detectedSubject);
        }
        if (detectedGrade) form.grade = detectedGrade;
        
        const cleanName = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]+/g, " ");
        if (!form.topic) {
          form.topic = cleanName;
        }
        
        if (detectedSubject && detectedGrade) {
          showToast(`Trích xuất ${data.length} ký tự. Đã nhận diện: Môn ${detectedSubject} - Lớp ${detectedGrade}!`, "info");
        } else if (detectedSubject) {
          showToast(`Trích xuất ${data.length} ký tự. Đã nhận diện: Môn ${detectedSubject}!`, "info");
        } else {
          showToast(`Trích xuất thành công ${data.length} ký tự từ file!`);
        }
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        isExtracting.value = false;
      }
    };

    const handleFileSelect = (e) => {
      const file = e.target.files[0];
      if (file) uploadFile(file);
    };

    const handleFileDrop = (e) => {
      const file = e.dataTransfer.files[0];
      if (file) uploadFile(file);
    };

    // Xử lý tải lên và phân tích Ma trận theo chuẩn Công văn 7991/BGDĐT-GDTrH
    const uploadMatrixFile = async (file) => {
      if (!file) return;
      matrixUploadedFileName.value = file.name;
      isAnalyzingMatrix.value = true;
      matrixError.value = "";
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch("/api/matrix/analyze", {
          method: "POST",
          body: fd
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Lỗi đọc file ma trận");
        }
        const data = await res.json();
        matrixSpec.value = data.matrix;
        
        // Tự động đồng bộ các thông số vào form đề thi chính
        if (data.matrix.subject) {
          form.subject = data.matrix.subject;
          const standardList = [
            "Toán học", "Vật lý", "Hóa học", "Sinh học", "Tiếng Anh", "Lịch sử", "Địa lý",
            "Giáo dục kinh tế & Pháp luật", "Tin học", "Giáo dục Quốc phòng & An ninh", "Công nghệ", "Ngữ văn"
          ];
          isCustomSubject.value = !standardList.includes(data.matrix.subject);
        }
        if (data.matrix.grade) form.grade = data.matrix.grade;
        if (data.matrix.duration_minutes) form.duration_minutes = data.matrix.duration_minutes;
        if (data.matrix.num_part1 !== undefined) form.num_part1 = data.matrix.num_part1;
        if (data.matrix.num_part2 !== undefined) form.num_part2 = data.matrix.num_part2;
        if (data.matrix.num_part3 !== undefined) form.num_part3 = data.matrix.num_part3;
        if (data.matrix.num_essay !== undefined) form.num_essay = data.matrix.num_essay;
        if (data.matrix.school_name && data.matrix.school_name.trim()) form.school_name = data.matrix.school_name;
        if (data.matrix.academic_year && data.matrix.academic_year.trim()) form.academic_year = data.matrix.academic_year;
        
        const totalQ = (data.matrix.num_part1 || 0) + (data.matrix.num_part2 || 0) + (data.matrix.num_part3 || 0) + (data.matrix.num_essay || 0);
        showToast(`Đã nhận dạng thành công ma trận môn ${data.matrix.subject} lớp ${data.matrix.grade} (${totalQ} câu hỏi)!`);
      } catch (err) {
        matrixError.value = err.message;
        showToast("Lỗi phân tích ma trận: " + err.message, "error");
      } finally {
        isAnalyzingMatrix.value = false;
      }
    };

    const handleMatrixFileSelect = (e) => {
      const file = e.target.files[0];
      if (file) uploadMatrixFile(file);
    };

    const handleMatrixFileDrop = (e) => {
      const file = e.dataTransfer.files[0];
      if (file) uploadMatrixFile(file);
    };

    const startGenerateFromMatrix = async () => {
      inputMode.value = "matrix";
      await startGenerate();
    };

    // Sync custom school name and academic year across active exam and variants
    const syncSchoolInfo = () => {
      if (exam.value) {
        if (form.school_name) exam.value.school_name = form.school_name;
        if (form.academic_year) exam.value.academic_year = form.academic_year;
      }
      if (variants.value && variants.value.length) {
        variants.value.forEach(v => {
          if (v.exam) {
            if (form.school_name) v.exam.school_name = form.school_name;
            if (form.academic_year) v.exam.academic_year = form.academic_year;
          }
        });
      }
    };

    // Load Mock Samples
    const loadSample = async (subjectKey) => {
      isGenerating.value = true;
      generateError.value = "";
      try {
        const res = await fetch(`/api/samples/${subjectKey}`);
        if (!res.ok) throw new Error("Không thể tải mẫu đề");
        const data = await res.json();
        
        // Preserve user's custom school name / year if explicitly modified
        if (form.school_name && form.school_name !== "SỞ GD&ĐT ... - TRƯỜNG THPT ...") {
          data.school_name = form.school_name;
        } else {
          form.school_name = data.school_name || "SỞ GD&ĐT ... - TRƯỜNG THPT ...";
        }
        if (form.academic_year && form.academic_year !== "NĂM HỌC 2026 - 2027") {
          data.academic_year = form.academic_year;
        } else {
          form.academic_year = data.academic_year || "NĂM HỌC 2026 - 2027";
        }

        exam.value = data;
        form.subject = data.subject;
        isCustomSubject.value = false;
        form.grade = data.grade;
        form.duration_minutes = data.duration_minutes;
        form.num_essay = data.part4_essay ? data.part4_essay.length : 0;
        showToast(`Đã nạp đề mẫu môn ${data.subject}! Đang tự động trộn 4 mã đề...`);
        await startShuffle();
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        isGenerating.value = false;
      }
    };

    // Generate Exam
    const startGenerate = async () => {
      isGenerating.value = true;
      generateError.value = "";
      try {
        const keysList = parsedKeys.value;
        const payload = {
          mode: inputMode.value,
          subject: form.subject,
          grade: form.grade,
          topic: form.topic,
          prompt: form.prompt,
          file_content: form.file_content,
          matrix_spec: inputMode.value === "matrix" ? matrixSpec.value : null,
          matrix_mode: inputMode.value === "matrix",
          num_part1: form.num_part1,
          num_part2: form.num_part2,
          num_part3: form.num_part3,
          num_essay: form.num_essay || 0,
          api_provider: apiProvider.value,
          api_key: keysList[0] || null,
          api_keys: keysList,
          model_name: modelName.value || "auto"
        };

        const res = await fetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Lỗi khởi tạo đề thi");
        }

        const data = await res.json();
        if (form.school_name) data.school_name = form.school_name;
        if (form.academic_year) data.academic_year = form.academic_year;
        exam.value = data;
        generateError.value = "";
        showToast("Tạo đề kiểm tra thành công! Đang tiến hành trộn đề...");
        await startShuffle();
      } catch (err) {
        generateError.value = err.message;
        const shortMsg = err.message.length > 80 ? err.message.slice(0, 80) + "..." : err.message;
        showToast(shortMsg, "error");
      } finally {
        isGenerating.value = false;
      }
    };

    // Shuffle Exam
    const startShuffle = async () => {
      if (!exam.value) return;
      isShuffling.value = true;
      try {
        if (form.school_name) exam.value.school_name = form.school_name;
        if (form.academic_year) exam.value.academic_year = form.academic_year;

        const payload = {
          exam: exam.value,
          num_variants: shuffleConfig.num_variants,
          start_code: shuffleConfig.start_code,
          shuffle_part1_options: shuffleConfig.shuffle_part1_options,
          shuffle_part2_subitems: shuffleConfig.shuffle_part2_subitems
        };

        const res = await fetch("/api/shuffle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Lỗi trộn đề");
        }

        const data = await res.json();
        // Sync school name and academic year across generated variants
        if (form.school_name || form.academic_year) {
          data.variants.forEach(v => {
            if (v.exam) {
              if (form.school_name) v.exam.school_name = form.school_name;
              if (form.academic_year) v.exam.academic_year = form.academic_year;
            }
          });
        }
        variants.value = data.variants;
        gradingMatrix.value = data.matrix;
        activeVariantCode.value = data.variants[0]?.code || "101";
        showToast(`Đã trộn thành công ${data.variants.length} mã đề!`);
        nextTick(triggerKaTeX);
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        isShuffling.value = false;
      }
    };

    // Helper to download blob
    const downloadBlob = (blob, filename) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    };

    // Export Single Word Docx
    const exportSingleDocx = async (code) => {
      const current = variants.value.find(v => v.code === code) || { exam: exam.value, code: code };
      showToast(`Đang xuất file Word mã đề ${code}...`);
      try {
        const res = await fetch("/api/export-docx", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exam: current.exam,
            variant_code: code,
            include_answers: true,
            include_explanations: true
          })
        });
        if (!res.ok) throw new Error("Lỗi tải file Word");
        const blob = await res.blob();
        downloadBlob(blob, `De_thi_${current.exam.subject}_Ma_${code}.docx`);
        showToast(`Tải xuống file Word mã ${code} thành công!`);
      } catch (err) {
        showToast(err.message, "error");
      }
    };

    // Export Word with Red Answers (Exam only with highlighted answers)
    const exportRedAnswersDocx = async (code) => {
      const current = variants.value.find(v => v.code === code) || { exam: exam.value, code: code };
      showToast(`Đang xuất file Word có đáp án in đỏ (Mã ${code})...`);
      try {
        const res = await fetch("/api/export-docx", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exam: current.exam,
            variant_code: code,
            include_answers: false,
            include_explanations: false,
            red_answers: true
          })
        });
        if (!res.ok) throw new Error("Lỗi tải file Word in đỏ đáp án");
        const blob = await res.blob();
        downloadBlob(blob, `De_thi_${current.exam.subject}_Ma_${code}_Dap_an_in_do.docx`);
        showToast(`Tải xuống file Word có đáp án in đỏ (Mã ${code}) thành công!`);
      } catch (err) {
        showToast(err.message, "error");
      }
    };

    // Export Master Combined Docx
    const exportMasterDocx = async () => {
      showToast("Đang xuất file Word tổng hợp...");
      try {
        const res = await fetch("/api/export-docx", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exam: exam.value,
            variant_code: "TONG_HOP",
            all_variants: variants.value,
            include_answers: true,
            include_explanations: true
          })
        });
        if (!res.ok) throw new Error("Lỗi tải file Word tổng hợp");
        const blob = await res.blob();
        downloadBlob(blob, `Tong_hop_De_va_Dap_an_${exam.value.subject}.docx`);
        showToast("Tải xuống file Word tổng hợp thành công!");
      } catch (err) {
        showToast(err.message, "error");
      }
    };

    // Export Zip All
    const exportZipAll = async () => {
      showToast("Đang đóng gói file ZIP các mã đề...");
      try {
        const res = await fetch("/api/export-zip", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exam: exam.value,
            variants: variants.value,
            include_answers: true,
            include_explanations: true
          })
        });
        if (!res.ok) throw new Error("Lỗi tải tệp ZIP");
        const blob = await res.blob();
        downloadBlob(blob, `Bo_de_thi_${exam.value.subject}_${variants.value.length}_ma_de.zip`);
        showToast("Tải xuống file ZIP thành công!");
      } catch (err) {
        showToast(err.message, "error");
      }
    };

    onMounted(() => {
      fetchServerConfig();
      // Automatically load Math sample on initial visit so the user immediately sees a live exam!
      loadSample("toan");
    });

    return {
      serverConfig,
      fetchServerConfig,
      form,
      inputMode,
      isCustomSubject,
      handleSubjectSelectChange,
      uploadedFileName,
      extractedPreview,
      fileInput,
      matrixSpec,
      matrixUploadedFileName,
      isAnalyzingMatrix,
      matrixError,
      matrixFileInput,
      showRawMatrixModal,
      handleMatrixFileSelect,
      handleMatrixFileDrop,
      startGenerateFromMatrix,
      isExtracting,
      isGenerating,
      isShuffling,
      generateError,
      exam,
      variants,
      activeVariantCode,
      activeExam,
      gradingMatrix,
      viewSection,
      shuffleConfig,
      showApiModal,
      apiProvider,
      apiKey,
      parsedKeys,
      parsedKeyCount,
      effectiveKeyCount,
      isUsingEnvKeys,
      modelName,
      toast,
      renderMath,
      setActiveVariant,
      handleFileSelect,
      handleFileDrop,
      loadSample,
      startGenerate,
      startShuffle,
      saveApiKey,
      isSavingEnv,
      saveToEnvFile,
      loadFromEnvFile,
      exportSingleDocx,
      exportRedAnswersDocx,
      exportMasterDocx,
      exportZipAll,
      syncSchoolInfo,
      calculateScoring,
      formScoring,
      activeScoring,
      getEssayPoints,
      formatPoints,
      cleanEssayExplanation
    };
  }
}).mount("#app");
