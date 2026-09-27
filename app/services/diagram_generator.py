import io
import base64
from typing import Dict, Any, Optional, Tuple, List
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def fig_to_base64(fig: plt.Figure) -> str:
    """Chuyển đổi đối tượng Matplotlib Figure sang chuỗi data URI PNG base64."""
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64_str}"

# ==============================================================================
# 1. TOÁN HỌC LỚP 12: ĐỒ THỊ HÀM SỐ & BẢNG BIẾN THIÊN
# ==============================================================================

def draw_cubic_graph(
    a: float = 1.0,
    b: float = 0.0,
    c: float = -3.0,
    d: float = 2.0,
    title: str = "Đồ thị hàm số bậc ba",
    caption: str = "Hình 1: Đồ thị hàm số bậc ba"
) -> Tuple[str, str]:
    """Vẽ đồ thị hàm số bậc ba y = ax^3 + bx^2 + cx + d."""
    fig, ax = plt.subplots(figsize=(4.6, 3.6), dpi=150)
    
    # Nghiệm đạo hàm y' = 3ax^2 + 2bx + c = 0
    delta_prime = 4 * b**2 - 12 * a * c
    x_extrema = []
    if delta_prime > 0 and a != 0:
        x1 = (-2 * b - np.sqrt(delta_prime)) / (6 * a)
        x2 = (-2 * b + np.sqrt(delta_prime)) / (6 * a)
        x_extrema = sorted([x1, x2])
    
    if x_extrema:
        x_min_plot = min(x_extrema) - 1.5
        x_max_plot = max(x_extrema) + 1.5
    else:
        x_min_plot, x_max_plot = -2.5, 2.5
        
    x = np.linspace(x_min_plot, x_max_plot, 400)
    y = a * x**3 + b * x**2 + c * x + d
    
    ax.plot(x, y, color='#1e3a8a', linewidth=2.2, label=r'$y = f(x)$')
    
    # Trục tọa độ Oxy
    ax.axhline(0, color='black', linewidth=1.1)
    ax.axvline(0, color='black', linewidth=1.1)
    
    # Đánh dấu các điểm cực trị nếu có
    for x_e in x_extrema:
        y_e = a * x_e**3 + b * x_e**2 + c * x_e + d
        ax.plot(x_e, y_e, 'ro', markersize=4.5)
        ax.plot([x_e, x_e], [0, y_e], 'r--', linewidth=0.9, alpha=0.7)
        ax.plot([0, x_e], [y_e, y_e], 'r--', linewidth=0.9, alpha=0.7)
        ax.text(x_e, -0.6 if y_e >= 0 else 0.3, f"{x_e:.1f}".rstrip('0').rstrip('.'), 
                fontsize=8.5, ha='center', color='darkred')
        ax.text(-0.3 if x_e >= 0 else 0.2, y_e, f"{y_e:.1f}".rstrip('0').rstrip('.'), 
                fontsize=8.5, va='center', color='darkred')

    # Điểm gốc O và nhãn x, y
    ax.text(-0.25, -0.35, 'O', fontsize=9.5, fontweight='bold')
    ax.text(x_max_plot - 0.2, -0.5, 'x', fontsize=10, fontstyle='italic', fontweight='bold')
    ax.text(0.15, max(y) * 0.9, 'y', fontsize=10, fontstyle='italic', fontweight='bold')
    
    ax.grid(True, linestyle=':', alpha=0.4, color='gray')
    ax.set_xlim(x_min_plot, x_max_plot)
    y_margin = (max(y) - min(y)) * 0.12 if max(y) != min(y) else 1.0
    ax.set_ylim(min(y) - y_margin, max(y) + y_margin)
    if title:
        ax.set_title(title, fontsize=10, pad=8, color='#0f172a', fontweight='bold')

    return fig_to_base64(fig), caption

