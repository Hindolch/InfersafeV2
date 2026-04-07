from manim import *


BG = "#08121C"
CARD = "#102234"
TEXT = "#EAF4FF"
MUTED = "#9CB7CC"
ACCENT = "#47C0FF"
GREEN = "#5BD68C"
YELLOW = "#F2C14E"
RED = "#FF6B6B"


class InfersafeV2Explainer(Scene):
    def construct(self) -> None:
        self.camera.background_color = BG
        self.intro_section()
        self.architecture_section()
        self.request_flow_section()
        self.benchmark_section()
        self.edge_case_section()
        self.constraints_section()
        self.outro_section()

    def intro_section(self) -> None:
        title = Text("InfersafeV2", font_size=44, color=TEXT, weight=BOLD)
        subtitle = Text(
            "A gateway-first LLM inference system",
            font_size=24,
            color=ACCENT,
        ).next_to(title, DOWN, buff=0.2)
        stack = Text(
            "FastAPI  •  vLLM  •  HAProxy  •  Prometheus  •  Grafana",
            font_size=22,
            color=MUTED,
        ).next_to(subtitle, DOWN, buff=0.35)

        badge = RoundedRectangle(
            corner_radius=0.2,
            width=5.8,
            height=0.7,
            stroke_color=GREEN,
            fill_color=CARD,
            fill_opacity=0.95,
        ).next_to(stack, DOWN, buff=0.5)
        badge_text = Text(
            "Validated on a GTX 1650 with a quantized model",
            font_size=20,
            color=GREEN,
        ).move_to(badge)

        self.play(FadeIn(title, shift=UP * 0.2), FadeIn(subtitle), FadeIn(stack))
        self.play(DrawBorderThenFill(badge), FadeIn(badge_text))
        self.wait(1.2)
        self.play(FadeOut(VGroup(title, subtitle, stack, badge, badge_text)))

    def architecture_section(self) -> None:
        title = self.section_title("1. Architecture")

        client = self.node("Client", 1.8, 0.9, ACCENT)
        gateway = self.node("Gateway", 2.2, 1.0, GREEN)
        lb = self.node("HAProxy", 2.2, 1.0, YELLOW)
        vllm = self.node("vLLM\nAWQ model", 2.6, 1.2, RED)
        metrics = self.node("Prometheus\nGrafana", 2.8, 1.2, ACCENT)

        top_nodes = VGroup(client, gateway, lb, vllm).arrange(RIGHT, buff=0.85).move_to(UP * 0.1)
        metrics.move_to(DOWN * 2.1)

        arrows = VGroup(
            Arrow(client.get_right(), gateway.get_left(), buff=0.15, color=TEXT),
            Arrow(gateway.get_right(), lb.get_left(), buff=0.15, color=TEXT),
            Arrow(lb.get_right(), vllm.get_left(), buff=0.15, color=TEXT),
            Arrow(gateway.get_bottom(), metrics.get_top() + LEFT * 0.9, buff=0.18, color=MUTED),
            Arrow(lb.get_bottom(), metrics.get_top() + RIGHT * 0.2, buff=0.18, color=MUTED),
        )

        caption = Text(
            "Policy and observability live in the gateway. Model execution lives in vLLM.",
            font_size=20,
            color=MUTED,
        ).to_edge(DOWN, buff=0.55)

        self.play(FadeIn(title))
        self.play(LaggedStart(*[DrawBorderThenFill(m) for m in [client, gateway, lb, vllm, metrics]], lag_ratio=0.15))
        self.play(LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.12))
        self.play(FadeIn(caption))
        self.wait(1.5)
        self.play(FadeOut(VGroup(title, client, gateway, lb, vllm, metrics, arrows, caption)))

    def request_flow_section(self) -> None:
        title = self.section_title("2. Request Lifecycle")

        # Left column: fixed-width cards, positioned in the left half
        CARD_W = 4.8
        steps = VGroup(
            self.flow_card_w("1. Validate", "payload size, token budget, JSON depth", GREEN, CARD_W),
            self.flow_card_w("2. Protect", "queue caps and concurrency limits", YELLOW, CARD_W),
            self.flow_card_w("3. Proxy", "forward request to the backend", ACCENT, CARD_W),
            self.flow_card_w("4. Stream", "record TTFT and TBT while tokens arrive", RED, CARD_W),
        ).arrange(DOWN, buff=0.22)
        # Place cards so their right edge is at x=-0.3 (leaves room for right panel)
        steps.align_to(LEFT * 6.8, LEFT).shift(RIGHT * 0.35)

        # Right panel: fixed width, sits in the right half with a clear gap
        right_panel = RoundedRectangle(
            corner_radius=0.22,
            width=4.5,
            height=4.2,
            stroke_color=ACCENT,
            fill_color=CARD,
            fill_opacity=0.95,
        )
        right_panel.align_to(RIGHT * 6.8, RIGHT).shift(LEFT * 0.35)
        right_panel.move_to(right_panel.get_center() * RIGHT + DOWN * 0.15 * UP)

        right_title = Text("Gateway outcomes", font_size=22, color=TEXT, weight=BOLD).move_to(
            right_panel.get_top() + DOWN * 0.42
        )
        bullets = VGroup(
            self.fit_text(Text("Structured 400s for overflow\nand bad payloads", font_size=16, color=TEXT), 3.8),
            self.fit_text(Text("Structured 503s for queue overload", font_size=16, color=TEXT), 3.8),
            self.fit_text(Text("Streaming path records live\ntiming metrics", font_size=16, color=TEXT), 3.8),
            self.fit_text(Text("Client disconnects can stop\nupstream work", font_size=16, color=TEXT), 3.8),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.28).next_to(right_title, DOWN, buff=0.28)
        bullets.align_to(right_panel, LEFT).shift(RIGHT * 0.32)

        # Dot travels only inside the left steps column
        request_dot = Dot(color=ACCENT, radius=0.09).move_to(steps[0].get_left() + LEFT * 0.45)
        path = VMobject(color=ACCENT).set_points_as_corners(
            [
                request_dot.get_center(),
                steps[0].get_left() + LEFT * 0.05,
                steps[0].get_right() + RIGHT * 0.05,
                steps[1].get_left() + LEFT * 0.05,
                steps[1].get_right() + RIGHT * 0.05,
                steps[2].get_left() + LEFT * 0.05,
                steps[2].get_right() + RIGHT * 0.05,
                steps[3].get_left() + LEFT * 0.05,
                steps[3].get_right() + RIGHT * 0.25,
            ]
        )

        self.play(FadeIn(title), LaggedStart(*[DrawBorderThenFill(s) for s in steps], lag_ratio=0.12))
        self.play(DrawBorderThenFill(right_panel), FadeIn(right_title), LaggedStart(*[FadeIn(b, shift=RIGHT * 0.15) for b in bullets], lag_ratio=0.12))
        self.play(MoveAlongPath(request_dot, path), run_time=3.0, rate_func=linear)
        self.wait(1.0)
        self.play(FadeOut(VGroup(title, steps, request_dot, right_panel, right_title, bullets)))

    def benchmark_section(self) -> None:
        title = self.section_title("3. Benchmarks")

        # Panels sit in the upper half of the frame
        left = self.metric_panel(
            "Sync throughput",
            [
                "Concurrency 1  ->  1.11 req/s",
                "Concurrency 2  ->  2.10 req/s",
                "Concurrency 4  ->  3.81 req/s",
            ],
            GREEN,
        ).move_to(LEFT * 3.3 + UP * 1.7)

        right = self.metric_panel(
            "Streaming timing",
            [
                "TTFT p50 at c=1  ->  220 ms",
                "TTFT p50 at c=4  ->  363 ms",
                "TBT p95 range    ->  158 to 167 ms",
                "TBT p99 range    ->  168 to 175 ms",
            ],
            ACCENT,
        ).move_to(RIGHT * 3.1 + UP * 1.7)

        # Graph lives clearly below the panels
        graph_axes = Axes(
            x_range=[0, 4, 1],
            y_range=[0, 4.5, 1],
            x_length=4.4,
            y_length=2.0,
            axis_config={"color": MUTED, "include_ticks": False},
        ).move_to(DOWN * 1.55 + LEFT * 0.5)

        labels = VGroup(
            Text("Concurrency", font_size=18, color=MUTED).next_to(graph_axes, DOWN, buff=0.12),
            Text("Throughput", font_size=18, color=MUTED).next_to(graph_axes, LEFT, buff=0.12).rotate(PI / 2),
        )
        points = [graph_axes.c2p(x, y) for x, y in [(1, 1.11), (2, 2.10), (3, 3.81)]]
        line = VMobject(color=GREEN).set_points_as_corners(points)
        dots = VGroup(*[Dot(p, color=GREEN, radius=0.07) for p in points])

        note = self.fit_text(Text(
            "Real numbers from the live quantized run, not placeholders.",
            font_size=16,
            color=YELLOW,
        ), 6.6)
        note.to_edge(DOWN, buff=0.3)

        self.play(FadeIn(title))
        self.play(DrawBorderThenFill(left), DrawBorderThenFill(right))
        self.play(Create(graph_axes), FadeIn(labels))
        self.play(Create(line), LaggedStart(*[GrowFromCenter(d) for d in dots], lag_ratio=0.15))
        self.play(FadeIn(note))
        self.wait(1.5)
        self.play(FadeOut(VGroup(title, left, right, graph_axes, labels, line, dots, note)))

    def edge_case_section(self) -> None:
        title = self.section_title("4. Edge Cases")

        table = VGroup(
            self.status_row("Context overflow", "PASS", GREEN),
            self.status_row("Thundering herd overload", "PASS", GREEN),
            self.status_row("Adversarial payloads", "PASS", GREEN),
            self.status_row("Mid-stream failure", "PARTIAL", YELLOW),
            self.status_row("Mixed GPU pressure", "PENDING", RED),
        ).arrange(DOWN, buff=0.18).move_to(UP * 0.1)

        footer = Text(
            "The key choice: prove what worked, and document the rest honestly.",
            font_size=22,
            color=TEXT,
        ).to_edge(DOWN, buff=0.5)

        self.play(FadeIn(title), LaggedStart(*[FadeIn(r, shift=UP * 0.1) for r in table], lag_ratio=0.1))
        self.play(FadeIn(footer))
        self.wait(1.3)
        self.play(FadeOut(VGroup(title, table, footer)))

    def constraints_section(self) -> None:
        title = self.section_title("5. Hardware Reality")

        left = self.metric_panel(
            "Host limits",
            [
                "GPU: GTX 1650",
                "VRAM: 4 GB",
                "Windows + Docker Desktop + WSL",
            ],
            RED,
        ).move_to(LEFT * 3.2)

        right = self.metric_panel(
            "What tuning changed",
            [
                "AWQ model instead of full precision",
                "MAX_MODEL_LEN: 4096 -> 2048",
                "GPU_MEMORY_UTILIZATION: 0.85 -> 0.55",
                "MAX_NUM_SEQS: 4",
            ],
            GREEN,
        ).move_to(RIGHT * 3.2)

        center_text = Text(
            "The project mattered because the serving path became real, measurable, and explainable.",
            font_size=24,
            color=TEXT,
        ).to_edge(DOWN, buff=0.55)

        self.play(FadeIn(title), DrawBorderThenFill(left), DrawBorderThenFill(right))
        self.play(FadeIn(center_text))
        self.wait(1.4)
        self.play(FadeOut(VGroup(title, left, right, center_text)))

    def outro_section(self) -> None:
        title = Text("InfersafeV2", font_size=40, color=TEXT, weight=BOLD).to_edge(UP, buff=0.8)
        body = VGroup(
            Text("A real LLM inference pipeline with streaming,", font_size=26, color=TEXT),
            Text("validation, observability, benchmarking,", font_size=26, color=TEXT),
            Text("and honest hardware-aware engineering.", font_size=26, color=TEXT),
        ).arrange(DOWN, buff=0.18).move_to(UP * 0.1)

        

        self.play(FadeIn(title), LaggedStart(*[FadeIn(line, shift=UP * 0.12) for line in body], lag_ratio=0.15))
        self.wait(2)

    def section_title(self, text: str) -> VGroup:
        title = Text(text, font_size=34, color=TEXT, weight=BOLD).to_edge(UP, buff=0.45)
        underline = Line(title.get_left(), title.get_right(), color=ACCENT, stroke_width=3).next_to(title, DOWN, buff=0.14)
        return VGroup(title, underline)

    def node(self, label: str, width: float, height: float, color: str) -> VGroup:
        box = RoundedRectangle(
            corner_radius=0.18,
            width=width,
            height=height,
            stroke_color=color,
            fill_color=CARD,
            fill_opacity=0.96,
        )
        if "\n" in label:
            text = Paragraph(*label.split("\n"), alignment="center", font_size=22, color=TEXT, line_spacing=0.75)
        else:
            text = Text(label, font_size=22, color=TEXT)
        self.fit_text(text, width - 0.35, height - 0.22)
        text.move_to(box)
        return VGroup(box, text)

    def flow_card(self, title: str, subtitle: str, color: str) -> VGroup:
        return self.flow_card_w(title, subtitle, color, 5.2)

    def flow_card_w(self, title: str, subtitle: str, color: str, width: float) -> VGroup:
        card = RoundedRectangle(
            corner_radius=0.18,
            width=width,
            height=1.1,
            stroke_color=color,
            fill_color=CARD,
            fill_opacity=0.96,
        )
        heading = self.fit_text(Text(title, font_size=22, color=TEXT, weight=BOLD), card.width - 0.6, 0.28)
        sub = self.fit_text(Text(subtitle, font_size=16, color=MUTED), card.width - 0.6, 0.23)
        content = VGroup(heading, sub).arrange(DOWN, aligned_edge=LEFT, buff=0.08)
        content.move_to(card)
        content.shift(LEFT * (card.width / 2 - content.width / 2 - 0.3))
        return VGroup(card, content)

    def metric_panel(self, heading: str, lines: list[str], color: str) -> VGroup:
        panel = RoundedRectangle(
            corner_radius=0.18,
            width=5.1,
            height=2.6,
            stroke_color=color,
            fill_color=CARD,
            fill_opacity=0.96,
        )
        title = self.fit_text(Text(heading, font_size=24, color=TEXT, weight=BOLD), panel.width - 0.5, 0.3)
        title.move_to(panel.get_top() + DOWN * 0.35)
        bullets = VGroup(*[self.fit_text(Text(line, font_size=18, color=TEXT), panel.width - 0.6, 0.24) for line in lines]).arrange(
            DOWN, aligned_edge=LEFT, buff=0.18
        )
        bullets.next_to(title, DOWN, buff=0.28)
        bullets.align_to(panel, LEFT).shift(RIGHT * 0.28)
        return VGroup(panel, title, bullets)

    def status_row(self, label: str, status: str, color: str) -> VGroup:
        row = RoundedRectangle(
            corner_radius=0.14,
            width=9.8,
            height=0.8,
            stroke_color=color,
            fill_color=CARD,
            fill_opacity=0.95,
        )
        left = self.fit_text(Text(label, font_size=22, color=TEXT), row.width - 2.5, 0.28)
        left.align_to(row, LEFT).shift(RIGHT * 0.3)
        badge = RoundedRectangle(
            corner_radius=0.12,
            width=1.7,
            height=0.45,
            stroke_color=color,
            fill_color=color,
            fill_opacity=0.18,
        ).align_to(row, RIGHT).shift(LEFT * 0.35)
        badge_text = Text(status, font_size=18, color=color, weight=BOLD).move_to(badge)
        return VGroup(row, left, badge, badge_text)

    def fit_text(self, mob: Mobject, max_width: float, max_height: float | None = None) -> Mobject:
        if mob.width > max_width:
            mob.scale_to_fit_width(max_width)
        if max_height is not None and mob.height > max_height:
            mob.scale_to_fit_height(max_height)
        return mob