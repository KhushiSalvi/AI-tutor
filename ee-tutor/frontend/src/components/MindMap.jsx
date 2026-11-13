import { useState, useRef, useEffect } from "react";
import { Download, ZoomIn, ZoomOut, RotateCcw } from "./Icons.jsx";

// Calculate tree layout coordinates
function layoutTree(rootNode, collapsedMap) {
  let nextY = 40;
  const nodes = [];
  const links = [];

  function traverse(node, depth, parentPos = null) {
    if (!node || !node.label) return null;
    const nodeId = `${depth}-${node.label}`;
    const isCollapsed = !!collapsedMap[nodeId];

    const current = {
      id: nodeId,
      label: node.label,
      depth,
      hasChildren: Boolean(node.children && node.children.length > 0),
      isCollapsed,
      x: depth * 200 + 70,
      y: 0,
    };

    if (parentPos) {
      links.push({
        source: parentPos,
        target: current,
        id: `${parentPos.id}->${current.id}`,
      });
    }

    if (current.hasChildren && !isCollapsed) {
      const childPositions = [];
      for (const child of node.children) {
        const cPos = traverse(child, depth + 1, current);
        if (cPos) childPositions.push(cPos);
      }
      if (childPositions.length > 0) {
        current.y = (childPositions[0].y + childPositions[childPositions.length - 1].y) / 2;
      } else {
        current.y = nextY;
        nextY += 56;
      }
    } else {
      current.y = nextY;
      nextY += 56;
    }

    nodes.push(current);
    return current;
  }

  traverse(rootNode, 0);
  return { nodes, links, height: Math.max(nextY + 40, 240), width: 750 };
}

export default function MindMap({ data, onNodeClick }) {
  const [collapsed, setCollapsed] = useState({});
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const svgRef = useRef(null);

  if (!data || !data.label) return null;

  const { nodes, links, height, width } = layoutTree(data, collapsed);

  const toggleCollapse = (nodeId) => {
    setCollapsed((prev) => ({ ...prev, [nodeId]: !prev[nodeId] }));
  };

  const handleMouseDown = (e) => {
    setDragging(true);
    setStartPos({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e) => {
    if (!dragging) return;
    setOffset({ x: e.clientX - startPos.x, y: e.clientY - startPos.y });
  };

  const handleMouseUp = () => setDragging(false);

  const downloadPNG = () => {
    if (!svgRef.current) return;
    const svgElement = svgRef.current;
    const svgString = new XMLSerializer().serializeToString(svgElement);
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    const img = new Image();
    const svgBlob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);

    img.onload = () => {
      canvas.width = width * 2;
      canvas.height = height * 2;
      ctx.fillStyle = "#16161a";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      const a = document.createElement("a");
      a.download = `mindmap-${(data.label || "concept").replace(/\s+/g, "_")}.png`;
      a.href = canvas.toDataURL("image/png");
      a.click();
    };
    img.src = url;
  };

  const colors = ["#7aa2f7", "#7dcfff", "#bb9af7", "#ff9e64"];

  return (
    <div className="mindmap-container" style={{ margin: "16px 0", background: "#16161a", borderRadius: "12px", border: "1px solid #282832", overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 16px", borderBottom: "1px solid #282832" }}>
        <div style={{ fontSize: "14px", fontWeight: 600, color: "#c0caf5", display: "flex", alignItems: "center", gap: "6px" }}>
          <span>🧠 Concept Mind Map</span>
        </div>
        <div style={{ display: "flex", gap: "6px" }}>
          <button className="act" title="Zoom In" onClick={() => setScale((s) => Math.min(s + 0.15, 2))}>
            <ZoomIn size={14} />
          </button>
          <button className="act" title="Zoom Out" onClick={() => setScale((s) => Math.max(s - 0.15, 0.5))}>
            <ZoomOut size={14} />
          </button>
          <button className="act" title="Reset View" onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }}>
            <RotateCcw size={14} />
          </button>
          <button className="act" title="Download PNG" onClick={downloadPNG}>
            <Download size={14} />
          </button>
        </div>
      </div>

      <div
        style={{ width: "100%", height: "260px", overflow: "auto", cursor: dragging ? "grabbing" : "grab", position: "relative" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <svg
          ref={svgRef}
          width={Math.max(width, 700)}
          height={height}
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
            transformOrigin: "0 0",
            transition: dragging ? "none" : "transform 0.15s ease-out",
          }}
        >
          {/* Connecting Curved Links */}
          {links.map((link) => {
            const dx = (link.target.x - link.source.x) / 2;
            const pathData = `M ${link.source.x + 40} ${link.source.y} C ${link.source.x + 40 + dx} ${link.source.y}, ${link.target.x - dx} ${link.target.y}, ${link.target.x - 20} ${link.target.y}`;
            return (
              <path
                key={link.id}
                d={pathData}
                fill="none"
                stroke="#3b4261"
                strokeWidth="2"
                strokeDasharray={link.target.depth === 2 ? "4 2" : "none"}
              />
            );
          })}

          {/* Tree Nodes */}
          {nodes.map((node) => {
            const col = colors[node.depth % colors.length];
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                style={{ cursor: node.hasChildren ? "pointer" : "default" }}
                onClick={() => node.hasChildren ? toggleCollapse(node.id) : onNodeClick?.(node.label)}
              >
                <rect
                  x="-20"
                  y="-16"
                  width={node.label.length * 8 + 48}
                  height="32"
                  rx="16"
                  fill="#1f2335"
                  stroke={col}
                  strokeWidth={node.depth === 0 ? "2.5" : "1.5"}
                />
                <circle cx="-6" cy="0" r="5" fill={col} />
                <text
                  x="6"
                  y="4"
                  fill="#c0caf5"
                  fontSize="12px"
                  fontWeight={node.depth === 0 ? "700" : "500"}
                  fontFamily="system-ui, sans-serif"
                >
                  {node.label}
                </text>
                {node.hasChildren && (
                  <text x={node.label.length * 8 + 16} y="4" fill="#7aa2f7" fontSize="11px" fontWeight="bold">
                    {node.isCollapsed ? "+" : "−"}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <div style={{ padding: "6px 14px", fontSize: "11px", color: "#565f89", borderTop: "1px solid #282832" }}>
        Tip: Drag to pan, scroll to navigate, click parent nodes to collapse/expand branches.
      </div>
    </div>
  );
}