def draw_rational_graph(
    a: float = 2.0,
    b: float = 1.0,
    c: float = 1.0,
    d: float = -1.0,
    title: str = "Đồ thị hàm phân thức nhất biến",
    caption: str = "Hình 2: Đồ thị hàm phân thức y = (ax+b)/(cx+d)"
) -> Tuple[str, str]:
    """Vẽ đồ thị hàm phân thức bậc nhất / bậc nhất y = (ax+b)/(cx+d)."""
    fig, ax = plt.subplots(figsize=(4.6, 3.6), dpi=150)
    
    x_asymptote = -d / c  # Tiệm cận đứng
    y_asymptote = a / c   # Tiệm cận ngang
    
    x_left = np.linspace(x_asymptote - 4.0, x_asymptote - 0.08, 250)
    x_right = np.linspace(x_asymptote + 0.08, x_asymptote + 4.0, 250)
    
    y_left = (a * x_left + b) / (c * x_left + d)
    y_right = (a * x_right + b) / (c * x_right + d)
    
    ax.plot(x_left, y_left, color='#1e3a8a', linewidth=2.2)
    ax.plot(x_right, y_right, color='#1e3a8a', linewidth=2.2)
    
    # Tiệm cận đứng và tiệm cận ngang (nét đứt màu đỏ cam)
    ax.axvline(x_asymptote, color='#dc2626', linestyle='--', linewidth=1.2, label=f'TCĐ: x = {x_asymptote:.1f}'.rstrip('0').rstrip('.'))
    ax.axhline(y_asymptote, color='#ea580c', linestyle='--', linewidth=1.2, label=f'TCN: y = {y_asymptote:.1f}'.rstrip('0').rstrip('.'))
    
    # Trục tọa độ Oxy
    ax.axhline(0, color='black', linewidth=1.1)
    ax.axvline(0, color='black', linewidth=1.1)
    
    ax.text(-0.3, -0.4, 'O', fontsize=9.5, fontweight='bold')
    ax.text(x_asymptote + 3.5, -0.6, 'x', fontsize=10, fontstyle='italic', fontweight='bold')
    ax.text(0.15, y_asymptote + 3.8, 'y', fontsize=10, fontstyle='italic', fontweight='bold')
    
    ax.set_xlim(x_asymptote - 4.5, x_asymptote + 4.5)
    ax.set_ylim(y_asymptote - 5.0, y_asymptote + 5.0)
    ax.grid(True, linestyle=':', alpha=0.4, color='gray')
    ax.legend(fontsize=8, loc='upper right')
    if title:
        ax.set_title(title, fontsize=10, pad=8, color='#0f172a', fontweight='bold')

    return fig_to_base64(fig), caption

def draw_quartic_graph(
    a: float = 1.0,
    b: float = -2.0,
    c: float = -1.0,
    title: str = "Đồ thị hàm số trùng phương",
    caption: str = "Hình 3: Đồ thị hàm số bậc bốn trùng phương"
) -> Tuple[str, str]:
    """Vẽ đồ thị hàm số bậc bốn trùng phương y = ax^4 + bx^2 + c."""
    fig, ax = plt.subplots(figsize=(4.6, 3.6), dpi=150)
    
    x = np.linspace(-2.2, 2.2, 400)
    y = a * x**4 + b * x**2 + c
    
    ax.plot(x, y, color='#1e3a8a', linewidth=2.2)
    ax.axhline(0, color='black', linewidth=1.1)
    ax.axvline(0, color='black', linewidth=1.1)
    
    # Cực trị
    if -b / (2 * a) > 0:
        x_e1 = np.sqrt(-b / (2 * a))
        x_extrema = [-x_e1, 0.0, x_e1]
    else:
        x_extrema = [0.0]
        
    for x_e in x_extrema:
        y_e = a * x_e**4 + b * x_e**2 + c
        ax.plot(x_e, y_e, 'ro', markersize=4.5)
        if x_e != 0:
            ax.plot([x_e, x_e], [0, y_e], 'r--', linewidth=0.9, alpha=0.7)
            ax.plot([0, x_e], [y_e, y_e], 'r--', linewidth=0.9, alpha=0.7)
            ax.text(x_e, -0.6 if y_e >= 0 else 0.3, f"{x_e:.1f}".rstrip('0').rstrip('.'), fontsize=8.5, ha='center', color='darkred')
            
    ax.text(-0.25, -0.35, 'O', fontsize=9.5, fontweight='bold')
    ax.text(2.0, -0.5, 'x', fontsize=10, fontstyle='italic', fontweight='bold')
    ax.text(0.15, max(y) * 0.9, 'y', fontsize=10, fontstyle='italic', fontweight='bold')
    
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(min(y) - 1.0, max(y) + 1.5)
    ax.grid(True, linestyle=':', alpha=0.4, color='gray')
    if title:
        ax.set_title(title, fontsize=10, pad=8, color='#0f172a', fontweight='bold')

    return fig_to_base64(fig), caption

