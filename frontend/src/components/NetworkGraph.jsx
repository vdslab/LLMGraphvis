import { useEffect, useRef, memo, useState } from 'react';
import * as d3 from 'd3';
import {
  DEFAULT_LABEL_PX,
  SCALE_EXTENT,
  labelCandidates,
  labelText,
  placeLabels,
  viewportTransform,
} from '../utils/graphView';

// Edges are drawn translucent so dense regions read as density; a highlighted
// edge is the exception the user is meant to see.
const EDGE_OPACITY = 0.3;
const HIGHLIGHT_EDGE_OPACITY = 0.9;

const NetworkGraph = memo(({
  nodes,
  links,
  showLabels = false,
  labelStyle = null,
  viewport = null,
  onNodeClick,
  onBackgroundClick,
}) => {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  // Keep refs for callbacks to avoid re-triggering the effect
  const onNodeClickRef = useRef(onNodeClick);
  const onBackgroundClickRef = useRef(onBackgroundClick);

  // Persist the user's pan/zoom across rebuilds (render_update events,
  // label toggle, resize) so the view doesn't snap back to default.
  const zoomTransformRef = useRef(d3.zoomIdentity);
  // A viewport instruction applies once; later renders keep the user's view.
  const appliedViewportRef = useRef(null);
  // Where an in-flight viewport animation is heading. A rebuild (the agent's
  // next render often arrives within the animation) must land there rather
  // than freeze the camera halfway.
  const viewportTargetRef = useRef(null);

  useEffect(() => {
    onNodeClickRef.current = onNodeClick;
    onBackgroundClickRef.current = onBackgroundClick;
  }, [onNodeClick, onBackgroundClick]);

  // Handle resizing
  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height
        });
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    
    // Explicit clean up of listeners before clearing content
    svg.on("click", null);
    svg.on(".zoom", null);
    
    svg.selectAll("*").remove(); // Clear previous

    if (!nodes.length) return;

    // Use dimensions from state if available, else fallback to ref (though ref should be accurate with observer)
    const width = dimensions.width || svgRef.current?.clientWidth || 0;
    const height = dimensions.height || svgRef.current?.clientHeight || 0;

    if (width === 0 || height === 0) return; // Wait for dimensions

    // 0. Bind background click
    svg.on("click", (event) => {
        if (onBackgroundClickRef.current) {
            onBackgroundClickRef.current(event);
        }
    });

    // 1. Create a map for quick node lookup
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    // 2. Determine data extent for scaling
    const xExtent = d3.extent(nodes, d => d.x);
    const yExtent = d3.extent(nodes, d => d.y);
    
    // Handle case where all x or y are same or undefined (fallback)
    const xMin = xExtent[0] !== undefined ? xExtent[0] : -500;
    const xMax = xExtent[1] !== undefined ? xExtent[1] : 500;
    const yMin = yExtent[0] !== undefined ? yExtent[0] : -500;
    const yMax = yExtent[1] !== undefined ? yExtent[1] : 500;

    // Use viewBox to handle scaling automatically
    // Determine the bounding box of the graph content
    const contentWidth = xMax - xMin || 1000;
    const contentHeight = yMax - yMin || 1000;
    
    const padding = Math.max(contentWidth, contentHeight) * 0.1; // 10% padding
    
    const viewBoxX = xMin - padding;
    const viewBoxY = yMin - padding;
    const viewBoxW = contentWidth + 2 * padding;
    const viewBoxH = contentHeight + 2 * padding;
    
    svg.attr("viewBox", `${viewBoxX} ${viewBoxY} ${viewBoxW} ${viewBoxH}`)
       .attr("preserveAspectRatio", "xMidYMid meet");

    // Group for zoomable content
    const g = svg.append("g");
    // viewBox units per screen pixel ("meet" scales by the tighter axis).
    const unitsPerPx = Math.max(viewBoxW / width, viewBoxH / height);

    // Highlighted elements are drawn last so they sit on top.
    const byHighlight = (a, b) => Number(Boolean(a.highlighted)) - Number(Boolean(b.highlighted));
    const orderedLinks = [...links].sort(byHighlight);
    const orderedNodes = [...nodes].sort(byHighlight);

    // 3. Draw Links
    g.append("g")
      .selectAll("line")
      .data(orderedLinks)
      .join("line")
      .attr("x1", d => {
        const sId = typeof d.source === 'object' ? d.source.id : d.source;
        const n = nodeMap.get(sId);
        return n ? n.x : 0;
      })
      .attr("y1", d => {
        const sId = typeof d.source === 'object' ? d.source.id : d.source;
        const n = nodeMap.get(sId);
        return n ? n.y : 0;
      })
      .attr("x2", d => {
        const tId = typeof d.target === 'object' ? d.target.id : d.target;
        const n = nodeMap.get(tId);
        return n ? n.x : 0;
      })
      .attr("y2", d => {
        const tId = typeof d.target === 'object' ? d.target.id : d.target;
        const n = nodeMap.get(tId);
        return n ? n.y : 0;
      })
      .attr("stroke", d => d.color || "#999")
      .attr("stroke-opacity", d => (
        d.highlighted
          ? HIGHLIGHT_EDGE_OPACITY
          // base_opacity: the user's edge opacity (ADR 0029); opacity: dimming.
          : (d.base_opacity ?? EDGE_OPACITY) * (d.opacity !== undefined ? d.opacity : 1)
      ))
      .attr("stroke-width", d => (d.highlighted ? Math.max(d.width || 1, 2) : d.width || 1));

    // 4. Draw Nodes
    const nodeGroup = g.append("g")
      .selectAll("g")
      .data(orderedNodes)
      .join("g")
      .attr("transform", d => `translate(${d.x},${d.y})`)
      .style("cursor", "pointer") // Indicate clickable
      .on("click", (event, d) => {
        // Prevent background click
        event.stopPropagation();
        if (onNodeClickRef.current) {
          onNodeClickRef.current(d);
        }
      });

    nodeGroup.append("circle")
      .attr("r", d => {
         // NetworkX node_size is area. User script uses size * 10.
         // Area = pi * r^2 = size * 10
         // r = sqrt(size * 10 / pi)
         const size = d.size || 5;
         return Math.sqrt(size * 10 / Math.PI);
      })
      .attr("fill", d => d.color || "#69b3a2")
      .attr("opacity", d => d.opacity !== undefined ? d.opacity : 1)
      .attr("stroke", d => (d.highlighted ? "#1f1f1f" : null))
      .attr("stroke-width", d => (d.highlighted ? 1.5 : null))
      .attr("vector-effect", "non-scaling-stroke");

    nodeGroup.append("title")
      .text(d => d.label);

    // 5. Labels: a separate top layer so no node covers a label. Their size is
    // fixed in screen pixels, and overlapping ones are thinned per zoom level.
    const fontPx = labelStyle?.font_size || DEFAULT_LABEL_PX;
    const maxLength = labelStyle?.max_length;
    const radius = d => Math.sqrt((d.size || 5) * 10 / Math.PI);
    const candidates = labelCandidates(nodes, { showLabels });
    const labels = g.append("g")
      .style("pointer-events", "none")
      .selectAll("text")
      .data(candidates)
      .join("text")
      .text(d => labelText(d.label, maxLength))
      .attr("text-anchor", "middle")
      .attr("fill", "#222")
      .attr("stroke", "#fff")
      .attr("stroke-linejoin", "round")
      .attr("paint-order", "stroke")
      .attr("opacity", d => (d.opacity !== undefined ? Math.max(d.opacity, 0.35) : 1));

    let frame = null;
    const layoutLabels = (transform) => {
      const k = transform.k;
      const unit = unitsPerPx / k; // user units per screen pixel at this zoom
      const visible = placeLabels(
        candidates,
        d => [(k * d.x + transform.x) / unitsPerPx, (k * (d.y - radius(d)) + transform.y) / unitsPerPx],
        { fontPx, maxLength },
      );
      labels
        .attr("x", d => d.x)
        .attr("y", d => d.y - radius(d) - 3 * unit)
        .attr("font-size", fontPx * unit)
        .attr("stroke-width", 3 * unit)
        .attr("display", d => (visible.has(d.id) ? null : "none"));
    };

    // 6. Add Zoom/Pan
    const zoom = d3.zoom()
      .scaleExtent(SCALE_EXTENT)
      .on("zoom", (event) => {
        zoomTransformRef.current = event.transform;
        g.attr("transform", event.transform);
        if (frame) cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => layoutLabels(event.transform));
      });

    svg.call(zoom);
    // Restore the previous pan/zoom instead of resetting to identity.
    svg.call(zoom.transform, zoomTransformRef.current);
    layoutLabels(zoomTransformRef.current);

    // 7. A new viewport instruction moves the camera once.
    if (viewport?.nonce && viewport.nonce !== appliedViewportRef.current) {
      appliedViewportRef.current = viewport.nonce;
      const target = viewportTransform(viewport, nodes, {
        x: viewBoxX, y: viewBoxY, width: viewBoxW, height: viewBoxH,
      });
      if (target) {
        const end = d3.zoomIdentity.translate(target.x, target.y).scale(target.k);
        viewportTargetRef.current = end;
        svg.transition()
          .duration(600)
          .call(zoom.transform, end)
          .on("end", () => { viewportTargetRef.current = null; });
      }
    }
    
    // Cleanup on unmount
    return () => {
        if (frame) cancelAnimationFrame(frame);
        svg.interrupt();
        if (viewportTargetRef.current) {
          zoomTransformRef.current = viewportTargetRef.current;
          viewportTargetRef.current = null;
        }
        svg.on("click", null);
        svg.on(".zoom", null);
        svg.selectAll("*").remove();
    };

  }, [nodes, links, showLabels, labelStyle, viewport, dimensions]); // Dependencies updated to exclude callbacks

  return (
    <div
      ref={containerRef}
      data-testid="network-graph"
      style={{ width: '100%', height: '100%', position: 'relative' }}
    >
      <svg ref={svgRef} style={{ width: '100%', height: '100%', display: 'block' }}></svg>
    </div>
  );
});

NetworkGraph.displayName = 'NetworkGraph';

export default NetworkGraph;
