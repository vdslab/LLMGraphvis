import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

const NetworkGraph = ({ nodes, links, onNodeFocus }) => {
  const svgRef = useRef();
  const [contextMenu, setContextMenu] = React.useState(null);

  useEffect(() => {
    const handleClickOutside = () => setContextMenu(null);
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!nodes.length) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    svg.selectAll("*").remove(); // Clear previous

    // 1. Create a map for quick node lookup
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    // 2. Determine data extent for scaling
    const xExtent = d3.extent(nodes, d => d.x);
    const yExtent = d3.extent(nodes, d => d.y);
    
    // Handle case where all x or y are same or undefined (fallback)
    const xMin = xExtent[0] !== undefined ? xExtent[0] : 0;
    const xMax = xExtent[1] !== undefined ? xExtent[1] : 1;
    const yMin = yExtent[0] !== undefined ? yExtent[0] : 0;
    const yMax = yExtent[1] !== undefined ? yExtent[1] : 1;

    const padding = 40;

    const xScale = d3.scaleLinear()
      .domain([xMin, xMax])
      .range([padding, width - padding]);

    const yScale = d3.scaleLinear()
      .domain([yMin, yMax])
      .range([padding, height - padding]);

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
        return n ? xScale(n.x) : 0;
      })
      .attr("y1", d => {
        const sId = typeof d.source === 'object' ? d.source.id : d.source;
        const n = nodeMap.get(sId);
        return n ? yScale(n.y) : 0;
      })
      .attr("x2", d => {
        const tId = typeof d.target === 'object' ? d.target.id : d.target;
        const n = nodeMap.get(tId);
        return n ? xScale(n.x) : 0;
      })
      .attr("y2", d => {
        const tId = typeof d.target === 'object' ? d.target.id : d.target;
        const n = nodeMap.get(tId);
        return n ? yScale(n.y) : 0;
      })
      .attr("stroke", d => d.color || "#999")
      .attr("stroke-opacity", d => d.opacity !== undefined ? d.opacity : 0.6)
      .attr("stroke-width", d => d.width || 1);

    // 4. Draw Nodes
    const node = g.append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("cx", d => xScale(d.x))
      .attr("cy", d => yScale(d.y))
      .attr("r", d => d.size || 5)
      .attr("fill", d => d.color || "#69b3a2")
      .attr("opacity", d => d.opacity !== undefined ? d.opacity : 1)
      .on("contextmenu", (event, d) => {
        event.preventDefault();
        setContextMenu({
          x: event.pageX,
          y: event.pageY,
          nodeId: d.id
        });
      });

    node.append("title")
      .text(d => d.label);

    // 5. Add Zoom/Pan
    const zoom = d3.zoom()
      .scaleExtent([0.1, 10])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
        setContextMenu(null); // Close menu on zoom/pan
      });

    svg.call(zoom);

  }, [nodes, links]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }}></svg>
      {contextMenu && (
        <div
          style={{
            position: 'fixed',
            top: contextMenu.y,
            left: contextMenu.x,
            backgroundColor: 'white',
            border: '1px solid #ccc',
            borderRadius: '4px',
            padding: '5px',
            zIndex: 1000,
            boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
            cursor: 'pointer'
          }}
          onClick={() => {
            if (onNodeFocus) onNodeFocus(contextMenu.nodeId);
            setContextMenu(null);
          }}
        >
          Focus (Ego Network)
        </div>
      )}
    </div>
  );
};

export default NetworkGraph;