def draw_variation_table(
    x_vals: Optional[List[str]] = None,
    y_prime: Optional[List[str]] = None,
    y_vals: Optional[List[str]] = None,
    title: str = "Bảng biến thiên của hàm số y = f(x)",
    caption: str = "Bảng biến thiên hàm số"
) -> Tuple[str, str]:
    """Vẽ bảng biến thiên chuẩn SGK 3 dòng (x, y', y) sắc nét bằng hình ảnh đồ họa."""
    if not x_vals:
        x_vals = [r"$-\infty$", "-1", "1", r"$+\infty$"]
    if not y_prime:
        y_prime = ["+", "0", "-", "0", "+"]
    if not y_vals:
        y_vals = [r"$-\infty$", "2", "-2", r"$+\infty$"]
        
    fig, ax = plt.subplots(figsize=(5.6, 2.2), dpi=150)
    ax.axis('off')
    
    # Khung bảng
    # Dòng 1: x (y từ 0.7 đến 1.0)
    # Dòng 2: y' (y từ 0.4 đến 0.7)
    # Dòng 3: y (y từ 0.0 đến 0.4)
    ax.plot([0, 10], [1.0, 1.0], 'k-', lw=1.2)
    ax.plot([0, 10], [0.7, 0.7], 'k-', lw=1.0)
    ax.plot([0, 10], [0.4, 0.4], 'k-', lw=1.0)
    ax.plot([0, 10], [0.0, 0.0], 'k-', lw=1.2)
    
    # Đường dọc ngăn cột nhãn
    ax.plot([1.4, 1.4], [0.0, 1.0], 'k-', lw=1.2)
    ax.plot([0.0, 0.0], [0.0, 1.0], 'k-', lw=1.2)
    ax.plot([10.0, 10.0], [0.0, 1.0], 'k-', lw=1.2)
    
    # Nhãn hàng
    ax.text(0.7, 0.85, r'$x$', fontsize=11, fontweight='bold', va='center', ha='center')
    ax.text(0.7, 0.55, r"$y'$", fontsize=11, fontweight='bold', va='center', ha='center')
    ax.text(0.7, 0.20, r'$y$', fontsize=11, fontweight='bold', va='center', ha='center')
    
    # Điền giá trị dòng x
    n_pts = len(x_vals)
    xs = np.linspace(2.2, 9.2, n_pts)
    for i, val in enumerate(x_vals):
        ax.text(xs[i], 0.85, val, fontsize=10, va='center', ha='center')
        
    # Điền dấu y'
    n_signs = len(y_prime)
    xs_signs = np.linspace(2.2, 9.2, n_signs)
    for i, s in enumerate(y_prime):
        ax.text(xs_signs[i], 0.55, s, fontsize=10, fontweight='bold' if s == '0' else 'normal',
                va='center', ha='center', color='darkblue' if s in ('+', '-') else 'black')
        
    # Mũi tên và giá trị dòng y (Cực đại đi lên, cực tiểu đi xuống)
    # Ví dụ với 4 mốc: -inf -> 2 -> -2 -> +inf
    if len(y_vals) >= 4:
        ax.text(2.2, 0.08, y_vals[0], fontsize=9.5, ha='center', va='center')
        ax.annotate('', xy=(4.3, 0.32), xytext=(2.6, 0.10), arrowprops=dict(arrowstyle="->", color="black", lw=1.2))
        ax.text(4.5, 0.34, y_vals[1], fontsize=10, fontweight='bold', ha='center', va='center', color='darkred')
        ax.annotate('', xy=(6.7, 0.10), xytext=(4.8, 0.32), arrowprops=dict(arrowstyle="->", color="black", lw=1.2))
        ax.text(6.9, 0.08, y_vals[2], fontsize=10, fontweight='bold', ha='center', va='center', color='darkblue')
        ax.annotate('', xy=(9.0, 0.32), xytext=(7.2, 0.10), arrowprops=dict(arrowstyle="->", color="black", lw=1.2))
        ax.text(9.2, 0.34, y_vals[3], fontsize=9.5, ha='center', va='center')
    else:
        for i, val in enumerate(y_vals):
            ax.text(xs[i], 0.20, val, fontsize=10, ha='center', va='center')
            
    ax.set_xlim(-0.2, 10.2)
    ax.set_ylim(-0.1, 1.1)
    
    return fig_to_base64(fig), caption


# ==============================================================================
# 2. VẬT LÝ: ĐỒ THỊ DAO ĐỘNG, SÓNG CƠ, NHIỆT ĐỘNG LỰC HỌC
# ==============================================================================

def draw_physics_oscillation(
    A: float = 4.0,
    T: float = 2.0,
    phi: float = 0.0,
    title: str = "Đồ thị li độ - thời gian của dao động điều hòa",
    caption: str = "Hình: Đồ thị dao động điều hòa x - t"
) -> Tuple[str, str]:
    """Vẽ đồ thị dao động điều hòa x(t) = A*cos(2*pi*t/T + phi)."""
    fig, ax = plt.subplots(figsize=(5.0, 3.2), dpi=150)
    
    t = np.linspace(0, 2.5 * T, 400)
    x = A * np.cos(2 * np.pi * t / T + phi)
    
    ax.plot(t, x, color='#0284c7', linewidth=2.2)
    ax.axhline(0, color='black', linewidth=1.1)
    ax.axvline(0, color='black', linewidth=1.1)
    
    # Biên độ +A và -A
    ax.axhline(A, color='gray', linestyle=':', alpha=0.6)
    ax.axhline(-A, color='gray', linestyle=':', alpha=0.6)
    ax.text(-0.15 * T, A, f"{A:g}", fontsize=9, va='center', fontweight='bold', color='darkblue')
    ax.text(-0.15 * T, -A, f"-{A:g}", fontsize=9, va='center', fontweight='bold', color='darkblue')
    
    # Các mốc thời gian chu kỳ T, 2T
    ax.plot([T, T], [0, A * np.cos(2 * np.pi + phi)], 'k--', lw=0.8, alpha=0.6)
    ax.text(T, -0.6, f"T = {T:g}s", fontsize=8.5, ha='center', color='black')
    ax.plot([2*T, 2*T], [0, A * np.cos(4 * np.pi + phi)], 'k--', lw=0.8, alpha=0.6)
    ax.text(2*T, -0.6, f"2T", fontsize=8.5, ha='center', color='black')
    
    ax.text(2.45 * T, -0.7, 't (s)', fontsize=9.5, fontstyle='italic', fontweight='bold')
    ax.text(0.05 * T, A * 1.15, 'x (cm)', fontsize=9.5, fontstyle='italic', fontweight='bold')
    
    ax.set_xlim(-0.2 * T, 2.6 * T)
    ax.set_ylim(-A * 1.35, A * 1.35)
    ax.grid(True, linestyle=':', alpha=0.4, color='gray')
    if title:
        ax.set_title(title, fontsize=10, pad=8, color='#0f172a', fontweight='bold')

    return fig_to_base64(fig), caption

