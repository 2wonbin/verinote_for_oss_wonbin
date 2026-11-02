// ---------------------------------------------------------------------------
// [STUDY-CUSTOM] HTML5 Canvas Interactive Knowledge Graph Viewer Component
// 순수 Canvas 기반의 경량 Force-Directed 지식 그래프 시각화 엔진
// ---------------------------------------------------------------------------

class KnowledgeGraphViewer {
  constructor(container, options = {}) {
    this.container = typeof container === 'string' ? document.querySelector(container) : container;
    if (!this.container) throw new Error('Graph container not found');

    this.options = Object.assign({
      width: 800,
      height: 480,
      nodeRadius: 24,
      springLength: 130,
      springCoeff: 0.04,
      repulsion: 1800,
      damping: 0.86,
      onSelectEdge: null,
      onSelectNode: null
    }, options);

    this.nodes = [];
    this.edges = [];
    this.nodeMap = new Map();

    // 뷰포트 변환 (Pan & Zoom)
    this.panX = 0;
    this.panY = 0;
    this.zoom = 1;
    this.minZoom = 0.2;
    this.maxZoom = 3.0;

    // 상호작용 상태
    this.isDragging = false;
    this.isPanning = false;
    this.draggedNode = null;
    this.hoveredNode = null;
    this.hoveredEdge = null;
    this.selectedElement = null; // { type: 'node'|'edge', data }
    this.lastMouseX = 0;
    this.lastMouseY = 0;
    this.animating = false;

    this.initDOM();
    this.bindEvents();
  }

  initDOM() {
    this.container.innerHTML = '';
    this.container.style.position = 'relative';
    this.container.style.overflow = 'hidden';
    this.container.style.background = '#fbfcf9';
    this.container.style.border = '1px solid #dfe5dc';
    this.container.style.borderRadius = '10px';
    this.container.style.boxShadow = 'inset 0 1px 3px rgba(0,0,0,0.02)';

    // Canvas
    this.canvas = document.createElement('canvas');
    this.canvas.style.display = 'block';
    this.canvas.style.width = '100%';
    this.canvas.style.height = `${this.options.height}px`;
    this.canvas.style.cursor = 'grab';
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');

    // 툴바 컨트롤
    const toolbar = document.createElement('div');
    toolbar.className = 'graph-toolbar';
    toolbar.style.position = 'absolute';
    toolbar.style.top = '12px';
    toolbar.style.right = '12px';
    toolbar.style.display = 'flex';
    toolbar.style.gap = '6px';
    toolbar.style.zIndex = '5';
    toolbar.innerHTML = `
      <button type="button" class="graph-btn" id="btn-zoom-in" title="확대" style="padding:6px 10px;font-size:12px;background:#ffffff;border:1px solid #dfe5dc;border-radius:6px;cursor:pointer;">＋</button>
      <button type="button" class="graph-btn" id="btn-zoom-out" title="축소" style="padding:6px 10px;font-size:12px;background:#ffffff;border:1px solid #dfe5dc;border-radius:6px;cursor:pointer;">－</button>
      <button type="button" class="graph-btn" id="btn-fit-view" title="화면 맞춤" style="padding:6px 10px;font-size:12px;background:#ffffff;border:1px solid #dfe5dc;border-radius:6px;cursor:pointer;">⟲ 맞춤</button>
    `;
    this.container.appendChild(toolbar);

    // 하단 인포 바 (클릭한 노드/관계 정보 및 원문 인용문 표시)
    this.infoBar = document.createElement('div');
    this.infoBar.className = 'graph-infobar';
    this.infoBar.style.display = 'none';
    this.infoBar.style.position = 'absolute';
    this.infoBar.style.bottom = '12px';
    this.infoBar.style.left = '12px';
    this.infoBar.style.right = '12px';
    this.infoBar.style.background = 'rgba(255, 255, 255, 0.94)';
    this.infoBar.style.backdropFilter = 'blur(4px)';
    this.infoBar.style.border = '1px solid #dfe5dc';
    this.infoBar.style.borderRadius = '8px';
    this.infoBar.style.padding = '10px 14px';
    this.infoBar.style.fontSize = '12px';
    this.infoBar.style.color = '#26392f';
    this.infoBar.style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)';
    this.container.appendChild(this.infoBar);

