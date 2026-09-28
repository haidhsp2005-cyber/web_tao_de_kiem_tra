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
        const fNameLower = (file.name || "").toLowerCase();
        const textSample = (data.text || "").slice(0, 4000);
        const textLower = textSample.toLowerCase();
        const combinedText = (fNameLower + " " + textLower);
        let detectedSubject = null;
        let detectedGrade = null;
        
        // 1. Kiểm tra tiêu đề / phần khai báo môn học rõ ràng ở đầu tài liệu hoặc tên file
        const mHeader = textSample.slice(0, 1500).match(/(?:môn|môn\s*học|phân\s*môn|bài\s*kiểm\s*tra\s*môn|đề\s*(?:thi|kiểm\s*tra)\s*môn?|ma\s*trận.*?môn)\s*[:\-–—]?\s*([^\n\r,\.;]{2,35})/i);
        if (mHeader) {
          const h = mHeader[1].toLowerCase().trim();
          if (["tin học", "tin", "informatics", "lập trình"].some(k => h.includes(k))) detectedSubject = "Tin học";
          else if (["tiếng anh", "english", "ngoại ngữ"].some(k => h.includes(k))) detectedSubject = "Tiếng Anh";
          else if (["toán học", "toán", "giải tích", "đại số", "hình học"].some(k => h.includes(k))) detectedSubject = "Toán học";
          else if (["vật lý", "vật lí", "vật li"].some(k => h.includes(k))) detectedSubject = "Vật lý";
          else if (["hóa học", "hóa"].some(k => h.includes(k))) detectedSubject = "Hóa học";
          else if (["sinh học", "sinh"].some(k => h.includes(k))) detectedSubject = "Sinh học";
          else if (["quốc phòng", "gdqp", "quân sự"].some(k => h.includes(k))) detectedSubject = "Giáo dục Quốc phòng & An ninh";
          else if (["lịch sử", "sử"].some(k => h.includes(k))) detectedSubject = "Lịch sử";
          else if (["địa lý", "địa lí", "địa li"].some(k => h.includes(k))) detectedSubject = "Địa lý";
          else if (["kinh tế", "pháp luật", "gdkt", "gdcd"].some(k => h.includes(k))) detectedSubject = "Giáo dục kinh tế & Pháp luật";
          else if (["ngữ văn", "văn học", "văn"].some(k => h.includes(k))) detectedSubject = "Ngữ văn";
          else if (["công nghệ"].some(k => h.includes(k))) detectedSubject = "Công nghệ";
        }

        // 2. Kiểm tra tên tệp (filename heuristic)
        if (!detectedSubject) {
          if (/(?:^|[^a-z0-9])(?:tin_hoc|tinhoc|tin[\s_-]*\d+|tin[\s_-]*k\d+|informatics|python|scratch|pascal)(?:[^a-z0-9]|$)/i.test(fNameLower)) {
            detectedSubject = "Tin học";
          } else if (/(?:^|[^a-z0-9])(?:tieng_anh|tienganh|english|vocab|ielts|toeic|unit[\s_-]*\d+)(?:[^a-z0-9]|$)/i.test(fNameLower)) {
            detectedSubject = "Tiếng Anh";
          } else if (/(?:^|[^a-z0-9])(?:toan|toan_hoc|toanhoc|math)(?:[^a-z0-9]|$)/i.test(fNameLower)) {
            detectedSubject = "Toán học";
          } else if (/(?:^|[^a-z0-9])(?:vat_ly|vat_li|vatly|vatli|physics)(?:[^a-z0-9]|$)/i.test(fNameLower)) {
            detectedSubject = "Vật lý";
          } else if (/(?:^|[^a-z0-9])(?:hoa_hoc|hoahoc|chemistry)(?:[^a-z0-9]|$)/i.test(fNameLower)) {
            detectedSubject = "Hóa học";
          } else if (/(?:^|[^a-z0-9])(?:sinh_hoc|sinhhoc|biology)(?:[^a-z0-9]|$)/i.test(fNameLower)) {
            detectedSubject = "Sinh học";
          } else if (/(?:^|[^a-z0-9])(?:gdqp|quoc_phong|quocphong)(?:[^a-z0-9]|$)/i.test(fNameLower)) {
            detectedSubject = "Giáo dục Quốc phòng & An ninh";
          }
        }

        // 3. Tính điểm phân loại theo nội dung chi tiết nếu chưa xác định được
        if (!detectedSubject) {
          const scores = {};

          // Tin học
          let tinScore = 0;
          const tinHigh = ['tin học', 'môn tin', 'trí tuệ nhân tạo', 'trí tuệ nhân tạo (ai)', 'machine learning', 'học máy', 'deep learning', 'mạng máy tính', 'lập trình', 'thuật toán', 'ngôn ngữ lập trình', 'cơ sở dữ liệu', 'csdl', 'hệ điều hành'];
          const tinMed = ['python', 'pascal', 'scratch', 'c++', 'bảng tính', 'excel', 'phần mềm', 'phần cứng', 'bộ nhớ ram', 'địa chỉ ip', 'an toàn số', 'an toàn mạng', 'an toàn thông tin', 'số nhị phân', 'bit', 'byte', 'trình duyệt', 'router', 'switch', 'lan', 'wan', 'tường lửa', 'mã độc', 'truy vấn sql', 'khoa học máy tính'];
          for (const k of tinHigh) { if (combinedText.includes(k)) tinScore += 10; }
          for (const k of tinMed) { if (combinedText.includes(k)) tinScore += 5; }
          if (/\b(?:ai|agi|lan|wan|cpu|ram|rom|sql|html|css)\b/i.test(combinedText)) tinScore += 6;
          if (/for\s+\w+\s+in\s+range|def\s+\w+\s*\(|print\s*\(|input\s*\(/i.test(textSample)) tinScore += 10;
          scores['Tin học'] = tinScore;

          // Tiếng Anh
          let taScore = 0;
          const taHigh = ['tiếng anh', 'english', 'ielts', 'toeic', 'toefl', 'pronunciation', 'phonetics', 'stress pattern', 'closest in meaning', 'opposite in meaning', 'reading comprehension', 'read the following passage', 'sentence transformation', 'word formation', 'cloze test'];
          for (const k of taHigh) { if (combinedText.includes(k)) taScore += 10; }
          const vocabMatches = (textSample.match(/^[a-zA-Z\s\-]+(?:\([a-zA-Z\s\.,]+\))?\s*[:\-=\/]\s*[\p{L}\s]+/gmu) || []).length;
          if (vocabMatches >= 3) taScore += vocabMatches * 4;
          if (tinScore < 8) {
            const commonEnglishWords = ['the', 'be', 'to', 'of', 'and', 'in', 'that', 'have', 'for', 'not', 'with', 'you', 'this', 'but', 'his', 'from', 'they', 'say', 'her', 'she', 'will', 'one', 'all', 'would', 'there', 'their', 'what', 'out', 'about', 'who', 'which', 'when', 'can', 'time', 'just', 'into', 'your', 'good', 'some', 'could', 'them', 'other', 'than', 'then', 'now', 'only', 'come', 'over', 'also', 'after', 'use', 'two', 'how', 'our', 'work', 'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these', 'give', 'most', 'advice', 'community', 'police', 'officer', 'garbage', 'collector', 'electrician', 'firefighter', 'suburb', 'guess', 'useful', 'lesson', 'unit'];
            const words = textLower.match(/[a-z]{2,}/g) || [];
            let enWordCount = 0;
            for (const w of words) { if (commonEnglishWords.includes(w)) enWordCount++; }
            if (words.length >= 10 && enWordCount >= 8) taScore += 8;
          }
          scores['Tiếng Anh'] = taScore;

          // Toán học
          let toanScore = 0;
          const toanWords = ['toán học', 'hàm số', 'đồ thị', 'phương trình', 'hệ phương trình', 'bất đẳng thức', 'đạo hàm', 'tích phân', 'nguyên hàm', 'hình chóp', 'tam giác vuông', 'đường tròn', 'vectơ', 'tọa độ oxyz', 'parabol', 'tiệm cận'];
          for (const k of toanWords) { if (combinedText.includes(k)) toanScore += 6; }
          scores['Toán học'] = toanScore;

          // Hóa học
          let hoaScore = 0;
          const hoaWords = ['hóa học', 'phản ứng hóa học', 'dung dịch', 'axit', 'bazơ', 'kim loại', 'phi kim', 'este', 'hiđrocacbon', 'khối lượng mol', 'nguyên tử khối', 'đồng phân', 'đồng đẳng'];
          for (const k of hoaWords) { if (combinedText.includes(k)) hoaScore += 6; }
          scores['Hóa học'] = hoaScore;

          // Vật lý
          let lyScore = 0;
          const lyWords = ['vật lý', 'vật lí', 'dao động điều hòa', 'sóng cơ', 'con lắc', 'quang học', 'thấu kính', 'điện trở', 'cường độ dòng điện', 'hiệu điện thế', 'vận tốc tức thời'];
          for (const k of lyWords) { if (combinedText.includes(k)) lyScore += 6; }
          scores['Vật lý'] = lyScore;

          // Sinh học
          let sinhScore = 0;
          const sinhWords = ['sinh học', 'di truyền', 'nhiễm sắc thể', 'tế bào', 'đột biến gen', 'quần thể', 'quần xã', 'hệ sinh thái', 'alen', 'kiểu gen', 'kiểu hình'];
          for (const k of sinhWords) { if (combinedText.includes(k)) sinhScore += 6; }
          scores['Sinh học'] = sinhScore;

          // GDQP
          let gdqpScore = 0;
          const gdqpWords = ['quốc phòng', 'an ninh', 'gdqp', 'quân đội', 'nghĩa vụ quân sự', 'chiến thuật', 'bắn súng', 'sơ cấp cứu', 'bảo vệ tổ quốc'];
          for (const k of gdqpWords) { if (combinedText.includes(k)) gdqpScore += 8; }
          scores['Giáo dục Quốc phòng & An ninh'] = gdqpScore;

          // Lịch sử, Địa lý, GD kinh tế & Pháp luật, Ngữ văn, Công nghệ
          if (['lịch sử', 'chiến dịch', 'khởi nghĩa', 'cách mạng'].some(k => combinedText.includes(k))) scores['Lịch sử'] = 6;
          if (['địa lý', 'địa lí', 'địa hình', 'khí hậu', 'sông ngòi'].some(k => combinedText.includes(k))) scores['Địa lý'] = 6;
          if (['kinh tế & pháp luật', 'kinh tế và pháp luật', 'gdkt', 'gdcd', 'pháp luật', 'hiến pháp'].some(k => combinedText.includes(k))) scores['Giáo dục kinh tế & Pháp luật'] = 8;
          if (['ngữ văn', 'văn học', 'tác phẩm', 'nhà thơ', 'nhà văn'].some(k => combinedText.includes(k))) scores['Ngữ văn'] = 6;
          if (['công nghệ', 'trồng trọt', 'chăn nuôi', 'cơ khí'].some(k => combinedText.includes(k))) scores['Công nghệ'] = 6;

          let maxVal = 0;
          let bestKey = 'Toán học';
          for (const [subj, sc] of Object.entries(scores)) {
            if (sc > maxVal) {
              maxVal = sc;
              bestKey = subj;
            }
          }
          if (maxVal > 0) detectedSubject = bestKey;
          else detectedSubject = "Toán học";
        }
        
        // 4. Nhận diện lớp/khối: Ưu tiên tiền tố định danh có ngữ cảnh
        for (const g of ["12", "11", "10", "9", "8", "7", "6", "5", "4", "3"]) {
          const reContext = new RegExp(`(?:lớp|khối\\s*lớp|khối|k|grade|unit|lop|khoi)\\s*${g}\\b|_${g}[_\\.]|(?:toan|tin|ly|hoa|sinh|anh|van|su|dia|gdqp|congnghe)\\s*${g}\\b`, "i");
          if (reContext.test(fNameLower) || reContext.test(textSample.slice(0, 2000))) {
            detectedGrade = g;
            break;
          }
        }
        if (!detectedGrade) {
          if (/(?:^|[^a-z0-9])(?:lop|khoi|k)?([3-9]|1[0-2])(?:[^a-z0-9]|$)/i.test(fNameLower)) {
            const m = fNameLower.match(/(?:^|[^a-z0-9])(?:lop|khoi|k)?([3-9]|1[0-2])(?:[^a-z0-9]|$)/i);
            if (m) detectedGrade = m[1];
          }
        }
        if (!detectedGrade && /trí tuệ nhân tạo|machine learning|học máy|đạo hàm|tích phân|oxyz/i.test(textSample)) {
          detectedGrade = "12";
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

    // Helper to safely parse JSON response and catch 502/503/504 HTML error gateways
    const parseJsonResponse = async (response, defaultMsg) => {
      if (!response.ok) {
        let msg = `${defaultMsg} (mã lỗi ${response.status})`;
        try {
          const errData = await response.json();
          if (errData && errData.detail) msg = errData.detail;
        } catch (e) {
          if (response.status === 502 || response.status === 503) {
            msg = "Máy chủ Render đang triển khai cập nhật hoặc khởi động lại (502/503). Vui lòng nhấn 'Tạo đề kiểm tra' lại sau vài giây.";
          } else if (response.status === 504) {
            msg = "Máy chủ phản hồi quá thời gian chờ (504 Gateway Timeout). Vui lòng thử lại.";
          }
        }
        throw new Error(msg);
      }
      return await response.json();
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

        const data = await parseJsonResponse(res, "Lỗi khởi tạo đề thi");
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

        const data = await parseJsonResponse(res, "Lỗi trộn đề");
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