def draw_thermodynamic_cycle(
    title: str = "Chu trình nhiệt động lực học trong hệ tọa độ p - V",
    caption: str = "Hình: Chu trình nhiệt động lực học p - V"
) -> Tuple[str, str]:
    """Vẽ chu trình nhiệt động học biến đổi trạng thái (1) -> (2) -> (3) -> (4) -> (1)."""
    fig, ax = plt.subplots(figsize=(4.6, 3.5), dpi=150)
    
    # 4 trạng thái: (V1, p1), (V2, p1), (V2, p2), (V1, p2)
    V1, V2 = 1.0, 3.5
    p1, p2 = 4.0, 1.5
    
    # Vẽ các đoạn thẳng có mũi tên chiều chu trình
    ax.annotate('', xy=(V2, p1), xytext=(V1, p1), arrowprops=dict(arrowstyle="->", color="#dc2626", lw=2))
    ax.annotate('', xy=(V2, p2), xytext=(V2, p1), arrowprops=dict(arrowstyle="->", color="#dc2626", lw=2))
    ax.annotate('', xy=(V1, p2), xytext=(V2, p2), arrowprops=dict(arrowstyle="->", color="#dc2626", lw=2))
    ax.annotate('', xy=(V1, p1), xytext=(V1, p2), arrowprops=dict(arrowstyle="->", color="#dc2626", lw=2))
    
    # Đánh số trạng thái (1), (2), (3), (4)
    ax.plot([V1, V2, V2, V1], [p1, p1, p2, p2], 'ko', markersize=5)
    ax.text(V1 - 0.25, p1 + 0.15, '(1)', fontsize=10, fontweight='bold', color='darkblue')
    ax.text(V2 + 0.15, p1 + 0.15, '(2)', fontsize=10, fontweight='bold', color='darkblue')
    ax.text(V2 + 0.15, p2 - 0.25, '(3)', fontsize=10, fontweight='bold', color='darkblue')
    ax.text(V1 - 0.25, p2 - 0.25, '(4)', fontsize=10, fontweight='bold', color='darkblue')
    
    # Đường gióng xuống trục
    ax.plot([V1, V1], [0, p2], 'k--', lw=0.8, alpha=0.6)
    ax.plot([V2, V2], [0, p2], 'k--', lw=0.8, alpha=0.6)
    ax.plot([0, V1], [p1, p1], 'k--', lw=0.8, alpha=0.6)
    ax.plot([0, V1], [p2, p2], 'k--', lw=0.8, alpha=0.6)
    
    ax.text(V1, -0.3, r'$V_1$', fontsize=9.5, ha='center')
    ax.text(V2, -0.3, r'$V_2$', fontsize=9.5, ha='center')
    ax.text(-0.35, p1, r'$p_1$', fontsize=9.5, va='center')
    ax.text(-0.35, p2, r'$p_2$', fontsize=9.5, va='center')
    
    ax.axhline(0, color='black', linewidth=1.1)
    ax.axvline(0, color='black', linewidth=1.1)
    ax.text(-0.25, -0.3, 'O', fontsize=9.5, fontweight='bold')
    ax.text(4.2, -0.35, r'$V\ (\text{m}^3)$', fontsize=9.5, fontweight='bold')
    ax.text(0.1, 4.6, r'$p\ (\text{Pa})$', fontsize=9.5, fontweight='bold')
    
    ax.set_xlim(-0.5, 4.8)
    ax.set_ylim(-0.5, 5.0)
    ax.grid(True, linestyle=':', alpha=0.3, color='gray')
    if title:
        ax.set_title(title, fontsize=10, pad=8, color='#0f172a', fontweight='bold')

    return fig_to_base64(fig), caption


# ==============================================================================
# 3. HÓA HỌC: ĐỒ THỊ CHUẨN ĐỘ & ĐỒ THỊ PHẢN ỨNG KẾT TỦA
# ==============================================================================

