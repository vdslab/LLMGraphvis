import { useEffect, useRef, memo, useState } from 'react';
import * as d3 from 'd3';

const NetworkGraph = memo(({ nodes, links, showLabels = false, onNodeClick, onBackgroundClick }) => {
  const svgRef = useRef();
  const containerRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  // Keep refs for callbacks to avoid re-triggering the effect
  const onNodeClickRef = useRef(onNodeClick);
  const onBackgroundClickRef = useRef(onBackgroundClick);

  // Persist the user's pan/zoom across rebuilds (render_update events,
  // label toggle, resize) so the view doesn't snap back to default.
  const zoomTransformRef = useRef(d3.zoomIdentity);

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

    // 3. Draw Links
    g.append("g")
      .selectAll("line")
      .data(links)
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
      .attr("stroke-opacity", 0.3) // NetworkX default/script specified
      .attr("stroke-width", d => d.width || 1);

    // 4. Draw Nodes
    const nodeGroup = g.append("g")
      .selectAll("g")
      .data(nodes)
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
      .attr("opacity", d => d.opacity !== undefined ? d.opacity : 1);

    if (showLabels) {
        nodeGroup.append("text")
          .text(d => d.label)
          .attr("font-size", "10px") // User might want readable size, 6px is tiny
          .attr("text-anchor", "middle")
          .attr("dy", -10) // Offset above node
          .attr("fill", "#333")
          .style("pointer-events", "none")
          .style("text-shadow", "1px 1px 1px white"); // Readability
    }

    nodeGroup.append("title")
      .text(d => d.label);

    // 5. Add Zoom/Pan
    const zoom = d3.zoom()
      .scaleExtent([0.1, 10])
      .on("zoom", (event) => {
        zoomTransformRef.current = event.transform;
        g.attr("transform", event.transform);
      });

    svg.call(zoom);
    // Restore the previous pan/zoom instead of resetting to identity.
    svg.call(zoom.transform, zoomTransformRef.current);
    
    // Cleanup on unmount
    return () => {
        svg.on("click", null);
        svg.on(".zoom", null);
        svg.selectAll("*").remove();
    };

  }, [nodes, links, showLabels, dimensions]); // Dependencies updated to exclude callbacks

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      <svg ref={svgRef} style={{ width: '100%', height: '100%', display: 'block' }}></svg>
    </div>
  );
});

export default NetworkGraph;
