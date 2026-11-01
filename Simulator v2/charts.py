from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

BG, GRID, TEXT, GREEN = "#151a1d", "#30383b", "#aab8ba", "#73e0bd"

class CapitalChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(figsize=(7, 3), dpi=100, facecolor=BG)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        self.axes = self.figure.add_subplot(111)
        self.draw_empty()

    def _style(self):
        self.axes.tick_params(colors=TEXT, labelsize=8)
        for spine in self.axes.spines.values():
            spine.set_color(GRID)
        self.axes.grid(True, color=GRID, linewidth=0.6, alpha=0.8)
        self.axes.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}"))
        self.figure.tight_layout()

    def draw_empty(self):
        self.axes.clear()
        self.axes.set_facecolor(BG)
        self.axes.text(0.5, 0.5, "Добавь операции, чтобы увидеть историю баланса", color=TEXT,
                       ha="center", va="center", transform=self.axes.transAxes)
        self._style()
        self.canvas.draw_idle()

    def plot_capital(self, labels, values):
        self.axes.clear()
        self.axes.set_facecolor(BG)
        if not values:
            self.draw_empty()
            return
        x = list(range(len(values)))
        self.axes.plot(x, values, color=GREEN, linewidth=2)
        self.axes.fill_between(x, values, color=GREEN, alpha=0.10)
        self.axes.set_xticks(x)
        self.axes.set_xticklabels(labels, rotation=30, ha="right", color=TEXT, fontsize=8)
        self.axes.set_ylabel("Баланс, ₽", color=TEXT, fontsize=9)
        self._style()
        self.canvas.draw_idle()

class AllocationChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(figsize=(4, 3), dpi=100, facecolor=BG)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        self.axes = self.figure.add_subplot(111)
        self.draw_empty()

    def draw_empty(self):
        self.axes.clear()
        self.axes.set_facecolor(BG)
        self.axes.text(0.5, 0.5, "Пока нет активов", color=TEXT, ha="center", va="center",
                       transform=self.axes.transAxes)
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.canvas.draw_idle()

    def plot_allocation(self, labels, values):
        self.axes.clear()
        self.axes.set_facecolor(BG)
        positive = [(label, value) for label, value in zip(labels, values) if value > 0]
        if not positive:
            self.draw_empty()
            return
        labels, values = zip(*positive)
        wedges, _ = self.axes.pie(values, startangle=90,
                                  wedgeprops={"width": 0.42, "edgecolor": BG})
        self.axes.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.08),
                         ncol=2, frameon=False, fontsize=8, labelcolor=TEXT)
        self.axes.set_aspect("equal")
        self.figure.tight_layout()
        self.canvas.draw_idle()