def draw_titration_curve(
    title: str = "Đường cong chuẩn độ dung dịch HCl bằng NaOH",
    caption: str = "Hình: Đồ thị chuẩn độ axit - bazơ"
) -> Tuple[str, str]:
    """Vẽ đường cong biến thiên pH trong quá trình chuẩn độ axit mạnh bằng bazơ mạnh."""
    fig, ax = plt.subplots(figsize=(4.8, 3.5), dpi=150)
    
    # Mô phỏng đường cong chuẩn độ S-curve
    V = np.linspace(0, 40, 400)
    V_eq = 20.0  # Điểm tương đương tại 20 mL
    # Công thức sigmoidal mô phỏng bước nhảy pH từ pH ~ 3 đến pH ~ 11
    pH = 7.0 + (14.0 / np.pi) * np.arctan(1.5 * (V - V_eq))
    pH = np.clip(pH, 1.0, 13.0)
    
    ax.plot(V, pH, color='#7c3aed', linewidth=2.2, label='Đường cong pH')
    ax.axhline(7.0, color='gray', linestyle='--', linewidth=0.9, alpha=0.7)
    ax.axvline(V_eq, color='gray', linestyle='--', linewidth=0.9, alpha=0.7)
    
    # Điểm tương đương
    ax.plot(V_eq, 7.0, 'ro', markersize=6)
    ax.text(V_eq + 1.2, 6.4, 'Điểm tương đương\n(pH = 7, V = 20 mL)', fontsize=8.5, color='darkred', fontweight='bold')
    
    ax.set_xlabel('Thể tích NaOH thêm vào (mL)', fontsize=9.5, fontweight='bold')
    ax.set_ylabel('Giá trị pH', fontsize=9.5, fontweight='bold')
    ax.set_xlim(0, 42)
    ax.set_ylim(0, 14.5)
    ax.set_yticks(range(0, 15, 2))
    ax.grid(True, linestyle=':', alpha=0.4, color='gray')
    if title:
        ax.set_title(title, fontsize=10, pad=8, color='#0f172a', fontweight='bold')

    return fig_to_base64(fig), caption

def draw_precipitation_graph(
    title: str = r"Đồ thị số mol kết tủa $CaCO_3$ khi sục khí $CO_2$ vào $Ca(OH)_2$",
    caption: str = "Hình: Đồ thị kết tủa theo số mol khí CO2"
) -> Tuple[str, str]:
    """Vẽ đồ thị hình tam giác kinh điển của phản ứng kết tủa và hòa tan kết tủa."""
    fig, ax = plt.subplots(figsize=(4.6, 3.2), dpi=150)
    
    # CO2 từ 0 -> a (kết tủa tăng), từ a -> 2a (kết tủa tan dần)
    a = 1.0
    x = [0, a, 2*a]
    y = [0, a, 0]
    
    ax.plot(x, y, color='#059669', linewidth=2.4)
    ax.plot([a, a], [0, a], 'k--', lw=0.9, alpha=0.7)
    ax.plot([0, a], [a, a], 'k--', lw=0.9, alpha=0.7)
    
    ax.plot(a, a, 'go', markersize=5)
    ax.text(a, a + 0.08, r'$n_{\max} = a$', fontsize=9, ha='center', color='darkgreen', fontweight='bold')
    ax.text(a, -0.12, r'$a$', fontsize=9.5, ha='center')
    ax.text(2*a, -0.12, r'$2a$', fontsize=9.5, ha='center')
    ax.text(-0.15, a, r'$a$', fontsize=9.5, va='center')
    
    ax.axhline(0, color='black', linewidth=1.1)
    ax.axvline(0, color='black', linewidth=1.1)
    ax.text(-0.12, -0.12, 'O', fontsize=9.5, fontweight='bold')
    ax.text(2.3*a, -0.15, r'$n_{CO_2}\ (\text{mol})$', fontsize=9.5, fontweight='bold')
    ax.text(0.05, 1.25*a, r'$n_{CaCO_3}\ (\text{mol})$', fontsize=9.5, fontweight='bold')
    
    ax.set_xlim(-0.2, 2.5 * a)
    ax.set_ylim(-0.2, 1.35 * a)
    ax.grid(True, linestyle=':', alpha=0.3, color='gray')
    if title:
        ax.set_title(title, fontsize=10, pad=8, color='#0f172a', fontweight='bold')

    return fig_to_base64(fig), caption


# ==============================================================================
# 4. SINH HỌC: SƠ ĐỒ PHẢ HỆ & ĐỒ THỊ QUẦN THỂ
# ==============================================================================

