from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from theme import SURFACE, LINE, MUTED, ACCENT, GOLD, PIE, TEXT

def style_axes(ax):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    for side, spine in ax.spines.items():
        spine.set_visible(side == "bottom")
        spine.set_color(LINE)
    ax.grid(True, axis="y", color=LINE, linewidth=0.6, alpha=0.7)
    ax.grid(False, axis="x")
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", " ")))

class _Chart(QWidget):
    def __init__(self, size, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(figsize=size, dpi=100, facecolor=SURFACE)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background:{SURFACE};")
        layout.addWidget(self.canvas)
        self.axes = self.figure.add_subplot(111)

    def _empty(self, text, axes_off=False):
        self.axes.clear()
        self.axes.set_facecolor(SURFACE)
        self.axes.text(0.5, 0.5, text, color=MUTED, ha="center", va="center", transform=self.axes.transAxes)
        if axes_off:
            self.axes.axis("off")
        else:
            style_axes(self.axes)
            self.axes.set_xticks([]); self.axes.set_yticks([])
        self.canvas.draw_idle()

class CapitalChart(_Chart):
    def __init__(self, parent=None):
        super().__init__((7, 3), parent)
        self.draw_empty()

    def draw_empty(self):
        self._empty("Добавь операции, чтобы увидеть историю баланса")

    def plot_capital(self, labels, values):
        if not values:
            return self.draw_empty()
        self.axes.clear()
        x = list(range(len(values)))
        self.axes.fill_between(x, values, color=ACCENT, alpha=0.10, linewidth=0)
        self.axes.plot(x, values, color=ACCENT, linewidth=1.6)
        self.axes.set_xticks(x)
        self.axes.set_xticklabels(labels, rotation=30, ha="right", color=MUTED, fontsize=8)
        self.axes.margins(x=0.04)
        style_axes(self.axes)
        self.figure.tight_layout()
        self.canvas.draw_idle()

class AllocationChart(_Chart):
    def __init__(self, parent=None):
        super().__init__((4, 3), parent)
        self.draw_empty()

    def draw_empty(self):
        self._empty("Пока нет активов", axes_off=True)

    def plot_allocation(self, labels, values):
        positive = [(l, v) for l, v in zip(labels, values) if v > 0]
        if not positive:
            return self.draw_empty()
        labels, values = zip(*positive)
        self.axes.clear()
        self.axes.set_facecolor(SURFACE)
        wedges, _ = self.axes.pie(values, startangle=90, colors=PIE[:len(values)] * 2,
                                  wedgeprops={"width": 0.45, "edgecolor": SURFACE, "linewidth": 2})
        self.axes.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=2,
                         frameon=False, fontsize=8, labelcolor=MUTED)
        self.axes.set_aspect("equal")
        self.figure.tight_layout()
        self.canvas.draw_idle()