    toolbar.querySelector('#btn-zoom-in').onclick = () => this.zoomBy(1.2);
    toolbar.querySelector('#btn-zoom-out').onclick = () => this.zoomBy(0.8);
    toolbar.querySelector('#btn-fit-view').onclick = () => this.fitView();

    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width || this.options.width;
    this.height = rect.height || this.options.height;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);
    this.render();
  }

  // -------------------------------------------------------------------------
  // 데이터 로드
  // -------------------------------------------------------------------------
  setData(graphData) {
    // graphData: { rows: [[src, pred, dst], ...], facts: [...], entities: [...] }
    this.nodes = [];
    this.edges = [];
    this.nodeMap.clear();

    const rawRows = graphData.rows || [];
    const facts = graphData.facts || [];
    const factMap = new Map();
    facts.forEach(f => {
      const p = f.payload || {};
      const key = `${p.subject}|${p.predicate}|${p.object}`;
      factMap.set(key, f);
    });

    const nodeIds = new Set();
    rawRows.forEach(([s, p, o]) => {
      nodeIds.add(s);
      nodeIds.add(o);
    });

    // 노드 생성 (원형 분산 배치)
    const total = nodeIds.size;
    let idx = 0;
    const radius = Math.min(this.width, this.height) * 0.32;
    const cx = this.width / 2;
    const cy = this.height / 2;

    nodeIds.forEach(id => {
      const angle = (idx / (total || 1)) * Math.PI * 2;
      const node = {
        id,
        label: id,
        x: cx + Math.cos(angle) * (radius + (Math.random() - 0.5) * 40),
        y: cy + Math.sin(angle) * (radius + (Math.random() - 0.5) * 40),
        vx: 0,
        vy: 0,
        type: 'entity',
        radius: this.options.nodeRadius
      };
      this.nodes.push(node);
      this.nodeMap.set(id, node);
      idx++;
    });

    // 엣지 생성
    rawRows.forEach(([s, p, o]) => {
      const source = this.nodeMap.get(s);
      const target = this.nodeMap.get(o);
      if (source && target) {
        const fact = factMap.get(`${s}|${p}|${o}`);
        this.edges.push({
          source,
          target,
          label: p,
          quote: fact?.payload?.quote || null,
          factId: fact?.id || null
        });
      }
    });

    this.selectedElement = null;
    this.infoBar.style.display = 'none';
    this.fitView();
    this.startSimulation();
  }

  // -------------------------------------------------------------------------
  // 물리 시뮬레이션 (Force-Directed)
  // -------------------------------------------------------------------------
  startSimulation() {
    this.energy = 1.0;
    if (!this.animating) {
      this.animating = true;
      requestAnimationFrame(() => this.tick());
    }
  }

  tick() {
    if (!this.animating) return;

    let totalDisplacement = 0;
    const { springLength, springCoeff, repulsion, damping } = this.options;
    const cx = this.width / 2;
    const cy = this.height / 2;

    // 1. 노드 간 반발력 (Coulomb's Law)
    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const a = this.nodes[i];
        const b = this.nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distSq = dx * dx + dy * dy || 1;
        const dist = Math.sqrt(distSq);
        if (dist < 400) {
          const force = repulsion / distSq;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          if (a !== this.draggedNode) { a.vx -= fx; a.vy -= fy; }
          if (b !== this.draggedNode) { b.vx += fx; b.vy += fy; }
        }
      }
    }

    // 2. 엣지 스프링 인력 (Hooke's Law)
    this.edges.forEach(e => {
      const a = e.source;
      const b = e.target;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - springLength) * springCoeff;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      if (a !== this.draggedNode) { a.vx += fx; a.vy += fy; }
      if (b !== this.draggedNode) { b.vx -= fx; b.vy -= fy; }
    });

    // 3. 중심 중력 & 위치 갱신
    this.nodes.forEach(n => {
      if (n === this.draggedNode) return;
      // 중심 인력
      n.vx += (cx - n.x) * 0.008;
      n.vy += (cy - n.y) * 0.008;

      n.vx *= damping;
      n.vy *= damping;

      n.x += n.vx;
      n.y += n.vy;

      totalDisplacement += Math.abs(n.vx) + Math.abs(n.vy);
    });

    this.render();

    // 에너지가 낮아지면 애니메이션 루프 절전
    if (totalDisplacement < 0.2 && !this.isDragging) {
      this.animating = false;
    } else {
      requestAnimationFrame(() => this.tick());
    }
  }

  // -------------------------------------------------------------------------
  // 렌더링
  // -------------------------------------------------------------------------
  render() {
    const ctx = this.ctx;
    ctx.save();
    ctx.clearRect(0, 0, this.width, this.height);

    // 은은한 배경 점선 격자 (Dot Grid)
    this.drawBackgroundGrid(ctx);

    // 뷰포트 변환
    ctx.translate(this.panX, this.panY);
    ctx.scale(this.zoom, this.zoom);

    // 엣지 그리기
    this.edges.forEach(e => this.drawEdge(ctx, e));

    // 노드 그리기
    this.nodes.forEach(n => this.drawNode(ctx, n));

    ctx.restore();
  }

  drawBackgroundGrid(ctx) {
    const dotGap = 24 * this.zoom;
    const offsetX = (this.panX % dotGap);
    const offsetY = (this.panY % dotGap);
    ctx.fillStyle = '#e8eee5';
    for (let x = offsetX; x < this.width; x += dotGap) {
      for (let y = offsetY; y < this.height; y += dotGap) {
        ctx.fillRect(x, y, 1.5, 1.5);
      }
    }
  }

  drawEdge(ctx, edge) {
    const isHovered = this.hoveredEdge === edge;
    const isSelected = this.selectedElement?.type === 'edge' && this.selectedElement.data === edge;
    const { source, target, label } = edge;

    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;

    // 노드 외곽 좌표 계산
    const r = target.radius + 6;
    const tx = target.x - (dx / dist) * r;
    const ty = target.y - (dy / dist) * r;
    const sx = source.x + (dx / dist) * (source.radius + 4);
    const sy = source.y + (dy / dist) * (source.radius + 4);

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(tx, ty);

    ctx.strokeStyle = isSelected ? '#1b4d37' : isHovered ? '#3b6f54' : '#b2c2ad';
    ctx.lineWidth = isSelected ? 3 : isHovered ? 2.5 : 1.5;
    ctx.stroke();

    // 화살표 머리
    const arrowLen = isSelected ? 10 : 8;
    const arrowAngle = Math.PI / 7;
    const angle = Math.atan2(dy, dx);
    ctx.fillStyle = ctx.strokeStyle;
    ctx.beginPath();
    ctx.moveTo(tx, ty);
    ctx.lineTo(tx - arrowLen * Math.cos(angle - arrowAngle), ty - arrowLen * Math.sin(angle - arrowAngle));
    ctx.lineTo(tx - arrowLen * Math.cos(angle + arrowAngle), ty - arrowLen * Math.sin(angle + arrowAngle));
    ctx.closePath();
    ctx.fill();

    // 관계명 알약 라벨
    if (label) {
      const midX = (sx + tx) / 2;
      const midY = (sy + ty) / 2;
      ctx.font = '10px Inter, -apple-system, sans-serif';
      const textWidth = ctx.measureText(label).width;
      const padX = 6;
      const padY = 3;

      ctx.fillStyle = isSelected ? '#245a45' : isHovered ? '#eaf2e7' : '#ffffff';
      ctx.strokeStyle = isSelected ? '#245a45' : '#cbd8c6';
      ctx.lineWidth = 1;

      // 둥근 사각형 뱃지
      this.drawRoundRect(ctx, midX - textWidth / 2 - padX, midY - 7 - padY, textWidth + padX * 2, 14 + padY * 2, 4, true, true);

      ctx.fillStyle = isSelected ? '#ffffff' : '#49604c';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, midX, midY);
    }

    ctx.restore();
  }

  drawNode(ctx, node) {
    const isHovered = this.hoveredNode === node;
    const isSelected = this.selectedElement?.type === 'node' && this.selectedElement.data === node;
    const isConnected = this.hoveredNode && this.edges.some(e =>
      (e.source === this.hoveredNode && e.target === node) || (e.target === this.hoveredNode && e.source === node)
    );

    ctx.save();
    ctx.translate(node.x, node.y);

    // 노드 라벨 크기 측정
    ctx.font = '12px Inter, -apple-system, sans-serif';
    const textWidth = ctx.measureText(node.label).width;
    const width = Math.max(textWidth + 24, 50);
    const height = 30;
    node.width = width;
    node.height = height;

    // 그림자
    if (isHovered || isSelected) {
      ctx.shadowColor = 'rgba(36, 90, 69, 0.2)';
      ctx.shadowBlur = 12;
      ctx.shadowOffsetY = 4;
    }

    // 카드 배경
    ctx.fillStyle = isSelected ? '#d9ead4' : isHovered ? '#edf4eb' : isConnected ? '#f4f8f2' : '#ffffff';
    ctx.strokeStyle = isSelected ? '#245a45' : isHovered ? '#3b6f54' : '#ccd9c7';
    ctx.lineWidth = isSelected ? 2.5 : isHovered ? 2 : 1.2;

    this.drawRoundRect(ctx, -width / 2, -height / 2, width, height, 8, true, true);

    // 텍스트 라벨
    ctx.shadowColor = 'transparent';
    ctx.fillStyle = isSelected ? '#1b4433' : '#26392f';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(node.label, 0, 0);

    ctx.restore();
  }

  drawRoundRect(ctx, x, y, w, h, r, fill, stroke) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
    if (fill) ctx.fill();
    if (stroke) ctx.stroke();
  }

  // -------------------------------------------------------------------------
  // 이벤트 바인딩 (드래그, 줌, 호버, 클릭)
  // -------------------------------------------------------------------------
  bindEvents() {
    this.canvas.addEventListener('mousedown', e => this.onMouseDown(e));
    window.addEventListener('mousemove', e => this.onMouseMove(e));
    window.addEventListener('mouseup', e => this.onMouseUp(e));
    this.canvas.addEventListener('wheel', e => this.onWheel(e), { passive: false });
    this.canvas.addEventListener('click', e => this.onClick(e));
  }

  getCanvasPos(e) {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  }

  toWorldPos(screenX, screenY) {
    return {
      x: (screenX - this.panX) / this.zoom,
      y: (screenY - this.panY) / this.zoom
    };
  }

  findNodeAt(worldX, worldY) {
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i];
      const hw = (n.width || 50) / 2;
      const hh = (n.height || 30) / 2;
      if (worldX >= n.x - hw && worldX <= n.x + hw && worldY >= n.y - hh && worldY <= n.y + hh) {
        return n;
      }
    }
    return null;
  }

  findEdgeAt(worldX, worldY) {
    for (const e of this.edges) {
      const midX = (e.source.x + e.target.x) / 2;
      const midY = (e.source.y + e.target.y) / 2;
      const dist = Math.hypot(worldX - midX, worldY - midY);
      if (dist < 18) return e;
    }
    return null;
  }

  onMouseDown(e) {
    const pos = this.getCanvasPos(e);
    const world = this.toWorldPos(pos.x, pos.y);
    const node = this.findNodeAt(world.x, world.y);

    if (node) {
      this.isDragging = true;
      this.draggedNode = node;
      this.canvas.style.cursor = 'grabbing';
      this.startSimulation();
    } else {
      this.isPanning = true;
      this.canvas.style.cursor = 'move';
    }
    this.lastMouseX = pos.x;
    this.lastMouseY = pos.y;
  }

  onMouseMove(e) {
    const pos = this.getCanvasPos(e);
    const dx = pos.x - this.lastMouseX;
    const dy = pos.y - this.lastMouseY;

    if (this.isDragging && this.draggedNode) {
      this.draggedNode.x += dx / this.zoom;
      this.draggedNode.y += dy / this.zoom;
      this.draggedNode.vx = 0;
      this.draggedNode.vy = 0;
      this.startSimulation();
    } else if (this.isPanning) {
      this.panX += dx;
      this.panY += dy;
      this.render();
    } else {
      // Hover 체크
      const world = this.toWorldPos(pos.x, pos.y);
      const node = this.findNodeAt(world.x, world.y);
      const edge = !node ? this.findEdgeAt(world.x, world.y) : null;

      if (node !== this.hoveredNode || edge !== this.hoveredEdge) {
        this.hoveredNode = node;
        this.hoveredEdge = edge;
        this.canvas.style.cursor = (node || edge) ? 'pointer' : 'grab';
        this.render();
      }
    }

    this.lastMouseX = pos.x;
    this.lastMouseY = pos.y;
  }

  onMouseUp() {
    this.isDragging = false;
    this.isPanning = false;
    this.draggedNode = null;
    this.canvas.style.cursor = (this.hoveredNode || this.hoveredEdge) ? 'pointer' : 'grab';
  }

  onWheel(e) {
    e.preventDefault();
    const pos = this.getCanvasPos(e);
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    this.zoomAt(pos.x, pos.y, factor);
  }

  zoomAt(screenX, screenY, factor) {
    const newZoom = Math.min(Math.max(this.zoom * factor, this.minZoom), this.maxZoom);
    if (newZoom === this.zoom) return;

    this.panX = screenX - (screenX - this.panX) * (newZoom / this.zoom);
    this.panY = screenY - (screenY - this.panY) * (newZoom / this.zoom);
    this.zoom = newZoom;
    this.render();
  }

  zoomBy(factor) {
    this.zoomAt(this.width / 2, this.height / 2, factor);
  }

  fitView() {
    if (this.nodes.length === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    this.nodes.forEach(n => {
      minX = Math.min(minX, n.x - (n.width || 40));
      maxX = Math.max(maxX, n.x + (n.width || 40));
      minY = Math.min(minY, n.y - (n.height || 30));
      maxY = Math.max(maxY, n.y + (n.height || 30));
    });

    const graphWidth = maxX - minX + 80;
    const graphHeight = maxY - minY + 80;
    const scaleX = this.width / graphWidth;
    const scaleY = this.height / graphHeight;
    this.zoom = Math.min(Math.max(Math.min(scaleX, scaleY), 0.5), 1.6);

    const midX = (minX + maxX) / 2;
    const midY = (minY + maxY) / 2;
    this.panX = this.width / 2 - midX * this.zoom;
    this.panY = this.height / 2 - midY * this.zoom;
    this.render();
  }

  onClick(e) {
    const pos = this.getCanvasPos(e);
    const world = this.toWorldPos(pos.x, pos.y);
    const node = this.findNodeAt(world.x, world.y);
    const edge = !node ? this.findEdgeAt(world.x, world.y) : null;

    if (edge) {
      this.selectedElement = { type: 'edge', data: edge };
      this.showInfoBar(`<strong>관계:</strong> <code>${edge.source.label}</code> → <strong>${edge.label}</strong> → <code>${edge.target.label}</code>`
        + (edge.quote ? `<blockquote class="quote" style="margin:6px 0 0;font-size:11px;">"${edge.quote}"</blockquote>` : '')
        + (edge.factId ? `<div class="muted" style="margin-top:4px;">사실 ID: ${edge.factId}</div>` : ''));
      if (this.options.onSelectEdge) this.options.onSelectEdge(edge);
    } else if (node) {
      this.selectedElement = { type: 'node', data: node };
      const connectedEdges = this.edges.filter(ed => ed.source === node || ed.target === node);
      this.showInfoBar(`<strong>개체:</strong> <code>${node.label}</code> · 연결된 관계 <strong>${connectedEdges.length}</strong>개`);
      if (this.options.onSelectNode) this.options.onSelectNode(node);
    } else {
      this.selectedElement = null;
      this.infoBar.style.display = 'none';
    }
    this.render();
  }

  showInfoBar(html) {
    this.infoBar.innerHTML = html;
    this.infoBar.style.display = 'block';
  }
}