def draw_pedigree(
    title: str = "Sơ đồ phả hệ di truyền tính trạng bệnh qua 3 thế hệ",
    caption: str = "Hình: Phả hệ di truyền gia đình"
) -> Tuple[str, str]:
    """Vẽ sơ đồ phả hệ di truyền người: Hình vuông (Nam), Hình tròn (Nữ), Màu đen (Bị bệnh)."""
    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=150)
    ax.axis('off')
    
    # Quy ước: Nam = vuông, Nữ = tròn. Bị bệnh = tô đen, Bình thường = trắng viền đen
    # Thế hệ I: Nam 1 (Bình thường), Nữ 2 (Bị bệnh)
    # Thế hệ II: Nam 3 (Bình thường), Nữ 4 (Bình thường) kết hôn với Nam 5 (Bị bệnh)
    # Thế hệ III: Con gái 6 (Bị bệnh), Con trai 7 (Bình thường)
    
    # Nhãn thế hệ
    ax.text(0.3, 2.6, 'Thế hệ I', fontsize=9.5, fontweight='bold', color='gray')
    ax.text(0.3, 1.5, 'Thế hệ II', fontsize=9.5, fontweight='bold', color='gray')
    ax.text(0.3, 0.4, 'Thế hệ III', fontsize=9.5, fontweight='bold', color='gray')
    
    # I-1 (Nam, bình thường: hình vuông trắng)
    square_I1 = plt.Rectangle((2.0, 2.4), 0.5, 0.5, facecolor='white', edgecolor='black', lw=1.5)
    ax.add_patch(square_I1)
    ax.text(2.25, 2.2, '1', fontsize=9, ha='center')
    
    # I-2 (Nữ, bị bệnh: hình tròn đen)
    circle_I2 = plt.Circle((4.5, 2.65), 0.28, facecolor='black', edgecolor='black', lw=1.5)
    ax.add_patch(circle_I2)
    ax.text(4.5, 2.2, '2', fontsize=9, ha='center')
    
    # Đường kết hôn I: nối I-1 và I-2
    ax.plot([2.5, 4.22], [2.65, 2.65], 'k-', lw=1.2)
    # Đường con cái xuống thế hệ II
    ax.plot([3.36, 3.36], [2.65, 1.8], 'k-', lw=1.2)
    ax.plot([2.25, 4.0], [1.8, 1.8], 'k-', lw=1.2)
    
    # II-3 (Nam, bình thường: vuông trắng tại x=2.0)
    ax.plot([2.25, 2.25], [1.8, 1.65], 'k-', lw=1.2)
    sq_II3 = plt.Rectangle((2.0, 1.3), 0.5, 0.5, facecolor='white', edgecolor='black', lw=1.5)
    ax.add_patch(sq_II3)
    ax.text(2.25, 1.1, '3', fontsize=9, ha='center')
    
    # II-4 (Nữ, bình thường: tròn trắng tại x=4.0)
    ax.plot([4.0, 4.0], [1.8, 1.58], 'k-', lw=1.2)
    cir_II4 = plt.Circle((4.0, 1.55), 0.28, facecolor='white', edgecolor='black', lw=1.5)
    ax.add_patch(cir_II4)
    ax.text(4.0, 1.1, '4', fontsize=9, ha='center')
    
    # II-5 (Nam kết hôn với II-4, bị bệnh: vuông đen tại x=5.5)
    ax.plot([4.28, 5.5], [1.55, 1.55], 'k-', lw=1.2)
    sq_II5 = plt.Rectangle((5.5, 1.3), 0.5, 0.5, facecolor='black', edgecolor='black', lw=1.5)
    ax.add_patch(sq_II5)
    ax.text(5.75, 1.1, '5', fontsize=9, ha='center')
    
    # Đường con cái thế hệ III (từ cặp 4 - 5)
    ax.plot([4.89, 4.89], [1.55, 0.75], 'k-', lw=1.2)
    ax.plot([4.0, 5.75], [0.75, 0.75], 'k-', lw=1.2)
    
    # III-6 (Nữ, bị bệnh: tròn đen tại x=4.0)
    ax.plot([4.0, 4.0], [0.75, 0.48], 'k-', lw=1.2)
    cir_III6 = plt.Circle((4.0, 0.45), 0.28, facecolor='black', edgecolor='black', lw=1.5)
    ax.add_patch(cir_III6)
    ax.text(4.0, 0.0, '6', fontsize=9, ha='center')
    
    # III-7 (Nam, bình thường: vuông trắng tại x=5.75)
    ax.plot([5.75, 5.75], [0.75, 0.55], 'k-', lw=1.2)
    sq_III7 = plt.Rectangle((5.5, 0.2), 0.5, 0.5, facecolor='white', edgecolor='black', lw=1.5)
    ax.add_patch(sq_III7)
    ax.text(5.75, 0.0, '7', fontsize=9, ha='center')
    
    # Chú thích quy ước
    ax.add_patch(plt.Rectangle((7.0, 2.2), 0.35, 0.35, facecolor='white', edgecolor='black', lw=1.2))
    ax.text(7.5, 2.3, ': Nam bình thường', fontsize=8.5, va='center')
    ax.add_patch(plt.Circle((7.18, 1.8), 0.18, facecolor='white', edgecolor='black', lw=1.2))
    ax.text(7.5, 1.8, ': Nữ bình thường', fontsize=8.5, va='center')
    ax.add_patch(plt.Rectangle((7.0, 1.2), 0.35, 0.35, facecolor='black', edgecolor='black', lw=1.2))
    ax.text(7.5, 1.3, ': Nam bị bệnh', fontsize=8.5, va='center')
    ax.add_patch(plt.Circle((7.18, 0.8), 0.18, facecolor='black', edgecolor='black', lw=1.2))
    ax.text(7.5, 0.8, ': Nữ bị bệnh', fontsize=8.5, va='center')
    
    ax.set_xlim(0, 9.8)
    ax.set_ylim(-0.3, 3.1)
    if title:
        ax.set_title(title, fontsize=10, pad=8, color='#0f172a', fontweight='bold')

    return fig_to_base64(fig), caption

def draw_population_curve(
    title: str = "Đường cong tăng trưởng số lượng cá thể của quần thể",
    caption: str = "Hình: Đồ thị tăng trưởng quần thể theo hình chữ J và chữ S"
) -> Tuple[str, str]:
    """Vẽ đường cong tăng trưởng quần thể dạng chữ J (tiềm năng) và chữ S (logistic)."""
    fig, ax = plt.subplots(figsize=(4.8, 3.4), dpi=150)
    
    t = np.linspace(0, 10, 300)
    
    # Đường cong chữ J (hàm mũ): N(t) = N0 * e^(r*t)
    y_J = 0.5 * np.exp(0.45 * t)
    
    # Đường cong chữ S (logistic): N(t) = K / (1 + b * e^(-r*t))
    K = 18.0
    y_S = K / (1.0 + 35.0 * np.exp(-0.85 * t))
    
    ax.plot(t[y_J <= 24], y_J[y_J <= 24], color='#dc2626', linewidth=2.2, label='Đường cong chữ J (Lý thuyết)')
    ax.plot(t, y_S, color='#16a34a', linewidth=2.2, label='Đường cong chữ S (Thực tế)')
    
    # Giới hạn chịu đựng của môi trường K
    ax.axhline(K, color='gray', linestyle='--', linewidth=1.1)
    ax.text(1.0, K + 0.6, 'Sức chứa của môi trường (K)', fontsize=8.5, color='black', fontweight='bold')
    
    ax.axhline(0, color='black', linewidth=1.1)
    ax.axvline(0, color='black', linewidth=1.1)
    ax.text(-0.4, -0.8, 'O', fontsize=9.5, fontweight='bold')
    ax.text(10.2, -0.8, 'Thời gian (t)', fontsize=9.5, fontweight='bold')
    ax.text(0.1, 24.5, 'Số lượng cá thể (N)', fontsize=9.5, fontweight='bold')
    
    ax.set_xlim(-0.5, 11.0)
    ax.set_ylim(-1.0, 26.0)
    ax.grid(True, linestyle=':', alpha=0.3, color='gray')
    ax.legend(fontsize=8.5, loc='upper left')
    if title:
        ax.set_title(title, fontsize=10, pad=8, color='#0f172a', fontweight='bold')

    return fig_to_base64(fig), caption


# ==============================================================================
# DISPATCHER CHÍNH
# ==============================================================================

def generate_diagram(spec: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Nhận vào đặc tả spec của hình ảnh/sơ đồ và trả về (image_base64, caption).
    """
    if not spec or not isinstance(spec, dict):
        return None, None
        
    diag_type = str(spec.get("type", "")).lower().strip()
    caption = spec.get("caption", "Hình minh họa")
    title = spec.get("title", "")
    
    try:
        # Toán 12
        if diag_type in ("cubic", "cubic_graph", "ham_bac_ba"):
            return draw_cubic_graph(
                a=float(spec.get("a", 1.0)),
                b=float(spec.get("b", 0.0)),
                c=float(spec.get("c", -3.0)),
                d=float(spec.get("d", 2.0)),
                title=title or "Đồ thị hàm số y = f(x)",
                caption=caption
            )
        elif diag_type in ("rational", "rational_graph", "ham_nhat_bien"):
            return draw_rational_graph(
                a=float(spec.get("a", 2.0)),
                b=float(spec.get("b", 1.0)),
                c=float(spec.get("c", 1.0)),
                d=float(spec.get("d", -1.0)),
                title=title or "Đồ thị hàm số phân thức y = (ax+b)/(cx+d)",
                caption=caption
            )
        elif diag_type in ("quartic", "quartic_graph", "ham_trung_phuong"):
            return draw_quartic_graph(
                a=float(spec.get("a", 1.0)),
                b=float(spec.get("b", -2.0)),
                c=float(spec.get("c", -1.0)),
                title=title or "Đồ thị hàm số bậc bốn trùng phương",
                caption=caption
            )
        elif diag_type in ("variation_table", "bang_bien_thien", "bbt"):
            return draw_variation_table(
                x_vals=spec.get("x_vals"),
                y_prime=spec.get("y_prime"),
                y_vals=spec.get("y_vals"),
                title=title or "Bảng biến thiên của hàm số",
                caption=caption or "Bảng biến thiên"
            )
            
        # Vật lý
        elif diag_type in ("physics_oscillation", "dao_dong", "x_t"):
            return draw_physics_oscillation(
                A=float(spec.get("A", 4.0)),
                T=float(spec.get("T", 2.0)),
                phi=float(spec.get("phi", 0.0)),
                title=title or "Đồ thị dao động điều hòa x - t",
                caption=caption
            )
        elif diag_type in ("thermodynamic", "p_v", "nhiet_dong_luc_hoc"):
            return draw_thermodynamic_cycle(
                title=title or "Chu trình nhiệt động lực học p - V",
                caption=caption
            )
            
        # Hóa học
        elif diag_type in ("titration", "chuan_do", "ph_curve"):
            return draw_titration_curve(
                title=title or "Đường cong chuẩn độ axit - bazơ",
                caption=caption
            )
        elif diag_type in ("precipitation", "ket_tua", "co2_graph"):
            return draw_precipitation_graph(
                title=title or "Đồ thị kết tủa theo lượng chất thêm vào",
                caption=caption
            )
            
        # Sinh học
        elif diag_type in ("pedigree", "pha_he"):
            return draw_pedigree(
                title=title or "Sơ đồ phả hệ di truyền tính trạng bệnh",
                caption=caption
            )
        elif diag_type in ("population_growth", "tang_truong_quan_the"):
            return draw_population_curve(
                title=title or "Đồ thị tăng trưởng số lượng cá thể của quần thể",
                caption=caption
            )
            
    except Exception as e:
        print(f"[Diagram Generator] Lỗi khi tạo đồ thị/sơ đồ '{diag_type}': {e}")
        
    return None, None

def auto_attach_diagrams_to_exam(exam: Any) -> Any:
    """
    Tự động quét và gắn hình ảnh minh họa, đồ thị hàm số và bảng biến thiên
    vào các câu hỏi Toán 12, Vật lý, Hóa học, Sinh học nếu câu hỏi đề cập hoặc có spec diagram.
    """
    subject_lower = str(getattr(exam, "subject", "")).lower()
    
    all_sections = [
        getattr(exam, "part1_mcq", []) or [],
        getattr(exam, "part2_tf", []) or [],
        getattr(exam, "part3_short", []) or [],
        getattr(exam, "part4_essay", []) or []
    ]
    
    for sec in all_sections:
        for q in sec:
            if getattr(q, "image_base64", None):
                continue
                
            q_text = str(getattr(q, "question", "")).lower()
            
            # 1. TOÁN HỌC (Lớp 12 & THPT)
            if "toán" in subject_lower:
                if "bảng biến thiên" in q_text or "bbt" in q_text:
                    b64, cap = draw_variation_table(caption="Hình: Bảng biến thiên của hàm số")
                    q.image_base64 = b64
                    q.image_caption = cap
                elif "đồ thị" in q_text or "hình vẽ" in q_text or "đường cong" in q_text:
                    if "trùng phương" in q_text or "bậc bốn" in q_text or "x^4" in q_text:
                        b64, cap = draw_quartic_graph(caption="Hình: Đồ thị hàm số bậc bốn trùng phương")
                        q.image_base64 = b64
                        q.image_caption = cap
                    elif "phân thức" in q_text or "tiệm cận" in q_text or "cx + d" in q_text or "cx+d" in q_text:
                        b64, cap = draw_rational_graph(caption="Hình: Đồ thị hàm phân thức hữu tỉ")
                        q.image_base64 = b64
                        q.image_caption = cap
                    else:
                        b64, cap = draw_cubic_graph(caption="Hình: Đồ thị hàm số y = f(x)")
                        q.image_base64 = b64
                        q.image_caption = cap
                        
            # 2. VẬT LÝ
            elif "vật" in subject_lower or "lý" in subject_lower or "ly" in subject_lower:
                if "dao động" in q_text and ("đồ thị" in q_text or "hình" in q_text or "li độ" in q_text):
                    b64, cap = draw_physics_oscillation(caption="Hình: Đồ thị dao động điều hòa li độ - thời gian")
                    q.image_base64 = b64
                    q.image_caption = cap
                elif "chu trình" in q_text or "nhiệt động" in q_text or "p-v" in q_text or "p - v" in q_text:
                    b64, cap = draw_thermodynamic_cycle(caption="Hình: Chu trình nhiệt động lực học trong hệ p - V")
                    q.image_base64 = b64
                    q.image_caption = cap
                    
            # 3. HÓA HỌC
            elif "hóa" in subject_lower or "hoa" in subject_lower:
                if "chuẩn độ" in q_text and ("đồ thị" in q_text or "đường cong" in q_text or "ph" in q_text):
                    b64, cap = draw_titration_curve(caption="Hình: Đường cong chuẩn độ axit - bazơ")
                    q.image_base64 = b64
                    q.image_caption = cap
                elif "kết tủa" in q_text and ("đồ thị" in q_text or "co2" in q_text or "hình" in q_text):
                    b64, cap = draw_precipitation_graph(caption="Hình: Đồ thị kết tủa theo lượng chất thêm vào")
                    q.image_base64 = b64
                    q.image_caption = cap
                    
            # 4. SINH HỌC
            elif "sinh" in subject_lower:
                if "phả hệ" in q_text or "gia đình" in q_text:
                    b64, cap = draw_pedigree(caption="Hình: Sơ đồ phả hệ di truyền tính trạng bệnh")
                    q.image_base64 = b64
                    q.image_caption = cap
                elif "tăng trưởng" in q_text and "quần thể" in q_text:
                    b64, cap = draw_population_curve(caption="Hình: Đồ thị tăng trưởng số lượng cá thể quần thể")
                    q.image_base64 = b64
                    q.image_caption = cap
                    
    return exam
